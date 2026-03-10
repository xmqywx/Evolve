import pytest
from unittest.mock import AsyncMock
from myagent.router import MessageRouter, SIMPLE, COMPLEX, SYSTEM, SEARCH, CHAT
from myagent.config import DoubaoSettings


@pytest.fixture
def router():
    settings = DoubaoSettings(enabled=False)
    doubao = AsyncMock()
    doubao._settings = settings
    return MessageRouter(doubao)


def test_classify_system_status(router):
    cat, detail = router.classify_by_rules("状态")
    assert cat == SYSTEM
    assert detail == "status"


def test_classify_system_cancel(router):
    cat, detail = router.classify_by_rules("取消")
    assert cat == SYSTEM
    assert detail == "cancel"


def test_classify_system_list(router):
    cat, detail = router.classify_by_rules("任务列表")
    assert cat == SYSTEM
    assert detail == "list_tasks"


def test_classify_search(router):
    cat, _ = router.classify_by_rules("搜索 Python best practices")
    assert cat == SEARCH


def test_classify_code_task(router):
    cat, _ = router.classify_by_rules("帮我修复这个bug")
    assert cat == SIMPLE


def test_classify_complex(router):
    cat, _ = router.classify_by_rules("设计一个新项目")
    assert cat == COMPLEX


def test_classify_default(router):
    cat, _ = router.classify_by_rules("hello world")
    assert cat == SIMPLE


@pytest.mark.asyncio
async def test_classify_system_uses_rules(router):
    result = await router.classify("状态")
    assert result["category"] == SYSTEM
    assert result["method"] == "rules"


@pytest.mark.asyncio
async def test_classify_fallback_when_doubao_disabled(router):
    result = await router.classify("帮我写代码")
    assert result["category"] == SIMPLE
    assert result["method"] == "rules"
