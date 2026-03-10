"""Doubao API client for embeddings and summarization."""
from __future__ import annotations

import json
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
            embedding = data["data"][0]["embedding"]
            # 豆包输出2048维，pgvector HNSW限制2000维，截断
            if len(embedding) > 2000:
                embedding = embedding[:2000]
            return embedding
        except Exception:
            logger.exception("Failed to get embedding from Doubao")
            return None

    async def summarize(self, text: str, max_tokens: int = 500) -> dict[str, Any] | None:
        if not self._settings.enabled or not self._settings.api_key:
            return None
        prompt = (
            '请将以下任务执行日志总结为结构化记忆。返回JSON格式:\n'
            '{\n'
            '  "summary": "一句话总结",\n'
            '  "key_decisions": ["决策1", "决策2"],\n'
            '  "files_changed": ["file1.py", "file2.py"],\n'
            '  "commands_run": ["cmd1", "cmd2"],\n'
            '  "tags": ["tag1", "tag2"],\n'
            '  "entities": [\n'
            '    {"name": "实体名", "type": "concept|file|person|project|bug", "content": "描述"}\n'
            '  ]\n'
            '}\n\n'
            f'任务日志:\n{text[:8000]}'
        )
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
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except Exception:
            logger.exception("Failed to summarize with Doubao")
            return None
