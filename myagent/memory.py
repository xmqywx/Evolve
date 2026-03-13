"""Memory manager - summarize tasks, hybrid search, entity management.

Bridge mode: combines MyAgent's own memories (SQLite + pgvector) with
claude-mem's cross-session observations for unified search results.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from myagent.claude_mem import ClaudeMemBridge
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
        claude_mem: ClaudeMemBridge | None = None,
    ) -> None:
        self._db = db
        self._doubao = doubao
        self._embedding_store = embedding_store
        self._claude_mem = claude_mem

    @property
    def claude_mem(self) -> ClaudeMemBridge | None:
        return self._claude_mem

    async def summarize_task(self, task_id: str) -> dict | None:
        task = await self._db.get_task(task_id)
        if task is None:
            return None

        logs = await self._db.get_task_logs(task_id)
        log_text = "\n".join(
            f"[{l.get('event_type', '')}] {l.get('content', '')}" for l in logs
        )
        if not log_text.strip():
            log_text = task.prompt + "\n" + (task.result_summary or "")

        structured = await self._doubao.summarize(log_text)
        if structured is None:
            structured = {
                "summary": task.result_summary or task.prompt,
                "key_decisions": [],
                "files_changed": [],
                "commands_run": [],
                "tags": [],
                "entities": [],
            }

        memory_id = await self._db.create_memory(
            task_id=task_id,
            summary=structured.get("summary", ""),
            key_decisions=json.dumps(structured.get("key_decisions", [])),
            files_changed=json.dumps(structured.get("files_changed", [])),
            tags=json.dumps(structured.get("tags", [])),
        )

        # Store embedding in pgvector
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
            await self._db.create_entity(
                name=entity.get("name", ""),
                entity_type=entity.get("type"),
                content=entity.get("content"),
                task_id=task_id,
            )

        return structured

    async def hybrid_search(
        self, query: str, limit: int = 10, project: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search across both MyAgent memories and claude-mem observations."""
        results: dict[str, dict] = {}

        # --- MyAgent vector search ---
        embedding = await self._doubao.get_embedding(query)
        if embedding:
            vector_results = await self._embedding_store.search(
                query_embedding=embedding, limit=limit * 2, project=project,
            )
            for r in vector_results:
                key = f"myagent_mem_{r.get('memory_id', r.get('id'))}"
                results[key] = {
                    "source": "myagent",
                    "kind": "memory",
                    "memory_id": r.get("memory_id"),
                    "task_id": r.get("task_id"),
                    "content": r.get("content", ""),
                    "tags": r.get("tags", []),
                    "project": r.get("project"),
                    "vector_score": float(r.get("similarity", 0)),
                    "keyword_score": 0.0,
                }

        # --- MyAgent keyword search ---
        keyword_results = await self._db.search_memories(query, limit=limit * 2)
        for r in keyword_results:
            key = f"myagent_mem_{r.get('id')}"
            if key in results:
                results[key]["keyword_score"] = 1.0
                results[key]["summary"] = r.get("summary", "")
            else:
                results[key] = {
                    "source": "myagent",
                    "kind": "memory",
                    "memory_id": r.get("id"),
                    "task_id": r.get("task_id"),
                    "content": r.get("summary", ""),
                    "tags": r.get("tags"),
                    "project": r.get("project"),
                    "vector_score": 0.0,
                    "keyword_score": 1.0,
                }

        # --- claude-mem observations ---
        if self._claude_mem and self._claude_mem.available:
            cm_results = self._claude_mem.search_observations(
                query, limit=limit, project=project,
            )
            for r in cm_results:
                key = f"cm_obs_{r.get('id')}"
                # Build content from available fields
                parts = []
                if r.get("title"):
                    parts.append(r["title"])
                if r.get("narrative"):
                    parts.append(r["narrative"])
                elif r.get("text"):
                    parts.append(r["text"])
                content = " - ".join(parts) if parts else ""

                results[key] = {
                    "source": "claude-mem",
                    "kind": "observation",
                    "obs_type": r.get("type", ""),
                    "title": r.get("title", ""),
                    "content": content,
                    "project": r.get("project"),
                    "created_at": r.get("created_at"),
                    "facts": r.get("facts"),
                    "files_modified": r.get("files_modified"),
                    "vector_score": 0.0,
                    "keyword_score": 0.8,  # FTS5 match from claude-mem
                }

            # Also search summaries
            cm_summaries = self._claude_mem.search_summaries(
                query, limit=limit // 2, project=project,
            )
            for r in cm_summaries:
                key = f"cm_sum_{r.get('id')}"
                parts = []
                if r.get("request"):
                    parts.append(r["request"])
                if r.get("learned"):
                    parts.append(f"Learned: {r['learned']}")
                content = " | ".join(parts) if parts else ""

                results[key] = {
                    "source": "claude-mem",
                    "kind": "summary",
                    "content": content,
                    "project": r.get("project"),
                    "created_at": r.get("created_at"),
                    "completed": r.get("completed"),
                    "next_steps": r.get("next_steps"),
                    "vector_score": 0.0,
                    "keyword_score": 0.7,
                }

        # Score and rank
        for r in results.values():
            r["score"] = VECTOR_WEIGHT * r["vector_score"] + KEYWORD_WEIGHT * r["keyword_score"]

        ranked = sorted(results.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:limit]

    async def get_context_for_task(self, prompt: str, limit: int = 5) -> str:
        """Get relevant memory context for a new task."""
        memories = await self.hybrid_search(prompt, limit=limit)
        if not memories:
            return ""
        lines = ["## Relevant Memories\n"]
        for m in memories:
            content = m.get("content") or m.get("summary", "")
            source_tag = f"[{m.get('source', 'unknown')}]"
            lines.append(f"- {source_tag} {content[:200]}")
        return "\n".join(lines)
