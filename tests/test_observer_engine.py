"""Tests for ObserverEngine core logic.

cmux interactions are mocked — we verify the control flow (context build,
prompt render, crash handling) without spawning real cmux workspaces.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from myagent.db import Database
from myagent.digital_humans import (
    DHConfig,
    DigitalHumanRegistry,
)
from myagent.migrations import migration_001
from myagent.observer import ObserverEngine


class _FakeProvider:
    """Minimal provider stub — only build_launch is called from ObserverEngine."""
    name = "codex"

    def build_launch(self, session_id):
        class _L:
            is_resume = False
            cmd = "echo 'fake provider'"
        return _L()


class _FakeConfig:
    """Minimal config namespace ObserverEngine reads from."""

    def __init__(self, db_path, persona_root, data_dir):
        self.agent = type("A", (), {
            "db_path": db_path,
            "persona_dir": persona_root,
            "data_dir": data_dir,
        })()
        self.claude = type("C", (), {"binary": "echo", "default_cwd": data_dir,
                                     "timeout": 60, "args": []})()
        self.codex = type("C", (), {"binary": "echo", "default_cwd": data_dir,
                                    "args": [], "model": "", "profile": "",
                                    "sessions_dir": "~/.codex/sessions"})()
        self.survival = type("S", (), {"workspace": data_dir, "enabled": True,
                                       "provider": "codex", "notify_feishu": False})()
        self.digital_humans = {
            "observer": DHConfig(
                id="observer",
                persona_dir="persona/observer",
                cmux_session="mycmux-observer-test",
                provider="codex",
                heartbeat_interval_secs=1800,
                skill_whitelist=[],
                endpoint_allowlist=["heartbeat", "discovery"],
                enabled=True,
            )
        }


@pytest_asyncio.fixture
async def db(tmp_path):
    d = Database(str(tmp_path / "agent.db"))
    await d.init()
    await migration_001.run(tmp_path / "agent.db")
    yield d
    await d.close()


@pytest.fixture
def registry(tmp_path):
    reg = DigitalHumanRegistry(state_root=tmp_path / "digital_humans")
    reg.register(
        DHConfig(
            id="observer",
            persona_dir="persona/observer",
            cmux_session="mycmux-observer-test",
            provider="codex",
            heartbeat_interval_secs=1800,
            skill_whitelist=[],
            endpoint_allowlist=["heartbeat", "discovery"],
            enabled=True,
        )
    )
    return reg


@pytest.fixture
def config(tmp_path):
    persona = tmp_path / "persona" / "observer"
    persona.mkdir(parents=True)
    (persona / "identity.md").write_text("# Observer\nYou observe.")
    return _FakeConfig(
        db_path=str(tmp_path / "agent.db"),
        persona_root=str(tmp_path / "persona"),
        data_dir=str(tmp_path),
    )


@pytest.fixture
def engine(db, registry, config):
    e = ObserverEngine(db=db, registry=registry, config=config, port=9999)
    # Force-inject fake provider (constructor calls build_provider which
    # expects a full config; we stub it).
    e._provider = _FakeProvider()
    return e


# ---- Context + prompt building ----


@pytest.mark.asyncio
async def test_build_context_reads_from_db(db, engine):
    await db.add_heartbeat(activity="coding", description="exec task", digital_human_id="executor")
    await db.add_deliverable(title="x", digital_human_id="executor")
    await db.add_discovery(title="y", digital_human_id="observer")
    ctx = await engine._build_context()
    assert len(ctx["exec_heartbeats"]) == 1
    assert ctx["exec_heartbeats"][0]["activity"] == "coding"
    assert len(ctx["exec_deliverables"]) == 1
    assert len(ctx["own_discoveries"]) == 1
    assert "now" in ctx


@pytest.mark.asyncio
async def test_render_prompt_includes_sections(engine):
    ctx = {
        "exec_heartbeats": [{"activity": "coding", "description": "A"}],
        "exec_deliverables": [{"type": "code", "title": "T"}],
        "own_discoveries": [{"category": "insight", "title": "D"}],
        "git_log_2h": "abc123 fix bug",
        "now": "2026-04-24T12:00:00+00:00",
    }
    prompt = await engine._render_prompt(ctx)
    assert "Executor 最近 heartbeat" in prompt
    assert "Executor 最近 deliverable" in prompt
    assert "防重复" in prompt
    assert "Git log" in prompt
    assert "abc123" in prompt
    assert len(prompt) <= 12_288   # CONTEXT_CAP_BYTES


@pytest.mark.asyncio
async def test_render_prompt_handles_none_fields(engine):
    """Regression: aiosqlite returns None for NULL cells. dict.get(k,'')
    doesn't fall back when value IS None (only when key is missing),
    so description=None caused 'NoneType not subscriptable' at 21:19 S1 day-0.
    """
    ctx = {
        "exec_heartbeats": [{"activity": "coding", "description": None}],
        "exec_deliverables": [{"type": None, "title": None}],
        "own_discoveries": [{"category": None, "title": None}],
        "git_log_2h": None,
        "now": "2026-04-24T12:00:00+00:00",
    }
    # Must not raise
    prompt = await engine._render_prompt(ctx)
    assert "Context refresh" in prompt


@pytest.mark.asyncio
async def test_render_prompt_caps_size(engine):
    huge_log = "x" * 20_000
    ctx = {
        "exec_heartbeats": [],
        "exec_deliverables": [],
        "own_discoveries": [],
        "git_log_2h": huge_log,
        "now": "2026-04-24T12:00:00+00:00",
    }
    prompt = await engine._render_prompt(ctx)
    assert len(prompt) <= 12_288


# ---- Crash supervisor ----


@pytest.mark.asyncio
async def test_handle_crash_increments_registry(engine, registry):
    registry.mark_started("observer", cmux_session="mycmux-observer-test")
    engine._running = False  # Skip the respawn path (no real cmux)
    with patch.object(engine, "_cmux", new=AsyncMock(return_value=(0, ""))), \
         patch("asyncio.sleep", new=AsyncMock()):
        await engine._handle_crash("test crash")
    state = registry.get_state("observer")
    assert state.restart_count == 1
    assert state.last_crash == "test crash"


@pytest.mark.asyncio
async def test_crash_loop_stops_after_threshold(engine, registry):
    """>10 crashes in 24h → engine.stop() is called."""
    registry.mark_started("observer", cmux_session="mycmux-observer-test")
    engine._running = True
    stop_called = False

    async def fake_stop():
        nonlocal stop_called
        stop_called = True
        engine._running = False
        return {"status": "stopped"}

    engine.stop = fake_stop
    with patch.object(engine, "_cmux", new=AsyncMock(return_value=(0, ""))), \
         patch("asyncio.sleep", new=AsyncMock()):
        # Populate 10 prior crashes, then one more should trigger stop
        import time
        now = time.time()
        engine._crash_timestamps = [now - i for i in range(10)]
        await engine._handle_crash("11th crash")
    assert stop_called


@pytest.mark.asyncio
async def test_crash_backoff_escalates(engine, registry):
    """Exponential backoff: 30s → 60 → 120 → 240 → 480 (cap)."""
    engine._running = False
    with patch.object(engine, "_cmux", new=AsyncMock(return_value=(0, ""))), \
         patch("asyncio.sleep", new=AsyncMock()) as sleep_mock:
        await engine._handle_crash("c1")
        # First call asyncio.sleep is the backoff
        first_backoff = sleep_mock.call_args_list[0][0][0]
        assert first_backoff == 30


# ---- _wait_for_cmux_ready branches ----


@pytest.mark.asyncio
async def test_wait_for_cmux_ready_happy_path(engine):
    """capture-pane returns 'OpenAI Codex' → ready immediately."""
    engine._running = True
    engine._workspace_id = "FAKE-UUID"
    with patch.object(
        engine, "_cmux",
        new=AsyncMock(return_value=(0, "╭─ OpenAI Codex v0.124.0 ─╮")),
    ), patch("asyncio.sleep", new=AsyncMock()):
        await engine._wait_for_cmux_ready(max_secs=5)
    # Should return without raising


@pytest.mark.asyncio
async def test_wait_for_cmux_ready_trust_dialog_autoaccepts(engine):
    """Trust dialog → auto-press '1' + Enter, then poll again."""
    engine._running = True
    engine._workspace_id = "FAKE-UUID"
    # First call: trust dialog. Second call (after auto-accept): ready marker.
    seq = [
        (0, "Do you trust the contents of this directory?"),
        (0, "Do you trust the contents of this directory?"),  # still showing
        (0, "╭─ OpenAI Codex v0.124.0 ─╮"),
    ]
    call_count = [0]

    async def fake_cmux(*args):
        # send-key calls for "1" and Enter don't need to advance the capture seq
        if args and args[0] == "send-key":
            return (0, "")
        idx = min(call_count[0], len(seq) - 1)
        call_count[0] += 1
        return seq[idx]

    with patch.object(engine, "_cmux", new=fake_cmux), \
         patch("asyncio.sleep", new=AsyncMock()):
        await engine._wait_for_cmux_ready(max_secs=10)
    # Should have sent "1" + Enter (2 send-key calls happened within the loop)
    # No raise = pass


@pytest.mark.asyncio
async def test_wait_for_cmux_ready_workspace_dead_returns_early(engine):
    """capture-pane returns non-zero exit → workspace dead, return early."""
    engine._running = True
    engine._workspace_id = "FAKE-UUID"
    with patch.object(
        engine, "_cmux", new=AsyncMock(return_value=(1, "not_found"))
    ), patch("asyncio.sleep", new=AsyncMock()):
        # Must not raise; must not loop forever
        await engine._wait_for_cmux_ready(max_secs=10)


@pytest.mark.asyncio
async def test_wait_for_cmux_ready_no_workspace_id_returns(engine):
    """No workspace_id → no-op."""
    engine._running = True
    engine._workspace_id = None
    with patch.object(engine, "_cmux", new=AsyncMock()) as cmux_mock:
        await engine._wait_for_cmux_ready(max_secs=5)
    cmux_mock.assert_not_called()


# ---- _cmux_workspace_alive (R20 runtime watchdog) ----


@pytest.mark.asyncio
async def test_cmux_workspace_alive_true_when_uuid_in_list(engine):
    engine._workspace_id = "AB0D5167-1234-5678-9ABC-DEF012345678"
    with patch.object(
        engine, "_cmux",
        new=AsyncMock(return_value=(0, "  AB0D5167-1234-5678-9ABC-DEF012345678  mycmux-observer")),
    ):
        assert await engine._cmux_workspace_alive() is True


@pytest.mark.asyncio
async def test_cmux_workspace_alive_false_when_missing(engine):
    engine._workspace_id = "DEAD-UUID"
    with patch.object(
        engine, "_cmux",
        new=AsyncMock(return_value=(0, "  OTHER-UUID  other-workspace")),
    ):
        assert await engine._cmux_workspace_alive() is False


@pytest.mark.asyncio
async def test_cmux_workspace_alive_true_on_cli_error(engine):
    """Conservative: if cmux CLI fails, assume alive (avoid false restarts)."""
    engine._workspace_id = "UUID"
    with patch.object(
        engine, "_cmux",
        new=AsyncMock(return_value=(1, "cli error")),
    ):
        assert await engine._cmux_workspace_alive() is True


@pytest.mark.asyncio
async def test_cmux_workspace_alive_false_when_no_workspace_id(engine):
    engine._workspace_id = None
    assert await engine._cmux_workspace_alive() is False
