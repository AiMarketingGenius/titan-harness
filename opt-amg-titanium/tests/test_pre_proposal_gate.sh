#!/usr/bin/env bash
# test_pre_proposal_gate.sh — unit tests for pre-proposal-gate.sh
set -euo pipefail

readonly TITANIUM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly GATE="$TITANIUM_DIR/pre-proposal-gate.sh"

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
    echo "PASS: $name (exit=$actual)"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $name (expected $expected, got $actual)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== test: --self-test ==="
assert_exit 0 "self-test clean" "$GATE" "--self-test"

echo "=== test: non-commit mode (no staged files) ==="
# When run outside pre-commit context, gate runs self-test + exits
TMPDIR=$(mktemp -d)
pushd "$TMPDIR" >/dev/null
git init -q
assert_exit 0 "empty-repo no-staged-files" "$GATE"
popd >/dev/null
rm -rf "$TMPDIR"

echo "=== test: GATE_OVERRIDE=1 ==="
assert_exit 0 "override bypass" env GATE_OVERRIDE=1 "$GATE" --self-test

echo
echo "─────────────────────────────"
echo "pre_proposal_gate: $PASS pass / $FAIL fail"
exit $FAIL
