import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from myagent.server import create_app


@pytest_asyncio.fixture
async def app(config_yaml):
    application = await create_app(config_yaml)
    yield application
    await application.state.feishu_client.close()
    await application.state.doubao_client.close()
    await application.state.embedding_store.close()
    await application.state.db.close()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test",
                           headers={"Authorization": "Bearer test"}) as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_submit_task(client):
    resp = await client.post("/api/tasks", json={
        "prompt": "test task",
        "cwd": "/tmp",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"].startswith("task_")
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_list_tasks(client):
    await client.post("/api/tasks", json={"prompt": "t1", "cwd": "/tmp"})
    await client.post("/api/tasks", json={"prompt": "t2", "cwd": "/tmp"})
    resp = await client.get("/api/tasks")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_task(client):
    create = await client.post("/api/tasks", json={"prompt": "find me", "cwd": "/tmp"})
    task_id = create.json()["id"]
    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["prompt"] == "find me"


@pytest.mark.asyncio
async def test_auth_required(config_yaml):
    application = await create_app(config_yaml)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/tasks")
        assert resp.status_code == 401
    await application.state.feishu_client.close()
    await application.state.doubao_client.close()
    await application.state.embedding_store.close()
    await application.state.db.close()


@pytest.mark.asyncio
async def test_jwt_login(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/api/login", json={"secret": "test"})
        assert resp.status_code == 200
        assert "token" in resp.json()


@pytest.mark.asyncio
async def test_jwt_login_wrong_secret(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/api/login", json={"secret": "wrong"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_jwt_auth_works(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Get JWT token
        resp = await c.post("/api/login", json={"secret": "test"})
        token = resp.json()["token"]
        # Use JWT to access API
        resp = await c.get("/api/sessions", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_session_list(client):
    resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_thinking_review_endpoint(client):
    resp = await client.post("/api/thinking/review")
    # Should work but return skipped since doubao is disabled
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        data = resp.json()
        assert data["status"] in ("ok", "skipped")


@pytest.mark.asyncio
async def test_memory_stats_endpoint(client):
    resp = await client.get("/api/memory/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "myagent" in data
    assert "claude_mem" in data


@pytest.mark.asyncio
async def test_memory_observations_endpoint(client):
    resp = await client.get("/api/memory/observations")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_memory_timeline_endpoint(client):
    resp = await client.get("/api/memory/timeline")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_memory_projects_endpoint(client):
    resp = await client.get("/api/memory/projects")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
