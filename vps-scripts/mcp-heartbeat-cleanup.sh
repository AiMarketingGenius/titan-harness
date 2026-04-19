#!/bin/bash
# mcp-heartbeat-cleanup.sh — CT-0419-07 Step 2 auxiliary
#
# Prunes heartbeat decisions older than 7 days from op_decisions to avoid
# polluting the table at ~8760 heartbeats/year. Runs weekly via systemd timer.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./mcp-common.sh
. "$SCRIPT_DIR/mcp-common.sh"

LOG_FILE="/opt/amg/logs/mcp-heartbeat-cleanup.log"
mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$LOG_FILE"; }

mcp_env_load
mcp_require_env || { log "FAIL missing_env"; exit 1; }

CUTOFF="$(python3 -c 'import datetime; print((datetime.datetime.utcnow()-datetime.timedelta(days=7)).isoformat()+"Z")')"

# DELETE via PostgREST: filter tags contains heartbeat AND created_at < cutoff
# Note: requires RLS delete policy; fall back to no-op if 401/403.
RESP=$(curl -sS -m 10 -w '\nHTTP:%{http_code}' -X DELETE \
  "${SUPABASE_URL}/rest/v1/op_decisions?tags=cs.{heartbeat}&created_at=lt.${CUTOFF}" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Prefer: return=minimal" 2>/dev/null)

HTTP=$(echo "$RESP" | grep -oE 'HTTP:[0-9]+$' | cut -d: -f2)

case "$HTTP" in
  200|204)
    log "OK pruned_before=${CUTOFF}"
    ;;
  401|403)
    log "SKIP insufficient_privileges http=${HTTP} (RLS policy may block DELETE on op_decisions; non-fatal)"
    ;;
  *)
    log "FAIL http=${HTTP} cutoff=${CUTOFF}"
    exit 2
    ;;
esac

exit 0
