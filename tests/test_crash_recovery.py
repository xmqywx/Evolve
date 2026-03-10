import pytest
from httpx import AsyncClient, ASGITransport
from myagent.server import create_app
from myagent.models import Task, TaskSource, TaskStatus
from myagent.db import Database


@pytest.mark.asyncio
async def test_crash_recovery_resets_running_tasks(tmp_path):
    """On startup, RUNNING tasks should be reset to PENDING."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("""
agent:
  name: TestAgent
  data_dir: "{tmp}"
  db_path: "{tmp}/agent.db"
  persona_dir: ""
claude:
  binary: echo
  timeout: 60
  args: []
scheduler:
  max_daily_calls: 10
  min_interval_seconds: 0
server:
  host: "127.0.0.1"
  port: 9999
  secret: "test"
feishu:
  enabled: false
relay:
  enabled: false
doubao:
  enabled: false
postgres:
  enabled: false
""".format(tmp=str(tmp_path)))

    # Pre-create a task in RUNNING state (simulating crash)
    db = Database(str(tmp_path / "agent.db"))
    await db.init()
    task = Task(prompt="stuck task", source=TaskSource.CLI, status=TaskStatus.RUNNING)
    await db.create_task(task)
    stuck_task = await db.get_task(task.id)
    assert stuck_task.status == TaskStatus.RUNNING
    await db.close()

    # Now start the app (should recover)
    app = await create_app(str(cfg))
    recovered = await app.state.db.get_task(task.id)
    assert recovered.status == TaskStatus.PENDING

    await app.state.feishu_client.close()
    await app.state.doubao_client.close()
    await app.state.embedding_store.close()
    await app.state.db.close()
