#!/usr/bin/env bash
# titan-claude-spawn.sh — canonical launch wrapper for Mobile Command v2 Step 6.3-b
#
# Used by lib/claude_cli_ctl.start_claude() when TITAN_CLAUDE_LAUNCH_CMD points
# here. Responsibilities:
#   1. Write own PID to TITAN_CLAUDE_PID_FILE (so claude_cli_ctl can later
#      stop/status the spawned process via that file).
#   2. exec the claude CLI as a detached child — the exec replaces this shell
#      with claude, retaining the same PID, so the pid file accurately points
#      at the live claude process.
#
# Env vars (with defaults):
#   TITAN_CLAUDE_PID_FILE     /var/run/titan-claude-session.pid
#   TITAN_CLAUDE_BIN          claude (assume on PATH)
#   TITAN_CLAUDE_ARGS         --print boot   (one-shot bootstrap; overridable)
#   TITAN_CLAUDE_WORKDIR      ~/titan-harness
#   TITAN_CLAUDE_OPERATOR_ID  passed in by claude_cli_ctl, exported to the child
#
# Override TITAN_CLAUDE_ARGS for interactive/persistent variants:
#   --resume                  (continue last session if Auto-Resume Protocol)
#   ""                        (interactive REPL, suitable when wrapped by tmux)
#
# To wrap in tmux for a persistent session that survives the wrapper exiting:
#   TITAN_CLAUDE_LAUNCH_CMD='tmux new-session -d -s titan-claude "claude --resume"'
#   …and skip this wrapper entirely. claude_cli_ctl reads the pid file the
#   wrapper writes; tmux-based launch needs an alternate pid-discovery hook.
#
# Exit codes (relevant when not exec'd):
#   1   pid file write failure
#   2   claude binary not found
set -euo pipefail

PID_FILE="${TITAN_CLAUDE_PID_FILE:-/var/run/titan-claude-session.pid}"
CLAUDE_BIN="${TITAN_CLAUDE_BIN:-claude}"
CLAUDE_ARGS="${TITAN_CLAUDE_ARGS:---print boot}"
WORKDIR="${TITAN_CLAUDE_WORKDIR:-$HOME/titan-harness}"

mkdir -p "$(dirname "$PID_FILE")" || { echo "[titan-claude-spawn] cannot mkdir pid dir" >&2; exit 1; }
echo "$$ launched-at-$(date -u +%FT%TZ)" > "$PID_FILE" || { echo "[titan-claude-spawn] pid file write failed" >&2; exit 1; }

if ! command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
  echo "[titan-claude-spawn] claude binary not found on PATH (TITAN_CLAUDE_BIN=$CLAUDE_BIN)" >&2
  exit 2
fi

cd "$WORKDIR" 2>/dev/null || cd "$HOME"

# Operator identity (forwarded by claude_cli_ctl) — claude itself doesn't read
# this, but it's available to any pre-exec hook a future revision might add.
export TITAN_CLAUDE_OPERATOR_ID="${TITAN_CLAUDE_OPERATOR_ID:-solon}"

# exec replaces this shell so the pid we just wrote is the long-running PID.
# shellcheck disable=SC2086 -- intentional word-splitting on CLAUDE_ARGS
exec "$CLAUDE_BIN" $CLAUDE_ARGS
