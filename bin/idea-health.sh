#!/bin/bash
# titan-harness/bin/idea-health.sh — quick health check for the idea pipeline
# Shows: queue depth, last capture, last drain, drain errors, Supabase reachability
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/titan-env.sh
source "$SCRIPT_DIR/../lib/titan-env.sh"

QUEUE_FILE="$TITAN_SESSION_DIR/ideas-queue.jsonl"
DRAIN_LOG="$TITAN_SESSION_DIR/ideas-drain.log"

echo "======================================================================"
echo "Titan Ideas Pipeline — Health Check"
echo "Instance: $TITAN_INSTANCE ($TITAN_OS)"
echo "Session dir: $TITAN_SESSION_DIR"
echo "======================================================================"
echo ""

# --- Queue state ---
if [ -f "$QUEUE_FILE" ]; then
  QUEUE_DEPTH=$(wc -l < "$QUEUE_FILE" | tr -d ' ')
  QUEUE_SIZE=$(du -h "$QUEUE_FILE" 2>/dev/null | cut -f1)
  QUEUE_MTIME=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$QUEUE_FILE" 2>/dev/null || stat -c "%y" "$QUEUE_FILE" 2>/dev/null | cut -d. -f1)
  echo "Queue file:   $QUEUE_FILE"
  echo "  depth:      $QUEUE_DEPTH lines pending"
  echo "  size:       ${QUEUE_SIZE:-?}"
  echo "  last write: $QUEUE_MTIME"
else
  echo "Queue file:   (not yet created — no ideas captured)"
fi
echo ""

# --- Drain log state ---
if [ -f "$DRAIN_LOG" ]; then
  LAST_DRAIN=$(tail -n 1 "$DRAIN_LOG" 2>/dev/null || echo "")
  # grep -c outputs 0 on no matches but ALSO exits 1. Use `|| true` to prevent double-counting via fallback.
  OK_COUNT=$(grep -c '^\[.*\] OK ' "$DRAIN_LOG" 2>/dev/null || true)
  FAIL_COUNT=$(grep -c '^\[.*\] FAIL ' "$DRAIN_LOG" 2>/dev/null || true)
  DEDUP_COUNT=$(grep -c '^\[.*\] DEDUP ' "$DRAIN_LOG" 2>/dev/null || true)
  OK_COUNT="${OK_COUNT:-0}"
  FAIL_COUNT="${FAIL_COUNT:-0}"
  DEDUP_COUNT="${DEDUP_COUNT:-0}"
  echo "Drain log:    $DRAIN_LOG"
  echo "  OK:         $OK_COUNT inserts"
  echo "  DEDUP:      $DEDUP_COUNT duplicates rejected (good)"
  echo "  FAIL:       $FAIL_COUNT errors"
  echo "  last line:  $LAST_DRAIN"
  echo ""
  if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "  Recent failures (last 5):"
    grep '^\[.*\] FAIL ' "$DRAIN_LOG" | tail -5 | sed 's/^/    /'
    echo ""
  fi
else
  echo "Drain log:    (not yet created — drainer hasn't run)"
fi
echo ""

# --- Service state ---
echo "Service / timer state:"
case "$TITAN_OS" in
  macos)
    if launchctl list 2>/dev/null | grep -q "com.titan.ideas.drain"; then
      STATUS=$(launchctl list com.titan.ideas.drain 2>/dev/null | grep -E '"(PID|LastExitStatus)"' | tr '\n' ' ')
      echo "  launchd:    LOADED — $STATUS"
    else
      echo "  launchd:    NOT LOADED (run install.sh to register)"
    fi
    ;;
  linux)
    if systemctl list-timers titan-ideas-drain.timer 2>/dev/null | grep -q titan-ideas-drain; then
      NEXT=$(systemctl list-timers titan-ideas-drain.timer --no-pager 2>/dev/null | awk 'NR==2 {print $1, $2}')
      echo "  systemd:    ACTIVE — next run: $NEXT"
    else
      echo "  systemd:    NOT ACTIVE (run install.sh to enable)"
    fi
    ;;
esac
echo ""

# --- Supabase reachability ---
if [ -n "${SUPABASE_URL:-}" ] && [ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" -m 4 \
    -G "$SUPABASE_URL/rest/v1/ideas" \
    --data-urlencode "select=id" \
    --data-urlencode "limit=1" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" 2>/dev/null)
  if [ "$HTTP_CODE" = "200" ]; then
    echo "Supabase:     ✓ reachable (ideas table responding)"
  else
    echo "Supabase:     ✗ HTTP $HTTP_CODE — table missing or auth error"
  fi

  # Recent idea count (last 24h)
  RECENT=$(curl -sS -m 4 \
    -G "$SUPABASE_URL/rest/v1/ideas" \
    --data-urlencode "select=id" \
    --data-urlencode "created_at=gte.$(date -u -v-1d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '-1 day' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(len(d) if isinstance(d, list) else '?', end='')
except Exception:
    print('?', end='')
" 2>/dev/null)
  echo "Ideas (24h):  $RECENT rows"
else
  echo "Supabase:     (not configured — SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing)"
fi
echo ""
echo "======================================================================"
