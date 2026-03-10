from pathlib import Path

import yaml
from pydantic import BaseModel


class AgentSettings(BaseModel):
    name: str
    data_dir: str
    db_path: str
    persona_dir: str = ""


class ClaudeSettings(BaseModel):
    binary: str = "claude"
    default_cwd: str = "."
    timeout: int = 600
    args: list[str] = []


class SchedulerSettings(BaseModel):
    max_daily_calls: int = 50
    min_interval_seconds: int = 30


class ServerSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8090
    secret: str = "change-me"


class FeishuSettings(BaseModel):
    app_id: str = ""
    app_secret: str = ""
    bot_webhook: str = ""
    chat_id: str = ""
    enabled: bool = True


class RelaySettings(BaseModel):
    url: str = "ws://localhost:9876/ws"
    token: str = ""
    reconnect_interval: int = 5
    enabled: bool = True


class DoubaoSettings(BaseModel):
    api_key: str = ""
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    chat_model: str = "doubao-seed-2-0-pro-260215"
    embedding_model: str = "doubao-embedding-large-text-240915"
    enabled: bool = True


class PostgresSettings(BaseModel):
    dsn: str = "postgresql://ying@localhost/myagent"
    enabled: bool = True


class AgentConfig(BaseModel):
    agent: AgentSettings
    claude: ClaudeSettings
    scheduler: SchedulerSettings
    server: ServerSettings
    feishu: FeishuSettings = FeishuSettings()
    relay: RelaySettings = RelaySettings()
    doubao: DoubaoSettings = DoubaoSettings()
    postgres: PostgresSettings = PostgresSettings()


def load_config(path: str) -> AgentConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(p) as f:
        data = yaml.safe_load(f)
    return AgentConfig(**data)
