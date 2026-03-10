from __future__ import annotations

import asyncio
from typing import Optional

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from myagent.config import load_config, AgentConfig
from myagent.db import Database
from myagent.models import Task, TaskSource, TaskStatus
from myagent.scheduler import Scheduler

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
    scheduler = Scheduler(db, config.claude, config.scheduler)

    app = FastAPI(title=config.agent.name)
    app.state.config = config
    app.state.db = db
    app.state.scheduler = scheduler

    # ------------------------------------------------------------------
    # Public routes
    # ------------------------------------------------------------------

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "name": config.agent.name,
            "scheduler_remaining": scheduler._rate_limiter.remaining,
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
    async def search_memories(q: str = Query(...)):
        results = await db.search_memories(q)
        return results

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
        await app.state.db.close()
