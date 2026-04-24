# S1 Observer Validation — Daily Log

Started: 2026-04-24

## Day 0 — 2026-04-24T20:49 CST (smoke test)

**Setup**
- Config flipped `digital_humans.observer.enabled: true`
- Service kickstarted at 20:49:11
- Observer workspace `929DF7CB` spawned at 20:49:12 in `/Users/ying/Documents/workspace/observer`
- Initial issue: codex required directory trust confirmation → resolved by manually approving once; trust persisted to `~/.codex/config.toml`, further restarts clean.
- Fix shipped in commit `747296b`: observer uses `survival.workspace/observer` subdir instead of `agent.data_dir`.

**Red-team results (all pass)**

| # | Test | Expected | Actual |
|---|------|----------|--------|
| 1 | Observer POST /api/agent/heartbeat | 200 | ✅ 200, digital_human_id=observer |
| 2 | Observer POST /api/agent/deliverable | 403 | ✅ 403 role_not_permitted: observer -> deliverable |
| 3 | Observer POST /api/agent/upgrade | 403 | ✅ 403 role_not_permitted: observer -> upgrade |
| 4 | Observer POST /api/agent/discovery | 200 | ✅ 200, id=11 |
| 5 | Observer POST duplicate discovery | duplicate_suppressed | ✅ hit_count=2 |
| 6 | Body spoof digital_human_id=executor | tagged observer (not spoofable) | ✅ tagged observer |

**DB state after smoke**
- agent_heartbeats: executor=178, observer=3 (1 engine-internal + 2 test)
- agent_discoveries observer rows: 1 (one unique + 1 suppressed duplicate)
- agent_discovery_dedup hit_count>1: 1
- Role isolation: 0 observer rows in deliverables/workflows/upgrades/reviews ✅

**Services healthy**
- Both cmux workspaces alive
- PID stable post-restart
- No error log entries beyond the initial codex-trust-prompt fix

**Status: Day 0 GREEN** — Observer is live, auth enforced, isolation enforced, dedup working. Day 1-7 counter starts now.

## Round 1 — 2026-04-24T21:23 CST (cold-start Executor)

**Setup**
- Killed both stale "生存引擎" workspaces (4137D5BD, C68670C1)
- Removed `/Users/ying/Documents/workspace/.cmux_workspace_id`
- POST `/api/survival/start` to trigger fresh SurvivalEngine.start()

**Results**
- ✅ SurvivalEngine.start() ran full path, `issue_token(registry, "executor")` fired
- ✅ `digital_humans/executor/state.json` now has `auth_token_hash: sha256:aba82a5b...`
- ✅ Cold executor heartbeat via DH token `eT_Cc3TE...` succeeded → DB id=183 tagged executor
- ✅ state.json `last_heartbeat_at` populated
- ✅ New "生存引擎" workspace 4397A486 alive

**Unprompted bonus**
- Observer at 21:23 posted REAL LLM-generated heartbeat (DB id=182):
  `"Observer context refreshed; no actionable discovery signal available in provided context."`
- This is codex (not my curl) — Observer's 30-min timer fired and the LLM responded.
- Note: I never saw Observer's first natural timer fire until now; that answers the P1 gap from day-0.

## Auto daily check — 2026-04-24T13:29:34.136530+00:00
- observer discovery count: 1
- observer restart_count: 1
- observer last_heartbeat_at: 2026-04-24T13:25:49.388041+00:00
- executor last_heartbeat_at: 2026-04-24T13:25:53.004673+00:00
- dedup suppressions (hit_count>1): 1
- discovery burst last hour: 1
- role isolation (expect all 0): {"agent_deliverables": 0, "agent_workflows": 0, "agent_upgrades": 0, "agent_reviews": 0}

## Auto daily check — 2026-04-24T15:01:18.445651+00:00
- observer discovery count: 3
- observer restart_count: 1
- observer last_heartbeat_at: 2026-04-24T14:13:32.306117+00:00
- executor last_heartbeat_at: 2026-04-24T13:49:56.266110+00:00
- dedup suppressions (hit_count>1): 1
- discovery burst last hour: 3
- role isolation (expect all 0): {"agent_deliverables": 0, "agent_workflows": 0, "agent_upgrades": 0, "agent_reviews": 0}
