"""Digital Human registry — config + runtime state + auth tokens.

S1 multi-digital-human roadmap, Task 4.
See: docs/specs/2026-04-24-s1-observer-digital-human.md § 4
"""
from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass
class DHConfig:
    """Static configuration for a digital human (read from config.yaml)."""

    id: str
    persona_dir: str
    cmux_session: str
    provider: str = "codex"
    heartbeat_interval_secs: int = 600
    skill_whitelist: list[str] = field(default_factory=list)
    endpoint_allowlist: list[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class DHState:
    """Runtime telemetry for a digital human (persisted to state.json).

    Config fields like skill_whitelist are NOT stored here — they live in
    config.yaml. See docs/decisions/2026-04-24-roles-boundary.md.
    """

    cmux_session: str | None = None
    started_at: str | None = None
    last_heartbeat_at: str | None = None
    restart_count: int = 0
    last_crash: str | None = None
    auth_token_hash: str | None = None
    enabled: bool = True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_token(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode()).hexdigest()


class DigitalHumanRegistry:
    """In-memory registry of DH configs + disk-backed runtime states + tokens."""

    def __init__(self, state_root: str | Path):
        self._configs: dict[str, DHConfig] = {}
        self._states: dict[str, DHState] = {}
        # token -> dh_id (in-memory only; only hash persisted)
        self._tokens: dict[str, str] = {}
        self._state_root = Path(state_root)
        self._state_root.mkdir(parents=True, exist_ok=True)

    # ---- Configuration ----

    def register(self, config: DHConfig) -> None:
        """Register a DH config. Loads existing state.json if present."""
        self._configs[config.id] = config
        if config.id not in self._states:
            self._states[config.id] = self._load_state(config.id)

    def list_ids(self) -> list[str]:
        return list(self._configs.keys())

    def list_configs(self) -> list[DHConfig]:
        return list(self._configs.values())

    def get_config(self, dh_id: str) -> DHConfig | None:
        return self._configs.get(dh_id)

    def get_state(self, dh_id: str) -> DHState | None:
        return self._states.get(dh_id)

    # ---- State persistence ----

    def _state_path(self, dh_id: str) -> Path:
        d = self._state_root / dh_id
        d.mkdir(parents=True, exist_ok=True)
        return d / "state.json"

    def _load_state(self, dh_id: str) -> DHState:
        p = self._state_path(dh_id)
        if not p.exists():
            return DHState()
        try:
            data = json.loads(p.read_text())
            return DHState(**{k: v for k, v in data.items() if k in DHState.__dataclass_fields__})
        except Exception:
            # Corrupt state.json — start fresh but preserve restart_count if possible
            return DHState()

    def _save_state(self, dh_id: str) -> None:
        state = self._states[dh_id]
        self._state_path(dh_id).write_text(json.dumps(asdict(state), indent=2))

    # ---- Lifecycle transitions ----

    def mark_started(self, dh_id: str, cmux_session: str) -> None:
        state = self._states[dh_id]
        state.cmux_session = cmux_session
        state.started_at = _now_iso()
        self._save_state(dh_id)

    def record_heartbeat(self, dh_id: str) -> None:
        if dh_id not in self._states:
            return
        self._states[dh_id].last_heartbeat_at = _now_iso()
        self._save_state(dh_id)

    def record_crash(self, dh_id: str, reason: str) -> None:
        state = self._states[dh_id]
        state.restart_count += 1
        state.last_crash = reason
        self._save_state(dh_id)


# ---- Token management (module-level helpers for clean DI) ----

def issue_token(registry: DigitalHumanRegistry, dh_id: str) -> str:
    """Mint a fresh auth token for dh_id; invalidates any prior token."""
    invalidate_token(registry, dh_id)
    token = secrets.token_urlsafe(32)
    registry._tokens[token] = dh_id
    state = registry._states.get(dh_id)
    if state is not None:
        state.auth_token_hash = _hash_token(token)
        registry._save_state(dh_id)
    return token


def validate_token(registry: DigitalHumanRegistry, token: str) -> str | None:
    """Return the DH id owning this token, or None if invalid."""
    if not token:
        return None
    return registry._tokens.get(token)


def invalidate_token(registry: DigitalHumanRegistry, dh_id: str) -> None:
    """Remove any token currently issued to dh_id."""
    to_del = [t for t, owner in registry._tokens.items() if owner == dh_id]
    for t in to_del:
        del registry._tokens[t]
    state = registry._states.get(dh_id)
    if state is not None:
        state.auth_token_hash = None
        registry._save_state(dh_id)


def get_active_token(registry: DigitalHumanRegistry, dh_id: str) -> str | None:
    """Return the current raw token for a DH, or None.

    Public helper so callers (admin debug endpoint, Observer env injection)
    don't reach into registry._tokens directly.
    """
    for tok, owner in registry._tokens.items():
        if owner == dh_id:
            return tok
    return None


def all_active_ids(registry: DigitalHumanRegistry) -> Iterable[str]:
    """Iterate DH ids that currently have a token issued."""
    seen: set[str] = set()
    for owner in registry._tokens.values():
        if owner not in seen:
            seen.add(owner)
            yield owner
