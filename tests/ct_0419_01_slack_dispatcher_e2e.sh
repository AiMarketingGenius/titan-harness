#!/usr/bin/env bash
# ct_0419_01_slack_dispatcher_e2e.sh
# E2E test for amg-slack-dispatcher per Sunday Playbook Item 1 Ship Criteria.
#
# Scenarios (all must pass for ship-tag):
#   A. 15 synthetic rapid-fire P1 with same fingerprint → 1 Slack send + 14 dedupes
#   B. Force daily cap breach → kill-switch activates → next dispatch goes Ntfy-only
#   C. Set maintenance-mode → P1 dispatch is suppressed
#   D. P3 dispatch → mcp-only (no push)
#   E. P2 dispatch → ntfy (no Slack)
#   F. Reset kill-switch + maintenance → P1 flows normally again
#
# Assumes dispatcher is running on VPS at 127.0.0.1:9876.
# Run this from Mac via SSH wrapper OR directly on VPS.
set -uo pipefail

DISP="${SLACK_DISPATCHER_URL:-http://127.0.0.1:9876}"
PASS=0
FAIL=0
TS=$(date -u +%Y%m%dT%H%M%SZ)

say() { echo "[E2E $TS] $*"; }
pass() { PASS=$((PASS+1)); say "PASS: $*"; }
fail() { FAIL=$((FAIL+1)); say "FAIL: $*"; }

# Helper: POST dispatch, return decision
dispatch() {
  local sev="$1" src="$2" msg="$3" fp="${4:-}"
  local body
  body=$(SEV="$sev" SRC="$src" MSG="$msg" FP="$fp" python3 -c '
import json, os
d = {"severity": os.environ["SEV"], "source": os.environ["SRC"], "message": os.environ["MSG"]}
if os.environ.get("FP"): d["fingerprint"] = os.environ["FP"]
print(json.dumps(d))
')
  curl -sS --max-time 4 -X POST -H "Content-Type: application/json" -d "$body" "$DISP/dispatch" 2>/dev/null
}

# Helper: GET admin endpoint
admin_get() {
  curl -sS --max-time 4 "$DISP$1" 2>/dev/null
}

say "=== PRE-FLIGHT ==="
health=$(admin_get /health)
if [[ -z "$health" ]]; then
  fail "dispatcher unreachable at $DISP"
  exit 1
fi
say "health: $health"

# Ensure clean state
admin_get /admin/reset-kill-switch > /dev/null
admin_get /admin/reset-maintenance > /dev/null
admin_get "/admin/set-daily-count?value=0" > /dev/null

say "=== SCENARIO A: 15 rapid-fire same fingerprint ==="
FP_A="e2e-a-$TS"
decisions=()
for i in $(seq 1 15); do
  r=$(dispatch P1 e2e-test-source "burst msg $i" "$FP_A")
  d=$(echo "$r" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("decision",""))' 2>/dev/null || echo "ERR")
  decisions+=("$d")
done

slack_count=0
dedup_count=0
for d in "${decisions[@]}"; do
  case "$d" in
    slack) slack_count=$((slack_count+1)) ;;
    deduped) dedup_count=$((dedup_count+1)) ;;
  esac
done

if [[ $slack_count -eq 1 ]] && [[ $dedup_count -eq 14 ]]; then
  pass "Scenario A: 1 slack + 14 deduped as expected"
else
  fail "Scenario A: expected 1 slack + 14 deduped, got slack=$slack_count dedup=$dedup_count (decisions: ${decisions[*]})"
fi

say "=== SCENARIO B: Force daily cap → kill-switch ==="
admin_get "/admin/set-daily-count?value=50" > /dev/null
FP_B="e2e-b-$TS"
r=$(dispatch P0 e2e-test-source "cap breach trigger" "$FP_B")
d=$(echo "$r" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("decision",""))' 2>/dev/null || echo "ERR")
if [[ "$d" == "kill-switch-activated-ntfy" ]] || [[ "$d" == "kill-switch-ntfy" ]]; then
  pass "Scenario B: kill-switch activated as expected (decision: $d)"
else
  fail "Scenario B: expected kill-switch-activated-ntfy, got '$d' (raw: $r)"
fi

ks=$(admin_get /health | python3 -c 'import json,sys; print(json.load(sys.stdin).get("kill_switch",""))' 2>/dev/null)
if [[ "$ks" == "True" ]]; then
  pass "Scenario B: kill-switch state is True in /health"
else
  fail "Scenario B: kill_switch state is not True (got: $ks)"
fi

say "=== SCENARIO C: Maintenance mode → P1 suppressed ==="
admin_get /admin/reset-kill-switch > /dev/null
admin_get "/admin/set-daily-count?value=0" > /dev/null
admin_get /admin/set-maintenance > /dev/null
FP_C="e2e-c-$TS"
r=$(dispatch P1 e2e-test-source "during maintenance" "$FP_C")
d=$(echo "$r" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("decision",""))' 2>/dev/null || echo "ERR")
if [[ "$d" == "maintenance-suppressed" ]]; then
  pass "Scenario C: P1 suppressed under maintenance"
else
  fail "Scenario C: expected maintenance-suppressed, got '$d'"
fi

say "=== SCENARIO D: P3 → mcp-only ==="
FP_D="e2e-d-$TS"
r=$(dispatch P3 e2e-test-source "telemetry" "$FP_D")
d=$(echo "$r" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("decision",""))' 2>/dev/null || echo "ERR")
if [[ "$d" == "mcp-only" ]]; then
  pass "Scenario D: P3 mcp-only"
else
  fail "Scenario D: expected mcp-only, got '$d'"
fi

say "=== SCENARIO E: P2 → ntfy ==="
admin_get /admin/reset-maintenance > /dev/null
FP_E="e2e-e-$TS"
r=$(dispatch P2 e2e-test-source "informational" "$FP_E")
d=$(echo "$r" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("decision",""))' 2>/dev/null || echo "ERR")
if [[ "$d" == "ntfy" ]]; then
  pass "Scenario E: P2 ntfy"
else
  fail "Scenario E: expected ntfy, got '$d'"
fi

say "=== SCENARIO F: Reset → P1 normal flow ==="
admin_get /admin/reset-kill-switch > /dev/null
admin_get /admin/reset-maintenance > /dev/null
admin_get "/admin/set-daily-count?value=0" > /dev/null
FP_F="e2e-f-$TS"
r=$(dispatch P1 e2e-test-source "post-reset normal" "$FP_F")
d=$(echo "$r" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("decision",""))' 2>/dev/null || echo "ERR")
if [[ "$d" == "slack" ]]; then
  pass "Scenario F: P1 flows to slack after reset"
else
  fail "Scenario F: expected slack, got '$d'"
fi

say "=== FINAL STATS ==="
admin_get /admin/stats

echo
echo "======================================"
echo "E2E RESULTS: PASS=$PASS FAIL=$FAIL"
echo "======================================"

# Reset final state
admin_get /admin/reset-kill-switch > /dev/null
admin_get /admin/reset-maintenance > /dev/null

[[ $FAIL -eq 0 ]] && exit 0 || exit 1
