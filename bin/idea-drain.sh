#!/bin/bash
# titan-harness/bin/idea-drain.sh
#
# Sole Supabase writer for the idea capture pipeline.
#
# Reads ~/titan-session/ideas-queue.jsonl line-by-line, POSTs each idea
# into public.ideas, and removes successfully-inserted lines from the
# queue. Failures (network, 5xx, etc.) stay in the queue for retry on
# the next drain cycle.
#
# A DB-layer UNIQUE (idea_hash, created_at::date) constraint means that
# if the same idea is queued twice and both are drained, Postgres rejects
# the second with HTTP 409 — we treat 409 as success (idempotent).
#
# Slack ping fires ONCE per successful insert, after the DB write, so the
# Slack message = confirmed in DB.
#
# Invoked by: titan-ideas-drain.timer (linux) or launchd plist (macos).
# Runs every 60s. Stateless. Safe to run concurrently (atomic file rename).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/titan-env.sh
source "$SCRIPT_DIR/../lib/titan-env.sh"

QUEUE_FILE="$TITAN_SESSION_DIR/ideas-queue.jsonl"
DRAIN_LOG="$TITAN_SESSION_DIR/ideas-drain.log"
LOCK_FILE="$TITAN_SESSION_DIR/ideas-drain.lock"

# --- Concurrency lock ---
if ! (set -o noclobber; echo "$$" > "$LOCK_FILE") 2>/dev/null; then
  # Another drainer is running or lock is stale (>5 min)
  if [ -f "$LOCK_FILE" ]; then
    LOCK_AGE=$(( $(date +%s) - $(stat -f %m "$LOCK_FILE" 2>/dev/null || stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0) ))
    if [ "$LOCK_AGE" -gt 300 ]; then
      rm -f "$LOCK_FILE"
      (set -o noclobber; echo "$$" > "$LOCK_FILE") 2>/dev/null || exit 0
    else
      exit 0
    fi
  else
    exit 0
  fi
fi
trap 'rm -f "$LOCK_FILE"' EXIT

# --- Nothing to do? ---
if [ ! -s "$QUEUE_FILE" ]; then
  exit 0
fi

# --- Config ---
if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  echo "[$(date -Iseconds)] FATAL missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY" >> "$DRAIN_LOG"
  exit 1
fi

IDEA_SLACK_WEBHOOK="${IDEA_SLACK_WEBHOOK:-${SLACK_WEBHOOK_URL:-}}"

# --- Atomic take: move queue file aside so new appends go to a fresh file ---
WORK_FILE="${QUEUE_FILE}.draining.$$"
mv "$QUEUE_FILE" "$WORK_FILE"
touch "$QUEUE_FILE"

# --- Drain loop ---
FAILED_FILE="${WORK_FILE}.failed"
: > "$FAILED_FILE"

TOTAL=0
OK=0
FAILED=0
DUPLICATE=0

while IFS= read -r LINE || [ -n "$LINE" ]; do
  [ -z "$LINE" ] && continue
  TOTAL=$((TOTAL + 1))

  # Send insert via Prefer: return=representation so we get the row back
  # (needed to grab the generated id for the Slack message + edit helpers).
  RESP=$(curl -sS -w "\n__HTTPCODE__:%{http_code}" -m 8 \
    -X POST "$SUPABASE_URL/rest/v1/ideas" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=representation" \
    -d "$LINE" 2>&1) || {
      echo "[$(date -Iseconds)] CURL_ERROR line=${LINE:0:80}" >> "$DRAIN_LOG"
      printf '%s\n' "$LINE" >> "$FAILED_FILE"
      FAILED=$((FAILED + 1))
      continue
    }

  HTTP_CODE=$(printf '%s' "$RESP" | sed -n 's/.*__HTTPCODE__:\([0-9]*\).*/\1/p' | tail -1)
  BODY=$(printf '%s' "$RESP" | sed 's/__HTTPCODE__:[0-9]*$//')

  case "$HTTP_CODE" in
    201|200)
      OK=$((OK + 1))
      # Extract the new row's id + idea_title via python for reliable JSON parse
      ROW_ID=$(printf '%s' "$BODY" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    if isinstance(d, list) and len(d) > 0:
        print(d[0].get('id', ''), end='')
except Exception:
    pass
" 2>/dev/null)
      ROW_TITLE=$(printf '%s' "$BODY" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    if isinstance(d, list) and len(d) > 0:
        print(d[0].get('idea_title', ''), end='')
except Exception:
    pass
" 2>/dev/null)

      echo "[$(date -Iseconds)] OK id=$ROW_ID title=\"${ROW_TITLE:0:60}\"" >> "$DRAIN_LOG"

      # Slack ping — after successful insert only
      if [ -n "$IDEA_SLACK_WEBHOOK" ]; then
        # Build ping payload via python to avoid shell escaping hell
        # Env vars go BEFORE `python3` (bash prefix-assignment syntax).
        SLACK_PAYLOAD=$(
          ROW_TITLE_VAR="$ROW_TITLE" \
          ROW_ID_VAR="$ROW_ID" \
          TITAN_INSTANCE_VAR="$TITAN_INSTANCE" \
          python3 -c "
import json, os, sys
title = os.environ.get('ROW_TITLE_VAR', '')
row_id = os.environ.get('ROW_ID_VAR', '')
instance = os.environ.get('TITAN_INSTANCE_VAR', '')
text = f'🔒 Idea locked by {instance}: *{title}*\n> id: {row_id}'
sys.stdout.write(json.dumps({'text': text}))
")

        curl -sS -m 4 -X POST "$IDEA_SLACK_WEBHOOK" \
          -H "Content-Type: application/json" \
          -d "$SLACK_PAYLOAD" > /dev/null 2>&1 || true
      fi
      ;;
    409)
      # Unique violation = DB-layer dedup hit. Treat as success (idempotent).
      DUPLICATE=$((DUPLICATE + 1))
      echo "[$(date -Iseconds)] DEDUP line=${LINE:0:80}" >> "$DRAIN_LOG"
      ;;
    *)
      FAILED=$((FAILED + 1))
      echo "[$(date -Iseconds)] FAIL http=$HTTP_CODE body=${BODY:0:200}" >> "$DRAIN_LOG"
      printf '%s\n' "$LINE" >> "$FAILED_FILE"
      ;;
  esac
done < "$WORK_FILE"

# --- Put any failed lines BACK at the head of the queue for retry ---
if [ -s "$FAILED_FILE" ]; then
  TMP=$(mktemp)
  cat "$FAILED_FILE" "$QUEUE_FILE" > "$TMP"
  mv "$TMP" "$QUEUE_FILE"
fi

rm -f "$WORK_FILE" "$FAILED_FILE"

echo "[$(date -Iseconds)] DRAIN total=$TOTAL ok=$OK dedup=$DUPLICATE failed=$FAILED" >> "$DRAIN_LOG"

# Also log to Supabase tool_log for cross-instance visibility (fire-and-forget)
titan_supabase_post "tool_log" "{\"tool_name\":\"idea-drain\",\"result_status\":\"complete\",\"payload\":{\"instance\":\"$TITAN_INSTANCE\",\"total\":$TOTAL,\"ok\":$OK,\"dedup\":$DUPLICATE,\"failed\":$FAILED}}"

exit 0
