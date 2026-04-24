#!/usr/bin/env bash
# S1 Observer validation — exit-criteria check
# Run at end of 7-day validation window to determine whether S1 can ship.
# See: docs/specs/2026-04-24-s1-observer-digital-human.md § 9

set -u
cd "$(dirname "$0")/.."

PASS=0
FAIL=0
check() {
  local name=$1 actual=$2 expected=$3
  if [ "$actual" = "$expected" ]; then
    echo "PASS: $name"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $name — expected $expected, got $actual"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== S1 Observer — exit criteria check ==="

# §9.1 Data contract
for t in agent_heartbeats agent_deliverables agent_discoveries agent_workflows agent_upgrades agent_reviews; do
  n=$(sqlite3 agent.db "SELECT COUNT(*) FROM pragma_table_info('$t') WHERE name='digital_human_id';")
  check "$t has digital_human_id column" "$n" "1"
done
[ -d persona/executor ] && check "persona/executor/ exists" "y" "y" || check "persona/executor/ exists" "n" "y"
[ -d persona/observer ] && check "persona/observer/ exists" "y" "y" || check "persona/observer/ exists" "n" "y"
[ -f digital_humans/executor/state.json ] && check "executor state.json" "y" "y" || check "executor state.json" "n" "y"
[ -f digital_humans/observer/state.json ] && check "observer state.json" "y" "y" || check "observer state.json" "n" "y"

# §9.2 Stable ≥7 days, restart_count ≤3
if [ -f digital_humans/observer/state.json ]; then
  rc=$(jq '.restart_count // 0' digital_humans/observer/state.json)
  check "observer restart_count ≤3" "$([ "$rc" -le 3 ] && echo 1 || echo 0)" "1"
fi

# §9.4 Discovery volume
dc=$(sqlite3 agent.db "SELECT COUNT(*) FROM agent_discoveries WHERE digital_human_id='observer';")
check "observer discovery count ≥50" "$([ "$dc" -ge 50 ] && echo 1 || echo 0)" "1"

# §9.5 Dedup working
dedup_hits=$(sqlite3 agent.db "SELECT COUNT(*) FROM agent_discovery_dedup WHERE hit_count > 1;")
check "dedup hit_count>1 count ≥5" "$([ "$dedup_hits" -ge 5 ] && echo 1 || echo 0)" "1"

# §9.6 Role isolation
for t in agent_deliverables agent_workflows agent_upgrades agent_reviews; do
  n=$(sqlite3 agent.db "SELECT COUNT(*) FROM $t WHERE digital_human_id='observer';")
  check "$t zero observer rows" "$n" "0"
done

# §9.8 Ratings filled (heuristic)
if [ -f docs/observer-rating-s1.md ]; then
  rated=$(grep -cE '^\|[^|]+\|[^|]+\|[^|]+\|\s*[yn]\s*\|' docs/observer-rating-s1.md 2>/dev/null || echo 0)
  check "ratings filled ≥20" "$([ "$rated" -ge 20 ] && echo 1 || echo 0)" "1"
fi

echo
echo "---"
echo "PASSED: $PASS   FAILED: $FAIL"
echo
echo "Manual checks remaining (script cannot verify automatically):"
echo "  - §9.3 cost: inspect docs/s1-daily-log.md — ≥5 of 7 days must have"
echo "              recorded daily cost ≤ \$10"
echo "  - §9.4 usefulness: spot-check docs/observer-rating-s1.md —"
echo "              ≥30% of 20 rated rows must be marked 'y'"
echo "  - Red-team tests: inspect docs/s1-daily-log.md for at least one"
echo "              documented 403 from observer attempting deliverable"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
