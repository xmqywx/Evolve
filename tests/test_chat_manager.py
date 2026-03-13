"""Tests for chat manager, context builder, and new DB tables."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from myagent.config import ChatSettings, ClaudeSettings
from myagent.context_builder import ContextBuilder
from myagent.db import Database
from myagent.session_registry import SessionRegistry
from myagent.memory import MemoryManager


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


@pytest.fixture
def chat_settings():
    return ChatSettings(max_messages_before_rotate=5)


@pytest.fixture
def mock_registry():
    registry = MagicMock(spec=SessionRegistry)
    registry.get_active_sessions.return_value = []
    return registry


@pytest.fixture
def mock_memory():
    memory = AsyncMock(spec=MemoryManager)
    memory.hybrid_search = AsyncMock(return_value=[])
    return memory


@pytest.fixture
def context_builder(db, mock_registry, mock_memory, chat_settings):
    return ContextBuilder(
        db=db,
        session_registry=mock_registry,
        memory_manager=mock_memory,
        chat_settings=chat_settings,
    )


# --- DB CRUD tests ---

class TestChatDB:
    @pytest.mark.asyncio
    async def test_create_chat_session(self, db):
        sid = await db.create_chat_session("test-session-1")
        assert sid > 0

    @pytest.mark.asyncio
    async def test_get_active_chat_session(self, db):
        await db.create_chat_session("test-session-1")
        session = await db.get_active_chat_session()
        assert session is not None
        assert session["claude_session_id"] == "test-session-1"
        assert session["status"] == "active"

    @pytest.mark.asyncio
    async def test_rotate_chat_session(self, db):
        sid = await db.create_chat_session("test-session-1")
        await db.rotate_chat_session(sid, "test summary")
        session = await db.get_active_chat_session()
        assert session is None

    @pytest.mark.asyncio
    async def test_add_and_get_chat_messages(self, db):
        await db.create_chat_session("sess-1")
        await db.add_chat_message("sess-1", "user", "hello")
        await db.add_chat_message("sess-1", "assistant", "hi there")
        messages = await db.get_chat_messages("sess-1")
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_get_recent_chat_messages(self, db):
        await db.create_chat_session("sess-1")
        await db.add_chat_message("sess-1", "user", "msg1")
        await db.add_chat_message("sess-1", "assistant", "msg2")
        messages = await db.get_recent_chat_messages(limit=10)
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_increment_message_count(self, db):
        sid = await db.create_chat_session("sess-1")
        await db.increment_chat_message_count(sid)
        await db.increment_chat_message_count(sid)
        session = await db.get_active_chat_session()
        assert session["message_count"] == 2

    @pytest.mark.asyncio
    async def test_list_chat_sessions(self, db):
        await db.create_chat_session("sess-1")
        await db.create_chat_session("sess-2")
        sessions = await db.list_chat_sessions()
        assert len(sessions) == 2


class TestSurvivalDB:
    @pytest.mark.asyncio
    async def test_create_survival_project(self, db):
        pid = await db.create_survival_project("test project", "desc", priority=8)
        assert pid > 0

    @pytest.mark.asyncio
    async def test_get_survival_project(self, db):
        pid = await db.create_survival_project("test project")
        project = await db.get_survival_project(pid)
        assert project is not None
        assert project["name"] == "test project"
        assert project["status"] == "idea"

    @pytest.mark.asyncio
    async def test_list_survival_projects(self, db):
        await db.create_survival_project("p1", priority=3)
        await db.create_survival_project("p2", priority=8)
        projects = await db.list_survival_projects()
        assert len(projects) == 2
        assert projects[0]["name"] == "p2"

    @pytest.mark.asyncio
    async def test_update_survival_project(self, db):
        pid = await db.create_survival_project("test")
        await db.update_survival_project(pid, status="prototyping", priority=9)
        project = await db.get_survival_project(pid)
        assert project["status"] == "prototyping"
        assert project["priority"] == 9

    @pytest.mark.asyncio
    async def test_get_active_survival_projects(self, db):
        await db.create_survival_project("p1")
        pid2 = await db.create_survival_project("p2")
        await db.update_survival_project(pid2, status="developing")
        active = await db.get_active_survival_projects()
        assert len(active) == 1
        assert active[0]["name"] == "p2"

    @pytest.mark.asyncio
    async def test_list_by_status(self, db):
        await db.create_survival_project("p1")
        pid2 = await db.create_survival_project("p2")
        await db.update_survival_project(pid2, status="developing")
        ideas = await db.list_survival_projects(status="idea")
        assert len(ideas) == 1


class TestProfileDB:
    @pytest.mark.asyncio
    async def test_add_profile_data(self, db):
        pid = await db.add_profile_data("git", "worked on MyAgent", category="project")
        assert pid > 0

    @pytest.mark.asyncio
    async def test_get_recent_profile_data(self, db):
        await db.add_profile_data("git", "commit 1")
        await db.add_profile_data("slack", "discussed project")
        all_data = await db.get_recent_profile_data()
        assert len(all_data) == 2
        git_data = await db.get_recent_profile_data(source="git")
        assert len(git_data) == 1


class TestContextBuilder:
    @pytest.mark.asyncio
    async def test_build_basic(self, context_builder):
        ctx = await context_builder.build()
        assert "当前状态" in ctx
        assert "行为准则" in ctx
        assert "中文" in ctx

    @pytest.mark.asyncio
    async def test_build_includes_sessions(self, context_builder, mock_registry):
        from myagent.models import SessionInfo, SessionStatus
        from datetime import datetime, timezone
        session = SessionInfo(
            id="test", pid=123, cwd="/tmp", project="TestProject",
            started_at=datetime.now(timezone.utc),
            last_active=datetime.now(timezone.utc),
            status=SessionStatus.ACTIVE,
        )
        mock_registry.get_active_sessions.return_value = [session]
        ctx = await context_builder.build()
        assert "1 个" in ctx
        assert "TestProject" in ctx


# --- Server endpoint tests (uses conftest.py config_yaml fixture) ---

@pytest_asyncio.fixture
async def client(config_yaml):
    from httpx import AsyncClient, ASGITransport
    from myagent.server import create_app
    app = await create_app(config_yaml)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test",
                           headers={"Authorization": "Bearer test"}) as c:
        yield c
    await app.state.feishu_client.close()
    await app.state.doubao_client.close()
    await app.state.embedding_store.close()
    await app.state.db.close()


class TestChatEndpoints:
    @pytest.mark.asyncio
    async def test_chat_history_empty(self, client):
        resp = await client.get("/api/chat/history")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_chat_sessions_empty(self, client):
        resp = await client.get("/api/chat/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_survival_projects_crud(self, client):
        # Create
        resp = await client.post(
            "/api/survival/projects",
            json={"name": "test project", "description": "make money", "priority": 8},
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 201, resp.text
        pid = resp.json()["id"]

        # List
        resp = await client.get("/api/survival/projects")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        # Update
        resp = await client.patch(
            f"/api/survival/projects/{pid}",
            json={"status": "developing"},
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_profile_insights_empty(self, client):
        resp = await client.get("/api/profile/insights")
        assert resp.status_code == 200
        assert resp.json() == []
