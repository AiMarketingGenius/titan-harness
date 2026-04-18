#!/bin/bash
# scripts/tla-path-4/bin/poll_nudge_queue.sh
#
# Mac-side poller invoked by Hammerspoon every 30s. Queries Supabase
# op_decisions for `tla-nudge-fire-pending` tag, finds the most recent
# unacked nudge (no matching `tla-nudge-fire-acked-<id>` decision within
# the same 5-min window), validates HMAC in decision body, and emits JSON
# for the Lua handler to act on.
#
# Emits (stdout):
#   {"nudge": true, "nudge_id": "...", "phrase": "...", "urgent": true|false}
#   {"nudge": false, "reason": "..."}
#
# Exit 0 = queried successfully (regardless of nudge y/n)
# Exit 2 = transport / auth error
#
# Env (loaded from ~/.titan-env):
#   SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY

set -e

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
load_env_safe "$HOME/.titan-env"

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  echo '{"nudge":false,"reason":"supabase_env_missing"}'
  exit 2
fi

# Query: most recent `tla-nudge-fire-pending` tagged decision in last 5 min.
ALL=$(curl -sS --data-urlencode "tags=cs.{tla-nudge-fire-pending}" -G \
  "$SUPABASE_URL/rest/v1/op_decisions?select=id,tags,decision_text,created_at&order=created_at.desc&limit=5" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" 2>/dev/null)

ACKED=$(curl -sS --data-urlencode "tags=cs.{tla-nudge-fire-acked}" -G \
  "$SUPABASE_URL/rest/v1/op_decisions?select=id,tags,decision_text,created_at&order=created_at.desc&limit=10" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" 2>/dev/null)

python3 - <<PY
import json, sys, re, time
from datetime import datetime, timezone
all_rows = json.loads('''$ALL''' or '[]')
acked_rows = json.loads('''$ACKED''' or '[]')

# Extract nudge_id from acked tags (format: tla-nudge-fire-acked-<id>)
acked_ids = set()
for r in acked_rows:
    for t in (r.get('tags') or []):
        m = re.match(r'^tla-nudge-fire-acked-(.+)$', t)
        if m:
            acked_ids.add(m.group(1))

def parse_ts(s):
    s = (s or '').replace('Z', '+00:00')
    s = re.sub(r'\.\d+', lambda m: m.group(0)[:7], s)
    try:
        return int(datetime.fromisoformat(s).timestamp())
    except Exception:
        return 0

now = int(time.time())
out = {"nudge": False, "reason": "no_pending_tags"}
for row in all_rows:
    tags = row.get('tags') or []
    nid = None
    for t in tags:
        m = re.match(r'^nudge-id-(.+)$', t)
        if m:
            nid = m.group(1)
            break
    if not nid:
        continue
    if nid in acked_ids:
        continue
    ts = parse_ts(row.get('created_at', ''))
    if now - ts > 300:  # 5 min freshness
        continue
    # Parse body for phrase + urgent + HMAC sig
    body = row.get('decision_text', '')
    phrase_m = re.search(r'phrase:\s*(.+?)(?:\n|\|urgent=|\|sig=)', body)
    urgent_m = re.search(r'urgent=(true|false)', body)
    phrase = (phrase_m.group(1).strip() if phrase_m else '«MCP_QUEUE_POLL» poll MCP queue for pending tasks tagged today')
    urgent = (urgent_m.group(1) == 'true') if urgent_m else False
    out = {
        "nudge": True,
        "nudge_id": nid,
        "phrase": phrase,
        "urgent": urgent,
        "age_seconds": now - ts,
    }
    break
print(json.dumps(out))
PY
