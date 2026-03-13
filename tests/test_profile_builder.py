"""Tests for ProfileBuilder."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

from myagent.config import ProfileSettings
from myagent.db import Database
from myagent.profile_builder import ProfileBuilder


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


@pytest.fixture
def mock_doubao():
    d = AsyncMock()
    d.chat = AsyncMock(return_value="工作摘要")
    return d


@pytest.fixture
def settings():
    return ProfileSettings(
        git_scan_enabled=True,
        terminal_history_enabled=True,
        browser_history_enabled=False,
    )


@pytest.fixture
def builder(db, mock_doubao, settings):
    return ProfileBuilder(db=db, doubao=mock_doubao, settings=settings)


class TestProfileBuilder:
    @pytest.mark.asyncio
    async def test_scan_all_calls_enabled_sources(self, builder):
        with patch.object(builder, "_scan_git", new_callable=AsyncMock, return_value={"status": "ok", "repos": 2}), \
             patch.object(builder, "_scan_terminal", new_callable=AsyncMock, return_value={"status": "ok", "commands": 50}), \
             patch.object(builder, "_scan_browser", new_callable=AsyncMock) as mock_browser:
            results = await builder.scan_all()
            assert "git" in results
            assert "terminal" in results
            assert "browser" not in results
            mock_browser.assert_not_called()

    @pytest.mark.asyncio
    async def test_scan_git_stores_profile_data(self, builder, db, mock_doubao):
        with patch("myagent.profile_builder.subprocess") as mock_sp:
            # Mock find command
            mock_sp.run.side_effect = [
                type("Result", (), {"stdout": "/tmp/fake/.git\n", "returncode": 0})(),
                type("Result", (), {"stdout": "abc123 test commit\ndef456 another commit\n", "returncode": 0})(),
            ]
            result = await builder._scan_git()
            assert result["status"] == "ok"
            mock_doubao.chat.assert_called_once()

            # Verify data stored
            data = await db.get_recent_profile_data(source="git")
            assert len(data) == 1

    @pytest.mark.asyncio
    async def test_scan_terminal_reads_history(self, builder, db, mock_doubao, tmp_path):
        # Create a fake zsh history
        history = tmp_path / ".zsh_history"
        history.write_text(": 1234567890:0;cd ~/Documents\n: 1234567891:0;git status\n")

        with patch("myagent.profile_builder.Path.home", return_value=tmp_path):
            result = await builder._scan_terminal()
            assert result["status"] == "ok"
            assert result["commands"] == 2

    @pytest.mark.asyncio
    async def test_scan_browser_skip_if_no_chrome(self, builder):
        with patch("myagent.profile_builder.Path.exists", return_value=False):
            result = await builder._scan_browser()
            assert result["status"] == "skip"

    @pytest.mark.asyncio
    async def test_disabled_sources_skipped(self, db, mock_doubao):
        settings = ProfileSettings(
            git_scan_enabled=False,
            terminal_history_enabled=False,
            browser_history_enabled=False,
        )
        builder = ProfileBuilder(db=db, doubao=mock_doubao, settings=settings)
        results = await builder.scan_all()
        assert results == {}
