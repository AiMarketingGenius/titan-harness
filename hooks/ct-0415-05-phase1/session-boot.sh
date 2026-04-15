#!/usr/bin/env bash
set -uo pipefail
STATE_DIR=/var/lib/titan-restart
mkdir -p "$STATE_DIR"
echo "$$" > "$STATE_DIR/session.pid"
echo "[titan-boot] $(date -Iseconds) session start, pid=$$" >&2
[[ -f "$STATE_DIR/last-state.json" ]] && {
  AGE=$(stat -c %Y "$STATE_DIR/last-state.json" 2>/dev/null || echo 0)
  echo "[titan-boot] last sprint state at $STATE_DIR/last-state.json (mtime=$AGE)" >&2
}
echo 0 > "$STATE_DIR/exchange-count"
exit 0
