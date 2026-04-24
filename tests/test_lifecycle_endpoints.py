"""Tests for digital_humans lifecycle API (S1 multi-DH roadmap, Task 5).

Covers /api/digital_humans (list/detail) + start/stop/restart behavior.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from myagent.server import create_app


@pytest.fixture
def config_with_dhs(tmp_path):
    """Config that includes a digital_humans: section with executor + observer."""
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
  secret: "test"
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
        headers={"Authorization": "Bearer test"},
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_list_dhs_returns_both(client):
    r = await client.get("/api/digital_humans")
    assert r.status_code == 200
    ids = {d["id"] for d in r.json()}
    assert ids == {"executor", "observer"}


@pytest.mark.asyncio
async def test_list_dhs_includes_allowlist(client):
    r = await client.get("/api/digital_humans")
    observer = next(d for d in r.json() if d["id"] == "observer")
    assert observer["config"]["endpoint_allowlist"] == ["heartbeat", "discovery"]
    assert observer["config"]["skill_whitelist"] == []


@pytest.mark.asyncio
async def test_get_dh_detail(client):
    r = await client.get("/api/digital_humans/executor")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "executor"
    assert data["config"]["cmux_session"] == "mycmux-executor"


@pytest.mark.asyncio
async def test_get_dh_missing_returns_404(client):
    r = await client.get("/api/digital_humans/nonexistent")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_start_executor_returns_501(client):
    """S1 scope: only observer has a pluggable runtime."""
    r = await client.post("/api/digital_humans/executor/start")
    assert r.status_code == 501


@pytest.mark.asyncio
async def test_start_observer_without_engine_returns_503(client):
    """Observer engine not yet wired (Task 10) → 503."""
    r = await client.post("/api/digital_humans/observer/start")
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_list_dhs_requires_auth(app):
    """verify_auth middleware rejects missing/wrong bearer token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/digital_humans")
        assert r.status_code in (401, 403)
