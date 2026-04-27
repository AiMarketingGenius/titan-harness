#!/bin/bash
set -euo pipefail
PORT=8765
PERSONA=hercules
LOG_DIR="$HOME/.openclaw/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/${PERSONA}_chat_server.log"

# Kill prior instance on this port (graceful, then SIGKILL).
PIDS=$(lsof -ti tcp:$PORT 2>/dev/null || true)
if [ -n "$PIDS" ]; then
  kill $PIDS 2>/dev/null || true
  sleep 0.4
  PIDS=$(lsof -ti tcp:$PORT 2>/dev/null || true)
  if [ -n "$PIDS" ]; then kill -9 $PIDS 2>/dev/null || true; fi
fi

cd "$HOME/titan-harness"
nohup /opt/homebrew/bin/python3 scripts/hercules_chat_server.py --persona "$PERSONA" --port "$PORT" >> "$LOG" 2>&1 &
SERVER_PID=$!
disown $SERVER_PID

# Wait for the port to come up.
for i in {1..30}; do
  if curl -sf "http://127.0.0.1:$PORT/api/state" >/dev/null 2>&1; then break; fi
  sleep 0.4
done

# Pre-load clipboard with this persona's boot prompt so Solon Cmd-V to paste at session start.
# Source: ~/AMG/agent-boot-prompts/<persona>.txt (per AGENT_BOOT_PROMPTS_2026-04-27 wiring).
PROMPT_FILE="$HOME/AMG/agent-boot-prompts/${PERSONA}.txt"
if [ -f "$PROMPT_FILE" ]; then
  pbcopy < "$PROMPT_FILE" || true
fi

# Open in Chrome --app mode (clean popout window, no URL bar) — falls back to
# Safari if Chrome isn't installed.
if [ -d "/Applications/Google Chrome.app" ]; then
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --app="http://127.0.0.1:$PORT/" \
    --user-data-dir="$HOME/.openclaw/chrome-app-$PERSONA" \
    --window-size=720,920 \
    --window-position=200,100 \
    >/dev/null 2>&1 &
  disown
else
  open -a Safari "http://127.0.0.1:$PORT/"
fi
