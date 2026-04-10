#!/bin/bash
# pre-tool-gate.sh — PreToolUse gate
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/titan-env.sh"

INPUT=$(cat)
TOOL=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null || echo "UNKNOWN")
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null || echo "")

ACTIVE_TASK_FILE="$TITAN_SESSION_DIR/ACTIVE_TASK_ID"
TASK_ID=""
[ -f "$ACTIVE_TASK_FILE" ] && TASK_ID=$(cat "$ACTIVE_TASK_FILE" 2>/dev/null)

BYPASS_FILE="$TITAN_SESSION_DIR/.gate_bypass"
BYPASS=0
[ -f "$BYPASS_FILE" ] && BYPASS=1

if [[ "$TOOL" == "Write" || "$TOOL" == "Edit" || "$TOOL" == "NotebookEdit" ]]; then
  if [ -z "$TASK_ID" ] && [ "$BYPASS" -eq 0 ]; then
    echo "BLOCKED by titan-harness: no active task claimed on instance '$TITAN_INSTANCE'." >&2
    echo "To proceed: write task id to $ACTIVE_TASK_FILE or touch $BYPASS_FILE" >&2
    exit 2
  fi
fi

titan_local_audit "PRE tool=$TOOL task=${TASK_ID:-none} session=${SESSION_ID:0:12}"

titan_supabase_post "tool_log" "{\"session_id\":\"$SESSION_ID\",\"task_id\":\"${TASK_ID:-null}\",\"tool_name\":\"$TOOL\",\"result_status\":\"pre\",\"payload\":{\"instance\":\"$TITAN_INSTANCE\"}}"

exit 0
