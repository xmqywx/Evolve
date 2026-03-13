"""Tests for web API endpoints (React SPA served separately)."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from myagent.server import create_app


@pytest_asyncio.fixture
async def web_app(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("""
agent:
  name: TestAgent
  data_dir: "{tmp}"
  db_path: "{tmp}/agent.db"
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
    app = await create_app(str(cfg))
    yield app
    await app.state.feishu_client.close()
    await app.state.doubao_client.close()
    await app.state.embedding_store.close()
    await app.state.db.close()


@pytest.mark.asyncio
async def test_health(web_app):
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login(web_app):
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/login", json={"secret": "test"})
        assert resp.status_code == 200
        assert "token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong(web_app):
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/login", json={"secret": "wrong"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sessions_api(web_app):
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test",
                           headers={"Authorization": "Bearer test"}) as client:
        resp = await client.get("/api/sessions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_status_includes_sessions(web_app):
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test",
                           headers={"Authorization": "Bearer test"}) as client:
        resp = await client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_sessions" in data
