"""Tests for DH Sovereignty config extensions (spec 2026-04-25)."""

import yaml

from myagent.config import AgentConfig, MCPPoolEntry, load_config


MINIMAL_BASE = """
agent:
  name: TestAgent
  data_dir: /tmp
  db_path: /tmp/agent.db
claude:
  binary: echo
scheduler:
  max_daily_calls: 10
server:
  port: 9999
  secret: test
"""


def test_minimal_config_has_empty_mcp_pool_and_defaults(tmp_path):
    """A config with no new fields still parses; new fields default to empty."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        MINIMAL_BASE
        + """
digital_humans:
  executor:
    persona_dir: persona/executor
    cmux_session: mycmux-executor
"""
    )
    config = load_config(str(cfg))
    assert isinstance(config, AgentConfig)
    assert config.mcp_pool == {}
    dh = config.digital_humans["executor"]
    assert dh.model == ""
    assert dh.prompt_template_file == ""
    assert dh.mcp_servers == []
    # Backwards-compat: existing fields untouched.
    assert dh.skill_whitelist == []
    assert dh.provider == "codex"


def test_config_with_new_fields_parses(tmp_path):
    """New DH-sovereignty fields parse through yaml → pydantic correctly."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        MINIMAL_BASE
        + """
mcp_pool:
  filesystem:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    env:
      FOO: bar
  github:
    command: docker
    args: ["run", "ghcr.io/github/github-mcp-server"]
digital_humans:
  executor:
    persona_dir: persona/executor
    cmux_session: mycmux-executor
    model: "claude-opus-4-7"
    prompt_template_file: "executor_prompt.md"
    mcp_servers: ["filesystem", "github"]
    skill_whitelist: ["*"]
"""
    )
    config = load_config(str(cfg))
    assert set(config.mcp_pool.keys()) == {"filesystem", "github"}
    fs = config.mcp_pool["filesystem"]
    assert fs.command == "npx"
    assert fs.args == ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    assert fs.env == {"FOO": "bar"}
    gh = config.mcp_pool["github"]
    assert gh.command == "docker"
    assert gh.env == {}

    dh = config.digital_humans["executor"]
    assert dh.model == "claude-opus-4-7"
    assert dh.prompt_template_file == "executor_prompt.md"
    assert dh.mcp_servers == ["filesystem", "github"]
    assert dh.skill_whitelist == ["*"]


def test_mcp_pool_entry_yaml_roundtrip():
    """MCPPoolEntry with args + env round-trips through yaml."""
    original = MCPPoolEntry(
        command="npx",
        args=["-y", "some-server", "--flag"],
        env={"TOKEN": "abc", "DEBUG": "1"},
    )
    dumped = yaml.safe_dump(original.model_dump())
    loaded = yaml.safe_load(dumped)
    restored = MCPPoolEntry(**loaded)
    assert restored.command == original.command
    assert restored.args == original.args
    assert restored.env == original.env
