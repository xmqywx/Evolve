# Spec Ledger

> Status of every spec file in `docs/specs/`. Updated when any spec's status changes.
> Authoritative master design: `docs/OVERVIEW.md`.

Status values:
- **Active** — current, authoritative
- **Partial** — partially superseded; some sections still current, see notes
- **Superseded** — replaced by a newer document; kept for historical reference
- **Deprecated** — abandoned; do not consult

---

| Spec File | Date | Status | Superseded By | Notes |
|-----------|------|--------|---------------|-------|
| `2026-03-10-session-monitor-design.md` | 2026-03-10 | Superseded | `docs/OVERVIEW.md` | Session list + monitoring UI. Absorbed into OVERVIEW § Sessions & Monitoring. |
| `2026-03-11-chat-survival-system-design.md` | 2026-03-11 | Superseded | `docs/OVERVIEW.md` | Chat + survival engine (tmux era). Absorbed into OVERVIEW § Survival Engine Upgrades. Contains tmux references — provider has since moved to codex + cmux. |
| `2026-03-13-myagent-v2-design.md` | 2026-03-13 | Superseded | `docs/OVERVIEW.md` | V2 main trunk. OVERVIEW is the merged/refined version. |
| `2026-03-14-workflow-v2-design.md` | 2026-03-14 | Superseded | `docs/OVERVIEW.md` | Workflows page + workflow store. Absorbed into OVERVIEW § Workflows Subsystem. |
| `2026-03-15-knowledge-hub-design.md` | 2026-03-15 | Superseded | `docs/OVERVIEW.md` | Memory / knowledge hub. Absorbed into OVERVIEW § Memory / Knowledge Hub. |
| `2026-04-24-stabilization-sprint-design.md` | 2026-04-24 | Completed | — | Documentation cleanup round (executed 2026-04-24). Prepared ground for multi-DH roadmap. |
| `2026-04-24-multi-digital-human-roadmap.md` | 2026-04-24 | Active | — | Multi-DH roadmap: 3 stages (S1 Observer, S2 Planner+Conductor, S3 Evolver). Only S1 is designed in detail. |
| `2026-04-24-s1-observer-digital-human.md` | 2026-04-24 | Active — code complete, live validation pending | — | Stage 1 detailed design: add Observer DH + land shared contracts (`digital_human_id`, per-DH persona/runtime dirs). Implementation 13/14 tasks done; 7-day validation window next. |

---

## Plans

Implementation plans live under `docs/specs/plans/`:

| Plan | Parent Spec | Status |
|------|-------------|--------|
| `plans/2026-03-16-knowledge-hub-remaining.md` | `2026-03-15-knowledge-hub-design.md` | See file head |
| `plans/2026-03-16-remaining-fixes.md` | V2 follow-up | See file head |
| `plans/2026-04-24-stabilization-sprint.md` | `2026-04-24-stabilization-sprint-design.md` | Completed |
| `plans/2026-04-24-s1-observer.md` | `2026-04-24-s1-observer-digital-human.md` | Active — code complete, validation pending |

---

## ADRs

Decisions live under `docs/decisions/`:

| ADR | Subject | Status |
|-----|---------|--------|
| `2026-04-24-storage.md` | SQLite as source of truth, Postgres scheduled for removal | Accepted |
| `2026-04-24-roles-boundary.md` | Three-layer role architecture (persona / skills / digital_humans) | Accepted |

---

_Last updated: 2026-04-24 (stabilization sprint step 2a)_
