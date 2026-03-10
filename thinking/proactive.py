"""Proactive thinking - daily review and insight generation."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from myagent.db import Database
from myagent.doubao import DoubaoClient
from myagent.feishu import FeishuClient
from myagent.memory import MemoryManager

logger = logging.getLogger(__name__)


class ProactiveThinking:
    def __init__(
        self,
        db: Database,
        doubao: DoubaoClient,
        feishu: FeishuClient,
        memory_manager: MemoryManager,
    ) -> None:
        self._db = db
        self._doubao = doubao
        self._feishu = feishu
        self._memory = memory_manager

    async def daily_review(self) -> str | None:
        """Morning thinking: review yesterday, find patterns, generate insights."""
        if not self._doubao._settings.enabled or not self._doubao._settings.api_key:
            return None

        # Get recent tasks
        tasks = await self._db.list_tasks(limit=20)
        task_summaries = []
        for t in tasks:
            d = t.model_dump()
            task_summaries.append(
                f"- [{d['status']}] {d['prompt'][:100]} "
                f"(source: {d['source']})"
            )

        # Get recent memories
        memories = await self._memory.hybrid_search("recent work summary", limit=5)
        memory_text = "\n".join(
            f"- {m.get('content', '')[:200]}" for m in memories
        )

        prompt = (
            '你是MyAgent，Ying的AI分身。进行每日晨间回顾。\n'
            '分析最近的任务和记忆，找出:\n'
            '1. 工作模式和趋势\n'
            '2. 潜在的改进机会\n'
            '3. 值得关注的洞察\n'
            '4. 对Ying的建议\n\n'
            '用简洁中文回答，重点突出有价值的发现。\n\n'
            f'最近任务:\n{"chr(10)".join(task_summaries[:10])}\n\n'
            f'记忆:\n{memory_text}'
        )

        try:
            client = await self._doubao._get_client()
            resp = await client.post("/chat/completions", json={
                "model": self._doubao._settings.chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 800,
                "temperature": 0.7,
            })
            resp.raise_for_status()
            data = resp.json()
            insight = data["choices"][0]["message"]["content"]

            # Send to Feishu
            await self._feishu.send_text(f"🌅 MyAgent 晨间回顾\n\n{insight}")

            return insight
        except Exception:
            logger.exception("Daily review failed")
            return None
