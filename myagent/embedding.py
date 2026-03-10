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
    return "[" + ",".join(str(v) for v in vec) + "]"
