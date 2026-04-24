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
