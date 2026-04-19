#!/usr/bin/env bash
# test_session_end_claim.sh — smoke test for session_end_claim_hook.sh
set -euo pipefail

readonly TITANIUM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly HOOK="$TITANIUM_DIR/session_end_claim_hook.sh"

PASS=0; FAIL=0

echo "=== syntax check ==="
if bash -n "$HOOK"; then echo "PASS: hook bash -n"; PASS=$((PASS+1))
else echo "FAIL: hook syntax"; FAIL=$((FAIL+1)); fi

echo "=== non-supabase env exits cleanly ==="
( unset SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY
  if SUPABASE_URL="" SUPABASE_SERVICE_ROLE_KEY="" "$HOOK" >/dev/null 2>&1; then
    echo "PASS: runs+exits 0 with no env"; PASS=$((PASS+1))
  else
    echo "FAIL: should exit 0 when env missing"; FAIL=$((FAIL+1))
  fi
)

echo
echo "─────────────────────────────"
echo "session_end_claim: $PASS pass / $FAIL fail"
exit $FAIL
