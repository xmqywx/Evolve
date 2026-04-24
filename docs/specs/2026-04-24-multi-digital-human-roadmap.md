# Multi-Digital-Human Roadmap — Design Spec

> **Status**: Active
> **Date**: 2026-04-24
> **Supersedes**: N/A (first multi-DH spec)
> **Pair docs**: `docs/OVERVIEW.md § 2.5` (forward reference), `docs/decisions/2026-04-24-roles-boundary.md` (three-layer role ADR), `docs/ARCHITECTURE.md § 2` (vocabulary)
> **Relation to stabilization sprint**: This spec builds on the stabilization sprint (2026-04-24). The sprint prepared the ground (vocabulary, ADRs, bus framing); this spec starts construction.

---

## 1. Context

MyAgent today runs a single long-running "digital human" — the survival engine (cmux + codex). All design work to date treats this as a singleton. This spec launches the transition to **multiple concurrent digital humans**, each with its own cmux session, persona, and role, all sharing the Self-Report event bus as their coordination substrate.

The transition is **staged**, not one-shot. Each stage produces a working, observable system that can be stopped or reverted before the next.

---

## 2. Three Stages

| Stage | New Digital Humans | Architectural delta | What it validates |
|-------|-------------------|---------------------|-------------------|
| **S1 — Dual-DH baseline** | Executor (renamed from "survival") + Observer (new, read-only) | `digital_human_id` column on all 6 `agent_*` tables; persona directory split into per-DH subdirs; `digital_humans/` runtime state directory; Observer cmux + identity prompt; UI per-DH filter | Two LLM sessions coexist stably; bus ID isolation works; Observer discoveries have real value |
| **S2 — Add Planner + Conductor** | Planner (emits workflow events, does not execute) + Conductor (thin arbitration role, decides "who acts next") | Conductor role; workflow events become scheduling signals rather than just "reusable pipelines" | LLM-driven task orchestration works (vs hardcoded SOP) |
| **S3 — Evolver joins** | Evolver (cron-triggered, reads traces, opens PRs modifying skill/prompt/config) | Pareto-evolution pipeline (Hermes GEPA-style); PR-only, never auto-merge | ≥30 days of accumulated trace data produces actually-useful self-improvement proposals |

**Each stage gets its own brainstorm → spec → plan → execute cycle.** S2 and S3 are explicitly *not* designed in this spec — they may evolve based on what S1 reveals.

---

## 3. Shared Contracts (land in S1, unchanged through S3)

These decisions are locked once S1 ships and are not revisited in later stages.

### 3.1 Event bus ID tagging

All 6 `agent_*` tables (`agent_heartbeats`, `agent_deliverables`, `agent_discoveries`, `agent_workflows`, `agent_upgrades`, `agent_reviews`) receive a new column:

```sql
ALTER TABLE agent_<kind> ADD COLUMN digital_human_id TEXT NOT NULL DEFAULT 'executor';
```

- Every row is tagged with the originating DH's ID.
- Historical rows are backfilled to `'executor'` (the survival engine's ID).
- DB helper methods (`db.py`) accept a `digital_human_id` parameter; all existing callers pass `'executor'`.
- API endpoints either accept `digital_human_id` in the body or infer it from an auth token mapping (S1 will use body parameter; auth mapping deferred).

### 3.2 Persona layer layout

```
persona/
├── executor/
│   ├── identity.md
│   ├── knowledge.md      (minimal version from stabilization sprint)
│   └── principles.md     (minimal version from stabilization sprint)
└── observer/
    ├── identity.md       (new, S1)
    ├── knowledge.md      (new, S1 — shares knowledge with Executor for now)
    └── principles.md     (new, S1)
```

`ContextBuilder` receives a `digital_human_id` and reads the matching subdirectory. Single-persona legacy paths (`persona/knowledge.md`) are removed; any loader still referencing them fails loudly rather than silently falls back.

### 3.3 Skill layer

`agents/*.md` (conceptually "skills") remain a shared library. Each DH's `identity.md` declares a **whitelist** of skill names it may call. The server enforces: when a DH requests a skill not on its whitelist, the call is rejected with a clear error. (This is the runtime half of the three-layer architecture ADR.)

### 3.4 Digital Human runtime layer

```
digital_humans/
├── executor/
│   └── state.json     # { "cmux_session": "...", "started_at": "...", "restart_count": N, "provider": "codex" }
└── observer/
    └── state.json
```

`state.json` is read/written by the server on DH lifecycle transitions. Crash recovery consults it to restore session IDs.

### 3.5 Digital Human lifecycle API

```
GET  /api/digital_humans                    # list all configured DHs + current state
POST /api/digital_humans/{id}/start
POST /api/digital_humans/{id}/stop
POST /api/digital_humans/{id}/restart
```

Config section in `config.yaml`:
```yaml
digital_humans:
  executor:
    persona_dir: persona/executor
    cmux_session: mycmux-executor
    provider: codex
    heartbeat_interval_secs: 600
    enabled: true
  observer:
    persona_dir: persona/observer
    cmux_session: mycmux-observer
    provider: codex
    heartbeat_interval_secs: 1800
    skill_whitelist: []        # Observer calls no skills in S1
    enabled: true
```

### 3.6 DH-to-DH communication rule

**All inter-DH coordination goes through the event bus**. No direct DH-to-DH message channel. A DH learns about another DH's activity by reading bus events filtered by `digital_human_id`. This constraint is permanent — all stages respect it.

---

## 4. Non-Goals (this roadmap + all stages unless later overturned)

- ❌ Multi-machine deployment
- ❌ DH-to-DH direct message channel (bus only)
- ❌ User-visible DH persona editor (future UX iteration)
- ❌ Different LLM providers per DH (all use codex; swap is via `config.yaml: survival.provider` globally)
- ❌ Role-switching inside a single cmux session (one DH = one session, always)
- ❌ Automated DH spawning by the agent itself (only Ying or a config change creates new DHs)

---

## 5. Risks and Stop-Loss

| Risk | Trigger | Action |
|------|---------|--------|
| Observer output is noise | After 50+ discoveries, abolish manual review finds <10% "actually useful" | Tune Observer prompt/context; do not progress to S2 |
| Cost explosion | Daily token budget >$15 sustained for 3 days | Raise Observer heartbeat interval; if still >$15, disable Observer |
| Dual-cmux instability | Observer restart count >10 per week | Root-cause (macOS pty limits? launchctl conflict?); do not progress to S2 until resolved |
| DDL migration failure | `ALTER TABLE` errors or row corruption | Restore from `backups/` (existing auto-backup); rollback the migration commit |
| Loop storm | Observer writes discoveries at >1/minute sustained | `INSERT OR IGNORE` via `dedup_key` should suppress; if bypass observed, halt Observer |
| Persona drift | Any prompt sent to Observer contains Executor-specific text (or vice-versa) | Regression in `ContextBuilder`; fix before any multi-DH change ships |

**Hard stop**: if any of the S1 exit criteria (see §6) fails for 2 consecutive weeks of attempted fixes, the roadmap pauses and we reassess the whole approach (possibly reverting to single-DH).

---

## 6. Progression Rules

Each stage has **exit criteria** (defined in its own sub-spec). The roadmap-level rule is:

- **S1 → S2**: requires S1 exit criteria met (see `docs/specs/2026-04-24-s1-observer-digital-human.md § 9`)
- **S2 → S3**: criteria defined in the S2 spec (not written in this round)
- **Abandoning**: any stage can be reverted. Because all coordination is via the bus and DH entries in `config.yaml`, removing a DH is: set `enabled: false`, stop its cmux, clean up `digital_humans/{id}/`. Data stays in `agent_*` tables for posterity.

---

## 7. Documentation Contracts

When each stage ships:
- Update `docs/OVERVIEW.md § 2.5` to reflect current DH count
- Update `docs/ARCHITECTURE.md § 2` vocabulary if terms evolve
- Update `docs/PROGRESS.md` with the new ledger entries
- Add the stage spec to `docs/specs/SPEC_LEDGER.md`
- File an ADR for any irreversible decision that wasn't in this roadmap

---

## 8. First Sub-Spec

The Stage 1 design lives in `docs/specs/2026-04-24-s1-observer-digital-human.md`. It contains the full Observer design, UI changes, DDL migrations, and exit criteria. S2 and S3 sub-specs do not exist yet and will be brainstormed after S1 ships.

---

_Roadmap brainstorm: 2026-04-24. Next action: S1 sub-spec + plan + execution._
