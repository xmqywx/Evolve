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
async def test_dashboard(web_app):
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies={"token": "test"}) as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "MyAgent" in resp.text
        assert "控制台" in resp.text


@pytest.mark.asyncio
async def test_dashboard_requires_auth(web_app):
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/", follow_redirects=False)
        assert resp.status_code == 307


@pytest.mark.asyncio
async def test_tasks_page(web_app):
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies={"token": "test"}) as client:
        resp = await client.get("/tasks")
        assert resp.status_code == 200
        assert "任务列表" in resp.text


@pytest.mark.asyncio
async def test_memory_page(web_app):
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies={"token": "test"}) as client:
        resp = await client.get("/memory")
        assert resp.status_code == 200
        assert "记忆搜索" in resp.text


@pytest.mark.asyncio
async def test_web_submit(web_app):
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/web/submit", data={"prompt": "test task from web"})
        assert resp.status_code == 200
        assert "已提交" in resp.text


@pytest.mark.asyncio
async def test_task_detail_404(web_app):
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies={"token": "test"}) as client:
        resp = await client.get("/tasks/nonexistent")
        assert resp.status_code == 404
