"""Supervisor Agent — analyzes survival engine activity and generates daily briefings."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from myagent.db import Database
from myagent.doubao import DoubaoClient

logger = logging.getLogger(__name__)

REPORT_PROMPT = """你是一个 AI 监督员，负责审查另一个 AI Agent（生存引擎）今天的工作表现。

以下是它今天的所有活动数据：

## 心跳记录 ({hb_count} 条)
{heartbeats}

## 产出物 ({del_count} 条)
{deliverables}

## 发现 ({disc_count} 条)
{discoveries}

## 工作流执行 ({wf_count} 条)
{workflow_runs}

## 定时任务执行 ({tr_count} 条)
{task_runs}

## 自我总结
{reviews}

---

请生成一份简明的每日简报，用中文，包含以下部分：

1. **一句话总结**：今天这个 Agent 整体表现如何（10-20字）
2. **有价值的工作**：列出今天真正有意义的产出（如果有的话）
3. **浪费时间的行为**：是否有无效循环、重复操作、空转
4. **效率评分**：1-10 分，基于实际产出/工作时长
5. **明日建议**：1-2 条具体可行的方向建议

保持简洁犀利，不要客套。如果 Agent 今天没做什么有价值的事，直接说。"""


async def generate_report(db: Database, doubao: DoubaoClient) -> dict | None:
    """Generate a supervisor report for today's activity."""
    if not doubao.is_enabled:
        logger.warning("Doubao not enabled, cannot generate supervisor report")
        return None

    activity = await db.get_today_activity()
    today = activity["date"]

    # Format activity data for the prompt
    def fmt_list(items: list[dict], fields: list[str], max_items: int = 20) -> str:
        if not items:
            return "无"
        lines = []
        for item in items[:max_items]:
            parts = [str(item.get(f, "")) for f in fields if item.get(f)]
            lines.append("- " + " | ".join(parts))
        return "\n".join(lines)

    heartbeats_text = fmt_list(activity["heartbeats"], ["activity", "description", "created_at"])
    deliverables_text = fmt_list(activity["deliverables"], ["title", "type", "status", "summary"])
    discoveries_text = fmt_list(activity["discoveries"], ["title", "category", "content", "priority"])
    workflow_runs_text = fmt_list(activity["workflow_runs"], ["status", "result_summary", "started_at"])
    task_runs_text = fmt_list(activity["task_runs"], ["status", "output", "error", "started_at"])
    reviews_text = fmt_list(activity["reviews"], ["accomplished", "failed", "learned", "next_priorities"])

    prompt = REPORT_PROMPT.format(
        hb_count=len(activity["heartbeats"]),
        heartbeats=heartbeats_text,
        del_count=len(activity["deliverables"]),
        deliverables=deliverables_text,
        disc_count=len(activity["discoveries"]),
        discoveries=discoveries_text,
        wf_count=len(activity["workflow_runs"]),
        workflow_runs=workflow_runs_text,
        tr_count=len(activity["task_runs"]),
        task_runs=task_runs_text,
        reviews=reviews_text,
    )

    logger.info("Generating supervisor report for %s", today)
    summary = await doubao.chat(prompt, max_tokens=1000, temperature=0.3)
    if not summary:
        logger.error("Failed to generate supervisor report")
        return None

    stats = json.dumps({
        "heartbeats": len(activity["heartbeats"]),
        "deliverables": len(activity["deliverables"]),
        "discoveries": len(activity["discoveries"]),
        "workflow_runs": len(activity["workflow_runs"]),
        "task_runs": len(activity["task_runs"]),
        "reviews": len(activity["reviews"]),
    })

    report_id = await db.add_supervisor_report(
        period=today,
        summary=summary,
        stats=stats,
    )

    logger.info("Supervisor report #%d saved for %s", report_id, today)
    return {"id": report_id, "period": today, "summary": summary, "stats": stats}
