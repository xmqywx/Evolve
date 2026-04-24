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
from myagent.dh_config import augment_codex_cmd, resolve
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

    async def _cmux_workspace_alive(self) -> bool:
        """Return True if our tracked workspace UUID still shows up in
        `cmux list-workspaces`. Conservative: on CLI error return True
        (can't tell, prefer false-alive over false-dead churn)."""
        if not self._workspace_id:
            return False
        code, out = await self._cmux("--id-format", "uuids", "list-workspaces")
        if code != 0:
            return True
        for line in out.splitlines():
            if line.strip().startswith(self._workspace_id):
                return True
        return False

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

        # DH-sovereign effective config (model / prompt_file / mcp).
        try:
            resolved = resolve(self.config, DH_ID)
        except KeyError:
            return {"status": "error", "error": "observer not configured"}
        self._resolved = resolved

        # Close any lingering workspace with same name from prior runs
        existing = await self._cmux_find_by_name(cfg.cmux_session)
        if existing:
            await self._cmux("close-workspace", "--workspace", existing)

        # Mint fresh token
        token = issue_token(self.registry, DH_ID)

        # Build shell command: export env then exec the provider CLI,
        # augmented with DH-specific codex -c overrides (model / mcp).
        launch = self._provider.build_launch(None)
        global_codex_model = getattr(
            getattr(self.config, "codex", None), "model", ""
        ) or ""
        launch_cmd = (
            augment_codex_cmd(launch.cmd, resolved, global_codex_model)
            if resolved.provider == "codex"
            else launch.cmd
        )
        exports = [
            "unset CLAUDECODE",
            f"export MYAGENT_URL=http://localhost:{self.port}",
            f"export MYAGENT_DH_TOKEN={token}",
        ]
        shell_cmd = "; ".join(exports) + f"; exec {launch_cmd}"

        # Use dedicated observer workspace dir (sibling of survival's workspace).
        # Falls back to survival.workspace if the observer subdir doesn't exist.
        obs_workspace = Path(self.config.survival.workspace) / "observer"
        obs_workspace.mkdir(parents=True, exist_ok=True)

        code, out = await self._cmux(
            "new-workspace",
            "--name", cfg.cmux_session,
            "--cwd", str(obs_workspace),
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
        # Initial kick: send identity prompt after codex TUI is ready.
        # Previously used a fixed 5s sleep; codex's trust prompt or slow
        # TUI init caused workspace death before we sent, leading to
        # 'Workspace not found' errors (see S1 day-0 log).
        try:
            if self._running:
                await self._wait_for_cmux_ready(max_secs=30)
            if self._running:
                await self._send_initial_prompt()
        except Exception:
            logger.exception("observer initial prompt failed")

        # Runtime watchdog: wake every WATCHDOG_INTERVAL seconds to check
        # that the cmux workspace is still alive. If codex TUI exited
        # between iterations (which happens if the model finishes / hits
        # a fatal error), we re-spawn on detection rather than waiting
        # the full heartbeat_interval.
        WATCHDOG_INTERVAL = 60  # seconds
        elapsed_since_iter = 0
        while self._running:
            try:
                await asyncio.sleep(WATCHDOG_INTERVAL)
                if not self._running:
                    break
                # Workspace health probe
                alive = await self._cmux_workspace_alive()
                if not alive:
                    logger.warning("observer: cmux workspace died mid-run; respawning")
                    await self._handle_crash("workspace_died_midrun")
                    elapsed_since_iter = 0
                    continue
                elapsed_since_iter += WATCHDOG_INTERVAL
                if elapsed_since_iter >= interval:
                    elapsed_since_iter = 0
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
        """Send Observer identity / prompt template on first start.

        Honors DH-sovereignty: if `prompt_template_file` is set, uses that
        file; otherwise falls back to identity.md (the classic path).
        """
        persona_path: Path | None = None
        resolved = getattr(self, "_resolved", None)
        if resolved is not None and resolved.prompt_template_path is not None:
            persona_path = resolved.prompt_template_path
        else:
            candidate = Path(self.config.agent.persona_dir) / DH_ID / "identity.md"
            if candidate.exists():
                persona_path = candidate
        if persona_path and persona_path.exists():
            identity = persona_path.read_text(encoding="utf-8")[:CONTEXT_CAP_BYTES]
            await self._send_to_cmux(identity)

    async def _wait_for_cmux_ready(self, max_secs: int = 30):
        """Poll cmux capture-pane until codex TUI appears to be up.

        Catches: trust prompt still showing, codex not yet rendered, or
        workspace already dead (returns early, _single_iteration will
        trigger crash handler on next send).
        """
        if not self._workspace_id:
            return
        start = time.time()
        # Indicators that codex TUI is ready to receive input
        ready_markers = ("OpenAI Codex", "codex", "model:", "› ", "❯ ")
        trust_marker = "trust the contents"
        while time.time() - start < max_secs:
            if not self._running:
                return
            code, out = await self._cmux(
                "capture-pane", "--workspace", self._workspace_id
            )
            if code != 0:
                # Workspace likely died — give up, main loop will detect
                return
            lower = out.lower()
            if trust_marker in lower:
                # Trust dialog showing; press "1" + Enter once and wait
                logger.info("observer: codex showing trust dialog, auto-accepting")
                await self._cmux("send-key", "--workspace", self._workspace_id, "1")
                await asyncio.sleep(0.3)
                await self._cmux(
                    "send-key", "--workspace", self._workspace_id, "Enter"
                )
                await asyncio.sleep(2)
                continue
            if any(m.lower() in lower for m in ready_markers):
                logger.info("observer: codex TUI ready after %.1fs", time.time() - start)
                return
            await asyncio.sleep(1)
        logger.warning(
            "observer: codex TUI didn't reach ready markers in %ds; "
            "proceeding anyway",
            max_secs,
        )

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
        # NOTE: use `(row.get(k) or '')` not `row.get(k, '')` — the latter
        # only falls back when the key is missing, not when the value is
        # explicitly None, which is what aiosqlite returns for NULL cells.
        def _s(d: dict, key: str, cap: int) -> str:
            v = d.get(key)
            return (v or "")[:cap] if isinstance(v, str) else ""

        lines = [
            f"## Context refresh @ {ctx['now']}",
            "",
            "### Executor 最近 heartbeat",
        ]
        for hb in ctx["exec_heartbeats"]:
            act = hb.get("activity") or "?"
            lines.append(f"- [{act}] {_s(hb, 'description', 100)}")
        lines.append("")
        lines.append("### Executor 最近 deliverable")
        for dl in ctx["exec_deliverables"]:
            t = dl.get("type") or "?"
            lines.append(f"- [{t}] {_s(dl, 'title', 80)}")
        lines.append("")
        lines.append("### 你最近发的 discovery (防重复)")
        for d in ctx["own_discoveries"]:
            c = d.get("category") or "?"
            lines.append(f"- [{c}] {_s(d, 'title', 80)}")
        lines.append("")
        if ctx.get("git_log_2h"):
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
        # Re-mint token + re-spawn workspace (re-resolve DH config in case
        # yaml was edited since last start).
        token = issue_token(self.registry, DH_ID)
        launch = self._provider.build_launch(None)
        try:
            resolved = resolve(self.config, DH_ID)
            self._resolved = resolved
            global_codex_model = getattr(
                getattr(self.config, "codex", None), "model", ""
            ) or ""
            launch_cmd = (
                augment_codex_cmd(launch.cmd, resolved, global_codex_model)
                if resolved.provider == "codex"
                else launch.cmd
            )
        except KeyError:
            launch_cmd = launch.cmd
        shell_cmd = (
            "unset CLAUDECODE; "
            f"export MYAGENT_URL=http://localhost:{self.port}; "
            f"export MYAGENT_DH_TOKEN={token}; "
            f"exec {launch_cmd}"
        )
        obs_workspace = Path(self.config.survival.workspace) / "observer"
        obs_workspace.mkdir(parents=True, exist_ok=True)
        code, out = await self._cmux(
            "new-workspace",
            "--name", cfg.cmux_session,
            "--cwd", str(obs_workspace),
            "--command", shell_cmd,
        )
        if code != 0:
            logger.error("observer respawn failed: %s", out)
            invalidate_token(self.registry, DH_ID)
            return
        await asyncio.sleep(0.4)
        self._workspace_id = await self._cmux_find_by_name(cfg.cmux_session)
        self.registry.mark_started(DH_ID, cmux_session=cfg.cmux_session)
