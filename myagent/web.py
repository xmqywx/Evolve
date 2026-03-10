"""Web routes for the MyAgent dashboard."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request, Depends, Query, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from myagent.models import Task, TaskSource, TaskStatus

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    db = request.app.state.db
    scheduler = request.app.state.scheduler
    tasks = await db.list_tasks(limit=10)
    status = {
        "scheduler_remaining": scheduler._rate_limiter.remaining,
    }
    return templates.TemplateResponse("index.html", {
        "request": request,
        "tasks": [t.model_dump() for t in tasks],
        "status": status,
    })


@router.get("/tasks", response_class=HTMLResponse)
async def task_list(request: Request, status: str | None = Query(None)):
    db = request.app.state.db
    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            pass
    tasks = await db.list_tasks(limit=100, status=task_status)
    return templates.TemplateResponse("tasks.html", {
        "request": request,
        "tasks": [t.model_dump() for t in tasks],
        "filter_status": status,
    })


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(request: Request, task_id: str):
    db = request.app.state.db
    task = await db.get_task(task_id)
    if task is None:
        return HTMLResponse("<h1>Task not found</h1>", status_code=404)
    logs = await db.get_task_logs(task_id)
    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "task": task.model_dump(),
        "logs": logs,
    })


@router.get("/memory", response_class=HTMLResponse)
async def memory_page(request: Request, q: str | None = Query(None)):
    results = []
    if q:
        memory_manager = request.app.state.memory_manager
        results = await memory_manager.hybrid_search(q, limit=20)
    return templates.TemplateResponse("memory.html", {
        "request": request,
        "results": results,
        "query": q,
    })


@router.get("/web/memory/search", response_class=HTMLResponse)
async def memory_search_htmx(request: Request, q: str = Query("")):
    """HTMX endpoint for memory search results."""
    results = []
    if q:
        memory_manager = request.app.state.memory_manager
        results = await memory_manager.hybrid_search(q, limit=20)
    return templates.TemplateResponse("memory.html", {
        "request": request,
        "results": results,
        "query": q,
    })


@router.post("/web/submit", response_class=HTMLResponse)
async def web_submit(request: Request, prompt: str = Form(...)):
    """HTMX endpoint for quick task submission."""
    db = request.app.state.db
    task = Task(prompt=prompt, source=TaskSource.WEB)
    await db.create_task(task)
    return HTMLResponse(
        f'<div class="text-green-400">Task submitted: {task.id[:12]}</div>'
    )
