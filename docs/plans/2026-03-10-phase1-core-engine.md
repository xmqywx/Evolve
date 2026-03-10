# Phase 1: Core Engine - Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core scheduling service, Claude Code execution engine, SQLite persistence, and CLI — making MyAgent usable from the terminal.

**Architecture:** FastAPI server manages a task queue persisted in SQLite. The executor calls `claude -p --dangerously-skip-permissions --output-format stream-json` and streams results back. A CLI provides submit/list/watch/cancel/search commands. All async, single-process.

**Tech Stack:** Python 3.14, FastAPI, uvicorn, aiosqlite, pydantic, pyyaml

---

## File Map

| File | Responsibility |
|------|---------------|
| `requirements.txt` | Python dependencies |
| `config.yaml` | All configuration (paths, limits, ports) |
| `myagent/config.py` | Load and validate config.yaml into Pydantic models |
| `myagent/db.py` | SQLite connection, schema init, query helpers |
| `myagent/models.py` | Pydantic models for Task, TaskLog, Message |
| `myagent/executor.py` | Call claude CLI, parse stream-json, stream results |
| `myagent/scheduler.py` | Task queue loop: pick next task, run executor, store results |
| `myagent/server.py` | FastAPI app: API endpoints for tasks + SSE + health |
| `myagent/cli.py` | CLI entry point: submit, list, watch, cancel, search |
| `myagent/__init__.py` | Package init |
| `tests/test_models.py` | Test Pydantic models |
| `tests/test_db.py` | Test SQLite operations |
| `tests/test_executor.py` | Test executor with mock claude CLI |
| `tests/test_scheduler.py` | Test scheduler logic |
| `tests/test_server.py` | Test API endpoints |
| `tests/conftest.py` | Shared fixtures |

---

## Chunk 1: Project Setup + Config + Models

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `config.yaml`
- Create: `myagent/__init__.py`

- [ ] **Step 1: Create virtual environment**

```bash
cd /Users/ying/Documents/MyAgent
python3 -m venv .venv
source .venv/bin/activate
```

- [ ] **Step 2: Create requirements.txt**

```
fastapi==0.133.1
uvicorn[standard]==0.41.0
httpx==0.28.1
aiosqlite>=0.20.0
pydantic>=2.12.0
pyyaml>=6.0
```

- [ ] **Step 3: Install dependencies**

```bash
cd /Users/ying/Documents/MyAgent
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: all packages install successfully.

- [ ] **Step 4: Create config.yaml**

```yaml
agent:
  name: "MyAgent"
  data_dir: "/Users/ying/Documents/MyAgent"
  db_path: "/Users/ying/Documents/MyAgent/agent.db"

claude:
  binary: "claude"
  default_cwd: "/Users/ying/Documents"
  timeout: 600
  args:
    - "--dangerously-skip-permissions"
    - "--output-format"
    - "stream-json"

scheduler:
  max_daily_calls: 50
  min_interval_seconds: 30

server:
  host: "0.0.0.0"
  port: 8090
  secret: "change-me-to-a-real-secret"
```

- [ ] **Step 5: Create package init**

```python
# myagent/__init__.py
```

- [ ] **Step 6: Init git repo**

```bash
cd /Users/ying/Documents/MyAgent
git init
```

- [ ] **Step 7: Create .gitignore**

```
.venv/
__pycache__/
*.pyc
agent.db
backups/
.env
```

- [ ] **Step 8: Commit scaffolding**

```bash
git add requirements.txt config.yaml myagent/__init__.py .gitignore
git commit -m "chore: project scaffolding with deps and config"
```

---

### Task 2: Config loader

**Files:**
- Create: `myagent/config.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test for config loading**

```python
# tests/test_config.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/ying/Documents/MyAgent
source .venv/bin/activate
pip install pytest pytest-asyncio
python -m pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'myagent.config'`

- [ ] **Step 3: Create conftest.py**

```python
# tests/conftest.py
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
""".format(tmp=str(tmp_path)))
    return str(cfg)
```

- [ ] **Step 4: Implement config.py**

```python
# myagent/config.py
from pathlib import Path

import yaml
from pydantic import BaseModel


class AgentSettings(BaseModel):
    name: str
    data_dir: str
    db_path: str


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


class AgentConfig(BaseModel):
    agent: AgentSettings
    claude: ClaudeSettings
    scheduler: SchedulerSettings
    server: ServerSettings


def load_config(path: str) -> AgentConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(p) as f:
        data = yaml.safe_load(f)
    return AgentConfig(**data)
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_config.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add myagent/config.py tests/conftest.py tests/test_config.py
git commit -m "feat: config loader with pydantic validation"
```

---

### Task 3: Pydantic models

**Files:**
- Create: `myagent/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_models.py
import pytest
from myagent.models import Task, TaskStatus, Message, TaskSource


def test_task_creation():
    task = Task(
        prompt="Fix the bug",
        source=TaskSource.CLI,
        cwd="/tmp",
    )
    assert task.id.startswith("task_")
    assert task.status == TaskStatus.PENDING
    assert task.prompt == "Fix the bug"
    assert task.priority == "normal"


def test_task_status_transitions():
    task = Task(prompt="test", source=TaskSource.CLI, cwd="/tmp")
    assert task.status == TaskStatus.PENDING

    task.status = TaskStatus.RUNNING
    assert task.status == TaskStatus.RUNNING

    task.status = TaskStatus.DONE
    assert task.status == TaskStatus.DONE


def test_message_creation():
    msg = Message(
        source=TaskSource.CLI,
        content="hello",
    )
    assert msg.id.startswith("msg_")
    assert msg.sender == "ying"
```

- [ ] **Step 2: Run test to verify fails**

```bash
python -m pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement models.py**

```python
# myagent/models.py
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
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_models.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add myagent/models.py tests/test_models.py
git commit -m "feat: pydantic models for Task and Message"
```

---

## Chunk 2: Database Layer

### Task 4: SQLite database

**Files:**
- Create: `myagent/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_db.py
import pytest
import pytest_asyncio
from myagent.db import Database
from myagent.models import Task, TaskStatus, TaskSource


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_create_and_get_task(db):
    task = Task(prompt="test task", source=TaskSource.CLI, cwd="/tmp")
    await db.create_task(task)

    retrieved = await db.get_task(task.id)
    assert retrieved is not None
    assert retrieved.prompt == "test task"
    assert retrieved.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_update_task_status(db):
    task = Task(prompt="test", source=TaskSource.CLI, cwd="/tmp")
    await db.create_task(task)

    await db.update_task(task.id, status=TaskStatus.RUNNING)
    updated = await db.get_task(task.id)
    assert updated.status == TaskStatus.RUNNING


@pytest.mark.asyncio
async def test_list_tasks(db):
    for i in range(3):
        t = Task(prompt=f"task {i}", source=TaskSource.CLI, cwd="/tmp")
        await db.create_task(t)

    tasks = await db.list_tasks()
    assert len(tasks) == 3


@pytest.mark.asyncio
async def test_get_next_pending_task(db):
    t1 = Task(prompt="first", source=TaskSource.CLI, cwd="/tmp", priority="normal")
    t2 = Task(prompt="urgent", source=TaskSource.CLI, cwd="/tmp", priority="high")
    await db.create_task(t1)
    await db.create_task(t2)

    next_task = await db.get_next_pending()
    assert next_task is not None
    assert next_task.priority == "high"


@pytest.mark.asyncio
async def test_log_task_event(db):
    task = Task(prompt="test", source=TaskSource.CLI, cwd="/tmp")
    await db.create_task(task)
    await db.log_event(task.id, "text", content="hello world")

    logs = await db.get_task_logs(task.id)
    assert len(logs) == 1
    assert logs[0]["content"] == "hello world"


@pytest.mark.asyncio
async def test_fts_search(db):
    task = Task(prompt="fix shopify webhook", source=TaskSource.CLI, cwd="/tmp")
    await db.create_task(task)
    await db.create_memory(task.id, summary="Fixed Shopify webhook signature verification bug", tags='["shopify", "webhook"]')

    results = await db.search_memories("shopify webhook")
    assert len(results) >= 1
    assert "shopify" in results[0]["summary"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_db.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'myagent.db'`

- [ ] **Step 3: Implement db.py**

```python
# myagent/db.py
import json
from datetime import datetime, timezone
from uuid import uuid4

import aiosqlite

from myagent.models import Task, TaskStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    prompt TEXT NOT NULL,
    priority TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'pending',
    cwd TEXT,
    created_at TEXT,
    started_at TEXT,
    finished_at TEXT,
    result_summary TEXT,
    raw_output TEXT,
    token_usage INTEGER,
    session_id TEXT,
    complexity TEXT
);

CREATE TABLE IF NOT EXISTS task_logs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    timestamp TEXT DEFAULT (datetime('now')),
    event_type TEXT,
    tool_name TEXT,
    content TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    summary TEXT NOT NULL,
    key_decisions TEXT,
    files_changed TEXT,
    commands_run TEXT,
    tags TEXT,
    project TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT,
    content TEXT,
    first_seen TEXT,
    last_updated TEXT,
    source_task_ids TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_search USING fts5(
    summary, key_decisions, tags,
    content='memories',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memory_search(rowid, summary, key_decisions, tags)
    VALUES (new.id, new.summary, new.key_decisions, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memory_search(memory_search, rowid, summary, key_decisions, tags)
    VALUES ('delete', old.id, old.summary, old.key_decisions, old.tags);
END;
"""

PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def init(self):
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def create_task(self, task: Task):
        await self._conn.execute(
            """INSERT INTO tasks (id, source, prompt, priority, status, cwd,
               created_at, started_at, finished_at, result_summary, raw_output,
               token_usage, session_id, complexity)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task.id, task.source.value, task.prompt, task.priority,
             task.status.value, task.cwd, task.created_at.isoformat(),
             None, None, None, None, None, None, None),
        )
        await self._conn.commit()

    async def get_task(self, task_id: str) -> Task | None:
        cursor = await self._conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_task(row)

    async def update_task(self, task_id: str, **fields):
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values())
        # Convert enums to their values
        vals = [v.value if hasattr(v, "value") else v for v in vals]
        vals.append(task_id)
        await self._conn.execute(
            f"UPDATE tasks SET {sets} WHERE id = ?", vals
        )
        await self._conn.commit()

    async def list_tasks(self, limit: int = 50, status: str | None = None) -> list[Task]:
        query = "SELECT * FROM tasks"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_task(r) for r in rows]

    async def get_next_pending(self) -> Task | None:
        cursor = await self._conn.execute(
            """SELECT * FROM tasks WHERE status = 'pending'
               ORDER BY CASE priority
                 WHEN 'high' THEN 0
                 WHEN 'normal' THEN 1
                 WHEN 'low' THEN 2
               END, created_at ASC LIMIT 1"""
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_task(row)

    async def log_event(self, task_id: str, event_type: str,
                        tool_name: str | None = None, content: str | None = None):
        await self._conn.execute(
            """INSERT INTO task_logs (id, task_id, event_type, tool_name, content)
               VALUES (?, ?, ?, ?, ?)""",
            (f"log_{uuid4().hex[:12]}", task_id, event_type, tool_name, content),
        )
        await self._conn.commit()

    async def get_task_logs(self, task_id: str) -> list[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM task_logs WHERE task_id = ? ORDER BY timestamp",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def create_memory(self, task_id: str, summary: str,
                            key_decisions: str | None = None,
                            files_changed: str | None = None,
                            tags: str | None = None,
                            project: str | None = None):
        await self._conn.execute(
            """INSERT INTO memories (task_id, summary, key_decisions,
               files_changed, tags, project)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (task_id, summary, key_decisions, files_changed, tags, project),
        )
        await self._conn.commit()

    async def search_memories(self, query: str, limit: int = 10) -> list[dict]:
        cursor = await self._conn.execute(
            """SELECT m.*, ms.rank
               FROM memory_search ms
               JOIN memories m ON m.id = ms.rowid
               WHERE memory_search MATCH ?
               ORDER BY ms.rank
               LIMIT ?""",
            (query, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    def _row_to_task(self, row) -> Task:
        d = dict(row)
        return Task(
            id=d["id"],
            source=d["source"],
            prompt=d["prompt"],
            priority=d["priority"],
            status=d["status"],
            cwd=d["cwd"] or ".",
            created_at=d["created_at"],
            result_summary=d.get("result_summary"),
            raw_output=d.get("raw_output"),
            token_usage=d.get("token_usage"),
            session_id=d.get("session_id"),
            complexity=d.get("complexity"),
        )
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_db.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add myagent/db.py tests/test_db.py
git commit -m "feat: SQLite database layer with FTS5 search"
```

---

## Chunk 3: Executor + Scheduler

### Task 5: Claude Code executor

**Files:**
- Create: `myagent/executor.py`
- Create: `tests/test_executor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_executor.py
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch
from myagent.executor import Executor
from myagent.config import ClaudeSettings


@pytest.fixture
def claude_settings(tmp_path):
    # Use 'echo' as a fake claude binary for testing
    script = tmp_path / "fake_claude.sh"
    script.write_text("""#!/bin/bash
echo '{"type":"assistant","content":"Hello from Claude"}'
echo '{"type":"result","content":"Task completed","session_id":"sess_123"}'
""")
    script.chmod(0o755)
    return ClaudeSettings(
        binary=str(script),
        default_cwd=str(tmp_path),
        timeout=10,
        args=[],
    )


@pytest.mark.asyncio
async def test_executor_runs_command(claude_settings):
    executor = Executor(claude_settings)
    events = []
    async for event in executor.execute("test prompt", cwd=claude_settings.default_cwd):
        events.append(event)
    assert len(events) >= 1


@pytest.mark.asyncio
async def test_executor_captures_session_id(claude_settings):
    executor = Executor(claude_settings)
    events = []
    async for event in executor.execute("test", cwd=claude_settings.default_cwd):
        events.append(event)
    result_events = [e for e in events if e.get("type") == "result"]
    assert len(result_events) == 1
    assert result_events[0].get("session_id") == "sess_123"


@pytest.mark.asyncio
async def test_executor_timeout(tmp_path):
    script = tmp_path / "slow_claude.sh"
    script.write_text("#!/bin/bash\nsleep 30\n")
    script.chmod(0o755)
    settings = ClaudeSettings(binary=str(script), default_cwd=str(tmp_path), timeout=1, args=[])
    executor = Executor(settings)
    events = []
    async for event in executor.execute("test", cwd=str(tmp_path)):
        events.append(event)
    error_events = [e for e in events if e.get("type") == "error"]
    assert len(error_events) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_executor.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement executor.py**

```python
# myagent/executor.py
import asyncio
import json
from typing import AsyncIterator

from myagent.config import ClaudeSettings


class Executor:
    def __init__(self, settings: ClaudeSettings):
        self.settings = settings

    async def execute(
        self,
        prompt: str,
        cwd: str | None = None,
        extra_args: list[str] | None = None,
    ) -> AsyncIterator[dict]:
        working_dir = cwd or self.settings.default_cwd
        cmd = [self.settings.binary] + self.settings.args
        if extra_args:
            cmd.extend(extra_args)
        cmd.extend(["-p", prompt])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )

            try:
                async for line in self._read_lines_with_timeout(proc):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        yield event
                    except json.JSONDecodeError:
                        yield {"type": "raw", "content": line}

                await asyncio.wait_for(proc.wait(), timeout=5)

            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                yield {"type": "error", "content": "Task timed out"}

        except FileNotFoundError:
            yield {"type": "error", "content": f"Binary not found: {self.settings.binary}"}
        except Exception as e:
            yield {"type": "error", "content": str(e)}

    async def _read_lines_with_timeout(self, proc) -> AsyncIterator[str]:
        while True:
            try:
                line = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=self.settings.timeout
                )
                if not line:
                    break
                yield line.decode("utf-8", errors="replace")
            except asyncio.TimeoutError:
                raise
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_executor.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add myagent/executor.py tests/test_executor.py
git commit -m "feat: Claude Code executor with streaming and timeout"
```

---

### Task 6: Scheduler

**Files:**
- Create: `myagent/scheduler.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scheduler.py
import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from myagent.scheduler import Scheduler, RateLimiter
from myagent.db import Database
from myagent.models import Task, TaskStatus, TaskSource
from myagent.config import ClaudeSettings, SchedulerSettings


@pytest.fixture
def scheduler_settings():
    return SchedulerSettings(max_daily_calls=5, min_interval_seconds=0)


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


def test_rate_limiter_allows():
    rl = RateLimiter(max_daily=5, min_interval=0)
    assert rl.can_execute() is True


def test_rate_limiter_blocks_over_limit():
    rl = RateLimiter(max_daily=2, min_interval=0)
    rl.record_call()
    rl.record_call()
    assert rl.can_execute() is False


def test_rate_limiter_resets_daily():
    rl = RateLimiter(max_daily=1, min_interval=0)
    rl.record_call()
    assert rl.can_execute() is False
    rl.reset_daily()
    assert rl.can_execute() is True


@pytest.mark.asyncio
async def test_scheduler_picks_up_task(db, scheduler_settings, tmp_path):
    # Create a fake claude that outputs a result
    script = tmp_path / "fake_claude.sh"
    script.write_text('#!/bin/bash\necho \'{"type":"result","content":"done"}\'\n')
    script.chmod(0o755)
    claude_settings = ClaudeSettings(binary=str(script), default_cwd=str(tmp_path), timeout=5, args=[])

    task = Task(prompt="test", source=TaskSource.CLI, cwd=str(tmp_path))
    await db.create_task(task)

    scheduler = Scheduler(db, claude_settings, scheduler_settings)
    processed = await scheduler.process_one()
    assert processed is True

    updated = await db.get_task(task.id)
    assert updated.status == TaskStatus.DONE
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_scheduler.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement scheduler.py**

```python
# myagent/scheduler.py
import asyncio
import logging
from datetime import datetime, timezone, date

from myagent.config import ClaudeSettings, SchedulerSettings
from myagent.db import Database
from myagent.executor import Executor
from myagent.models import TaskStatus

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_daily: int, min_interval: float):
        self.max_daily = max_daily
        self.min_interval = min_interval
        self._today_count = 0
        self._today_date = date.today()
        self._last_call: float = 0

    def can_execute(self) -> bool:
        self._check_day_rollover()
        if self._today_count >= self.max_daily:
            return False
        import time
        if self.min_interval > 0 and (time.time() - self._last_call) < self.min_interval:
            return False
        return True

    def record_call(self):
        import time
        self._check_day_rollover()
        self._today_count += 1
        self._last_call = time.time()

    def reset_daily(self):
        self._today_count = 0
        self._today_date = date.today()

    @property
    def remaining(self) -> int:
        self._check_day_rollover()
        return max(0, self.max_daily - self._today_count)

    def _check_day_rollover(self):
        if date.today() != self._today_date:
            self._today_count = 0
            self._today_date = date.today()


class Scheduler:
    def __init__(self, db: Database, claude_settings: ClaudeSettings,
                 scheduler_settings: SchedulerSettings):
        self.db = db
        self.executor = Executor(claude_settings)
        self.rate_limiter = RateLimiter(
            max_daily=scheduler_settings.max_daily_calls,
            min_interval=scheduler_settings.min_interval_seconds,
        )
        self._running = False
        self._current_task_id: str | None = None

    async def process_one(self) -> bool:
        """Pick up and execute the next pending task. Returns True if a task was processed."""
        if not self.rate_limiter.can_execute():
            logger.warning("Rate limit reached (%d remaining)", self.rate_limiter.remaining)
            return False

        task = await self.db.get_next_pending()
        if not task:
            return False

        self._current_task_id = task.id
        await self.db.update_task(task.id,
                                  status=TaskStatus.RUNNING,
                                  started_at=datetime.now(timezone.utc).isoformat())

        self.rate_limiter.record_call()
        raw_parts = []
        last_content = ""

        try:
            async for event in self.executor.execute(task.prompt, cwd=task.cwd):
                event_type = event.get("type", "unknown")
                content = event.get("content", "")

                await self.db.log_event(task.id, event_type, content=str(event))

                if event_type == "error":
                    await self.db.update_task(
                        task.id,
                        status=TaskStatus.FAILED,
                        finished_at=datetime.now(timezone.utc).isoformat(),
                        result_summary=content,
                    )
                    self._current_task_id = None
                    return True

                if isinstance(content, str) and content:
                    raw_parts.append(content)
                    last_content = content

                session_id = event.get("session_id")
                if session_id:
                    await self.db.update_task(task.id, session_id=session_id)

            summary = last_content or "Task completed"
            await self.db.update_task(
                task.id,
                status=TaskStatus.DONE,
                finished_at=datetime.now(timezone.utc).isoformat(),
                result_summary=summary[:1000],
                raw_output="\n".join(raw_parts)[:50000],
            )

        except Exception as e:
            logger.exception("Task %s failed", task.id)
            await self.db.update_task(
                task.id,
                status=TaskStatus.FAILED,
                finished_at=datetime.now(timezone.utc).isoformat(),
                result_summary=str(e),
            )

        self._current_task_id = None
        return True

    async def run_loop(self, poll_interval: float = 2.0):
        """Main scheduler loop. Runs until stopped."""
        self._running = True
        logger.info("Scheduler started")
        while self._running:
            try:
                processed = await self.process_one()
                if not processed:
                    await asyncio.sleep(poll_interval)
            except Exception:
                logger.exception("Scheduler loop error")
                await asyncio.sleep(poll_interval)

    def stop(self):
        self._running = False

    async def cancel_task(self, task_id: str) -> bool:
        task = await self.db.get_task(task_id)
        if not task:
            return False
        if task.status == TaskStatus.PENDING:
            await self.db.update_task(task_id, status=TaskStatus.FAILED,
                                      result_summary="Cancelled by user")
            return True
        return False
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_scheduler.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add myagent/scheduler.py tests/test_scheduler.py
git commit -m "feat: task scheduler with rate limiting"
```

---

## Chunk 4: Server + CLI

### Task 7: FastAPI server

**Files:**
- Create: `myagent/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_server.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from myagent.server import create_app
from myagent.config import load_config


@pytest_asyncio.fixture
async def app(config_yaml):
    application = await create_app(config_yaml)
    yield application
    # cleanup: close db
    await application.state.db.close()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test",
                           headers={"Authorization": "Bearer test"}) as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_submit_task(client):
    resp = await client.post("/api/tasks", json={
        "prompt": "test task",
        "cwd": "/tmp",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"].startswith("task_")
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_list_tasks(client):
    await client.post("/api/tasks", json={"prompt": "t1", "cwd": "/tmp"})
    await client.post("/api/tasks", json={"prompt": "t2", "cwd": "/tmp"})
    resp = await client.get("/api/tasks")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_task(client):
    create = await client.post("/api/tasks", json={"prompt": "find me", "cwd": "/tmp"})
    task_id = create.json()["id"]
    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["prompt"] == "find me"


@pytest.mark.asyncio
async def test_auth_required(config_yaml):
    application = await create_app(config_yaml)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/tasks")
        assert resp.status_code == 401
    await application.state.db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_server.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement server.py**

```python
# myagent/server.py
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from myagent.config import load_config, AgentConfig
from myagent.db import Database
from myagent.models import Task, TaskSource
from myagent.scheduler import Scheduler

logger = logging.getLogger(__name__)


class TaskSubmit(BaseModel):
    prompt: str
    cwd: str | None = None
    priority: str = "normal"
    source: str = "web"


async def verify_auth(request: Request):
    config: AgentConfig = request.app.state.config
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing authorization")
    token = auth[7:]
    if token != config.server.secret:
        raise HTTPException(401, "Invalid token")


async def create_app(config_path: str) -> FastAPI:
    config = load_config(config_path)
    db = Database(config.agent.db_path)
    await db.init()

    app = FastAPI(title=config.agent.name)
    app.state.config = config
    app.state.db = db
    app.state.scheduler = Scheduler(db, config.claude, config.scheduler)

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "name": config.agent.name,
            "scheduler_remaining": app.state.scheduler.rate_limiter.remaining,
        }

    @app.post("/api/tasks", status_code=201, dependencies=[Depends(verify_auth)])
    async def submit_task(body: TaskSubmit):
        task = Task(
            prompt=body.prompt,
            source=TaskSource(body.source) if body.source in TaskSource.__members__.values() else TaskSource.WEB,
            cwd=body.cwd or config.claude.default_cwd,
            priority=body.priority,
        )
        await db.create_task(task)
        return task.model_dump()

    @app.get("/api/tasks", dependencies=[Depends(verify_auth)])
    async def list_tasks(status: str | None = None, limit: int = 50):
        tasks = await db.list_tasks(limit=limit, status=status)
        return [t.model_dump() for t in tasks]

    @app.get("/api/tasks/{task_id}", dependencies=[Depends(verify_auth)])
    async def get_task(task_id: str):
        task = await db.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        return task.model_dump()

    @app.post("/api/tasks/{task_id}/cancel", dependencies=[Depends(verify_auth)])
    async def cancel_task(task_id: str):
        success = await app.state.scheduler.cancel_task(task_id)
        if not success:
            raise HTTPException(400, "Cannot cancel task")
        return {"cancelled": True}

    @app.get("/api/tasks/{task_id}/logs", dependencies=[Depends(verify_auth)])
    async def get_task_logs(task_id: str):
        logs = await db.get_task_logs(task_id)
        return logs

    @app.get("/api/memory/search", dependencies=[Depends(verify_auth)])
    async def search_memory(q: str, limit: int = 10):
        results = await db.search_memories(q, limit=limit)
        return results

    @app.get("/api/status", dependencies=[Depends(verify_auth)])
    async def status():
        return {
            "scheduler_running": app.state.scheduler._running,
            "current_task": app.state.scheduler._current_task_id,
            "daily_remaining": app.state.scheduler.rate_limiter.remaining,
        }

    return app


async def run_server(config_path: str):
    import uvicorn
    app = await create_app(config_path)

    # Start scheduler in background
    scheduler_task = asyncio.create_task(app.state.scheduler.run_loop())

    server_config = uvicorn.Config(
        app, host=app.state.config.server.host,
        port=app.state.config.server.port,
        log_level="info",
    )
    server = uvicorn.Server(server_config)

    try:
        await server.serve()
    finally:
        app.state.scheduler.stop()
        scheduler_task.cancel()
        await app.state.db.close()
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_server.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add myagent/server.py tests/test_server.py
git commit -m "feat: FastAPI server with task API and auth"
```

---

### Task 8: CLI

**Files:**
- Create: `myagent/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_cli.py
import pytest
from unittest.mock import patch, AsyncMock
from myagent.cli import parse_args


def test_parse_submit():
    args = parse_args(["submit", "Fix the bug in auth.py"])
    assert args.command == "submit"
    assert args.prompt == "Fix the bug in auth.py"


def test_parse_list():
    args = parse_args(["list"])
    assert args.command == "list"


def test_parse_search():
    args = parse_args(["search", "shopify webhook"])
    assert args.command == "search"
    assert args.query == "shopify webhook"


def test_parse_cancel():
    args = parse_args(["cancel", "task_123"])
    assert args.command == "cancel"
    assert args.task_id == "task_123"


def test_parse_watch():
    args = parse_args(["watch", "task_123"])
    assert args.command == "watch"
    assert args.task_id == "task_123"


def test_parse_status():
    args = parse_args(["status"])
    assert args.command == "status"
```

- [ ] **Step 2: Run test to verify fails**

```bash
python -m pytest tests/test_cli.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement cli.py**

```python
# myagent/cli.py
import argparse
import asyncio
import json
import sys

import httpx


DEFAULT_URL = "http://127.0.0.1:8090"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="agent", description="MyAgent CLI")
    parser.add_argument("--url", default=DEFAULT_URL, help="Server URL")
    parser.add_argument("--token", default=None, help="Auth token")

    sub = parser.add_subparsers(dest="command")

    # submit
    p_submit = sub.add_parser("submit", help="Submit a task")
    p_submit.add_argument("prompt", help="Task prompt")
    p_submit.add_argument("--cwd", default=None, help="Working directory")
    p_submit.add_argument("--priority", default="normal", choices=["low", "normal", "high"])

    # list
    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--status", default=None)
    p_list.add_argument("--limit", type=int, default=20)

    # watch
    p_watch = sub.add_parser("watch", help="Watch task output")
    p_watch.add_argument("task_id", help="Task ID")

    # cancel
    p_cancel = sub.add_parser("cancel", help="Cancel a task")
    p_cancel.add_argument("task_id", help="Task ID")

    # search
    p_search = sub.add_parser("search", help="Search memories")
    p_search.add_argument("query", help="Search query")

    # status
    sub.add_parser("status", help="System status")

    return parser.parse_args(argv)


def _get_token(args) -> str:
    if args.token:
        return args.token
    import os
    return os.environ.get("MYAGENT_TOKEN", "change-me")


async def _run(args):
    token = _get_token(args)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=args.url, headers=headers, timeout=30) as client:
        if args.command == "submit":
            resp = await client.post("/api/tasks", json={
                "prompt": args.prompt,
                "cwd": args.cwd,
                "priority": args.priority,
                "source": "cli",
            })
            data = resp.json()
            print(f"Task created: {data['id']}")
            print(f"Status: {data['status']}")

        elif args.command == "list":
            params = {"limit": args.limit}
            if args.status:
                params["status"] = args.status
            resp = await client.get("/api/tasks", params=params)
            tasks = resp.json()
            if not tasks:
                print("No tasks.")
                return
            for t in tasks:
                status_icon = {"pending": "...", "running": ">>", "done": "OK", "failed": "XX"}.get(t["status"], "??")
                print(f"[{status_icon}] {t['id']}  {t['prompt'][:60]}")

        elif args.command == "watch":
            resp = await client.get(f"/api/tasks/{args.task_id}")
            if resp.status_code == 404:
                print("Task not found")
                return
            task = resp.json()
            print(f"Task: {task['id']}")
            print(f"Status: {task['status']}")
            print(f"Prompt: {task['prompt']}")
            if task.get("result_summary"):
                print(f"\nResult:\n{task['result_summary']}")

            logs_resp = await client.get(f"/api/tasks/{args.task_id}/logs")
            logs = logs_resp.json()
            if logs:
                print(f"\nLogs ({len(logs)} events):")
                for log in logs[-20:]:
                    print(f"  [{log.get('event_type', '?')}] {str(log.get('content', ''))[:100]}")

        elif args.command == "cancel":
            resp = await client.post(f"/api/tasks/{args.task_id}/cancel")
            if resp.status_code == 200:
                print(f"Cancelled: {args.task_id}")
            else:
                print(f"Failed: {resp.json().get('detail', 'unknown error')}")

        elif args.command == "search":
            resp = await client.get("/api/memory/search", params={"q": args.query})
            results = resp.json()
            if not results:
                print("No results.")
                return
            for r in results:
                print(f"---")
                print(f"Task: {r.get('task_id', '?')}")
                print(f"Summary: {r.get('summary', '')}")
                if r.get("tags"):
                    print(f"Tags: {r['tags']}")

        elif args.command == "status":
            resp = await client.get("/api/status")
            data = resp.json()
            print(f"Scheduler running: {data.get('scheduler_running', False)}")
            print(f"Current task: {data.get('current_task', 'idle')}")
            print(f"Daily calls remaining: {data.get('daily_remaining', '?')}")

        else:
            print("Use: agent submit|list|watch|cancel|search|status")


def main(argv: list[str] | None = None):
    args = parse_args(argv)
    if not args.command:
        parse_args(["--help"])
        return
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_cli.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add myagent/cli.py tests/test_cli.py
git commit -m "feat: CLI with submit/list/watch/cancel/search/status"
```

---

### Task 9: Entry point + integration test

**Files:**
- Create: `run.py`
- Create: `agent` (CLI wrapper script)
- Create: `tests/test_integration.py`

- [ ] **Step 1: Create run.py (server entry point)**

```python
# run.py
import asyncio
import sys

from myagent.server import run_server

CONFIG_PATH = "config.yaml"

if __name__ == "__main__":
    config = sys.argv[1] if len(sys.argv) > 1 else CONFIG_PATH
    asyncio.run(run_server(config))
```

- [ ] **Step 2: Create agent CLI wrapper**

```bash
#!/usr/bin/env bash
# agent — CLI wrapper
DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/.venv/bin/activate" 2>/dev/null
exec python3 -m myagent.cli "$@"
```

Make it executable:

```bash
chmod +x /Users/ying/Documents/MyAgent/agent
```

- [ ] **Step 3: Add __main__.py for module execution**

```python
# myagent/__main__.py
from myagent.cli import main
main()
```

- [ ] **Step 4: Write integration test**

```python
# tests/test_integration.py
"""Integration test: submit a task via API, verify it lands in DB."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from myagent.server import create_app


@pytest_asyncio.fixture
async def app(config_yaml):
    application = await create_app(config_yaml)
    yield application
    application.state.scheduler.stop()
    await application.state.db.close()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test",
                           headers={"Authorization": "Bearer test"}) as c:
        yield c


@pytest.mark.asyncio
async def test_full_task_lifecycle(client, app):
    # Submit
    resp = await client.post("/api/tasks", json={
        "prompt": "echo hello",
        "cwd": "/tmp",
        "source": "cli",
    })
    assert resp.status_code == 201
    task_id = resp.json()["id"]

    # Verify in list
    resp = await client.get("/api/tasks")
    ids = [t["id"] for t in resp.json()]
    assert task_id in ids

    # Get by ID
    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.json()["status"] == "pending"

    # Process with scheduler (uses fake claude from conftest)
    processed = await app.state.scheduler.process_one()
    assert processed is True

    # Verify completed
    resp = await client.get(f"/api/tasks/{task_id}")
    task = resp.json()
    assert task["status"] in ("done", "failed")

    # Logs exist
    resp = await client.get(f"/api/tasks/{task_id}/logs")
    assert resp.status_code == 200
```

- [ ] **Step 5: Run all tests**

```bash
cd /Users/ying/Documents/MyAgent
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: All tests pass (18+ tests).

- [ ] **Step 6: Commit**

```bash
git add run.py agent myagent/__main__.py tests/test_integration.py
git commit -m "feat: entry points and integration test - Phase 1 complete"
```

---

## Chunk 5: Manual Verification

### Task 10: End-to-end manual test

- [ ] **Step 1: Start the server**

```bash
cd /Users/ying/Documents/MyAgent
source .venv/bin/activate
python run.py
```

Expected: Server starts on `0.0.0.0:8090`, scheduler begins polling.

- [ ] **Step 2: In another terminal, submit a task**

```bash
cd /Users/ying/Documents/MyAgent
export MYAGENT_TOKEN="change-me-to-a-real-secret"
./agent submit "List all Python files in ~/Documents/frida_scripts"
```

Expected: prints `Task created: task_...`

- [ ] **Step 3: Check task list**

```bash
./agent list
```

Expected: shows the submitted task. Status transitions from `...` (pending) to `>>` (running) to `OK` (done).

- [ ] **Step 4: Watch the result**

```bash
./agent watch <task_id from step 2>
```

Expected: shows task details and Claude Code's output.

- [ ] **Step 5: Test search**

```bash
./agent search "Python files"
```

Expected: (empty for now, memories will work once Phase 3 adds summarization)

- [ ] **Step 6: Test status**

```bash
./agent status
```

Expected: shows scheduler running, daily calls remaining.

- [ ] **Step 7: Verify health endpoint**

```bash
curl http://127.0.0.1:8090/health
```

Expected: `{"status":"ok","name":"MyAgent",...}`

---

## Phase 1 Deliverables

After completing all tasks:

| What | Status |
|------|--------|
| FastAPI server with task API | Working |
| Claude Code executor with streaming | Working |
| SQLite persistence (tasks, logs, memories, FTS5) | Working |
| Task scheduler with rate limiting | Working |
| CLI (submit/list/watch/cancel/search/status) | Working |
| Bearer token auth | Working |
| 18+ automated tests | Passing |

**Next:** Phase 2 (飞书通知 + wdao.chat 中继) — will be a separate plan.
