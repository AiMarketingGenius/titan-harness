#!/usr/bin/env bash
set -uo pipefail
STATE_DIR=/var/lib/titan-restart
EVENT_JSON=$(cat 2>/dev/null || echo '{}')
TRANSCRIPT_PATH=$(echo "$EVENT_JSON" | jq -r '.transcript_path // ""')
SESSION_ID=$(echo "$EVENT_JSON" | jq -r '.session_id // "unknown"')
MCP_URL="${MCP_URL:-https://memory.aimarketinggenius.io}"
mkdir -p "$STATE_DIR"
[[ -f "$TRANSCRIPT_PATH" ]] || exit 0
LAST_TURNS=$(jq -s '[.[] | select(.message.role=="assistant" and .isSidechain!=true)] | .[-5:] | map(.message.content | if type=="array" then map(select(.type=="text") | .text) | join("\n") else . end) | join("\n---\n")' "$TRANSCRIPT_PATH" 2>/dev/null || echo "")
STATE=$(jq -n --arg sid "$SESSION_ID" --arg turns "$LAST_TURNS" --arg ts "$(date -Iseconds)" --arg t "$TRANSCRIPT_PATH" \
  '{session_id:$sid,captured_at:$ts,last_5_turns:$turns,transcript_path:$t,capture_reason:"pre_compact_or_restart"}')
curl -s -X POST "${MCP_URL}/memory/sprint-state" -H "Content-Type: application/json" -d "$STATE" --max-time 15 >/dev/null 2>&1 || true
echo "$STATE" > "$STATE_DIR/last-state.json"
exit 0
