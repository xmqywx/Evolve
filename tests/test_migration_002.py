"""Tests for migration 002 (agent_config.digital_human_id + dh index)."""
from __future__ import annotations

import pytest
import pytest_asyncio
import aiosqlite

from myagent.migrations import migration_002 as m2


@pytest_asyncio.fixture
async def pre_migration_db(tmp_path):
    """Create a DB with an agent_config table + historical rows."""
    db_path = tmp_path / "agent.db"
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(
            "CREATE TABLE agent_config ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        await db.executemany(
            "INSERT INTO agent_config (key, value) VALUES (?, ?)",
            [("k1", "v1"), ("k2", "v2"), ("k3", "v3")],
        )
        await db.commit()
    return db_path


@pytest.mark.asyncio
async def test_migration_adds_digital_human_id_nullable(pre_migration_db):
    await m2.run(pre_migration_db)
    async with aiosqlite.connect(str(pre_migration_db)) as db:
        async with db.execute(
            "SELECT key, digital_human_id FROM agent_config"
        ) as cur:
            rows = await cur.fetchall()
    assert len(rows) == 3
    assert all(r[1] is None for r in rows), "existing rows should have NULL digital_human_id"


@pytest.mark.asyncio
async def test_migration_creates_dh_index(pre_migration_db):
    await m2.run(pre_migration_db)
    async with aiosqlite.connect(str(pre_migration_db)) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_agent_config_dh'"
        ) as cur:
            row = await cur.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_migration_is_idempotent(pre_migration_db):
    await m2.run(pre_migration_db)
    # Second run must not raise
    await m2.run(pre_migration_db)
    async with aiosqlite.connect(str(pre_migration_db)) as db:
        async with db.execute("PRAGMA table_info(agent_config)") as cur:
            cols = [row[1] async for row in cur]
    assert cols.count("digital_human_id") == 1


@pytest.mark.asyncio
async def test_migration_skips_missing_table(tmp_path):
    """A DB without agent_config should not crash."""
    db_path = tmp_path / "empty.db"
    async with aiosqlite.connect(str(db_path)) as db:
        # Create a sentinel unrelated table so the DB file exists with schema
        await db.execute("CREATE TABLE something_else (id INTEGER PRIMARY KEY)")
        await db.commit()
    # Should not raise
    await m2.run(db_path)
    # And should not have created agent_config
    async with aiosqlite.connect(str(db_path)) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_config'"
        ) as cur:
            assert await cur.fetchone() is None
