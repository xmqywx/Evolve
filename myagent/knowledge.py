"""KnowledgeEngine — ingest, evaluate, deduplicate and inject knowledge into prompts."""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

from myagent.db import Database
from myagent.doubao import DoubaoClient

logger = logging.getLogger(__name__)

EVALUATE_PROMPT = """评估以下经验的复用价值，返回JSON：
{{"refined":"精炼为一句可执行的经验（≤80字）","category":"lesson|discovery|skill|insight","score":1-10,"tags":["标签1","标签2"]}}

评分标准：
- 10: 不遵守就会出事
- 8-9: 重要的通用经验
- 5-7: 有用但有时效性
- 1-4: 一次性信息

原文：{text}"""


class KnowledgeEngine:
    def __init__(self, db: Database, doubao: DoubaoClient):
        self._db = db
        self._doubao = doubao

    # ---- real-time ingestion ----

    async def ingest_from_review(self, learned: list[str], source_id: int):
        """Evaluate each learned item via Doubao, dedup, and store."""
        for text in learned:
            if not text or not text.strip():
                continue
            try:
                if await self._is_duplicate(text):
                    logger.debug("Duplicate knowledge skipped: %s", text[:50])
                    continue
                evaluated = await self._evaluate(text)
                if not evaluated:
                    # Doubao failed, store raw
                    await self._db.add_knowledge(
                        content=text.strip()[:200],
                        category="lesson",
                        source="review",
                        source_id=str(source_id),
                        layer="recent",
                        tags=None,
                        score=5.0,
                        expires_at=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                    )
                    continue
                score = evaluated.get("score", 5)
                layer = "permanent" if score >= 8 else "recent"
                expires = None if layer == "permanent" else (
                    datetime.now(timezone.utc) + timedelta(days=30)
                ).isoformat()
                tags = json.dumps(evaluated.get("tags", []), ensure_ascii=False)
                await self._db.add_knowledge(
                    content=evaluated.get("refined", text.strip()[:200]),
                    category=evaluated.get("category", "lesson"),
                    source="review",
                    source_id=str(source_id),
                    layer=layer,
                    tags=tags,
                    score=float(score),
                    expires_at=expires,
                )
            except Exception:
                logger.exception("Failed to ingest learned item: %s", text[:50])

    async def ingest_from_discovery(self, title, content, category, priority, source_id: int):
        """Store discovery directly as knowledge."""
        try:
            combined = f"{title}: {content}" if content else title
            if await self._is_duplicate(combined):
                return
            score = {"high": 8.0, "medium": 6.0, "low": 4.0}.get(priority, 5.0)
            layer = "permanent" if score >= 8 else "recent"
            expires = None if layer == "permanent" else (
                datetime.now(timezone.utc) + timedelta(days=30)
            ).isoformat()
            await self._db.add_knowledge(
                content=combined[:200],
                category="discovery",
                source="discovery_api",
                source_id=str(source_id),
                layer=layer,
                tags=json.dumps([category], ensure_ascii=False) if category else None,
                score=score,
                expires_at=expires,
            )
        except Exception:
            logger.exception("Failed to ingest discovery: %s", title)

    # ---- scheduled ingestion ----

    async def scan_plans(self, workspace: str):
        """Scan plans/ directory, extract active plan topics as task-layer knowledge."""
        plans_dir = Path(workspace) / "plans"
        if not plans_dir.is_dir():
            return
        # Clear old task-layer knowledge from plan_scan
        existing = await self._db.get_knowledge(layer="task", limit=200)
        for k in existing:
            if k.get("source") == "plan_scan":
                await self._db.update_knowledge(k["id"], retired=1)
        # Scan current plans
        for f in sorted(plans_dir.glob("*.md")):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")[:2000]
                title = f.stem
                # Extract first non-empty line as summary
                summary = ""
                for line in text.split("\n"):
                    line = line.strip().lstrip("#").strip()
                    if line:
                        summary = line[:150]
                        break
                if not summary:
                    summary = title
                await self._db.add_knowledge(
                    content=f"活跃计划: {summary}",
                    category="insight",
                    source="plan_scan",
                    source_id=title,
                    layer="task",
                    tags=json.dumps([title], ensure_ascii=False),
                    score=6.0,
                    expires_at=None,
                )
            except Exception:
                logger.exception("Failed to scan plan: %s", f)

    # ---- evaluation ----

    async def _evaluate(self, text: str) -> dict | None:
        """Call Doubao to evaluate and refine a piece of knowledge."""
        if not self._doubao.is_enabled:
            return None
        try:
            prompt = EVALUATE_PROMPT.format(text=text)
            result = await self._doubao.chat(prompt, max_tokens=300, temperature=0.3)
            if not result:
                return None
            # Try to parse JSON from response
            result = result.strip()
            # Handle markdown code blocks
            if result.startswith("```"):
                lines = result.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                result = "\n".join(lines).strip()
            return json.loads(result)
        except (json.JSONDecodeError, Exception):
            logger.warning("Doubao evaluation failed for: %s", text[:50])
            return None

    async def _is_duplicate(self, content: str) -> bool:
        """Simple substring match dedup against existing knowledge."""
        content_lower = content.strip().lower()[:100]
        if not content_lower:
            return True
        existing = await self._db.get_knowledge(limit=100)
        for k in existing:
            existing_lower = (k.get("content") or "").lower()
            if content_lower in existing_lower or existing_lower in content_lower:
                return True
        return False

    # ---- injection ----

    async def build_knowledge_prompt(self, current_plans: list[str] | None = None) -> dict:
        """Assemble three-layer knowledge text for prompt injection."""
        permanent = await self._db.get_knowledge(layer="permanent", limit=20)
        recent = await self._db.get_knowledge(layer="recent", days=14, limit=15)
        task = await self._db.get_knowledge(layer="task", limit=10)

        # Increment use counts
        for items in [permanent, recent, task]:
            for k in items:
                try:
                    await self._db.increment_use_count(k["id"])
                except Exception:
                    pass

        def fmt_items(items):
            if not items:
                return "（暂无）"
            lines = []
            for k in items:
                score = k.get("score", 0)
                lines.append(f"- [{score:.0f}分] {k['content']}")
            return "\n".join(lines)

        return {
            "permanent": fmt_items(permanent),
            "recent": fmt_items(recent),
            "task": fmt_items(task),
        }

    # ---- maintenance ----

    async def cleanup(self):
        """Retire expired knowledge, auto-archive old plans."""
        count = await self._db.retire_expired_knowledge()
        if count:
            logger.info("Retired %d expired knowledge entries", count)
