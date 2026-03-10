from __future__ import annotations

import asyncio
import logging
from typing import Optional

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from myagent.config import load_config, AgentConfig
from myagent.db import Database
from myagent.doubao import DoubaoClient
from myagent.embedding import EmbeddingStore
from myagent.feishu import FeishuClient, build_task_card, parse_feishu_event
from myagent.memory import MemoryManager
from myagent.models import Task, TaskSource, TaskStatus
from myagent.scheduler import Scheduler
from myagent.ws_client import RelayClient

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

    scheduler = Scheduler(db, config.claude, config.scheduler, on_task_done=on_task_done)

    # Relay client (WebSocket to wdao.chat)
    async def on_relay_message(msg: dict) -> None:
        """Handle incoming message from relay (Feishu events)."""
        parsed = parse_feishu_event(msg)
        if parsed is None:
            return
        # Create task from Feishu message
        task = Task(
            prompt=parsed["content"],
            source=TaskSource.FEISHU,
        )
        await db.create_task(task)
        logging.getLogger(__name__).info("Task created from Feishu: %s", task.id)

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

        task = Task(
            prompt=body.prompt,
            cwd=body.cwd,
            priority=body.priority,
            source=source,
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

    # Start relay client if enabled
    relay_task = None
    if config.relay.enabled:
        relay_task = asyncio.create_task(app.state.relay_client.run())

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
