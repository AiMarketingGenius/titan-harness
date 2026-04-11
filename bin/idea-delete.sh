#!/bin/bash
# titan-harness/bin/idea-delete.sh — soft-delete an idea (sets status='dead')
# Use --hard to hard-delete (row removed entirely).
# Usage: idea-delete.sh <id> [--hard]
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/titan-env.sh
source "$SCRIPT_DIR/../lib/titan-env.sh"

if [ $# -lt 1 ]; then
  echo "Usage: idea-delete.sh <id> [--hard]"
  exit 1
fi

ID="$1"
HARD=0
if [ "${2:-}" = "--hard" ]; then
  HARD=1
fi

if [ "$HARD" -eq 1 ]; then
  RESP=$(curl -sS -w "\n__HTTPCODE__:%{http_code}" -m 8 \
    -X DELETE "$SUPABASE_URL/rest/v1/ideas?id=eq.$ID" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY")
  HTTP_CODE=$(printf '%s' "$RESP" | sed -n 's/.*__HTTPCODE__:\([0-9]*\).*/\1/p' | tail -1)
  if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "204" ]; then
    echo "Idea $ID HARD-deleted (row removed)."
  else
    echo "ERROR: HTTP $HTTP_CODE"
    printf '%s\n' "$RESP"
    exit 1
  fi
else
  # Soft delete — PATCH status to 'dead'
  RESP=$(curl -sS -w "\n__HTTPCODE__:%{http_code}" -m 8 \
    -X PATCH "$SUPABASE_URL/rest/v1/ideas?id=eq.$ID" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=minimal" \
    -d '{"status":"dead"}')
  HTTP_CODE=$(printf '%s' "$RESP" | sed -n 's/.*__HTTPCODE__:\([0-9]*\).*/\1/p' | tail -1)
  if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "204" ]; then
    echo "Idea $ID soft-deleted (status='dead'; row retained for audit)."
  else
    echo "ERROR: HTTP $HTTP_CODE"
    printf '%s\n' "$RESP"
    exit 1
  fi
fi
