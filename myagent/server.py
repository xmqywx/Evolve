from __future__ import annotations

import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from myagent.auth import create_token, verify_token
from myagent.claude_mem import ClaudeMemBridge
from myagent.config import load_config, AgentConfig
from myagent.context_manager import ContextManager
from myagent.db import Database
from myagent.doubao import DoubaoClient
from myagent.embedding import EmbeddingStore
from myagent.feishu import FeishuClient, build_task_card, build_sessions_card, parse_feishu_event
from myagent.memory import MemoryManager
from myagent.models import Task, TaskSource, TaskStatus, SessionStatus
from myagent.scanner import SessionScanner
from myagent.scheduler import Scheduler
from myagent.session_registry import SessionRegistry
from myagent.router import MessageRouter, SYSTEM, CHAT, SEARCH
from myagent.context_builder import ContextBuilder
from myagent.survival import SurvivalEngine
from myagent.profile_builder import ProfileBuilder
from myagent.ws_client import RelayClient
from myagent.ws_hub import WebSocketHub

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


# ------------------------------------------------------------------
# Tmux session registry helpers (module-level so usable from both
# create_app() endpoints and run_server() startup code)
# ------------------------------------------------------------------

def _register_tmux_session(
    registry: SessionRegistry, tmux_name: str, alias: str, color: str,
) -> None:
    """Register a tmux-managed session in the session registry."""
    from myagent.models import SessionInfo, SessionStatus
    session = SessionInfo(
        id=f"tmux-{tmux_name}",
        pid=None,
        cwd="",
        project=tmux_name,
        started_at=datetime.now(timezone.utc),
        last_active=datetime.now(timezone.utc),
        status=SessionStatus.ACTIVE,
        alias=alias,
        color=color,
    )
    registry.update_session(session)


def _unregister_tmux_session(registry: SessionRegistry, tmux_name: str) -> None:
    """Mark a tmux session as finished in the registry."""
    from myagent.models import SessionStatus
    session = registry.get_session(f"tmux-{tmux_name}")
    if session:
        session.status = SessionStatus.FINISHED
        session.last_active = datetime.now(timezone.utc)
        registry.update_session(session)


# ------------------------------------------------------------------
# Request models
# ------------------------------------------------------------------

class TaskSubmit(BaseModel):
    prompt: str
    cwd: str = "."
    priority: str = "normal"
    source: str = "web"


class LoginRequest(BaseModel):
    secret: str


class SessionRegister(BaseModel):
    session_id: str
    pid: int
    cwd: str


class SessionSendMessage(BaseModel):
    message: str


class SessionMetaUpdate(BaseModel):
    alias: str | None = None
    color: str | None = None
    archived: bool | None = None
    status: str | None = None


class SurvivalProjectCreate(BaseModel):
    name: str
    description: str | None = None
    directory: str | None = None
    priority: int = 5


class SurvivalProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    priority: int | None = None
    notes: str | None = None


# ------------------------------------------------------------------
# Auth dependency (supports both JWT and legacy Bearer secret)
# ------------------------------------------------------------------

async def verify_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    token_str = credentials.credentials
    config = request.app.state.config
    # Try legacy secret first
    if token_str == config.server.secret:
        return
    # Try JWT
    payload = verify_token(token_str, config.jwt.secret)
    if payload is not None:
        return
    raise HTTPException(status_code=401, detail="Unauthorized")


# ------------------------------------------------------------------
# App factory
# ------------------------------------------------------------------

async def create_app(config_path: str) -> FastAPI:
    config = load_config(config_path)
    db = Database(config.agent.db_path)
    await db.init()

    # Crash recovery: reset any RUNNING tasks to PENDING
    running_tasks = await db.list_tasks(status=TaskStatus.RUNNING)
    for t in running_tasks:
        logger.info("Recovering stuck task: %s", t.id)
        await db.update_task(t.id, status=TaskStatus.PENDING)

    # Doubao + pgvector + claude-mem bridge + memory
    doubao_client = DoubaoClient(config.doubao)
    embedding_store = EmbeddingStore(config.postgres)
    await embedding_store.init()

    claude_mem_bridge = None
    if config.claude_mem.enabled:
        claude_mem_bridge = ClaudeMemBridge(config.claude_mem.db_path)
        if claude_mem_bridge.available:
            logger.info("claude-mem bridge connected: %s", config.claude_mem.db_path)
        else:
            logger.warning("claude-mem database not found: %s", config.claude_mem.db_path)

    memory_manager = MemoryManager(db, doubao_client, embedding_store, claude_mem=claude_mem_bridge)

    # Feishu client
    feishu_client = FeishuClient(config.feishu)

    # Session registry + hub
    session_registry = SessionRegistry(max_messages=config.scanner.max_messages_cached)
    ws_hub = WebSocketHub()

    # Wire registry changes to WebSocket hub
    def on_registry_change(event_type: str, session_id: str, data):
        async def _push():
            if event_type in ("session_new", "session_updated"):
                session = session_registry.get_session(session_id)
                if session:
                    await ws_hub.broadcast("sessions", {
                        "type": event_type,
                        "session": session.model_dump(mode="json"),
                    })
            elif event_type == "new_messages":
                await ws_hub.broadcast(f"session:{session_id}", {
                    "type": "new_messages",
                    "session_id": session_id,
                    "messages": data if isinstance(data, list) else [],
                })
        task = asyncio.create_task(_push())
        task.add_done_callback(lambda t: logger.error("Push error: %s", t.exception()) if not t.cancelled() and t.exception() else None)

    session_registry.add_listener(on_registry_change)

    # Scanner
    async def on_scan_change(sessions, new_messages):
        for s in sessions:
            # Preserve alias/color/archived from existing session
            existing = session_registry.get_session(s.id)
            if existing:
                s.alias = existing.alias
                s.color = existing.color
                s.archived = existing.archived
            else:
                # Check DB for previously archived sessions
                db_session = await db.get_session(s.id)
                if db_session:
                    s.alias = db_session.alias
                    s.color = db_session.color
                    s.archived = db_session.archived
            # Skip pushing updates for archived sessions
            if s.archived:
                await db.upsert_session(s)
                continue
            msgs = new_messages.get(s.id)
            session_registry.update_session(s, msgs)
            await db.upsert_session(s)

    scanner = SessionScanner(config.scanner, on_change=on_scan_change)

    # Notification callback
    async def on_task_done(task_id: str, status: str, summary: str | None) -> None:
        task = await db.get_task(task_id)
        if task is None:
            return
        duration = None
        if task.started_at and task.finished_at:
            duration = (task.finished_at - task.started_at).total_seconds()
        card = build_task_card(
            task_id=task_id,
            prompt=task.prompt,
            status=status,
            summary=summary,
            duration_seconds=duration,
        )
        await feishu_client.send_card(card)

        try:
            await memory_manager.summarize_task(task_id)
        except Exception:
            logger.exception("Failed to summarize task %s", task_id)

    # Context manager
    context_manager = ContextManager(
        persona_dir=config.agent.persona_dir,
    ) if config.agent.persona_dir else None

    scheduler = Scheduler(
        db, config.claude, config.scheduler,
        on_task_done=on_task_done,
        context_manager=context_manager,
        memory_manager=memory_manager,
        doubao_client=doubao_client,
    )

    # Proactive thinking
    proactive_thinking = None
    try:
        from thinking.proactive import ProactiveThinking
        proactive_thinking = ProactiveThinking(db, doubao_client, feishu_client, memory_manager)
        logger.info("Proactive thinking system initialized")
    except ImportError:
        logger.warning("Thinking modules not available, proactive thinking disabled")

    # Context builder (used by other features)
    context_builder = ContextBuilder(
        db=db,
        session_registry=session_registry,
        memory_manager=memory_manager,
        chat_settings=config.chat,
        persona_dir=config.agent.persona_dir,
    )

    # Survival engine - with real-time log broadcasting
    async def _broadcast_survival_log(cycle_id: str, step: str, content: str):
        await ws_hub.broadcast("survival", {
            "type": "survival_log",
            "cycle_id": cycle_id,
            "step": step,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

    survival_engine = SurvivalEngine(
        db=db,
        claude_settings=config.claude,
        feishu=feishu_client,
        settings=config.survival,
        on_log=_broadcast_survival_log,
    )

    # Profile builder
    profile_builder = ProfileBuilder(
        db=db,
        doubao=doubao_client,
        settings=config.profile,
    )

    # Message router
    message_router = MessageRouter(doubao_client)

    # Relay client (WebSocket to wdao.chat)
    async def on_relay_message(msg: dict) -> None:
        parsed = parse_feishu_event(msg)
        if parsed is None:
            return

        content = parsed["content"]
        chat_id = parsed.get("chat_id", "")

        classification = await message_router.classify(content)
        category = classification["category"]

        if category == SYSTEM:
            detail = classification.get("detail", "")
            reply = await _handle_system_command(detail, db, scheduler, session_registry)
            if chat_id:
                await feishu_client.send_message_to_chat(chat_id, reply)
            return

        if category == CHAT:
            reply = await doubao_client.chat(
                f"你是 MyYing，Ying 的 AI 分身助手。简洁友好地回复：\n\n{content}",
                max_tokens=500,
                temperature=0.7,
            )
            if reply and chat_id:
                await feishu_client.send_message_to_chat(chat_id, reply)
            elif not reply and chat_id:
                await feishu_client.send_message_to_chat(chat_id, "收到，但我暂时无法回复（豆包未启用）")
            return

        if category == SEARCH:
            if chat_id:
                await feishu_client.send_message_to_chat(chat_id, f"收到，正在处理：{content[:50]}...")

        task = Task(
            prompt=content,
            source=TaskSource.FEISHU,
            complexity=category,
        )
        await db.create_task(task)
        logger.info("Task created from Feishu: %s (category=%s)", task.id, category)

        if chat_id and category != SEARCH:
            await feishu_client.send_message_to_chat(
                chat_id, f"任务已创建，排队执行中...\nID: {task.id[:20]}"
            )

    async def _handle_system_command(detail, db, scheduler, registry) -> str:
        if detail == "status":
            remaining = scheduler._rate_limiter.remaining
            running = scheduler._running
            active_sessions = len(registry.get_active_sessions())
            return (
                f"运行状态: {'运行中' if running else '已停止'}\n"
                f"今日剩余额度: {remaining}\n"
                f"活跃会话: {active_sessions}"
            )
        elif detail == "list_tasks":
            tasks = await db.list_tasks(limit=5)
            if not tasks:
                return "暂无任务"
            lines = []
            status_map = {"done": "完成", "failed": "失败", "running": "执行中", "pending": "等待中"}
            for t in tasks:
                s = status_map.get(t.status.value, t.status.value)
                lines.append(f"[{s}] {t.prompt[:40]}")
            return "最近任务:\n" + "\n".join(lines)
        elif detail == "sessions":
            sessions = registry.get_active_sessions()
            if not sessions:
                return "当前没有活跃的 Claude 会话"
            lines = []
            for s in sessions:
                lines.append(f"[Running] {s.project} | {s.cwd}")
            return f"活跃会话 ({len(sessions)}):\n" + "\n".join(lines)
        elif detail == "session_detail":
            sessions = registry.get_active_sessions()
            if not sessions:
                return "当前没有活跃的 Claude 会话"
            # Return first active session's recent messages
            s = sessions[0]
            msgs = registry.get_messages(s.id)
            recent = msgs[-3:] if len(msgs) > 3 else msgs
            lines = [f"会话: {s.project} ({s.cwd})"]
            for m in recent:
                role = m.get("type", "?")
                content = ""
                msg_data = m.get("message", {})
                if isinstance(msg_data, dict):
                    c = msg_data.get("content", "")
                    if isinstance(c, str):
                        content = c[:100]
                    elif isinstance(c, list):
                        for block in c:
                            if isinstance(block, dict) and block.get("type") == "text":
                                content = block.get("text", "")[:100]
                                break
                lines.append(f"[{role}] {content}")
            return "\n".join(lines)
        else:
            return f"未知命令: {detail}"

    relay_client = RelayClient(config.relay, on_message=on_relay_message)

    app = FastAPI(title=config.agent.name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.config = config
    app.state.db = db
    app.state.scheduler = scheduler
    app.state.feishu_client = feishu_client
    app.state.relay_client = relay_client
    app.state.doubao_client = doubao_client
    app.state.embedding_store = embedding_store
    app.state.memory_manager = memory_manager
    app.state.context_manager = context_manager
    app.state.message_router = message_router
    app.state.session_registry = session_registry
    app.state.ws_hub = ws_hub
    app.state.scanner = scanner
    app.state.claude_mem_bridge = claude_mem_bridge
    app.state.proactive_thinking = proactive_thinking
    app.state.context_builder = context_builder
    app.state.survival_engine = survival_engine
    app.state.profile_builder = profile_builder

    # ------------------------------------------------------------------
    # Public routes
    # ------------------------------------------------------------------

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "name": config.agent.name,
            "scheduler_remaining": scheduler._rate_limiter.remaining,
            "feishu_enabled": config.feishu.enabled,
            "relay_enabled": config.relay.enabled,
            "doubao_enabled": config.doubao.enabled,
            "pgvector_enabled": config.postgres.enabled,
            "claude_mem_available": claude_mem_bridge.available if claude_mem_bridge else False,
            "active_sessions": len(session_registry.get_active_sessions()),
        }

    @app.post("/api/login")
    async def login(body: LoginRequest):
        if body.secret != config.server.secret:
            raise HTTPException(status_code=401, detail="Invalid secret")
        token = create_token(config.jwt.secret, config.jwt.expiry_hours)
        return {"token": token}

    # ------------------------------------------------------------------
    # Protected routes
    # ------------------------------------------------------------------

    @app.post("/api/tasks", status_code=201, dependencies=[Depends(verify_auth)])
    async def submit_task(body: TaskSubmit):
        try:
            source = TaskSource(body.source)
        except ValueError:
            source = TaskSource.WEB

        classification = await message_router.classify(body.prompt)
        complexity = classification["category"]

        task = Task(
            prompt=body.prompt,
            cwd=body.cwd,
            priority=body.priority,
            source=source,
            complexity=complexity,
        )
        await db.create_task(task)
        return task.model_dump(mode="json")

    @app.get("/api/tasks", dependencies=[Depends(verify_auth)])
    async def list_tasks(
        status: str | None = Query(None),
        limit: int = Query(50),
    ):
        task_status = None
        if status is not None:
            try:
                task_status = TaskStatus(status)
            except ValueError:
                pass
        tasks = await db.list_tasks(limit=limit, status=task_status)
        return [t.model_dump(mode="json") for t in tasks]

    @app.get("/api/tasks/{task_id}", dependencies=[Depends(verify_auth)])
    async def get_task(task_id: str):
        task = await db.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task.model_dump(mode="json")

    @app.post("/api/tasks/{task_id}/cancel", dependencies=[Depends(verify_auth)])
    async def cancel_task(task_id: str):
        success = await scheduler.cancel_task(task_id)
        if not success:
            raise HTTPException(status_code=400, detail="Cannot cancel task")
        return {"status": "cancelled"}

    @app.get("/api/tasks/{task_id}/logs", dependencies=[Depends(verify_auth)])
    async def get_task_logs(task_id: str):
        task = await db.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        logs = await db.get_task_logs(task_id)
        return logs

    @app.get("/api/memory/search", dependencies=[Depends(verify_auth)])
    async def search_memories(
        q: str = Query(...),
        limit: int = Query(10),
        source: str | None = Query(None),
        project: str | None = Query(None),
    ):
        results = await memory_manager.hybrid_search(q, limit=limit, project=project)
        if source:
            results = [r for r in results if r.get("source") == source]
        return results

    @app.get("/api/memory/context", dependencies=[Depends(verify_auth)])
    async def get_memory_context(q: str = Query(...), limit: int = Query(5)):
        context = await memory_manager.get_context_for_task(q, limit=limit)
        return {"context": context}

    @app.get("/api/memory/stats", dependencies=[Depends(verify_auth)])
    async def get_memory_stats():
        """Get combined memory statistics from both sources."""
        stats = {
            "myagent": {
                "memories": await db.count_memories(),
                "tasks": await db.count_tasks(),
            },
            "claude_mem": {},
        }

        if claude_mem_bridge and claude_mem_bridge.available:
            stats["claude_mem"] = claude_mem_bridge.get_stats()

        return stats

    @app.get("/api/memory/observations", dependencies=[Depends(verify_auth)])
    async def get_observations(
        limit: int = Query(50),
        obs_type: str | None = Query(None),
        project: str | None = Query(None),
    ):
        """Get recent observations from claude-mem."""
        if not claude_mem_bridge or not claude_mem_bridge.available:
            return []
        return claude_mem_bridge.get_recent_observations(
            limit=limit, obs_type=obs_type, project=project,
        )

    @app.get("/api/memory/timeline", dependencies=[Depends(verify_auth)])
    async def get_timeline(
        limit: int = Query(30),
        project: str | None = Query(None),
    ):
        """Get session summaries timeline from claude-mem."""
        if not claude_mem_bridge or not claude_mem_bridge.available:
            return []
        return claude_mem_bridge.get_timeline(limit=limit, project=project)

    @app.get("/api/memory/projects", dependencies=[Depends(verify_auth)])
    async def get_memory_projects():
        """Get distinct project names from claude-mem."""
        if not claude_mem_bridge or not claude_mem_bridge.available:
            return []
        return claude_mem_bridge.get_projects()

    # ------------------------------------------------------------------
    # Agent Self-Report API (Phase 3)
    # ------------------------------------------------------------------

    class HeartbeatRequest(BaseModel):
        activity: str
        description: str | None = None
        task_ref: str | None = None
        progress_pct: int | None = None
        eta_minutes: int | None = None

    @app.post("/api/agent/heartbeat", dependencies=[Depends(verify_auth)])
    async def agent_heartbeat(req: HeartbeatRequest):
        hb_id = await db.add_heartbeat(
            activity=req.activity, description=req.description,
            task_ref=req.task_ref, progress_pct=req.progress_pct,
            eta_minutes=req.eta_minutes,
        )
        return {"status": "ok", "id": hb_id}

    @app.get("/api/agent/heartbeat", dependencies=[Depends(verify_auth)])
    async def get_heartbeat(latest: bool = Query(False), limit: int = Query(50)):
        if latest:
            hb = await db.get_latest_heartbeat()
            return hb or {}
        return await db.list_heartbeats(limit=limit)

    class DeliverableRequest(BaseModel):
        title: str
        type: str = "code"
        status: str = "draft"
        path: str | None = None
        summary: str | None = None
        repo: str | None = None
        value_estimate: str | None = None

    @app.post("/api/agent/deliverable", dependencies=[Depends(verify_auth)])
    async def agent_deliverable(req: DeliverableRequest):
        d_id = await db.add_deliverable(
            title=req.title, type=req.type, status=req.status,
            path=req.path, summary=req.summary, repo=req.repo,
            value_estimate=req.value_estimate,
        )
        return {"status": "ok", "id": d_id}

    @app.get("/api/agent/deliverables", dependencies=[Depends(verify_auth)])
    async def list_deliverables(
        type: str | None = Query(None), status: str | None = Query(None),
        limit: int = Query(50),
    ):
        return await db.list_deliverables(type=type, status=status, limit=limit)

    class DeliverableUpdateRequest(BaseModel):
        status: str | None = None
        title: str | None = None
        summary: str | None = None

    @app.patch("/api/agent/deliverables/{deliverable_id}", dependencies=[Depends(verify_auth)])
    async def update_deliverable(deliverable_id: int, req: DeliverableUpdateRequest):
        fields = {k: v for k, v in req.model_dump().items() if v is not None}
        ok = await db.update_deliverable(deliverable_id, **fields)
        if not ok:
            raise HTTPException(status_code=404, detail="Deliverable not found")
        return {"status": "ok"}

    class DiscoveryRequest(BaseModel):
        title: str
        category: str = "insight"
        content: str | None = None
        actionable: bool = False
        priority: str = "medium"

    @app.post("/api/agent/discovery", dependencies=[Depends(verify_auth)])
    async def agent_discovery(req: DiscoveryRequest):
        d_id = await db.add_discovery(
            title=req.title, category=req.category, content=req.content,
            actionable=req.actionable, priority=req.priority,
        )
        return {"status": "ok", "id": d_id}

    @app.get("/api/agent/discoveries", dependencies=[Depends(verify_auth)])
    async def list_discoveries(
        category: str | None = Query(None), priority: str | None = Query(None),
        limit: int = Query(50),
    ):
        return await db.list_discoveries(category=category, priority=priority, limit=limit)

    class WorkflowRequest(BaseModel):
        name: str
        trigger: str = "manual"
        steps: list[dict] | None = None
        enabled: bool = False

    @app.post("/api/agent/workflow", dependencies=[Depends(verify_auth)])
    async def agent_workflow(req: WorkflowRequest):
        import json
        steps_json = json.dumps(req.steps) if req.steps else None
        w_id = await db.add_workflow(
            name=req.name, trigger=req.trigger,
            steps=steps_json, enabled=req.enabled,
        )
        return {"status": "ok", "id": w_id}

    @app.get("/api/agent/workflows", dependencies=[Depends(verify_auth)])
    async def list_workflows(limit: int = Query(50)):
        return await db.list_workflows(limit=limit)

    @app.patch("/api/agent/workflows/{workflow_id}", dependencies=[Depends(verify_auth)])
    async def update_workflow(workflow_id: int, req: dict):
        ok = await db.update_workflow(workflow_id, **req)
        if not ok:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return {"status": "ok"}

    class UpgradeRequest(BaseModel):
        proposal: str
        reason: str | None = None
        risk: str = "low"
        impact: str | None = None

    @app.post("/api/agent/upgrade", dependencies=[Depends(verify_auth)])
    async def agent_upgrade(req: UpgradeRequest):
        u_id = await db.add_upgrade(
            proposal=req.proposal, reason=req.reason,
            risk=req.risk, impact=req.impact,
        )
        return {"status": "ok", "id": u_id}

    @app.get("/api/agent/upgrades", dependencies=[Depends(verify_auth)])
    async def list_upgrades(status: str | None = Query(None), limit: int = Query(50)):
        return await db.list_upgrades(status=status, limit=limit)

    @app.patch("/api/agent/upgrades/{upgrade_id}", dependencies=[Depends(verify_auth)])
    async def update_upgrade_status(upgrade_id: int, req: dict):
        status_val = req.get("status")
        if status_val not in ("approved", "rejected", "pending"):
            raise HTTPException(status_code=400, detail="Invalid status")
        ok = await db.update_upgrade(upgrade_id, status_val)
        if not ok:
            raise HTTPException(status_code=404, detail="Upgrade not found")
        return {"status": "ok"}

    class ReviewRequest(BaseModel):
        period: str
        accomplished: list[str] | None = None
        failed: list[str] | None = None
        learned: list[str] | None = None
        next_priorities: list[str] | None = None
        tokens_used: int | None = None
        cost_estimate: str | None = None

    @app.post("/api/agent/review", dependencies=[Depends(verify_auth)])
    async def agent_review(req: ReviewRequest):
        import json
        r_id = await db.add_review(
            period=req.period,
            accomplished=json.dumps(req.accomplished) if req.accomplished else None,
            failed=json.dumps(req.failed) if req.failed else None,
            learned=json.dumps(req.learned) if req.learned else None,
            next_priorities=json.dumps(req.next_priorities) if req.next_priorities else None,
            tokens_used=req.tokens_used,
            cost_estimate=req.cost_estimate,
        )
        return {"status": "ok", "id": r_id}

    @app.get("/api/agent/reviews", dependencies=[Depends(verify_auth)])
    async def list_reviews(limit: int = Query(20)):
        return await db.list_reviews(limit=limit)

    @app.get("/api/agent/stats", dependencies=[Depends(verify_auth)])
    async def get_agent_stats():
        return await db.get_agent_stats()

    # ------------------------------------------------------------------
    # Thinking
    # ------------------------------------------------------------------

    @app.post("/api/thinking/review", dependencies=[Depends(verify_auth)])
    async def trigger_daily_review():
        """Manually trigger a daily review."""
        if not proactive_thinking:
            raise HTTPException(status_code=503, detail="Thinking system not available")
        insight = await proactive_thinking.daily_review()
        if insight is None:
            return {"status": "skipped", "insight": None}
        return {"status": "ok", "insight": insight}

    @app.get("/api/status", dependencies=[Depends(verify_auth)])
    async def get_status():
        return {
            "scheduler_remaining": scheduler._rate_limiter.remaining,
            "scheduler_running": scheduler._running,
            "active_sessions": len(session_registry.get_active_sessions()),
        }

    # ------------------------------------------------------------------
    # Chat API (tmux-based)
    # ------------------------------------------------------------------

    CHAT_TMUX_SESSION = "chat"

    async def _chat_tmux_exists() -> bool:
        proc = await asyncio.create_subprocess_shell(
            f"tmux has-session -t {CHAT_TMUX_SESSION} 2>/dev/null",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return (proc.returncode or 0) == 0

    async def _chat_run_cmd(cmd: str) -> tuple[int, str]:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0 and stderr:
            output += "\n" + stderr.decode("utf-8", errors="replace").strip()
        return proc.returncode or 0, output

    @app.post("/api/chat/start", dependencies=[Depends(verify_auth)])
    async def start_chat():
        if not shutil.which("tmux"):
            return {"status": "error", "error": "tmux not installed"}
        if await _chat_tmux_exists():
            return {"status": "already_running"}

        code, output = await _chat_run_cmd(
            f"tmux new-session -d -s {CHAT_TMUX_SESSION}"
        )
        if code == 0:
            # Force tmux to resize to the largest client
            await _chat_run_cmd(f"tmux set-option -t {CHAT_TMUX_SESSION} window-size largest")
            await _chat_run_cmd(f"tmux set-option -t {CHAT_TMUX_SESSION} aggressive-resize on")
        if code != 0:
            return {"status": "error", "error": output}

        # Unset CLAUDECODE to avoid "nested session" error, then launch claude
        await _chat_run_cmd(
            f'tmux send-keys -t {CHAT_TMUX_SESSION} "unset CLAUDECODE" Enter'
        )
        claude_cmd = f"{config.claude.binary} --dangerously-skip-permissions"
        await _chat_run_cmd(
            f'tmux send-keys -t {CHAT_TMUX_SESSION} "{claude_cmd}" Enter'
        )

        # Register in session registry with alias and color
        _register_tmux_session(
            session_registry, CHAT_TMUX_SESSION, "AI 对话", "#1677ff",
        )
        return {"status": "started"}

    @app.post("/api/chat/stop", dependencies=[Depends(verify_auth)])
    async def stop_chat():
        if not await _chat_tmux_exists():
            return {"status": "not_running"}
        code, output = await _chat_run_cmd(f"tmux kill-session -t {CHAT_TMUX_SESSION}")
        _unregister_tmux_session(session_registry, CHAT_TMUX_SESSION)
        return {"status": "stopped" if code == 0 else "error", "output": output}

    @app.get("/api/chat/status", dependencies=[Depends(verify_auth)])
    async def get_chat_status():
        exists = await _chat_tmux_exists()
        pid = None
        cmd = ""
        if exists:
            code, out = await _chat_run_cmd(
                f"tmux list-panes -t {CHAT_TMUX_SESSION} -F '#{{pane_pid}}' 2>/dev/null"
            )
            if code == 0 and out.strip().isdigit():
                pid = int(out.strip())
            _, cmd = await _chat_run_cmd(
                f"tmux list-panes -t {CHAT_TMUX_SESSION} -F '#{{pane_current_command}}' 2>/dev/null"
            )
            cmd = cmd.strip()
        return {
            "running": exists,
            "pid": pid,
            "current_command": cmd,
            "session_name": CHAT_TMUX_SESSION,
            "claude_session_id": None,
        }

    @app.post("/api/chat/send", dependencies=[Depends(verify_auth)])
    async def send_chat_message(body: dict):
        if not await _chat_tmux_exists():
            return {"status": "not_running"}
        msg = body.get("message", "")
        if not msg:
            return {"status": "error", "error": "message is empty"}
        # Write to temp file, use tmux load-buffer + paste-buffer for reliable input
        tmp_file = Path("/tmp/.chat_tmp_message")
        try:
            tmp_file.write_text(msg, encoding="utf-8")
            await _chat_run_cmd(f"tmux load-buffer -t {CHAT_TMUX_SESSION} {tmp_file}")
            await _chat_run_cmd(f"tmux paste-buffer -t {CHAT_TMUX_SESSION}")
            await _chat_run_cmd(f"tmux send-keys -t {CHAT_TMUX_SESSION} Enter")
        finally:
            tmp_file.unlink(missing_ok=True)
        return {"status": "sent"}

    @app.post("/api/chat/interrupt", dependencies=[Depends(verify_auth)])
    async def interrupt_chat():
        if not await _chat_tmux_exists():
            return {"status": "not_running"}
        await _chat_run_cmd(f"tmux send-keys -t {CHAT_TMUX_SESSION} C-c")
        return {"status": "interrupted"}

    # ------------------------------------------------------------------
    # Survival API
    # ------------------------------------------------------------------

    @app.get("/api/survival/projects", dependencies=[Depends(verify_auth)])
    async def list_survival_projects(status: str | None = Query(None)):
        return await db.list_survival_projects(status=status)

    @app.post("/api/survival/projects", status_code=201, dependencies=[Depends(verify_auth)])
    async def create_survival_project(body: SurvivalProjectCreate):
        pid = await db.create_survival_project(
            name=body.name, description=body.description,
            directory=body.directory, priority=body.priority,
        )
        return {"id": pid, "status": "created"}

    @app.patch("/api/survival/projects/{project_id}", dependencies=[Depends(verify_auth)])
    async def update_survival_project(project_id: int, body: SurvivalProjectUpdate):
        raw = body.model_dump(exclude_unset=True)
        if not raw:
            raise HTTPException(status_code=400, detail="No fields to update")
        await db.update_survival_project(project_id, **raw)
        return {"status": "updated"}

    @app.post("/api/survival/start", dependencies=[Depends(verify_auth)])
    async def start_survival():
        result = await survival_engine.start()
        # Start watchdog if not already running
        if result.get("status") in ("started", "already_running") and not survival_engine._running:
            asyncio.create_task(survival_engine.run_watchdog())
        if result.get("status") in ("started", "already_running"):
            _register_tmux_session(session_registry, "survival", "生存引擎", "#ff4d4f")
        return result

    @app.post("/api/survival/stop", dependencies=[Depends(verify_auth)])
    async def stop_survival():
        survival_engine.stop_watchdog()
        result = await survival_engine.stop()
        _unregister_tmux_session(session_registry, "survival")
        return result

    @app.post("/api/survival/interrupt", dependencies=[Depends(verify_auth)])
    async def interrupt_survival():
        return await survival_engine.interrupt()

    @app.post("/api/survival/watchdog", dependencies=[Depends(verify_auth)])
    async def toggle_watchdog(body: dict):
        enabled = body.get("enabled", False)
        if enabled and not survival_engine._running:
            asyncio.create_task(survival_engine.run_watchdog())
            return {"status": "started"}
        elif not enabled and survival_engine._running:
            survival_engine.stop_watchdog()
            return {"status": "stopped"}
        return {"status": "no_change", "watchdog_active": survival_engine._running}

    @app.post("/api/survival/send", dependencies=[Depends(verify_auth)])
    async def send_survival_message(body: dict):
        msg = body.get("message", "")
        if not msg:
            return {"status": "error", "error": "empty message"}
        return await survival_engine.send_message(msg)

    @app.get("/api/survival/status", dependencies=[Depends(verify_auth)])
    async def survival_status():
        return await survival_engine.get_status()

    @app.post("/api/survival/discover-session", dependencies=[Depends(verify_auth)])
    async def discover_survival_session():
        """Try to link survival tmux process to a scanner session."""
        sessions = await db.list_sessions()
        sid = await survival_engine.discover_session_id(sessions)
        return {"session_id": sid}

    @app.get("/api/survival/logs", dependencies=[Depends(verify_auth)])
    async def get_survival_logs(cycle_id: str | None = Query(None), limit: int = Query(100)):
        return await db.get_survival_logs(cycle_id=cycle_id, limit=limit)

    @app.get("/api/survival/cycles", dependencies=[Depends(verify_auth)])
    async def list_survival_cycles(limit: int = Query(20)):
        return await db.list_survival_cycles(limit=limit)

    # ------------------------------------------------------------------
    # Profile API
    # ------------------------------------------------------------------

    @app.get("/api/profile/insights", dependencies=[Depends(verify_auth)])
    async def get_profile_insights(source: str | None = Query(None), limit: int = Query(20)):
        return await db.get_recent_profile_data(source=source, limit=limit)

    @app.post("/api/profile/scan", dependencies=[Depends(verify_auth)])
    async def trigger_profile_scan():
        results = await profile_builder.scan_all()
        return results

    @app.get("/api/profile/sources", dependencies=[Depends(verify_auth)])
    async def get_profile_sources():
        return {
            "git_scan_enabled": config.profile.git_scan_enabled,
            "terminal_history_enabled": config.profile.terminal_history_enabled,
            "browser_history_enabled": config.profile.browser_history_enabled,
            "slack_enabled": config.profile.slack_enabled,
            "wechat_enabled": config.profile.wechat_enabled,
            "scan_interval_hours": config.profile.scan_interval_hours,
        }

    # ------------------------------------------------------------------
    # Session API
    # ------------------------------------------------------------------

    @app.get("/api/sessions", dependencies=[Depends(verify_auth)])
    async def list_sessions(
        status: str | None = Query(None),
        include_archived: bool = Query(False),
    ):
        sessions = session_registry.get_all_sessions()
        if status:
            try:
                s = SessionStatus(status)
                sessions = [x for x in sessions if x.status == s]
            except ValueError:
                pass
        if not include_archived:
            sessions = [x for x in sessions if not x.archived]
        # Sort: active first, then by last_active desc
        sessions.sort(key=lambda x: (0 if x.status == SessionStatus.ACTIVE else 1, -x.last_active.timestamp()))
        return [s.model_dump(mode="json") for s in sessions]

    @app.get("/api/sessions/archived", dependencies=[Depends(verify_auth)])
    async def list_archived_sessions():
        sessions = session_registry.get_all_sessions()
        archived = [x for x in sessions if x.archived]
        archived.sort(key=lambda x: -x.last_active.timestamp())
        return [s.model_dump(mode="json") for s in archived]

    @app.patch("/api/sessions/{session_id}", dependencies=[Depends(verify_auth)])
    async def update_session_meta(session_id: str, body: SessionMetaUpdate):
        session = session_registry.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        raw = body.model_dump(exclude_unset=True)
        if not raw:
            raise HTTPException(status_code=400, detail="No fields to update")
        # Treat empty strings as None (clear)
        updates = {k: (None if v == "" else v) for k, v in raw.items()}
        # Handle status separately (convert string to enum)
        if "status" in updates and updates["status"]:
            try:
                updates["status"] = SessionStatus(updates["status"]).value
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {updates['status']}")
        # Update DB
        await db.update_session_meta(session_id, **updates)
        # Update in-memory registry
        for k, v in updates.items():
            if k == "status" and v:
                session.status = SessionStatus(v)
            else:
                setattr(session, k, v)
        session_registry.update_session(session)
        return session.model_dump(mode="json")

    @app.get("/api/sessions/{session_id}", dependencies=[Depends(verify_auth)])
    async def get_session(session_id: str):
        session = session_registry.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        # Read full messages from JSONL file (not cached 200)
        messages = []
        if not session_id.startswith("proc-"):
            from myagent.scanner import encode_cwd_to_dirname, parse_jsonl_messages
            projects_dir = Path(os.path.expanduser(config.scanner.claude_projects_dir))
            # Find the JSONL file
            for project_dir in projects_dir.iterdir():
                if not project_dir.is_dir():
                    continue
                jsonl_path = project_dir / f"{session_id}.jsonl"
                if jsonl_path.exists():
                    try:
                        text = jsonl_path.read_text(encoding="utf-8")
                        messages = parse_jsonl_messages(text.split("\n"))
                    except Exception:
                        logger.exception("Failed to read JSONL for session %s", session_id)
                    break
        if not messages:
            messages = session_registry.get_messages(session_id)
        return {
            "session": session.model_dump(mode="json"),
            "messages": messages,
            "total": len(messages),
        }

    @app.post("/api/sessions/{session_id}/stop", dependencies=[Depends(verify_auth)])
    async def stop_session(session_id: str):
        """Send SIGINT to a Claude session's process (like Ctrl+C)."""
        import signal
        session = session_registry.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if not session.pid:
            raise HTTPException(status_code=400, detail="Session has no PID")
        try:
            os.kill(session.pid, signal.SIGINT)
            return {"status": "ok", "message": f"SIGINT sent to PID {session.pid}"}
        except ProcessLookupError:
            return {"status": "error", "message": f"Process {session.pid} not found"}
        except PermissionError:
            raise HTTPException(status_code=403, detail=f"No permission to signal PID {session.pid}")

    # Track background resume processes
    _resume_procs: dict[str, asyncio.subprocess.Process] = {}

    async def _run_claude_resume(session_id: str, msg: str, cwd: str, image_paths: list[str] | None = None):
        """Run claude --resume in background. Returns immediately.
        Response comes through JSONL tail watcher."""
        cmd = [
            config.claude.binary,
            "--resume", session_id,
            "-p", msg,
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ]
        if image_paths:
            for img_path in image_paths:
                cmd.extend(["--file", img_path])
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        try:
            # Kill any existing resume process for this session
            old_proc = _resume_procs.pop(session_id, None)
            if old_proc and old_proc.returncode is None:
                try:
                    old_proc.kill()
                except ProcessLookupError:
                    pass

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            _resume_procs[session_id] = proc

            # Try to get a quick response (10s). If it takes longer,
            # return immediately — JSONL tail watcher will push the response.
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
                _resume_procs.pop(session_id, None)
                response_text = ""
                if stdout:
                    import json as _json
                    for line in stdout.decode().splitlines():
                        try:
                            obj = _json.loads(line)
                            if obj.get("type") == "assistant" and obj.get("message", {}).get("content"):
                                content = obj["message"]["content"]
                                if isinstance(content, str):
                                    response_text = content
                                elif isinstance(content, list):
                                    parts = [b["text"] for b in content if b.get("type") == "text" and b.get("text")]
                                    if parts:
                                        response_text = "\n".join(parts)
                        except _json.JSONDecodeError:
                            pass
                stderr_text = stderr.decode() if stderr else ""
                if proc.returncode != 0:
                    logger.warning("claude --resume exit %d: %s", proc.returncode, stderr_text[:500])
                return {
                    "status": "ok" if proc.returncode == 0 else "error",
                    "response": response_text,
                    "error": stderr_text[:500] if proc.returncode != 0 else "",
                }
            except asyncio.TimeoutError:
                # Process is still running — response will come via JSONL tail
                logger.info("claude --resume for %s running in background (>10s)", session_id)

                # Clean up in background when done
                async def _cleanup():
                    try:
                        await proc.communicate()
                    except Exception:
                        pass
                    finally:
                        _resume_procs.pop(session_id, None)
                asyncio.create_task(_cleanup())

                return {
                    "status": "streaming",
                    "response": "",
                    "error": "",
                }
        except Exception as e:
            logger.exception("Failed to send message to session %s", session_id)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/sessions/{session_id}/send", dependencies=[Depends(verify_auth)])
    async def send_session_message(session_id: str, request: Request):
        """Send a message to a Claude Code session. Supports JSON or multipart/form-data with images."""
        session = session_registry.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if session_id.startswith("proc-"):
            raise HTTPException(status_code=400, detail="Cannot send to process-only sessions")

        content_type = request.headers.get("content-type", "")
        image_paths: list[str] = []
        msg_text = ""

        if "multipart/form-data" in content_type:
            from fastapi import UploadFile
            import tempfile
            form = await request.form()
            msg_text = form.get("message", "")
            if isinstance(msg_text, UploadFile):
                msg_text = (await msg_text.read()).decode()
            for key in form:
                if key == "images":
                    files = form.getlist("images")
                    for f in files:
                        if hasattr(f, "read"):
                            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                            tmp.write(await f.read())
                            tmp.close()
                            image_paths.append(tmp.name)
        else:
            body = await request.json()
            msg_text = body.get("message", "")

        if not msg_text and not image_paths:
            raise HTTPException(status_code=400, detail="No message or images provided")

        # Check if session has an active terminal process — --resume will hang
        if session.pid:
            try:
                os.kill(session.pid, 0)  # Check if process exists (signal 0)
                # Process is alive — can't use --resume on an active session
                return {
                    "status": "busy",
                    "response": "",
                    "error": f"Session has an active process (PID {session.pid}). "
                             "Cannot send via --resume while Claude is running in a terminal. "
                             "Use the terminal directly or wait for it to finish.",
                }
            except (ProcessLookupError, PermissionError):
                pass  # Process is gone, safe to resume

        try:
            result = await _run_claude_resume(session_id, msg_text, session.cwd, image_paths or None)
        finally:
            # Clean up temp image files
            for p in image_paths:
                try:
                    os.unlink(p)
                except OSError:
                    pass

        # After successful send, ensure session stays active
        if result.get("status") in ("ok", "streaming"):
            from datetime import datetime, timezone
            session.status = SessionStatus.ACTIVE
            session.last_active = datetime.now(timezone.utc)
            session_registry.update_session(session)
            await db.update_session_meta(session_id, status="active")

        return result

    @app.post("/api/sessions/register", dependencies=[Depends(verify_auth)])
    async def register_session(body: SessionRegister):
        from myagent.models import SessionInfo
        from myagent.scanner import extract_project_name
        from datetime import datetime, timezone
        session = SessionInfo(
            id=body.session_id,
            pid=body.pid,
            cwd=body.cwd,
            project=extract_project_name(body.cwd),
            started_at=datetime.now(timezone.utc),
            last_active=datetime.now(timezone.utc),
            status=SessionStatus.ACTIVE,
            is_wrapped=True,
        )
        session_registry.update_session(session)
        await db.upsert_session(session)
        return {"status": "registered", "session_id": body.session_id}

    # ------------------------------------------------------------------
    # WebSocket endpoints
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Shared: tmux PTY WebSocket helper
    # ------------------------------------------------------------------

    async def _ws_tmux_terminal(websocket: WebSocket, tmux_session: str):
        """Attach to a tmux session via PTY and bridge to WebSocket.

        Binary frames = terminal I/O, text JSON frames = control (resize).
        """
        import pty as pty_mod
        import fcntl
        import struct
        import termios

        master_fd, slave_fd = pty_mod.openpty()

        # Wait for the first resize message from xterm.js before attaching,
        # so tmux adopts the correct size from the start.
        initial_rows, initial_cols = 40, 120  # fallback defaults
        try:
            first_msg = await asyncio.wait_for(websocket.receive(), timeout=3.0)
            if "text" in first_msg and first_msg["text"]:
                ctrl = json.loads(first_msg["text"])
                if ctrl.get("type") == "resize":
                    initial_rows = ctrl.get("rows", 40)
                    initial_cols = ctrl.get("cols", 120)
        except (asyncio.TimeoutError, Exception):
            pass

        # Set PTY size BEFORE attaching tmux
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ,
                     struct.pack("HHHH", initial_rows, initial_cols, 0, 0))

        try:
            proc = await asyncio.create_subprocess_exec(
                "tmux", "attach-session", "-d", "-t", tmux_session,
                stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            )
        finally:
            os.close(slave_fd)

        loop = asyncio.get_event_loop()

        async def read_pty():
            try:
                while True:
                    data = await loop.run_in_executor(None, os.read, master_fd, 4096)
                    if not data:
                        break
                    await websocket.send_bytes(data)
            except (OSError, Exception):
                pass

        async def write_pty():
            try:
                while True:
                    msg = await websocket.receive()
                    if msg["type"] == "websocket.disconnect":
                        break
                    if "bytes" in msg and msg["bytes"]:
                        await loop.run_in_executor(None, os.write, master_fd, msg["bytes"])
                    elif "text" in msg and msg["text"]:
                        try:
                            ctrl = json.loads(msg["text"])
                            if ctrl.get("type") == "resize":
                                rows = ctrl.get("rows", 40)
                                cols = ctrl.get("cols", 120)
                                fcntl.ioctl(master_fd, termios.TIOCSWINSZ,
                                            struct.pack("HHHH", rows, cols, 0, 0))
                        except json.JSONDecodeError:
                            await loop.run_in_executor(
                                None, os.write, master_fd, msg["text"].encode("utf-8"))
            except (WebSocketDisconnect, Exception):
                pass

        reader_task = asyncio.create_task(read_pty())
        writer_task = asyncio.create_task(write_pty())

        try:
            await asyncio.gather(reader_task, writer_task, return_exceptions=True)
        finally:
            reader_task.cancel()
            writer_task.cancel()
            try:
                os.close(master_fd)
            except OSError:
                pass
            if proc.returncode is None:
                proc.terminate()

    @app.websocket("/ws/chat")
    async def ws_chat(websocket: WebSocket, token: str = Query("")):
        cfg = websocket.app.state.config
        if token != cfg.server.secret and verify_token(token, cfg.jwt.secret) is None:
            await websocket.close(code=4001, reason="Unauthorized")
            return
        await websocket.accept()
        await _ws_tmux_terminal(websocket, CHAT_TMUX_SESSION)

    @app.websocket("/ws/survival")
    async def ws_survival(websocket: WebSocket, token: str = Query("")):
        cfg = websocket.app.state.config
        if token != cfg.server.secret and verify_token(token, cfg.jwt.secret) is None:
            await websocket.close(code=4001, reason="Unauthorized")
            return
        await websocket.accept()
        await _ws_tmux_terminal(websocket, "survival")

    @app.websocket("/ws/sessions")
    async def ws_sessions(websocket: WebSocket, token: str = Query("")):
        # Verify token
        config = websocket.app.state.config
        if token != config.server.secret and verify_token(token, config.jwt.secret) is None:
            await websocket.close(code=4001, reason="Unauthorized")
            return
        await websocket.accept()
        ws_hub.subscribe("sessions", websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            ws_hub.unsubscribe("sessions", websocket)

    # JSONL tail watchers: session_id -> { task, offset, subscribers }
    _jsonl_watchers: dict[str, dict] = {}
    _jsonl_lock = asyncio.Lock()

    async def _tail_jsonl(session_id: str):
        """Background task that tails a JSONL file and pushes new lines to WebSocket."""
        import json as _json
        projects_dir = Path(os.path.expanduser(config.scanner.claude_projects_dir))
        jsonl_path = None
        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            p = project_dir / f"{session_id}.jsonl"
            if p.exists():
                jsonl_path = p
                break

        if not jsonl_path:
            return

        # Start from current end of file
        try:
            offset = jsonl_path.stat().st_size
        except OSError:
            return

        watcher = _jsonl_watchers.get(session_id)
        if watcher:
            watcher["offset"] = offset

        while session_id in _jsonl_watchers and _jsonl_watchers[session_id]["subscribers"] > 0:
            try:
                current_size = jsonl_path.stat().st_size
            except OSError:
                await asyncio.sleep(1)
                continue

            w = _jsonl_watchers.get(session_id)
            if not w:
                break
            offset = w["offset"]

            if current_size > offset:
                try:
                    with open(jsonl_path, "r", encoding="utf-8") as f:
                        f.seek(offset)
                        new_data = f.read(current_size - offset)
                    w["offset"] = current_size

                    new_lines = new_data.strip().split("\n")
                    events = []
                    for line in new_lines:
                        if not line.strip():
                            continue
                        try:
                            obj = _json.loads(line)
                        except _json.JSONDecodeError:
                            continue
                        msg_type = obj.get("type", "")
                        # Include content messages + progress for status
                        if msg_type in ("user", "assistant", "system", "progress"):
                            events.append(obj)

                    if events:
                        channel = f"session:{session_id}"
                        await ws_hub.broadcast(channel, {
                            "type": "live_events",
                            "session_id": session_id,
                            "events": events,
                        })
                except Exception:
                    logger.exception("Error tailing JSONL for %s", session_id)

            await asyncio.sleep(0.5)

        # Cleanup
        _jsonl_watchers.pop(session_id, None)

    @app.websocket("/ws/sessions/{session_id}")
    async def ws_session_detail(websocket: WebSocket, session_id: str, token: str = Query("")):
        config = websocket.app.state.config
        if token != config.server.secret and verify_token(token, config.jwt.secret) is None:
            await websocket.close(code=4001, reason="Unauthorized")
            return
        await websocket.accept()
        channel = f"session:{session_id}"
        ws_hub.subscribe(channel, websocket)

        # Start JSONL tail watcher if not running
        if not session_id.startswith("proc-"):
            async with _jsonl_lock:
                if session_id not in _jsonl_watchers:
                    _jsonl_watchers[session_id] = {"subscribers": 1, "offset": 0, "task": None}
                    _jsonl_watchers[session_id]["task"] = asyncio.create_task(_tail_jsonl(session_id))
                else:
                    _jsonl_watchers[session_id]["subscribers"] += 1

        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            ws_hub.unsubscribe(channel, websocket)
            async with _jsonl_lock:
                if session_id in _jsonl_watchers:
                    _jsonl_watchers[session_id]["subscribers"] -= 1

    # ------------------------------------------------------------------
    # Serve React SPA (must be last)
    # ------------------------------------------------------------------

    web_dist = Path(__file__).parent.parent / "web" / "dist"
    if web_dist.exists():
        assets_dir = web_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            file_path = (web_dist / full_path).resolve()
            if file_path.is_relative_to(web_dist) and file_path.exists() and file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(web_dist / "index.html"))

    return app


# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------

async def _daily_review_loop(app: FastAPI) -> None:
    """Background loop that triggers daily review at configured time."""
    config = app.state.config
    proactive = app.state.proactive_thinking
    if not proactive or not config.thinking.daily_review_enabled:
        return

    target_hour = config.thinking.daily_review_hour
    target_minute = config.thinking.daily_review_minute
    last_run_date = None

    while True:
        try:
            now = datetime.now()
            today = now.date()

            if (
                last_run_date != today
                and now.hour == target_hour
                and now.minute >= target_minute
            ):
                logger.info("Starting scheduled daily review")
                try:
                    insight = await proactive.daily_review()
                    if insight:
                        logger.info("Daily review completed: %s...", insight[:100])
                    else:
                        logger.info("Daily review skipped (no insight)")
                except Exception:
                    logger.exception("Daily review failed")
                last_run_date = today

            await asyncio.sleep(30)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Daily review loop error")
            await asyncio.sleep(60)


async def _backup_loop(app: FastAPI) -> None:
    """Background loop that backs up SQLite database daily at 3 AM."""
    import shutil

    config = app.state.config
    db_path = Path(config.agent.db_path)
    backup_dir = Path(config.agent.data_dir) / "backups"
    backup_dir.mkdir(exist_ok=True)
    last_backup_date = None
    max_backups = 7

    while True:
        try:
            now = datetime.now()
            today = now.date()

            if last_backup_date != today and now.hour >= 3:
                backup_name = f"agent-{today.isoformat()}.db"
                backup_path = backup_dir / backup_name
                try:
                    if db_path.exists():
                        shutil.copy2(str(db_path), str(backup_path))
                        logger.info("SQLite backup created: %s", backup_path)

                        # Clean up old backups
                        backups = sorted(backup_dir.glob("agent-*.db"))
                        while len(backups) > max_backups:
                            old = backups.pop(0)
                            old.unlink()
                            logger.info("Removed old backup: %s", old)
                except Exception:
                    logger.exception("SQLite backup failed")
                last_backup_date = today

            await asyncio.sleep(3600)  # Check hourly
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Backup loop error")
            await asyncio.sleep(3600)


async def run_server(config_path: str) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    app = await create_app(config_path)
    config = app.state.config

    loop_task = asyncio.create_task(app.state.scheduler.run_loop())

    # Start scanner
    scanner_task = asyncio.create_task(app.state.scanner.run_scan_loop())

    # Start daily review cron + backup
    review_task = asyncio.create_task(_daily_review_loop(app))
    backup_task = asyncio.create_task(_backup_loop(app))

    # Register existing survival tmux session (don't auto-start watchdog; user controls via UI)
    if config.survival.enabled:
        async def _check_survival():
            exists = await app.state.survival_engine._tmux_session_exists()
            if exists:
                logger.info("Existing survival tmux session found, registering")
                _register_tmux_session(app.state.session_registry, "survival", "生存引擎", "#ff4d4f")
        asyncio.create_task(_check_survival())

    # Register existing chat tmux session if it's already running
    proc = await asyncio.create_subprocess_shell(
        "tmux has-session -t chat 2>/dev/null",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    if (proc.returncode or 0) == 0:
        _register_tmux_session(app.state.session_registry, "chat", "AI 对话", "#1677ff")

    # Start profile builder
    profile_task = asyncio.create_task(app.state.profile_builder.run_loop())

    # Start relay client if enabled (wrapped to prevent crash)
    relay_task = None
    if config.relay.enabled:
        async def _safe_relay():
            while True:
                try:
                    await app.state.relay_client.run()
                    break
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.exception("Relay client crashed, restarting in 5s...")
                    await asyncio.sleep(5)
        relay_task = asyncio.create_task(_safe_relay())

    server_config = uvicorn.Config(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level="info",
    )
    server = uvicorn.Server(server_config)
    try:
        await server.serve()
    finally:
        app.state.scheduler.stop()
        app.state.scanner.stop()
        loop_task.cancel()
        scanner_task.cancel()
        review_task.cancel()
        backup_task.cancel()
        if relay_task:
            app.state.relay_client.stop()
            relay_task.cancel()
        await app.state.feishu_client.close()
        await app.state.doubao_client.close()
        await app.state.embedding_store.close()
        await app.state.db.close()
