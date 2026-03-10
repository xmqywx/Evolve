import pytest
from unittest.mock import AsyncMock, MagicMock
from myagent.memory import MemoryManager, VECTOR_WEIGHT, KEYWORD_WEIGHT


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.get_task.return_value = MagicMock(
        id="task_1", prompt="test task", result_summary="done", raw_output="output"
    )
    db.get_task_logs.return_value = [
        {"event_type": "result", "content": "Task completed successfully"}
    ]
    db.search_memories.return_value = []
    db.create_memory = AsyncMock()
    db._conn = AsyncMock()
    db._conn.execute = AsyncMock()
    db._conn.commit = AsyncMock()
    return db


@pytest.fixture
def mock_doubao():
    doubao = AsyncMock()
    doubao.summarize.return_value = {
        "summary": "Test task completed",
        "key_decisions": ["decision1"],
        "files_changed": ["file1.py"],
        "commands_run": [],
        "tags": ["test"],
        "entities": [],
    }
    doubao.get_embedding.return_value = [0.1] * 2000
    return doubao


@pytest.fixture
def mock_embedding_store():
    store = AsyncMock()
    store.store.return_value = 1
    store.search.return_value = []
    return store


@pytest.mark.asyncio
async def test_summarize_task(mock_db, mock_doubao, mock_embedding_store):
    mm = MemoryManager(mock_db, mock_doubao, mock_embedding_store)
    result = await mm.summarize_task("task_1")
    assert result is not None
    assert result["summary"] == "Test task completed"
    mock_db.create_memory.assert_called_once()
    mock_doubao.get_embedding.assert_called()


@pytest.mark.asyncio
async def test_summarize_task_not_found(mock_db, mock_doubao, mock_embedding_store):
    mock_db.get_task.return_value = None
    mm = MemoryManager(mock_db, mock_doubao, mock_embedding_store)
    result = await mm.summarize_task("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_hybrid_search_keyword_only(mock_db, mock_doubao, mock_embedding_store):
    mock_doubao.get_embedding.return_value = None
    mock_db.search_memories.return_value = [
        {"id": 1, "task_id": "t1", "summary": "Found result", "tags": "[]", "project": None}
    ]
    mm = MemoryManager(mock_db, mock_doubao, mock_embedding_store)
    results = await mm.hybrid_search("test query")
    assert len(results) == 1
    assert results[0]["keyword_score"] == 1.0
    assert results[0]["score"] == KEYWORD_WEIGHT


@pytest.mark.asyncio
async def test_hybrid_search_vector_only(mock_db, mock_doubao, mock_embedding_store):
    mock_embedding_store.search.return_value = [
        {"memory_id": 1, "task_id": "t1", "content": "Vector result", "similarity": 0.9, "tags": [], "project": None}
    ]
    mm = MemoryManager(mock_db, mock_doubao, mock_embedding_store)
    results = await mm.hybrid_search("test query")
    assert len(results) == 1
    assert results[0]["vector_score"] == 0.9
    assert results[0]["score"] == pytest.approx(VECTOR_WEIGHT * 0.9)


@pytest.mark.asyncio
async def test_hybrid_search_combined(mock_db, mock_doubao, mock_embedding_store):
    mock_embedding_store.search.return_value = [
        {"memory_id": 1, "task_id": "t1", "content": "Result", "similarity": 0.8, "tags": [], "project": None}
    ]
    mock_db.search_memories.return_value = [
        {"id": 1, "task_id": "t1", "summary": "Result keyword", "tags": "[]", "project": None}
    ]
    mm = MemoryManager(mock_db, mock_doubao, mock_embedding_store)
    results = await mm.hybrid_search("test")
    assert len(results) == 1
    assert results[0]["vector_score"] == 0.8
    assert results[0]["keyword_score"] == 1.0
    expected_score = VECTOR_WEIGHT * 0.8 + KEYWORD_WEIGHT * 1.0
    assert results[0]["score"] == pytest.approx(expected_score)


@pytest.mark.asyncio
async def test_get_context_for_task(mock_db, mock_doubao, mock_embedding_store):
    mock_db.search_memories.return_value = [
        {"id": 1, "task_id": "t1", "summary": "Previous memory", "tags": "[]", "project": None}
    ]
    mock_doubao.get_embedding.return_value = None
    mm = MemoryManager(mock_db, mock_doubao, mock_embedding_store)
    context = await mm.get_context_for_task("new task")
    assert "Relevant Memories" in context
    assert "Previous memory" in context
