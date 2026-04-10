#!/bin/bash
# session-start.sh — SessionStart hook
# Prints latest NEXT_TASK from Supabase + latest HANDOVER tail into Claude context.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/titan-env.sh"

echo "===== TITAN HARNESS — instance: $TITAN_INSTANCE ($TITAN_OS) ====="
echo "Session dir: $TITAN_SESSION_DIR"

# Pull NEXT_TASK from Supabase (source of truth)
if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  NEXT=$(curl -s -m 5 "$SUPABASE_URL/rest/v1/session_next_task?id=eq.1&select=ts,task_id,summary,body,updated_by_instance" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" 2>/dev/null)
  if [ -n "$NEXT" ] && [ "$NEXT" != "[]" ]; then
    echo ""
    echo "===== NEXT_TASK (from Supabase) ====="
    echo "$NEXT" | python3 -c "
import sys, json
try:
  d = json.load(sys.stdin)
  if d:
    r = d[0]
    print(f\"Updated: {r.get('ts','')} by {r.get('updated_by_instance','')}\")
    print(f\"Task ID: {r.get('task_id','(none)')}\")
    print(f\"Summary: {r.get('summary','(none)')}\")
    body = r.get('body') or {}
    if body: print(f\"Body: {json.dumps(body)[:500]}\")
except Exception as e:
  print(f'(parse error: {e})')
"
  fi
  
  # Pull last 3 session_handover entries
  HOV=$(curl -s -m 5 "$SUPABASE_URL/rest/v1/session_handover?select=ts,instance,close_reason,summary&order=ts.desc&limit=3" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" 2>/dev/null)
  if [ -n "$HOV" ] && [ "$HOV" != "[]" ]; then
    echo ""
    echo "===== RECENT HANDOVERS (last 3 across all instances) ====="
    echo "$HOV" | python3 -c "
import sys, json
try:
  for r in json.load(sys.stdin):
    print(f\"  [{r.get('ts','')[:19]}] {r.get('instance','?')} — {r.get('close_reason','?')} — {(r.get('summary') or '')[:80]}\")
except: pass
"
  fi
fi

# Post session_start to titan_audit_log
SID="${TITAN_INSTANCE}-$(date -u +%Y%m%dT%H%M%SZ)"
titan_supabase_post "titan_audit_log" "{\"session_id\":\"$SID\",\"action\":\"session_start\",\"actor\":\"titan\",\"payload\":{\"instance\":\"$TITAN_INSTANCE\",\"os\":\"$TITAN_OS\"}}"

titan_local_audit "SESSION_START instance=$TITAN_INSTANCE"

# If on Linux VPS with boot-audit.sh present, also run it
if [ "$TITAN_OS" = "linux" ] && [ -x /opt/titan-session/boot-audit.sh ]; then
  echo ""
  echo "===== BOOT AUDIT (VPS) ====="
  /opt/titan-session/boot-audit.sh 2>&1 | head -40
fi

exit 0
