# Session Monitor Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MyAgent discovers, monitors, and displays all Claude Code sessions running on the Mac with real-time WebSocket updates, a React Dashboard (mobile-friendly with Ant Design), and Feishu session queries.

**Architecture:** A SessionScanner watches processes and JSONL files, feeding a SessionRegistry that pushes changes through a WebSocket Hub to a React frontend. A `myagent` wrapper CLI proxies Claude for future remote control. JWT replaces cookie auth.

**Tech Stack:** Python 3.14, FastAPI, aiosqlite, watchfiles, React 18, TypeScript, Vite, Ant Design, WebSocket, PyJWT

---

## File Structure

### New Files

| File | Responsibility |
|---|---|
| `myagent/scanner.py` | Process scanning + JSONL file parsing |
| `myagent/session_registry.py` | Session state management, change detection, notifications |
| `myagent/ws_hub.py` | WebSocket connection management and broadcasting |
| `myagent/auth.py` | JWT token creation and verification |
| `tests/test_scanner.py` | Scanner tests |
| `tests/test_session_registry.py` | Registry tests |
| `tests/test_ws_hub.py` | WebSocket hub tests |
| `tests/test_auth.py` | JWT auth tests |
| `web/` | React frontend (full directory) |
| `pyproject.toml` | Package config with `myagent` CLI entry point |

### Modified Files

| File | Changes |
|---|---|
| `myagent/config.py` | Add `ScannerSettings`, `JWTSettings` to `AgentConfig` |
| `myagent/db.py` | Add `sessions` table to schema, CRUD methods |
| `myagent/models.py` | Add `SessionStatus` enum, `SessionInfo` model |
| `myagent/server.py` | Add session API endpoints, WebSocket endpoints, JWT auth, serve React static |
| `myagent/cli.py` | Add `wrap` subcommand for Claude wrapper |
| `myagent/router.py` | Add session query routing (system:sessions, system:session_detail) |
| `myagent/feishu.py` | Add `build_sessions_card()` for session list card |
| `config.yaml` | Add `scanner` and `jwt` sections |
| `requirements.txt` | Add `watchfiles`, `pyjwt` |

---

## Chunk 1: Backend Foundation

### Task 1: Configuration and Models

**Files:**
- Modify: `myagent/config.py`
- Modify: `myagent/models.py`
- Modify: `config.yaml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Add ScannerSettings and JWTSettings to config.py**

Add after `PostgresSettings`:

```python
class ScannerSettings(BaseModel):
    process_interval: int = 5
    claude_projects_dir: str = "~/.claude/projects"
    max_messages_cached: int = 200

class JWTSettings(BaseModel):
    secret: str = "change-me-jwt-secret"
    expiry_hours: int = 168  # 7 days
```

Add to `AgentConfig`:

```python
class AgentConfig(BaseModel):
    # ... existing fields ...
    scanner: ScannerSettings = ScannerSettings()
    jwt: JWTSettings = JWTSettings()
```

- [ ] **Step 2: Add SessionStatus and SessionInfo to models.py**

```python
class SessionStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    FINISHED = "finished"

class SessionInfo(BaseModel):
    id: str
    pid: int | None = None
    cwd: str
    project: str
    tty: str | None = None
    started_at: datetime
    last_active: datetime
    status: SessionStatus = SessionStatus.ACTIVE
    is_wrapped: bool = False
```

- [ ] **Step 3: Add scanner and jwt sections to config.yaml**

```yaml
scanner:
  process_interval: 5
  claude_projects_dir: "~/.claude/projects"
  max_messages_cached: 200

jwt:
  secret: "myagent-jwt-secret-change-me"
  expiry_hours: 168
```

- [ ] **Step 4: Run existing config tests to verify no breakage**

Run: `source .venv/bin/activate && python -m pytest tests/test_config.py -v`
Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add myagent/config.py myagent/models.py config.yaml
git commit -m "feat: add scanner and JWT config, session models"
```

---

### Task 2: Database Sessions Table

**Files:**
- Modify: `myagent/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing tests for session CRUD**

Add to `tests/test_db.py`:

```python
@pytest.mark.asyncio
async def test_create_and_get_session(db):
    from myagent.models import SessionInfo, SessionStatus
    from datetime import datetime, timezone
    session = SessionInfo(
        id="sess-001",
        cwd="/Users/ying/Documents/test",
        project="test",
        started_at=datetime.now(timezone.utc),
        last_active=datetime.now(timezone.utc),
    )
    await db.upsert_session(session)
    result = await db.get_session("sess-001")
    assert result is not None
    assert result.id == "sess-001"
    assert result.project == "test"

@pytest.mark.asyncio
async def test_list_sessions(db):
    from myagent.models import SessionInfo, SessionStatus
    from datetime import datetime, timezone
    for i in range(3):
        s = SessionInfo(
            id=f"sess-{i}",
            cwd=f"/path/{i}",
            project=f"proj-{i}",
            started_at=datetime.now(timezone.utc),
            last_active=datetime.now(timezone.utc),
            status=SessionStatus.ACTIVE if i < 2 else SessionStatus.FINISHED,
        )
        await db.upsert_session(s)
    all_sessions = await db.list_sessions()
    assert len(all_sessions) == 3
    active = await db.list_sessions(status=SessionStatus.ACTIVE)
    assert len(active) == 2

@pytest.mark.asyncio
async def test_upsert_session_updates(db):
    from myagent.models import SessionInfo, SessionStatus
    from datetime import datetime, timezone
    session = SessionInfo(
        id="sess-upd",
        cwd="/path/a",
        project="proj-a",
        started_at=datetime.now(timezone.utc),
        last_active=datetime.now(timezone.utc),
        status=SessionStatus.ACTIVE,
    )
    await db.upsert_session(session)
    session.status = SessionStatus.FINISHED
    await db.upsert_session(session)
    result = await db.get_session("sess-upd")
    assert result.status == SessionStatus.FINISHED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_db.py::test_create_and_get_session -v`
Expected: FAIL (upsert_session not defined)

- [ ] **Step 3: Add sessions table to schema and implement CRUD**

Add to `_SCHEMA` in `db.py`:

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    pid INTEGER,
    cwd TEXT NOT NULL,
    project TEXT NOT NULL,
    tty TEXT,
    started_at TEXT NOT NULL,
    last_active TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    is_wrapped BOOLEAN NOT NULL DEFAULT 0
);
```

Add methods to `Database` class:

```python
async def upsert_session(self, session: SessionInfo) -> None:
    from myagent.models import SessionInfo
    await self._conn.execute(
        """INSERT INTO sessions (id, pid, cwd, project, tty, started_at, last_active, status, is_wrapped)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             pid=excluded.pid, cwd=excluded.cwd, project=excluded.project,
             tty=excluded.tty, last_active=excluded.last_active,
             status=excluded.status, is_wrapped=excluded.is_wrapped""",
        (
            session.id, session.pid, session.cwd, session.project,
            session.tty, session.started_at.isoformat(),
            session.last_active.isoformat(), session.status.value,
            session.is_wrapped,
        ),
    )
    await self._conn.commit()

async def get_session(self, session_id: str) -> SessionInfo | None:
    from myagent.models import SessionInfo, SessionStatus
    cursor = await self._conn.execute(
        "SELECT * FROM sessions WHERE id = ?", (session_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return _row_to_session(row)

async def list_sessions(self, status: SessionStatus | None = None, limit: int = 50) -> list[SessionInfo]:
    from myagent.models import SessionInfo, SessionStatus
    if status is not None:
        cursor = await self._conn.execute(
            "SELECT * FROM sessions WHERE status = ? ORDER BY last_active DESC LIMIT ?",
            (status.value, limit),
        )
    else:
        cursor = await self._conn.execute(
            "SELECT * FROM sessions ORDER BY last_active DESC LIMIT ?", (limit,)
        )
    rows = await cursor.fetchall()
    return [_row_to_session(r) for r in rows]
```

Add helper:

```python
def _row_to_session(row: aiosqlite.Row) -> SessionInfo:
    from myagent.models import SessionInfo, SessionStatus
    d = dict(row)
    d["status"] = SessionStatus(d["status"])
    d["is_wrapped"] = bool(d["is_wrapped"])
    if d.get("started_at"):
        d["started_at"] = datetime.fromisoformat(d["started_at"])
    if d.get("last_active"):
        d["last_active"] = datetime.fromisoformat(d["last_active"])
    return SessionInfo(**d)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_db.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add myagent/db.py tests/test_db.py
git commit -m "feat: add sessions table and CRUD to database"
```

---

### Task 3: JWT Authentication

**Files:**
- Create: `myagent/auth.py`
- Test: `tests/test_auth.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add pyjwt to requirements.txt**

Add line: `pyjwt>=2.8.0`

- [ ] **Step 2: Install dependency**

Run: `source .venv/bin/activate && pip install pyjwt`

- [ ] **Step 3: Write failing tests**

Create `tests/test_auth.py`:

```python
import pytest
from myagent.auth import create_token, verify_token

def test_create_and_verify_token():
    token = create_token("test-secret", expiry_hours=1)
    assert token is not None
    payload = verify_token(token, "test-secret")
    assert payload is not None
    assert "exp" in payload

def test_verify_invalid_token():
    result = verify_token("invalid.token.here", "test-secret")
    assert result is None

def test_verify_wrong_secret():
    token = create_token("secret-a", expiry_hours=1)
    result = verify_token(token, "secret-b")
    assert result is None
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_auth.py -v`
Expected: FAIL (module not found)

- [ ] **Step 5: Implement auth.py**

Create `myagent/auth.py`:

```python
"""JWT authentication utilities."""
from __future__ import annotations

import time
from typing import Any

import jwt


def create_token(secret: str, expiry_hours: int = 168) -> str:
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + expiry_hours * 3600,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_token(token: str, secret: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except (jwt.InvalidTokenError, jwt.DecodeError):
        return None
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_auth.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add myagent/auth.py tests/test_auth.py requirements.txt
git commit -m "feat: add JWT authentication module"
```

---

### Task 4: Session Scanner

**Files:**
- Create: `myagent/scanner.py`
- Test: `tests/test_scanner.py`

- [ ] **Step 1: Add watchfiles to requirements.txt**

Add line: `watchfiles>=1.0.0`

Run: `source .venv/bin/activate && pip install watchfiles`

- [ ] **Step 2: Write failing tests for process scanning**

Create `tests/test_scanner.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from myagent.scanner import SessionScanner, parse_ps_output, parse_jsonl_messages

def test_parse_ps_output():
    """Parse ps output into process info dicts."""
    lines = [
        "  1234 ttys001  Mon Mar  9 22:06:40 2026     claude --dangerously-skip-permissions",
        "  5678 ttys002  Tue Mar 10 10:33:44 2026     claude -p hello",
    ]
    result = parse_ps_output(lines)
    assert len(result) == 2
    assert result[0]["pid"] == 1234
    assert result[0]["tty"] == "ttys001"
    assert result[1]["pid"] == 5678

def test_parse_ps_output_empty():
    result = parse_ps_output([])
    assert result == []

def test_parse_jsonl_messages():
    """Parse JSONL lines into conversation messages, skipping internal events."""
    import json
    lines = [
        json.dumps({"type": "user", "uuid": "u1", "message": {"role": "user", "content": "hello"}, "sessionId": "s1"}),
        json.dumps({"type": "assistant", "uuid": "a1", "message": {"role": "assistant", "content": [{"type": "text", "text": "hi"}]}, "sessionId": "s1"}),
        json.dumps({"type": "progress", "data": {"type": "tool_use"}}),
        json.dumps({"type": "file-history-snapshot", "snapshot": {}}),
        json.dumps({"type": "system", "uuid": "sys1", "message": {"content": "system msg"}, "sessionId": "s1"}),
    ]
    result = parse_jsonl_messages(lines)
    assert len(result) == 3  # user, assistant, system — skip progress, file-history-snapshot
    assert result[0]["type"] == "user"
    assert result[1]["type"] == "assistant"
    assert result[2]["type"] == "system"

def test_parse_jsonl_messages_invalid_json():
    lines = ["not json", '{"type": "user", "uuid": "u1", "message": {"role": "user", "content": "ok"}, "sessionId": "s1"}']
    result = parse_jsonl_messages(lines)
    assert len(result) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_scanner.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement scanner.py**

Create `myagent/scanner.py`:

```python
"""Session scanner - discovers Claude processes and reads JSONL session files."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Awaitable

from myagent.config import ScannerSettings
from myagent.models import SessionInfo, SessionStatus

logger = logging.getLogger(__name__)

# Internal Claude event types to skip
SKIP_TYPES = {"progress", "file-history-snapshot", "queue-operation", "change", "last-prompt"}


def parse_ps_output(lines: list[str]) -> list[dict[str, Any]]:
    """Parse `ps -eo pid,tty,lstart,command` output lines for claude processes."""
    results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(
            r"\s*(\d+)\s+(\S+)\s+(.+?)\s+(claude\s.*|/.*claude\s.*)",
            line,
        )
        if not match:
            continue
        pid = int(match.group(1))
        tty = match.group(2)
        # lstart_str = match.group(3)  # complex to parse, use /proc or ps -o etimes
        results.append({"pid": pid, "tty": tty if tty != "??" else None})
    return results


def parse_jsonl_messages(lines: list[str]) -> list[dict[str, Any]]:
    """Parse JSONL lines, returning only conversation messages."""
    messages = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg_type = data.get("type", "")
        if msg_type in SKIP_TYPES:
            continue
        if msg_type in ("user", "assistant", "system"):
            messages.append(data)
    return messages


def extract_project_name(cwd: str) -> str:
    """Extract short project name from working directory path."""
    parts = Path(cwd).parts
    # Use last directory component
    if len(parts) >= 2:
        return parts[-1]
    return cwd


def cwd_to_projects_dir(cwd: str, claude_projects_dir: str) -> str:
    """Convert a cwd to the ~/.claude/projects/ directory name."""
    # Claude uses path with / replaced by -
    return cwd.replace("/", "-")


class SessionScanner:
    """Scans for Claude processes and reads their session JSONL files."""

    def __init__(
        self,
        settings: ScannerSettings,
        on_change: Callable[[list[SessionInfo], list[dict]], Awaitable[None]] | None = None,
    ) -> None:
        self._settings = settings
        self._on_change = on_change
        self._running = False
        self._sessions: dict[str, SessionInfo] = {}
        self._message_cache: dict[str, list[dict]] = {}  # session_id -> messages

    @property
    def sessions(self) -> dict[str, SessionInfo]:
        return dict(self._sessions)

    def get_messages(self, session_id: str) -> list[dict]:
        return list(self._message_cache.get(session_id, []))

    async def scan_processes(self) -> list[dict[str, Any]]:
        """Scan for running claude processes."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ps", "-eo", "pid,tty,lstart,command",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            lines = stdout.decode().split("\n")
            claude_lines = [l for l in lines if "claude" in l and "grep" not in l]
            return parse_ps_output(claude_lines)
        except Exception:
            logger.exception("Failed to scan processes")
            return []

    async def get_process_cwd(self, pid: int) -> str | None:
        """Get working directory of a process via lsof."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "lsof", "-p", str(pid),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            for line in stdout.decode().split("\n"):
                if "cwd" in line:
                    parts = line.split()
                    if parts:
                        return parts[-1]
        except Exception:
            pass
        return None

    def scan_jsonl_files(self) -> dict[str, Path]:
        """Find all session JSONL files across all project dirs."""
        projects_dir = Path(os.path.expanduser(self._settings.claude_projects_dir))
        result = {}
        if not projects_dir.exists():
            return result
        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            for jsonl_file in project_dir.glob("*.jsonl"):
                session_id = jsonl_file.stem
                # Skip non-UUID filenames
                if len(session_id) < 30:
                    continue
                result[session_id] = jsonl_file
        return result

    def read_session_messages(self, jsonl_path: Path) -> list[dict]:
        """Read and parse messages from a JSONL session file."""
        try:
            text = jsonl_path.read_text(encoding="utf-8")
            lines = text.split("\n")
            messages = parse_jsonl_messages(lines)
            max_cached = self._settings.max_messages_cached
            return messages[-max_cached:] if len(messages) > max_cached else messages
        except Exception:
            logger.exception("Failed to read session file: %s", jsonl_path)
            return []

    async def run_scan_loop(self) -> None:
        """Main scan loop - runs periodically."""
        self._running = True
        while self._running:
            try:
                await self._scan_once()
            except Exception:
                logger.exception("Scan error")
            await asyncio.sleep(self._settings.process_interval)

    async def _scan_once(self) -> None:
        """Perform one full scan cycle."""
        # 1. Get running processes
        processes = await self.scan_processes()
        active_pids = set()
        pid_to_info: dict[int, dict] = {}

        for p in processes:
            pid = p["pid"]
            active_pids.add(pid)
            cwd = await self.get_process_cwd(pid)
            if cwd:
                pid_to_info[pid] = {**p, "cwd": cwd}

        # 2. Scan JSONL files
        jsonl_files = self.scan_jsonl_files()

        # 3. Match and update sessions
        updated = False
        for session_id, jsonl_path in jsonl_files.items():
            messages = self.read_session_messages(jsonl_path)
            if not messages:
                continue

            # Extract session info from first message
            first_msg = messages[0]
            cwd = first_msg.get("cwd", "")
            session_id_from_msg = first_msg.get("sessionId", session_id)

            # Check if process is still running
            pid = None
            for p_pid, p_info in pid_to_info.items():
                if p_info.get("cwd") == cwd:
                    pid = p_pid
                    break

            # Determine status
            if pid is not None:
                status = SessionStatus.ACTIVE
            else:
                status = SessionStatus.FINISHED

            # Parse timestamps
            last_msg = messages[-1]
            started_at = datetime.now(timezone.utc)  # fallback
            last_active = datetime.now(timezone.utc)

            session = SessionInfo(
                id=session_id_from_msg,
                pid=pid,
                cwd=cwd,
                project=extract_project_name(cwd),
                tty=pid_to_info.get(pid, {}).get("tty") if pid else None,
                started_at=started_at,
                last_active=last_active,
                status=status,
            )

            old = self._sessions.get(session.id)
            if old != session or session.id not in self._message_cache:
                updated = True

            self._sessions[session.id] = session
            self._message_cache[session.id] = messages

        if updated and self._on_change:
            sessions_list = list(self._sessions.values())
            await self._on_change(sessions_list, [])

    def stop(self) -> None:
        self._running = False
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_scanner.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add myagent/scanner.py tests/test_scanner.py requirements.txt
git commit -m "feat: add session scanner with process and JSONL discovery"
```

---

### Task 5: Session Registry

**Files:**
- Create: `myagent/session_registry.py`
- Test: `tests/test_session_registry.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_session_registry.py`:

```python
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from myagent.session_registry import SessionRegistry
from myagent.models import SessionInfo, SessionStatus

@pytest.fixture
def registry():
    return SessionRegistry(max_messages=50)

def test_update_session(registry):
    session = SessionInfo(
        id="s1", cwd="/path/a", project="proj-a",
        started_at=datetime.now(timezone.utc),
        last_active=datetime.now(timezone.utc),
    )
    changed = registry.update_session(session, [])
    assert changed is True
    assert registry.get_session("s1") is not None

def test_update_session_no_change(registry):
    session = SessionInfo(
        id="s1", cwd="/path/a", project="proj-a",
        started_at=datetime.now(timezone.utc),
        last_active=datetime.now(timezone.utc),
    )
    registry.update_session(session, [])
    changed = registry.update_session(session, [])
    assert changed is False

def test_get_all_sessions(registry):
    for i in range(3):
        s = SessionInfo(
            id=f"s{i}", cwd=f"/path/{i}", project=f"proj-{i}",
            started_at=datetime.now(timezone.utc),
            last_active=datetime.now(timezone.utc),
        )
        registry.update_session(s, [])
    result = registry.get_all_sessions()
    assert len(result) == 3

def test_get_messages(registry):
    session = SessionInfo(
        id="s1", cwd="/path/a", project="proj-a",
        started_at=datetime.now(timezone.utc),
        last_active=datetime.now(timezone.utc),
    )
    messages = [{"type": "user", "uuid": "u1", "message": {"content": "hello"}}]
    registry.update_session(session, messages)
    result = registry.get_messages("s1")
    assert len(result) == 1
    assert result[0]["uuid"] == "u1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_session_registry.py -v`
Expected: FAIL

- [ ] **Step 3: Implement session_registry.py**

Create `myagent/session_registry.py`:

```python
"""Session registry - in-memory session state with change detection."""
from __future__ import annotations

import logging
from typing import Any, Callable

from myagent.models import SessionInfo

logger = logging.getLogger(__name__)


class SessionRegistry:
    """Manages session state in memory with change notifications."""

    def __init__(self, max_messages: int = 200) -> None:
        self._sessions: dict[str, SessionInfo] = {}
        self._messages: dict[str, list[dict]] = {}
        self._max_messages = max_messages
        self._listeners: list[Callable[[str, str, Any], None]] = []

    def add_listener(self, callback: Callable[[str, str, Any], None]) -> None:
        """Add a change listener. Called with (event_type, session_id, data)."""
        self._listeners.append(callback)

    def _notify(self, event_type: str, session_id: str, data: Any = None) -> None:
        for listener in self._listeners:
            try:
                listener(event_type, session_id, data)
            except Exception:
                logger.exception("Listener error")

    def update_session(
        self, session: SessionInfo, messages: list[dict] | None = None
    ) -> bool:
        """Update a session. Returns True if anything changed."""
        old = self._sessions.get(session.id)
        changed = False

        if old is None:
            changed = True
            self._notify("session_new", session.id, session)
        elif old != session:
            changed = True
            self._notify("session_updated", session.id, session)

        self._sessions[session.id] = session

        if messages is not None:
            old_count = len(self._messages.get(session.id, []))
            trimmed = messages[-self._max_messages:]
            self._messages[session.id] = trimmed
            if len(trimmed) != old_count:
                changed = True
                # Notify with only new messages
                new_msgs = trimmed[old_count:] if old_count < len(trimmed) else []
                if new_msgs:
                    self._notify("new_messages", session.id, new_msgs)

        return changed

    def get_session(self, session_id: str) -> SessionInfo | None:
        return self._sessions.get(session_id)

    def get_all_sessions(self) -> list[SessionInfo]:
        return list(self._sessions.values())

    def get_messages(self, session_id: str) -> list[dict]:
        return list(self._messages.get(session_id, []))

    def get_active_sessions(self) -> list[SessionInfo]:
        from myagent.models import SessionStatus
        return [s for s in self._sessions.values() if s.status == SessionStatus.ACTIVE]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_session_registry.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add myagent/session_registry.py tests/test_session_registry.py
git commit -m "feat: add session registry with change detection"
```

---

### Task 6: WebSocket Hub

**Files:**
- Create: `myagent/ws_hub.py`
- Test: `tests/test_ws_hub.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ws_hub.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from myagent.ws_hub import WebSocketHub

@pytest.mark.asyncio
async def test_hub_subscribe_and_broadcast():
    hub = WebSocketHub()
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    hub.subscribe("sessions", ws)
    await hub.broadcast("sessions", {"type": "update", "data": "test"})
    ws.send_json.assert_called_once_with({"type": "update", "data": "test"})

@pytest.mark.asyncio
async def test_hub_unsubscribe():
    hub = WebSocketHub()
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    hub.subscribe("sessions", ws)
    hub.unsubscribe("sessions", ws)
    await hub.broadcast("sessions", {"type": "update"})
    ws.send_json.assert_not_called()

@pytest.mark.asyncio
async def test_hub_dead_connection_removed():
    hub = WebSocketHub()
    ws = AsyncMock()
    ws.send_json = AsyncMock(side_effect=Exception("closed"))
    hub.subscribe("sessions", ws)
    await hub.broadcast("sessions", {"type": "update"})
    # Dead connection should be removed
    assert len(hub._channels.get("sessions", set())) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_ws_hub.py -v`
Expected: FAIL

- [ ] **Step 3: Implement ws_hub.py**

Create `myagent/ws_hub.py`:

```python
"""WebSocket hub - manages connections and broadcasts updates."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketHub:
    """Manages WebSocket subscriptions by channel."""

    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = {}

    def subscribe(self, channel: str, ws: WebSocket) -> None:
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(ws)
        logger.info("WS subscribed to %s (total: %d)", channel, len(self._channels[channel]))

    def unsubscribe(self, channel: str, ws: WebSocket) -> None:
        if channel in self._channels:
            self._channels[channel].discard(ws)
            logger.info("WS unsubscribed from %s (total: %d)", channel, len(self._channels[channel]))

    def unsubscribe_all(self, ws: WebSocket) -> None:
        for channel in self._channels:
            self._channels[channel].discard(ws)

    async def broadcast(self, channel: str, data: dict[str, Any]) -> int:
        if channel not in self._channels:
            return 0
        dead: list[WebSocket] = []
        sent = 0
        for ws in self._channels[channel]:
            try:
                await ws.send_json(data)
                sent += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._channels[channel].discard(ws)
        return sent

    def channel_count(self, channel: str) -> int:
        return len(self._channels.get(channel, set()))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_ws_hub.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add myagent/ws_hub.py tests/test_ws_hub.py
git commit -m "feat: add WebSocket hub for real-time broadcasting"
```

---

## Chunk 2: Server Integration

### Task 7: Server - Session API and WebSocket Endpoints

**Files:**
- Modify: `myagent/server.py`
- Test: `tests/test_server.py` (add new tests)

- [ ] **Step 1: Write failing tests for session API**

Add to `tests/test_server.py`:

```python
@pytest.mark.asyncio
async def test_session_list(web_app):
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login to get JWT token
        resp = await client.post("/api/login", json={"secret": "test"})
        token = resp.json()["token"]
        # List sessions
        resp = await client.get("/api/sessions", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

@pytest.mark.asyncio
async def test_jwt_login(web_app):
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/login", json={"secret": "test"})
        assert resp.status_code == 200
        assert "token" in resp.json()

@pytest.mark.asyncio
async def test_jwt_login_wrong_secret(web_app):
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/login", json={"secret": "wrong"})
        assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_server.py::test_jwt_login -v`
Expected: FAIL

- [ ] **Step 3: Add JWT login endpoint, session API, and WebSocket endpoints to server.py**

Key additions to `server.py`:

1. Import new modules (`auth`, `scanner`, `session_registry`, `ws_hub`)
2. Add `POST /api/login` endpoint returning JWT
3. Add `verify_jwt` dependency using `auth.verify_token`
4. Add `GET /api/sessions` and `GET /api/sessions/{id}` endpoints
5. Add `POST /api/sessions/register` for wrapper registration
6. Add `WS /ws/sessions` and `WS /ws/sessions/{id}` WebSocket endpoints
7. Initialize scanner, registry, hub in `create_app()`
8. Start scanner loop in `run_server()`
9. Serve React static files from `web/dist/` if directory exists

See spec for full endpoint list. Keep existing endpoints working but switch auth dependency to accept both JWT Bearer and legacy Bearer secret.

- [ ] **Step 4: Run all tests**

Run: `source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All PASS (both new and existing)

- [ ] **Step 5: Commit**

```bash
git add myagent/server.py tests/test_server.py
git commit -m "feat: add session API, WebSocket endpoints, JWT auth to server"
```

---

### Task 8: Feishu Session Queries

**Files:**
- Modify: `myagent/router.py`
- Modify: `myagent/feishu.py`
- Modify: `myagent/server.py` (on_relay_message handler)
- Test: `tests/test_router.py`

- [ ] **Step 1: Add session command patterns to router.py**

Add to `SYSTEM_PATTERNS`:

```python
r"(我的|查看|有哪些)?(会话|session)": "sessions",
r"(.*)(怎么样了|在做什么|进度)": "session_detail",
```

Add to `_extract_system_detail` valid commands: `"sessions"`, `"session_detail"`

- [ ] **Step 2: Add build_sessions_card to feishu.py**

```python
def build_sessions_card(sessions: list[dict]) -> dict:
    """Build a Feishu card showing active sessions."""
    elements = []
    status_icon = {"active": "[Running]", "idle": "[Idle]", "finished": "[Done]"}

    for s in sessions:
        icon = status_icon.get(s.get("status", ""), "")
        project = s.get("project", "unknown")
        cwd = s.get("cwd", "")
        last_active = s.get("last_active", "")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**{icon} {project}** | `{cwd}`\nLast active: {last_active}"},
        })

    if not elements:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "No active sessions"},
        })

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "MyAgent Session Monitor"}],
    })

    return {
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": f"Claude Sessions ({len(sessions)})"},
        },
        "elements": elements,
    }
```

- [ ] **Step 3: Handle session commands in server.py on_relay_message**

Add to `_handle_system_command`:

```python
elif detail == "sessions":
    sessions = registry.get_active_sessions()
    if not sessions:
        return "No active Claude sessions"
    lines = []
    for s in sessions:
        status_icon = {"active": "[Running]", "idle": "[Idle]", "finished": "[Done]"}
        icon = status_icon.get(s.status.value, "")
        lines.append(f"{icon} {s.project} | {s.cwd}")
    return "Active sessions:\n" + "\n".join(lines)
```

- [ ] **Step 4: Run router tests**

Run: `source .venv/bin/activate && python -m pytest tests/test_router.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add myagent/router.py myagent/feishu.py myagent/server.py tests/test_router.py
git commit -m "feat: add Feishu session query commands"
```

---

### Task 9: CLI Wrapper (wrap subcommand)

**Files:**
- Modify: `myagent/cli.py`
- Test: `tests/test_cli.py`
- Create: `pyproject.toml`

- [ ] **Step 1: Write failing test for wrap argument parsing**

Add to `tests/test_cli.py`:

```python
def test_parse_wrap_command():
    from myagent.cli import parse_args
    args = parse_args(["wrap", "--", "--dangerously-skip-permissions"])
    assert args.command == "wrap"
    assert args.claude_args == ["--dangerously-skip-permissions"]

def test_parse_wrap_no_args():
    from myagent.cli import parse_args
    args = parse_args(["wrap"])
    assert args.command == "wrap"
    assert args.claude_args == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_cli.py::test_parse_wrap_command -v`
Expected: FAIL

- [ ] **Step 3: Add wrap subcommand to cli.py**

Add to `parse_args`:

```python
# wrap
p_wrap = sub.add_parser("wrap", help="Wrap claude with MyAgent monitoring")
p_wrap.add_argument("claude_args", nargs="*", default=[],
                     help="Arguments to pass to claude")
```

Add to `main`:

```python
elif args.command == "wrap":
    from myagent.wrapper import run_wrapper
    import asyncio
    asyncio.run(run_wrapper(args.claude_args, args.url, args.secret))
```

- [ ] **Step 4: Create myagent/wrapper.py**

```python
"""Claude wrapper - proxies stdin/stdout and registers with MyAgent server."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)


async def run_wrapper(
    claude_args: list[str],
    server_url: str = "http://127.0.0.1:8090",
    secret: str = "",
) -> None:
    """Spawn claude as subprocess, proxy I/O, register with server."""
    session_id = uuid4().hex
    cwd = os.getcwd()

    cmd = ["claude"] + claude_args
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        cwd=cwd,
    )

    # Register with server (best-effort)
    try:
        headers = {"Authorization": f"Bearer {secret}"} if secret else {}
        async with httpx.AsyncClient(base_url=server_url, headers=headers) as client:
            await client.post("/api/sessions/register", json={
                "session_id": session_id,
                "pid": proc.pid,
                "cwd": cwd,
            })
    except Exception:
        pass  # Server may not be running

    # Forward signals
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: proc.send_signal(s))

    # Wait for process to finish
    returncode = await proc.wait()
    sys.exit(returncode)
```

- [ ] **Step 5: Create pyproject.toml**

```toml
[project]
name = "myagent"
version = "0.1.0"
description = "MyAgent AI digital twin"
requires-python = ">=3.12"

[project.scripts]
myagent = "myagent.cli:main"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

- [ ] **Step 6: Install as editable package**

Run: `source .venv/bin/activate && pip install -e .`

- [ ] **Step 7: Run tests**

Run: `source .venv/bin/activate && python -m pytest tests/test_cli.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add myagent/cli.py myagent/wrapper.py tests/test_cli.py pyproject.toml
git commit -m "feat: add claude wrapper CLI and pyproject.toml"
```

---

## Chunk 3: React Frontend

### Task 10: React Project Setup

**Files:**
- Create: `web/` directory with Vite + React + TypeScript + Ant Design

- [ ] **Step 1: Initialize Vite project**

```bash
cd /Users/ying/Documents/MyAgent
npm create vite@latest web -- --template react-ts
cd web
npm install antd @ant-design/icons
npm install -D @types/node
```

- [ ] **Step 2: Configure Vite proxy**

Update `web/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8090',
      '/ws': {
        target: 'ws://localhost:8090',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
```

- [ ] **Step 3: Set up App structure with routing**

Create `web/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider, theme } from 'antd'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Sessions from './pages/Sessions'
import SessionDetail from './pages/SessionDetail'
import Tasks from './pages/Tasks'
import Memory from './pages/Memory'

const darkTheme = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#1677ff',
    borderRadius: 6,
  },
}

function App() {
  const token = localStorage.getItem('token')
  if (!token) {
    return (
      <ConfigProvider theme={darkTheme}>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="*" element={<Navigate to="/login" />} />
          </Routes>
        </BrowserRouter>
      </ConfigProvider>
    )
  }
  return (
    <ConfigProvider theme={darkTheme}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/sessions/:id" element={<SessionDetail />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/memory" element={<Memory />} />
          </Route>
          <Route path="/login" element={<Login />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  )
}

export default App
```

- [ ] **Step 4: Install react-router-dom**

```bash
cd web && npm install react-router-dom
```

- [ ] **Step 5: Verify dev server starts**

```bash
cd web && npm run dev
```

Open http://localhost:3000 - should see login page

- [ ] **Step 6: Commit**

```bash
git add web/
echo "node_modules" >> web/.gitignore
git commit -m "feat: initialize React frontend with Vite + Ant Design dark theme"
```

---

### Task 11: Login Page

**Files:**
- Create: `web/src/pages/Login.tsx`
- Create: `web/src/utils/api.ts`

- [ ] **Step 1: Create API utility**

Create `web/src/utils/api.ts`:

```typescript
const BASE_URL = ''

export function getToken(): string | null {
  return localStorage.getItem('token')
}

export function setToken(token: string): void {
  localStorage.setItem('token', token)
}

export function clearToken(): void {
  localStorage.removeItem('token')
}

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const resp = await fetch(`${BASE_URL}${path}`, { ...options, headers })
  if (resp.status === 401) {
    clearToken()
    window.location.href = '/login'
  }
  return resp
}
```

- [ ] **Step 2: Create Login page**

Create `web/src/pages/Login.tsx`:

```tsx
import { useState } from 'react'
import { Card, Input, Button, Typography, message } from 'antd'
import { LockOutlined } from '@ant-design/icons'

const { Title } = Typography

export default function Login() {
  const [secret, setSecret] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async () => {
    setLoading(true)
    try {
      const resp = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ secret }),
      })
      if (resp.ok) {
        const data = await resp.json()
        localStorage.setItem('token', data.token)
        window.location.href = '/'
      } else {
        message.error('Invalid token')
      }
    } catch {
      message.error('Connection failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#141414' }}>
      <Card style={{ width: 360 }}>
        <Title level={3} style={{ textAlign: 'center', marginBottom: 24 }}>MyAgent</Title>
        <Input.Password
          prefix={<LockOutlined />}
          placeholder="Enter secret"
          value={secret}
          onChange={e => setSecret(e.target.value)}
          onPressEnter={handleLogin}
          style={{ marginBottom: 16 }}
        />
        <Button type="primary" block loading={loading} onClick={handleLogin}>
          Login
        </Button>
      </Card>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/
git commit -m "feat: add login page and API utility"
```

---

### Task 12: Layout and Dashboard Page

**Files:**
- Create: `web/src/components/Layout.tsx`
- Create: `web/src/pages/Dashboard.tsx`

- [ ] **Step 1: Create Layout with navigation**

Create `web/src/components/Layout.tsx` with antd Layout, Sider with Menu. Menu items:
- Dashboard (DashboardOutlined)
- Sessions (DesktopOutlined)
- Tasks (UnorderedListOutlined)
- Memory (SearchOutlined)

Use `Outlet` from react-router-dom for content area. Responsive: Sider collapses on mobile.

- [ ] **Step 2: Create Dashboard page**

Create `web/src/pages/Dashboard.tsx` with:
- 4 stat cards: Active Sessions, Today's Remaining Quota, Total Tasks, Connections (Feishu/Relay)
- Recent sessions list (top 5)
- Quick task submit form

Use `apiFetch` to load data from `/api/sessions`, `/api/status`, `/api/tasks`.

- [ ] **Step 3: Verify in browser**

Start backend + frontend, login, check Dashboard renders.

- [ ] **Step 4: Commit**

```bash
git add web/src/
git commit -m "feat: add layout with navigation and dashboard page"
```

---

### Task 13: Sessions List Page

**Files:**
- Create: `web/src/pages/Sessions.tsx`
- Create: `web/src/components/SessionCard.tsx`
- Create: `web/src/hooks/useWebSocket.ts`

- [ ] **Step 1: Create useWebSocket hook**

Create `web/src/hooks/useWebSocket.ts`:

```typescript
import { useEffect, useRef, useCallback } from 'react'
import { getToken } from '../utils/api'

export function useWebSocket(
  path: string,
  onMessage: (data: any) => void,
  enabled: boolean = true,
) {
  const wsRef = useRef<WebSocket | null>(null)

  const connect = useCallback(() => {
    if (!enabled) return
    const token = getToken()
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}${path}?token=${token}`
    const ws = new WebSocket(url)
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage(data)
      } catch {}
    }
    ws.onclose = () => {
      setTimeout(connect, 3000)
    }
    wsRef.current = ws
  }, [path, onMessage, enabled])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [connect])

  return wsRef
}
```

- [ ] **Step 2: Create SessionCard component**

`web/src/components/SessionCard.tsx`:
- Show project name, cwd, status badge (green=active, gray=idle, default=finished), last active time, PID
- Use antd Card, Tag, Typography
- Click navigates to `/sessions/{id}`

- [ ] **Step 3: Create Sessions page**

`web/src/pages/Sessions.tsx`:
- Fetch sessions from `/api/sessions`
- Subscribe to `/ws/sessions` for real-time updates
- Filter tabs: All / Active / Idle / Finished
- Grid of SessionCard components (responsive: 1 col mobile, 2 col tablet, 3 col desktop)

- [ ] **Step 4: Verify in browser**

Check session list renders, WebSocket updates work.

- [ ] **Step 5: Commit**

```bash
git add web/src/
git commit -m "feat: add sessions list page with real-time WebSocket updates"
```

---

### Task 14: Session Detail Page (Chat Stream)

**Files:**
- Create: `web/src/pages/SessionDetail.tsx`
- Create: `web/src/components/MessageBubble.tsx`
- Create: `web/src/components/ToolCallBlock.tsx`
- Create: `web/src/components/CodeBlock.tsx`

- [ ] **Step 1: Create CodeBlock component**

`web/src/components/CodeBlock.tsx`:
- Syntax highlighted code block using Prism.js or highlight.js
- Copy button
- Language label

Install: `cd web && npm install prismjs @types/prismjs`

- [ ] **Step 2: Create ToolCallBlock component**

`web/src/components/ToolCallBlock.tsx`:
- Collapsible panel (antd Collapse)
- Shows tool name as header, params and result when expanded
- Icon per tool type (FileOutlined for Read/Write, CodeOutlined for Bash, SearchOutlined for Grep)

- [ ] **Step 3: Create MessageBubble component**

`web/src/components/MessageBubble.tsx`:
- User messages: right-aligned, blue background
- Assistant messages: left-aligned, dark background
- Parse assistant content: array of text blocks and tool_use blocks
- Text blocks rendered as markdown (install `react-markdown`)
- Tool use blocks rendered as ToolCallBlock
- Timestamp below each message

Install: `cd web && npm install react-markdown`

- [ ] **Step 4: Create SessionDetail page**

`web/src/pages/SessionDetail.tsx`:
- Header: project name, PID, status badge, start time, duration
- Message list: scrollable container, auto-scroll to bottom on new messages
- Subscribe to `/ws/sessions/{id}` for real-time message stream
- Load initial messages from `GET /api/sessions/{id}`
- Bottom: disabled input box with "Remote control coming in Phase 2" placeholder

- [ ] **Step 5: Test on mobile viewport**

Open Chrome DevTools, toggle device toolbar, verify chat layout works on 375px width.

- [ ] **Step 6: Commit**

```bash
git add web/src/
git commit -m "feat: add session detail page with chat stream and real-time updates"
```

---

### Task 15: Tasks and Memory Pages

**Files:**
- Create: `web/src/pages/Tasks.tsx`
- Create: `web/src/pages/Memory.tsx`

- [ ] **Step 1: Create Tasks page**

`web/src/pages/Tasks.tsx`:
- Fetch from `/api/tasks`
- antd Table with columns: Status (Tag), Prompt, Source, Created, Duration
- Filter by status (tabs)
- Click row to expand and show logs

- [ ] **Step 2: Create Memory page**

`web/src/pages/Memory.tsx`:
- Search input
- Fetch from `/api/memory/search?q=...`
- Display results as antd List items

- [ ] **Step 3: Commit**

```bash
git add web/src/
git commit -m "feat: add tasks and memory pages"
```

---

### Task 16: Build and Serve Static Files

**Files:**
- Modify: `myagent/server.py`

- [ ] **Step 1: Build React app**

```bash
cd web && npm run build
```

Verify `web/dist/` contains `index.html` and assets.

- [ ] **Step 2: Add static file serving to server.py**

In `create_app()`, after all API routes:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

web_dist = Path(__file__).parent.parent / "web" / "dist"
if web_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(web_dist / "assets")), name="static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve React SPA - all non-API routes return index.html."""
        file_path = web_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(web_dist / "index.html"))
```

- [ ] **Step 3: Remove old HTMX templates and web.py routes**

Delete:
- `myagent/templates/` directory
- `myagent/web.py`
- Remove `from myagent.web import router as web_router` and `app.include_router(web_router)` from server.py
- Remove `jinja2` from requirements.txt

- [ ] **Step 4: Run full test suite**

Run: `source .venv/bin/activate && python -m pytest tests/ -v`

Fix any broken tests (test_web.py tests need to be removed or rewritten for new API).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: serve React SPA, remove HTMX templates"
```

---

## Chunk 4: Integration and Polish

### Task 17: End-to-End Testing

- [ ] **Step 1: Start the server**

```bash
source .venv/bin/activate && python run.py
```

- [ ] **Step 2: Open Dashboard on desktop and mobile**

- Desktop: http://localhost:8090
- Mobile: http://<mac-ip>:8090

Verify:
- Login works
- Dashboard shows stats
- Sessions page shows running Claude sessions
- Clicking a session shows message history
- Real-time updates work (start a new claude session, verify it appears)
- Tasks page works
- Memory search works

- [ ] **Step 3: Test Feishu commands**

Send via Feishu:
- "我的会话" - should return active sessions
- "查看状态" - should include session count
- "你好" - should get Doubao chat reply

- [ ] **Step 4: Test myagent wrapper**

```bash
myagent wrap -- --dangerously-skip-permissions
```

Verify it appears as a wrapped session in Dashboard.

- [ ] **Step 5: Fix any issues found**

- [ ] **Step 6: Commit fixes**

```bash
git add -A
git commit -m "fix: end-to-end testing fixes"
```

---

### Task 18: Update Config and Documentation

- [ ] **Step 1: Update config.yaml with all new sections**

- [ ] **Step 2: Run full test suite one final time**

```bash
source .venv/bin/activate && python -m pytest tests/ -v
```

Expected: All PASS

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: session monitor complete - scanner, registry, React dashboard, wrapper CLI"
```
