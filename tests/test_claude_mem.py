"""Tests for claude_mem bridge."""
import sqlite3
import tempfile
from pathlib import Path

import pytest

from myagent.claude_mem import ClaudeMemBridge, _escape_fts5


@pytest.fixture
def mock_db(tmp_path):
    """Create a temporary SQLite database mimicking claude-mem schema."""
    db_path = tmp_path / "claude-mem.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE sdk_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_session_id TEXT UNIQUE NOT NULL,
            memory_session_id TEXT UNIQUE,
            project TEXT NOT NULL,
            user_prompt TEXT,
            started_at TEXT NOT NULL,
            started_at_epoch INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        );

        CREATE TABLE observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_session_id TEXT NOT NULL,
            project TEXT NOT NULL,
            text TEXT,
            type TEXT NOT NULL,
            title TEXT,
            subtitle TEXT,
            facts TEXT,
            narrative TEXT,
            concepts TEXT,
            files_read TEXT,
            files_modified TEXT,
            prompt_number INTEGER,
            created_at TEXT NOT NULL,
            created_at_epoch INTEGER NOT NULL
        );

        CREATE VIRTUAL TABLE observations_fts USING fts5(
            title, subtitle, narrative, text, facts, concepts,
            content='observations', content_rowid='id'
        );

        CREATE TRIGGER observations_ai AFTER INSERT ON observations BEGIN
            INSERT INTO observations_fts(rowid, title, subtitle, narrative, text, facts, concepts)
            VALUES (new.id, new.title, new.subtitle, new.narrative, new.text, new.facts, new.concepts);
        END;

        CREATE TABLE session_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_session_id TEXT NOT NULL,
            project TEXT NOT NULL,
            request TEXT,
            investigated TEXT,
            learned TEXT,
            completed TEXT,
            next_steps TEXT,
            files_read TEXT,
            files_edited TEXT,
            notes TEXT,
            prompt_number INTEGER,
            created_at TEXT NOT NULL,
            created_at_epoch INTEGER NOT NULL
        );

        CREATE VIRTUAL TABLE session_summaries_fts USING fts5(
            request, investigated, learned, completed, next_steps, notes,
            content='session_summaries', content_rowid='id'
        );

        CREATE TRIGGER session_summaries_ai AFTER INSERT ON session_summaries BEGIN
            INSERT INTO session_summaries_fts(rowid, request, investigated, learned, completed, next_steps, notes)
            VALUES (new.id, new.request, new.investigated, new.learned, new.completed, new.next_steps, new.notes);
        END;

        CREATE TABLE user_prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_session_id TEXT NOT NULL,
            prompt_number INTEGER NOT NULL,
            prompt_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_at_epoch INTEGER NOT NULL
        );
    """)

    # Insert test data
    conn.execute("""
        INSERT INTO sdk_sessions (content_session_id, memory_session_id, project, started_at, started_at_epoch, status)
        VALUES ('sess-1', 'mem-1', 'TestProject', '2026-03-10T10:00:00Z', 1741600000, 'completed')
    """)
    conn.execute("""
        INSERT INTO observations (memory_session_id, project, type, title, subtitle, narrative, text, facts, concepts, created_at, created_at_epoch)
        VALUES ('mem-1', 'TestProject', 'feature', 'Added user authentication', 'JWT token flow', 'Implemented JWT-based auth with login endpoint', 'auth implementation', 'JWT tokens expire after 7 days', 'authentication, security', '2026-03-10T10:00:00Z', 1741600000)
    """)
    conn.execute("""
        INSERT INTO observations (memory_session_id, project, type, title, subtitle, narrative, text, facts, concepts, created_at, created_at_epoch)
        VALUES ('mem-1', 'TestProject', 'bugfix', 'Fixed database connection leak', 'Connection pool exhaustion', 'Fixed by using context managers for all DB connections', 'db fix', 'Always use context managers', 'database, reliability', '2026-03-10T11:00:00Z', 1741603600)
    """)
    conn.execute("""
        INSERT INTO observations (memory_session_id, project, type, title, subtitle, narrative, text, facts, concepts, created_at, created_at_epoch)
        VALUES ('mem-1', 'OtherProject', 'discovery', 'Explored new API patterns', '', 'REST vs GraphQL comparison', 'api patterns', '', 'API, design', '2026-03-10T12:00:00Z', 1741607200)
    """)
    conn.execute("""
        INSERT INTO session_summaries (memory_session_id, project, request, investigated, learned, completed, next_steps, created_at, created_at_epoch)
        VALUES ('mem-1', 'TestProject', 'Implement authentication system', 'JWT libraries, session management', 'JWT is simpler than session cookies for API auth', 'JWT login and token verification', 'Add refresh tokens', '2026-03-10T12:00:00Z', 1741607200)
    """)
    conn.execute("""
        INSERT INTO user_prompts (content_session_id, prompt_number, prompt_text, created_at, created_at_epoch)
        VALUES ('sess-1', 1, 'Add JWT authentication', '2026-03-10T10:00:00Z', 1741600000)
    """)
    conn.commit()
    conn.close()
    return str(db_path)


@pytest.fixture
def bridge(mock_db):
    return ClaudeMemBridge(db_path=mock_db)


class TestClaudeMemBridge:
    def test_available(self, bridge):
        assert bridge.available is True

    def test_unavailable(self, tmp_path):
        bridge = ClaudeMemBridge(db_path=str(tmp_path / "nonexistent.db"))
        assert bridge.available is False

    def test_unavailable_returns_empty(self, tmp_path):
        bridge = ClaudeMemBridge(db_path=str(tmp_path / "nonexistent.db"))
        assert bridge.search_observations("test") == []
        assert bridge.search_summaries("test") == []
        assert bridge.get_recent_observations() == []
        assert bridge.get_timeline() == []
        assert bridge.get_projects() == []
        assert bridge.get_stats() == {"available": False}

    def test_search_observations(self, bridge):
        results = bridge.search_observations("authentication")
        assert len(results) >= 1
        assert results[0]["kind"] == "observation"
        assert results[0]["source"] == "claude-mem"
        assert "authentication" in results[0]["title"].lower() or "auth" in results[0].get("text", "").lower()

    def test_search_observations_by_type(self, bridge):
        results = bridge.search_observations("database connection", obs_type="bugfix")
        assert len(results) >= 1
        assert all(r["type"] == "bugfix" for r in results)

    def test_search_observations_by_project(self, bridge):
        results = bridge.search_observations("API patterns", project="OtherProject")
        assert len(results) >= 1
        assert all("OtherProject" in r["project"] for r in results)

    def test_search_observations_empty_query(self, bridge):
        results = bridge.search_observations("")
        assert results == []

    def test_search_summaries(self, bridge):
        results = bridge.search_summaries("authentication")
        assert len(results) >= 1
        assert results[0]["kind"] == "summary"
        assert results[0]["source"] == "claude-mem"

    def test_search_summaries_by_project(self, bridge):
        results = bridge.search_summaries("authentication", project="TestProject")
        assert len(results) >= 1

    def test_get_recent_observations(self, bridge):
        results = bridge.get_recent_observations(limit=10)
        assert len(results) == 3  # All 3 test observations

    def test_get_recent_observations_filter_type(self, bridge):
        results = bridge.get_recent_observations(obs_type="feature")
        assert len(results) == 1
        assert results[0]["type"] == "feature"

    def test_get_recent_observations_filter_project(self, bridge):
        results = bridge.get_recent_observations(project="TestProject")
        assert len(results) == 2  # 2 in TestProject

    def test_get_timeline(self, bridge):
        results = bridge.get_timeline(limit=10)
        assert len(results) == 1
        assert results[0]["kind"] == "summary"
        assert results[0]["request"] == "Implement authentication system"

    def test_get_timeline_filter_project(self, bridge):
        results = bridge.get_timeline(project="NonExistent")
        assert len(results) == 0

    def test_get_stats(self, bridge):
        stats = bridge.get_stats()
        assert stats["available"] is True
        assert stats["total_observations"] == 3
        assert stats["total_sessions"] == 1
        assert stats["total_summaries"] == 1
        assert stats["total_prompts"] == 1
        assert "feature" in stats["observations_by_type"]
        assert stats["observations_by_type"]["feature"] == 1
        assert "TestProject" in stats["top_projects"]

    def test_get_projects(self, bridge):
        projects = bridge.get_projects()
        assert "TestProject" in projects
        assert "OtherProject" in projects

    def test_search_limit(self, bridge):
        results = bridge.search_observations("authentication", limit=1)
        assert len(results) <= 1


class TestEscapeFTS5:
    def test_single_word(self):
        assert _escape_fts5("hello") == '"hello"'

    def test_multiple_words(self):
        assert _escape_fts5("hello world") == '"hello" "world"'

    def test_empty_string(self):
        assert _escape_fts5("") == ""

    def test_whitespace_only(self):
        assert _escape_fts5("   ") == ""

    def test_special_chars_escaped(self):
        result = _escape_fts5('OR AND "quotes"')
        assert '"OR"' in result
        assert '"AND"' in result
