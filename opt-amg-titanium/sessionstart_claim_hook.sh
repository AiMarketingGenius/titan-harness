#!/usr/bin/env bash
# sessionstart_claim_hook.sh — TITANIUM DOCTRINE v1.0 Gap 6(C).
#
# Fires on SessionStart AFTER sessionstart_mark_ready.sh. Queries MCP
# for highest-priority urgent pre_approved task assigned to titan. If
# found, writes/refreshes ~/titan-session/NEXT_TASK.md so the boot
# greeting includes it as Now/Next. Non-blocking — exits 0 silently if
# MCP unreachable or queue empty (doesn't block session start).

set -euo pipefail

readonly SESSION_DIR="$HOME/titan-session"
readonly NEXT_TASK="$SESSION_DIR/NEXT_TASK.md"
readonly LOG_FILE="$HOME/titan-harness/logs/sessionstart_claim_hook.log"
mkdir -p "$SESSION_DIR" "$(dirname "$LOG_FILE")"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG_FILE"; }

for env_file in "$HOME/.titan-env" "/opt/amg-titan/.env"; do
  [ -f "$env_file" ] && . "$env_file"
done

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  log "skip: supabase env missing"
  exit 0
fi

# Check if NEXT_TASK.md is already current (<1h old) — if so, don't clobber
if [ -f "$NEXT_TASK" ]; then
  mtime_file=$(stat -f%m "$NEXT_TASK" 2>/dev/null || stat -c%Y "$NEXT_TASK" 2>/dev/null || echo 0)
  now=$(date +%s)
  if [ $((now - mtime_file)) -lt 3600 ]; then
    log "NEXT_TASK.md fresh (<1h); preserving"
    exit 0
  fi
fi

# Query for highest-priority urgent pre_approved
task_row=$(curl -sS --max-time 10 -G "$SUPABASE_URL/rest/v1/operator_task_queue" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  --data-urlencode "select=task_id,objective,priority,approval,status,created_at" \
  --data-urlencode "assigned_to=eq.titan" \
  --data-urlencode "approval=eq.pre_approved" \
  --data-urlencode "status=in.(approved,queued)" \
  --data-urlencode "order=priority.asc,created_at.asc" \
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
  log "queue empty"
  exit 0
fi

# Write NEXT_TASK.md
printf '%s' "$task_row" | python3 -c "
import json, sys, datetime as d
r = json.loads(sys.stdin.read() or '[]')
if not r: sys.exit(0)
t = r[0]
path = '$NEXT_TASK'
with open(path, 'w') as f:
    f.write(f'# NEXT TASK (auto-claimed by sessionstart_claim_hook.sh)\n\n')
    f.write(f'**Task:** {t[\"task_id\"]}\n')
    f.write(f'**Priority:** {t[\"priority\"]}\n')
    f.write(f'**Written:** {d.datetime.utcnow().isoformat()}Z\n\n')
    f.write(f'## Objective\n\n{t.get(\"objective\",\"\")}\n\n')
    f.write(f'Claim via mcp__claim_task(operator_id=\"titan\", task_id=\"{t[\"task_id\"]}\") and execute.\n')
"

log "wrote NEXT_TASK.md for $tid"
exit 0
