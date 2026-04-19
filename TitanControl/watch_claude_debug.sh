#!/bin/zsh
# watch_claude_debug.sh — TitanControl Restart Handler v1.0
# Path 1 (self-restart): debug-log panic-string watcher.
# Runs as a long-lived LaunchAgent process (io.aimg.titan-logwatch).

set -euo pipefail

APP_DIR="$HOME/Library/Application Support/TitanControl"
LOG_FILE="$APP_DIR/logs/claude-debug.log"
HANDLER="$APP_DIR/request_restart.sh"
STATE_DIR="$APP_DIR/state"
DEDUPE_WINDOW_SECS=60

mkdir -p "$APP_DIR/logs" "$STATE_DIR"
touch "$LOG_FILE"

last_fire=0
tail -F "$LOG_FILE" | while IFS= read -r line; do
  if echo "$line" | egrep -qi 'authentication_failed|401 Unauthorized|rate_limit|timeout|max_output_tokens|panic|server_error|connection reset|anthropic.*error'; then
    now=$(date +%s)
    if (( now - last_fire > DEDUPE_WINDOW_SECS )); then
      last_fire=$now
      count="$(cat "$STATE_DIR/exchange_count" 2>/dev/null || true)"
      /bin/zsh "$HANDLER" \
        --source "self:error-signal" \
        --reason "debug_log_match" \
        --exchange-count "${count:-}" \
        >/dev/null 2>&1 || true
    fi
  fi
done
