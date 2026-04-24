"""Verify SurvivalEngine._build_identity_prompt honors
digital_humans.executor.prompt_template_file when set (DH Sovereignty).

Precedence: file > DB survival_prompt > default. All go through
.format(**variables) so {projects_text} etc. still substitute.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from myagent.db import Database
from myagent.migrations import migration_001, migration_002
from myagent.survival import SurvivalEngine


@pytest_asyncio.fixture
async def db(tmp_path):
    d = Database(str(tmp_path / "agent.db"))
    await d.init()
    await migration_001.run(tmp_path / "agent.db")
    await migration_002.run(tmp_path / "agent.db")
    yield d
    await d.close()


def _make_cfg(persona_dir: Path, prompt_template_file: str = ""):
    """Build a minimal AgentConfig-like object with .agent.persona_dir
    and .digital_humans.executor.prompt_template_file."""
    dh_executor = SimpleNamespace(
        persona_dir="persona/executor",
        cmux_session="mycmux-executor",
        provider="codex",
        heartbeat_interval_secs=600,
        endpoint_allowlist=["heartbeat"],
        skill_whitelist=["*"],
        enabled=True,
        model="",
        prompt_template_file=prompt_template_file,
        mcp_servers=[],
    )
    return SimpleNamespace(
        agent=SimpleNamespace(persona_dir=str(persona_dir)),
        digital_humans={"executor": dh_executor},
        codex=SimpleNamespace(model="", binary="codex", default_cwd=".", args=[]),
        claude=SimpleNamespace(binary="echo", default_cwd=".", timeout=60, args=[]),
        mcp_pool={},
    )


def _make_engine(db, agent_cfg):
    """Construct a SurvivalEngine with only the bits _build_identity_prompt needs."""
    from myagent.config import ClaudeSettings, SurvivalSettings
    eng = SurvivalEngine(
        db=db,
        claude_settings=ClaudeSettings(binary="echo", default_cwd=".", timeout=60, args=[]),
        feishu=MagicMock(),
        settings=SurvivalSettings(workspace="/tmp/ws", enabled=True, provider="codex"),
        server_secret="",
        agent_config=agent_cfg,
    )
    # Stub _get_template_variables so it returns all variables the default
    # template references, so .format() doesn't KeyError.
    async def _fake_vars(projects=None, profile=None):
        # Union of every variable the default survival template references
        # (grep '{[a-z_]+}' myagent/survival.py)
        return {
            "projects_text": "P",
            "profile_text": "PR",
            "caps_text": "C",
            "behs_text": "B",
            "skills_text": "S",
            "ws": "WS",
            "knowledge_permanent": "KP",
            "knowledge_recent": "KR",
            "knowledge_task": "KT",
        }
    eng._get_template_variables = _fake_vars  # type: ignore
    return eng


@pytest.mark.asyncio
async def test_file_template_wins_over_db(db, tmp_path):
    # Setup persona dir with a custom prompt.md
    persona_root = tmp_path / "persona"
    (persona_root / "executor").mkdir(parents=True)
    prompt_file = persona_root / "executor" / "prompt.md"
    prompt_file.write_text("FILE {projects_text}\n", encoding="utf-8")

    # Also set DB survival_prompt — file should win
    await db.set_agent_config("survival_prompt", "DB {projects_text}")

    cfg = _make_cfg(persona_root, prompt_template_file="executor/prompt.md")
    eng = _make_engine(db, cfg)
    prompt = await eng._build_identity_prompt([], [])
    assert prompt.startswith("FILE P")
    assert "DB" not in prompt


@pytest.mark.asyncio
async def test_db_template_used_when_no_file(db, tmp_path):
    persona_root = tmp_path / "persona"
    (persona_root / "executor").mkdir(parents=True)

    await db.set_agent_config("survival_prompt", "DB-{projects_text}")

    # prompt_template_file not set → falls through to DB
    cfg = _make_cfg(persona_root, prompt_template_file="")
    eng = _make_engine(db, cfg)
    prompt = await eng._build_identity_prompt([], [])
    assert prompt.startswith("DB-P")


@pytest.mark.asyncio
async def test_default_template_used_when_file_missing_and_no_db(db, tmp_path):
    persona_root = tmp_path / "persona"
    (persona_root / "executor").mkdir(parents=True)

    # File path set but file doesn't exist → falls through
    cfg = _make_cfg(persona_root, prompt_template_file="executor/missing.md")
    eng = _make_engine(db, cfg)
    prompt = await eng._build_identity_prompt([], [])
    # Should contain one of the variable values from the default template
    assert len(prompt) > 0
    # Default template has {projects_text} substituted to "P"
    assert "P" in prompt


@pytest.mark.asyncio
async def test_file_template_falls_back_on_format_error(db, tmp_path):
    persona_root = tmp_path / "persona"
    (persona_root / "executor").mkdir(parents=True)
    # Template references a variable that isn't in _get_template_variables
    (persona_root / "executor" / "prompt.md").write_text(
        "FILE {missing_variable}", encoding="utf-8",
    )
    cfg = _make_cfg(persona_root, prompt_template_file="executor/prompt.md")
    eng = _make_engine(db, cfg)
    # Should fall back to default template, not raise
    prompt = await eng._build_identity_prompt([], [])
    assert "missing_variable" not in prompt  # the raw {...} should NOT appear


@pytest.mark.asyncio
async def test_absent_agent_config_preserves_legacy_behavior(db, tmp_path):
    # Engine without agent_config (back-compat path) → DB template
    await db.set_agent_config("survival_prompt", "LEGACY-{projects_text}")
    from myagent.config import ClaudeSettings, SurvivalSettings
    eng = SurvivalEngine(
        db=db,
        claude_settings=ClaudeSettings(binary="echo", default_cwd=".", timeout=60, args=[]),
        feishu=MagicMock(),
        settings=SurvivalSettings(workspace="/tmp/ws", enabled=True, provider="codex"),
        server_secret="",
        # agent_config=None  → legacy mode
    )
    async def _vars(projects=None, profile=None):
        return {"projects_text": "P", "profile_text": "", "caps_text": "",
                "behs_text": "", "skills_text": "", "ws": "",
                "knowledge_permanent": "", "knowledge_recent": "",
                "knowledge_task": ""}
    eng._get_template_variables = _vars  # type: ignore
    prompt = await eng._build_identity_prompt([], [])
    assert prompt.startswith("LEGACY-P")
