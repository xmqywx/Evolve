"""Task planner - decompose complex tasks into subtasks using Doubao."""
from __future__ import annotations

import json
import logging
from typing import Any

from myagent.doubao import DoubaoClient

logger = logging.getLogger(__name__)


class Planner:
    def __init__(self, doubao: DoubaoClient) -> None:
        self._doubao = doubao

    async def decompose(self, prompt: str) -> list[dict[str, str]]:
        """Break a complex task into subtasks using Doubao."""
        if not self._doubao._settings.enabled or not self._doubao._settings.api_key:
            return [{"prompt": prompt, "priority": "normal"}]

        plan_prompt = (
            '将以下复杂任务分解为2-5个独立可执行的子任务。\n'
            '返回JSON数组格式: [{"prompt": "子任务描述", "priority": "high|normal|low"}]\n'
            '只返回JSON，不要其他内容。\n\n'
            f'任务: {prompt[:2000]}'
        )

        try:
            client = await self._doubao._get_client()
            resp = await client.post("/chat/completions", json={
                "model": self._doubao._settings.chat_model,
                "messages": [{"role": "user", "content": plan_prompt}],
                "max_tokens": 500,
                "temperature": 0.3,
            })
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            subtasks = json.loads(content.strip())
            if isinstance(subtasks, list) and subtasks:
                return subtasks
        except Exception:
            logger.exception("Failed to decompose task")

        return [{"prompt": prompt, "priority": "normal"}]
