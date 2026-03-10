from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

import aiosqlite

from myagent.models import Task, TaskStatus, TaskSource, SessionInfo, SessionStatus

PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}


class Database:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    async def init(self) -> None:
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_SCHEMA)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # tasks
    # ------------------------------------------------------------------

    async def create_task(self, task: Task) -> None:
        await self._conn.execute(
            """INSERT INTO tasks
               (id, source, prompt, priority, status, cwd,
                created_at, started_at, finished_at,
                result_summary, raw_output, token_usage,
                session_id, complexity)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                task.id,
                task.source.value,
                task.prompt,
                task.priority,
                task.status.value,
                task.cwd,
                task.created_at.isoformat(),
                task.started_at.isoformat() if task.started_at else None,
                task.finished_at.isoformat() if task.finished_at else None,
                task.result_summary,
                task.raw_output,
                task.token_usage,
                task.session_id,
                task.complexity,
            ),
        )
        await self._conn.commit()

    async def get_task(self, task_id: str) -> Task | None:
        cursor = await self._conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_task(row)

    async def update_task(self, task_id: str, **fields) -> None:
        if not fields:
            return
        parts, values = [], []
        for key, val in fields.items():
            parts.append(f"{key} = ?")
            values.append(val.value if isinstance(val, Enum) else val)
        values.append(task_id)
        await self._conn.execute(
            f"UPDATE tasks SET {', '.join(parts)} WHERE id = ?", values
        )
        await self._conn.commit()

    async def list_tasks(self, limit: int = 50, status: TaskStatus | None = None) -> list[Task]:
        if status is not None:
            cursor = await self._conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status.value, limit),
            )
        else:
            cursor = await self._conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]

    async def count_tasks(self) -> int:
        cursor = await self._conn.execute("SELECT COUNT(*) FROM tasks")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_next_pending(self) -> Task | None:
        cursor = await self._conn.execute(
            """SELECT * FROM tasks
               WHERE status = ?
               ORDER BY
                 CASE priority
                   WHEN 'high' THEN 0
                   WHEN 'normal' THEN 1
                   WHEN 'low' THEN 2
                   ELSE 3
                 END,
                 created_at ASC
               LIMIT 1""",
            (TaskStatus.PENDING.value,),
        )
        row = await cursor.fetchone()
        return _row_to_task(row) if row else None

    # ------------------------------------------------------------------
    # task logs
    # ------------------------------------------------------------------

    async def log_event(
        self,
        task_id: str,
        event_type: str,
        tool_name: str | None = None,
        content: str | None = None,
    ) -> None:
        log_id = uuid4().hex[:12]
        await self._conn.execute(
            """INSERT INTO task_logs (id, task_id, timestamp, event_type, tool_name, content)
               VALUES (?,?,?,?,?,?)""",
            (
                log_id,
                task_id,
                datetime.now(timezone.utc).isoformat(),
                event_type,
                tool_name,
                content,
            ),
        )
        await self._conn.commit()

    async def get_task_logs(self, task_id: str) -> list[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM task_logs WHERE task_id = ? ORDER BY timestamp", (task_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # memories
    # ------------------------------------------------------------------

    async def create_memory(
        self,
        task_id: str,
        summary: str,
        key_decisions: str | None = None,
        files_changed: str | None = None,
        tags: str | None = None,
        project: str | None = None,
    ) -> int:
        cursor = await self._conn.execute(
            """INSERT INTO memories
               (task_id, created_at, summary, key_decisions, files_changed, tags, project)
               VALUES (?,?,?,?,?,?,?)""",
            (
                task_id,
                datetime.now(timezone.utc).isoformat(),
                summary,
                key_decisions,
                files_changed,
                tags,
                project,
            ),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def search_memories(self, query: str, limit: int = 10) -> list[dict]:
        safe_query = _escape_fts5(query)
        if not safe_query:
            return []
        cursor = await self._conn.execute(
            """SELECT m.*
               FROM memory_search ms
               JOIN memories m ON m.id = ms.rowid
               WHERE memory_search MATCH ?
               LIMIT ?""",
            (safe_query, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # sessions
    # ------------------------------------------------------------------

    async def upsert_session(self, session: SessionInfo) -> None:
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
        cursor = await self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_session(row)

    async def list_sessions(self, status: SessionStatus | None = None, limit: int = 50) -> list[SessionInfo]:
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

    # ------------------------------------------------------------------
    # entities
    # ------------------------------------------------------------------

    async def create_entity(
        self,
        name: str,
        entity_type: str | None = None,
        content: str | None = None,
        task_id: str | None = None,
    ) -> int:
        cursor = await self._conn.execute(
            """INSERT INTO entities (name, type, content, first_seen, last_updated, source_task_ids)
               VALUES (?, ?, ?, datetime('now'), datetime('now'), ?)""",
            (name, entity_type, content, f'["{task_id}"]' if task_id else "[]"),
        )
        await self._conn.commit()
        return cursor.lastrowid


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _escape_fts5(query: str) -> str:
    """Escape special FTS5 characters to prevent query syntax errors."""
    # Quote each token to avoid FTS5 syntax issues with special chars
    tokens = query.strip().split()
    if not tokens:
        return ""
    return " ".join(f'"{t}"' for t in tokens)


def _row_to_session(row: aiosqlite.Row) -> SessionInfo:
    d = dict(row)
    d["status"] = SessionStatus(d["status"])
    d["is_wrapped"] = bool(d["is_wrapped"])
    if d.get("started_at"):
        d["started_at"] = datetime.fromisoformat(d["started_at"])
    if d.get("last_active"):
        d["last_active"] = datetime.fromisoformat(d["last_active"])
    return SessionInfo(**d)


def _row_to_task(row: aiosqlite.Row) -> Task:
    d = dict(row)
    d["source"] = TaskSource(d["source"])
    d["status"] = TaskStatus(d["status"])
    if d.get("created_at"):
        d["created_at"] = datetime.fromisoformat(d["created_at"])
    if d.get("started_at"):
        d["started_at"] = datetime.fromisoformat(d["started_at"])
    if d.get("finished_at"):
        d["finished_at"] = datetime.fromisoformat(d["finished_at"])
    return Task(**d)


# ------------------------------------------------------------------
# schema
# ------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    prompt TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'pending',
    cwd TEXT NOT NULL DEFAULT '.',
    created_at TEXT NOT NULL,
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
    task_id TEXT NOT NULL REFERENCES tasks(id),
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    tool_name TEXT,
    content TEXT
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT REFERENCES tasks(id),
    created_at TEXT NOT NULL,
    summary TEXT,
    key_decisions TEXT,
    files_changed TEXT,
    commands_run TEXT,
    tags TEXT,
    project TEXT
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

CREATE VIRTUAL TABLE IF NOT EXISTS memory_search USING fts5(
    summary,
    key_decisions,
    tags,
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
