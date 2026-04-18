#!/bin/bash
# scripts/tla-path-4/bin/ack_nudge.sh <nudge_id> <outcome>
#
# Mac-side ack: writes `tla-nudge-fire-acked-<nudge_id>` MCP decision after
# Hammerspoon has (a) injected the phrase, (b) deferred, or (c) errored.
# outcome = injected | deferred | failed | dry_run

set -e
NUDGE_ID="${1:-unknown}"
OUTCOME="${2:-unknown}"
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

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

BODY=$(cat <<JSON
{
  "decision_text": "TLA PATH 4 NUDGE ACKED nudge_id=$NUDGE_ID outcome=$OUTCOME ts=$TS — Hammerspoon processed MCP-polled nudge signal, took action per outcome. Dedupe guard: this ack tag prevents re-injection on subsequent poll cycles within the pending record's 5-min freshness window.",
  "tags": ["tla-nudge-fire-acked", "tla-nudge-fire-acked-$NUDGE_ID", "outcome-$OUTCOME", "path-4-live"],
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
echo "acked $NUDGE_ID $OUTCOME"
