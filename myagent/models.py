from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class TaskSource(str, Enum):
    CLI = "cli"
    WEB = "web"
    FEISHU = "feishu"
    CRON = "cron"


def _task_id() -> str:
    return f"task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"


def _msg_id() -> str:
    return f"msg_{uuid4().hex[:12]}"


class Task(BaseModel):
    id: str = Field(default_factory=_task_id)
    source: TaskSource
    prompt: str
    priority: str = "normal"
    status: TaskStatus = TaskStatus.PENDING
    cwd: str = "."
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_summary: str | None = None
    raw_output: str | None = None
    token_usage: int | None = None
    session_id: str | None = None
    complexity: str | None = None


class Message(BaseModel):
    id: str = Field(default_factory=_msg_id)
    source: TaskSource = TaskSource.CLI
    sender: str = "ying"
    content: str
    reply_to: str | None = None
    attachments: list[str] = []
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
