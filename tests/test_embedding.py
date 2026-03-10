import pytest
from myagent.embedding import EmbeddingStore, _format_vector
from myagent.config import PostgresSettings


def test_format_vector():
    vec = [0.1, 0.2, 0.3]
    result = _format_vector(vec)
    assert result == "[0.1,0.2,0.3]"


def test_format_vector_empty():
    assert _format_vector([]) == "[]"


def test_embedding_store_creation():
    settings = PostgresSettings(dsn="postgresql://test@localhost/test", enabled=True)
    store = EmbeddingStore(settings)
    assert store._settings.enabled is True


@pytest.mark.asyncio
async def test_embedding_store_disabled():
    settings = PostgresSettings(enabled=False)
    store = EmbeddingStore(settings)
    await store.init()
    assert store._pool is None
    result = await store.search([0.1, 0.2], limit=5)
    assert result == []
    result = await store.store(1, "task_1", "test", [0.1, 0.2])
    assert result is None
    await store.delete_by_memory_id(1)  # should not raise
    await store.close()
