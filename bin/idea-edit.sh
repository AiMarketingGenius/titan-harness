#!/bin/bash
# titan-harness/bin/idea-edit.sh — edit an idea row
# Usage: idea-edit.sh <id> [--title "..."] [--text "..."] [--status captured|reviewing|promoted|dead] [--notes "..."]
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/titan-env.sh
source "$SCRIPT_DIR/../lib/titan-env.sh"

if [ $# -lt 2 ]; then
  cat <<EOF
Usage: idea-edit.sh <id> [options]
  --title "New title"
  --text "New idea text" (note: this does NOT recompute idea_hash)
  --status captured|reviewing|promoted|dead
  --notes "Notes"
EOF
  exit 1
fi

ID="$1"; shift

# Build payload via python (safer than jq for arbitrary strings)
UPDATES=""
while [ $# -gt 0 ]; do
  case "$1" in
    --title)  UPDATES="$UPDATES idea_title $2"; shift 2 ;;
    --text)   UPDATES="$UPDATES idea_text $2"; shift 2 ;;
    --status) UPDATES="$UPDATES status $2"; shift 2 ;;
    --notes)  UPDATES="$UPDATES notes $2"; shift 2 ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

if [ -z "$UPDATES" ]; then
  echo "ERROR: no updates specified"
  exit 1
fi

PAYLOAD=$(python3 -c "
import sys, json
args = sys.argv[1:]
d = {}
for i in range(0, len(args), 2):
    d[args[i]] = args[i+1]
sys.stdout.write(json.dumps(d))
" $UPDATES)

# Note: id goes in URL query string, NOT payload
RESP=$(curl -sS -w "\n__HTTPCODE__:%{http_code}" -m 8 \
  -X PATCH "$SUPABASE_URL/rest/v1/ideas?id=eq.$ID" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d "$PAYLOAD")

HTTP_CODE=$(printf '%s' "$RESP" | sed -n 's/.*__HTTPCODE__:\([0-9]*\).*/\1/p' | tail -1)
BODY=$(printf '%s' "$RESP" | sed 's/__HTTPCODE__:[0-9]*$//')

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "204" ]; then
  echo "Idea $ID updated."
  printf '%s\n' "$BODY" | python3 -m json.tool 2>/dev/null || printf '%s\n' "$BODY"
else
  echo "ERROR: HTTP $HTTP_CODE"
  printf '%s\n' "$BODY"
  exit 1
fi
