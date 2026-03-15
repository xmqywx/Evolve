from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import uuid4

import aiosqlite

from myagent.models import Task, TaskStatus, TaskSource, SessionInfo, SessionStatus

PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}


class Database:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    @property
    def _db(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._conn

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    async def init(self) -> None:
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_SCHEMA)
        # Migrations: add columns if missing
        for col, defn in [("alias", "TEXT"), ("color", "TEXT"), ("archived", "BOOLEAN NOT NULL DEFAULT 0")]:
            try:
                await self._conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} {defn}")
                await self._conn.commit()
            except Exception:
                pass  # column already exists
        # Workflow v2 migrations
        for col, defn in [
            ("category", "TEXT NOT NULL DEFAULT 'automation'"),
            ("description", "TEXT"),
            ("dependencies", "TEXT"),
            ("estimated_time", "INTEGER"),
            ("estimated_value", "TEXT"),
        ]:
            try:
                await self._conn.execute(f"ALTER TABLE agent_workflows ADD COLUMN {col} {defn}")
                await self._conn.commit()
            except Exception:
                pass

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # tasks
    # ------------------------------------------------------------------

    async def create_task(self, task: Task) -> None:
        await self._db.execute(
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
        await self._db.commit()

    async def get_task(self, task_id: str) -> Task | None:
        cursor = await self._db.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_task(row)

    _TASK_COLUMNS = {"status", "started_at", "finished_at", "result_summary", "raw_output", "token_usage", "session_id", "complexity", "priority"}

    async def update_task(self, task_id: str, **fields) -> None:
        fields = {k: v for k, v in fields.items() if k in self._TASK_COLUMNS}
        if not fields:
            return
        parts, values = [], []
        for key, val in fields.items():
            parts.append(f"{key} = ?")
            values.append(val.value if isinstance(val, Enum) else val)
        values.append(task_id)
        await self._db.execute(
            f"UPDATE tasks SET {', '.join(parts)} WHERE id = ?", values
        )
        await self._db.commit()

    async def list_tasks(self, limit: int = 50, status: TaskStatus | None = None) -> list[Task]:
        if status is not None:
            cursor = await self._db.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status.value, limit),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]

    async def count_tasks(self) -> int:
        cursor = await self._db.execute("SELECT COUNT(*) FROM tasks")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_next_pending(self) -> Task | None:
        cursor = await self._db.execute(
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
        await self._db.execute(
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
        await self._db.commit()

    async def get_task_logs(self, task_id: str) -> list[dict]:
        cursor = await self._db.execute(
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
        cursor = await self._db.execute(
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
        await self._db.commit()
        return cursor.lastrowid

    async def count_memories(self) -> int:
        cursor = await self._db.execute("SELECT COUNT(*) FROM memories")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def search_memories(self, query: str, limit: int = 10) -> list[dict]:
        safe_query = _escape_fts5(query)
        if not safe_query:
            return []
        cursor = await self._db.execute(
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
        await self._db.execute(
            """INSERT INTO sessions (id, pid, cwd, project, tty, started_at, last_active, status, is_wrapped, alias, color, archived)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 pid=excluded.pid, cwd=excluded.cwd, project=excluded.project,
                 tty=excluded.tty, last_active=excluded.last_active,
                 status=excluded.status, is_wrapped=excluded.is_wrapped""",
            (
                session.id, session.pid, session.cwd, session.project,
                session.tty, session.started_at.isoformat(),
                session.last_active.isoformat(), session.status.value,
                session.is_wrapped, session.alias, session.color, session.archived,
            ),
        )
        await self._db.commit()

    async def update_session_meta(self, session_id: str, **kwargs) -> bool:
        """Update alias, color, archived fields for a session."""
        allowed = {"alias", "color", "archived", "status"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [session_id]
        cursor = await self._db.execute(
            f"UPDATE sessions SET {sets} WHERE id = ?", vals,
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def get_session(self, session_id: str) -> SessionInfo | None:
        cursor = await self._db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_session(row)

    async def list_sessions(self, status: SessionStatus | None = None, limit: int = 50) -> list[SessionInfo]:
        if status is not None:
            cursor = await self._db.execute(
                "SELECT * FROM sessions WHERE status = ? ORDER BY last_active DESC LIMIT ?",
                (status.value, limit),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM sessions ORDER BY last_active DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [_row_to_session(r) for r in rows]

    # ------------------------------------------------------------------
    # entities
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # chat sessions & messages
    # ------------------------------------------------------------------

    async def create_chat_session(self, claude_session_id: str) -> int:
        cursor = await self._db.execute(
            """INSERT INTO chat_sessions (claude_session_id, status, started_at)
               VALUES (?, 'active', datetime('now'))""",
            (claude_session_id,),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_active_chat_session(self) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM chat_sessions WHERE status = 'active' ORDER BY id DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def rotate_chat_session(self, session_id: int, summary: str) -> None:
        await self._db.execute(
            "UPDATE chat_sessions SET status = 'rotated', summary = ?, ended_at = datetime('now') WHERE id = ?",
            (summary, session_id),
        )
        await self._db.commit()

    async def update_chat_session_claude_id(self, session_id: int, claude_session_id: str) -> None:
        await self._db.execute(
            "UPDATE chat_sessions SET claude_session_id = ? WHERE id = ?",
            (claude_session_id, session_id),
        )
        await self._db.commit()

    async def increment_chat_message_count(self, session_id: int) -> None:
        await self._db.execute(
            "UPDATE chat_sessions SET message_count = message_count + 1 WHERE id = ?",
            (session_id,),
        )
        await self._db.commit()

    async def add_chat_message(
        self, chat_session_id: str, role: str, content: str, context_snapshot: str | None = None,
    ) -> int:
        cursor = await self._db.execute(
            """INSERT INTO chat_messages (chat_session_id, role, content, context_snapshot, created_at)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (chat_session_id, role, content, context_snapshot),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_chat_messages(self, chat_session_id: str, limit: int = 50) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM chat_messages WHERE chat_session_id = ? ORDER BY id DESC LIMIT ?",
            (chat_session_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in reversed(rows)]

    async def get_recent_chat_messages(self, limit: int = 20) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM chat_messages ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in reversed(rows)]

    async def list_chat_sessions(self, limit: int = 20) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM chat_sessions ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # survival projects
    # ------------------------------------------------------------------

    async def create_survival_project(
        self, name: str, description: str | None = None, directory: str | None = None, priority: int = 5,
    ) -> int:
        cursor = await self._db.execute(
            """INSERT INTO survival_projects (name, description, directory, priority, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'idea', datetime('now'), datetime('now'))""",
            (name, description, directory, priority),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_survival_project(self, project_id: int) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM survival_projects WHERE id = ?", (project_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_survival_projects(self, status: str | None = None) -> list[dict]:
        if status:
            cursor = await self._db.execute(
                "SELECT * FROM survival_projects WHERE status = ? ORDER BY priority DESC, updated_at DESC",
                (status,),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM survival_projects ORDER BY priority DESC, updated_at DESC"
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_active_survival_projects(self) -> list[dict]:
        cursor = await self._db.execute(
            """SELECT * FROM survival_projects
               WHERE status NOT IN ('abandoned', 'idea')
               ORDER BY priority DESC, updated_at DESC"""
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    _SURVIVAL_COLUMNS = {"name", "description", "status", "directory", "estimated_revenue", "actual_revenue", "priority", "notes"}

    async def update_survival_project(self, project_id: int, **fields) -> None:
        fields = {k: v for k, v in fields.items() if k in self._SURVIVAL_COLUMNS}
        if not fields:
            return
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        parts, values = [], []
        for key, val in fields.items():
            parts.append(f"{key} = ?")
            values.append(val)
        values.append(project_id)
        await self._db.execute(
            f"UPDATE survival_projects SET {', '.join(parts)} WHERE id = ?", values
        )
        await self._db.commit()

    # ------------------------------------------------------------------
    # profile data
    # ------------------------------------------------------------------

    async def add_profile_data(
        self, source: str, content: str, category: str | None = None,
        raw_reference: str | None = None, related_project: str | None = None,
    ) -> int:
        cursor = await self._db.execute(
            """INSERT INTO profile_data (source, category, content, raw_reference, related_project, created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (source, category, content, raw_reference, related_project),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_recent_profile_data(self, source: str | None = None, limit: int = 20) -> list[dict]:
        if source:
            cursor = await self._db.execute(
                "SELECT * FROM profile_data WHERE source = ? ORDER BY id DESC LIMIT ?",
                (source, limit),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM profile_data ORDER BY id DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # survival_logs
    # ------------------------------------------------------------------

    async def add_survival_log(self, cycle_id: str, step: str, content: str) -> int:
        cursor = await self._db.execute(
            "INSERT INTO survival_logs (cycle_id, step, content, created_at) VALUES (?,?,?,?)",
            (cycle_id, step, content, datetime.now(timezone.utc).isoformat()),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_survival_logs(self, cycle_id: str | None = None, limit: int = 100) -> list[dict]:
        if cycle_id:
            cursor = await self._db.execute(
                "SELECT * FROM survival_logs WHERE cycle_id = ? ORDER BY id", (cycle_id,)
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM survival_logs ORDER BY id DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def list_survival_cycles(self, limit: int = 20) -> list[dict]:
        cursor = await self._db.execute(
            """SELECT cycle_id, MIN(created_at) as started_at, MAX(created_at) as ended_at,
                      COUNT(*) as step_count, GROUP_CONCAT(DISTINCT step) as steps
               FROM survival_logs GROUP BY cycle_id ORDER BY MAX(id) DESC LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # entities
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # agent self-report: heartbeats
    # ------------------------------------------------------------------

    async def add_heartbeat(
        self, activity: str, description: str | None = None,
        task_ref: str | None = None, progress_pct: int | None = None,
        eta_minutes: int | None = None,
    ) -> int:
        cursor = await self._db.execute(
            """INSERT INTO agent_heartbeats (activity, description, task_ref, progress_pct, eta_minutes, created_at)
               VALUES (?,?,?,?,?,?)""",
            (activity, description, task_ref, progress_pct, eta_minutes,
             datetime.now(timezone.utc).isoformat()),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_latest_heartbeat(self) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM agent_heartbeats ORDER BY id DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_heartbeats(self, limit: int = 50) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM agent_heartbeats ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in await cursor.fetchall()]

    # ------------------------------------------------------------------
    # agent self-report: deliverables
    # ------------------------------------------------------------------

    async def add_deliverable(
        self, title: str, type: str = "code", status: str = "draft",
        path: str | None = None, summary: str | None = None,
        repo: str | None = None, value_estimate: str | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            """INSERT INTO agent_deliverables (title, type, status, path, summary, repo, value_estimate, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (title, type, status, path, summary, repo, value_estimate, now, now),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def list_deliverables(self, type: str | None = None, status: str | None = None, limit: int = 50) -> list[dict]:
        conditions, params = [], []
        if type:
            conditions.append("type = ?")
            params.append(type)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)
        cursor = await self._db.execute(
            f"SELECT * FROM agent_deliverables{where} ORDER BY id DESC LIMIT ?", params,
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def update_deliverable(self, deliverable_id: int, **fields) -> bool:
        allowed = {"title", "type", "status", "path", "summary", "repo", "value_estimate"}
        fields = {k: v for k, v in fields.items() if k in allowed}
        if not fields:
            return False
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [deliverable_id]
        cursor = await self._db.execute(
            f"UPDATE agent_deliverables SET {sets} WHERE id = ?", vals,
        )
        await self._db.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # agent self-report: discoveries
    # ------------------------------------------------------------------

    async def add_discovery(
        self, title: str, category: str = "insight",
        content: str | None = None, actionable: bool = False,
        priority: str = "medium",
    ) -> int:
        cursor = await self._db.execute(
            """INSERT INTO agent_discoveries (title, category, content, actionable, priority, created_at)
               VALUES (?,?,?,?,?,?)""",
            (title, category, content, actionable, priority,
             datetime.now(timezone.utc).isoformat()),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def list_discoveries(self, category: str | None = None, priority: str | None = None, limit: int = 50) -> list[dict]:
        conditions, params = [], []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if priority:
            conditions.append("priority = ?")
            params.append(priority)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)
        cursor = await self._db.execute(
            f"SELECT * FROM agent_discoveries{where} ORDER BY id DESC LIMIT ?", params,
        )
        return [dict(r) for r in await cursor.fetchall()]

    # ------------------------------------------------------------------
    # agent self-report: workflows
    # ------------------------------------------------------------------

    async def add_workflow(
        self, name: str, trigger: str = "manual",
        category: str = "automation", description: str | None = None,
        steps: str | None = None, dependencies: str | None = None,
        estimated_time: int | None = None, estimated_value: str | None = None,
        enabled: bool = False,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            """INSERT INTO agent_workflows
               (name, trigger, category, description, steps, dependencies,
                estimated_time, estimated_value, enabled, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (name, trigger, category, description, steps, dependencies,
             estimated_time, estimated_value, enabled, now, now),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def list_workflows(self, limit: int = 50) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM agent_workflows ORDER BY id DESC LIMIT ?", (limit,)
        )
        workflows = [dict(r) for r in await cursor.fetchall()]
        # Attach run stats for each workflow
        for w in workflows:
            stats = await self._get_workflow_run_stats(w["id"])
            w.update(stats)
        return workflows

    async def get_workflow(self, workflow_id: int) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM agent_workflows WHERE id = ?", (workflow_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        w = dict(row)
        w.update(await self._get_workflow_run_stats(workflow_id))
        return w

    async def _get_workflow_run_stats(self, workflow_id: int) -> dict:
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM agent_workflow_runs WHERE workflow_id = ?",
            (workflow_id,),
        )
        run_count = (await cursor.fetchone())[0]
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM agent_workflow_runs WHERE workflow_id = ? AND status = 'success'",
            (workflow_id,),
        )
        success_count = (await cursor.fetchone())[0]
        cursor = await self._db.execute(
            "SELECT revenue FROM agent_workflow_runs WHERE workflow_id = ? AND revenue IS NOT NULL",
            (workflow_id,),
        )
        revenues = [r[0] for r in await cursor.fetchall()]
        cursor = await self._db.execute(
            "SELECT started_at FROM agent_workflow_runs WHERE workflow_id = ? ORDER BY id DESC LIMIT 1",
            (workflow_id,),
        )
        last_row = await cursor.fetchone()
        return {
            "run_count": run_count,
            "success_count": success_count,
            "success_rate": round(success_count / run_count * 100) if run_count > 0 else 0,
            "total_revenue": ", ".join(revenues) if revenues else None,
            "last_run_at": last_row[0] if last_row else None,
        }

    async def update_workflow(self, workflow_id: int, **fields) -> bool:
        allowed = {"name", "trigger", "category", "description", "steps",
                   "dependencies", "estimated_time", "estimated_value", "enabled"}
        fields = {k: v for k, v in fields.items() if k in allowed}
        if not fields:
            return False
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [workflow_id]
        cursor = await self._db.execute(
            f"UPDATE agent_workflows SET {sets} WHERE id = ?", vals,
        )
        await self._db.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # agent workflow runs
    # ------------------------------------------------------------------

    async def add_workflow_run(
        self, workflow_id: int, status: str = "running",
        steps_completed: int = 0, total_steps: int = 0,
        result_summary: str | None = None, revenue: str | None = None,
        error_log: str | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        finished = now if status in ("success", "partial", "failed") else None
        cursor = await self._db.execute(
            """INSERT INTO agent_workflow_runs
               (workflow_id, status, steps_completed, total_steps,
                result_summary, revenue, error_log, started_at, finished_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (workflow_id, status, steps_completed, total_steps,
             result_summary, revenue, error_log, now, finished),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def list_workflow_runs(self, workflow_id: int, limit: int = 20) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM agent_workflow_runs WHERE workflow_id = ? ORDER BY id DESC LIMIT ?",
            (workflow_id, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]

    # ------------------------------------------------------------------
    # agent self-report: upgrades
    # ------------------------------------------------------------------

    async def add_upgrade(
        self, proposal: str, reason: str | None = None,
        risk: str = "low", impact: str | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            """INSERT INTO agent_upgrades (proposal, reason, risk, impact, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (proposal, reason, risk, impact, "pending", now, now),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def list_upgrades(self, status: str | None = None, limit: int = 50) -> list[dict]:
        if status:
            cursor = await self._db.execute(
                "SELECT * FROM agent_upgrades WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status, limit),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM agent_upgrades ORDER BY id DESC LIMIT ?", (limit,)
            )
        return [dict(r) for r in await cursor.fetchall()]

    async def update_upgrade(self, upgrade_id: int, status: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            "UPDATE agent_upgrades SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, upgrade_id),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # agent self-report: reviews
    # ------------------------------------------------------------------

    async def add_review(
        self, period: str, accomplished: str | None = None,
        failed: str | None = None, learned: str | None = None,
        next_priorities: str | None = None, tokens_used: int | None = None,
        cost_estimate: str | None = None,
    ) -> int:
        cursor = await self._db.execute(
            """INSERT INTO agent_reviews (period, accomplished, failed, learned, next_priorities, tokens_used, cost_estimate, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (period, accomplished, failed, learned, next_priorities,
             tokens_used, cost_estimate, datetime.now(timezone.utc).isoformat()),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def list_reviews(self, limit: int = 20) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM agent_reviews ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_latest_review(self) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM agent_reviews ORDER BY id DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # agent self-report: aggregated stats
    # ------------------------------------------------------------------

    async def get_agent_stats(self) -> dict:
        stats = {}
        for table, key in [
            ("agent_heartbeats", "heartbeats"),
            ("agent_deliverables", "deliverables"),
            ("agent_discoveries", "discoveries"),
            ("agent_workflows", "workflows"),
            ("agent_upgrades", "upgrades"),
            ("agent_reviews", "reviews"),
        ]:
            cursor = await self._db.execute(f"SELECT COUNT(*) FROM {table}")
            row = await cursor.fetchone()
            stats[key] = row[0] if row else 0
        # Pending upgrades count
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM agent_upgrades WHERE status = 'pending'"
        )
        row = await cursor.fetchone()
        stats["pending_upgrades"] = row[0] if row else 0
        # Today's deliverables
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM agent_deliverables WHERE date(created_at) = date('now')"
        )
        row = await cursor.fetchone()
        stats["deliverables_today"] = row[0] if row else 0
        return stats

    # ------------------------------------------------------------------
    # agent_config
    # ------------------------------------------------------------------

    async def get_agent_config(self) -> dict:
        """Get all agent config key-value pairs."""
        cursor = await self._db.execute("SELECT key, value FROM agent_config")
        rows = await cursor.fetchall()
        return {r[0]: r[1] for r in rows}

    async def set_agent_config(self, key: str, value: str) -> None:
        """Upsert a single agent config key."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT INTO agent_config (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, value, now),
        )
        await self._db.commit()

    async def set_agent_config_bulk(self, items: dict[str, str]) -> None:
        """Upsert multiple agent config keys."""
        now = datetime.now(timezone.utc).isoformat()
        for key, value in items.items():
            await self._db.execute(
                "INSERT INTO agent_config (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, value, now),
            )
        await self._db.commit()

    # ------------------------------------------------------------------
    # supervisor reports
    # ------------------------------------------------------------------

    async def add_supervisor_report(self, period: str, summary: str, details: str | None = None, stats: str | None = None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            "INSERT INTO supervisor_reports (period, summary, details, stats, created_at) VALUES (?,?,?,?,?)",
            (period, summary, details, stats, now),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def list_supervisor_reports(self, limit: int = 30) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM supervisor_reports ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_supervisor_report(self, report_id: int) -> dict | None:
        cursor = await self._db.execute("SELECT * FROM supervisor_reports WHERE id = ?", (report_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_today_activity(self) -> dict:
        """Collect today's agent activity for supervisor analysis."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Heartbeats today
        cursor = await self._db.execute(
            "SELECT * FROM agent_heartbeats WHERE date(created_at) = ? ORDER BY id DESC",
            (today,),
        )
        heartbeats = [dict(r) for r in await cursor.fetchall()]

        # Deliverables today
        cursor = await self._db.execute(
            "SELECT * FROM agent_deliverables WHERE date(created_at) = ? ORDER BY id DESC",
            (today,),
        )
        deliverables = [dict(r) for r in await cursor.fetchall()]

        # Discoveries today
        cursor = await self._db.execute(
            "SELECT * FROM agent_discoveries WHERE date(created_at) = ? ORDER BY id DESC",
            (today,),
        )
        discoveries = [dict(r) for r in await cursor.fetchall()]

        # Workflow runs today
        cursor = await self._db.execute(
            "SELECT * FROM agent_workflow_runs WHERE date(started_at) = ? ORDER BY id DESC",
            (today,),
        )
        workflow_runs = [dict(r) for r in await cursor.fetchall()]

        # Scheduled task runs today
        cursor = await self._db.execute(
            "SELECT * FROM scheduled_task_runs WHERE date(started_at) = ? ORDER BY id DESC",
            (today,),
        )
        task_runs = [dict(r) for r in await cursor.fetchall()]

        # Reviews today
        cursor = await self._db.execute(
            "SELECT * FROM agent_reviews WHERE date(created_at) = ? ORDER BY id DESC",
            (today,),
        )
        reviews = [dict(r) for r in await cursor.fetchall()]

        return {
            "date": today,
            "heartbeats": heartbeats,
            "deliverables": deliverables,
            "discoveries": discoveries,
            "workflow_runs": workflow_runs,
            "task_runs": task_runs,
            "reviews": reviews,
        }

    # ------------------------------------------------------------------
    # scheduled tasks
    # ------------------------------------------------------------------

    async def create_scheduled_task(
        self, name: str, cron_expr: str,
        description: str | None = None,
        command: str | None = None, workflow_id: int | None = None,
        enabled: bool = True, next_run_at: str | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            """INSERT INTO scheduled_tasks
               (name, cron_expr, description, command, workflow_id, enabled, next_run_at, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (name, cron_expr, description, command, workflow_id, enabled, next_run_at, now, now),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def list_scheduled_tasks(self) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM scheduled_tasks ORDER BY id DESC"
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_scheduled_task(self, task_id: int) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_scheduled_task(self, task_id: int, **fields) -> bool:
        if not fields:
            return False
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [task_id]
        cursor = await self._db.execute(
            f"UPDATE scheduled_tasks SET {sets} WHERE id = ?", vals,
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def delete_scheduled_task(self, task_id: int) -> bool:
        await self._db.execute(
            "DELETE FROM scheduled_task_runs WHERE task_id = ?", (task_id,)
        )
        cursor = await self._db.execute(
            "DELETE FROM scheduled_tasks WHERE id = ?", (task_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def add_scheduled_task_run(
        self, task_id: int, status: str = "running",
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            """INSERT INTO scheduled_task_runs (task_id, status, started_at)
               VALUES (?,?,?)""",
            (task_id, status, now),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def finish_scheduled_task_run(
        self, run_id: int, status: str, output: str | None = None, error: str | None = None,
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            "UPDATE scheduled_task_runs SET status = ?, output = ?, error = ?, finished_at = ? WHERE id = ?",
            (status, output, error, now, run_id),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def list_scheduled_task_runs(self, task_id: int, limit: int = 20) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM scheduled_task_runs WHERE task_id = ? ORDER BY id DESC LIMIT ?",
            (task_id, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_enabled_scheduled_tasks(self) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM scheduled_tasks WHERE enabled = 1"
        )
        return [dict(r) for r in await cursor.fetchall()]

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
        cursor = await self._db.execute(
            """INSERT INTO entities (name, type, content, first_seen, last_updated, source_task_ids)
               VALUES (?, ?, ?, datetime('now'), datetime('now'), ?)""",
            (name, entity_type, content, f'["{task_id}"]' if task_id else "[]"),
        )
        await self._db.commit()
        return cursor.lastrowid

    # ------------------------------------------------------------------
    # knowledge_base
    # ------------------------------------------------------------------

    async def add_knowledge(self, content, category, source, source_id=None,
                            layer="recent", tags=None, score=5.0, expires_at=None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            """INSERT INTO knowledge_base
               (content, category, source, source_id, layer, tags, score, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (content, category, source, source_id, layer, tags, score, now, expires_at),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_knowledge(self, layer=None, category=None, days=None, limit=20) -> list[dict]:
        sql = "SELECT * FROM knowledge_base WHERE retired = 0"
        params: list = []
        if layer:
            sql += " AND layer = ?"
            params.append(layer)
        if category:
            sql += " AND category = ?"
            params.append(category)
        if days:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            sql += " AND created_at >= ?"
            params.append(cutoff)
        sql += " ORDER BY score DESC, created_at DESC LIMIT ?"
        params.append(limit)
        cursor = await self._db.execute(sql, params)
        return [dict(r) for r in await cursor.fetchall()]

    async def search_knowledge_by_tags(self, tags: list[str], limit=10) -> list[dict]:
        if not tags:
            return []
        conditions = " OR ".join(["tags LIKE ?" for _ in tags])
        params = [f"%{t}%" for t in tags]
        params.append(limit)
        cursor = await self._db.execute(
            f"SELECT * FROM knowledge_base WHERE retired = 0 AND ({conditions}) "
            f"ORDER BY score DESC LIMIT ?",
            params,
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def update_knowledge(self, kid, **fields):
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values())
        vals.append(kid)
        await self._db.execute(
            f"UPDATE knowledge_base SET {sets} WHERE id = ?", vals,
        )
        await self._db.commit()

    async def retire_expired_knowledge(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            "UPDATE knowledge_base SET retired = 1 WHERE retired = 0 AND expires_at IS NOT NULL AND expires_at < ?",
            (now,),
        )
        await self._db.commit()
        return cursor.rowcount

    async def promote_knowledge(self, kid):
        await self._db.execute(
            "UPDATE knowledge_base SET layer = 'permanent', expires_at = NULL WHERE id = ?",
            (kid,),
        )
        await self._db.commit()

    async def increment_use_count(self, kid):
        await self._db.execute(
            "UPDATE knowledge_base SET use_count = use_count + 1 WHERE id = ?",
            (kid,),
        )
        await self._db.commit()

    async def list_knowledge(self, limit=50, layer=None, category=None, include_retired=False) -> list[dict]:
        sql = "SELECT * FROM knowledge_base WHERE 1=1"
        params: list = []
        if not include_retired:
            sql += " AND retired = 0"
        if layer:
            sql += " AND layer = ?"
            params.append(layer)
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor = await self._db.execute(sql, params)
        return [dict(r) for r in await cursor.fetchall()]

    async def delete_knowledge(self, kid):
        await self._db.execute("DELETE FROM knowledge_base WHERE id = ?", (kid,))
        await self._db.commit()

    async def get_knowledge_stats(self) -> dict:
        stats = {"total": 0, "by_layer": {}, "by_category": {}}
        cursor = await self._db.execute(
            "SELECT layer, COUNT(*) as cnt FROM knowledge_base WHERE retired = 0 GROUP BY layer"
        )
        for r in await cursor.fetchall():
            d = dict(r)
            stats["by_layer"][d["layer"]] = d["cnt"]
            stats["total"] += d["cnt"]
        cursor = await self._db.execute(
            "SELECT category, COUNT(*) as cnt FROM knowledge_base WHERE retired = 0 GROUP BY category"
        )
        for r in await cursor.fetchall():
            d = dict(r)
            stats["by_category"][d["category"]] = d["cnt"]
        return stats


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
    d["archived"] = bool(d.get("archived", 0))
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
    is_wrapped BOOLEAN NOT NULL DEFAULT 0,
    alias TEXT,
    color TEXT,
    archived BOOLEAN NOT NULL DEFAULT 0
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

CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claude_session_id TEXT NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    summary TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    context_snapshot TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS survival_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'idea',
    directory TEXT,
    estimated_revenue TEXT,
    actual_revenue TEXT,
    priority INTEGER NOT NULL DEFAULT 5,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    category TEXT,
    content TEXT NOT NULL,
    raw_reference TEXT,
    related_project TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS survival_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id TEXT NOT NULL,
    step TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Agent Self-Report tables (Phase 3)

CREATE TABLE IF NOT EXISTS agent_heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity TEXT NOT NULL,
    description TEXT,
    task_ref TEXT,
    progress_pct INTEGER,
    eta_minutes INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_deliverables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'code',
    status TEXT NOT NULL DEFAULT 'draft',
    path TEXT,
    summary TEXT,
    repo TEXT,
    value_estimate TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_discoveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'insight',
    content TEXT,
    actionable BOOLEAN NOT NULL DEFAULT 0,
    priority TEXT NOT NULL DEFAULT 'medium',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_workflows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    trigger TEXT NOT NULL DEFAULT 'manual',
    category TEXT NOT NULL DEFAULT 'automation',
    description TEXT,
    steps TEXT,
    dependencies TEXT,
    estimated_time INTEGER,
    estimated_value TEXT,
    enabled BOOLEAN NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_workflow_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    steps_completed INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 0,
    result_summary TEXT,
    revenue TEXT,
    error_log TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY (workflow_id) REFERENCES agent_workflows(id)
);

CREATE TABLE IF NOT EXISTS agent_upgrades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal TEXT NOT NULL,
    reason TEXT,
    risk TEXT NOT NULL DEFAULT 'low',
    impact TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL,
    accomplished TEXT,
    failed TEXT,
    learned TEXT,
    next_priorities TEXT,
    tokens_used INTEGER,
    cost_estimate TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cron_expr TEXT NOT NULL,
    description TEXT,
    command TEXT,
    workflow_id INTEGER,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    last_run_at TEXT,
    next_run_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES agent_workflows(id)
);

CREATE TABLE IF NOT EXISTS supervisor_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL,
    summary TEXT NOT NULL,
    details TEXT,
    stats TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scheduled_task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    output TEXT,
    error TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY (task_id) REFERENCES scheduled_tasks(id)
);

CREATE TABLE IF NOT EXISTS knowledge_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    category TEXT NOT NULL,
    source TEXT NOT NULL,
    source_id TEXT,
    layer TEXT NOT NULL DEFAULT 'recent',
    tags TEXT,
    score REAL DEFAULT 5.0,
    use_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    retired INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_kb_layer ON knowledge_base(layer, retired);
CREATE INDEX IF NOT EXISTS idx_kb_created ON knowledge_base(created_at);
"""
