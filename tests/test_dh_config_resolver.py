"""Tests for myagent.dh_config.resolve — DH Sovereignty effective config."""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from myagent.config import DigitalHumanEntry, MCPPoolEntry
from myagent.dh_config import ResolvedDHConfig, build_codex_mcp_flags, resolve


class _Cfg:
    """Minimal AgentConfig-shaped stub."""

    def __init__(self, *, persona_root: Path, digital_humans: dict,
                 mcp_pool: dict | None = None, codex_model: str = "",
                 claude_args=None):
        self.agent = type("A", (), {"persona_dir": str(persona_root)})()
        self.codex = type("C", (), {"model": codex_model})()
        self.claude = type("K", (), {"args": claude_args or []})()
        self.digital_humans = digital_humans
        self.mcp_pool = mcp_pool or {}


def _dh(**overrides) -> DigitalHumanEntry:
    base = dict(
        persona_dir="persona/xx",
        cmux_session="mycmux-xx",
        provider="codex",
    )
    base.update(overrides)
    return DigitalHumanEntry(**base)


@pytest.fixture
def persona_root(tmp_path):
    for dh_id in ("executor", "observer"):
        d = tmp_path / dh_id
        d.mkdir(parents=True)
        (d / "identity.md").write_text(f"# {dh_id} identity\n")
    return tmp_path


def test_resolve_uses_dh_model_when_set(persona_root):
    cfg = _Cfg(
        persona_root=persona_root,
        digital_humans={"executor": _dh(model="gpt-5.5-mini")},
        codex_model="gpt-5.5",
    )
    got = resolve(cfg, "executor")
    assert got.model == "gpt-5.5-mini"


def test_resolve_falls_back_to_global_codex_model(persona_root):
    cfg = _Cfg(
        persona_root=persona_root,
        digital_humans={"executor": _dh(model="")},
        codex_model="gpt-5.5",
    )
    got = resolve(cfg, "executor")
    assert got.model == "gpt-5.5"


def test_resolve_prompt_file_precedence(persona_root):
    # Create a custom prompt.md under persona/executor/
    (persona_root / "executor" / "prompt.md").write_text("CUSTOM TEMPLATE")
    cfg = _Cfg(
        persona_root=persona_root,
        digital_humans={"executor": _dh(prompt_template_file="prompt.md")},
    )
    got = resolve(cfg, "executor")
    assert got.prompt_template_path is not None
    assert got.prompt_template_path.name == "prompt.md"
    assert got.prompt_template_path.read_text() == "CUSTOM TEMPLATE"


def test_resolve_prompt_file_fallback_to_identity(persona_root):
    cfg = _Cfg(
        persona_root=persona_root,
        digital_humans={"executor": _dh(prompt_template_file="")},
    )
    got = resolve(cfg, "executor")
    assert got.prompt_template_path is not None
    assert got.prompt_template_path.name == "identity.md"


def test_resolve_mcp_resolves_from_pool(persona_root):
    pool = {
        "linear": MCPPoolEntry(
            command="npx",
            args=["-y", "mcp-linear"],
            env={"TOKEN": "xyz"},
        ),
    }
    cfg = _Cfg(
        persona_root=persona_root,
        digital_humans={"executor": _dh(mcp_servers=["linear"])},
        mcp_pool=pool,
    )
    got = resolve(cfg, "executor")
    assert len(got.mcp_servers) == 1
    entry = got.mcp_servers[0]
    assert entry["command"] == "npx"
    assert entry["args"] == ["-y", "mcp-linear"]
    assert entry["env"] == {"TOKEN": "xyz"}
    assert entry["key"] == "linear"


def test_resolve_mcp_skips_unknown_key(persona_root, caplog):
    cfg = _Cfg(
        persona_root=persona_root,
        digital_humans={"executor": _dh(mcp_servers=["ghost"])},
        mcp_pool={},
    )
    with caplog.at_level(logging.WARNING, logger="myagent.dh_config"):
        got = resolve(cfg, "executor")
    assert got.mcp_servers == []
    assert any("ghost" in rec.message for rec in caplog.records)


def test_resolve_unknown_dh_raises(persona_root):
    cfg = _Cfg(persona_root=persona_root, digital_humans={})
    with pytest.raises(KeyError, match="unknown dh nobody"):
        resolve(cfg, "nobody")


def test_resolve_default_observer_has_no_model_override(persona_root):
    """Observer with all fields empty + codex global 'gpt-5.5' → inherits global.

    This is the exact backwards-compat case: executor's current yaml has no
    per-DH model, and must continue producing cfg.codex.model under the hood.
    """
    cfg = _Cfg(
        persona_root=persona_root,
        digital_humans={"observer": _dh(provider="codex")},
        codex_model="gpt-5.5",
    )
    got = resolve(cfg, "observer")
    assert isinstance(got, ResolvedDHConfig)
    assert got.provider == "codex"
    assert got.model == "gpt-5.5"
    assert got.mcp_servers == []
    # identity.md fallback (prompt_template_file empty)
    assert got.prompt_template_path is not None
    assert got.prompt_template_path.name == "identity.md"


# ---- build_codex_mcp_flags (verified syntax 2026-04-25 via codex 0.124.0) ----


def test_build_codex_mcp_flags_empty():
    assert build_codex_mcp_flags([]) == []


def test_build_codex_mcp_flags_command_only():
    flags = build_codex_mcp_flags([
        {"key": "linear", "command": "npx", "args": [], "env": {}},
    ])
    assert flags == ['-c mcp_servers.linear.command="npx"']


def test_build_codex_mcp_flags_full_entry():
    flags = build_codex_mcp_flags([
        {
            "key": "vercel",
            "command": "npx",
            "args": ["-y", "@vercel/mcp"],
            "env": {"VERCEL_TOKEN": "abc123"},
        },
    ])
    # Order: command, args array, env scalars
    assert flags == [
        '-c mcp_servers.vercel.command="npx"',
        '-c mcp_servers.vercel.args=["-y","@vercel/mcp"]',
        '-c mcp_servers.vercel.env.VERCEL_TOKEN="abc123"',
    ]


def test_build_codex_mcp_flags_skips_keyless_entry():
    flags = build_codex_mcp_flags([{"command": "x"}])
    assert flags == []


def test_build_codex_mcp_flags_multiple_servers_independent():
    flags = build_codex_mcp_flags([
        {"key": "a", "command": "A", "args": [], "env": {}},
        {"key": "b", "command": "B", "args": [], "env": {}},
    ])
    assert '-c mcp_servers.a.command="A"' in flags
    assert '-c mcp_servers.b.command="B"' in flags
    assert len(flags) == 2
