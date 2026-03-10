"""Session scanner - discovers Claude processes and reads JSONL session files."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Awaitable

from myagent.config import ScannerSettings
from myagent.models import SessionInfo, SessionStatus

logger = logging.getLogger(__name__)

# Internal Claude event types to skip
SKIP_TYPES = {"progress", "file-history-snapshot", "queue-operation", "change", "last-prompt"}


def parse_ps_output(lines: list[str]) -> list[dict[str, Any]]:
    """Parse ps output lines for claude processes."""
    results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(
            r"\s*(\d+)\s+(\S+)\s+(.+?)\s{2,}(claude\s.*|/.*claude\s.*)",
            line,
        )
        if not match:
            # Try simpler pattern
            parts = line.split()
            if len(parts) >= 4 and parts[0].isdigit():
                results.append({"pid": int(parts[0]), "tty": parts[1] if parts[1] != "??" else None})
                continue
            continue
        results.append({"pid": int(match.group(1)), "tty": match.group(2) if match.group(2) != "??" else None})
    return results


def parse_jsonl_messages(lines: list[str]) -> list[dict[str, Any]]:
    """Parse JSONL lines, returning only conversation messages."""
    messages = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg_type = data.get("type", "")
        if msg_type in SKIP_TYPES:
            continue
        if msg_type in ("user", "assistant", "system"):
            messages.append(data)
    return messages


def extract_project_name(cwd: str) -> str:
    """Extract short project name from working directory path."""
    parts = Path(cwd).parts
    if len(parts) >= 2:
        return parts[-1]
    return cwd


class SessionScanner:
    """Scans for Claude processes and reads their session JSONL files."""

    def __init__(
        self,
        settings: ScannerSettings,
        on_change: Callable[[list[SessionInfo], dict[str, list[dict]]], Awaitable[None]] | None = None,
    ) -> None:
        self._settings = settings
        self._on_change = on_change
        self._running = False
        self._sessions: dict[str, SessionInfo] = {}
        self._message_cache: dict[str, list[dict]] = {}

    @property
    def sessions(self) -> dict[str, SessionInfo]:
        return dict(self._sessions)

    def get_messages(self, session_id: str) -> list[dict]:
        return list(self._message_cache.get(session_id, []))

    async def scan_processes(self) -> list[dict[str, Any]]:
        """Scan for running claude processes."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ps", "-eo", "pid,tty,command",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            lines = stdout.decode().split("\n")
            claude_lines = [
                l for l in lines
                if "claude" in l and "grep" not in l
                and "node" not in l and "mcp" not in l
            ]
            return parse_ps_output(claude_lines)
        except Exception:
            logger.exception("Failed to scan processes")
            return []

    async def get_process_cwd(self, pid: int) -> str | None:
        """Get working directory of a process via lsof."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "lsof", "-p", str(pid),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            for line in stdout.decode().split("\n"):
                if "cwd" in line:
                    parts = line.split()
                    if parts:
                        return parts[-1]
        except Exception:
            pass
        return None

    def scan_jsonl_files(self) -> dict[str, Path]:
        """Find all session JSONL files across all project dirs."""
        projects_dir = Path(os.path.expanduser(self._settings.claude_projects_dir))
        result = {}
        if not projects_dir.exists():
            return result
        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            for jsonl_file in project_dir.glob("*.jsonl"):
                session_id = jsonl_file.stem
                if len(session_id) < 30:
                    continue
                result[session_id] = jsonl_file
        return result

    def read_session_messages(self, jsonl_path: Path) -> list[dict]:
        """Read and parse messages from a JSONL session file."""
        try:
            text = jsonl_path.read_text(encoding="utf-8")
            lines = text.split("\n")
            messages = parse_jsonl_messages(lines)
            max_cached = self._settings.max_messages_cached
            return messages[-max_cached:] if len(messages) > max_cached else messages
        except Exception:
            logger.exception("Failed to read session file: %s", jsonl_path)
            return []

    async def run_scan_loop(self) -> None:
        """Main scan loop."""
        self._running = True
        while self._running:
            try:
                await self._scan_once()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Scan error")
            await asyncio.sleep(self._settings.process_interval)

    async def _scan_once(self) -> None:
        """Perform one full scan cycle."""
        # 1. Get running processes
        processes = await self.scan_processes()
        pid_to_info: dict[int, dict] = {}
        for p in processes:
            pid = p["pid"]
            cwd = await self.get_process_cwd(pid)
            if cwd:
                pid_to_info[pid] = {**p, "cwd": cwd}

        # 2. Scan JSONL files
        jsonl_files = self.scan_jsonl_files()

        # 3. Match and update sessions
        updated = False
        new_messages: dict[str, list[dict]] = {}

        for session_id, jsonl_path in jsonl_files.items():
            messages = self.read_session_messages(jsonl_path)
            if not messages:
                continue

            first_msg = messages[0]
            cwd = first_msg.get("cwd", "")
            if not cwd:
                continue

            # Check if process is still running
            pid = None
            for p_pid, p_info in pid_to_info.items():
                if p_info.get("cwd") == cwd:
                    pid = p_pid
                    break

            status = SessionStatus.ACTIVE if pid is not None else SessionStatus.FINISHED

            session = SessionInfo(
                id=session_id,
                pid=pid,
                cwd=cwd,
                project=extract_project_name(cwd),
                tty=pid_to_info.get(pid, {}).get("tty") if pid else None,
                started_at=datetime.now(timezone.utc),
                last_active=datetime.now(timezone.utc),
                status=status,
            )

            old = self._sessions.get(session.id)
            old_msg_count = len(self._message_cache.get(session.id, []))

            self._sessions[session.id] = session
            self._message_cache[session.id] = messages

            if old is None or old.status != session.status or len(messages) != old_msg_count:
                updated = True
                new_messages[session.id] = messages

        if updated and self._on_change:
            await self._on_change(list(self._sessions.values()), new_messages)

    def stop(self) -> None:
        self._running = False
