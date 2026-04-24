"""Tests for per-DH scoping on db.get_agent_config / set_agent_config.

Covers the lookup rule from the DH Sovereignty spec § 5:
- get(dh_id, key) → try (dh_id, key), fall back to (NULL, key), else None.
- set(dh_id, key, value) → UPSERT with explicit dh_id (NULL is distinct).
- Backwards-compat: existing callers without dh_id behave as before (NULL rows).
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from myagent.db import Database
from myagent.migrations import migration_002


@pytest_asyncio.fixture
async def db(tmp_path):
    db_path = str(tmp_path / "agent.db")
    d = Database(db_path)
    await d.init()
    # Apply the DH-sovereignty migration (idempotent; required when running
    # fresh DBs that were first created with the old schema).
    await migration_002.run(db_path)
    yield d
    await d.close()


@pytest.mark.asyncio
async def test_set_and_get_global(db):
    await db.set_agent_config("speed", "fast")
    assert await db.get_agent_config_value("speed") == "fast"
    assert await db.get_agent_config() == {"speed": "fast"}


@pytest.mark.asyncio
async def test_set_and_get_per_dh(db):
    await db.set_agent_config("speed", "fast", digital_human_id="executor")
    # Per-DH merged view should include executor's override
    merged = await db.get_agent_config(digital_human_id="executor")
    assert merged == {"speed": "fast"}
    # Global (NULL) view should be empty
    assert await db.get_agent_config() == {}


@pytest.mark.asyncio
async def test_fallback_to_global(db):
    await db.set_agent_config("speed", "fast")  # global
    # executor has no override → falls through to global
    assert await db.get_agent_config_value("speed", digital_human_id="executor") == "fast"
    # observer also falls through
    assert await db.get_agent_config_value("speed", digital_human_id="observer") == "fast"


@pytest.mark.asyncio
async def test_per_dh_overrides_global(db):
    await db.set_agent_config("speed", "slow")  # global
    await db.set_agent_config("speed", "fast", digital_human_id="executor")
    # Executor sees its own
    assert await db.get_agent_config_value("speed", digital_human_id="executor") == "fast"
    # Observer still sees global
    assert await db.get_agent_config_value("speed", digital_human_id="observer") == "slow"
    # Global view unchanged
    assert await db.get_agent_config() == {"speed": "slow"}


@pytest.mark.asyncio
async def test_two_dhs_independent(db):
    await db.set_agent_config("focus", "code", digital_human_id="executor")
    await db.set_agent_config("focus", "watch", digital_human_id="observer")
    assert await db.get_agent_config_value("focus", digital_human_id="executor") == "code"
    assert await db.get_agent_config_value("focus", digital_human_id="observer") == "watch"


@pytest.mark.asyncio
async def test_set_upsert_updates_existing(db):
    await db.set_agent_config("speed", "fast", digital_human_id="executor")
    await db.set_agent_config("speed", "turbo", digital_human_id="executor")
    assert await db.get_agent_config_value("speed", digital_human_id="executor") == "turbo"


@pytest.mark.asyncio
async def test_delete_per_dh_removes_override_not_global(db):
    await db.set_agent_config("speed", "slow")
    await db.set_agent_config("speed", "fast", digital_human_id="executor")
    removed = await db.delete_agent_config("speed", digital_human_id="executor")
    assert removed is True
    # Executor now falls back to global
    assert await db.get_agent_config_value("speed", digital_human_id="executor") == "slow"
    # Global untouched
    assert await db.get_agent_config_value("speed") == "slow"


@pytest.mark.asyncio
async def test_delete_missing_returns_false(db):
    removed = await db.delete_agent_config("ghost", digital_human_id="executor")
    assert removed is False


@pytest.mark.asyncio
async def test_get_agent_config_rows_only_per_dh(db):
    await db.set_agent_config("a", "1")
    await db.set_agent_config("b", "2", digital_human_id="executor")
    assert await db.get_agent_config_rows(digital_human_id="executor") == {"b": "2"}
    assert await db.get_agent_config_rows(digital_human_id=None) == {"a": "1"}


@pytest.mark.asyncio
async def test_bulk_set_per_dh(db):
    await db.set_agent_config_bulk(
        {"a": "1", "b": "2"}, digital_human_id="executor"
    )
    assert await db.get_agent_config_rows(digital_human_id="executor") == {"a": "1", "b": "2"}


@pytest.mark.asyncio
async def test_legacy_global_bulk_still_works(db):
    # No dh_id → global NULL rows
    await db.set_agent_config_bulk({"x": "1"})
    assert await db.get_agent_config() == {"x": "1"}
    # And it's not visible as an 'override' for any DH
    assert await db.get_agent_config_rows(digital_human_id="executor") == {}
