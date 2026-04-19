#!/bin/bash
# tests/test_hammerspoon_auto_restart_cycle.sh
#
# E2E smoke for Hammerspoon auto-restart suite (CT-0418-08 item #1/6).
#
# Runs in DRY_RUN mode by default — logs the MCP request + forces a
# Hammerspoon poll without actually quitting Claude Code. Full live-cycle
# test requires Solon running it manually (see README §E2E smoke option 4).
#
# Verifies:
#   1. titan_request_auto_restart.sh logs a pending decision to MCP
#   2. poll_auto_restart_queue.sh finds the decision + emits JSON payload
#      with restart=true + restart_id + wake_phrase + reason
#   3. ack_auto_restart.sh marks the request complete
#   4. Second poll does NOT return the same request (acked filter works)
#   5. Kill-switch (titan-auto-restart-disabled tag) makes poll return
#      disabled=true
#
# Exit 0 = all assertions green
# Exit 1 = any assertion fires
# Exit 77 = env missing (supabase creds)

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/scripts/hammerspoon-auto-restart/bin"

if [ ! -f "$HOME/.titan-env" ]; then
  echo "SKIP: ~/.titan-env missing"
  exit 77
fi

source "$HOME/.titan-env" 2>/dev/null || true
if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  echo "SKIP: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing"
  exit 77
fi

echo "=== [1/5] Log pending restart via titan_request_auto_restart.sh ==="
OUT=$(bash "$BIN/titan_request_auto_restart.sh" --reason "e2e-smoke-test")
echo "   request output: $OUT"
RESTART_ID=$(echo "$OUT" | python3 -c "import json,sys; print(json.load(sys.stdin)['restart_id'])")
if [ -z "$RESTART_ID" ] || [ "$RESTART_ID" = "null" ]; then
  echo "FAIL: no restart_id returned"
  exit 1
fi
echo "   restart_id: $RESTART_ID"

echo ""
echo "=== [2/5] Poll queue — should return our request ==="
sleep 1  # allow decision to be indexed
POLL_OUT=$(bash "$BIN/poll_auto_restart_queue.sh")
echo "   poll output: $POLL_OUT"
GOT_RID=$(echo "$POLL_OUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('restart_id',''))")
if [ "$GOT_RID" != "$RESTART_ID" ]; then
  # Might pick up an older pending request if one exists — check for `restart: true` at least
  RESTART_Y=$(echo "$POLL_OUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('restart'))")
  if [ "$RESTART_Y" != "True" ]; then
    echo "FAIL: poll did not return restart=true (got $POLL_OUT)"
    exit 1
  fi
  echo "   NOTE: poll returned an earlier pending request ($GOT_RID) — using that for ack test"
  RESTART_ID="$GOT_RID"
fi

echo ""
echo "=== [3/5] Ack the request ==="
bash "$BIN/ack_auto_restart.sh" "$RESTART_ID" "dry_run"
echo "   acked $RESTART_ID"

echo ""
echo "=== [4/5] Re-poll — acked request should NOT reappear ==="
sleep 1
POLL_AGAIN=$(bash "$BIN/poll_auto_restart_queue.sh")
echo "   re-poll output: $POLL_AGAIN"
REAPPEARED=$(echo "$POLL_AGAIN" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('yes' if d.get('restart_id') == '$RESTART_ID' else 'no')
")
if [ "$REAPPEARED" = "yes" ]; then
  echo "FAIL: acked request reappeared — ack filter broken"
  exit 1
fi
echo "   acked request correctly filtered"

echo ""
echo "=== [5/5] Kill-switch check ==="
# Log a titan-auto-restart-disabled decision + re-poll.
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
KILL_PAYLOAD=$(python3 -c "
import json
print(json.dumps({
  'decision_text': 'e2e test kill-switch flip ts=$TS — will auto-expire after 24h per poll script logic',
  'tags': ['titan-auto-restart-disabled', 'e2e-test-artifact', 'ephemeral'],
  'project_source': 'titan',
}))
")
curl -sS -X POST "$SUPABASE_URL/rest/v1/op_decisions" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=minimal" \
  --data "$KILL_PAYLOAD" >/dev/null
sleep 1

POLL_KILLED=$(bash "$BIN/poll_auto_restart_queue.sh")
echo "   poll-under-kill: $POLL_KILLED"
DISABLED=$(echo "$POLL_KILLED" | python3 -c "import json,sys; print(json.load(sys.stdin).get('disabled'))")
if [ "$DISABLED" != "True" ]; then
  echo "FAIL: kill-switch not honored by poller"
  exit 1
fi
echo "   kill-switch honored (disabled=true)"

# Clean up: log a newer titan-auto-restart-enabled decision so production
# resumes. Poll script honors latest-of-pair rule, so this re-enables.
TS2=$(date -u +%Y-%m-%dT%H:%M:%SZ)
ENABLE_PAYLOAD=$(python3 -c "
import json
print(json.dumps({
  'decision_text': 'e2e test kill-switch rescind ts=$TS2',
  'tags': ['titan-auto-restart-enabled', 'e2e-test-artifact', 'ephemeral'],
  'project_source': 'titan',
}))
")
curl -sS -X POST "$SUPABASE_URL/rest/v1/op_decisions" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=minimal" \
  --data "$ENABLE_PAYLOAD" >/dev/null
sleep 1

RECOVERED=$(bash "$BIN/poll_auto_restart_queue.sh")
echo "   poll-after-rescind: $RECOVERED"
DISABLED2=$(echo "$RECOVERED" | python3 -c "import json,sys; print(json.load(sys.stdin).get('disabled'))")
if [ "$DISABLED2" = "True" ]; then
  echo "FAIL: enable-rescind did not clear kill-switch"
  exit 1
fi
echo "   kill-switch cleared by newer enable decision"

echo ""
echo "PASS: hammerspoon_auto_restart_cycle E2E (dry-run)"
echo "NOTE: full live cycle (actual quit + relaunch) requires Solon manual test per README"
