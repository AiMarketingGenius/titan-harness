#!/bin/zsh
# run_titan_session.sh — Terminal-launched Claude Code wrapper for TitanControl restart
# Part of TitanControl Unified Restart Handler v1.0 (CT-0419, pre_approved)
#
# NEVER launch claude with --bare (skips SessionStart hook, defeats auto-context-load).

set -euo pipefail

APP_DIR="$HOME/Library/Application Support/TitanControl"
STATE_DIR="$APP_DIR/state"
LOG_DIR="$APP_DIR/logs"
BOOT_PROMPT_FILE="$APP_DIR/boot_prompt.txt"
STATUS_FILE="$STATE_DIR/status.json"

# Titan working directory — verified at ship time
TITAN_WORKDIR="$HOME/titan-harness"

mkdir -p "$STATE_DIR" "$LOG_DIR"
cd "$TITAN_WORKDIR"

CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude || true)}"
[[ -n "$CLAUDE_BIN" ]] || { echo "claude binary not on PATH" >&2; exit 127; }

PGID="$(ps -o pgid= $$ | tr -d ' ')"
echo "$PGID" > "$STATE_DIR/titan.pgid"
printf '\033]1;Titan\007'   # Terminal tab title

PROMPT="$(cat "$BOOT_PROMPT_FILE")"
REQUEST_ID="$(cat "$STATE_DIR/request_id" 2>/dev/null || true)"

REQUEST_ID="$REQUEST_ID" python3 - "$STATUS_FILE" <<'PY'
import json, os, sys, time
path = sys.argv[1]
data = {
  "request_id": os.environ.get("REQUEST_ID",""),
  "state": "booting",
  "note": "launching_claude",
  "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
tmp = path + ".tmp"
with open(tmp, "w") as f: json.dump(data, f)
os.replace(tmp, path)
PY

# Interactive session with initial prompt (preserves SessionStart hook chain)
"$CLAUDE_BIN" --debug-file "$LOG_DIR/claude-debug.log" "$PROMPT" &
CLAUDE_PID=$!
echo "$CLAUDE_PID" > "$STATE_DIR/claude.pid"
wait "$CLAUDE_PID"
RC=$?

REQUEST_ID="$REQUEST_ID" RC="$RC" python3 - "$STATUS_FILE" <<'PY'
import json, os, sys, time
path = sys.argv[1]
data = {
  "request_id": os.environ.get("REQUEST_ID",""),
  "state": "dead",
  "note": f"claude_exit_{os.environ.get('RC','1')}",
  "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
tmp = path + ".tmp"
with open(tmp, "w") as f: json.dump(data, f)
os.replace(tmp, path)
PY

exit "$RC"
