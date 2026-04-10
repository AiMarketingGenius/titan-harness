#!/bin/bash
# post-tool-log.sh — PostToolUse
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/titan-env.sh"

INPUT=$(cat)
TOOL=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null || echo "UNKNOWN")
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null || echo "")

TASK_ID=""
[ -f "$TITAN_SESSION_DIR/ACTIVE_TASK_ID" ] && TASK_ID=$(cat "$TITAN_SESSION_DIR/ACTIVE_TASK_ID" 2>/dev/null)

titan_local_audit "POST tool=$TOOL task=${TASK_ID:-none} session=${SESSION_ID:0:12}"
titan_supabase_post "tool_log" "{\"session_id\":\"$SESSION_ID\",\"task_id\":\"${TASK_ID:-null}\",\"tool_name\":\"$TOOL\",\"result_status\":\"post\",\"payload\":{\"instance\":\"$TITAN_INSTANCE\"}}"

exit 0
