#!/usr/bin/env bash
# titan-harness/bin/idea-to-execution.sh
# Thin wrapper around lib/idea_to_execution.py that sources env + enforces preflight.
#
# Usage:
#   idea-to-execution.sh --once             # single poll cycle (cron-friendly)
#   idea-to-execution.sh --daemon           # long-running loop
#   idea-to-execution.sh --dry-run --once   # log-only mode
set -euo pipefail

_HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source the policy loader + env
if [ -f "$_HARNESS_DIR/lib/titan-env.sh" ]; then
    # shellcheck source=../lib/titan-env.sh
    . "$_HARNESS_DIR/lib/titan-env.sh" >/dev/null 2>&1 || true
fi
if [ -f "$HOME/.titan-env" ]; then
    # shellcheck source=/dev/null
    . "$HOME/.titan-env" >/dev/null 2>&1 || true
fi

# Non-bypassable preflight
if [ -x "$_HARNESS_DIR/bin/harness-preflight.sh" ]; then
    if ! "$_HARNESS_DIR/bin/harness-preflight.sh" >&2; then
        echo "idea-to-execution: harness-preflight failed — refusing to run" >&2
        exit 10
    fi
fi

exec python3 "$_HARNESS_DIR/lib/idea_to_execution.py" "$@"
