"""AI provider abstraction for SurvivalEngine.

Two providers supported, both run inside the `survival` tmux session so the
existing cmux-based UI (survival pane → `tmux attach-session -t survival`)
keeps working uniformly. The differences are isolated to:

  - launch command (which binary, which flags)
  - session id persistence (per-provider file)
  - where JSONL conversation logs live on disk
  - how to map raw JSONL events onto the supervisor's message schema
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from myagent.config import ClaudeSettings, CodexSettings


@dataclass
class ProviderLaunch:
    """Shell command to start the AI CLI inside a fresh tmux pane."""
    cmd: str              # full shell command line, e.g. `claude --resume XYZ`
    is_resume: bool       # True if this continues an existing session


class AIProvider(ABC):
    """Interface a SurvivalEngine uses to drive a specific AI CLI."""

    name: str = "base"

    @abstractmethod
    def build_launch(self, session_id: str | None) -> ProviderLaunch:
        """Build the command to launch the CLI (fresh or resumed)."""

    @property
    @abstractmethod
    def session_file_name(self) -> str:
        """Filename (under workspace) used to persist the session id."""

    @abstractmethod
    def find_jsonl_path(self, session_id: str) -> Path | None:
        """Locate the JSONL transcript for a given session id, if present."""

    @abstractmethod
    def normalize_event(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        """Map one raw JSONL line to the supervisor's unified message schema,
        or return None to drop it.

        Unified schema matches Claude's existing shape so downstream code
        (supervisor, web UI, scanner) doesn't need per-provider branches:
            {"type": "user"|"assistant"|"system"|"progress", "content": str, ...}
        """


# ---------------------------------------------------------------------------
# Claude — existing behavior, wrapped
# ---------------------------------------------------------------------------

class ClaudeTmuxProvider(AIProvider):
    name = "claude"

    def __init__(self, settings: ClaudeSettings, projects_dir: str = "~/.claude/projects"):
        self._s = settings
        self._projects_dir = Path(os.path.expanduser(projects_dir))

    def build_launch(self, session_id: str | None) -> ProviderLaunch:
        # Keep parity with the old hardcoded command in survival.py:648
        cmd = f"{self._s.binary} --dangerously-skip-permissions --chrome"
        if session_id:
            cmd += f" --resume {session_id}"
            return ProviderLaunch(cmd=cmd, is_resume=True)
        return ProviderLaunch(cmd=cmd, is_resume=False)

    @property
    def session_file_name(self) -> str:
        return ".claude_session_id"

    def find_jsonl_path(self, session_id: str) -> Path | None:
        if not self._projects_dir.exists():
            return None
        for project_dir in self._projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            p = project_dir / f"{session_id}.jsonl"
            if p.exists():
                return p
        return None

    def normalize_event(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        t = raw.get("type", "")
        if t in ("user", "assistant", "system", "progress"):
            return raw
        return None


# ---------------------------------------------------------------------------
# Codex — `codex` interactive inside tmux, JSONL under ~/.codex/sessions
# ---------------------------------------------------------------------------

class CodexTmuxProvider(AIProvider):
    name = "codex"

    def __init__(self, settings: CodexSettings):
        self._s = settings
        self._sessions_dir = Path(os.path.expanduser(settings.sessions_dir))

    def build_launch(self, session_id: str | None) -> ProviderLaunch:
        extra = " ".join(self._s.args) if self._s.args else ""
        config_flags = []
        if self._s.model:
            config_flags.append(f'-c model="{self._s.model}"')
        if self._s.profile:
            config_flags.append(f"--profile {self._s.profile}")
        cfg = " ".join(config_flags)

        if session_id:
            parts = [self._s.binary, "resume", session_id]
            if cfg:
                parts.insert(1, cfg)
            if extra:
                parts.append(extra)
            return ProviderLaunch(cmd=" ".join(parts), is_resume=True)

        parts = [self._s.binary]
        if cfg:
            parts.append(cfg)
        if extra:
            parts.append(extra)
        return ProviderLaunch(cmd=" ".join(parts), is_resume=False)

    @property
    def session_file_name(self) -> str:
        return ".codex_session_id"

    def find_jsonl_path(self, session_id: str) -> Path | None:
        """Codex stores sessions under YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl."""
        if not self._sessions_dir.exists():
            return None
        # Narrow search by scanning recent day dirs; fallback to full walk.
        matches = list(self._sessions_dir.rglob(f"rollout-*-{session_id}.jsonl"))
        if matches:
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return matches[0]
        return None

    def normalize_event(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        """Map a codex rollout JSONL line to the unified schema.

        Codex event shapes seen in rollout files:
            {"type":"session_meta", "payload":{...}}
            {"type":"response_item", "payload":{"type":"message","role":"user"|"assistant","content":[...]}}
            {"type":"response_item", "payload":{"type":"reasoning",...}}
            {"type":"response_item", "payload":{"type":"function_call",...}}
            {"type":"event_msg", "payload":{"type":"agent_message"|"turn_started"|...}}
        """
        t = raw.get("type", "")
        payload = raw.get("payload") or {}

        if t == "session_meta":
            return {"type": "system", "content": "[codex session started]", "raw": raw}

        if t == "response_item":
            itype = payload.get("type", "")
            if itype == "message":
                role = payload.get("role", "assistant")
                content = _extract_codex_content(payload.get("content"))
                if role in ("user", "assistant") and content:
                    return {"type": role, "content": content, "raw": raw}
            elif itype == "reasoning":
                summary = payload.get("summary") or []
                text = " ".join(
                    s.get("text", "") for s in summary if isinstance(s, dict)
                ).strip()
                if text:
                    return {"type": "assistant", "content": f"[reasoning] {text}", "raw": raw}
            elif itype in ("function_call", "local_shell_call", "custom_tool_call"):
                name = payload.get("name") or payload.get("type")
                args = payload.get("arguments") or payload.get("action") or {}
                return {
                    "type": "assistant",
                    "content": f"[tool:{name}] {args}"[:2000],
                    "raw": raw,
                }

        if t == "event_msg":
            etype = payload.get("type", "")
            if etype == "agent_message":
                return {
                    "type": "assistant",
                    "content": payload.get("message", ""),
                    "raw": raw,
                }
            if etype in ("turn_started", "turn_completed", "turn_failed"):
                return {"type": "progress", "content": etype, "raw": raw}

        return None


def _extract_codex_content(content: Any) -> str:
    """Codex message.content is a list of blocks like
    [{"type":"input_text"|"output_text","text":"..."}]."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    out = []
    for block in content:
        if isinstance(block, dict):
            txt = block.get("text") or block.get("content") or ""
            if isinstance(txt, str):
                out.append(txt)
    return "\n".join(out).strip()


def build_provider(provider_name: str, claude_cfg: ClaudeSettings, codex_cfg: CodexSettings,
                   claude_projects_dir: str = "~/.claude/projects") -> AIProvider:
    """Factory — pick a provider by name."""
    if provider_name == "codex":
        return CodexTmuxProvider(codex_cfg)
    return ClaudeTmuxProvider(claude_cfg, projects_dir=claude_projects_dir)
