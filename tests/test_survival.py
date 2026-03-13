"""Tests for SurvivalEngine v5 (tmux-based)."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from myagent.config import SurvivalSettings, ClaudeSettings
from myagent.db import Database
from myagent.survival import SurvivalEngine


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


@pytest.fixture
def settings(tmp_path):
    return SurvivalSettings(
        enabled=True,
        workspace=str(tmp_path / "workspace"),
        notify_feishu=False,
    )


@pytest.fixture
def claude_settings():
    return ClaudeSettings(binary="claude", model="test-model")


@pytest.fixture
def mock_feishu():
    f = AsyncMock()
    f.send_text = AsyncMock(return_value=True)
    return f


@pytest.fixture
def on_log():
    return AsyncMock()


@pytest.fixture
def engine(db, claude_settings, mock_feishu, settings, on_log):
    return SurvivalEngine(
        db=db, claude_settings=claude_settings, feishu=mock_feishu,
        settings=settings, on_log=on_log,
    )


class TestSurvivalEngine:
    def test_workspace_created(self, engine):
        assert engine._workspace.exists()

    def test_tmux_available(self, engine):
        # tmux is installed on this system
        assert engine._tmux_available()

    @pytest.mark.asyncio
    async def test_start_no_tmux(self, engine):
        """Start fails gracefully if tmux not available."""
        with patch.object(SurvivalEngine, '_tmux_available', return_value=False):
            result = await engine.start()
        assert result["status"] == "error"
        assert "tmux" in result["error"]

    @pytest.mark.asyncio
    async def test_start_already_running(self, engine):
        """Start returns already_running if session exists."""
        with patch.object(engine, '_tmux_session_exists', return_value=True):
            result = await engine.start()
        assert result["status"] == "already_running"

    @pytest.mark.asyncio
    async def test_start_first_time(self, engine, on_log):
        """First start creates tmux session and sends identity prompt."""
        with patch.object(engine, '_tmux_session_exists', return_value=False), \
             patch.object(engine, '_run_cmd', return_value=(0, "")) as mock_cmd, \
             patch.object(engine, 'send_message', return_value={"status": "sent"}) as mock_send:
            result = await engine.start()

        assert result["status"] == "started"
        assert result["restart_count"] == 1
        # Should have called tmux new-session
        assert any("new-session" in str(call) for call in mock_cmd.call_args_list)
        # Should have sent identity prompt
        mock_send.assert_called_once()
        prompt = mock_send.call_args[0][0]
        assert "生存引擎" in prompt

    @pytest.mark.asyncio
    async def test_start_with_resume(self, engine):
        """Start with existing session ID uses --resume via send-keys."""
        engine._session_file.parent.mkdir(parents=True, exist_ok=True)
        engine._session_file.write_text("existing-session-123")

        with patch.object(engine, '_tmux_session_exists', return_value=False), \
             patch.object(engine, '_run_cmd', return_value=(0, "")) as mock_cmd:
            result = await engine.start()

        assert result["status"] == "started"
        # --resume should be in one of the send-keys calls
        all_calls = " ".join(str(c) for c in mock_cmd.call_args_list)
        assert "--resume" in all_calls
        assert "existing-session-123" in all_calls

    @pytest.mark.asyncio
    async def test_stop(self, engine):
        """Stop kills tmux session."""
        with patch.object(engine, '_tmux_session_exists', return_value=True), \
             patch.object(engine, '_run_cmd', return_value=(0, "")):
            result = await engine.stop()
        assert result["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_stop_not_running(self, engine):
        with patch.object(engine, '_tmux_session_exists', return_value=False):
            result = await engine.stop()
        assert result["status"] == "not_running"

    @pytest.mark.asyncio
    async def test_interrupt(self, engine):
        """Interrupt sends Ctrl+C via tmux."""
        with patch.object(engine, '_tmux_session_exists', return_value=True), \
             patch.object(engine, '_run_cmd', return_value=(0, "")) as mock_cmd:
            result = await engine.interrupt()
        assert result["status"] == "interrupted"
        assert any("C-c" in str(call) for call in mock_cmd.call_args_list)

    @pytest.mark.asyncio
    async def test_interrupt_not_running(self, engine):
        with patch.object(engine, '_tmux_session_exists', return_value=False):
            result = await engine.interrupt()
        assert result["status"] == "not_running"

    @pytest.mark.asyncio
    async def test_send_message(self, engine, on_log):
        """Send message writes to temp file and uses tmux paste-buffer."""
        with patch.object(engine, '_tmux_session_exists', return_value=True), \
             patch.object(engine, '_run_cmd', return_value=(0, "")):
            result = await engine.send_message("去 Upwork 看看新单")
        assert result["status"] == "sent"
        # Log should record the inject
        inject_calls = [c for c in on_log.call_args_list if "inject" in str(c)]
        assert len(inject_calls) >= 1

    @pytest.mark.asyncio
    async def test_send_message_not_running(self, engine):
        with patch.object(engine, '_tmux_session_exists', return_value=False):
            result = await engine.send_message("test")
        assert result["status"] == "not_running"

    @pytest.mark.asyncio
    async def test_get_status(self, engine):
        with patch.object(engine, '_tmux_session_exists', return_value=True), \
             patch.object(engine, '_tmux_get_pane_pid', return_value=12345), \
             patch.object(engine, '_tmux_get_current_command', return_value="claude"):
            status = await engine.get_status()

        assert status["running"] is True
        assert status["pid"] == 12345
        assert status["current_command"] == "claude"

    @pytest.mark.asyncio
    async def test_get_status_not_running(self, engine):
        with patch.object(engine, '_tmux_session_exists', return_value=False):
            status = await engine.get_status()
        assert status["running"] is False
        assert status["pid"] is None

    def test_session_id_persistence(self, engine):
        engine._save_claude_session_id("test-sid-123")
        assert engine._claude_session_id == "test-sid-123"
        loaded = engine._load_claude_session_id()
        assert loaded == "test-sid-123"

    @pytest.mark.asyncio
    async def test_build_identity_prompt(self, engine, db):
        await db.create_survival_project("AI service", "automation", priority=9)
        projects = await db.list_survival_projects()
        profile = await db.get_recent_profile_data(limit=5)

        prompt = engine._build_identity_prompt(projects, profile)
        assert "AI service" in prompt
        assert "生存引擎" in prompt
        assert "plans/" in prompt
        assert "Upwork" in prompt

    @pytest.mark.asyncio
    async def test_discover_session_id(self, engine):
        """Discover links tmux PID to scanner session."""
        with patch.object(engine, '_tmux_get_pane_pid', return_value=12345):
            sessions = [
                {"pid": 99999, "id": "other-session"},
                {"pid": 12345, "id": "our-session-abc"},
            ]
            sid = await engine.discover_session_id(sessions)
        assert sid == "our-session-abc"
        assert engine._claude_session_id == "our-session-abc"

    def test_stop_watchdog(self, engine):
        engine._running = True
        engine.stop_watchdog()
        assert engine._running is False

    @pytest.mark.asyncio
    async def test_log(self, engine, on_log):
        await engine._log("test_step", "test content")
        on_log.assert_called_once()
        assert on_log.call_args[0][1] == "test_step"
        assert on_log.call_args[0][2] == "test content"
