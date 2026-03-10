import pytest


@pytest.fixture
def config_yaml(tmp_path):
    """Provides a minimal valid config.yaml for testing."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("""
agent:
  name: "TestAgent"
  data_dir: "{tmp}"
  db_path: "{tmp}/agent.db"
claude:
  binary: "echo"
  default_cwd: "{tmp}"
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
""".format(tmp=str(tmp_path)))
    return str(cfg)
