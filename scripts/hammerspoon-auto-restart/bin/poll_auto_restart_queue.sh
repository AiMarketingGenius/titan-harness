#!/bin/bash
# scripts/hammerspoon-auto-restart/bin/poll_auto_restart_queue.sh
#
# Mac-side poller for titan_auto_restart.lua. Queries Supabase op_decisions
# for the most recent unacked titan-auto-restart-pending request and emits
# JSON for the Lua handler. Also surfaces the kill-switch tag so the Lua
# side can refuse to act.
#
# Emits (stdout):
#   {"restart": true, "restart_id": "...", "wake_phrase": "...", "reason": "..."}
#   {"restart": false, "reason": "..."}
#   {"disabled": true, "reason": "kill-switch-active"}
#
# Exit 0 = query ok   Exit 2 = transport/env error

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
  echo '{"restart":false,"reason":"supabase_env_missing"}'
  exit 2
fi

TMPDIR=$(mktemp -d -t titan-auto-restart-poll.XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT

curl -sS --data-urlencode "tags=cs.{titan-auto-restart-disabled}" -G \
  "$SUPABASE_URL/rest/v1/op_decisions?select=id,created_at&order=created_at.desc&limit=1" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -o "$TMPDIR/disabled.json" 2>/dev/null

curl -sS --data-urlencode "tags=cs.{titan-auto-restart-enabled}" -G \
  "$SUPABASE_URL/rest/v1/op_decisions?select=id,created_at&order=created_at.desc&limit=1" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -o "$TMPDIR/enabled.json" 2>/dev/null

curl -sS --data-urlencode "tags=cs.{titan-auto-restart-pending}" -G \
  "$SUPABASE_URL/rest/v1/op_decisions?select=id,tags,decision_text,created_at&order=created_at.desc&limit=5" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -o "$TMPDIR/pending.json" 2>/dev/null

curl -sS --data-urlencode "tags=cs.{titan-auto-restart-acked}" -G \
  "$SUPABASE_URL/rest/v1/op_decisions?select=id,tags,decision_text,created_at&order=created_at.desc&limit=20" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -o "$TMPDIR/acked.json" 2>/dev/null

python3 - "$TMPDIR/disabled.json" "$TMPDIR/enabled.json" "$TMPDIR/pending.json" "$TMPDIR/acked.json" <<'PY'
import json, re, sys, time
from datetime import datetime

def load(p):
    try:
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

disabled_rows = load(sys.argv[1])
enabled_rows  = load(sys.argv[2])
pending_rows  = load(sys.argv[3])
acked_rows    = load(sys.argv[4])

def parse_ts(s):
    if not s:
        return 0
    s = s.replace('Z', '+00:00')
    # Python 3.9 datetime.fromisoformat requires exactly 6 microsecond digits.
    # Pad or truncate fractional seconds to 6.
    m = re.match(r'(.+?)\.(\d+)(.*)$', s)
    if m:
        pre, frac, post = m.group(1), m.group(2), m.group(3)
        frac = (frac + '000000')[:6]
        s = f"{pre}.{frac}{post}"
    try:
        return int(datetime.fromisoformat(s).timestamp())
    except Exception:
        return 0

now = int(time.time())

latest_disabled_ts = max((parse_ts(r.get('created_at', '')) for r in disabled_rows), default=0)
latest_enabled_ts  = max((parse_ts(r.get('created_at', '')) for r in enabled_rows),  default=0)

# Disable if: latest disabled is < 24h old AND newer than latest enable.
if latest_disabled_ts > 0 and (now - latest_disabled_ts) < 86400 and latest_disabled_ts > latest_enabled_ts:
    print(json.dumps({
        "disabled": True,
        "reason": "kill-switch-active",
        "age_s": now - latest_disabled_ts,
    }))
    sys.exit(0)

acked_ids = set()
for r in acked_rows:
    for t in (r.get('tags') or []):
        m = re.match(r'^titan-auto-restart-acked-(.+)$', t)
        if m:
            acked_ids.add(m.group(1))

out = {"restart": False, "reason": "no_pending"}
for row in pending_rows:
    tags = row.get('tags') or []
    rid = None
    for t in tags:
        m = re.match(r'^restart-id-(.+)$', t)
        if m:
            rid = m.group(1)
            break
    if not rid:
        continue
    if rid in acked_ids:
        continue
    ts = parse_ts(row.get('created_at', ''))
    if now - ts > 600:  # 10 min freshness
        continue
    body = row.get('decision_text', '') or ''
    phrase_m = re.search(r'wake_phrase:\s*(.+?)(?:\n|$)', body)
    reason_m = re.search(r'reason:\s*(.+?)(?:\n|$)', body)
    phrase = phrase_m.group(1).strip() if phrase_m else None
    reason = reason_m.group(1).strip() if reason_m else "context-wall"
    out = {
        "restart": True,
        "restart_id": rid,
        "wake_phrase": phrase,
        "reason": reason,
        "age_seconds": now - ts,
    }
    break
print(json.dumps(out))
PY
