"""Tests for migration 001 (digital_human_id + dedup + indexes)."""
from __future__ import annotations

import pytest
import pytest_asyncio
import aiosqlite

from myagent.migrations import migration_001 as m1

AGENT_TABLES = [
    "agent_heartbeats",
    "agent_deliverables",
    "agent_discoveries",
    "agent_workflows",
    "agent_upgrades",
    "agent_reviews",
]


@pytest_asyncio.fixture
async def pre_migration_db(tmp_path):
    """Create a DB with pre-migration schema + historical rows."""
    db_path = tmp_path / "agent.db"
    async with aiosqlite.connect(str(db_path)) as db:
        for t in AGENT_TABLES:
            await db.execute(
                f"CREATE TABLE {t} (id INTEGER PRIMARY KEY, created_at TEXT)"
            )
            await db.executemany(
                f"INSERT INTO {t} (id, created_at) VALUES (?, ?)",
                [(i, f"2026-01-0{i}") for i in range(1, 4)],
            )
        await db.commit()
    return db_path


@pytest.mark.asyncio
async def test_migration_adds_digital_human_id_default_executor(pre_migration_db):
    await m1.run(pre_migration_db)
    async with aiosqlite.connect(str(pre_migration_db)) as db:
        for t in AGENT_TABLES:
            async with db.execute(f"SELECT digital_human_id FROM {t}") as cur:
                rows = await cur.fetchall()
            assert all(r[0] == "executor" for r in rows), f"{t} has non-executor rows"
            assert len(rows) == 3


@pytest.mark.asyncio
async def test_migration_creates_dedup_table(pre_migration_db):
    await m1.run(pre_migration_db)
    async with aiosqlite.connect(str(pre_migration_db)) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_discovery_dedup'"
        ) as cur:
            assert await cur.fetchone() is not None


@pytest.mark.asyncio
async def test_migration_creates_indexes(pre_migration_db):
    await m1.run(pre_migration_db)
    async with aiosqlite.connect(str(pre_migration_db)) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%_dh'"
        ) as cur:
            names = {row[0] async for row in cur}
    assert names == {"idx_heartbeats_dh", "idx_deliverables_dh", "idx_discoveries_dh"}


@pytest.mark.asyncio
async def test_migration_is_idempotent(pre_migration_db):
    await m1.run(pre_migration_db)
    # Second run must not raise
    await m1.run(pre_migration_db)
    # And not duplicate columns
    async with aiosqlite.connect(str(pre_migration_db)) as db:
        async with db.execute("PRAGMA table_info(agent_heartbeats)") as cur:
            cols = [row[1] async for row in cur]
    assert cols.count("digital_human_id") == 1


@pytest.mark.asyncio
async def test_migration_skips_missing_tables(tmp_path):
    """A DB with only some tables still migrates cleanly."""
    db_path = tmp_path / "partial.db"
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(
            "CREATE TABLE agent_heartbeats (id INTEGER PRIMARY KEY, created_at TEXT)"
        )
        await db.commit()
    # Should not raise
    await m1.run(db_path)
    async with aiosqlite.connect(str(db_path)) as db:
        async with db.execute("PRAGMA table_info(agent_heartbeats)") as cur:
            cols = [row[1] async for row in cur]
    assert "digital_human_id" in cols
