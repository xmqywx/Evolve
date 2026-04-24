"""Tests for digital_human_id parameter on all agent_* DB helpers + dedup helpers.

S1 multi-DH roadmap, Task 2.
"""
from __future__ import annotations

import datetime as dt

import pytest
import pytest_asyncio

from myagent.db import Database
from myagent.migrations import migration_001 as m1


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    # Apply S1 migration so digital_human_id columns + dedup table exist.
    await m1.run(tmp_path / "test.db")
    yield database
    await database.close()


# ----- heartbeat -----

@pytest.mark.asyncio
async def test_add_heartbeat_default_is_executor(db):
    await db.add_heartbeat(activity="coding", description="t")
    rows = await db.list_heartbeats()
    assert rows[0]["digital_human_id"] == "executor"


@pytest.mark.asyncio
async def test_add_heartbeat_explicit_observer(db):
    await db.add_heartbeat(activity="idle", description="", digital_human_id="observer")
    rows_obs = await db.list_heartbeats(digital_human_id="observer")
    rows_exec = await db.list_heartbeats(digital_human_id="executor")
    assert len(rows_obs) == 1
    assert len(rows_exec) == 0


@pytest.mark.asyncio
async def test_list_heartbeats_no_filter_returns_all(db):
    await db.add_heartbeat(activity="coding", description="e", digital_human_id="executor")
    await db.add_heartbeat(activity="idle", description="o", digital_human_id="observer")
    rows = await db.list_heartbeats(digital_human_id=None)
    ids = {r["digital_human_id"] for r in rows}
    assert ids == {"executor", "observer"}


@pytest.mark.asyncio
async def test_get_latest_heartbeat_filters_by_dh(db):
    await db.add_heartbeat(activity="coding", digital_human_id="executor")
    await db.add_heartbeat(activity="idle", digital_human_id="observer")
    latest_obs = await db.get_latest_heartbeat(digital_human_id="observer")
    assert latest_obs is not None
    assert latest_obs["digital_human_id"] == "observer"
    assert latest_obs["activity"] == "idle"


# ----- deliverable -----

@pytest.mark.asyncio
async def test_add_deliverable_explicit_dh(db):
    await db.add_deliverable(title="x", digital_human_id="observer")
    rows = await db.list_deliverables(digital_human_id="observer")
    assert len(rows) == 1
    assert rows[0]["digital_human_id"] == "observer"


@pytest.mark.asyncio
async def test_list_deliverables_combined_filters(db):
    await db.add_deliverable(title="a", type="code", status="draft", digital_human_id="executor")
    await db.add_deliverable(title="b", type="research", status="draft", digital_human_id="observer")
    await db.add_deliverable(title="c", type="code", status="draft", digital_human_id="observer")
    rows = await db.list_deliverables(type="code", digital_human_id="observer")
    assert len(rows) == 1
    assert rows[0]["title"] == "c"


# ----- discovery -----

@pytest.mark.asyncio
async def test_add_discovery_default_executor(db):
    await db.add_discovery(title="y")
    rows = await db.list_discoveries()
    assert rows[0]["digital_human_id"] == "executor"


@pytest.mark.asyncio
async def test_list_discoveries_filter_by_dh(db):
    await db.add_discovery(title="opp", category="opportunity", digital_human_id="observer")
    await db.add_discovery(title="risk", category="risk", digital_human_id="executor")
    rows = await db.list_discoveries(digital_human_id="observer")
    assert len(rows) == 1
    assert rows[0]["title"] == "opp"


# ----- workflow / upgrade / review -----

@pytest.mark.asyncio
async def test_add_workflow_dh(db):
    await db.add_workflow(name="wf1", digital_human_id="executor")
    rows = await db.list_workflows(digital_human_id="executor")
    assert rows[0]["digital_human_id"] == "executor"


@pytest.mark.asyncio
async def test_add_upgrade_dh(db):
    await db.add_upgrade(proposal="enable puppeteer", digital_human_id="executor")
    rows = await db.list_upgrades(digital_human_id="executor")
    assert rows[0]["digital_human_id"] == "executor"


@pytest.mark.asyncio
async def test_add_review_dh(db):
    await db.add_review(period="2026-04-24", digital_human_id="observer")
    rows = await db.list_reviews(digital_human_id="observer")
    assert rows[0]["digital_human_id"] == "observer"


# ----- dedup -----

@pytest.mark.asyncio
async def test_dedup_insert_and_get(db):
    await db.insert_dedup("key1")
    existing = await db.get_dedup("key1")
    assert existing is not None
    assert existing["hit_count"] == 1


@pytest.mark.asyncio
async def test_dedup_increment(db):
    await db.insert_dedup("key2")
    await db.increment_dedup("key2")
    await db.increment_dedup("key2")
    existing = await db.get_dedup("key2")
    assert existing["hit_count"] == 3


@pytest.mark.asyncio
async def test_dedup_insert_ignore_is_idempotent(db):
    await db.insert_dedup("dup")
    await db.insert_dedup("dup")   # no error
    existing = await db.get_dedup("dup")
    assert existing["hit_count"] == 1


@pytest.mark.asyncio
async def test_purge_dedup_ttl_removes_old(db):
    old_ts = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)).isoformat()
    # Use private _db to insert with arbitrary timestamp — acceptable
    # test-only backdoor to simulate aged data.
    await db._db.execute(
        "INSERT INTO agent_discovery_dedup (dedup_key, first_seen_at, hit_count) VALUES (?, ?, ?)",
        ("oldkey", old_ts, 1),
    )
    await db._db.commit()
    removed = await db.purge_dedup_ttl(days=7)
    assert removed == 1
    assert await db.get_dedup("oldkey") is None


@pytest.mark.asyncio
async def test_purge_dedup_ttl_keeps_recent(db):
    await db.insert_dedup("recent")
    removed = await db.purge_dedup_ttl(days=7)
    assert removed == 0
    assert await db.get_dedup("recent") is not None
