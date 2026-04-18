#!/bin/bash
# /opt/amg-security/tla_idle_detector.sh (VPS-side; invoked by systemd timer every 60s)
#
# TLA v1.1 Path 4 — autonomous idle detection + pending-nudge writer.
# Replaces the n8n HTTP-POST-to-Mac pattern with an MCP-write pattern that
# works regardless of VPS→Mac inbound reachability. Mac Hammerspoon polls
# Supabase every 30s via lib/tla-path-4/bin/poll_nudge_queue.sh; this script
# is the PRODUCER that writes the `tla-nudge-fire-pending` decision.
#
# Triggers (per CO-ARCHITECT round-1 consensus 2026-04-18T18:28Z):
#   idle_threshold = 10 min (configurable via TLA_IDLE_MINUTES env)
#   dedupe window = 15 min (don't write new pending if one already fired)
#   urgent override: tasks with priority=urgent bypass idle gate
#   kill-switch: skip if tla-nudge-disabled OR tla-disabled tag present
#
# Exit codes:
#   0 = ran successfully (regardless of whether nudge was written)
#   1 = Supabase transport error
#   2 = kill-switch active (observational, not fatal)

set -e

TLA_IDLE_MINUTES="${TLA_IDLE_MINUTES:-10}"
TLA_DEDUPE_MINUTES="${TLA_DEDUPE_MINUTES:-15}"
LOG="${LOG:-/var/log/tla-idle-detector.log}"

load_env_safe() {
  local f="$1"
  [ -f "$f" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue ;;
      *=*)
        local key="${line%%=*}"
        local value="${line#*=}"
        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"
        [ -z "$key" ] && continue
        case "$value" in
          '"'*'"') value="${value#\"}"; value="${value%\"}" ;;
          "'"*"'") value="${value#\'}"; value="${value%\'}" ;;
        esac
        export "$key=$value"
        ;;
    esac
  done < "$f"
}
load_env_safe /etc/amg/supabase.env
load_env_safe /root/.titan-env

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  echo "[$(date -u +%FT%TZ)] FATAL: SUPABASE env missing" >> "$LOG"
  exit 1
fi

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Fetch inputs (all three queries in one Python block for atomic decision)
LATEST_TITAN=$(curl -sS "$SUPABASE_URL/rest/v1/op_decisions?select=created_at&order=created_at.desc&limit=1&project_source=eq.titan" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" 2>/dev/null || echo '[]')

PENDING_TASKS=$(curl -sS --data-urlencode "status=eq.pending" --data-urlencode "approval=eq.pre_approved" -G \
  "$SUPABASE_URL/rest/v1/op_task_queue?select=task_id,priority&order=created_at.asc&limit=20" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" 2>/dev/null || echo '[]')

KILL_NUDGE=$(curl -sS --data-urlencode "tags=cs.{tla-nudge-disabled}" -G \
  "$SUPABASE_URL/rest/v1/op_decisions?select=id&order=created_at.desc&limit=1" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" 2>/dev/null || echo '[]')

KILL_ALL=$(curl -sS --data-urlencode "tags=cs.{tla-disabled}" -G \
  "$SUPABASE_URL/rest/v1/op_decisions?select=id&order=created_at.desc&limit=1" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" 2>/dev/null || echo '[]')

RECENT_PENDING=$(curl -sS --data-urlencode "tags=cs.{tla-nudge-fire-pending}" -G \
  "$SUPABASE_URL/rest/v1/op_decisions?select=id,created_at&order=created_at.desc&limit=5" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" 2>/dev/null || echo '[]')

DECIDE=$(python3 <<PY
import json, time, re, uuid
from datetime import datetime, timezone

def safe_list(raw):
    try:
        data = json.loads(raw or '[]')
        if isinstance(data, list):
            # Keep only dict entries (defend against PostgREST error responses)
            return [x for x in data if isinstance(x, dict)]
        return []
    except Exception:
        return []

latest = safe_list('''$LATEST_TITAN''')
pending = safe_list('''$PENDING_TASKS''')
kill_nudge = safe_list('''$KILL_NUDGE''')
kill_all = safe_list('''$KILL_ALL''')
recent_pending = safe_list('''$RECENT_PENDING''')

now = int(time.time())
idle_min_threshold = int('${TLA_IDLE_MINUTES}')
dedupe_min_threshold = int('${TLA_DEDUPE_MINUTES}')

def parse_ts(s):
    s = (s or '').replace('Z', '+00:00')
    s = re.sub(r'\.\d+', lambda m: m.group(0)[:7], s)
    try: return int(datetime.fromisoformat(s).timestamp())
    except: return 0

latest_titan_ts = parse_ts((latest[0] if latest else {}).get('created_at', ''))
idle_min = 99999 if latest_titan_ts == 0 else (now - latest_titan_ts) / 60

urgent_present = any((t.get('priority') or '').lower() == 'urgent' for t in pending)

# Kill-switch (checked first)
if kill_all or kill_nudge:
    print(json.dumps({"action": "skip", "reason": "kill_switch_active", "idle_min": idle_min}))
    raise SystemExit

# Dedupe: a pending decision within last N min blocks new writes
latest_pending_ts = parse_ts((recent_pending[0] if recent_pending else {}).get('created_at', ''))
dedupe_min_since = 99999 if latest_pending_ts == 0 else (now - latest_pending_ts) / 60
if dedupe_min_since < dedupe_min_threshold and not urgent_present:
    print(json.dumps({"action": "skip", "reason": f"dedupe_window_{dedupe_min_since:.1f}m_lt_{dedupe_min_threshold}m", "idle_min": idle_min}))
    raise SystemExit

# Gate on queue + idle
if not pending:
    print(json.dumps({"action": "skip", "reason": "queue_empty", "idle_min": idle_min}))
    raise SystemExit
if idle_min < idle_min_threshold and not urgent_present:
    print(json.dumps({"action": "skip", "reason": f"idle_{idle_min:.1f}m_lt_{idle_min_threshold}m", "pending_count": len(pending)}))
    raise SystemExit

# FIRE: write a pending decision
nudge_id = str(uuid.uuid4())[:12]
phrase = "«MCP_QUEUE_POLL» poll MCP queue for pending tasks tagged today"
print(json.dumps({
    "action": "fire",
    "nudge_id": nudge_id,
    "phrase": phrase,
    "urgent": urgent_present,
    "idle_min": round(idle_min, 1),
    "pending_count": len(pending),
}))
PY
)

echo "[$TS] $DECIDE" >> "$LOG"

# Parse action field; if fire, write the pending decision
ACTION=$(printf '%s' "$DECIDE" | python3 -c "import json,sys;print(json.load(sys.stdin).get('action','skip'))")

if [ "$ACTION" = "fire" ]; then
  NUDGE_ID=$(printf '%s' "$DECIDE" | python3 -c "import json,sys;print(json.load(sys.stdin).get('nudge_id',''))")
  PHRASE=$(printf '%s' "$DECIDE" | python3 -c "import json,sys;print(json.load(sys.stdin).get('phrase',''))")
  URGENT=$(printf '%s' "$DECIDE" | python3 -c "import json,sys;print('true' if json.load(sys.stdin).get('urgent') else 'false')")
  IDLE_MIN=$(printf '%s' "$DECIDE" | python3 -c "import json,sys;print(json.load(sys.stdin).get('idle_min',0))")
  PENDING_COUNT=$(printf '%s' "$DECIDE" | python3 -c "import json,sys;print(json.load(sys.stdin).get('pending_count',0))")

  BODY=$(cat <<JSON
{
  "decision_text": "TLA PATH 4 IDLE DETECTOR FIRE nudge_id=$NUDGE_ID ts=$TS — Titan idle for ${IDLE_MIN}min with $PENDING_COUNT pre-approved pending tasks. phrase: $PHRASE |urgent=$URGENT|sig=systemd-tla-idle-detector",
  "tags": ["tla-nudge-fire-pending", "nudge-id-$NUDGE_ID", "path-4-live", "idle-detector-fire"],
  "project_source": "titan",
  "decision_type": "execution",
  "operator_id": "OPERATOR_AMG"
}
JSON
)
  curl -sS -X POST "$SUPABASE_URL/rest/v1/op_decisions" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=minimal" \
    -d "$BODY" >/dev/null
  echo "[$TS] wrote pending nudge_id=$NUDGE_ID" >> "$LOG"
fi

exit 0
