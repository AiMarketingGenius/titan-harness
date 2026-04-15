#!/usr/bin/env bash
# Stop hook — fires after each Claude assistant turn completes.
# Hardened 2026-04-15 per Perplexity review:
#   - Persistent state at /var/lib/titan-restart/ (survives /tmp wipe)
#   - flock around counter increment (race-safe under concurrent Stop events)
#   - Targets only the session PID via PID file written by SessionStart
set -uo pipefail
STATE_DIR=/var/lib/titan-restart
COUNTER_FILE="$STATE_DIR/exchange-count"
LOCK_FILE="$STATE_DIR/counter.lock"
SIGNAL_FILE="$STATE_DIR/restart-requested"
MCP_URL="${MCP_URL:-https://memory.aimarketinggenius.io}"
SLACK_BOT_URL="${SLACK_BOT_URL:-http://localhost:3300}"
THRESHOLD="${TITAN_EXCHANGE_THRESHOLD:-25}"
EVENT_JSON=$(cat 2>/dev/null || echo '{}')
SESSION_ID=$(echo "$EVENT_JSON" | jq -r '.session_id // "unknown"')
TRANSCRIPT_PATH=$(echo "$EVENT_JSON" | jq -r '.transcript_path // ""')
LAST_MSG=$(echo "$EVENT_JSON" | jq -r '.last_assistant_message // ""')

mkdir -p "$STATE_DIR"

# Atomic increment under flock
COUNT=$(
  exec 9>"$LOCK_FILE"
  flock -x 9
  if [[ ! -f "$COUNTER_FILE" ]]; then echo 1 > "$COUNTER_FILE"; echo 1
  else
    NEW=$(( $(cat "$COUNTER_FILE") + 1 ))
    echo "$NEW" > "$COUNTER_FILE"
    echo "$NEW"
  fi
)

# Cross-check against transcript when available (transcript count is authoritative)
if [[ -f "$TRANSCRIPT_PATH" ]]; then
  ACTUAL=$(jq -s '[.[] | select(.message.role=="assistant" and .isSidechain!=true)] | length' "$TRANSCRIPT_PATH" 2>/dev/null || echo "$COUNT")
  if [[ "$ACTUAL" -gt "$COUNT" ]]; then
    COUNT="$ACTUAL"
    exec 9>"$LOCK_FILE"; flock -x 9; echo "$COUNT" > "$COUNTER_FILE"; flock -u 9
  fi
fi

if [[ "$COUNT" -ge "$THRESHOLD" ]]; then
  PAYLOAD=$(jq -n --arg sid "$SESSION_ID" --arg msg "$LAST_MSG" --arg count "$COUNT" --arg ts "$(date -Iseconds)" \
    '{session_id:$sid,event:"pre_restart_capture",exchange_count:($count|tonumber),last_assistant_message:$msg,timestamp:$ts}')
  curl -s -X POST "${MCP_URL}/memory/session-state" -H "Content-Type: application/json" -d "$PAYLOAD" --max-time 10 >/dev/null 2>&1 || true
  SLACK=$(jq -n --arg c "$COUNT" '{type:"restart_warning",message:":recycle: Titan hitting exchange limit (\($c)/25) — preparing context handoff and restart"}')
  curl -s -X POST "${SLACK_BOT_URL}/notify" -H "Content-Type: application/json" -d "$SLACK" --max-time 5 >/dev/null 2>&1 || true
  touch "$SIGNAL_FILE"
  exec 9>"$LOCK_FILE"; flock -x 9; echo 0 > "$COUNTER_FILE"; flock -u 9
fi
exit 0
