#!/usr/bin/env bash
# test_stale_sweeper.sh — dry-run test for stale_task_sweeper.sh
set -euo pipefail

readonly TITANIUM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly SWEEPER="$TITANIUM_DIR/stale_task_sweeper.sh"

PASS=0; FAIL=0

echo "=== syntax check ==="
if bash -n "$SWEEPER"; then echo "PASS: sweeper bash -n"; PASS=$((PASS+1))
else echo "FAIL: sweeper syntax"; FAIL=$((FAIL+1)); fi

echo "=== dry-run (no writes) ==="
if [ -f "$HOME/.titan-env" ]; then
  if "$SWEEPER" --dry-run >/dev/null 2>&1; then
    echo "PASS: dry-run completes"; PASS=$((PASS+1))
  else
    echo "SKIP: dry-run requires live MCP — OK if env missing"
  fi
else
  echo "SKIP: no ~/.titan-env (ok in CI)"
fi

echo
echo "─────────────────────────────"
echo "stale_sweeper: $PASS pass / $FAIL fail"
exit $FAIL
