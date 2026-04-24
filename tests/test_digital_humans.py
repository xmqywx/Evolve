"""Tests for myagent.digital_humans (registry + tokens).

S1 multi-DH roadmap, Task 4.
"""
from __future__ import annotations

import json
import pytest

from myagent.digital_humans import (
    DHConfig,
    DHState,
    DigitalHumanRegistry,
    get_active_token,
    invalidate_token,
    issue_token,
    validate_token,
)


@pytest.fixture
def registry(tmp_path):
    reg = DigitalHumanRegistry(state_root=tmp_path / "digital_humans")
    reg.register(
        DHConfig(
            id="executor",
            persona_dir="persona/executor",
            cmux_session="mycmux-executor",
            provider="codex",
            heartbeat_interval_secs=600,
            skill_whitelist=["*"],
            endpoint_allowlist=["heartbeat", "deliverable", "discovery", "workflow", "upgrade", "review"],
        )
    )
    reg.register(
        DHConfig(
            id="observer",
            persona_dir="persona/observer",
            cmux_session="mycmux-observer",
            provider="codex",
            heartbeat_interval_secs=1800,
            skill_whitelist=[],
            endpoint_allowlist=["heartbeat", "discovery"],
        )
    )
    return reg


# ---- Registry basics ----


def test_registry_lists_configured_dhs(registry):
    assert sorted(registry.list_ids()) == ["executor", "observer"]


def test_get_config_returns_dhconfig(registry):
    cfg = registry.get_config("observer")
    assert cfg is not None
    assert cfg.endpoint_allowlist == ["heartbeat", "discovery"]


def test_get_config_missing_returns_none(registry):
    assert registry.get_config("nonexistent") is None


# ---- State persistence ----


def test_mark_started_writes_state_json(registry, tmp_path):
    registry.mark_started("executor", cmux_session="mycmux-executor")
    path = tmp_path / "digital_humans" / "executor" / "state.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["cmux_session"] == "mycmux-executor"
    assert data["restart_count"] == 0
    assert data["started_at"] is not None


def test_record_heartbeat_updates_state(registry):
    registry.mark_started("observer", cmux_session="mycmux-observer")
    registry.record_heartbeat("observer")
    state = registry.get_state("observer")
    assert state.last_heartbeat_at is not None


def test_record_crash_increments_restart_count(registry):
    registry.mark_started("observer", cmux_session="mycmux-observer")
    registry.record_crash("observer", reason="cmux died")
    registry.record_crash("observer", reason="codex crash")
    state = registry.get_state("observer")
    assert state.restart_count == 2
    assert state.last_crash == "codex crash"


def test_state_survives_new_registry_instance(registry, tmp_path):
    registry.mark_started("executor", cmux_session="mycmux-executor")
    registry.record_crash("executor", reason="test")
    # New registry instance reads state from disk
    reg2 = DigitalHumanRegistry(state_root=tmp_path / "digital_humans")
    reg2.register(
        DHConfig(
            id="executor",
            persona_dir="persona/executor",
            cmux_session="mycmux-executor",
        )
    )
    state = reg2.get_state("executor")
    assert state.restart_count == 1
    assert state.last_crash == "test"


# ---- Token lifecycle ----


def test_token_issue_and_validate(registry):
    token = issue_token(registry, "observer")
    assert validate_token(registry, token) == "observer"


def test_token_invalidate(registry):
    token = issue_token(registry, "observer")
    invalidate_token(registry, "observer")
    assert validate_token(registry, token) is None


def test_invalid_token_returns_none(registry):
    assert validate_token(registry, "bogus") is None
    assert validate_token(registry, "") is None


def test_token_rotates_on_reissue(registry):
    t1 = issue_token(registry, "observer")
    t2 = issue_token(registry, "observer")
    assert t1 != t2
    assert validate_token(registry, t1) is None
    assert validate_token(registry, t2) == "observer"


def test_token_hash_persisted_to_state(registry):
    token = issue_token(registry, "executor")
    state = registry.get_state("executor")
    assert state.auth_token_hash is not None
    assert state.auth_token_hash.startswith("sha256:")
    # Raw token is NOT in state (security)
    assert token not in state.auth_token_hash


def test_get_active_token(registry):
    assert get_active_token(registry, "observer") is None
    token = issue_token(registry, "observer")
    assert get_active_token(registry, "observer") == token
    invalidate_token(registry, "observer")
    assert get_active_token(registry, "observer") is None
