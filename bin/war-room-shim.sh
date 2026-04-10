#!/bin/bash
# bin/war-room-shim.sh
#
# Phase G.3 — integration shim for titan-queue-watcher.
#
# Called between "executed" and "completed" checkpoints in the queue
# watcher. Decides whether a task's deliverable should be graded by the
# war room; if yes, runs war-room.sh and swaps the deliverable for the
# (possibly refined) final output.
#
# Safe by design:
#   - If war-room.sh is missing, skip silently.
#   - If war_room.enabled=false in policy, war-room.sh already exits 0
#     and just copies input → output unchanged. We still swap.
#   - Any non-zero exit from war-room.sh → keep original deliverable,
#     log warning, continue. Never blocks task completion.
#
# Usage:
#   war-room-shim.sh <task_id> <deliverable_path> <task_type> [tags_csv]
#
# Env (inherited from caller):
#   PERPLEXITY_API_KEY, ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_*
#
# Exit codes:
#   0 — done (swap may or may not have happened)
#   Never exits non-zero; failures logged but swallowed.
#
# Output:
#   Writes graded deliverable to <deliverable_path>.graded on success.
#   Prints a single summary line to stdout:
#     skipped:<reason>                — war room didn't run
#     graded:<grade>:<rounds>:<cost>  — war room ran

set -u

TASK_ID="${1:-}"
DELIVERABLE_PATH="${2:-}"
TASK_TYPE="${3:-}"
TAGS_CSV="${4:-}"

_HARNESS_DIR="/opt/titan-harness"
_WAR_ROOM="$_HARNESS_DIR/bin/war-room.sh"
_LOG="/var/log/titan-war-room.log"

_log() {
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) task=$TASK_ID $1" >> "$_LOG" 2>/dev/null
}

# ---- Sanity checks (every one bails out cleanly) ----
if [ -z "$TASK_ID" ] || [ -z "$DELIVERABLE_PATH" ]; then
  echo "skipped:bad-args"
  exit 0
fi

if [ ! -f "$DELIVERABLE_PATH" ]; then
  _log "no deliverable at $DELIVERABLE_PATH"
  echo "skipped:no-deliverable"
  exit 0
fi

if [ ! -x "$_WAR_ROOM" ]; then
  _log "war-room.sh not executable at $_WAR_ROOM"
  echo "skipped:war-room-missing"
  exit 0
fi

# Minimum deliverable length — don't war-room one-liners
_size=$(wc -c < "$DELIVERABLE_PATH" 2>/dev/null || echo 0)
if [ "$_size" -lt 200 ]; then
  echo "skipped:too-short:${_size}b"
  exit 0
fi

# ---- Trigger decision ----
# War room fires only for certain task categories. Matches:
#   1. task_type contains 'plan', 'architecture', 'phase', or 'spec'
#   2. tags include 'war_room', 'plan_finalization', 'architecture_decision',
#      'phase_completion'
#
# Everything else (routine blog writes, SEO audits, etc.) skips silently.
_trigger=""
_lower_type=$(echo "$TASK_TYPE" | tr '[:upper:]' '[:lower:]')
_lower_tags=$(echo "$TAGS_CSV" | tr '[:upper:]' '[:lower:]')

case "$_lower_type" in
  *plan*)          _trigger="plan_finalization" ;;
  *architecture*)  _trigger="architecture_decision" ;;
  *spec*)          _trigger="architecture_decision" ;;
  *phase*)         _trigger="phase_completion" ;;
esac

if [ -z "$_trigger" ]; then
  case "$_lower_tags" in
    *war_room*|*war-room*)          _trigger="manual" ;;
    *plan_finalization*)            _trigger="plan_finalization" ;;
    *architecture_decision*)        _trigger="architecture_decision" ;;
    *phase_completion*)             _trigger="phase_completion" ;;
  esac
fi

if [ -z "$_trigger" ]; then
  echo "skipped:no-trigger"
  exit 0
fi

# ---- Run the war room ----
_log "launching war-room trigger=$_trigger size=${_size}b"
_out="${DELIVERABLE_PATH}.graded"
_json="${DELIVERABLE_PATH}.war-room.json"

"$_WAR_ROOM" \
  --input "$DELIVERABLE_PATH" \
  --output "$_out" \
  --phase "$TASK_TYPE" \
  --trigger "$_trigger" \
  --json > "$_json" 2>> "$_LOG"
_rc=$?

if [ "$_rc" -ne 0 ] || [ ! -s "$_out" ]; then
  _log "war-room failed rc=$_rc, keeping original deliverable"
  echo "skipped:war-room-error:rc=$_rc"
  exit 0
fi

# Parse grade/rounds/cost from JSON
_parsed=$(python3 - <<PYEOF 2>/dev/null
import json, sys
try:
    with open("$_json") as f:
        d = json.load(f)
    print(f"{d.get('final_grade','?')}|{d.get('rounds',0)}|{d.get('total_cost_cents',0)}|{d.get('terminal_reason','?')}")
except Exception:
    print("?|0|0|parse-error")
PYEOF
)
_grade=$(echo "$_parsed" | cut -d'|' -f1)
_rounds=$(echo "$_parsed" | cut -d'|' -f2)
_cost=$(echo "$_parsed" | cut -d'|' -f3)
_term=$(echo "$_parsed" | cut -d'|' -f4)

_log "war-room complete grade=$_grade rounds=$_rounds cost=${_cost}¢ terminal=$_term"

# Only swap deliverable if the graded version is non-trivially larger.
# This protects against Haiku revisions that accidentally truncate.
_orig_size=$_size
_new_size=$(wc -c < "$_out" 2>/dev/null || echo 0)
# Allow graded to be between 50% and 500% of original size.
if [ "$_new_size" -lt $((_orig_size / 2)) ] || [ "$_new_size" -gt $((_orig_size * 5)) ]; then
  _log "graded size ${_new_size}b out of sanity range ($((_orig_size/2))–$((_orig_size*5))); keeping original"
  echo "graded:$_grade:$_rounds:$_cost:kept-original"
  exit 0
fi

# Swap
cp "$_out" "$DELIVERABLE_PATH"
echo "graded:$_grade:$_rounds:$_cost:swapped"
exit 0
