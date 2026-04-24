# MyAgent V2 — Phase Progress Ledger

> Live completion ledger for the 5-phase V2 redesign from `docs/OVERVIEW.md § 8`.
> Updated by hand after each meaningful milestone.

**Overall V2 completion: 5/5 phases have meaningful implementation, 1 phase (Phase 5) still has open sub-items.**

Legend: ✅ done · 🚧 partial · ⬜ not started

---

## Phase 1: Tailwind + icon sidebar + dark/light

**Status: ✅ done**

Evidence:
- `web/tailwind.config.ts`, `web/postcss.config.js`, `web/src/index.css` with `@tailwind` directives
- `web/src/contexts/ThemeContext.tsx` implements dark/light mode
- Lucide icons used across 15+ pages (`rg -l "lucide" web/src/pages/`)
- Ant Design is being incrementally removed — ongoing (see CLAUDE.md migration note)

Next:
- Finish removing remaining Ant Design imports (tracked outside this sprint)

---

## Phase 2: Rewrite existing pages

**Status: ✅ done**

Evidence — all 6 planned pages exist under `web/src/pages/`:
- `Dashboard.tsx` (Overview), `Chat.tsx`, `Sessions.tsx`, `Survival.tsx` (Engine), `Tasks.tsx`, `Memory.tsx`
- Plus additional pages introduced post-V2: `Knowledge.tsx`, `PromptEditor.tsx`, `ScheduledTasks.tsx`, `Supervisor.tsx`, `Extensions.tsx`, `SessionDetail.tsx`, `Guide.tsx`, `Settings.tsx`

Next:
- Verify each page uses Tailwind-only (no mixed Ant Design) — separate audit task, not in this sprint

---

## Phase 3: Self-Report API

**Status: ✅ done**

Evidence:
- 6 DB tables exist in `myagent/db.py`: `agent_heartbeats`, `agent_deliverables`, `agent_discoveries`, `agent_workflows`, `agent_upgrades`, `agent_reviews` (grep confirms all 6 have INSERT + SELECT helpers)
- Endpoints wired in `myagent/server.py` (grep: heartbeat/deliverable/discovery references)
- `myagent/survival.py:1` module docstring: "heartbeat-aware autonomous AI agent supervisor" — agent calls back via API, not via log scraping

Next:
- Add `digital_human_id` column to each table (migration planned for next-round multi-digital-human spec, NOT this sprint)

---

## Phase 4: Three new pages (Output / Workflows / Capabilities)

**Status: ✅ done**

Evidence:
- `web/src/pages/Output.tsx` exists
- `web/src/pages/Workflows.tsx` exists
- `web/src/pages/Capabilities.tsx` exists

Next:
- Verify Capabilities page writes config back to DB and identity prompt re-reads on next render (visual test, outside this sprint)

---

## Phase 5: Integration (bus-driven watchdog, context-aware nudges, semantic Feishu, context-aware restart, chokidar scan)

**Status: 🚧 partial — core integration done, full audit pending**

Evidence (done):
- `myagent/survival.py:5-9` docstring lists all 5 integration deliverables (heartbeat-first detection, capture-pane fallback, context-aware nudges, semantic Feishu reports, context recovery on restart)
- `_build_context_nudge` at `survival.py:209` and `_build_no_heartbeat_nudge` at `survival.py:250` — both implemented
- Timeout thresholds defined: `HEARTBEAT_WARN_TIMEOUT = 600`, `HEARTBEAT_CRITICAL_TIMEOUT = 900`
- Feishu client integration in `myagent/feishu.py` + survival invocation at `survival.py:329`
- `myagent/scanner.py` handles session watching (equivalent to chokidar pattern)
- Recent commits `0bc97b2`, `93d0ebc`, `b225760` touched watchdog, tmux→cmux migration, Feishu/WS wiring

Open sub-items:
- Semantic Feishu report format vs the mock in `OVERVIEW § 4.4` — needs side-by-side verification
- Context-aware restart: confirm `--resume` path injects recovery message (no grep match for "recovery" keyword; may be using different variable name)

Next:
- Side-by-side compare live Feishu output vs `OVERVIEW § 4.4` mock
- Trace restart flow for recovery-message injection
- Both verifications deferred to next work session, not this stabilization sprint

---

## Cross-phase residuals

### tmux residuals (pre-audit count from Task 9 step 9.1)

- **Docs layer**: 47 hits across `*.md` files (>20 threshold → stop-loss applies, see Task 9)
- **Code layer**: 99 hits across `*.py` / `*.ts` / `*.tsx` / `*.js` files
  - Current policy: code residuals are catalogued but not touched this round (per spec §2.2 non-goals)
  - Catalog will be appended below after Task 9 runs

(Catalog appended by Task 9 on completion.)

---

_Last updated: 2026-04-24 (stabilization sprint step 4)._
