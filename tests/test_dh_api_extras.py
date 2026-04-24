"""Tests for R13 + R17 new API surface.

- GET /api/digital_humans/{id}/persona
- GET /api/agent/stats?digital_human_id=
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from myagent.digital_humans import issue_token
from myagent.server import create_app


@pytest.fixture
def config_with_dhs(tmp_path):
    cfg = tmp_path / "config.yaml"
    # Create minimal persona dirs so the persona endpoint has something to return
    (tmp_path / "persona" / "executor").mkdir(parents=True)
    (tmp_path / "persona" / "observer").mkdir(parents=True)
    (tmp_path / "persona" / "executor" / "identity.md").write_text("# Executor\nhello")
    (tmp_path / "persona" / "observer" / "identity.md").write_text("# Observer\nwatch")
    cfg.write_text(f"""
agent:
  name: "TestAgent"
  data_dir: "{tmp_path}"
  db_path: "{tmp_path}/agent.db"
  persona_dir: "{tmp_path}/persona"
claude:
  binary: "echo"
  default_cwd: "{tmp_path}"
  timeout: 60
  args: []
scheduler:
  max_daily_calls: 10
  min_interval_seconds: 1
server:
  host: "127.0.0.1"
  port: 9999
  secret: "test-master"
feishu:
  enabled: false
relay:
  enabled: false
doubao:
  enabled: false
postgres:
  enabled: false
digital_humans:
  executor:
    persona_dir: persona/executor
    cmux_session: mycmux-executor
    provider: codex
    heartbeat_interval_secs: 600
    skill_whitelist: ["*"]
    endpoint_allowlist: ["heartbeat", "deliverable", "discovery", "workflow", "upgrade", "review"]
    enabled: true
  observer:
    persona_dir: persona/observer
    cmux_session: mycmux-observer
    provider: codex
    heartbeat_interval_secs: 1800
    skill_whitelist: []
    endpoint_allowlist: ["heartbeat", "discovery"]
    enabled: false
""")
    return str(cfg)


@pytest_asyncio.fixture
async def app(config_with_dhs):
    application = await create_app(config_with_dhs)
    yield application
    application.state.scheduler.stop()
    await application.state.db.close()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer test-master"},
    ) as c:
        yield c


# ---- /api/digital_humans/{id}/persona ----


@pytest.mark.asyncio
async def test_persona_endpoint_returns_identity_content(client):
    r = await client.get("/api/digital_humans/executor/persona")
    assert r.status_code == 200
    data = r.json()
    assert data["digital_human_id"] == "executor"
    assert data["files"]["identity.md"].startswith("# Executor")


@pytest.mark.asyncio
async def test_persona_endpoint_missing_files_return_none(client):
    # knowledge.md + principles.md not created → None
    r = await client.get("/api/digital_humans/observer/persona")
    assert r.status_code == 200
    data = r.json()
    assert data["files"]["identity.md"].startswith("# Observer")
    assert data["files"]["knowledge.md"] is None
    assert data["files"]["principles.md"] is None


@pytest.mark.asyncio
async def test_persona_unknown_dh_404(client):
    r = await client.get("/api/digital_humans/nobody/persona")
    assert r.status_code == 404


# ---- PUT /api/digital_humans/{id}/persona/{filename} ----


@pytest.mark.asyncio
async def test_put_persona_writes_file(client, config_with_dhs):
    r = await client.put(
        "/api/digital_humans/observer/persona/knowledge.md",
        json={"content": "# new content\nhello"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["digital_human_id"] == "observer"
    assert data["size"] > 0

    # Read back via GET
    r2 = await client.get("/api/digital_humans/observer/persona")
    assert r2.json()["files"]["knowledge.md"] == "# new content\nhello"


@pytest.mark.asyncio
async def test_put_persona_invalid_filename_400(client):
    r = await client.put(
        "/api/digital_humans/observer/persona/hack.sh",
        json={"content": "rm -rf /"},
    )
    assert r.status_code == 400
    assert "invalid_filename" in r.json()["detail"]


@pytest.mark.asyncio
async def test_put_persona_unknown_dh_404(client):
    r = await client.put(
        "/api/digital_humans/nobody/persona/identity.md",
        json={"content": "x"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_put_persona_non_string_content_400(client):
    r = await client.put(
        "/api/digital_humans/observer/persona/identity.md",
        json={"content": 123},
    )
    assert r.status_code == 400


# ---- /api/agent/stats ----


@pytest.mark.asyncio
async def test_stats_global_returns_all_counts(client):
    r = await client.get("/api/agent/stats")
    assert r.status_code == 200
    data = r.json()
    for k in ("heartbeats", "deliverables", "discoveries", "workflows",
              "upgrades", "reviews", "pending_upgrades",
              "deliverables_today", "discoveries_today", "heartbeats_today"):
        assert k in data


@pytest.mark.asyncio
async def test_stats_scoped_to_executor(client, app):
    # Issue an executor token + write a heartbeat so there's something to count
    token = issue_token(app.state.dh_registry, "executor")
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        await c.post("/api/agent/heartbeat", json={"activity": "coding"})

    r = await client.get("/api/agent/stats?digital_human_id=executor")
    assert r.status_code == 200
    data = r.json()
    assert data["heartbeats_today"] >= 1


@pytest.mark.asyncio
async def test_stats_scoped_to_observer_is_zero_when_no_writes(client):
    r = await client.get("/api/agent/stats?digital_human_id=observer")
    assert r.status_code == 200
    data = r.json()
    # Observer has made no writes in this test, so everything should be 0
    assert data["heartbeats"] == 0
    assert data["discoveries"] == 0
    assert data["deliverables_today"] == 0


@pytest.mark.asyncio
async def test_stats_empty_digital_human_id_returns_400(client):
    r = await client.get("/api/agent/stats?digital_human_id=")
    assert r.status_code == 400
    assert r.json()["detail"] == "empty_digital_human_id"
