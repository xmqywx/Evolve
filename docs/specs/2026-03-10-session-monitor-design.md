# Claude Session Monitor - Design Spec

> **Status: Superseded** — See `docs/OVERVIEW.md § 7 Sessions & Monitoring` for current design. This file kept as implementation-detail reference.

## Goal

MyAgent can discover, monitor, and display all Claude Code sessions running on the Mac, with real-time updates via WebSocket, a React Dashboard (mobile-friendly), and Feishu integration.

## Architecture: Hybrid Mode

Two discovery mechanisms work in parallel:

1. **Process scanning** - `ps` every 5 seconds to find all `claude` processes (PID, cwd, tty, start time)
2. **JSONL file watching** - `watchfiles` monitors `~/.claude/projects/` for session data changes

Additionally, sessions started via the `myagent` wrapper register directly with the server, providing richer metadata and future remote-control capability (Phase 2).

## Data Model

```python
class Session:
    id: str              # session UUID (from JSONL filename)
    pid: int | None      # process PID (present when active)
    cwd: str             # working directory
    project: str         # project name (extracted from cwd)
    tty: str | None      # terminal
    started_at: datetime
    last_active: datetime
    status: "active" | "idle" | "finished"
    is_wrapped: bool     # started via myagent wrapper
    messages: list       # recent N conversation messages
```

Merging logic: PID exists = active, JSONL exists but no process = finished.

## New Modules

### scanner.py - SessionScanner

Responsibilities:
- Periodic process scan (`ps aux | grep claude`)
- Extract PID, cwd (via `lsof -p`), tty, start time
- Map cwd to `~/.claude/projects/` directory path
- Watch JSONL files for changes using `watchfiles`
- Parse JSONL: extract user/assistant/system messages, skip internal events (progress, file-history-snapshot, queue-operation, change)
- Reference: Happy's `sessionScanner.ts` filtering logic

### session_registry.py - SessionRegistry

Responsibilities:
- Merge process scan results with JSONL data
- Maintain in-memory session state
- Cache last 200 messages per session
- Detect state changes (new session, status change, new message)
- Notify WebSocket Hub on changes
- Persist session metadata to SQLite `sessions` table

### ws_hub.py - WebSocket Hub

Responsibilities:
- Manage Dashboard WebSocket connections
- Two channel types:
  - `/ws/sessions` - global session list updates (new/removed/status change)
  - `/ws/sessions/{id}` - single session real-time message stream
- Broadcast changes from SessionRegistry to subscribed clients
- Handle connection lifecycle (connect, disconnect, reconnect)

### cli.py - MyAgent Wrapper CLI

Command:
```bash
myagent                                    # interactive mode (same as claude)
myagent --dangerously-skip-permissions     # pass-through all claude args
myagent -p "task"                          # non-interactive mode
```

Behavior:
1. Spawn `claude` subprocess, proxy stdin/stdout/stderr transparently
2. Register with MyAgent server: POST `/api/sessions/register` with session_id, pid, cwd
3. Heartbeat every 10 seconds
4. Connect to server WebSocket for future remote control (Phase 2 prep, no-op in Phase 1)
5. Terminal experience identical to running `claude` directly

Installation: `pip install -e .` adds `myagent` command, or alias in `~/.zshrc`.

## Frontend: React Dashboard

### Tech Stack

- React 18 + TypeScript
- Ant Design (antd) - UI framework
- Vite - build tool
- Native WebSocket
- Prism.js or highlight.js - code highlighting
- @ant-design/icons - icons (no emoji anywhere)

### Design Style

- Dark theme, dark gray + blue accent (no purple)
- No emoji, all antd icons
- Compact layout, high information density
- Mobile-first responsive design

### Pages

```
web/src/
  pages/
    Dashboard.tsx       # Overview: active sessions count, task stats, system status
    Sessions.tsx        # Session list - card layout, status filters
    SessionDetail.tsx   # Chat-style message stream with real-time WebSocket updates
    Tasks.tsx           # Task list (existing functionality)
    Memory.tsx          # Memory search (existing functionality)
    Login.tsx           # JWT-based login
  components/
    SessionCard.tsx     # Session card for list view
    MessageBubble.tsx   # Chat bubble (user right, assistant left)
    ToolCallBlock.tsx   # Collapsible tool call display
    CodeBlock.tsx       # Syntax-highlighted code block
  hooks/
    useWebSocket.ts     # WebSocket connection hook
  App.tsx
  main.tsx
```

### Session List Page (`/sessions`)

- Card layout, one card per session
- Card content: project name, cwd (truncated), status tag (active/idle/finished), last active time
- Active sessions sorted first, with pulsing green indicator
- Filter by status

### Session Detail Page (`/sessions/{id}`)

- Top: session metadata (project, PID, start time, duration)
- Body: chat message stream
  - User messages aligned right, assistant messages aligned left
  - Tool calls in collapsible blocks (click to expand params and results)
  - Code blocks with syntax highlighting
- Real-time updates via WebSocket, no page refresh needed
- Bottom: input box (Phase 1: disabled with placeholder "Phase 2"; wrapper sessions only)

### Mobile Adaptation

- Responsive via Tailwind/antd breakpoints
- Session list: single column full-width cards on mobile
- Chat stream: full screen, WeChat-like experience
- Fixed top nav bar, fixed bottom input area

### Build & Serve

- Development: Vite dev server proxies `/api/*` and `/ws/*` to `:8090`
- Production: `vite build` outputs to `web/dist/`, FastAPI serves static files
- Existing HTMX templates fully replaced

## API Changes

### New Endpoints

```
GET  /api/sessions                  # List all sessions
GET  /api/sessions/{id}             # Session detail + message history
POST /api/sessions/register         # Wrapper registration
WS   /ws/sessions                   # Global session state stream
WS   /ws/sessions/{id}              # Single session message stream
```

### Auth Change

- Replace cookie-based auth with JWT token
- Login returns JWT, frontend stores in localStorage
- All API/WS requests include Bearer token

### Existing Endpoints (kept)

```
GET  /health
POST /api/tasks
GET  /api/tasks
GET  /api/tasks/{id}
POST /api/tasks/{id}/cancel
GET  /api/tasks/{id}/logs
GET  /api/memory/search
GET  /api/memory/context
GET  /api/status
```

## Feishu Integration Enhancement

### Session Commands

| User says | Route | Response |
|---|---|---|
| "my sessions" / "what's running" | system:sessions | Active session summary card |
| "how's the quant one" | system:session_detail | Fuzzy match project, return recent messages |
| "check status" | system:status | System status + active session count |

### Feishu Card Format

Session list displayed as structured card:
```
[Running] quant | ~/Documents/Kris/quant
Last active: 2m ago
Doing: Analyzing K-line data...

[Running] shopApi | ~/Documents/Shop/shopApi
Last active: 15m ago
Doing: Fixing payment API...
```

### Proactive Notifications

Push Feishu messages on:
- Wrapper session completed or errored
- Session idle > 30 minutes (configurable)
- New session started (configurable)

Notification frequency configurable to avoid spam.

## Configuration

```yaml
scanner:
  process_interval: 5
  claude_projects_dir: "~/.claude/projects"
  max_messages_cached: 200

jwt:
  secret: "change-me"
  expiry_hours: 168  # 7 days
```

## Database Changes

New `sessions` table:
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    pid INTEGER,
    cwd TEXT NOT NULL,
    project TEXT NOT NULL,
    tty TEXT,
    started_at TEXT NOT NULL,
    last_active TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    is_wrapped BOOLEAN NOT NULL DEFAULT 0
);
```

## File Structure (new/modified)

```
myagent/
  scanner.py            # NEW - SessionScanner
  session_registry.py   # NEW - SessionRegistry
  ws_hub.py             # NEW - WebSocket Hub
  cli.py                # NEW - myagent wrapper CLI
  server.py             # MODIFIED - add WS endpoints, session API, JWT auth
  config.py             # MODIFIED - add scanner/jwt config
  db.py                 # MODIFIED - add sessions table
  router.py             # MODIFIED - add session query routing
  feishu.py             # MODIFIED - session summary cards
web/                    # NEW - React frontend
  src/
  package.json
  vite.config.ts
  tsconfig.json
```

## Phase Scope

### Phase 1 (this spec)
- SessionScanner (process scan + JSONL watch)
- SessionRegistry (state management + SQLite)
- WebSocket Hub (real-time push)
- React Dashboard (all pages, mobile responsive)
- myagent wrapper CLI (registration + heartbeat, no remote control)
- Feishu session queries + summary cards
- JWT auth replacing cookie auth

### Phase 2 (future)
- Remote message sending to wrapper sessions
- Local/remote control switching (keyboard takeover)
- Feishu -> specific session messaging
- Session grouping and tagging
