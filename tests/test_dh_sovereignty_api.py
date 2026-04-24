"""Tests for the DH Sovereignty API endpoints (Task A3).

Covers all 12 endpoints introduced in docs/specs/2026-04-25-dh-sovereignty-design.md § 6:
  GET/PUT/DELETE /api/digital_humans/{id}/config
  GET/PUT        /api/digital_humans/{id}/skills
  GET/PUT        /api/digital_humans/{id}/mcp
  GET/PUT        /api/digital_humans/{id}/model
  GET/PUT        /api/digital_humans/{id}/prompt
  GET            /api/mcp_pool
"""
from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
import yaml
from httpx import AsyncClient, ASGITransport

from myagent.server import create_app


@pytest.fixture
def config_with_dhs(tmp_path):
    cfg = tmp_path / "config.yaml"
    (tmp_path / "persona" / "executor").mkdir(parents=True)
    (tmp_path / "persona" / "observer").mkdir(parents=True)
    (tmp_path / "persona" / "executor" / "identity.md").write_text("# Executor")
    (tmp_path / "persona" / "observer" / "identity.md").write_text("# Observer")
    # Skill pool — two skills on disk so /skills has something to show.
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "researcher.md").write_text("# researcher")
    (agents_dir / "code-reviewer.md").write_text("# code-reviewer")

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
codex:
  binary: "codex"
  model: "gpt-5-global"
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
    skill_whitelist: ["researcher"]
    endpoint_allowlist: ["heartbeat", "deliverable", "discovery", "workflow", "upgrade", "review"]
    enabled: true
    model: ""
    mcp_servers: ["linear"]
  observer:
    persona_dir: persona/observer
    cmux_session: mycmux-observer
    provider: codex
    heartbeat_interval_secs: 1800
    skill_whitelist: []
    endpoint_allowlist: ["heartbeat", "discovery"]
    enabled: false
    model: "gpt-5-mini"
    mcp_servers: []
mcp_pool:
  linear:
    command: "npx"
    args: ["-y", "mcp-linear"]
    env: {{}}
  vercel:
    command: "npx"
    args: ["-y", "@vercel/mcp"]
    env: {{}}
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


# ---------------- /config ----------------

@pytest.mark.asyncio
async def test_get_dh_config_returns_yaml_and_empty_overrides(client):
    r = await client.get("/api/digital_humans/executor/config")
    assert r.status_code == 200
    data = r.json()
    assert data["dh_id"] == "executor"
    assert data["yaml"]["provider"] == "codex"
    assert data["overrides"] == {}
    assert data["global"] == {}
    assert data["effective"] == {}


@pytest.mark.asyncio
async def test_get_dh_config_unknown_404(client):
    r = await client.get("/api/digital_humans/nobody/config")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_put_dh_config_writes_override(client):
    r = await client.put(
        "/api/digital_humans/executor/config",
        json={"key": "speed", "value": "fast"},
    )
    assert r.status_code == 200
    assert r.json()["value"] == "fast"

    r2 = await client.get("/api/digital_humans/executor/config")
    data = r2.json()
    assert data["overrides"]["speed"] == "fast"
    assert data["effective"]["speed"] == "fast"


@pytest.mark.asyncio
async def test_put_dh_config_requires_key(client):
    r = await client.put(
        "/api/digital_humans/executor/config",
        json={"value": "fast"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_put_dh_config_requires_value(client):
    r = await client.put(
        "/api/digital_humans/executor/config",
        json={"key": "speed"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_put_dh_config_unknown_dh_404(client):
    r = await client.put(
        "/api/digital_humans/nobody/config",
        json={"key": "speed", "value": "fast"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_dh_config_removes_override(client, app):
    # seed global + per-DH
    await app.state.db.set_agent_config("speed", "slow")
    await app.state.db.set_agent_config("speed", "fast", digital_human_id="executor")
    r = await client.delete("/api/digital_humans/executor/config/speed")
    assert r.status_code == 200
    data = r.json()
    assert data["removed"] is True
    assert data["fallback"] == "slow"

    r2 = await client.get("/api/digital_humans/executor/config")
    assert r2.json()["overrides"] == {}


@pytest.mark.asyncio
async def test_delete_dh_config_unknown_dh_404(client):
    r = await client.delete("/api/digital_humans/nobody/config/foo")
    assert r.status_code == 404


# ---------------- /skills ----------------

@pytest.mark.asyncio
async def test_get_dh_skills_lists_pool_and_whitelist(client):
    r = await client.get("/api/digital_humans/executor/skills")
    assert r.status_code == 200
    data = r.json()
    assert set(data["all"]) == {"researcher", "code-reviewer"}
    assert data["whitelisted"] == ["researcher"]


@pytest.mark.asyncio
async def test_put_dh_skills_rewrites_yaml(client, config_with_dhs):
    r = await client.put(
        "/api/digital_humans/observer/skills",
        json={"whitelisted": ["researcher", "code-reviewer"]},
    )
    assert r.status_code == 200
    # Round-trip via GET
    r2 = await client.get("/api/digital_humans/observer/skills")
    assert set(r2.json()["whitelisted"]) == {"researcher", "code-reviewer"}
    # And the yaml on disk was actually rewritten
    data = yaml.safe_load(Path(config_with_dhs).read_text())
    assert set(data["digital_humans"]["observer"]["skill_whitelist"]) == {
        "researcher", "code-reviewer",
    }


@pytest.mark.asyncio
async def test_put_dh_skills_bad_body_400(client):
    r = await client.put(
        "/api/digital_humans/executor/skills",
        json={"whitelisted": "researcher"},  # not a list
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_get_dh_skills_unknown_404(client):
    r = await client.get("/api/digital_humans/nobody/skills")
    assert r.status_code == 404


# ---------------- /mcp ----------------

@pytest.mark.asyncio
async def test_get_dh_mcp_returns_pool_and_enabled(client):
    r = await client.get("/api/digital_humans/executor/mcp")
    assert r.status_code == 200
    data = r.json()
    assert set(data["pool"].keys()) == {"linear", "vercel"}
    assert data["enabled"] == ["linear"]


@pytest.mark.asyncio
async def test_put_dh_mcp_writes_yaml(client, config_with_dhs):
    r = await client.put(
        "/api/digital_humans/observer/mcp",
        json={"enabled": ["vercel"]},
    )
    assert r.status_code == 200
    r2 = await client.get("/api/digital_humans/observer/mcp")
    assert r2.json()["enabled"] == ["vercel"]
    data = yaml.safe_load(Path(config_with_dhs).read_text())
    assert data["digital_humans"]["observer"]["mcp_servers"] == ["vercel"]


@pytest.mark.asyncio
async def test_put_dh_mcp_rejects_unknown_key(client):
    r = await client.put(
        "/api/digital_humans/executor/mcp",
        json={"enabled": ["linear", "made-up-server"]},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_put_dh_mcp_bad_body_400(client):
    r = await client.put(
        "/api/digital_humans/executor/mcp",
        json={"enabled": "linear"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_get_mcp_pool_global(client):
    r = await client.get("/api/mcp_pool")
    assert r.status_code == 200
    pool = r.json()
    assert set(pool.keys()) == {"linear", "vercel"}
    assert pool["linear"]["command"] == "npx"


# ---------------- /model ----------------

@pytest.mark.asyncio
async def test_get_dh_model_observer_has_override(client):
    r = await client.get("/api/digital_humans/observer/model")
    assert r.status_code == 200
    data = r.json()
    assert data["current"] == "gpt-5-mini"
    assert data["provider"] == "codex"
    assert data["global_default"] == "gpt-5-global"


@pytest.mark.asyncio
async def test_get_dh_model_executor_uses_global(client):
    r = await client.get("/api/digital_humans/executor/model")
    data = r.json()
    assert data["current"] == ""
    assert data["global_default"] == "gpt-5-global"


@pytest.mark.asyncio
async def test_put_dh_model_writes_yaml(client, config_with_dhs):
    r = await client.put(
        "/api/digital_humans/executor/model",
        json={"model": "gpt-5-turbo"},
    )
    assert r.status_code == 200
    r2 = await client.get("/api/digital_humans/executor/model")
    assert r2.json()["current"] == "gpt-5-turbo"
    data = yaml.safe_load(Path(config_with_dhs).read_text())
    assert data["digital_humans"]["executor"]["model"] == "gpt-5-turbo"


@pytest.mark.asyncio
async def test_put_dh_model_empty_string_resets_to_global(client):
    # first override, then reset
    await client.put("/api/digital_humans/observer/model", json={"model": "x"})
    r = await client.put(
        "/api/digital_humans/observer/model",
        json={"model": ""},
    )
    assert r.status_code == 200
    r2 = await client.get("/api/digital_humans/observer/model")
    assert r2.json()["current"] == ""


@pytest.mark.asyncio
async def test_put_dh_model_bad_body(client):
    r = await client.put(
        "/api/digital_humans/executor/model",
        json={"model": 123},
    )
    assert r.status_code == 400


# ---------------- /prompt ----------------

@pytest.mark.asyncio
async def test_get_dh_prompt_creates_empty_file_if_missing(client, tmp_path):
    r = await client.get("/api/digital_humans/executor/prompt")
    assert r.status_code == 200
    assert r.json()["template"] == ""
    assert r.json()["variables"] == []


@pytest.mark.asyncio
async def test_put_and_get_dh_prompt_roundtrip(client):
    template = "Hello {name}, you live at {location}. Your task is {task}."
    r = await client.put(
        "/api/digital_humans/executor/prompt",
        json={"template": template},
    )
    assert r.status_code == 200
    assert set(r.json()["variables"]) == {"name", "location", "task"}

    r2 = await client.get("/api/digital_humans/executor/prompt")
    data = r2.json()
    assert data["template"] == template
    assert set(data["variables"]) == {"name", "location", "task"}


@pytest.mark.asyncio
async def test_put_dh_prompt_bad_body(client):
    r = await client.put(
        "/api/digital_humans/executor/prompt",
        json={"template": 42},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_put_dh_prompt_unknown_dh_404(client):
    r = await client.put(
        "/api/digital_humans/nobody/prompt",
        json={"template": "x"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_dh_prompt_unknown_dh_404(client):
    r = await client.get("/api/digital_humans/nobody/prompt")
    assert r.status_code == 404
