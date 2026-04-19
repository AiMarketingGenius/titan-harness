#!/usr/bin/env bash
# test_regression_probe.sh — unit tests for regression_integrity_probe.sh
set -euo pipefail

readonly TITANIUM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly PROBE="$TITANIUM_DIR/regression_integrity_probe.sh"

PASS=0
FAIL=0

assert_exit() {
  local expected="$1"
  shift
  local name="$1"
  shift
  local actual
  set +e
  "$@" >/dev/null 2>&1
  actual=$?
  set -e
  if [ "$actual" = "$expected" ]; then
    echo "PASS: $name"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $name (expected $expected, got $actual)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== syntax check ==="
assert_exit 0 "probe bash -n" bash -n "$PROBE"

echo "=== probe 0 (governance gate self-check) ==="
# probe 0 should pass since pre-proposal-gate --self-test passes
assert_exit 0 "probe 0 passes" "$PROBE" --probe 0

echo
echo "─────────────────────────────"
echo "regression_probe: $PASS pass / $FAIL fail"
exit $FAIL
