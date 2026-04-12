#!/usr/bin/env bash
# lib/fast-mode.sh
# Ironclad architecture §4.5 — shell helpers for blaze/fast mode.
# Source this, then call fast_mode_enable / fast_mode_opt_out <task_type>.

fast_mode_enable() {
  export TITAN_FAST_MODE=1
  export TITAN_STREAMING=1
  export TITAN_PARALLEL_THINKING=1
  echo "[FAST-MODE] enabled: streaming=ON parallel_thinking=ON"
}

fast_mode_disable() {
  export TITAN_FAST_MODE=0
  export TITAN_STREAMING=0
  export TITAN_PARALLEL_THINKING=0
  echo "[FAST-MODE] disabled"
}

fast_mode_opt_out() {
  local TASK_TYPE="${1:-}"
  local OPT_OUT_LIST="plan architecture war_room_revise deep_debug"
  for t in $OPT_OUT_LIST; do
    if [[ "$TASK_TYPE" == "$t" ]]; then
      export TITAN_FAST_MODE=0
      export TITAN_STREAMING=0
      echo "[FAST-MODE] opt-out for task_type=$TASK_TYPE"
      local HARNESS="${TITAN_HARNESS_DIR:-$HOME/titan-harness}"
      mkdir -p "$HARNESS/.harness-state"
      python3 - <<PY
import json, os, datetime
f = "$HARNESS/.harness-state/fast_mode_events.json"
events = []
if os.path.exists(f):
    try:
        events = json.load(open(f))
    except Exception:
        events = []
events.append({
  'ts': datetime.datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'task_type': "$TASK_TYPE",
  'action': 'opt_out',
})
json.dump(events[-200:], open(f, 'w'), indent=2)
PY
      return
    fi
  done
}
