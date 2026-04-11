#!/bin/bash
# titan-harness/bin/idea-list.sh — list ideas from Supabase
# Usage: idea-list.sh [--status captured|reviewing|promoted|dead] [--limit N]
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/titan-env.sh
source "$SCRIPT_DIR/../lib/titan-env.sh"

STATUS="captured"
LIMIT=20
while [ $# -gt 0 ]; do
  case "$1" in
    --status) STATUS="$2"; shift 2 ;;
    --limit)  LIMIT="$2"; shift 2 ;;
    --all)    STATUS=""; shift ;;
    -h|--help)
      echo "Usage: idea-list.sh [--status captured|reviewing|promoted|dead|--all] [--limit N]"
      exit 0 ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

QUERY="select=id,idea_title,status,instance_id,created_at&order=created_at.desc&limit=$LIMIT"
if [ -n "$STATUS" ]; then
  QUERY="${QUERY}&status=eq.$STATUS"
fi

curl -sS -G "$SUPABASE_URL/rest/v1/ideas" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  --data-urlencode "${QUERY//&/\n}" \
  2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception as e:
    print(f'ERROR parsing response: {e}', file=sys.stderr)
    sys.exit(1)
if not d:
    print('(no ideas found)')
    sys.exit(0)
print(f'{\"ID\":<38} {\"STATUS\":<10} {\"INSTANCE\":<14} {\"CREATED\":<22} TITLE')
print('-' * 120)
for row in d:
    rid = row.get('id', '')[:36]
    st = row.get('status', '')[:10]
    inst = row.get('instance_id', '')[:14]
    ct = row.get('created_at', '')[:22]
    title = (row.get('idea_title') or '')[:50]
    print(f'{rid:<38} {st:<10} {inst:<14} {ct:<22} {title}')
print()
print(f'Total: {len(d)}')
"
