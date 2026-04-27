#!/bin/bash
set -euo pipefail
PORT=8800
LOG="$HOME/.openclaw/logs/atlas_dashboard.log"
mkdir -p "$(dirname "$LOG")"

PIDS=$(lsof -ti tcp:$PORT 2>/dev/null || true)
if [ -n "$PIDS" ]; then
  kill $PIDS 2>/dev/null || true
  sleep 0.4
  PIDS=$(lsof -ti tcp:$PORT 2>/dev/null || true)
  [ -n "$PIDS" ] && kill -9 $PIDS 2>/dev/null || true
fi

cd "$HOME/titan-harness"
nohup /opt/homebrew/bin/python3 scripts/atlas_dashboard_server.py --port "$PORT" >> "$LOG" 2>&1 &
disown $!

for i in {1..30}; do
  if curl -sf "http://127.0.0.1:$PORT/api/factory-status" >/dev/null 2>&1; then break; fi
  sleep 0.4
done

if [ -d "/Applications/Google Chrome.app" ]; then
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --app="http://127.0.0.1:$PORT/" \
    --user-data-dir="$HOME/.openclaw/chrome-app-atlas" \
    --window-size=1280,860 \
    --window-position=120,80 \
    >/dev/null 2>&1 &
  disown
else
  open -a Safari "http://127.0.0.1:$PORT/"
fi
