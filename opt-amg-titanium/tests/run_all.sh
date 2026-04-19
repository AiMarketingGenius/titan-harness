#!/usr/bin/env bash
# run_all.sh — run every Titanium unit test, aggregate results.
set -euo pipefail
TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOTAL_PASS=0; TOTAL_FAIL=0
for t in "$TESTS_DIR"/test_*.sh; do
  echo "▶ Running $(basename "$t")"
  if "$t"; then
    :
  else
    TOTAL_FAIL=$((TOTAL_FAIL + $?))
  fi
  echo
done
echo "═══════════════════════════════"
echo "Total failures across suites: $TOTAL_FAIL"
exit $TOTAL_FAIL
