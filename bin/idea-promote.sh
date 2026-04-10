#!/bin/bash
# titan-harness/bin/idea-promote.sh
#
# Promote an idea into the strict `tasks` table as a full CT-MMDD-NN task.
# Marks the source idea with status='promoted' and fills promoted_to_task_id.
#
# Usage:
#   idea-promote.sh <idea-id> \
#     --objective "One sentence: what's the deliverable?" \
#     --instructions "Numbered steps..." \
#     --acceptance "Measurable definition of done" \
#     [--priority urgent|normal|low] \
#     [--project EOM] \
#     [--agent alex|maya|jordan|sam|riley|nadia|lumina|ops]

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/titan-env.sh
source "$SCRIPT_DIR/../lib/titan-env.sh"

if [ $# -lt 1 ]; then
  cat <<EOF
Usage: idea-promote.sh <idea-id> [options]
Required options:
  --objective    "One-sentence deliverable"
  --instructions "Numbered steps to execute"
  --acceptance   "Measurable definition of done"
Optional:
  --priority     urgent|normal|low  (default: normal)
  --project      EOM                (default: EOM)
  --agent        alex|maya|jordan|sam|riley|nadia|lumina|ops
EOF
  exit 1
fi

IDEA_ID="$1"; shift
OBJECTIVE=""
INSTRUCTIONS=""
ACCEPTANCE=""
PRIORITY="normal"
PROJECT="EOM"
AGENT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --objective)    OBJECTIVE="$2"; shift 2 ;;
    --instructions) INSTRUCTIONS="$2"; shift 2 ;;
    --acceptance)   ACCEPTANCE="$2"; shift 2 ;;
    --priority)     PRIORITY="$2"; shift 2 ;;
    --project)      PROJECT="$2"; shift 2 ;;
    --agent)        AGENT="$2"; shift 2 ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

if [ -z "$OBJECTIVE" ] || [ -z "$INSTRUCTIONS" ] || [ -z "$ACCEPTANCE" ]; then
  echo "ERROR: --objective, --instructions, --acceptance are all required"
  exit 1
fi

# Fetch the idea row
IDEA_RESP=$(curl -sS -m 6 \
  -G "$SUPABASE_URL/rest/v1/ideas" \
  --data-urlencode "id=eq.$IDEA_ID" \
  --data-urlencode "select=id,idea_text,idea_title,status" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY")

IDEA_FOUND=$(printf '%s' "$IDEA_RESP" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    if isinstance(d, list) and len(d) > 0:
        print('yes')
        print(d[0].get('idea_title',''))
        print(d[0].get('status',''))
    else:
        print('no')
except Exception as e:
    print('error')
    print(str(e))
" 2>/dev/null)

FOUND=$(printf '%s' "$IDEA_FOUND" | head -1)
if [ "$FOUND" != "yes" ]; then
  echo "ERROR: idea $IDEA_ID not found or API error"
  echo "$IDEA_RESP"
  exit 1
fi

CURRENT_STATUS=$(printf '%s' "$IDEA_FOUND" | sed -n 3p)
if [ "$CURRENT_STATUS" = "promoted" ]; then
  echo "WARN: idea $IDEA_ID already promoted; aborting to prevent duplicate tasks"
  exit 1
fi

# Generate task_id in CT-MMDD-NN format
# Get next NN by counting existing tasks from today
TODAY=$(date +%m%d)
COUNT_RESP=$(curl -sS -m 6 \
  -G "$SUPABASE_URL/rest/v1/tasks" \
  --data-urlencode "task_id=like.CT-${TODAY}-%" \
  --data-urlencode "select=task_id" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY")

NEXT_NN=$(printf '%s' "$COUNT_RESP" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ids = [row.get('task_id','') for row in d if isinstance(row, dict)]
    nums = []
    for tid in ids:
        parts = tid.split('-')
        if len(parts) == 3 and parts[2].isdigit():
            nums.append(int(parts[2]))
    nxt = (max(nums) + 1) if nums else 1
    print(f'{nxt:02d}', end='')
except Exception:
    print('01', end='')
")

TASK_ID="CT-${TODAY}-${NEXT_NN}"

# Build task payload (env vars BEFORE `python3` — bash prefix-assignment syntax)
TASK_PAYLOAD=$(
  TASK_ID_VAR="$TASK_ID" \
  PRIORITY_VAR="$PRIORITY" \
  OBJECTIVE_VAR="$OBJECTIVE" \
  INSTRUCTIONS_VAR="$INSTRUCTIONS" \
  ACCEPTANCE_VAR="$ACCEPTANCE" \
  PROJECT_VAR="$PROJECT" \
  AGENT_VAR="$AGENT" \
  IDEA_ID_VAR="$IDEA_ID" \
  python3 -c "
import json, os, sys
d = {
    'task_id': os.environ['TASK_ID_VAR'],
    'priority': os.environ['PRIORITY_VAR'],
    'objective': os.environ['OBJECTIVE_VAR'],
    'instructions': os.environ['INSTRUCTIONS_VAR'],
    'acceptance_criteria': os.environ['ACCEPTANCE_VAR'],
    'project_id': os.environ['PROJECT_VAR'],
    'assigned_to': 'titan',
    'approval': 'pending',
    'status': 'pending',
    'queued_by': f\"idea-promote:{os.environ['IDEA_ID_VAR']}\",
    'tags': ['promoted-from-idea', os.environ['IDEA_ID_VAR']],
}
agent = os.environ.get('AGENT_VAR', '')
if agent:
    d['agent'] = agent
sys.stdout.write(json.dumps(d))
")

CREATE_RESP=$(curl -sS -w "\n__HTTPCODE__:%{http_code}" -m 8 \
  -X POST "$SUPABASE_URL/rest/v1/tasks" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d "$TASK_PAYLOAD")

HTTP_CODE=$(printf '%s' "$CREATE_RESP" | sed -n 's/.*__HTTPCODE__:\([0-9]*\).*/\1/p' | tail -1)
if [ "$HTTP_CODE" != "201" ] && [ "$HTTP_CODE" != "200" ]; then
  echo "ERROR: failed to create task ($HTTP_CODE)"
  printf '%s\n' "$CREATE_RESP"
  exit 1
fi

# Mark source idea as promoted
curl -sS -m 6 \
  -X PATCH "$SUPABASE_URL/rest/v1/ideas?id=eq.$IDEA_ID" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=minimal" \
  -d "{\"status\":\"promoted\",\"promoted_to_task_id\":\"$TASK_ID\"}" > /dev/null

echo "✓ Idea $IDEA_ID promoted to task $TASK_ID"
echo "  objective:   $OBJECTIVE"
echo "  priority:    $PRIORITY"
echo "  project:     $PROJECT"
echo "  approval:    pending (awaiting your approval before titan-queue-watcher picks it up)"
