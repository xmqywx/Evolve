"""Supervisor Agent — analyzes survival engine activity and generates briefings."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from myagent.db import Database
from myagent.doubao import DoubaoClient
from myagent.scanner import parse_jsonl_messages

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Daily report prompt (DB-based stats)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Session analysis prompt (JSONL-based deep analysis)
# ---------------------------------------------------------------------------
ANALYZE_PROMPT = """你是一个 AI 监督员，负责深度审查另一个 AI Agent（生存引擎）的实际对话记录。

以下是从它的对话 JSONL 中提取的关键操作摘要（共 {total_actions} 个动作，{total_messages} 条消息）：

{actions_text}

---

请从以下角度进行分析，用中文：

### 1. 执行概览
- 这段时间内 Agent 做了哪些事情？按时间顺序列出主要动作链

### 2. 决策质量
- 每个关键决策是否合理？是否选择了正确的工具和方法？
- 有没有不必要的操作或错误的判断？

### 3. 效率分析
- 是否存在重复操作、无效循环、来回修改？
- 有没有更好的方式完成同样的任务？

### 4. 指令遵循
- Agent 是否按照用户/系统指令行事？
- 有没有偏离任务目标？

### 5. 评分与建议
- 效率评分：1-10 分
- 具体改进建议（1-3 条）

保持犀利直接。"""


# ---------------------------------------------------------------------------
# JSONL extraction: compress conversation into key actions
# ---------------------------------------------------------------------------
def extract_session_actions(session_id: str, projects_dir: str) -> dict:
    """Read a session JSONL and extract key actions (tool_use, decisions, errors).

    Returns a dict with extracted summary text and stats.
    """
    projects_path = Path(projects_dir).expanduser()
    jsonl_path = _find_jsonl(session_id, projects_path)
    if not jsonl_path:
        return {"error": f"JSONL file not found for session {session_id}"}

    text = jsonl_path.read_text(encoding="utf-8", errors="replace")
    messages = parse_jsonl_messages(text.split("\n"))

    if not messages:
        return {"error": "No messages found in session"}

    actions: list[str] = []
    total_tool_uses = 0
    tool_names: dict[str, int] = {}

    for msg in messages:
        role = msg.get("message", {}).get("role", msg.get("type", ""))
        content = msg.get("message", {}).get("content", "")

        if role == "user":
            # Extract user instructions (truncate long ones)
            user_text = _extract_text(content)
            if user_text:
                truncated = user_text[:300] + ("..." if len(user_text) > 300 else "")
                actions.append(f"[用户] {truncated}")

        elif role == "assistant":
            if isinstance(content, list):
                # Extract tool_use and text blocks
                for block in content:
                    if isinstance(block, dict):
                        btype = block.get("type", "")
                        if btype == "tool_use":
                            total_tool_uses += 1
                            name = block.get("name", "unknown")
                            tool_names[name] = tool_names.get(name, 0) + 1
                            inp = block.get("input", {})
                            inp_summary = _summarize_tool_input(name, inp)
                            actions.append(f"[工具] {name}: {inp_summary}")
                        elif btype == "text":
                            text_content = block.get("text", "")
                            if text_content.strip():
                                truncated = text_content.strip()[:200]
                                if len(text_content.strip()) > 200:
                                    truncated += "..."
                                actions.append(f"[AI说] {truncated}")
                        # Skip thinking blocks — internal reasoning
            elif isinstance(content, str) and content.strip():
                truncated = content.strip()[:200]
                if len(content.strip()) > 200:
                    truncated += "..."
                actions.append(f"[AI说] {truncated}")

    # Build summary — limit to ~6000 chars for Doubao context
    actions_text = "\n".join(actions)
    if len(actions_text) > 6000:
        # Keep first 2000 + last 4000 (recent activity matters more)
        actions_text = actions_text[:2000] + "\n\n... (中间省略) ...\n\n" + actions_text[-4000:]

    tool_summary = ", ".join(f"{k}×{v}" for k, v in sorted(tool_names.items(), key=lambda x: -x[1])[:15])

    stats = {
        "total_messages": len(messages),
        "total_actions": len(actions),
        "total_tool_uses": total_tool_uses,
        "tool_summary": tool_summary,
    }

    return {
        "actions_text": actions_text,
        "stats": stats,
    }


def _find_jsonl(session_id: str, projects_dir: Path) -> Path | None:
    """Find a JSONL file by session ID across all project directories."""
    if not projects_dir.exists():
        return None
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        jsonl_path = project_dir / f"{session_id}.jsonl"
        if jsonl_path.exists():
            return jsonl_path
    return None


def find_latest_survival_jsonl(projects_dir: str, workspace: str) -> tuple[str, Path] | None:
    """Find the most recent JSONL file for the survival engine workspace."""
    from myagent.scanner import encode_cwd_to_dirname
    projects_path = Path(projects_dir).expanduser()
    encoded = encode_cwd_to_dirname(workspace)
    project_path = projects_path / encoded
    if not project_path.exists():
        # Try underscore variant (workspace path may use _ instead of -)
        for d in projects_path.iterdir():
            if d.is_dir() and "survival" in d.name.lower():
                project_path = d
                break
        else:
            return None

    jsonl_files = sorted(project_path.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in jsonl_files:
        if len(f.stem) >= 30:
            return f.stem, f
    return None


def _extract_text(content) -> str:
    """Extract plain text from message content (string or content blocks)."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return " ".join(parts).strip()
    return ""


def _summarize_tool_input(tool_name: str, inp: dict) -> str:
    """Create a concise summary of tool input."""
    if not isinstance(inp, dict):
        return str(inp)[:100]

    if tool_name in ("Read", "read"):
        return (inp.get("file_path") or "")[:100]
    if tool_name in ("Edit", "edit"):
        path = inp.get("file_path") or ""
        old = (inp.get("old_string") or "")[:50]
        return f"{path} (修改: {old}...)" if old else path
    if tool_name in ("Write", "write"):
        path = inp.get("file_path") or ""
        size = len(inp.get("content") or "")
        return f"{path} ({size} chars)"
    if tool_name in ("Bash", "bash"):
        cmd = (inp.get("command") or "")[:150]
        return cmd
    if tool_name in ("Glob", "glob"):
        return inp.get("pattern") or ""
    if tool_name in ("Grep", "grep"):
        return f"pattern={inp.get('pattern', '')} path={inp.get('path', '')}"

    # Generic: show first 2 keys
    parts = []
    for k, v in list(inp.items())[:2]:
        val = str(v)[:60]
        parts.append(f"{k}={val}")
    return ", ".join(parts) if parts else "(empty)"


# ---------------------------------------------------------------------------
# Generate report from DB stats (daily auto-report)
# ---------------------------------------------------------------------------
async def generate_report(db: Database, doubao: DoubaoClient) -> dict | None:
    """Generate a supervisor report for today's activity."""
    if not doubao.is_enabled:
        logger.warning("Doubao not enabled, cannot generate supervisor report")
        return None

    activity = await db.get_today_activity()
    today = activity["date"]

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


# ---------------------------------------------------------------------------
# Analyze session JSONL (deep analysis triggered by user)
# ---------------------------------------------------------------------------
async def analyze_session(
    session_id: str,
    projects_dir: str,
    db: Database,
    doubao: DoubaoClient,
) -> dict | None:
    """Analyze a specific session's JSONL conversation log."""
    if not doubao.is_enabled:
        logger.warning("Doubao not enabled, cannot analyze session")
        return None

    logger.info("Extracting actions from session %s", session_id)
    extracted = extract_session_actions(session_id, projects_dir)

    if "error" in extracted:
        logger.error("Extraction failed: %s", extracted["error"])
        return {"error": extracted["error"]}

    stats = extracted["stats"]
    prompt = ANALYZE_PROMPT.format(
        total_actions=stats["total_actions"],
        total_messages=stats["total_messages"],
        actions_text=extracted["actions_text"],
    )

    logger.info(
        "Analyzing session %s: %d messages, %d actions, tools: %s",
        session_id, stats["total_messages"], stats["total_actions"], stats["tool_summary"],
    )
    summary = await doubao.chat(prompt, max_tokens=1500, temperature=0.3)
    if not summary:
        logger.error("Failed to analyze session")
        return None

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_stats = json.dumps({
        "session_id": session_id,
        "total_messages": stats["total_messages"],
        "total_tool_uses": stats["total_tool_uses"],
        "tool_summary": stats["tool_summary"],
        "type": "session_analysis",
    })

    report_id = await db.add_supervisor_report(
        period=f"{today} (会话分析)",
        summary=summary,
        stats=report_stats,
    )

    logger.info("Session analysis report #%d saved", report_id)
    return {"id": report_id, "period": today, "summary": summary, "stats": report_stats}
