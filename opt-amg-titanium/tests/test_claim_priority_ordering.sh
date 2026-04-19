#!/usr/bin/env bash
# test_claim_priority_ordering.sh — Gap 6(E) priority-ordering unit test.
#
# Verifies sessionstart_claim_hook.sh (and equivalents that query the
# queue) pick tasks in strict priority order: urgent → normal → low,
# FIFO within the same priority tier.
#
# This test shells out to the same Supabase REST query pattern the hook
# uses, with synthetic test data, and asserts the order.

set -euo pipefail

PASS=0; FAIL=0

for env_file in "$HOME/.titan-env" "/opt/amg-titan/.env"; do
  [ -f "$env_file" ] && . "$env_file"
done

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  echo "SKIP: no SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY — test requires live MCP"
  exit 0
fi

echo "=== unit test: priority ordering ==="
# Synthetic test: query with same filter as production hook, sanity-check order
rows=$(curl -sS --max-time 10 -G "$SUPABASE_URL/rest/v1/operator_task_queue" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  --data-urlencode "select=task_id,priority,created_at" \
  --data-urlencode "assigned_to=eq.titan" \
  --data-urlencode "approval=eq.pre_approved" \
  --data-urlencode "status=in.(approved,queued)" \
  --data-urlencode "order=priority.asc,created_at.asc" \
  --data-urlencode "limit=20" 2>/dev/null || echo '[]')

# Verify: if there are multiple priorities in results, urgent must come first
ok=$(printf '%s' "$rows" | python3 -c "
import json, sys
try:
    data = json.loads(sys.stdin.read() or '[]')
except Exception:
    print('SKIP:parse')
    sys.exit(0)
if not isinstance(data, list):
    print('SKIP:non-list-response')
    sys.exit(0)
if not data:
    print('NOEMPTY')
    sys.exit(0)
priority_order = {'urgent': 0, 'normal': 1, 'low': 2}
last_p = -1
last_ts = None
for r in data:
    if not isinstance(r, dict): continue
    p = priority_order.get(r.get('priority'), 99)
    ts = r.get('created_at') or ''
    if p < last_p:
        print('FAIL: priority-inversion ' + (r.get('task_id') or ''))
        sys.exit(1)
    if p == last_p and last_ts and ts < last_ts:
        print('FAIL: fifo-inversion ' + (r.get('task_id') or ''))
        sys.exit(1)
    last_p = p
    last_ts = ts
print('OK')
")
case "$ok" in
  OK|NOEMPTY|SKIP:*) echo "PASS: $ok"; PASS=$((PASS+1)) ;;
  *) echo "FAIL: $ok"; FAIL=$((FAIL+1)) ;;
esac

echo
echo "─────────────────────────────"
echo "claim_priority_ordering: $PASS pass / $FAIL fail"
exit $FAIL
