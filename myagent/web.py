"""Web routes for the MyAgent dashboard."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request, Depends, Query, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from myagent.models import Task, TaskSource, TaskStatus

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

router = APIRouter()


def _verify_web_auth(request: Request, token: str | None = Cookie(None)) -> bool:
    """Check cookie-based auth for web routes."""
    secret = request.app.state.config.server.secret
    return token == secret


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
async def login_submit(request: Request, secret: str = Form(...)):
    config_secret = request.app.state.config.server.secret
    if secret != config_secret:
        return templates.TemplateResponse(request, "login.html", {"error": "Invalid token"})
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("token", secret, httponly=True, samesite="strict")
    return response


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not _verify_web_auth(request, request.cookies.get("token")):
        return RedirectResponse(url="/login")
    db = request.app.state.db
    config = request.app.state.config
    scheduler = request.app.state.scheduler
    tasks = await db.list_tasks(limit=10)
    total_tasks = await db.count_tasks()
    status = {
        "scheduler_remaining": scheduler._rate_limiter.remaining,
        "feishu_enabled": config.feishu.enabled,
        "relay_enabled": config.relay.enabled,
    }
    return templates.TemplateResponse(request, "index.html", {
        "tasks": [t.model_dump(mode="json") for t in tasks],
        "total_tasks": total_tasks,
        "status": status,
    })


@router.get("/tasks", response_class=HTMLResponse)
async def task_list(request: Request, status: str | None = Query(None)):
    if not _verify_web_auth(request, request.cookies.get("token")):
        return RedirectResponse(url="/login")
    db = request.app.state.db
    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            pass
    tasks = await db.list_tasks(limit=100, status=task_status)
    return templates.TemplateResponse(request, "tasks.html", {
        "tasks": [t.model_dump(mode="json") for t in tasks],
        "filter_status": status,
    })


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(request: Request, task_id: str):
    if not _verify_web_auth(request, request.cookies.get("token")):
        return RedirectResponse(url="/login")
    db = request.app.state.db
    task = await db.get_task(task_id)
    if task is None:
        return HTMLResponse("<h1>Task not found</h1>", status_code=404)
    logs = await db.get_task_logs(task_id)
    return templates.TemplateResponse(request, "task_detail.html", {
        "task": task.model_dump(mode="json"),
        "logs": logs,
    })


@router.get("/memory", response_class=HTMLResponse)
async def memory_page(request: Request, q: str | None = Query(None)):
    if not _verify_web_auth(request, request.cookies.get("token")):
        return RedirectResponse(url="/login")
    results = []
    if q:
        memory_manager = request.app.state.memory_manager
        results = await memory_manager.hybrid_search(q, limit=20)
    return templates.TemplateResponse(request, "memory.html", {
        "results": results,
        "query": q,
    })


@router.get("/web/memory/search", response_class=HTMLResponse)
async def memory_search_htmx(request: Request, q: str = Query("")):
    """HTMX endpoint for memory search results (returns fragment)."""
    results = []
    if q:
        memory_manager = request.app.state.memory_manager
        results = await memory_manager.hybrid_search(q, limit=20)
    return templates.TemplateResponse(request, "_memory_results.html", {
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
        f'<div class="text-green-400">任务已提交: {task.id[:12]}</div>'
    )
