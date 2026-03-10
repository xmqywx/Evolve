# Phase 3: Memory System + Vector Search

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the three-layer memory system (raw logs + structured summaries + knowledge entities) with hybrid search combining pgvector semantic search (weight 0.7) and SQLite FTS5 keyword search (weight 0.3). Use Doubao embedding API for vector generation.

**Architecture:** Task completion triggers memory summarization (via Doubao). Summaries are stored in SQLite (with FTS5) and their embeddings in PostgreSQL/pgvector. Hybrid search combines both results with weighted scoring.

**Tech Stack:** Python 3.14, asyncpg, pgvector, Doubao embedding API (doubao-embedding-large-text-240915), httpx

---

## File Map

| File | Responsibility |
|------|---------------|
| `myagent/config.py` | Add DoubaoSettings, PostgresSettings |
| `config.yaml` | Add doubao + postgres config sections |
| `myagent/doubao.py` | Doubao API client: embeddings + summarization |
| `myagent/embedding.py` | Vector storage: pgvector CRUD + similarity search |
| `myagent/memory.py` | Memory manager: summarize tasks, hybrid search, entity extraction |
| `myagent/server.py` | Add memory endpoints, wire memory into scheduler callback |
| `schema.sql` | PostgreSQL schema for pgvector |
| `tests/test_doubao.py` | Test Doubao API client (mocked) |
| `tests/test_embedding.py` | Test pgvector operations |
| `tests/test_memory.py` | Test memory manager + hybrid search |

---

## Chunk 1: Config + Doubao Client

### Task 1: Add Doubao and Postgres config settings

**Files:**
- Modify: `myagent/config.py`
- Modify: `config.yaml`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add DoubaoSettings and PostgresSettings to config.py**

```python
class DoubaoSettings(BaseModel):
    api_key: str = ""
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    chat_model: str = "doubao-seed-2-0-pro-260215"
    embedding_model: str = "doubao-embedding-large-text-240915"
    enabled: bool = True

class PostgresSettings(BaseModel):
    dsn: str = "postgresql://ying@localhost/myagent"
    enabled: bool = True
```

Add to AgentConfig:
```python
class AgentConfig(BaseModel):
    agent: AgentSettings
    claude: ClaudeSettings
    scheduler: SchedulerSettings
    server: ServerSettings
    feishu: FeishuSettings = FeishuSettings()
    relay: RelaySettings = RelaySettings()
    doubao: DoubaoSettings = DoubaoSettings()
    postgres: PostgresSettings = PostgresSettings()
```

- [ ] **Step 2: Update config.yaml**

```yaml
doubao:
  api_key: ""
  base_url: "https://ark.cn-beijing.volces.com/api/v3"
  chat_model: "doubao-seed-2-0-pro-260215"
  embedding_model: "doubao-embedding-large-text-240915"
  enabled: false

postgres:
  dsn: "postgresql://ying@localhost/myagent"
  enabled: false
```

- [ ] **Step 3: Update conftest.py** — add `doubao: enabled: false` and `postgres: enabled: false`

- [ ] **Step 4: Add config test, run all tests, commit**

### Task 2: Doubao API client

**Files:**
- Create: `myagent/doubao.py`
- Create: `tests/test_doubao.py`
- Modify: `requirements.txt` (add asyncpg)

- [ ] **Step 1: Create myagent/doubao.py**

```python
"""Doubao (豆包) API client for embeddings and summarization."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from myagent.config import DoubaoSettings

logger = logging.getLogger(__name__)


class DoubaoClient:
    def __init__(self, settings: DoubaoSettings) -> None:
        self._settings = settings
        self._http: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self._settings.base_url,
                headers={"Authorization": f"Bearer {self._settings.api_key}"},
                timeout=30,
            )
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def get_embedding(self, text: str) -> list[float] | None:
        """Get embedding vector for text using Doubao embedding model."""
        if not self._settings.enabled or not self._settings.api_key:
            return None
        try:
            client = await self._get_client()
            resp = await client.post("/embeddings", json={
                "model": self._settings.embedding_model,
                "input": [text],
                "encoding_format": "float",
            })
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]
        except Exception:
            logger.exception("Failed to get embedding from Doubao")
            return None

    async def summarize(self, text: str, max_tokens: int = 500) -> dict[str, Any] | None:
        """Summarize task output into structured memory format."""
        if not self._settings.enabled or not self._settings.api_key:
            return None
        prompt = f"""请将以下任务执行日志总结为结构化记忆。返回JSON格式:
{{
  "summary": "一句话总结",
  "key_decisions": ["决策1", "决策2"],
  "files_changed": ["file1.py", "file2.py"],
  "commands_run": ["cmd1", "cmd2"],
  "tags": ["tag1", "tag2"],
  "entities": [
    {{"name": "实体名", "type": "concept|file|person|project|bug", "content": "描述"}}
  ]
}}

任务日志:
{text[:8000]}"""

        try:
            client = await self._get_client()
            resp = await client.post("/chat/completions", json={
                "model": self._settings.chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            })
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            # Parse JSON from response
            import json
            # Try to extract JSON from markdown code block
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except Exception:
            logger.exception("Failed to summarize with Doubao")
            return None
```

- [ ] **Step 2: Create tests/test_doubao.py**

```python
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from myagent.doubao import DoubaoClient
from myagent.config import DoubaoSettings


def test_doubao_client_creation():
    settings = DoubaoSettings(api_key="test_key", enabled=True)
    client = DoubaoClient(settings)
    assert client._settings.api_key == "test_key"


@pytest.mark.asyncio
async def test_doubao_disabled_returns_none():
    settings = DoubaoSettings(enabled=False)
    client = DoubaoClient(settings)
    result = await client.get_embedding("test")
    assert result is None
    result = await client.summarize("test")
    assert result is None


@pytest.mark.asyncio
async def test_doubao_no_api_key_returns_none():
    settings = DoubaoSettings(api_key="", enabled=True)
    client = DoubaoClient(settings)
    result = await client.get_embedding("test")
    assert result is None
```

- [ ] **Step 3: Add asyncpg to requirements.txt, install**

```bash
echo "asyncpg>=0.30.0" >> requirements.txt
pip install asyncpg
```

- [ ] **Step 4: Run all tests, commit**

---

## Chunk 2: PostgreSQL + pgvector Embedding Storage

### Task 3: PostgreSQL schema + pgvector setup

**Files:**
- Create: `schema.sql`

- [ ] **Step 1: Create schema.sql**

```sql
-- Run this once: CREATE DATABASE myagent;
-- Then connect to myagent and run:

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memory_embeddings (
    id SERIAL PRIMARY KEY,
    memory_id INTEGER NOT NULL,
    task_id TEXT,
    content TEXT NOT NULL,
    embedding vector(2048),
    tags TEXT[],
    project TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_hnsw
    ON memory_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_tags
    ON memory_embeddings USING gin (tags);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_project
    ON memory_embeddings (project);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_task_id
    ON memory_embeddings (task_id);
```

- [ ] **Step 2: Create database and run schema**

```bash
createdb myagent 2>/dev/null || true
psql -U ying -d myagent -f schema.sql
```

- [ ] **Step 3: Commit**

### Task 4: Embedding storage module (pgvector operations)

**Files:**
- Create: `myagent/embedding.py`
- Create: `tests/test_embedding.py`

- [ ] **Step 1: Create myagent/embedding.py**

```python
"""Vector embedding storage using PostgreSQL + pgvector."""
from __future__ import annotations

import logging
from typing import Any

import asyncpg

from myagent.config import PostgresSettings

logger = logging.getLogger(__name__)


class EmbeddingStore:
    def __init__(self, settings: PostgresSettings) -> None:
        self._settings = settings
        self._pool: asyncpg.Pool | None = None

    async def init(self) -> None:
        if not self._settings.enabled:
            logger.info("PostgreSQL/pgvector disabled")
            return
        try:
            self._pool = await asyncpg.create_pool(self._settings.dsn, min_size=1, max_size=5)
            # Register vector type
            async with self._pool.acquire() as conn:
                await conn.execute("SELECT 1")
            logger.info("Connected to PostgreSQL with pgvector")
        except Exception:
            logger.exception("Failed to connect to PostgreSQL")
            self._pool = None

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def store(
        self,
        memory_id: int,
        task_id: str | None,
        content: str,
        embedding: list[float],
        tags: list[str] | None = None,
        project: str | None = None,
    ) -> int | None:
        if not self._pool:
            return None
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """INSERT INTO memory_embeddings (memory_id, task_id, content, embedding, tags, project)
                       VALUES ($1, $2, $3, $4::vector, $5, $6)
                       RETURNING id""",
                    memory_id, task_id, content,
                    _format_vector(embedding), tags, project,
                )
                return row["id"]
        except Exception:
            logger.exception("Failed to store embedding")
            return None

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self._pool:
            return []
        try:
            vec_str = _format_vector(query_embedding)
            if project:
                sql = """SELECT id, memory_id, task_id, content, tags, project,
                                1 - (embedding <=> $1::vector) AS similarity
                         FROM memory_embeddings
                         WHERE project = $2
                         ORDER BY embedding <=> $1::vector
                         LIMIT $3"""
                args = (vec_str, project, limit)
            else:
                sql = """SELECT id, memory_id, task_id, content, tags, project,
                                1 - (embedding <=> $1::vector) AS similarity
                         FROM memory_embeddings
                         ORDER BY embedding <=> $1::vector
                         LIMIT $2"""
                args = (vec_str, limit)

            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, *args)
                return [dict(r) for r in rows]
        except Exception:
            logger.exception("Failed to search embeddings")
            return []

    async def delete_by_memory_id(self, memory_id: int) -> None:
        if not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM memory_embeddings WHERE memory_id = $1", memory_id
                )
        except Exception:
            logger.exception("Failed to delete embedding")


def _format_vector(vec: list[float]) -> str:
    """Format vector as PostgreSQL vector literal."""
    return "[" + ",".join(str(v) for v in vec) + "]"
```

- [ ] **Step 2: Create tests/test_embedding.py** (unit tests that don't need real DB)

```python
import pytest
from myagent.embedding import EmbeddingStore, _format_vector
from myagent.config import PostgresSettings


def test_format_vector():
    vec = [0.1, 0.2, 0.3]
    result = _format_vector(vec)
    assert result == "[0.1,0.2,0.3]"


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
```

- [ ] **Step 3: Run tests, commit**

---

## Chunk 3: Memory Manager + Hybrid Search

### Task 5: Memory manager with hybrid search

**Files:**
- Create: `myagent/memory.py`
- Create: `tests/test_memory.py`

- [ ] **Step 1: Create myagent/memory.py**

```python
"""Memory manager - summarize tasks, hybrid search, entity management."""
from __future__ import annotations

import json
import logging
from typing import Any

from myagent.db import Database
from myagent.doubao import DoubaoClient
from myagent.embedding import EmbeddingStore

logger = logging.getLogger(__name__)

VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3


class MemoryManager:
    def __init__(
        self,
        db: Database,
        doubao: DoubaoClient,
        embedding_store: EmbeddingStore,
    ) -> None:
        self._db = db
        self._doubao = doubao
        self._embedding_store = embedding_store

    async def summarize_task(self, task_id: str) -> dict | None:
        """Summarize a completed task into structured memory + embeddings."""
        task = await self._db.get_task(task_id)
        if task is None:
            return None

        # Get task logs
        logs = await self._db.get_task_logs(task_id)
        log_text = "\n".join(
            f"[{l.get('event_type', '')}] {l.get('content', '')}"
            for l in logs
        )

        if not log_text.strip():
            log_text = task.prompt + "\n" + (task.result_summary or "")

        # Summarize via Doubao
        structured = await self._doubao.summarize(log_text)

        if structured is None:
            # Fallback: minimal summary
            structured = {
                "summary": task.result_summary or task.prompt,
                "key_decisions": [],
                "files_changed": [],
                "commands_run": [],
                "tags": [],
                "entities": [],
            }

        # Store in SQLite memories table
        await self._db.create_memory(
            task_id=task_id,
            summary=structured.get("summary", ""),
            key_decisions=json.dumps(structured.get("key_decisions", [])),
            files_changed=json.dumps(structured.get("files_changed", [])),
            tags=json.dumps(structured.get("tags", [])),
        )

        # Get memory ID (last inserted)
        memories = await self._db.search_memories(structured.get("summary", "")[:50], limit=1)
        memory_id = memories[0]["id"] if memories else 0

        # Generate embedding and store in pgvector
        summary_text = structured.get("summary", "")
        embedding = await self._doubao.get_embedding(summary_text)
        if embedding and memory_id:
            await self._embedding_store.store(
                memory_id=memory_id,
                task_id=task_id,
                content=summary_text,
                embedding=embedding,
                tags=structured.get("tags"),
            )

        # Extract entities
        for entity in structured.get("entities", []):
            await self._db._conn.execute(
                """INSERT INTO entities (name, type, content, first_seen, last_updated, source_task_ids)
                   VALUES (?, ?, ?, datetime('now'), datetime('now'), ?)""",
                (entity.get("name"), entity.get("type"), entity.get("content"),
                 json.dumps([task_id])),
            )
            await self._db._conn.commit()

        return structured

    async def hybrid_search(
        self,
        query: str,
        limit: int = 10,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid search: pgvector (0.7) + FTS5 (0.3), merged and ranked."""
        results: dict[str, dict] = {}

        # 1. Vector search via pgvector
        embedding = await self._doubao.get_embedding(query)
        if embedding:
            vector_results = await self._embedding_store.search(
                query_embedding=embedding, limit=limit * 2, project=project,
            )
            for r in vector_results:
                key = f"mem_{r.get('memory_id', r.get('id'))}"
                results[key] = {
                    "memory_id": r.get("memory_id"),
                    "task_id": r.get("task_id"),
                    "content": r.get("content", ""),
                    "tags": r.get("tags", []),
                    "project": r.get("project"),
                    "vector_score": float(r.get("similarity", 0)),
                    "keyword_score": 0.0,
                }

        # 2. Keyword search via SQLite FTS5
        keyword_results = await self._db.search_memories(query, limit=limit * 2)
        for r in keyword_results:
            key = f"mem_{r.get('id')}"
            if key in results:
                results[key]["keyword_score"] = 1.0
                results[key]["summary"] = r.get("summary", "")
            else:
                results[key] = {
                    "memory_id": r.get("id"),
                    "task_id": r.get("task_id"),
                    "content": r.get("summary", ""),
                    "tags": r.get("tags"),
                    "project": r.get("project"),
                    "vector_score": 0.0,
                    "keyword_score": 1.0,
                }

        # 3. Compute combined score and sort
        for r in results.values():
            r["score"] = (
                VECTOR_WEIGHT * r["vector_score"]
                + KEYWORD_WEIGHT * r["keyword_score"]
            )

        ranked = sorted(results.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:limit]

    async def get_context_for_task(self, prompt: str, limit: int = 5) -> str:
        """Get relevant memory context to inject into a task prompt."""
        memories = await self.hybrid_search(prompt, limit=limit)
        if not memories:
            return ""
        lines = ["## Relevant Memories\n"]
        for m in memories:
            content = m.get("content") or m.get("summary", "")
            lines.append(f"- {content[:200]}")
        return "\n".join(lines)
```

- [ ] **Step 2: Create tests/test_memory.py**

```python
import pytest
import json
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
    doubao.get_embedding.return_value = [0.1] * 2048
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
    mock_doubao.get_embedding.return_value = None  # No vector search
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
```

- [ ] **Step 3: Run tests, commit**

---

## Chunk 4: Server Integration + API Endpoints

### Task 6: Wire memory into server + add endpoints

**Files:**
- Modify: `myagent/server.py`

- [ ] **Step 1: Modify server.py**

In `create_app()`:
- Create DoubaoClient, EmbeddingStore, MemoryManager
- Initialize EmbeddingStore
- Store on app.state
- Update on_task_done callback to also summarize task into memory
- Update `/api/memory/search` to use hybrid search
- Add new endpoint: `GET /api/memory/context?q=...` for getting context string

In `run_server()`:
- Close EmbeddingStore and DoubaoClient on shutdown

- [ ] **Step 2: Run all tests, commit**

### Task 7: Setup PostgreSQL database and run schema

- [ ] **Step 1: Create database**
```bash
createdb myagent 2>/dev/null || true
```

- [ ] **Step 2: Run schema**
```bash
psql -U ying -d myagent -f schema.sql
```

- [ ] **Step 3: Verify**
```bash
psql -U ying -d myagent -c "\dt"
psql -U ying -d myagent -c "\dx"
```

### Task 8: Full test suite + E2E

- [ ] **Step 1: Run all tests**
- [ ] **Step 2: Final commit**
