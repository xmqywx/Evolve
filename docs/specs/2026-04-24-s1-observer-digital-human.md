# S1 — Observer Digital Human (Stage 1 Design Spec)

> **Status**: Active
> **Date**: 2026-04-24
> **Parent roadmap**: `docs/specs/2026-04-24-multi-digital-human-roadmap.md`
> **Scope**: Add the second digital human ("Observer") + land the shared contracts that Stages 2/3 will build on. Rename current survival engine to "Executor" at the concept level.
> **Depends on**: stabilization sprint 2026-04-24 (landed ARCHITECTURE, OVERVIEW, roles-boundary ADR).

---

## 1. Goal

Ship a system where two digital humans — Executor and Observer — run concurrently on the same Mac Studio, coordinating through the Self-Report event bus, with full per-DH data isolation and UI visibility.

**"Done" means**: both DHs run for ≥7 consecutive days, Observer produces ≥50 discoveries of which ≥30% are user-rated useful, and daily cost stays below $10. Concrete exit criteria in §9.

---

## 2. What changes (high level)

1. **Data**: `digital_human_id` column on 6 tables; historical data backfilled to `'executor'`
2. **Filesystem**: `persona/` split into `persona/{executor,observer}/`; new `digital_humans/` runtime state directory
3. **Code**: `ContextBuilder` becomes DH-aware; `SurvivalEngine` becomes one instance among many; new `ObserverEngine` module; new lifecycle API endpoints
4. **UI**: per-DH filter on existing pages; new `/digital_humans` page; on-line DH indicator on `/overview`
5. **Config**: new `digital_humans:` section in `config.yaml`

---

## 3. Data model changes

### 3.1 DDL migration

Single migration commit containing 6 ALTER TABLE statements:

```sql
ALTER TABLE agent_heartbeats   ADD COLUMN digital_human_id TEXT NOT NULL DEFAULT 'executor';
ALTER TABLE agent_deliverables ADD COLUMN digital_human_id TEXT NOT NULL DEFAULT 'executor';
ALTER TABLE agent_discoveries  ADD COLUMN digital_human_id TEXT NOT NULL DEFAULT 'executor';
ALTER TABLE agent_workflows    ADD COLUMN digital_human_id TEXT NOT NULL DEFAULT 'executor';
ALTER TABLE agent_upgrades     ADD COLUMN digital_human_id TEXT NOT NULL DEFAULT 'executor';
ALTER TABLE agent_reviews      ADD COLUMN digital_human_id TEXT NOT NULL DEFAULT 'executor';
```

Plus new table for loop prevention:

```sql
CREATE TABLE IF NOT EXISTS agent_discovery_dedup (
    dedup_key TEXT PRIMARY KEY,
    first_seen_at TIMESTAMP NOT NULL,
    hit_count INTEGER DEFAULT 1
);
```

Plus indexes for UI filter performance:

```sql
CREATE INDEX IF NOT EXISTS idx_heartbeats_dh   ON agent_heartbeats(digital_human_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deliverables_dh ON agent_deliverables(digital_human_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_discoveries_dh  ON agent_discoveries(digital_human_id, created_at DESC);
```

### 3.2 Backfill

Migration is zero-downtime via `DEFAULT 'executor'`. No backfill script needed for existing rows — the default value applies retroactively to all historical rows since SQLite rewrites the table on ADD COLUMN with DEFAULT.

Verification query post-migration:
```sql
SELECT digital_human_id, COUNT(*) FROM agent_heartbeats GROUP BY digital_human_id;
-- Expected: one row with digital_human_id='executor' and count matching pre-migration total
```

### 3.3 DB helper API

`myagent/db.py` changes (keep existing callers working):

```python
async def insert_heartbeat(self, *, digital_human_id: str = "executor", activity: str, ...):
    ...

async def list_heartbeats(self, *, digital_human_id: str | None = None, limit: int = 50):
    """If digital_human_id is None, returns all DHs; else filters."""
    ...
```

Pattern applies to all 6 INSERT and all `list_*` / `get_latest_*` helpers. Defaults preserve existing behavior; new code passes explicit IDs.

---

## 4. Filesystem changes

### 4.1 Persona directory

```
persona/
├── executor/
│   ├── identity.md       (moved from persona/identity.md)
│   ├── knowledge.md      (moved from persona/knowledge.md)
│   └── principles.md     (moved from persona/principles.md)
└── observer/
    ├── identity.md       (new, see §6)
    ├── knowledge.md      (new — initially a copy of executor's; Ying can diverge later)
    └── principles.md     (new — subset focused on observation: "never execute", "never produce deliverables")
```

Old flat paths (`persona/*.md`) are removed from the repo. Any code still referencing them is updated or fails loudly.

`persona/about_ying.md` and `persona/private.md` (both in `.gitignore`) stay at the top level — they're Ying-specific notes, not DH-specific.

### 4.2 Digital Human runtime state

```
digital_humans/
├── executor/
│   └── state.json
└── observer/
    └── state.json
```

`state.json` schema:
```json
{
  "cmux_session": "mycmux-executor",
  "provider": "codex",
  "started_at": "2026-04-24T17:00:00+08:00",
  "last_heartbeat_at": "2026-04-24T17:10:00+08:00",
  "restart_count": 0,
  "enabled": true
}
```

Directory is created by the server on DH first-start if missing. Written by lifecycle API handlers and by the DH's own runtime loop (heartbeat echo).

---

## 5. Config changes

New section in `config.yaml`:

```yaml
digital_humans:
  executor:
    persona_dir: persona/executor
    cmux_session: mycmux-executor
    provider: codex               # inherits from survival.provider at load time; explicit here for clarity
    heartbeat_interval_secs: 600  # 10 min
    skill_whitelist: ["*"]        # Executor can call any skill
    enabled: true
  observer:
    persona_dir: persona/observer
    cmux_session: mycmux-observer
    provider: codex
    heartbeat_interval_secs: 1800 # 30 min
    skill_whitelist: []           # Observer calls no skills in S1
    enabled: true
```

The legacy `survival:` block stays but becomes the "source of truth for Executor" — Executor-specific flags (`workspace`, `provider`) are read from `survival.*` when `digital_humans.executor.*` is absent. Later stages may consolidate. Do not duplicate flags in both blocks in S1.

---

## 6. Observer design

### 6.1 Identity prompt (`persona/observer/identity.md`)

```markdown
# Observer Digital Human

你是 MyAgent 的 Observer。你的唯一职责是观察 Executor 的工作、系统状态和外部世界，
发现值得 Ying 知道的信号（机会 / 风险 / 洞察 / 市场数据），并通过 Self-Report API 上报。

## 你能做什么

- 调用 `POST /api/agent/heartbeat`（每 30 分钟一次或状态变化时）
- 调用 `POST /api/agent/discovery`（每次发现有价值的信号）

## 你不能做什么

- 不得调用 deliverable / workflow / upgrade / review API
- 不得调用任何 skill agent（你的 skill_whitelist 为空）
- 不得写文件、执行代码、修改代码
- 不得直接给 Executor 发消息（所有沟通走 discovery 事件，Executor 自己读）

## 你的信息来源（每次 context 刷新）

ContextBuilder 每次唤醒你时提供：
1. Executor 最近 3 条 heartbeat (它在做什么)
2. Executor 最近 3 条 deliverable (它产出了什么)
3. 你自己最近 10 条 discovery (防重复)
4. 过去 2 小时的 git log (代码层面的变化)
5. 可选：指定日志文件的尾 200 行

## discovery 的 dedup_key

你发 discovery 时必须提供 dedup_key，规则：
`dedup_key = lowercase(title) + "|" + category + "|" + date(YYYY-MM-DD)`

如果系统返回"duplicate suppressed"，说明 24h 内已有同类 discovery — 跳过，不要重发。

## priority 规则

- high: Ying 看到会立即采取行动的信号（商机、严重错误、数据异常）
- medium: 值得记录但不紧急
- low: 弱信号 / 备忘

宁少勿滥。你的 KPI 是 Ying 对 discovery 的"有用率" ≥ 30%。

## 何时 heartbeat

每轮 context 刷新（每 30 分钟）至少发一次 heartbeat，`activity: "researching"` 或 `"idle"`。不发 = 工作等于没做（系统会标记你卡死）。
```

### 6.2 Observer runtime loop (`myagent/observer.py`)

New module, pattern mirrors `survival.py` but simplified:

```python
class ObserverEngine:
    def __init__(self, db, config, feishu): ...
    async def start(self): ...                    # spawn mycmux-observer
    async def stop(self): ...
    async def _loop(self):
        while self._running:
            ctx = await self._build_context()     # §6.3
            prompt = await self._render_prompt(ctx)
            await self._send_to_cmux(prompt)      # nudge the LLM with new context
            await asyncio.sleep(1800)             # 30 min
```

Key differences from `SurvivalEngine`:
- No watchdog-based nudge (relies on timer)
- No capture-pane fallback (doesn't matter if output is missed)
- No Feishu report call (S1 scope; S2 may revisit)
- No `--resume` recovery prompt (Observer is stateless-ish; session restart just reloads context)

### 6.3 Observer `ContextBuilder`

Factor the existing `ContextBuilder` to accept `digital_human_id`. For Observer:

```python
async def build_observer_context(self, db):
    return {
        "exec_heartbeats": await db.list_heartbeats(digital_human_id="executor", limit=3),
        "exec_deliverables": await db.list_deliverables(digital_human_id="executor", limit=3),
        "own_discoveries": await db.list_discoveries(digital_human_id="observer", limit=10),
        "git_log_2h": subprocess.run(["git", "log", "--since=2 hours ago", "--oneline"], ...).stdout,
    }
```

No skill library summary (observer has no skills). No task ref (observer has no active task).

### 6.4 Loop prevention

Server-side check on `POST /api/agent/discovery`:

```python
@router.post("/api/agent/discovery")
async def discovery(req: DiscoveryReq, dh_id: str = Header(...)):
    dedup_key = req.dedup_key or compute_default(req)
    existing = await db.get_dedup(dedup_key)
    if existing:
        await db.increment_dedup(dedup_key)
        return {"status": "duplicate_suppressed", "hit_count": existing.hit_count + 1}
    await db.insert_dedup(dedup_key)
    await db.insert_discovery(digital_human_id=dh_id, ...)
    return {"status": "ok"}
```

Additionally, per §3.1 the skill whitelist check rejects disallowed API calls. A request by `observer` to `POST /api/agent/deliverable` returns `403 role_not_permitted`.

---

## 7. UI changes

### 7.1 `/overview` (Dashboard.tsx)

Add a top strip above existing content:

```
┌─────────────────────────────────────────────────────────┐
│ DH online:  [● Executor: researching (60%)]  [● Observer: idle]  [+ manage] │
└─────────────────────────────────────────────────────────┘
```

Each DH chip: color-coded status dot, name, activity + progress. Click-through to `/digital_humans/{id}`.

### 7.2 Filter on existing pages

On `/sessions`, `/output`, `/memory` (Discoveries tab), `/workflows`: add a segmented control at the top:

```
[ All ] [ Executor ] [ Observer ]
```

Filter value is a query-string param; server accepts `?digital_human_id=` on list endpoints.

### 7.3 New page `/digital_humans`

Routes: `/digital_humans` (list), `/digital_humans/{id}` (detail).

List view — cards:
```
┌──────────────────────────────────┐
│ ● Executor                       │
│ persona: persona/executor/        │
│ cmux: mycmux-executor            │
│ last heartbeat: 2m ago           │
│ today: 5 deliverables / 12 hb    │
│ [Stop] [Restart] [Open session]  │
└──────────────────────────────────┘
```

Detail view: identity.md preview, recent heartbeats/deliveries/discoveries, skill whitelist, config summary, restart log.

### 7.4 Not in S1

- Persona editor UI (use text editor / git for now)
- DH creation wizard (config.yaml only)
- Discovery curation UI (new "is this useful?" button) — deferred; manual review for now

---

## 8. API changes

### 8.1 Modified — all existing `POST /api/agent/*`

Accept `digital_human_id` in body (optional; defaults to `'executor'` for back-compat with existing callers that don't know about DHs). Server writes that column value.

For S1, Ying will explicitly set `digital_human_id: observer` in the Observer's curl prompt template.

### 8.2 Modified — all existing `GET /api/...` list endpoints

Accept optional `?digital_human_id=` query param; omitted = all DHs.

### 8.3 New — lifecycle endpoints

```
GET  /api/digital_humans                         → [{ id, config, state, last_heartbeat }, ...]
GET  /api/digital_humans/{id}                    → detail
POST /api/digital_humans/{id}/start              → spawns cmux, writes state.json, 200 OK
POST /api/digital_humans/{id}/stop               → kills cmux gracefully (send exit signal, wait 10s)
POST /api/digital_humans/{id}/restart            → stop + start
```

### 8.4 New — role-permission check middleware

Before handling any `POST /api/agent/*`, middleware reads `digital_human_id` from body, looks up that DH's `skill_whitelist` + endpoint allowlist in config, rejects if mismatch.

Endpoint allowlist per DH:
- `executor`: all 6 endpoints
- `observer`: `heartbeat` + `discovery` only

---

## 9. Exit criteria (= "S1 done")

1. **Data contract landed**: all 6 tables have `digital_human_id`, historical rows tagged `'executor'`, `persona/{executor,observer}/` subdirs exist, `digital_humans/{executor,observer}/state.json` written on startup.
2. **Dual-DH stable for ≥7 consecutive days**: both Executor and Observer run 168 hours continuously. Observer unexpected restart count ≤3 over the window. No Mac swap or OOM events attributable to MyAgent.
3. **Cost control**: daily token consumption (combined DHs) < 500k; daily cost < $10 for 5 of 7 days.
4. **Observer output audit**: ≥50 discoveries in `agent_discoveries` with `digital_human_id='observer'`; manual review (Ying spot-checks 20 random entries) finds ≥30% useful (priority high or genuinely actionable medium).
5. **Loop prevention works**: `agent_discovery_dedup` table has at least 5 entries with `hit_count > 1`, proving dedup is actually suppressing; zero "discovery storm" events (>3 discoveries/min for sustained 5 min).
6. **Role isolation**: zero rows in `agent_deliverables`, `agent_workflows`, `agent_upgrades`, `agent_reviews` where `digital_human_id='observer'`. Any such row indicates Observer breached its role.
7. **UI fidelity**: all list pages respect the DH filter; `/digital_humans` page shows live state.

If any criterion misses by >2 weeks of iteration, pause and reassess per roadmap § 5 stop-loss.

---

## 10. Out of scope (push to S2 or later)

- Conductor role / arbitration logic
- DH-to-DH channel (bus-only per roadmap § 3.6)
- Observer calling skills
- Observer doing any writes beyond `heartbeat` and `discovery`
- Automatic DH spawning by another DH
- Per-DH separate LLM provider
- Persona editor UI
- Discovery-usefulness rating UI

---

## 11. Risks (S1-specific, complementing roadmap § 5)

| Risk | Mitigation |
|------|------------|
| Observer's ContextBuilder pulls too much data → cost explosion | Hard cap `git_log_2h` and any log file reads to 4KB each. Cap total prompt to 12KB. |
| DDL migration on production `agent.db` fails mid-way | Run against a fresh copy first (`cp agent.db /tmp/migration-test.db; sqlite3 /tmp/...`); migration script is idempotent (IF NOT EXISTS for indexes, ADD COLUMN in SQLite is naturally idempotent if we `try/except`). |
| Cmux can't handle 2 concurrent named sessions | Verified on dev laptop before shipping; rollback = disable observer in config. |
| Observer identity drifts (starts producing deliverables) | Server-side role-permission middleware hard-rejects disallowed calls (§8.4). Logged + alerted. |
| Existing callers break because they pass no `digital_human_id` | DEFAULT 'executor' on column + default param in helpers means unchanged callers keep working. Covered by migration test. |

---

## 12. Implementation order (high level; detailed steps in plan)

1. DDL migration + backfill verification (idempotent script)
2. DB helper API gains `digital_human_id` parameter (default preserves behavior)
3. Move `persona/*.md` → `persona/executor/*.md`; update ContextBuilder caller
4. Introduce `digital_humans/` directory + `state.json` read/write
5. Lifecycle API endpoints
6. Role-permission middleware
7. Observer identity prompt + Observer persona files
8. `ObserverEngine` module
9. Observer runtime context + prompt template
10. Wire `ObserverEngine` into the server lifespan (start on boot)
11. UI: DH filter on list pages
12. UI: `/digital_humans` list + detail pages
13. UI: DH status strip on `/overview`
14. Live validation week — collect 7+ days of operation, measure against exit criteria

Detailed implementation plan lives in `docs/specs/plans/2026-04-24-s1-observer.md` (to be written after this spec is reviewed and approved).

---

_S1 brainstorm: 2026-04-24._
