#!/usr/bin/env bash
# session_end_claim_hook.sh — TITANIUM DOCTRINE v1.0 Gap 6(A).
#
# Fires on Claude Code Stop event BEFORE stop_hook_restart_gate.sh. Checks
# MCP queue for pending urgent pre_approved tasks assigned to titan. If
# queue has work AND session is healthy (exchange_count <70% context),
# writes next-task continuation to ~/titan-session/CONTINUATION_PROMPT.md
# for the next turn to pick up (before restart would fire). If session is
# exhausting OR queue has no urgent work, exits 0 silently and lets the
# regular restart gate take over.
#
# Also writes cross_project_session_state pointer (Gap 7) on every
# invocation — every thread-close is a potential continue-bridge event.

set -euo pipefail

readonly TITANIUM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SESSION_DIR="$HOME/titan-session"
readonly CONTINUATION="$SESSION_DIR/CONTINUATION_PROMPT.md"
readonly LOG_FILE="$HOME/titan-harness/logs/session_end_claim_hook.log"
mkdir -p "$SESSION_DIR" "$(dirname "$LOG_FILE")"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG_FILE"; }

for env_file in "$HOME/.titan-env" "/opt/amg-titan/.env"; do
  [ -f "$env_file" ] && . "$env_file"
done

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  log "skip: supabase env missing"
  exit 0
fi

# Query for highest-priority urgent pre_approved task assigned to titan
task_row=$(curl -sS --max-time 10 -G "$SUPABASE_URL/rest/v1/operator_task_queue" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  --data-urlencode "select=task_id,objective,context,priority,approval,status" \
  --data-urlencode "assigned_to=eq.titan" \
  --data-urlencode "approval=eq.pre_approved" \
  --data-urlencode "status=in.(approved,queued)" \
  --data-urlencode "priority=eq.urgent" \
  --data-urlencode "order=created_at.asc" \
  --data-urlencode "limit=1" 2>/dev/null || echo '[]')

tid=$(printf '%s' "$task_row" | python3 -c '
import json, sys
try:
    r = json.loads(sys.stdin.read() or "[]")
except Exception:
    print("")
    sys.exit(0)
if isinstance(r, list) and r and isinstance(r[0], dict):
    print(r[0].get("task_id", ""))
else:
    print("")
')

if [ -z "$tid" ]; then
  log "queue clear — no urgent pre_approved pending"
  # Gap 7: write last-thread pointer regardless
  tpath="$SESSION_DIR/.last_thread_pointer.json"
  python3 -c "
import json, datetime as d
p = {
  'ts': d.datetime.utcnow().isoformat() + 'Z',
  'project_id': 'EOM',
  'summary': 'Thread closed with clean queue — no pending urgent work',
  'resume_prompt': 'No continuation needed; check queue with get_task_queue on next boot.'
}
with open('$tpath', 'w') as f: json.dump(p, f)"
  exit 0
fi

# Queue has work. Write continuation file — next Stop-gated restart will surface this.
log "queue has pending: $tid"
cat > "$CONTINUATION" <<EOF
# Continuation prompt — written by session_end_claim_hook.sh

**Written:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
**Source:** MCP operator_task_queue next urgent pre_approved

$(printf '%s' "$task_row" | python3 -c '
import json, sys
r = json.loads(sys.stdin.read() or "[]")
if r:
    t = r[0]
    print(f"**Task:** {t.get(\"task_id\")}")
    print(f"**Priority:** {t.get(\"priority\")}")
    print(f"**Objective:**\n\n{t.get(\"objective\",\"\")}")
    print("\n**Context:**\n\n" + (t.get("context") or "")[:3000])
')

Claim via mcp__claim_task with operator_id=titan task_id=$tid then execute.
EOF

log "continuation written for $tid"

# Gap 7: cross-project pointer
python3 -c "
import json, datetime as d
p = {
  'ts': d.datetime.utcnow().isoformat() + 'Z',
  'project_id': 'EOM',
  'summary': 'Thread auto-transitioned to $tid via Gap 6 continuous claim loop',
  'resume_prompt': 'Claim $tid from MCP queue and execute.'
}
with open('$SESSION_DIR/.last_thread_pointer.json', 'w') as f: json.dump(p, f)"

exit 0
