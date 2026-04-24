#!/usr/bin/env bash
# S1 Observer validation — daily health check
# Run once a day during the 7-day validation window.
# Usage: bash scripts/s1_daily_check.sh [>> docs/s1-daily-log.md]

set -e
cd "$(dirname "$0")/.."

echo "=== $(date -u +%FT%TZ) — S1 daily check ==="

echo
echo "--- Observer discovery count ---"
sqlite3 agent.db "SELECT COUNT(*) FROM agent_discoveries WHERE digital_human_id='observer';"

echo
echo "--- Observer restart count ---"
if [ -f digital_humans/observer/state.json ]; then
  jq '.restart_count // 0' digital_humans/observer/state.json
else
  echo "(no state.json yet)"
fi

echo
echo "--- Observer last heartbeat ---"
sqlite3 agent.db "SELECT created_at, activity, description FROM agent_heartbeats WHERE digital_human_id='observer' ORDER BY id DESC LIMIT 1;"

echo
echo "--- Today's dedup suppressions (hit_count > 1) ---"
sqlite3 agent.db "SELECT COUNT(*) FROM agent_discovery_dedup WHERE hit_count > 1;"

echo
echo "--- Role isolation audit (expected 0 for each) ---"
for t in agent_deliverables agent_workflows agent_upgrades agent_reviews; do
  n=$(sqlite3 agent.db "SELECT COUNT(*) FROM $t WHERE digital_human_id='observer';")
  echo "$t: $n"
done

echo
echo "--- Discovery burst check (last hour, expected <60) ---"
sqlite3 agent.db "SELECT COUNT(*) FROM agent_discoveries WHERE digital_human_id='observer' AND created_at > datetime('now', '-1 hour');"

echo
echo "--- Cost heuristic (today's review entries, if any) ---"
sqlite3 agent.db "SELECT period, cost_estimate FROM agent_reviews WHERE digital_human_id IN ('executor','observer') AND date(created_at) = date('now');"

echo "=== done ==="
