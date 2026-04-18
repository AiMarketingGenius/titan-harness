#!/bin/bash
# scripts/tla-path-4/bin/log_mcp_invocation.sh
#
# Called by tla_nudge.lua post-injection to write an MCP `op_decisions` row
# tagged `tla-invocation-path-4` capturing the phrase + timestamp.
#
# Usage: bash log_mcp_invocation.sh <tag> <phrase-excerpt>
#
# Env needed (loaded from ~/.titan-env):
#   SUPABASE_URL
#   SUPABASE_SERVICE_ROLE_KEY

set -e
TAG="${1:-tla-invocation-path-4}"
PHRASE_EXCERPT="${2:-<no-phrase-provided>}"
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

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  echo "SUPABASE env missing — cannot log MCP invocation" >&2
  exit 3
fi

BODY=$(cat <<JSON
{
  "decision_text": "TLA Path 4 nudge injected at $TS. Phrase excerpt: $PHRASE_EXCERPT",
  "tags": ["$TAG", "path-4-live", "hammerspoon-injection"],
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

echo "MCP invocation logged: $TAG"
