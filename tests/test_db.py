import pytest
import pytest_asyncio
from myagent.db import Database
from myagent.models import Task, TaskStatus, TaskSource


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_create_and_get_task(db):
    task = Task(prompt="test task", source=TaskSource.CLI, cwd="/tmp")
    await db.create_task(task)
    retrieved = await db.get_task(task.id)
    assert retrieved is not None
    assert retrieved.prompt == "test task"
    assert retrieved.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_update_task_status(db):
    task = Task(prompt="test", source=TaskSource.CLI, cwd="/tmp")
    await db.create_task(task)
    await db.update_task(task.id, status=TaskStatus.RUNNING)
    updated = await db.get_task(task.id)
    assert updated.status == TaskStatus.RUNNING


@pytest.mark.asyncio
async def test_list_tasks(db):
    for i in range(3):
        t = Task(prompt=f"task {i}", source=TaskSource.CLI, cwd="/tmp")
        await db.create_task(t)
    tasks = await db.list_tasks()
    assert len(tasks) == 3


@pytest.mark.asyncio
async def test_get_next_pending_task(db):
    t1 = Task(prompt="first", source=TaskSource.CLI, cwd="/tmp", priority="normal")
    t2 = Task(prompt="urgent", source=TaskSource.CLI, cwd="/tmp", priority="high")
    await db.create_task(t1)
    await db.create_task(t2)
    next_task = await db.get_next_pending()
    assert next_task is not None
    assert next_task.priority == "high"


@pytest.mark.asyncio
async def test_log_task_event(db):
    task = Task(prompt="test", source=TaskSource.CLI, cwd="/tmp")
    await db.create_task(task)
    await db.log_event(task.id, "text", content="hello world")
    logs = await db.get_task_logs(task.id)
    assert len(logs) == 1
    assert logs[0]["content"] == "hello world"


@pytest.mark.asyncio
async def test_fts_search(db):
    task = Task(prompt="fix shopify webhook", source=TaskSource.CLI, cwd="/tmp")
    await db.create_task(task)
    await db.create_memory(task.id, summary="Fixed Shopify webhook signature verification bug", tags='["shopify", "webhook"]')
    results = await db.search_memories("shopify webhook")
    assert len(results) >= 1
    assert "shopify" in results[0]["summary"].lower()
