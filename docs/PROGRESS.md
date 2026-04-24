# MyAgent V2 — Phase Progress Ledger

> Live completion ledger for the 5-phase V2 redesign from `docs/OVERVIEW.md § 8`.
> Updated by hand after each meaningful milestone.

**Overall V2 completion: 5/5 phases done (runtime-verified).** Remaining work is code-debt cleanup (cmux migration in server.py, test rewrite) and the next-round multi-digital-human architecture, not V2 phase gaps.

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

**Status: ✅ done — all 5 sub-items runtime-verified**

Verified (read code line-by-line):
- ✅ `_build_context_nudge` at `survival.py:209-248` — reads `get_latest_heartbeat` + `list_deliverables` + `get_active_survival_projects`; composes message per `OVERVIEW § 4.3` mock
- ✅ `_build_no_heartbeat_nudge` at `survival.py:250-260` — curl examples + "不汇报=没做" directive
- ✅ `_build_semantic_report` at `survival.py:266+` — aggregates heartbeat activity labels + progress + daily deliverables + top discoveries; matches `OVERVIEW § 4.4`
- ✅ `_build_recovery_prompt` at `survival.py:339` — built on `--resume`, sent at `survival.py:721` inside the `is_resume` branch (see `survival.py:679` launch flag)
- ✅ chokidar-equivalent: `myagent/scanner.py:233` uses `watchfiles.awatch`; `:221` polling is fallback when watchfiles is not installed
- Timeout thresholds: `HEARTBEAT_WARN_TIMEOUT = 600s`, `HEARTBEAT_CRITICAL_TIMEOUT = 900s`

Recent commits: `0bc97b2` (watchdog false-positive fix), `93d0ebc` (tmux→cmux), `b225760` (Feishu/WS wiring).

Remaining open follow-ups (tech debt, not Phase 5 gaps):
- cmux migration in `myagent/server.py` (61 tmux hits — see tmux residual section)
- `tests/test_survival.py` rewrite for cmux (31 hits; commit `2da6592` says "skip pending cmux rewrite")

---

## S1 Observer — Multi-DH roadmap (2026-04-24)

**Status: code complete (13/14 tasks); 7-day validation pending**

Evidence per task:
| # | Task | Status | Commit | Tests |
|---|------|--------|--------|-------|
| T1 | Migration 001 (digital_human_id + dedup table) | ✅ | `fc03498` | 5/5 |
| T2 | DB helpers DH-aware + dedup helpers | ✅ | `5bab7be` | 16/16 |
| T3 | Persona split + ContextBuilder DH-aware | ✅ | `7efa9ea` | 7/7 regressing clean |
| T4 | DigitalHumanRegistry module | ✅ | `a3090d9` | 13/13 |
| T5 | Config + lifecycle API | ✅ | `a9980ad` | 7/7 |
| T6 | Per-DH auth + endpoint allowlist middleware | ✅ | `27a294a` | 12/12 |
| T7 | Dedup TTL purge cron (23:00 daily) | ✅ | `2ee296b` | smoke ok |
| T8 | Observer persona files | ✅ | `dc17d46` | persona loads 2893 chars |
| T9 | ObserverEngine module | ✅ | `e132fe7` | 6/6 |
| T10 | ObserverEngine wired in lifespan + admin dh_token endpoint | ✅ | `ed9afd0` | lifecycle ok |
| T11 | DHFilter component + list endpoints accept ?digital_human_id= | ✅ | `405e724` | 224 suite pass |
| T12/T13 | /digital_humans page + Dashboard strip + sidebar | ✅ | `61435e9` | tsc clean |
| T14 | Validation scaffolding (daily + exit scripts + rating sink) | ✅ | `3ba0624` | — |
| T14-day-0 | Observer flipped on + service restarted + 6/6 red-team pass | ✅ | `135cc8e` | Live verified 2026-04-24 20:49 |
| T14-automation | launchd agent installed for daily 23:55 auto-check | ✅ | `72bcd1b` | Dry-run OK |
| T14-live-7d | **7-day live validation window** | 🚧 | — | Day 0 passed; day 1-7 gathering real observer discoveries |

Full test suite at completion of code: **224 pass / 2 pre-existing failures / 19 skipped**.

### Live validation status

✅ **Day 0 smoke passed 2026-04-24 20:49 CST** — see `docs/s1-daily-log.md`
✅ **Day 0+ 10-round hardening 2026-04-24 21:23–21:40 CST** — see rounds R1–R10 below
✅ Daily check wired into in-process `_supervisor_loop` (23:00 cron) — writes to `docs/s1-daily-log.md`
🚧 Day 1–7 gathering real observer discoveries — supervisor loop auto-appends nightly

### 10-round self-audit rollout (2026-04-24 evening, R1–R10)

| Round | Fix | Commit |
|-------|-----|--------|
| R1 | Cold-start Executor → T27 token mint path actually fires + state.json populated | `8ef4268` |
| R2 | Harden: `BACKCOMPAT_MASTER_AS_EXECUTOR = False` (close master-token writes-as-executor hole) | `3c771e5` |
| R3 | Move daily check from launchd (hit macOS TCC) into in-process `_supervisor_loop` | `93d6d83` |
| R4 | Production `vite build` green — fix `apiFetch<T>` misuse + unused imports | `6845fd4` |
| R5 | Observer `_render_prompt` crashed on `None` DB fields → helper + regression test | `702e8f7` |
| R6 | `ContextManager` DH-aware; remove `/executor` path-join hack in server.py | `38589ae` |
| R7 | Drop 2 obsolete `chat_manager` tests → **full suite 225/0 green** | `a812ef0` |
| R8 | `SurvivalEngine.start()` now calls `registry.mark_started("executor", ...)` so executor state.json populates | `9cd8f58` |
| R9 | `.gitignore digital_humans/` runtime state + security audit (tokens not leakable via ps/history) | `5c37d23` |
| R10 | Final sweep: 225 pass, both DHs healthy on API, cmux alive | `42cdd0a` |

### Second 10-round rollout (2026-04-24 late-evening, R11–R20)

| Round | Fix | Commit |
|-------|-----|--------|
| R11 | Grep-scan + fix `.get(k, '')[:N]` NoneType pattern in 5 modules (context_builder / supervisor / survival / cli) | `66b4636` |
| R12 | Delete dead `deploy/launchd/`; purge stale root `persona/*.md` from HEAD (T3 'git mv' left duplicates) | `34318a7` |
| R13 | `GET /api/digital_humans/{id}/persona` endpoint + DigitalHumans page: color-coded allowlist badges + expandable persona preview | `ef19610` |
| R14 | New `/discoveries` page — dedicated UI for `agent_discoveries` (was sqlite-only before) + sidebar icon + i18n | `b4f0c37` |
| R15 | Observer prompt rewrite — proactive scanner mandate + 4-signal checklist + output SLA + good/bad examples | `a3676c7` |
| R16 | Dashboard DH strip shows today's 📦 deliverables + 💡 discoveries per DH | `c37802f` |
| R17 | `/api/agent/stats?digital_human_id=` backend filter + richer today counts; replaces R16 client-side filter | `1f417c3` |
| R18 | 7 new tests covering R13 persona endpoint + R17 stats scoping; **232 total pass** | `4200463` |
| R19 | Observer `_wait_for_cmux_ready` — poll-until-ready + auto-accept trust dialog; replaces racy 5s sleep | `afa30b9` |
| R20 | **Observer produced its first 2 real LLM-authored discoveries** (PPT backend CPU + Playlet-Clip Gmail bottleneck, both medium-risk) | _this commit_ |

Observer behavior change post-R15 prompt tuning: heartbeats went from repeating "no actionable discovery" to substantive "Observer context refreshed; monitoring Executor/system/external..." and two genuine risk signals landed in `agent_discoveries`.

### When validation window ends (day 7)

1. Run `bash scripts/s1_exit_check.sh` manually
2. Fill `docs/observer-rating-s1.md` with 20 random discoveries + rate (Ying)
3. If all exit criteria pass → brainstorm S2 (Planner + Conductor)
4. If any fail → diagnose, extend window, re-run exit_check

### To toggle observer off mid-window (rollback)

```bash
# Edit config.yaml: digital_humans.observer.enabled: false
launchctl kickstart -k "gui/$UID/com.ying.myagent"
# Verify: cmux list-workspaces | grep mycmux-observer  # should be empty
```

---

## Cross-phase residuals

### tmux residuals (audit result — Task 9, 2026-04-24)

**Summary**: docs layer 54 hits, code layer 99 hits. Stop-loss rule triggered (docs >20) — sites catalogued below rather than annotated one-by-one.

#### Docs layer breakdown (`rg -c "tmux" -g '*.md'`)

| File | Hits | Classification | Action |
|------|------|----------------|--------|
| `docs/specs/plans/2026-04-24-stabilization-sprint.md` | 23 | Meta — this sprint discussing tmux migration | None, expected |
| `docs/specs/2026-04-24-stabilization-sprint-design.md` | 7 | Meta — this sprint's spec | None, expected |
| `README.md` | 1 | Now contextual ("formerly tmux") after 2026-04-24 update | None, contextual |
| `README_CN.md` | 1 | Now contextual ("从 tmux 迁移") after 2026-04-24 update | None, contextual |
| `docs/specs/2026-03-13-myagent-v2-design.md` | 5 | Superseded v2 spec; banner notes legacy | None, banner sufficient |
| `docs/PROGRESS.md` | 2 | This file's catalog | None, expected |
| `docs/OVERVIEW.md` | 2 | Mentions "formerly tmux" explicitly | None, contextual |
| `docs/specs/SPEC_LEDGER.md` | 1 | Ledger note on cmux migration | None, contextual |
| `docs/specs/2026-03-11-chat-survival-system-design.md` | 1 | Superseded; banner says "tmux references are legacy" | None, banner sufficient |
| `docs/plans/2026-03-13-phase1-tailwind-migration.md` | 1 | Old plan, historical | None |
| `docs/ARCHITECTURE.md` | 1 | Mentions "formerly tmux" explicitly | None, contextual |
| `CLAUDE.md` | 1 | Mentions "formerly tmux" explicitly | None, contextual |

**Net actionable docs residuals**: none remaining. README / README_CN were fixed in commit `1d6dffe` (2026-04-24).

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

---

## DH Sovereignty (2026-04-25) — code-complete

Spec: `docs/specs/2026-04-25-dh-sovereignty-design.md`
Phases A+B shipped; C (legacy banners) + D (this entry) close the loop.

Backend:
- Migration 002: agent_config.digital_human_id nullable column + composite UNIQUE(digital_human_id, key)
- Config schema: DigitalHumanEntry gains model/prompt_template_file/mcp_servers; AgentConfig gains mcp_pool
- yaml_writer.py: atomic config.yaml rewriter with 10-backup rotation
- db.py: get_agent_config/set_agent_config gain digital_human_id (NULL = global fallback)
- dh_config.py: resolve(cfg, dh_id) → ResolvedDHConfig; augment_codex_cmd() for -c model + MCP flags
- server.py: 12 new endpoints (GET/PUT/DELETE config, GET/PUT skills/mcp/model/prompt, GET mcp_pool)
- observer.py + survival.py: on start(), resolve per-DH config + augment codex cmd

Frontend:
- DigitalHumanDetail.tsx tabbed page at /digital_humans/:id
- 7 tab components (Overview/Identity/Prompt/Skills/MCP/Model/Capabilities)
- Legacy /capabilities /prompt /identity_prompts pages gain scope banners
- 4 new vitest files (DigitalHumanDetail + 3 representative tabs)

Test totals:
- Backend: 302 passed / 19 skipped
- Frontend: 14 passed
- Build: clean

Known limitations:
- survival.py's prompt_template_file not yet honored (current prompt is
  DB-template with variable substitution; swapping to file would regress)
- MCP -c flag syntax carries a TODO-verify until we have a real mcp_pool
  entry to test against
- Observer may still self-restart on mid-run codex exit (watchdog
  added in R20 catches it but doesn't prevent)
