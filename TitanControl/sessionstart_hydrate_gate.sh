#!/bin/bash
# sessionstart_hydrate_gate.sh — CT-0419-07 Step 1 gate
#
# Runs AFTER sessionstart_hydrate_mcp.sh in the SessionStart hook chain.
# Refuses to pass the gate unless /state/mcp_hydration.json exists, is <30s old,
# and hydrate_status.json reports state="context_loaded" (or context_loaded_with_drift).
#
# On gate-miss: writes hydrate_ready.json state="hydrate_gate_refused" + reason.
# Claude Code still proceeds; Titan's first turn MUST read hydrate_ready.json +
# hydrate_status.json per boot_verification_prompt.txt and behave accordingly.
#
# This is PURE hydration-loop verification and is independent of the TitanControl
# Unified Restart Handler's sessionstart_mark_ready.sh (which writes status.json +
# context-ready for the restart state machine). Both can coexist.

set -u

TC_DIR="${HOME}/Library/Application Support/TitanControl"
STATE_DIR="${TC_DIR}/state"
HYD_FILE="${STATE_DIR}/mcp_hydration.json"
STATUS_FILE="${STATE_DIR}/hydrate_status.json"
READY_FILE="${STATE_DIR}/hydrate_ready.json"
LOG_FILE="${STATE_DIR}/hydrate_gate.log"

mkdir -p "$STATE_DIR"
touch "$LOG_FILE"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$LOG_FILE"; }

refuse() {
  local reason="$1"
  log "REFUSED: $reason"
  python3 - "$READY_FILE" "$reason" <<'PY' 2>/dev/null
import json, sys, datetime
path, reason = sys.argv[1:]
with open(path, "w") as f:
    json.dump({
        "state": "hydrate_gate_refused",
        "reason": reason,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }, f, indent=2)
PY
  exit 1
}

if [ ! -f "$HYD_FILE" ]; then
  refuse "hydration_file_missing"
fi

if [ ! -f "$STATUS_FILE" ]; then
  refuse "hydrate_status_file_missing"
fi

NOW=$(date +%s)
HYD_MTIME=$(stat -f %m "$HYD_FILE" 2>/dev/null || stat -c %Y "$HYD_FILE" 2>/dev/null)
if [ -z "$HYD_MTIME" ]; then
  refuse "hydration_mtime_unreadable"
fi
AGE=$((NOW - HYD_MTIME))
if [ "$AGE" -gt 30 ]; then
  refuse "hydration_stale_age_${AGE}s"
fi

STATE=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("state",""))' "$STATUS_FILE" 2>/dev/null)
case "$STATE" in
  context_loaded|context_loaded_with_drift)
    ;;
  *)
    refuse "bad_state_${STATE:-empty}"
    ;;
esac

VALID=$(python3 - "$HYD_FILE" <<'PY' 2>/dev/null
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    ok = (d.get("counts", {}).get("decisions", 0) > 0
          and d.get("sprint_state_hash"))
    print("VALID" if ok else "INVALID")
except Exception:
    print("INVALID")
PY
)

if [ "$VALID" != "VALID" ]; then
  refuse "hydration_content_invalid"
fi

python3 - "$READY_FILE" "$STATE" "$AGE" <<'PY' 2>/dev/null
import json, sys, datetime
path, state, age = sys.argv[1:]
with open(path, "w") as f:
    json.dump({
        "state": "hydrate_gate_passed",
        "hydration_state": state,
        "hydration_age_seconds": int(age),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }, f, indent=2)
PY

log "GATE_PASSED hydration_state=$STATE age=${AGE}s"
exit 0
