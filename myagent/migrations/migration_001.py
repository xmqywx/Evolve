"""Migration 001: digital_human_id column + dedup table + filter indexes.

Idempotent: re-running on an already-migrated DB is a no-op.
Used by S1 of the multi-digital-human roadmap.
See: docs/specs/2026-04-24-s1-observer-digital-human.md § 3
"""
from __future__ import annotations

import aiosqlite
from pathlib import Path

AGENT_TABLES = [
    "agent_heartbeats",
    "agent_deliverables",
    "agent_discoveries",
    "agent_workflows",
    "agent_upgrades",
    "agent_reviews",
]


async def _has_column(db: aiosqlite.Connection, table: str, column: str) -> bool:
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        cols = [row[1] async for row in cur]
    return column in cols


async def _has_table(db: aiosqlite.Connection, name: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ) as cur:
        return await cur.fetchone() is not None


async def run(db_path: str | Path) -> None:
    """Apply migration 001 idempotently against the DB at db_path."""
    async with aiosqlite.connect(str(db_path)) as db:
        # 1. Add digital_human_id column (guarded per table)
        for t in AGENT_TABLES:
            if not await _has_table(db, t):
                # Table doesn't exist yet — skip. Fresh installs will get the
                # column via schema.sql; this migration is for upgrading an
                # existing DB.
                continue
            if not await _has_column(db, t, "digital_human_id"):
                await db.execute(
                    f"ALTER TABLE {t} ADD COLUMN digital_human_id "
                    f"TEXT NOT NULL DEFAULT 'executor'"
                )

        # 2. Dedup table (IF NOT EXISTS is naturally idempotent)
        if not await _has_table(db, "agent_discovery_dedup"):
            await db.execute(
                """
                CREATE TABLE agent_discovery_dedup (
                    dedup_key TEXT PRIMARY KEY,
                    first_seen_at TIMESTAMP NOT NULL,
                    hit_count INTEGER DEFAULT 1
                )
                """
            )

        # 3. Filter indexes — only on tables that exist.
        index_specs = [
            ("idx_heartbeats_dh", "agent_heartbeats"),
            ("idx_deliverables_dh", "agent_deliverables"),
            ("idx_discoveries_dh", "agent_discoveries"),
        ]
        for idx_name, table in index_specs:
            if await _has_table(db, table):
                await db.execute(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} "
                    f"ON {table}(digital_human_id, created_at DESC)"
                )

        await db.commit()


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) != 2:
        sys.stderr.write("usage: python -m myagent.migrations.migration_001 <db_path>\n")
        sys.exit(1)
    asyncio.run(run(sys.argv[1]))
    print(f"migration_001: applied to {sys.argv[1]}")
