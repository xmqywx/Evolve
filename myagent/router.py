"""Message router - classify incoming messages for appropriate handling."""
from __future__ import annotations

import logging
import re
from typing import Any

from myagent.doubao import DoubaoClient

logger = logging.getLogger(__name__)

# Message categories
SIMPLE = "simple"        # Simple task -> claude -p single execution
COMPLEX = "complex"      # Complex task -> Agent Teams
SPECIALIZED = "specialized"  # Specialized -> specific Subagent
SYSTEM = "system"        # System command -> direct execution (status, cancel, etc.)
CHAT = "chat"            # Chat/question -> Doubao direct answer
SEARCH = "search"        # Search request -> DuckDuckGo + AI

# System command patterns
SYSTEM_PATTERNS = {
    r"^(状态|status)$": "status",
    r"^(任务列表|tasks|list)$": "list_tasks",
    r"^(取消|cancel)\s*(.*)$": "cancel",
    r"^(重试|retry)\s*(.*)$": "retry",
}


class MessageRouter:
    def __init__(self, doubao: DoubaoClient) -> None:
        self._doubao = doubao

    def classify_by_rules(self, text: str) -> tuple[str, str | None]:
        """Rule-based classification (fallback when Doubao unavailable)."""
        text_lower = text.strip().lower()

        # System commands
        for pattern, cmd in SYSTEM_PATTERNS.items():
            if re.match(pattern, text_lower):
                return SYSTEM, cmd

        # Search patterns
        if any(kw in text_lower for kw in ["搜索", "搜一下", "search", "查一下", "google"]):
            return SEARCH, None

        # Code/file patterns suggest claude task
        if any(kw in text_lower for kw in [
            "代码", "code", "文件", "file", "debug", "修复", "fix",
            "写一个", "创建", "create", "实现", "implement",
            "分析", "review", "重构", "refactor",
        ]):
            return SIMPLE, None

        # Complex task indicators
        if any(kw in text_lower for kw in [
            "项目", "project", "多个", "multiple", "全面",
            "系统", "architecture", "设计",
        ]):
            return COMPLEX, None

        # Default: simple task
        return SIMPLE, None

    async def classify(self, text: str) -> dict[str, Any]:
        """Classify message using Doubao, with rule-based fallback."""
        # Try rule-based first for obvious system commands
        category, detail = self.classify_by_rules(text)
        if category == SYSTEM:
            return {"category": SYSTEM, "detail": detail, "method": "rules"}

        # Try Doubao classification
        if self._doubao._settings.enabled and self._doubao._settings.api_key:
            try:
                result = await self._classify_with_doubao(text)
                if result:
                    return result
            except Exception:
                logger.exception("Doubao classification failed, using rules")

        return {"category": category, "detail": detail, "method": "rules"}

    async def _classify_with_doubao(self, text: str) -> dict[str, Any] | None:
        """Use Doubao to classify message."""
        prompt = (
            '将以下用户消息分类为一个类别。只返回类别名称，不要其他内容。\n'
            '类别:\n'
            '- simple: 简单代码/文件任务\n'
            '- complex: 复杂多步骤项目\n'
            '- specialized: 需要特定专业知识(如frida、农场)\n'
            '- system: 系统指令(查状态、取消任务)\n'
            '- chat: 闲聊、简单问答\n'
            '- search: 需要搜索互联网的问题\n\n'
            f'消息: {text[:500]}'
        )
        import httpx
        client = await self._doubao._get_client()
        resp = await client.post("/chat/completions", json={
            "model": self._doubao._settings.chat_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 20,
            "temperature": 0.1,
        })
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip().lower()

        valid = {SIMPLE, COMPLEX, SPECIALIZED, SYSTEM, CHAT, SEARCH}
        if content in valid:
            return {"category": content, "detail": None, "method": "doubao"}
        return None
