# MyAgent — Unified Design Overview

> **Status**: Active. Authoritative master design for MyAgent, merged 2026-04-24.
> **Supersedes**: `specs/2026-03-10-session-monitor-design.md`, `specs/2026-03-11-chat-survival-system-design.md`, `specs/2026-03-13-myagent-v2-design.md`, `specs/2026-03-14-workflow-v2-design.md`, `specs/2026-03-15-knowledge-hub-design.md`. Old specs kept for implementation detail reference.
> **Pair docs**: `ARCHITECTURE.md` (map), `PROGRESS.md` (phase ledger), `specs/SPEC_LEDGER.md` (spec status), `decisions/*.md` (ADRs).

---

## 1. Product Positioning

**MyAgent is an AI control plane, not a monitor.**

- Monitor = I watch the agent work.
- Control = I define what it does, how it does it, and to what standard. It runs. I collect.

MyAgent is Ying's personal AI command center — a web dashboard over a long-running, evolvable AI employee.

### 1.1 Six fatal problems this design solves
1. No "soul" UI — the dashboard doesn't show what the agent is doing or producing.
2. Agent is a black box — scrolling terminal text only; no status/progress/next-step.
3. No deliverable management — outputs scattered across the filesystem.
4. Hardcoded config — behavior changes require code edits and restarts.
5. UI looks like a back-office admin panel, not a command cockpit.
6. Fragmented "roles" — persona / skill-cards / survival-engine prompt all disconnected.

---

## 2. Self-Report Event Bus

**The architectural backbone.** Every agent→human signal goes through one bus. All digital humans write here. UI, watchdog, Feishu reporter, knowledge engine all read from here.

### 2.1 Bus framing

Classic agent systems scrape terminals or tail logs. MyAgent inverts this: **the agent calls back via HTTP**, structured, on its own schedule. This eliminates ANSI-parsing, makes the UI a pure consumer, and — critically — **allows multiple digital humans to share the same substrate** by tagging events with a `digital_human_id`.

Current state: one digital human (the survival engine) writes events. Future: N digital humans write events, each tagged.

### 2.2 Six endpoints

| Endpoint | Purpose | Key fields |
|----------|---------|-----------|
| `POST /api/agent/heartbeat` | Current activity | `activity` (researching\|coding\|writing\|searching\|deploying\|reviewing\|idle), `description`, `task_ref`, `progress_pct`, `eta_minutes` |
| `POST /api/agent/deliverable` | Produced artifact | `title`, `type` (code\|research\|article\|template\|script\|tool), `status` (draft\|ready\|published\|pushed), `path`, `summary`, `repo`, `value_estimate` |
| `POST /api/agent/discovery` | Valuable insight | `title`, `category` (opportunity\|risk\|insight\|market_data), `content`, `actionable`, `priority` (high\|medium\|low) |
| `POST /api/agent/workflow` | Reusable pipeline | `name`, `trigger` (manual\|scheduled\|on_event), `steps[]`, `enabled` (default false — user approves in UI) |
| `POST /api/agent/upgrade` | Self-improvement proposal | `proposal`, `reason`, `risk`, `impact`, `status` (pending\|approved\|rejected) |
| `POST /api/agent/review` | Periodic retrospective | `period`, `accomplished[]`, `failed[]`, `learned[]`, `next_priorities[]`, `tokens_used`, `cost_estimate` |

### 2.3 Storage

SQLite tables, one per endpoint (see `docs/decisions/2026-04-24-storage.md`):
- `agent_heartbeats` — latest + history
- `agent_deliverables`
- `agent_discoveries`
- `agent_workflows` (expanded schema in § 5)
- `agent_upgrades`
- `agent_reviews`

Future addition for multi-digital-human: every row gains a `digital_human_id` column; endpoints gain a `digital_human_id` field (defaults to `"survival"` for back-compat).

### 2.4 Prompt integration

The identity prompt tells the agent:
- New task → `heartbeat`
- Artifact produced → `deliverable`
- Valuable info found → `discovery`
- Reusable pattern designed → `workflow`
- New capability needed → `upgrade`
- End of work round (or 2h mark) → `review`
- Call pattern: `curl -X POST http://localhost:3818/api/agent/<kind> -H "Content-Type: application/json" -d '{...}'`
- **Not reporting = work didn't happen.**

### 2.5 Future: multi-digital-human on the same bus

When the next-round spec introduces multiple digital humans (planner / executor / observer / evolver), each runs its own cmux session, each has its own persona, and each calls the **same** 6 endpoints tagged with its `digital_human_id`. The bus stays unchanged. UI pages start showing per-role filters. The supervisor/conductor digital human reads the bus and emits `workflow` events to assign the next goal — no new endpoints needed.

This is why Self-Report is architected as a bus now, even though only one producer exists today.

---

## 3. Three New UI Pages

### 3.1 Output (产出)

Consumes `agent_deliverables`. Grouped by `type` (code / research / article / template). Card view: title + status badge + summary + repo link. Filters: type, status, time range. Actions: mark status change, open file path, view on GitHub.

### 3.2 Workflows (工作流)

Consumes `agent_workflows`. List view: name, trigger, step count, enabled state. Toggle switch per row. Expand for step detail. New workflows from the agent default to `enabled: false` with "pending approval" badge. See § 5 for data model.

### 3.3 Capabilities (能力)

Three sections:

**Capability toggles** — from DB-backed config:
- `browser_access`, `code_execution`, `file_write` (+ scope config), `git_push`, `spend_money` (+ limit), `feishu_notify`, `install_packages`

**Behavior sliders** —
- Autonomy: `conservative | balanced | aggressive`
- Report frequency: `every_step | milestone | result_only`
- Risk tolerance: `safe_only | moderate | experimental`
- Work rhythm: `deep_focus | balanced | multi_task`

**Upgrade proposals** — pending rows from `agent_upgrades`. User approves/rejects.

Config changes write to DB; identity prompt reads from DB on next render.

---

## 4. Survival Engine Upgrades

### 4.1 Current pain points (pre-upgrade)

| Area | Current | Problem |
|------|---------|---------|
| Idle detection | cmux capture-pane text diff | Thinking screens don't change; off-screen output missed |
| Nudge message | Fixed "continue, check plans/" | No context |
| Feedback | One-way send-keys, fire-and-forget | No delivery confirmation |
| Feishu report | Raw terminal screenshot | ANSI noise, truncated, no semantics |
| Restart | Blind `--resume` | Agent must re-remember context |
| Goal awareness | "Go do stuff" | No definition of done |

### 4.2 Replace screen-watching with the bus

Once heartbeat is live, watchdog stops needing capture-pane as primary signal.

```
Every 10s check last heartbeat timestamp:
  < 5 min   → normal, no action
  5–10 min  → possibly stuck, gentle reminder (once)
  > 10 min  → confirmed stuck, context-aware nudge
  never     → agent didn't call API, tell it to report
```

capture-pane kept as fallback for "bus silent" case only.

### 4.3 Context-aware nudges

Old: `继续工作。检查 plans/ 目录...`

New: `你上次汇报在 8 分钟前，当时在做「分析 Upwork 定价」(进度 40%)。继续这个任务。完成后调 deliverable API 提交成果，然后调 heartbeat 汇报下一步。`

If no heartbeat → fall back to reading latest plan file in `plans/`.

### 4.4 Semantic Feishu reports

Aggregate from DB, not screenshot:

```
🔥 生存引擎 15:30 进展报告
━━━━━━━━━━━━━━━━━━━━
📍 当前：分析 Upwork 定价 (60%)
📦 今日产出：2 个交付物，1 个发现
💡 最新发现：Polar.sh 佣金仅 4%（高优先级）
🔄 下一步：准备 Upwork proposal 模板
💰 Token：约 35k（≈$1.05）
```

### 4.5 Context-aware restart

On unexpected exit, read latest heartbeat + deliverables + review from DB, inject recovery message into the resumed session:

```
你在 15:23 意外退出。恢复上下文：
- 最后任务：分析 Upwork 定价 (40%，来自 heartbeat)
- 已完成产出：n8n 模板包（来自 deliverables）
- 最近复盘：Chrome extension 上架被拒，转 Polar.sh（来自 review）
从断点继续。
```

### 4.6 ChatManager + ContextBuilder + ProfileBuilder

(Absorbed from `specs/2026-03-11-chat-survival-system-design.md` — see that file for field-level detail.)

- **ChatManager**: multi-turn conversations with Claude/Codex, context window management, history table.
- **ContextBuilder**: composes runtime prompt from persona + latest state + current task + skill library.
- **ProfileBuilder**: offline crawler that reads Ying's data sources (Slack, WeChat local DB on Mac, git history, terminal history, browser history) to ground the agent's "who you serve" knowledge. Opt-in, runs on schedule.

Provider: `codex` by default (`config.yaml: survival.provider`). Claude CLI supported as alternate. Terminal: `cmux` (formerly tmux, see `ARCHITECTURE.md § 7`).

---

## 5. Workflows Subsystem

Workflows = agent's **self-authored skill library**. The agent designs a repeatable pipeline, user approves, it becomes a callable skill.

### 5.1 Data model

`agent_workflows` (redesigned, see `specs/2026-03-14-workflow-v2-design.md` for full migration):
- `id`, `name`, `description`
- `trigger` (manual / scheduled / on_event), `trigger_config` (cron, event name)
- `steps` (JSON array of step objects)
- `enabled` (bool, default false for agent-authored)
- `created_by` (agent / user)
- `last_run_at`, `last_run_status`
- `version` (incremented on edit)

**Step object**:
```json
{
  "id": "step-1",
  "action": "web_search | write_article | save_deliverable | run_shell | llm_call | ...",
  "params": { /* action-specific */ },
  "on_success": "step-2",
  "on_failure": "abort | continue | retry"
}
```

`agent_workflow_runs` (new):
- `id`, `workflow_id`, `version`, `trigger_type`
- `started_at`, `finished_at`, `status` (running / success / failed / cancelled)
- `step_results` (JSON array of per-step outcome + output + tokens)
- `error_message`

### 5.2 API

CRUD on `/api/workflows` (list / create / update / enable / disable / delete). Execution on `/api/workflows/{id}/run`. Run history on `/api/workflows/{id}/runs`.

### 5.3 Agent integration

Identity prompt is injected with **skill library summary** — one-line-per-workflow list of enabled workflows the agent can invoke by name. Calling a workflow is: `POST /api/workflows/<name>/run` with params.

### 5.4 Implementation detail reference

See `specs/2026-03-14-workflow-v2-design.md` for table migration SQL, full API schemas, and UI mockups.

---

## 6. Memory / Knowledge Hub

The knowledge hub is **the agent's persistent learned experience**, distilled from review + discovery events and injected back into future prompts.

### 6.1 Three-layer injection

Prompt composed from:
1. **Identity + rules** (~400 chars, from `persona/identity.md` + `principles.md`)
2. **API cheatsheet** (~800 chars, variable-templated)
3. **Knowledge base** (~5000–6500 chars, three-tier injection):
   - Core lessons (strict rules)
   - Recently learned
   - Task-relevant excerpts

Plus: current task env (~1000 chars), capability/behavior config (~500 chars), start directive (~100 chars).

### 6.2 Data model

`knowledge_base` table:
- `id`, `category` (lesson / api / insight / rule / skill), `title`, `content`
- `source` (review / discovery / manual)
- `source_ref` (FK to agent_reviews.id or agent_discoveries.id)
- `tier` (core / recent / contextual)
- `created_at`, `last_used_at`, `use_count`

### 6.3 KnowledgeEngine module (`myagent/knowledge.py`)

- CRUD on `knowledge_base`
- **Extraction pipeline**: on `review` or `discovery` event, call LLM with an extraction prompt to convert narrative into atomic knowledge entries
- **Injection**: called by ContextBuilder when composing the next prompt; selects top-K by relevance and tier

### 6.4 Collection hooks

- `review` endpoint appends extraction job to queue
- `discovery` endpoint appends extraction job to queue
- Hourly scan of `plans/` directory for manually-added notes
- Daily 22:00 session analysis runs in the `_supervisor_loop`

### 6.5 Dashboard page

`Knowledge.tsx` — view / edit / tier-promote / demote / delete entries. API: `/api/knowledge/*`.

### 6.6 Implementation detail reference

See `specs/2026-03-15-knowledge-hub-design.md` for the full extraction prompt template, prompt-assembly order, and migration plan.

---

## 7. Sessions & Monitoring

### 7.1 Hybrid mode

MyAgent tracks two kinds of Claude/Codex sessions:
1. **Managed** sessions (started by MyAgent itself via cmux)
2. **External** sessions (Ying running `claude` directly in a terminal, picked up by the scanner)

Both appear in the UI and on the bus.

### 7.2 Modules

- `myagent/scanner.py` — watches `~/.claude/projects/` for JSONL changes (chokidar-equivalent via Python watcher)
- `myagent/session_registry.py` — in-memory + DB registry of all known sessions
- `myagent/ws_hub.py` — WebSocket fan-out for live session events to the UI

### 7.3 UI pages

- `/sessions` — list of all sessions with status, last activity, token usage
- `/sessions/{id}` — detail view with message stream, resume/kill actions
- Mobile-friendly (future scope; current: desktop first)

### 7.4 Feishu integration

Commands via bot:
- `/status` → current agent state summary
- `/sessions` → active session list
- `/resume <id>` → resume a session

Proactive notifications on: long idle, error thresholds, upgrade proposals pending.

### 7.5 Implementation detail reference

See `specs/2026-03-10-session-monitor-design.md` for API schemas, Feishu card format, and auth model.

---

## 8. Phase Plan (V2 redesign)

Five phases — live status in `docs/PROGRESS.md`.

1. **Tailwind + icon sidebar + dark/light** — base layout
2. **Rewrite existing pages** — Overview, Chat, Sessions, Engine, Tasks, Memory
3. **Self-Report API** — 6 endpoints + DB tables + prompt wiring
4. **Three new pages** — Output, Workflows, Capabilities
5. **Integration** — watchdog on bus, context-aware nudges, semantic Feishu, context-aware restart, chokidar session scan

Next-round spec will add phase 6: **multi-digital-human architecture** on top of the bus.

---

## 9. Tech Stack & Constraints

- Backend: Python 3.12+ / FastAPI / SQLite / uvicorn
- Frontend: React + TypeScript + Vite + Tailwind (migrating from Ant Design)
- Terminal: xterm.js + **cmux** (formerly tmux)
- Provider: **codex** default, claude supported (`config.yaml: survival.provider`)
- Storage: **SQLite** (`agent.db`) is source of truth. Postgres being removed — see `docs/decisions/2026-04-24-storage.md`.
- Virtual env: `.venv`
- Git: every meaningful change committed AND pushed to `xmqywx/Evolve`

Do not:
- Multi-tenant
- Multi-provider routing (only codex/claude swap)
- Mobile-first (desktop first, mobile is best-effort)
- i18n framework (text is bilingual inline, no framework)

---

## 10. Open Questions (not resolved in this round)

Surfaced during the spec merge; queued for next-round design:

1. **Persona vs knowledge hub overlap** — `persona/knowledge.md` and `knowledge_base.tier=core` both contain "core rules Ying wants the agent to follow". Which wins on conflict? Proposed: persona is **immutable rules** (Ying authors), knowledge is **learned** (agent authors). But the boundary is fuzzy.
2. **Workflows vs skill agents** — `agent_workflows` (DB-backed pipelines) and `agents/*.md` skill cards (markdown prompts) both represent "callable skills". Should workflows eventually supersede skill cards, or remain orthogonal? Deferred to multi-digital-human spec.
3. **digital_human_id back-compat** — adding the column means every existing row gets `"survival"` as default. Safe for V2, but multi-DH spec must define role-discovery precisely.
4. **Prompt size ceiling** — three-layer injection targets ~8000 chars; codex / claude context windows allow far more, but cost grows linearly. Ceiling enforcement deferred.
5. **Upgrade approval latency** — if Ying is away, upgrade proposals sit pending. Should the agent have a "grace list" of low-risk auto-approved upgrade categories? Deferred.

---

## 11. Pointers

- System map & vocabulary: `docs/ARCHITECTURE.md`
- Phase completion: `docs/PROGRESS.md`
- Spec status index: `docs/specs/SPEC_LEDGER.md`
- ADRs: `docs/decisions/`
- Active cleanup plan: `docs/specs/plans/2026-04-24-stabilization-sprint.md`
- Old specs (reference only): `docs/specs/2026-03-*.md` — each has a Superseded banner pointing here

---

_Last updated: 2026-04-24 (stabilization sprint step 3)._
