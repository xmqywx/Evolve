"""ObserverEngine — the Observer digital human runtime loop.

S1 multi-DH roadmap, Task 9.
See: docs/specs/2026-04-24-s1-observer-digital-human.md § 6

Design differences from SurvivalEngine:
- Timer-driven (30 min sleep), not watchdog-driven
- No capture-pane fallback (observer produces via API only, screen doesn't matter)
- No Feishu report call (not in S1 scope)
- No --resume recovery prompt (observer is context-cheap; restart reloads from scratch)
- Self-contained crash supervisor with exponential backoff + 24h circuit breaker
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from myagent.ai_provider import build_provider
from myagent.digital_humans import (
    DigitalHumanRegistry,
    invalidate_token,
    issue_token,
)

logger = logging.getLogger(__name__)

CMUX_BIN = "/Applications/cmux.app/Contents/Resources/bin/cmux"
DH_ID = "observer"
CONTEXT_CAP_BYTES = 12_288  # ≤12 KB per spec §11


class CmuxError(Exception):
    pass


class ObserverEngine:
    """Runtime controller for the Observer digital human.

    Owns: one cmux workspace, one auth token, a timer loop, and crash state.
    Does NOT own: any writes to agent_deliverables/workflows/upgrades/reviews
    (role-permission middleware guarantees Observer can't reach those endpoints).
    """

    def __init__(self, db, registry: DigitalHumanRegistry, config, port: int = 3818):
        self.db = db
        self.registry = registry
        self.config = config
        self.port = port
        self._running = False
        self._task: asyncio.Task | None = None
        self._workspace_id: str | None = None
        self._crash_timestamps: list[float] = []
        # Resolve provider for this DH's cmux session.
        dh_cfg = config.digital_humans.get(DH_ID)
        provider_name = dh_cfg.provider if dh_cfg else "codex"
        self._provider = build_provider(
            provider_name,
            claude_cfg=config.claude,
            codex_cfg=config.codex,
        )

    # ---- cmux helpers (mirror SurvivalEngine) ----

    @staticmethod
    def _cmux_available() -> bool:
        return Path(CMUX_BIN).exists()

    @staticmethod
    async def _run_exec(*args: str) -> tuple[int, str]:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        out = stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0 and stderr:
            out += "\n" + stderr.decode("utf-8", errors="replace").strip()
        return proc.returncode or 0, out

    async def _cmux(self, *args: str) -> tuple[int, str]:
        return await self._run_exec(CMUX_BIN, *args)

    async def _cmux_find_by_name(self, name: str) -> str | None:
        code, out = await self._cmux("--id-format", "uuids", "list-workspaces")
        if code != 0:
            return None
        for line in out.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and parts[1].strip() == name:
                return parts[0]
        return None

    # ---- Lifecycle ----

    async def start(self) -> dict:
        """Spawn cmux workspace, mint token, inject into env, start loop."""
        if self._running:
            return {"status": "already_running"}
        if not self._cmux_available():
            return {"status": "error", "error": "cmux not installed"}
        cfg = self.config.digital_humans.get(DH_ID)
        if not cfg:
            return {"status": "error", "error": "observer not configured"}

        # Close any lingering workspace with same name from prior runs
        existing = await self._cmux_find_by_name(cfg.cmux_session)
        if existing:
            await self._cmux("close-workspace", "--workspace", existing)

        # Mint fresh token
        token = issue_token(self.registry, DH_ID)

        # Build shell command: export env then exec the provider CLI
        launch = self._provider.build_launch(None)
        exports = [
            "unset CLAUDECODE",
            f"export MYAGENT_URL=http://localhost:{self.port}",
            f"export MYAGENT_DH_TOKEN={token}",
        ]
        shell_cmd = "; ".join(exports) + f"; exec {launch.cmd}"

        code, out = await self._cmux(
            "new-workspace",
            "--name", cfg.cmux_session,
            "--cwd", self.config.agent.data_dir,
            "--command", shell_cmd,
        )
        if code != 0:
            invalidate_token(self.registry, DH_ID)
            logger.error("observer cmux spawn failed: %s", out)
            return {"status": "error", "error": out}

        await asyncio.sleep(0.4)
        uuid = await self._cmux_find_by_name(cfg.cmux_session)
        if not uuid:
            invalidate_token(self.registry, DH_ID)
            logger.error("observer workspace UUID not found after spawn")
            return {"status": "error", "error": "uuid_not_found"}
        self._workspace_id = uuid
        self.registry.mark_started(DH_ID, cmux_session=cfg.cmux_session)

        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("ObserverEngine started (workspace=%s)", uuid[:8])
        return {"status": "started", "workspace": uuid}

    async def stop(self) -> dict:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._workspace_id:
            await self._cmux("close-workspace", "--workspace", self._workspace_id)
            self._workspace_id = None
        invalidate_token(self.registry, DH_ID)
        logger.info("ObserverEngine stopped")
        return {"status": "stopped"}

    # ---- Runtime loop ----

    async def _loop(self):
        cfg = self.config.digital_humans.get(DH_ID)
        interval = cfg.heartbeat_interval_secs if cfg else 1800
        # Initial kick: send identity prompt shortly after startup so the LLM
        # has context before its first heartbeat.
        try:
            await asyncio.sleep(5)
            if self._running:
                await self._send_initial_prompt()
        except Exception:
            logger.exception("observer initial prompt failed")

        while self._running:
            try:
                await asyncio.sleep(interval)
                if not self._running:
                    break
                await self._single_iteration()
            except asyncio.CancelledError:
                raise
            except CmuxError as e:
                await self._handle_crash(f"cmux: {e}")
            except Exception as e:
                logger.exception("observer iteration error")
                await self._handle_crash(f"unexpected: {type(e).__name__}: {e}")

    async def _single_iteration(self):
        """One timer tick: build fresh context, send prompt to cmux session."""
        ctx = await self._build_context()
        prompt = await self._render_prompt(ctx)
        await self._send_to_cmux(prompt)

    async def _send_initial_prompt(self):
        """Send Observer identity prompt on first start."""
        persona_path = (
            Path(self.config.agent.persona_dir) / DH_ID / "identity.md"
        )
        if persona_path.exists():
            identity = persona_path.read_text(encoding="utf-8")[:CONTEXT_CAP_BYTES]
            await self._send_to_cmux(identity)

    async def _build_context(self) -> dict:
        """Assemble context from DB + git log for the next LLM turn."""
        exec_hb = await self.db.list_heartbeats(limit=3, digital_human_id="executor")
        exec_dl = await self.db.list_deliverables(limit=3, digital_human_id="executor")
        own_disc = await self.db.list_discoveries(limit=10, digital_human_id=DH_ID)
        # Git log — cap 4KB; ignore failures (no git is not fatal)
        git_log = ""
        try:
            res = subprocess.run(
                ["git", "log", "--since=2 hours ago", "--oneline"],
                cwd=self.config.agent.data_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            git_log = (res.stdout or "")[:4096]
        except Exception:
            pass
        return {
            "exec_heartbeats": exec_hb,
            "exec_deliverables": exec_dl,
            "own_discoveries": own_disc,
            "git_log_2h": git_log,
            "now": datetime.now(timezone.utc).isoformat(),
        }

    async def _render_prompt(self, ctx: dict) -> str:
        lines = [
            f"## Context refresh @ {ctx['now']}",
            "",
            "### Executor 最近 heartbeat",
        ]
        for hb in ctx["exec_heartbeats"]:
            lines.append(f"- [{hb.get('activity','?')}] {hb.get('description','')[:100]}")
        lines.append("")
        lines.append("### Executor 最近 deliverable")
        for dl in ctx["exec_deliverables"]:
            lines.append(f"- [{dl.get('type','?')}] {dl.get('title','')[:80]}")
        lines.append("")
        lines.append("### 你最近发的 discovery (防重复)")
        for d in ctx["own_discoveries"]:
            lines.append(f"- [{d.get('category','?')}] {d.get('title','')[:80]}")
        lines.append("")
        if ctx["git_log_2h"]:
            lines.append("### Git log (过去 2 小时)")
            lines.append(ctx["git_log_2h"][:2000])
        lines.append("")
        lines.append(
            "请调用 heartbeat 汇报当前状态 (即使 idle 也要发)。"
            "如果看到值得 Ying 注意的信号，调用 discovery。"
        )
        out = "\n".join(lines)
        return out[:CONTEXT_CAP_BYTES]

    async def _send_to_cmux(self, text: str):
        if not self._workspace_id:
            raise CmuxError("no workspace")
        code, out = await self._cmux("send", "--workspace", self._workspace_id, text)
        if code != 0:
            raise CmuxError(f"send failed: {out}")
        await asyncio.sleep(0.2)
        code, out = await self._cmux(
            "send-key", "--workspace", self._workspace_id, "Enter"
        )
        if code != 0:
            raise CmuxError(f"send-key failed: {out}")

    # ---- Crash supervisor ----

    async def _handle_crash(self, reason: str):
        now = time.time()
        # Drop entries older than 24h
        self._crash_timestamps = [t for t in self._crash_timestamps if now - t < 86400]
        self._crash_timestamps.append(now)
        self.registry.record_crash(DH_ID, reason=reason)
        logger.warning("observer crash (count=%d): %s",
                       len(self._crash_timestamps), reason)
        if len(self._crash_timestamps) > 10:
            logger.error("observer crash loop (>10/24h); stopping")
            await self.stop()
            return
        # Exponential backoff: 30, 60, 120, 240, 480 (cap)
        backoff = min(30 * (2 ** (len(self._crash_timestamps) - 1)), 480)
        logger.info("observer backoff %ds before restart attempt", backoff)
        await asyncio.sleep(backoff)
        # Attempt to re-establish cmux workspace
        cfg = self.config.digital_humans.get(DH_ID)
        if not cfg or not self._running:
            return
        existing = await self._cmux_find_by_name(cfg.cmux_session)
        if existing:
            await self._cmux("close-workspace", "--workspace", existing)
        # Re-mint token + re-spawn workspace
        token = issue_token(self.registry, DH_ID)
        launch = self._provider.build_launch(None)
        shell_cmd = (
            "unset CLAUDECODE; "
            f"export MYAGENT_URL=http://localhost:{self.port}; "
            f"export MYAGENT_DH_TOKEN={token}; "
            f"exec {launch.cmd}"
        )
        code, out = await self._cmux(
            "new-workspace",
            "--name", cfg.cmux_session,
            "--cwd", self.config.agent.data_dir,
            "--command", shell_cmd,
        )
        if code != 0:
            logger.error("observer respawn failed: %s", out)
            invalidate_token(self.registry, DH_ID)
            return
        await asyncio.sleep(0.4)
        self._workspace_id = await self._cmux_find_by_name(cfg.cmux_session)
        self.registry.mark_started(DH_ID, cmux_session=cfg.cmux_session)
