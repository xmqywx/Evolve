"""Migration 002: per-DH agent_config overrides.

Adds a nullable digital_human_id column to agent_config so per-DH values can
override the global default (NULL). Also creates a composite index on
(digital_human_id, key) to make lookups cheap.

Idempotent: re-running on an already-migrated DB is a no-op.
Used by Task A1 of the DH Sovereignty roadmap.
See: docs/specs/2026-04-25-dh-sovereignty-design.md § 5
"""
from __future__ import annotations

import aiosqlite
from pathlib import Path


async def _has_column(db: aiosqlite.Connection, table: str, column: str) -> bool:
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        cols = [row[1] async for row in cur]
    return column in cols


async def _has_table(db: aiosqlite.Connection, name: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ) as cur:
        return await cur.fetchone() is not None


async def _has_index(db: aiosqlite.Connection, name: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (name,)
    ) as cur:
        return await cur.fetchone() is not None


async def _table_pk(db: aiosqlite.Connection, table: str) -> list[str]:
    """Return list of PRIMARY KEY column names on the given table."""
    pk = []
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        async for row in cur:
            # row: (cid, name, type, notnull, dflt_value, pk)
            if row[5]:
                pk.append(row[1])
    return pk


async def run(db_path: str | Path) -> None:
    """Apply migration 002 idempotently against the DB at db_path.

    - Adds nullable digital_human_id column.
    - Rebuilds the table so its uniqueness constraint is composite
      (digital_human_id, key) rather than key-only — otherwise per-DH
      overrides would collide with the global row (key-as-PK).
    - Preserves existing rows (treated as global, dh_id = NULL).
    - Idempotent: repeat runs are no-ops once the new shape is in place.
    """
    async with aiosqlite.connect(str(db_path)) as db:
        # Guard: if agent_config doesn't exist (fresh install before schema
        # has run), nothing to do — schema.sql will create the column.
        if not await _has_table(db, "agent_config"):
            return

        if not await _has_column(db, "agent_config", "digital_human_id"):
            await db.execute(
                "ALTER TABLE agent_config ADD COLUMN digital_human_id TEXT DEFAULT NULL"
            )

        # If PRIMARY KEY is still (key,), rebuild with composite UNIQUE.
        pk = await _table_pk(db, "agent_config")
        if pk == ["key"]:
            has_updated_at = await _has_column(db, "agent_config", "updated_at")
            await db.execute("BEGIN")
            try:
                await db.execute(
                    """
                    CREATE TABLE agent_config_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        digital_human_id TEXT DEFAULT NULL,
                        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                        UNIQUE(digital_human_id, key)
                    )
                    """
                )
                if has_updated_at:
                    await db.execute(
                        "INSERT INTO agent_config_new (key, value, digital_human_id, updated_at) "
                        "SELECT key, value, digital_human_id, updated_at FROM agent_config"
                    )
                else:
                    await db.execute(
                        "INSERT INTO agent_config_new (key, value, digital_human_id) "
                        "SELECT key, value, digital_human_id FROM agent_config"
                    )
                await db.execute("DROP TABLE agent_config")
                await db.execute("ALTER TABLE agent_config_new RENAME TO agent_config")
                await db.commit()
            except Exception:
                await db.execute("ROLLBACK")
                raise

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_config_dh "
            "ON agent_config(digital_human_id, key)"
        )

        await db.commit()


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) != 2:
        sys.stderr.write("usage: python -m myagent.migrations.migration_002 <db_path>\n")
        sys.exit(1)
    asyncio.run(run(sys.argv[1]))
    print(f"migration_002: applied to {sys.argv[1]}")
