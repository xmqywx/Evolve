# Phase 4: Web Panel + Intelligent Routing

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan.

**Goal:** Build the web dashboard (htmx + Tailwind CDN, zero-build) with 4 pages and add Doubao-based message routing for task classification.

**Architecture:** FastAPI serves Jinja2 templates with htmx for dynamic updates. SSE for real-time task output. Doubao classifies incoming messages to route to appropriate execution strategy.

**Tech Stack:** Jinja2, htmx, Tailwind CDN, SSE, Doubao API

---

## File Map

| File | Responsibility |
|------|---------------|
| `myagent/router.py` | Message classification: simple/complex/specialized/system/chat |
| `myagent/web.py` | Web routes (HTML pages) mounted on FastAPI app |
| `myagent/templates/base.html` | Base template with Tailwind + htmx |
| `myagent/templates/index.html` | Dashboard: status, stats, recent tasks |
| `myagent/templates/tasks.html` | Task list with filters |
| `myagent/templates/task_detail.html` | Task detail with logs |
| `myagent/templates/memory.html` | Memory search interface |
| `tests/test_router.py` | Test message classification |
| `tests/test_web.py` | Test web page rendering |

---

## Chunk 1: Message Router

### Task 1: Doubao-based message router

**Files:**
- Create: `myagent/router.py`
- Create: `tests/test_router.py`

The router classifies messages into categories using Doubao, with fallback rules.

## Chunk 2: Web Templates + Routes

### Task 2: Jinja2 templates and web routes

**Files:**
- Create: `myagent/templates/base.html`
- Create: `myagent/templates/index.html`
- Create: `myagent/templates/tasks.html`
- Create: `myagent/templates/task_detail.html`
- Create: `myagent/templates/memory.html`
- Create: `myagent/web.py`
- Modify: `myagent/server.py` (mount web routes)
- Modify: `requirements.txt` (add jinja2)

## Chunk 3: Integration + Tests

### Task 3: Wire web + router into server, tests

### Task 4: Full test suite + verification
