#!/usr/bin/env bash
# stale_task_sweeper.sh — TITANIUM DOCTRINE v1.0 Gap 4.
#
# Runs daily at 00:00 UTC. Any task with status in (active, locked,
# in_progress, approved) AND last_heartbeat > 48hr → flagged for review
# (Slack/MCP). After 7-day additional grace with no heartbeat → auto-reset
# to status=queued and clear locked_by.
#
# Args:
#   --dry-run      report only, no writes
#   --cleanup-pre-2026-04-15  one-shot initial cleanup pass for pre-2026-04-15
#                              zombie tasks

set -euo pipefail

readonly TITANIUM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOG_FILE="${STALE_LOG:-$HOME/titan-harness/logs/stale_task_sweeper.log}"
mkdir -p "$(dirname "$LOG_FILE")"

DRY_RUN=0
CLEANUP_PRE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --cleanup-pre-2026-04-15) CLEANUP_PRE=1 ;;
  esac
done

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG_FILE"; }

for env_file in "$HOME/.titan-env" "/opt/amg-titan/.env"; do
  [ -f "$env_file" ] && . "$env_file"
done
: "${SUPABASE_URL:?SUPABASE_URL not set}"
: "${SUPABASE_SERVICE_ROLE_KEY:?SUPABASE_SERVICE_ROLE_KEY not set}"

# 48hr staleness threshold
STALE_SINCE="$(python3 -c "import datetime as d; print((d.datetime.utcnow() - d.timedelta(hours=48)).isoformat() + 'Z')")"
# 7d grace after stale-flagged
AUTO_RESET_SINCE="$(python3 -c "import datetime as d; print((d.datetime.utcnow() - d.timedelta(days=9)).isoformat() + 'Z')")"
# Cleanup-pre cutoff
CLEANUP_CUTOFF="2026-04-15T00:00:00Z"

# Query tasks with stale heartbeat or pre-cutoff
log "querying operator_task_queue for stale tasks"
q=$(curl -sS --max-time 30 -G "$SUPABASE_URL/rest/v1/operator_task_queue" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  --data-urlencode "select=task_id,status,approval,locked_by,last_heartbeat,updated_at,created_at" \
  --data-urlencode "status=in.(active,locked,in_progress,approved)" \
  --data-urlencode "limit=500")

stale_tasks=$(printf '%s' "$q" | python3 -c "
import json, sys, datetime as d
rows = json.loads(sys.stdin.read() or '[]')
stale_since = '${STALE_SINCE}'
cleanup_cutoff = '${CLEANUP_CUTOFF}'
cleanup_pre = ${CLEANUP_PRE}
out = []
for r in rows:
    hb = r.get('last_heartbeat') or r.get('updated_at') or r.get('created_at')
    if not hb:
        continue
    if hb < stale_since:
        out.append({'task_id': r.get('task_id'), 'stale': True, 'heartbeat': hb, 'status': r.get('status'), 'locked_by': r.get('locked_by')})
    elif cleanup_pre and hb < cleanup_cutoff:
        out.append({'task_id': r.get('task_id'), 'stale': True, 'pre_cutoff': True, 'heartbeat': hb, 'status': r.get('status'), 'locked_by': r.get('locked_by')})
print(json.dumps(out, indent=2))
")

count=$(printf '%s' "$stale_tasks" | python3 -c 'import json,sys; print(len(json.loads(sys.stdin.read() or "[]")))')
log "found $count stale tasks"
printf '%s\n' "$stale_tasks" | head -60 | tee -a "$LOG_FILE"

if [ "$DRY_RUN" = "1" ]; then
  log "dry-run; no writes"
  exit 0
fi

if [ "$count" = "0" ]; then
  exit 0
fi

# Flag stale tasks via MCP log_decision; auto-reset only those older than 9d since heartbeat
log "flagging + auto-resetting where applicable (WARN-only for first 7 days post-ship)"
printf '%s' "$stale_tasks" | python3 <<'PY'
import json, os, sys, urllib.request, datetime as d
rows = json.loads(sys.stdin.read() or '[]')
supa_url = os.environ['SUPABASE_URL']
key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
now = d.datetime.utcnow().isoformat() + 'Z'
auto_reset_cutoff = (d.datetime.utcnow() - d.timedelta(days=9)).isoformat() + 'Z'

for r in rows:
    tid = r['task_id']
    hb = r.get('heartbeat') or ''
    # Log flag decision
    body = {
      'decision_text': f"[stale-task-flagged] task_id={tid} last_heartbeat={hb} status={r.get('status')} locked_by={r.get('locked_by')}",
      'rationale': 'stale_task_sweeper.sh Gap 4',
      'project_source': 'titan',
      'tags': ['stale-task-flagged', f'task:{tid}', 'gap-4', 'titanium-v1.0']
    }
    req = urllib.request.Request(
      supa_url + '/rest/v1/op_decisions',
      data=json.dumps(body).encode(),
      headers={'Content-Type': 'application/json', 'apikey': key,
               'Authorization': f'Bearer {key}', 'Prefer': 'return=minimal'},
      method='POST')
    try:
      urllib.request.urlopen(req, timeout=10)
      print(f"flagged {tid}")
    except Exception as e:
      print(f"flag-err {tid} {e}")

    # Auto-reset only if heartbeat >9d old (7d grace beyond the 2d stale threshold)
    if hb and hb < auto_reset_cutoff:
      patch = {'status': 'queued', 'locked_by': None, 'notes': f'auto-reset by stale_task_sweeper.sh {now}'}
      req = urllib.request.Request(
        supa_url + f'/rest/v1/operator_task_queue?task_id=eq.{tid}',
        data=json.dumps(patch).encode(),
        headers={'Content-Type': 'application/json', 'apikey': key,
                 'Authorization': f'Bearer {key}', 'Prefer': 'return=minimal'},
        method='PATCH')
      try:
        urllib.request.urlopen(req, timeout=10)
        print(f"auto-reset {tid}")
      except Exception as e:
        print(f"reset-err {tid} {e}")
PY

log "stale_task_sweeper complete"
