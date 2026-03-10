import pytest
from unittest.mock import AsyncMock, MagicMock
from myagent.config import DoubaoSettings

from thinking.planner import Planner
from thinking.reflector import Reflector
from thinking.proactive import ProactiveThinking


@pytest.fixture
def disabled_doubao():
    doubao = AsyncMock()
    doubao._settings = DoubaoSettings(enabled=False)
    return doubao


def test_planner_creation(disabled_doubao):
    planner = Planner(disabled_doubao)
    assert planner._doubao is not None


@pytest.mark.asyncio
async def test_planner_disabled_returns_original(disabled_doubao):
    planner = Planner(disabled_doubao)
    result = await planner.decompose("complex task")
    assert len(result) == 1
    assert result[0]["prompt"] == "complex task"


def test_reflector_creation(disabled_doubao):
    reflector = Reflector(disabled_doubao)
    assert reflector._doubao is not None


@pytest.mark.asyncio
async def test_reflector_disabled_returns_unknown(disabled_doubao):
    reflector = Reflector(disabled_doubao)
    result = await reflector.evaluate("test", "result")
    assert result["quality"] == "unknown"
    assert result["needs_review"] is False


@pytest.mark.asyncio
async def test_proactive_disabled_returns_none(disabled_doubao):
    db = AsyncMock()
    feishu = AsyncMock()
    memory = AsyncMock()
    pt = ProactiveThinking(db, disabled_doubao, feishu, memory)
    result = await pt.daily_review()
    assert result is None
