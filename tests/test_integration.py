"""Integration test: submit a task via API, verify it lands in DB and can be processed."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from myagent.server import create_app


@pytest_asyncio.fixture
async def app(config_yaml):
    application = await create_app(config_yaml)
    yield application
    application.state.scheduler.stop()
    await application.state.db.close()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test",
                           headers={"Authorization": "Bearer test"}) as c:
        yield c


@pytest.mark.asyncio
async def test_full_task_lifecycle(client, app):
    # Submit
    resp = await client.post("/api/tasks", json={
        "prompt": "echo hello",
        "cwd": "/tmp",
        "source": "cli",
    })
    assert resp.status_code == 201
    task_id = resp.json()["id"]

    # Verify in list
    resp = await client.get("/api/tasks")
    ids = [t["id"] for t in resp.json()]
    assert task_id in ids

    # Get by ID
    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.json()["status"] == "pending"

    # Process with scheduler (uses fake claude from conftest)
    processed = await app.state.scheduler.process_one()
    assert processed is True

    # Verify completed
    resp = await client.get(f"/api/tasks/{task_id}")
    task = resp.json()
    assert task["status"] in ("done", "failed")

    # Logs exist
    resp = await client.get(f"/api/tasks/{task_id}/logs")
    assert resp.status_code == 200
