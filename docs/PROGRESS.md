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

### tmux residuals (audit result — Task 9, 2026-04-24)

**Summary**: docs layer 54 hits, code layer 99 hits. Stop-loss rule triggered (docs >20) — sites catalogued below rather than annotated one-by-one.

#### Docs layer breakdown (`rg -c "tmux" -g '*.md'`)

| File | Hits | Classification | Action |
|------|------|----------------|--------|
| `docs/specs/plans/2026-04-24-stabilization-sprint.md` | 23 | Meta — this sprint discussing tmux migration | None, expected |
| `docs/specs/2026-04-24-stabilization-sprint-design.md` | 7 | Meta — this sprint's spec | None, expected |
| `README.md` | 5 | Project readme — may still describe tmux setup | **Needs update (next round)** |
| `README_CN.md` | 5 | Chinese readme | **Needs update (next round)** |
| `docs/specs/2026-03-13-myagent-v2-design.md` | 5 | Superseded v2 spec; banner notes legacy | None, banner sufficient |
| `docs/PROGRESS.md` | 2 | This file's catalog | None, expected |
| `docs/OVERVIEW.md` | 2 | Mentions "formerly tmux" explicitly | None, contextual |
| `docs/specs/SPEC_LEDGER.md` | 1 | Ledger note on cmux migration | None, contextual |
| `docs/specs/2026-03-11-chat-survival-system-design.md` | 1 | Superseded; banner says "tmux references are legacy" | None, banner sufficient |
| `docs/plans/2026-03-13-phase1-tailwind-migration.md` | 1 | Old plan, historical | None |
| `docs/ARCHITECTURE.md` | 1 | Mentions "formerly tmux" explicitly | None, contextual |
| `CLAUDE.md` | 1 | Mentions "formerly tmux" explicitly | None, contextual |

**Net actionable docs residuals**: `README.md` + `README_CN.md` (10 hits total). Deferred to a follow-up "docs polish" round.

#### Code layer breakdown (`rg -c "tmux" -g '*.py' -g '*.ts' -g '*.tsx' -g '*.js'`)

| File | Hits | Classification |
|------|------|----------------|
| `myagent/server.py` | 61 | Active code — migration partial, still references tmux in some paths |
| `tests/test_survival.py` | 31 | Legacy tmux-era tests — commit `2da6592` says "skip pending cmux rewrite" |
| `myagent/ai_provider.py` | 4 | Provider abstraction references |
| `web/dist/assets/index-B5hKc0s6.js` | 2 | Built artifact — will regenerate on next build |
| `web/src/pages/Chat.tsx` | 1 | Frontend reference |

**Net actionable code residuals**: ~96 hits (excluding built JS). This is the scope of a future tmux→cmux code-migration round, not this stabilization sprint. Per spec §2.2, code is not touched here.

#### Recommended follow-up tasks (not in this sprint)

1. **README rewrite** — align `README.md` + `README_CN.md` with cmux/codex/tailwind. Est. 30 min.
2. **`myagent/server.py` tmux audit** — identify whether 61 hits are legacy comments, dead code, or actively-used paths. Grep-and-classify, 1–2 hours.
3. **`tests/test_survival.py` rewrite** — cmux equivalent of legacy tmux tests. Est. 2–4 hours.
4. **`myagent/ai_provider.py` + `Chat.tsx` cleanup** — small surface, likely 15 min each.

---

_Last updated: 2026-04-24 (stabilization sprint step 4)._
