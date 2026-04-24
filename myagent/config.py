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


class CodexSettings(BaseModel):
    binary: str = "codex"
    default_cwd: str = "."
    args: list[str] = []
    model: str = ""
    profile: str = ""
    sessions_dir: str = "~/.codex/sessions"


class SchedulerSettings(BaseModel):
    max_daily_calls: int = 50
    min_interval_seconds: int = 30


class ServerSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 3818
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


class ClaudeMemSettings(BaseModel):
    db_path: str = "~/.claude-mem/claude-mem.db"
    enabled: bool = True


class ThinkingSettings(BaseModel):
    daily_review_enabled: bool = True
    daily_review_hour: int = 8  # 24h format, local time
    daily_review_minute: int = 0


class ScannerSettings(BaseModel):
    process_interval: int = 5
    claude_projects_dir: str = "~/.claude/projects"
    max_messages_cached: int = 200


class ChatSettings(BaseModel):
    max_messages_before_rotate: int = 50
    context_max_tokens: int = 2000
    persona_files: list[str] = [
        "persona/identity.md",
        "persona/about_ying.md",
        "persona/principles.md",
    ]


class SurvivalSettings(BaseModel):
    enabled: bool = True
    workspace: str = "/Users/ying/Documents/workspace"
    notify_feishu: bool = True
    provider: str = "claude"  # claude | codex


class ProfileSettings(BaseModel):
    slack_token: str = ""
    slack_enabled: bool = False
    wechat_enabled: bool = False
    wechat_key: str = ""
    git_scan_enabled: bool = True
    terminal_history_enabled: bool = True
    browser_history_enabled: bool = True
    scan_interval_hours: int = 4


class JWTSettings(BaseModel):
    secret: str = "change-me-jwt-secret"
    expiry_hours: int = 168  # 7 days


class AgentConfig(BaseModel):
    agent: AgentSettings
    claude: ClaudeSettings
    codex: CodexSettings = CodexSettings()
    scheduler: SchedulerSettings
    server: ServerSettings
    feishu: FeishuSettings = FeishuSettings()
    relay: RelaySettings = RelaySettings()
    doubao: DoubaoSettings = DoubaoSettings()
    postgres: PostgresSettings = PostgresSettings()
    scanner: ScannerSettings = ScannerSettings()
    claude_mem: ClaudeMemSettings = ClaudeMemSettings()
    thinking: ThinkingSettings = ThinkingSettings()
    chat: ChatSettings = ChatSettings()
    survival: SurvivalSettings = SurvivalSettings()
    profile: ProfileSettings = ProfileSettings()
    jwt: JWTSettings = JWTSettings()


def load_config(path: str) -> AgentConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(p) as f:
        data = yaml.safe_load(f)
    return AgentConfig(**data)
