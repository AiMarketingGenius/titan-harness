#!/bin/zsh
# request_restart.sh — TitanControl Unified Restart Handler v1.0
# CT-0419 (pre_approved, urgent) — dual-engine-synthesized spec
#
# Called by BOTH self-restart (Stop/StopFailure/debug-log watcher hooks)
# and mobile command (Hammerspoon HTTP server at port 8765). Single source
# of truth for lock + teardown + relaunch + status + MCP logging.

set -euo pipefail

APP_DIR="$HOME/Library/Application Support/TitanControl"
STATE_DIR="$APP_DIR/state"
LOG_DIR="$APP_DIR/logs"
RUNNER="$APP_DIR/run_titan_session.sh"
STATUS_FILE="$STATE_DIR/status.json"
LOCK_DIR="$STATE_DIR/restart.lock"
LOCK_META="$LOCK_DIR/meta.json"
MEMORY_URL="https://memory.aimarketinggenius.io/events"
LOCK_STALE_SECS=45
TERM_WAIT=5
BOOT_WAIT_LOOPS=50   # 50 x 0.2s = 10s

mkdir -p "$STATE_DIR" "$LOG_DIR"

SOURCE="manual:mobile-command"
REASON="manual_request"
EXCHANGE_COUNT=""
REQUEST_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)         SOURCE="$2"; shift 2 ;;
    --reason)         REASON="$2"; shift 2 ;;
    --exchange-count) EXCHANGE_COUNT="$2"; shift 2 ;;
    --request-id)     REQUEST_ID="$2"; shift 2 ;;
    *) shift ;;
  esac
done

[[ -n "$REQUEST_ID" ]] || REQUEST_ID="$(date +%s)-$$-$RANDOM"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG_DIR/restart.log"; }

write_status() {
  local state="$1" note="${2:-}"
  REQUEST_ID="$REQUEST_ID" STATE="$state" NOTE="$note" SOURCE="$SOURCE" \
    REASON="$REASON" EXCHANGE_COUNT="$EXCHANGE_COUNT" python3 - "$STATUS_FILE" <<'PY'
import json, os, sys, time
path = sys.argv[1]
data = {
  "request_id": os.environ["REQUEST_ID"],
  "state": os.environ["STATE"],
  "note": os.environ.get("NOTE",""),
  "trigger_source": os.environ.get("SOURCE",""),
  "reason": os.environ.get("REASON",""),
  "exchange_count": os.environ.get("EXCHANGE_COUNT",""),
  "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  "last_trigger_ts": int(time.time()),
}
tmp = path + ".tmp"
with open(tmp, "w") as f: json.dump(data, f)
os.replace(tmp, path)
PY
}

post_memory() {
  local result="$1" latency_ms="$2" note="${3:-}"
  SOURCE="$SOURCE" REQUEST_ID="$REQUEST_ID" REASON="$REASON" \
    EXCHANGE_COUNT="$EXCHANGE_COUNT" RESULT="$result" LATENCY_MS="$latency_ms" NOTE="$note" \
    python3 <<'PY' | curl -fsS --max-time 3 -H 'Content-Type: application/json' -d @- "$MEMORY_URL" >/dev/null 2>&1 || true
import json, os, time
print(json.dumps({
  "event_type": "titan_restart",
  "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  "request_id": os.environ["REQUEST_ID"],
  "trigger_source": os.environ["SOURCE"],
  "reason": os.environ["REASON"],
  "exchange_count": os.environ.get("EXCHANGE_COUNT",""),
  "result": os.environ["RESULT"],
  "latency_ms": int(os.environ["LATENCY_MS"]),
  "note": os.environ.get("NOTE",""),
}))
PY
}

# macOS-correct liveness check (no /proc on macOS)
pid_alive() { kill -0 "$1" 2>/dev/null; }

claim_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    REQUEST_ID="$REQUEST_ID" SOURCE="$SOURCE" REASON="$REASON" python3 - > "$LOCK_META" <<'PY'
import json, os, time
print(json.dumps({
  "request_id": os.environ["REQUEST_ID"],
  "pid": os.getpid(),
  "source": os.environ["SOURCE"],
  "reason": os.environ["REASON"],
  "created_at": time.time(),
}))
PY
    return 0
  fi
  return 1
}

lock_is_stale() {
  [[ -f "$LOCK_META" ]] || return 0
  python3 - "$LOCK_META" "$LOCK_STALE_SECS" <<'PY'
import json, os, sys, time
path, ttl = sys.argv[1], int(sys.argv[2])
try:
  with open(path) as f: d = json.load(f)
  pid = int(d.get("pid", 0))
  try:
    os.kill(pid, 0); alive = True
  except (OSError, ProcessLookupError):
    alive = False
  stale = (time.time() - float(d.get("created_at", 0))) > ttl or not alive
  sys.exit(0 if stale else 1)
except Exception:
  sys.exit(0)
PY
}

kill_group()       { [[ -n "${1:-}" ]] && kill -TERM -- "-$1" 2>/dev/null || true; }
kill_group_force() { [[ -n "${1:-}" ]] && kill -KILL -- "-$1" 2>/dev/null || true; }

START_NS=$(python3 -c 'import time; print(time.time_ns())')

# Acquire lock or no-op cleanly
if ! claim_lock; then
  if lock_is_stale; then
    rm -rf "$LOCK_DIR"
    claim_lock || { log "lock_claim_failed_after_stale_reclaim"; exit 2; }
  else
    write_status "booting" "restart_already_in_progress"
    log "noop_duplicate request_id=$REQUEST_ID source=$SOURCE reason=$REASON"
    exit 0
  fi
fi

trap 'rm -rf "$LOCK_DIR" 2>/dev/null || true' EXIT

write_status "killing" "terminating_existing_session"
log "restart_begin request_id=$REQUEST_ID source=$SOURCE reason=$REASON exchange_count=$EXCHANGE_COUNT"

# PGID-based teardown
PGIDS=()
[[ -f "$STATE_DIR/titan.pgid" ]] && PGIDS+=("$(tr -d '[:space:]' < "$STATE_DIR/titan.pgid")")
while IFS= read -r pid; do
  [[ -n "$pid" ]] || continue
  pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')"
  [[ -n "$pgid" ]] && PGIDS+=("$pgid")
done < <(pgrep -f "run_titan_session\.sh|/claude($| )" || true)

typeset -A seen
for pg in "${PGIDS[@]}"; do
  [[ -n "${seen[$pg]:-}" ]] && continue
  seen[$pg]=1
  kill_group "$pg"
done

sleep "$TERM_WAIT"

for pg in "${PGIDS[@]}"; do
  pgrep -g "$pg" >/dev/null 2>&1 && kill_group_force "$pg"
done

# Clear stale state
rm -f "$STATE_DIR"/claude.pid "$STATE_DIR"/titan.pgid "$STATE_DIR"/context-ready
printf '%s' "$REQUEST_ID" > "$STATE_DIR/request_id"

# Reset exchange counter on EVERY successful self-restart (v2 bug fix)
if [[ "$SOURCE" == "self:stop-hook" ]]; then
  printf '0' > "$STATE_DIR/exchange_count"
fi

write_status "booting" "starting_fresh_session"

# Launch fresh Claude Code session in Terminal
osascript <<OSA
tell application "Terminal"
  activate
  do script "/bin/zsh -lc " & quoted form of "$RUNNER"
end tell
OSA

# Wait up to 10s for claude.pid to appear and be live
alive=0
for _ in $(seq 1 $BOOT_WAIT_LOOPS); do
  if [[ -f "$STATE_DIR/claude.pid" ]]; then
    pid="$(tr -d '[:space:]' < "$STATE_DIR/claude.pid")"
    if pid_alive "$pid"; then alive=1; break; fi
  fi
  sleep 0.2
done

END_NS=$(python3 -c 'import time; print(time.time_ns())')
LATENCY_MS=$(( (END_NS - START_NS) / 1000000 ))

if [[ "$alive" -eq 1 ]]; then
  write_status "alive" "claude_process_running"
  post_memory "success" "$LATENCY_MS" "claude_process_running"
  log "restart_success request_id=$REQUEST_ID latency_ms=$LATENCY_MS"
  exit 0
else
  write_status "failed" "claude_did_not_boot"
  post_memory "failure" "$LATENCY_MS" "claude_did_not_boot"
  log "restart_failed request_id=$REQUEST_ID latency_ms=$LATENCY_MS"
  exit 1
fi
