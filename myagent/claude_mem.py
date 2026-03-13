"""Bridge to read claude-mem's SQLite database for cross-session memory."""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "~/.claude-mem/claude-mem.db"


class ClaudeMemBridge:
    """Read-only bridge to claude-mem's SQLite database.

    Provides search across observations, session summaries, and user prompts
    without modifying the database (claude-mem owns writes via its MCP server).
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self._db_path = str(Path(db_path).expanduser())
        self._available = Path(self._db_path).exists()

    @property
    def available(self) -> bool:
        return self._available

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        try:
            yield conn
        finally:
            conn.close()

    def search_observations(
        self,
        query: str,
        limit: int = 20,
        obs_type: str | None = None,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """Full-text search across observations."""
        if not self._available:
            return []
        try:
            safe_query = _escape_fts5(query)
            if not safe_query:
                return []

            with self._connect() as conn:
                sql = """
                    SELECT o.id, o.memory_session_id, o.project, o.type, o.title,
                           o.subtitle, o.narrative, o.text, o.facts, o.concepts,
                           o.files_read, o.files_modified, o.created_at, o.created_at_epoch
                    FROM observations_fts fts
                    JOIN observations o ON o.id = fts.rowid
                    WHERE observations_fts MATCH ?
                """
                params: list[Any] = [safe_query]
                if obs_type:
                    sql += " AND o.type = ?"
                    params.append(obs_type)
                if project:
                    sql += " AND o.project LIKE ?"
                    params.append(f"%{project}%")
                sql += " ORDER BY o.created_at_epoch DESC LIMIT ?"
                params.append(limit)

                rows = conn.execute(sql, params).fetchall()
                return [_obs_to_dict(r) for r in rows]
        except Exception:
            logger.exception("Failed to search claude-mem observations")
            return []

    def search_summaries(
        self,
        query: str,
        limit: int = 10,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """Full-text search across session summaries."""
        if not self._available:
            return []
        try:
            safe_query = _escape_fts5(query)
            if not safe_query:
                return []

            with self._connect() as conn:
                sql = """
                    SELECT s.id, s.memory_session_id, s.project, s.request,
                           s.investigated, s.learned, s.completed, s.next_steps,
                           s.files_read, s.files_edited, s.notes, s.created_at,
                           s.created_at_epoch
                    FROM session_summaries_fts fts
                    JOIN session_summaries s ON s.id = fts.rowid
                    WHERE session_summaries_fts MATCH ?
                """
                params: list[Any] = [safe_query]
                if project:
                    sql += " AND s.project LIKE ?"
                    params.append(f"%{project}%")
                sql += " ORDER BY s.created_at_epoch DESC LIMIT ?"
                params.append(limit)

                rows = conn.execute(sql, params).fetchall()
                return [_summary_to_dict(r) for r in rows]
        except Exception:
            logger.exception("Failed to search claude-mem summaries")
            return []

    def get_recent_observations(
        self,
        limit: int = 50,
        obs_type: str | None = None,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get most recent observations."""
        if not self._available:
            return []
        try:
            with self._connect() as conn:
                sql = "SELECT * FROM observations WHERE 1=1"
                params: list[Any] = []
                if obs_type:
                    sql += " AND type = ?"
                    params.append(obs_type)
                if project:
                    sql += " AND project LIKE ?"
                    params.append(f"%{project}%")
                sql += " ORDER BY created_at_epoch DESC LIMIT ?"
                params.append(limit)

                rows = conn.execute(sql, params).fetchall()
                return [_obs_to_dict(r) for r in rows]
        except Exception:
            logger.exception("Failed to get recent observations")
            return []

    def get_timeline(
        self,
        limit: int = 30,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get session summaries as a timeline."""
        if not self._available:
            return []
        try:
            with self._connect() as conn:
                sql = "SELECT * FROM session_summaries WHERE 1=1"
                params: list[Any] = []
                if project:
                    sql += " AND project LIKE ?"
                    params.append(f"%{project}%")
                sql += " ORDER BY created_at_epoch DESC LIMIT ?"
                params.append(limit)

                rows = conn.execute(sql, params).fetchall()
                return [_summary_to_dict(r) for r in rows]
        except Exception:
            logger.exception("Failed to get timeline")
            return []

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics from claude-mem."""
        if not self._available:
            return {"available": False}
        try:
            with self._connect() as conn:
                stats: dict[str, Any] = {"available": True}

                stats["total_observations"] = conn.execute(
                    "SELECT COUNT(*) FROM observations"
                ).fetchone()[0]
                stats["total_sessions"] = conn.execute(
                    "SELECT COUNT(*) FROM sdk_sessions"
                ).fetchone()[0]
                stats["total_summaries"] = conn.execute(
                    "SELECT COUNT(*) FROM session_summaries"
                ).fetchone()[0]
                stats["total_prompts"] = conn.execute(
                    "SELECT COUNT(*) FROM user_prompts"
                ).fetchone()[0]

                rows = conn.execute(
                    "SELECT type, COUNT(*) as cnt FROM observations GROUP BY type ORDER BY cnt DESC"
                ).fetchall()
                stats["observations_by_type"] = {r["type"]: r["cnt"] for r in rows}

                rows = conn.execute(
                    "SELECT project, COUNT(*) as cnt FROM observations GROUP BY project ORDER BY cnt DESC LIMIT 10"
                ).fetchall()
                stats["top_projects"] = {r["project"]: r["cnt"] for r in rows}

                return stats
        except Exception:
            logger.exception("Failed to get claude-mem stats")
            return {"available": False}

    def get_projects(self) -> list[str]:
        """Get distinct project names."""
        if not self._available:
            return []
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT DISTINCT project FROM observations ORDER BY project"
                ).fetchall()
                return [r["project"] for r in rows]
        except Exception:
            return []


def _escape_fts5(query: str) -> str:
    tokens = query.strip().split()
    if not tokens:
        return ""
    return " ".join(f'"{t}"' for t in tokens)


def _sanitize_str(v: Any) -> Any:
    """Remove control characters that break JSON serialization."""
    if isinstance(v, str):
        return v.replace("\x00", "").replace("\x1b", "")
    return v


def _obs_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = {k: _sanitize_str(v) for k, v in dict(row).items()}
    d["source"] = "claude-mem"
    d["kind"] = "observation"
    return d


def _summary_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = {k: _sanitize_str(v) for k, v in dict(row).items()}
    d["source"] = "claude-mem"
    d["kind"] = "summary"
    return d
