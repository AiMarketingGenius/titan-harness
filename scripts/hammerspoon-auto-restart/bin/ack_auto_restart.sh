#!/bin/bash
# scripts/hammerspoon-auto-restart/bin/ack_auto_restart.sh <restart_id> <outcome>
#
# Logs a Supabase op_decision with tags:
#   titan-auto-restart-acked
#   titan-auto-restart-acked-<restart_id>
#   outcome-<outcome>   (restarted|deferred|failed|aborted|dry_run)
# so poll_auto_restart_queue.sh stops re-serving the same restart request.

set -e

RESTART_ID="${1:-no-id}"
OUTCOME="${2:-unknown}"

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
  echo "supabase env missing" >&2
  exit 2
fi

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
PAYLOAD=$(cat <<EOF
{
  "decision_text": "titan-auto-restart-acked restart_id=$RESTART_ID outcome=$OUTCOME ts=$TS",
  "tags": ["titan-auto-restart-acked", "titan-auto-restart-acked-$RESTART_ID", "outcome-$OUTCOME", "hammerspoon-auto-restart-live"],
  "project_source": "titan"
}
EOF
)

curl -sS -X POST "$SUPABASE_URL/rest/v1/op_decisions" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=minimal" \
  --data "$PAYLOAD" >/dev/null
