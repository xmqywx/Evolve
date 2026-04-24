"""Tests for per-DH auth + endpoint allowlist (S1 multi-DH roadmap, Task 6)."""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from myagent.server import create_app
from myagent.digital_humans import issue_token


@pytest.fixture
def config_with_dhs(tmp_path):
    cfg = tmp_path / "config.yaml"
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
async def observer_token(app):
    return issue_token(app.state.dh_registry, "observer")


@pytest_asyncio.fixture
async def executor_token(app):
    return issue_token(app.state.dh_registry, "executor")


async def _client(app, auth: str | None):
    transport = ASGITransport(app=app)
    headers = {"Authorization": auth} if auth else {}
    return AsyncClient(transport=transport, base_url="http://test", headers=headers)


# ---- Auth basics ----


@pytest.mark.asyncio
async def test_agent_heartbeat_without_token_returns_401(app):
    async with await _client(app, None) as c:
        r = await c.post("/api/agent/heartbeat", json={"activity": "coding"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_agent_heartbeat_with_invalid_token_returns_401(app):
    async with await _client(app, "Bearer nope") as c:
        r = await c.post("/api/agent/heartbeat", json={"activity": "coding"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_observer_token_can_heartbeat(app, observer_token):
    async with await _client(app, f"Bearer {observer_token}") as c:
        r = await c.post("/api/agent/heartbeat", json={"activity": "idle", "description": "t"})
    assert r.status_code == 200
    assert r.json()["digital_human_id"] == "observer"


# ---- Endpoint allowlist enforcement ----


@pytest.mark.asyncio
async def test_observer_cannot_post_deliverable(app, observer_token):
    async with await _client(app, f"Bearer {observer_token}") as c:
        r = await c.post("/api/agent/deliverable", json={
            "title": "malicious", "type": "code", "status": "draft"
        })
    assert r.status_code == 403
    assert "role_not_permitted" in r.json()["detail"]


@pytest.mark.asyncio
async def test_observer_cannot_post_workflow(app, observer_token):
    async with await _client(app, f"Bearer {observer_token}") as c:
        r = await c.post("/api/agent/workflow", json={"name": "x"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_observer_cannot_post_upgrade(app, observer_token):
    async with await _client(app, f"Bearer {observer_token}") as c:
        r = await c.post("/api/agent/upgrade", json={"proposal": "x"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_observer_cannot_post_review(app, observer_token):
    async with await _client(app, f"Bearer {observer_token}") as c:
        r = await c.post("/api/agent/review", json={"period": "2026-04-24"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_executor_token_can_post_all(app, executor_token):
    h = {"Authorization": f"Bearer {executor_token}"}
    async with await _client(app, f"Bearer {executor_token}") as c:
        r1 = await c.post("/api/agent/heartbeat", json={"activity": "coding"})
        r2 = await c.post("/api/agent/deliverable", json={"title": "x", "type": "code"})
        r3 = await c.post("/api/agent/workflow", json={"name": "w"})
        r4 = await c.post("/api/agent/upgrade", json={"proposal": "p"})
        r5 = await c.post("/api/agent/review", json={"period": "2026-04-24"})
    for r in (r1, r2, r3, r4, r5):
        assert r.status_code == 200, f"executor got {r.status_code} on {r.request.url}: {r.text}"
        assert r.json()["digital_human_id"] == "executor"


# ---- Discovery dedup ----


@pytest.mark.asyncio
async def test_duplicate_discovery_is_suppressed(app, observer_token):
    async with await _client(app, f"Bearer {observer_token}") as c:
        payload = {"title": "Polar.sh fee 4%", "category": "opportunity", "priority": "high"}
        r1 = await c.post("/api/agent/discovery", json=payload)
        r2 = await c.post("/api/agent/discovery", json=payload)
    assert r1.json()["status"] == "ok"
    assert r2.json()["status"] == "duplicate_suppressed"
    assert r2.json()["hit_count"] == 2


@pytest.mark.asyncio
async def test_client_cannot_override_dedup_key(app, observer_token):
    async with await _client(app, f"Bearer {observer_token}") as c:
        payload = {"title": "X", "category": "insight"}
        r1 = await c.post("/api/agent/discovery", json=payload)
        # Attempt to bypass with a different dedup_key in body → should be ignored
        r2 = await c.post("/api/agent/discovery", json={**payload, "dedup_key": "totally-different"})
    assert r1.json()["status"] == "ok"
    assert r2.json()["status"] == "duplicate_suppressed"


# ---- Back-compat: master token maps to executor ----


@pytest.mark.asyncio
async def test_master_token_rejected_on_agent_endpoints(app):
    """After R2 hardening, master server.secret / JWT is NOT a valid DH
    credential. Writes to /api/agent/* must carry a per-DH token."""
    async with await _client(app, "Bearer test-master") as c:
        r = await c.post("/api/agent/heartbeat", json={"activity": "coding"})
    assert r.status_code == 401
    assert "invalid_dh_token" in r.json()["detail"]


@pytest.mark.asyncio
async def test_body_digital_human_id_does_not_spoof(app, observer_token):
    """Observer posting with body digital_human_id=executor must still be
    treated as observer (token wins)."""
    async with await _client(app, f"Bearer {observer_token}") as c:
        r = await c.post("/api/agent/heartbeat",
                         json={"activity": "idle", "digital_human_id": "executor"})
    assert r.status_code == 200
    # body value is ignored; token wins
    assert r.json()["digital_human_id"] == "observer"
