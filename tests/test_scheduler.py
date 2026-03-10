import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from myagent.scheduler import Scheduler, RateLimiter
from myagent.db import Database
from myagent.models import Task, TaskStatus, TaskSource
from myagent.config import ClaudeSettings, SchedulerSettings


@pytest.fixture
def scheduler_settings():
    return SchedulerSettings(max_daily_calls=5, min_interval_seconds=0)


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


def test_rate_limiter_allows():
    rl = RateLimiter(max_daily=5, min_interval=0)
    assert rl.can_execute() is True


def test_rate_limiter_blocks_over_limit():
    rl = RateLimiter(max_daily=2, min_interval=0)
    rl.record_call()
    rl.record_call()
    assert rl.can_execute() is False


def test_rate_limiter_resets_daily():
    rl = RateLimiter(max_daily=1, min_interval=0)
    rl.record_call()
    assert rl.can_execute() is False
    rl.reset_daily()
    assert rl.can_execute() is True


@pytest.mark.asyncio
async def test_scheduler_picks_up_task(db, scheduler_settings, tmp_path):
    script = tmp_path / "fake_claude.sh"
    script.write_text('#!/bin/bash\necho \'{"type":"result","content":"done"}\'\n')
    script.chmod(0o755)
    claude_settings = ClaudeSettings(binary=str(script), default_cwd=str(tmp_path), timeout=5, args=[])

    task = Task(prompt="test", source=TaskSource.CLI, cwd=str(tmp_path))
    await db.create_task(task)

    scheduler = Scheduler(db, claude_settings, scheduler_settings)
    processed = await scheduler.process_one()
    assert processed is True

    updated = await db.get_task(task.id)
    assert updated.status == TaskStatus.DONE


@pytest.mark.asyncio
async def test_scheduler_notification_callback(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    await db.init()

    notifications = []

    async def on_task_done(task_id: str, status: str, summary: str | None):
        notifications.append({"task_id": task_id, "status": status, "summary": summary})

    script = tmp_path / "fake_claude.sh"
    script.write_text('#!/bin/bash\necho \'{"type":"result","content":"done"}\'\n')
    script.chmod(0o755)

    claude = ClaudeSettings(binary=str(script), default_cwd=str(tmp_path), timeout=10, args=[])
    sched_settings = SchedulerSettings(max_daily_calls=10, min_interval_seconds=0)
    scheduler = Scheduler(db, claude, sched_settings, on_task_done=on_task_done)

    task = Task(prompt="test notification", source=TaskSource.CLI, cwd=str(tmp_path))
    await db.create_task(task)

    await scheduler.process_one()

    assert len(notifications) == 1
    assert notifications[0]["task_id"] == task.id
    assert notifications[0]["status"] in ("done", "failed")

    await db.close()
