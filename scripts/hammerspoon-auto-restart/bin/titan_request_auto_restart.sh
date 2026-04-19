#!/bin/bash
# scripts/hammerspoon-auto-restart/bin/titan_request_auto_restart.sh
#
# Called by Titan (Claude Code) when emitting RESTART_HANDOFF at ≥85% context.
# Logs a Supabase op_decision tagged `titan-auto-restart-pending` + a unique
# `restart-id-<uuid>` so Hammerspoon's poll_auto_restart_queue.sh picks it up
# within 30s and triggers the quit → pause → relaunch → inject cycle.
#
# Optional env / args:
#   WAKE_PHRASE (env or --wake-phrase)     Defaults to MCP-handoff resume phrase.
#   HANDOFF_COMMIT (env or --commit)       Defaults to current HEAD.
#   REASON (env or --reason)               Defaults to "context-wall".
#
# Exit 0 = request logged to MCP
# Exit 2 = env / transport error

set -e

WAKE_PHRASE_DEFAULT="Wake. §13.1b poll. Resume Sunday runway per MCP RESTART_HANDOFF."
REASON="${REASON:-context-wall}"
HANDOFF_COMMIT="${HANDOFF_COMMIT:-}"
WAKE_PHRASE="${WAKE_PHRASE:-}"
DRY_RUN="${DRY_RUN:-0}"

while [ $# -gt 0 ]; do
  case "$1" in
    --wake-phrase) WAKE_PHRASE="$2"; shift 2 ;;
    --commit)      HANDOFF_COMMIT="$2"; shift 2 ;;
    --reason)      REASON="$2"; shift 2 ;;
    --dry-run)     DRY_RUN=1; shift ;;
    *) echo "unknown arg $1" >&2; exit 2 ;;
  esac
done

[ -z "$WAKE_PHRASE" ] && WAKE_PHRASE="$WAKE_PHRASE_DEFAULT"

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
  echo "{\"error\":\"supabase_env_missing\"}" >&2
  exit 2
fi

if [ -z "$HANDOFF_COMMIT" ] && command -v git >/dev/null 2>&1; then
  HANDOFF_COMMIT=$(git -C "$HOME/titan-harness" rev-parse --short HEAD 2>/dev/null || echo "unknown")
fi

RESTART_ID=$(uuidgen 2>/dev/null | tr 'A-Z' 'a-z' || python3 -c 'import uuid; print(uuid.uuid4())')
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

BODY="titan-auto-restart request
restart_id: $RESTART_ID
wake_phrase: $WAKE_PHRASE
reason: $REASON
handoff_commit: $HANDOFF_COMMIT
requested_at: $TS"

if [ "$DRY_RUN" = "1" ]; then
  cat <<EOF
{"dry_run": true, "restart_id": "$RESTART_ID", "wake_phrase": "$WAKE_PHRASE", "reason": "$REASON", "handoff_commit": "$HANDOFF_COMMIT"}
EOF
  exit 0
fi

PAYLOAD=$(python3 -c "
import json, sys
payload = {
  'decision_text': '''$BODY''',
  'tags': [
    'titan-auto-restart-pending',
    'restart-id-$RESTART_ID',
    'hammerspoon-auto-restart-live',
    'reason-$REASON',
  ],
  'project_source': 'titan',
}
print(json.dumps(payload))
")

curl -sS -X POST "$SUPABASE_URL/rest/v1/op_decisions" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=minimal" \
  --data "$PAYLOAD" >/dev/null

cat <<EOF
{"restart_id": "$RESTART_ID", "logged": true, "wake_phrase": "$WAKE_PHRASE", "reason": "$REASON"}
EOF
