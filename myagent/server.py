from __future__ import annotations

import asyncio
import logging
from typing import Optional

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from myagent.config import load_config, AgentConfig
from myagent.context_manager import ContextManager
from myagent.db import Database
from myagent.doubao import DoubaoClient
from myagent.embedding import EmbeddingStore
from myagent.feishu import FeishuClient, build_task_card, parse_feishu_event
from myagent.memory import MemoryManager
from myagent.models import Task, TaskSource, TaskStatus
from myagent.scheduler import Scheduler
from myagent.router import MessageRouter, SYSTEM, CHAT, SEARCH
from myagent.web import router as web_router
from myagent.ws_client import RelayClient

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


# ------------------------------------------------------------------
# Request models
# ------------------------------------------------------------------

class TaskSubmit(BaseModel):
    prompt: str
    cwd: str = "."
    priority: str = "normal"
    source: str = "web"


# ------------------------------------------------------------------
# Auth dependency
# ------------------------------------------------------------------

async def verify_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    secret = request.app.state.config.server.secret
    if credentials is None or credentials.credentials != secret:
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

    # Doubao + pgvector + memory
    doubao_client = DoubaoClient(config.doubao)
    embedding_store = EmbeddingStore(config.postgres)
    await embedding_store.init()
    memory_manager = MemoryManager(db, doubao_client, embedding_store)

    # Feishu client
    feishu_client = FeishuClient(config.feishu)

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

        # Summarize into memory (best-effort)
        try:
            await memory_manager.summarize_task(task_id)
        except Exception:
            logging.getLogger(__name__).exception("Failed to summarize task %s", task_id)

    # Context manager
    context_manager = ContextManager(
        persona_dir=config.agent.persona_dir,
    ) if config.agent.persona_dir else None

    scheduler = Scheduler(
        db, config.claude, config.scheduler,
        on_task_done=on_task_done,
        context_manager=context_manager,
        memory_manager=memory_manager,
    )

    # Message router
    message_router = MessageRouter(doubao_client)

    # Relay client (WebSocket to wdao.chat)
    async def on_relay_message(msg: dict) -> None:
        """Handle incoming message from relay (Feishu events)."""
        parsed = parse_feishu_event(msg)
        if parsed is None:
            return

        content = parsed["content"]
        chat_id = parsed.get("chat_id", "")

        # Route the message
        classification = await message_router.classify(content)
        category = classification["category"]

        if category == SYSTEM:
            detail = classification.get("detail", "")
            reply = await _handle_system_command(detail, db, scheduler)
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

        # Create task
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

    async def _handle_system_command(detail: str, db: Database, scheduler: Scheduler) -> str:
        if detail == "status":
            remaining = scheduler._rate_limiter.remaining
            running = scheduler._running
            return f"运行状态: {'运行中' if running else '已停止'}\n今日剩余额度: {remaining}"
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
        else:
            return f"未知命令: {detail}"

    relay_client = RelayClient(config.relay, on_message=on_relay_message)

    app = FastAPI(title=config.agent.name)
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

    # Mount web routes
    app.include_router(web_router)

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
        }

    # ------------------------------------------------------------------
    # Protected routes
    # ------------------------------------------------------------------

    @app.post("/api/tasks", status_code=201, dependencies=[Depends(verify_auth)])
    async def submit_task(body: TaskSubmit):
        try:
            source = TaskSource(body.source)
        except ValueError:
            source = TaskSource.WEB

        # Route message to determine complexity
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
    async def search_memories(q: str = Query(...), limit: int = Query(10)):
        results = await memory_manager.hybrid_search(q, limit=limit)
        return results

    @app.get("/api/memory/context", dependencies=[Depends(verify_auth)])
    async def get_memory_context(q: str = Query(...), limit: int = Query(5)):
        context = await memory_manager.get_context_for_task(q, limit=limit)
        return {"context": context}

    @app.get("/api/status", dependencies=[Depends(verify_auth)])
    async def get_status():
        return {
            "scheduler_remaining": scheduler._rate_limiter.remaining,
            "scheduler_running": scheduler._running,
        }

    return app


# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------

async def run_server(config_path: str) -> None:
    app = await create_app(config_path)
    config = app.state.config

    loop_task = asyncio.create_task(app.state.scheduler.run_loop())

    # Start relay client if enabled (wrapped to prevent crash)
    relay_task = None
    if config.relay.enabled:
        async def _safe_relay():
            while True:
                try:
                    await app.state.relay_client.run()
                    break  # Normal exit
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
        loop_task.cancel()
        if relay_task:
            app.state.relay_client.stop()
            relay_task.cancel()
        await app.state.feishu_client.close()
        await app.state.doubao_client.close()
        await app.state.embedding_store.close()
        await app.state.db.close()
