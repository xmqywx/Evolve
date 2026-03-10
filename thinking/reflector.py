"""Task reflector - evaluate task quality after completion."""
from __future__ import annotations

import json
import logging
from typing import Any

from myagent.doubao import DoubaoClient

logger = logging.getLogger(__name__)


class Reflector:
    def __init__(self, doubao: DoubaoClient) -> None:
        self._doubao = doubao

    async def evaluate(self, prompt: str, result: str | None) -> dict[str, Any]:
        """Evaluate task result quality using Doubao."""
        if not self._doubao._settings.enabled or not self._doubao._settings.api_key:
            return {"quality": "unknown", "needs_review": False, "feedback": ""}

        eval_prompt = (
            '评估以下任务的完成质量。返回JSON:\n'
            '{"quality": "good|fair|poor", "needs_review": true/false, '
            '"feedback": "简短评价", "lessons": ["经验1"]}\n\n'
            f'任务: {prompt[:500]}\n'
            f'结果: {(result or "无结果")[:2000]}'
        )

        try:
            client = await self._doubao._get_client()
            resp = await client.post("/chat/completions", json={
                "model": self._doubao._settings.chat_model,
                "messages": [{"role": "user", "content": eval_prompt}],
                "max_tokens": 300,
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
            logger.exception("Failed to evaluate task")
            return {"quality": "unknown", "needs_review": False, "feedback": ""}
