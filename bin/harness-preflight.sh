#!/usr/bin/env bash
# titan-harness/bin/harness-preflight.sh — Phase G.5 CORE CONTRACT
#
# Mandatory pre-flight for ANY runner built on the titan-harness:
#   - mp-runner.sh (already wired)
#   - titan_queue_watcher.py (already wired)
#   - All future client-specific runners
#
# Verifies:
#   1. policy.yaml has a populated capacity: block (POLICY_CAPACITY_* exported)
#   2. check-capacity.sh exists and is executable
#   3. A baseline capacity check runs successfully (exit != 2)
#
# Exit codes:
#   0 — ready to run
#   10 — capacity block missing / invalid
#   11 — check-capacity.sh missing or not executable
#   12 — baseline capacity check hard-blocked (box is hot, defer runner start)
set -e

_HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Ensure policy loaded
if [ -z "${POLICY_CAPACITY_MAX_CLAUDE_SESSIONS:-}" ] && [ -f "$_HARNESS_DIR/lib/titan-env.sh" ]; then
  # shellcheck source=../lib/titan-env.sh
  . "$_HARNESS_DIR/lib/titan-env.sh" >/dev/null 2>&1 || true
fi

if [ "${POLICY_CAPACITY_BLOCK_VALIDATED:-0}" != "1" ] || [ -z "${POLICY_CAPACITY_MAX_CLAUDE_SESSIONS:-}" ]; then
  echo "harness-preflight: CORE CONTRACT VIOLATION — capacity block missing from policy.yaml" >&2
  echo "harness-preflight: refusing to start runner" >&2
  exit 10
fi

if [ ! -x "$_HARNESS_DIR/bin/check-capacity.sh" ]; then
  echo "harness-preflight: CORE CONTRACT VIOLATION — check-capacity.sh missing or not executable" >&2
  exit 11
fi

# Baseline: allow soft-block at startup (runner can self-throttle), but hard-block = defer start
if ! "$_HARNESS_DIR/bin/check-capacity.sh" >&2; then
  _ec=$?
  if [ "$_ec" -eq 2 ]; then
    echo "harness-preflight: baseline capacity hard-blocked (cpu/ram critical) — deferring runner start" >&2
    exit 12
  fi
fi

echo "harness-preflight: OK (capacity block valid, check-capacity executable, baseline ok/soft)"
exit 0
