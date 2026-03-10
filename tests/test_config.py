import pytest
from myagent.config import load_config, AgentConfig


def test_load_config_from_yaml(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("""
agent:
  name: "TestAgent"
  data_dir: "/tmp/test"
  db_path: "/tmp/test/agent.db"
claude:
  binary: "claude"
  default_cwd: "/tmp"
  timeout: 300
  args: ["--dangerously-skip-permissions"]
scheduler:
  max_daily_calls: 10
  min_interval_seconds: 5
server:
  host: "127.0.0.1"
  port: 9090
  secret: "test-secret"
""")
    config = load_config(str(cfg_file))
    assert config.agent.name == "TestAgent"
    assert config.claude.timeout == 300
    assert config.scheduler.max_daily_calls == 10
    assert config.server.port == 9090


def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/config.yaml")


def test_config_with_feishu(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("""
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
feishu:
  app_id: "cli_test_app"
  app_secret: "cli_test_secret"
  bot_webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
  chat_id: "oc_test123"
relay:
  url: "ws://localhost:9876/ws"
  token: "relay_secret"
""")
    from myagent.config import load_config
    config = load_config(str(cfg))
    assert config.feishu.app_id == "cli_test_app"
    assert config.feishu.bot_webhook == "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
    assert config.relay.url == "ws://localhost:9876/ws"
    assert config.relay.token == "relay_secret"
