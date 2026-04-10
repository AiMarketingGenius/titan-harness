#!/bin/bash
# session-end.sh — SessionEnd hook
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/titan-env.sh"

INPUT=$(cat 2>/dev/null || echo '{}')
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null || echo "")
REASON=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('reason',''))" 2>/dev/null || echo "")
DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)

ACTIVE_TASK=""
[ -f "$TITAN_SESSION_DIR/ACTIVE_TASK_ID" ] && ACTIVE_TASK=$(cat "$TITAN_SESSION_DIR/ACTIVE_TASK_ID" 2>/dev/null)

RECENT_TAIL=$(tail -20 "$TITAN_SESSION_DIR/audit.log" 2>/dev/null | python3 -c "
import sys, json
lines = sys.stdin.read().strip().split('\n')
print(json.dumps(lines))
" 2>/dev/null)
[ -z "$RECENT_TAIL" ] && RECENT_TAIL='[]'

# Append to local HANDOVER.md cache
cat >> "$TITAN_SESSION_DIR/HANDOVER.md" << HOV

## Session closed: $DATE
- Instance: $TITAN_INSTANCE ($TITAN_OS)
- Session ID: ${SESSION_ID:0:12}
- Close reason: ${REASON:-unknown}
- Active task at close: ${ACTIVE_TASK:-none}

HOV

titan_local_audit "SESSION_END instance=$TITAN_INSTANCE reason=${REASON:-unknown}"

# Post session_handover row (source of truth)
SAFE_REASON=$(echo "${REASON:-unknown}" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")
SAFE_SUMMARY="Session from $TITAN_INSTANCE"
BODY="{\"instance\":\"$TITAN_INSTANCE\",\"session_id\":\"${SESSION_ID:-unknown}\",\"close_reason\":${SAFE_REASON},\"active_task_id\":\"${ACTIVE_TASK:-null}\",\"summary\":\"$SAFE_SUMMARY\",\"tool_tail\":$RECENT_TAIL}"
titan_supabase_post "session_handover" "$BODY"

# Also post to titan_audit_log
titan_supabase_post "titan_audit_log" "{\"session_id\":\"${SESSION_ID:-unknown}\",\"task_id\":\"${ACTIVE_TASK:-null}\",\"action\":\"session_end\",\"actor\":\"titan\",\"payload\":{\"instance\":\"$TITAN_INSTANCE\",\"reason\":${SAFE_REASON}}}"

exit 0
