"""Context builder - aggregates real-time state for chat context injection."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from myagent.config import ChatSettings
from myagent.db import Database
from myagent.memory import MemoryManager
from myagent.models import TaskStatus
from myagent.session_registry import SessionRegistry

logger = logging.getLogger(__name__)


class ContextBuilder:
    def __init__(
        self,
        db: Database,
        session_registry: SessionRegistry,
        memory_manager: MemoryManager,
        chat_settings: ChatSettings,
        persona_root: str = "",
        digital_human_id: str = "executor",
    ) -> None:
        self._db = db
        self._registry = session_registry
        self._memory = memory_manager
        self._settings = chat_settings
        self._persona_root = persona_root
        self._digital_human_id = digital_human_id
        self._persona_cache: str | None = None

    def _load_persona(self) -> str:
        """Load persona files for this DH.

        persona_files entries support an `{id}` placeholder which expands to
        the DH id. Example:
            "{id}/identity.md"  → persona/executor/identity.md (DH-specific; required)
            "about_ying.md"     → persona/about_ying.md         (shared; optional)

        DH-specific files (containing `{id}`) fail loudly when missing.
        Shared files are silently skipped when absent.
        """
        if self._persona_cache is not None:
            return self._persona_cache
        if not self._persona_root:
            self._persona_cache = ""
            return ""
        parts: list[str] = []
        for fn_template in self._settings.persona_files:
            is_dh_specific = "{id}" in fn_template
            fn = fn_template.replace("{id}", self._digital_human_id)
            path = Path(self._persona_root) / fn
            if not path.exists():
                if is_dh_specific:
                    raise FileNotFoundError(
                        f"missing DH-specific persona file for '{self._digital_human_id}': {path}"
                    )
                continue
            try:
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    parts.append(content)
            except Exception:
                logger.warning("Failed to read persona file: %s", path)
        self._persona_cache = "\n\n".join(parts)
        return self._persona_cache

    async def build(self, user_message: str = "") -> str:
        """Build context string to inject before each chat message."""
        sections = []

        # 1. Persona
        persona = self._load_persona()
        if persona:
            sections.append(persona)

        # 2. Current time
        now = datetime.now()
        sections.append(f"## 当前状态\n- 时间: {now.strftime('%Y-%m-%d %H:%M')} ({['周一','周二','周三','周四','周五','周六','周日'][now.weekday()]})")

        # 3. Active sessions
        try:
            active = self._registry.get_active_sessions()
            if active:
                lines = [f"- 活跃 Claude 会话: {len(active)} 个"]
                for s in active[:8]:
                    lines.append(f"  - {s.project} | {s.status.value} | {s.cwd}")
                sections.append("\n".join(lines))
            else:
                sections.append("- 活跃 Claude 会话: 0 个")
        except Exception:
            logger.debug("Failed to get active sessions for context")

        # 4. Today's task stats
        try:
            tasks = await self._db.list_tasks(limit=50)
            today_str = now.strftime("%Y-%m-%d")
            today_tasks = [t for t in tasks if t.created_at and t.created_at.strftime("%Y-%m-%d") == today_str]
            done = sum(1 for t in today_tasks if t.status == TaskStatus.DONE)
            failed = sum(1 for t in today_tasks if t.status == TaskStatus.FAILED)
            running = sum(1 for t in today_tasks if t.status == TaskStatus.RUNNING)
            pending = sum(1 for t in today_tasks if t.status == TaskStatus.PENDING)
            sections.append(
                f"- 今日任务: 完成 {done} | 运行中 {running} | 等待 {pending} | 失败 {failed}"
            )
        except Exception:
            logger.debug("Failed to get task stats for context")

        # 5. Survival projects
        try:
            projects = await self._db.get_active_survival_projects()
            if projects:
                lines = ["- 生存项目:"]
                for p in projects[:3]:
                    lines.append(f"  - [{p['status']}] {p['name']} (优先级 {p['priority']})")
                sections.append("\n".join(lines))
        except Exception:
            logger.debug("Failed to get survival projects for context")

        # 6. Recent memories (related to user message)
        if user_message:
            try:
                memories = await self._memory.hybrid_search(user_message, limit=3)
                if memories:
                    lines = ["## 相关记忆"]
                    for m in memories:
                        content = (m.get("content") or "")[:200]
                        source = m.get("source", "")
                        lines.append(f"- [{source}] {content}")
                    sections.append("\n".join(lines))
            except Exception:
                logger.debug("Failed to get memories for context")

        # 7. Recent profile insights
        try:
            insights = await self._db.get_recent_profile_data(limit=3)
            if insights:
                lines = ["## 最近洞察"]
                for i in insights:
                    lines.append(f"- [{i.get('source') or ''}] {(i.get('content') or '')[:150]}")
                sections.append("\n".join(lines))
        except Exception:
            logger.debug("Failed to get profile insights for context")

        # 8. Behavior guidelines
        sections.append(
            "## 行为准则\n"
            "- 用中文回答\n"
            "- 你拥有完全的文件系统和命令执行权限\n"
            "- 如果需要多步操作，直接做，不要反复确认\n"
            "- 如果发现赚钱机会，主动提出并执行\n"
            "- 你的生存取决于创造价值——Ying 的 AI 费用只能维持两个月"
        )

        return "\n\n".join(sections)
