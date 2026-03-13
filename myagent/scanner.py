"""Session scanner - discovers Claude processes and reads JSONL session files."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Awaitable

from myagent.config import ScannerSettings
from myagent.models import SessionInfo, SessionStatus

logger = logging.getLogger(__name__)

# Internal Claude event types to skip
SKIP_TYPES = {"progress", "file-history-snapshot", "queue-operation", "change", "last-prompt"}

# Only consider JSONL files modified in the last 24 hours
RECENT_THRESHOLD_SECS = 86400


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


def encode_cwd_to_dirname(cwd: str) -> str:
    """Encode a filesystem path to Claude's project directory name format.

    Claude replaces '/' with '-' in the path.
    e.g. '/Users/ying/Documents/MyAgent' -> '-Users-ying-Documents-MyAgent'
    """
    return cwd.replace("/", "-")


def decode_project_dir_name(dirname: str) -> str:
    """Best-effort decode of Claude project directory name back to path.

    Not perfectly reversible since '-' in original paths is ambiguous.
    Use encode_cwd_to_dirname for matching instead.
    """
    if dirname.startswith("-"):
        return "/" + dirname[1:].replace("-", "/")
    return dirname.replace("-", "/")


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
        # Track file sizes to avoid re-reading unchanged files
        self._file_sizes: dict[str, int] = {}

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
            claude_lines = []
            for l in lines:
                # Must contain "claude" but filter out non-claude processes
                if "claude" not in l or "grep" in l:
                    continue
                # Skip shell wrappers that just happen to reference .claude/ paths
                if "/bin/zsh" in l or "/bin/bash" in l or "/bin/sh" in l:
                    continue
                # Skip node/bun/mcp processes
                if "node " in l or "/bun " in l or "mcp" in l:
                    continue
                claude_lines.append(l)
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

    def scan_jsonl_files(
        self, only_recent: bool = True, active_dirnames: set[str] | None = None,
    ) -> dict[str, Path]:
        """Find session JSONL files.

        For active_dirnames (directories with running processes), always include
        the most recently modified JSONL file regardless of age.
        For other directories, only include files modified within RECENT_THRESHOLD_SECS.
        """
        projects_dir = Path(os.path.expanduser(self._settings.claude_projects_dir))
        result = {}
        if not projects_dir.exists():
            return result
        now = time.time()
        active_dirnames = active_dirnames or set()

        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue

            is_active_dir = project_dir.name in active_dirnames
            best_for_active: tuple[float, str, Path] | None = None

            for jsonl_file in project_dir.glob("*.jsonl"):
                session_id = jsonl_file.stem
                if len(session_id) < 30:
                    continue
                try:
                    mtime = jsonl_file.stat().st_mtime
                except OSError:
                    continue

                if only_recent and now - mtime <= RECENT_THRESHOLD_SECS:
                    result[session_id] = jsonl_file
                elif is_active_dir:
                    # Track the most recent file for active directories
                    if best_for_active is None or mtime > best_for_active[0]:
                        best_for_active = (mtime, session_id, jsonl_file)

            # For active dirs, ensure at least the latest JSONL is included
            if best_for_active and best_for_active[1] not in result:
                result[best_for_active[1]] = best_for_active[2]

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
        """Main scan loop (polling fallback)."""
        self._running = True
        while self._running:
            try:
                await self._scan_once()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Scan error")
            await asyncio.sleep(self._settings.process_interval)

    async def run_watch_loop(self) -> None:
        """File-watching loop using watchfiles. Falls back to polling on error."""
        try:
            from watchfiles import awatch, Change
        except ImportError:
            logger.warning("watchfiles not installed, falling back to polling")
            await self.run_scan_loop()
            return

        projects_dir = Path(os.path.expanduser(self._settings.claude_projects_dir))
        if not projects_dir.exists():
            logger.warning("Projects dir %s not found, falling back to polling", projects_dir)
            await self.run_scan_loop()
            return

        self._running = True
        # Do an initial full scan
        try:
            await self._scan_once()
        except Exception:
            logger.exception("Initial scan error")

        # Also run a slow poll for process changes (every 30s) alongside file watch
        async def _slow_poll():
            while self._running:
                await asyncio.sleep(30)
                try:
                    await self._scan_once()
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.exception("Slow poll scan error")

        poll_task = asyncio.create_task(_slow_poll())

        try:
            async for changes in awatch(projects_dir, recursive=True, step=500):
                if not self._running:
                    break
                # Filter: only react to .jsonl file changes
                jsonl_changed = any(
                    str(path).endswith('.jsonl')
                    for change_type, path in changes
                    if change_type in (Change.modified, Change.added)
                )
                if jsonl_changed:
                    try:
                        await self._scan_once()
                    except Exception:
                        logger.exception("Watch-triggered scan error")
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("watchfiles error, falling back to polling")
            await self.run_scan_loop()
        finally:
            poll_task.cancel()
            try:
                await poll_task
            except asyncio.CancelledError:
                pass

    def _match_pid_to_dirname(
        self, parent_dirname: str, pid_to_info: dict[int, dict], claimed_pids: set[int],
    ) -> int | None:
        """Match a JSONL parent dirname to a running process PID.

        Supports both exact match and prefix match (process cwd may be a subdirectory).
        """
        for pid, info in pid_to_info.items():
            if pid in claimed_pids:
                continue
            proc_encoded = encode_cwd_to_dirname(info["cwd"])
            # Exact match or process is in a subdirectory of this project
            if proc_encoded == parent_dirname or proc_encoded.startswith(parent_dirname + "-"):
                return pid
        return None

    async def _scan_once(self) -> None:
        """Perform one full scan cycle."""
        # 1. Get running processes
        processes = await self.scan_processes()
        pid_set: set[int] = set()
        pid_to_info: dict[int, dict] = {}
        for p in processes:
            pid = p["pid"]
            pid_set.add(pid)
            cwd = await self.get_process_cwd(pid)
            if cwd:
                pid_to_info[pid] = {**p, "cwd": cwd}

        # 2. Scan JSONL files (include dirs with running processes)
        # Build active_dirnames from process cwds
        active_dirnames = set()
        projects_dir = Path(os.path.expanduser(self._settings.claude_projects_dir))
        for info in pid_to_info.values():
            encoded = encode_cwd_to_dirname(info["cwd"])
            active_dirnames.add(encoded)
            # If exact dir doesn't exist, check if any project dir is a prefix
            # (process may be in a subdirectory of the project)
            if not (projects_dir / encoded).exists():
                for d in projects_dir.iterdir():
                    if d.is_dir() and encoded.startswith(d.name + "-"):
                        active_dirnames.add(d.name)
                        break
        jsonl_files = self.scan_jsonl_files(only_recent=True, active_dirnames=active_dirnames)

        # 3. Match and update sessions from JSONL files
        updated_sessions: list[SessionInfo] = []
        new_messages: dict[str, list[dict]] = {}
        # Pre-claim PIDs from existing active sessions (for skipped unchanged files)
        claimed_pids: set[int] = set()
        for s in self._sessions.values():
            if s.status == SessionStatus.ACTIVE and s.pid and not s.id.startswith("proc-"):
                claimed_pids.add(s.pid)

        # Noise patterns to filter out
        _NOISE_DIRS = {"observer-sessions", ".claude-mem", "claude-plugins"}

        for session_id, jsonl_path in jsonl_files.items():
            # Skip noise directories
            parent_name = jsonl_path.parent.name.lower()
            if any(noise in parent_name for noise in _NOISE_DIRS):
                continue

            # Skip files that haven't changed (same size)
            try:
                file_size = jsonl_path.stat().st_size
            except OSError:
                continue
            old_size = self._file_sizes.get(session_id, 0)
            if file_size == old_size and session_id in self._sessions:
                continue
            self._file_sizes[session_id] = file_size

            messages = self.read_session_messages(jsonl_path)

            # Decode cwd from parent directory name
            cwd = decode_project_dir_name(jsonl_path.parent.name)
            if not cwd:
                continue

            parent_dirname = jsonl_path.parent.name
            pid = self._match_pid_to_dirname(parent_dirname, pid_to_info, claimed_pids)
            if pid is not None:
                claimed_pids.add(pid)

            # Determine status
            try:
                mtime = jsonl_path.stat().st_mtime
                file_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
                recently_modified = (time.time() - mtime) < 120
            except OSError:
                file_dt = datetime.now(timezone.utc)
                recently_modified = False

            if pid is not None:
                status = SessionStatus.ACTIVE
            elif recently_modified:
                status = SessionStatus.IDLE
            else:
                status = SessionStatus.FINISHED

            old_session = self._sessions.get(session_id)
            started_at = old_session.started_at if old_session else file_dt

            session = SessionInfo(
                id=session_id,
                pid=pid if status == SessionStatus.ACTIVE else None,
                cwd=cwd,
                project=extract_project_name(cwd),
                tty=pid_to_info.get(pid, {}).get("tty") if pid else None,
                started_at=started_at,
                last_active=file_dt,
                status=status,
            )

            self._sessions[session_id] = session
            self._message_cache[session_id] = messages
            updated_sessions.append(session)
            new_messages[session_id] = messages

        # 4. Create sessions for running processes that have no JSONL match
        for pid, info in pid_to_info.items():
            if pid in claimed_pids:
                continue
            cwd = info["cwd"]
            session_id = f"proc-{pid}"
            now = datetime.now(timezone.utc)

            old_session = self._sessions.get(session_id)
            started_at = old_session.started_at if old_session else now

            session = SessionInfo(
                id=session_id,
                pid=pid,
                cwd=cwd,
                project=extract_project_name(cwd),
                tty=info.get("tty"),
                started_at=started_at,
                last_active=now,
                status=SessionStatus.ACTIVE,
            )

            if old_session is None or old_session.status != session.status:
                self._sessions[session_id] = session
                updated_sessions.append(session)

        # 5. Mark sessions as finished if their process is gone
        #    But skip if session was recently active (within 5 min) — resume commands
        #    can cause temporary PID absence
        now = datetime.now(timezone.utc)
        for sid, s in list(self._sessions.items()):
            if s.status == SessionStatus.ACTIVE and s.pid and s.pid not in pid_set:
                age = (now - s.last_active).total_seconds()
                if age < 300:  # 5 minutes grace period
                    continue
                s_updated = s.model_copy(update={"status": SessionStatus.FINISHED, "pid": None})
                self._sessions[sid] = s_updated
                updated_sessions.append(s_updated)

        if updated_sessions and self._on_change:
            await self._on_change(updated_sessions, new_messages)

    def stop(self) -> None:
        self._running = False
