import pytest
from httpx import AsyncClient, ASGITransport
from myagent.server import create_app


@pytest.mark.asyncio
async def test_server_starts_with_feishu_disabled(tmp_path):
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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["feishu_enabled"] is False
        assert data["relay_enabled"] is False
        assert data["doubao_enabled"] is False
        assert data["pgvector_enabled"] is False
    await app.state.feishu_client.close()
    await app.state.doubao_client.close()
    await app.state.embedding_store.close()
    await app.state.db.close()


@pytest.mark.asyncio
async def test_server_has_feishu_client(tmp_path):
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
  bot_webhook: "https://example.com/hook"
  enabled: true
relay:
  enabled: false
doubao:
  enabled: false
postgres:
  enabled: false
""".format(tmp=str(tmp_path)))

    app = await create_app(str(cfg))
    assert app.state.feishu_client is not None
    assert app.state.relay_client is not None
    await app.state.feishu_client.close()
    await app.state.doubao_client.close()
    await app.state.embedding_store.close()
    await app.state.db.close()
