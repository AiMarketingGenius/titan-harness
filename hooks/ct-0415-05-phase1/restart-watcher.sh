#!/usr/bin/env bash
set -uo pipefail
STATE_DIR=/var/lib/titan-restart
LOG=/var/log/titan-restart-watcher.log
SIGNAL="$STATE_DIR/restart-requested"
PID_FILE="$STATE_DIR/session.pid"
mkdir -p "$STATE_DIR"
exec >>"$LOG" 2>&1
echo "----- $(date -Iseconds) watcher start (hardened) -----"
while true; do
  if [[ -f "$SIGNAL" ]]; then
    echo "$(date -Iseconds) restart-requested signal observed"
    rm -f "$SIGNAL"
    # Target ONLY the recorded session PID (not all 'claude' processes)
    if [[ -f "$PID_FILE" ]]; then
      TARGET_PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
      if [[ -n "$TARGET_PID" ]] && kill -0 "$TARGET_PID" 2>/dev/null; then
        echo "  signaling PID $TARGET_PID (from session.pid)"
        kill -TERM "$TARGET_PID" 2>/dev/null || true
      else
        echo "  no live PID at $PID_FILE (stale or unset) — skipping kill"
      fi
    else
      echo "  no $PID_FILE present — session-boot hasn't fired this lifecycle yet"
    fi
    sleep 30
  fi
  sleep 5
done
