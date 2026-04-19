#!/bin/bash
# stop_hook_drift_snapshot.sh — CT-0419-07 Step 5
#
# Fires on Claude Code Stop hook. Writes last_decision_snapshot.json so the
# NEXT SessionStart hydrate script can detect cross-session data loss.
#
# Captures: last_decision_id + sprint_state_hash from current /state/mcp_hydration.json
# (written by the most recent hydrate run). Fast — no MCP round-trip in Stop hook.

set -u

TC_DIR="${HOME}/Library/Application Support/TitanControl"
STATE_DIR="${TC_DIR}/state"
HYD_FILE="${STATE_DIR}/mcp_hydration.json"
SNAP_FILE="${STATE_DIR}/last_decision_snapshot.json"
LOG_FILE="${STATE_DIR}/stop_hook.log"

mkdir -p "$STATE_DIR"
touch "$LOG_FILE"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$LOG_FILE"; }

if [ ! -f "$HYD_FILE" ]; then
  log "SKIP no hydration file"
  exit 0
fi

python3 - "$HYD_FILE" "$SNAP_FILE" <<'PY' 2>>"$LOG_FILE"
import json, sys, datetime
hyd_path, snap_path = sys.argv[1:]
try:
    with open(hyd_path) as f:
        h = json.load(f)
    snap = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "last_decision_id": h.get("last_decision_id"),
        "sprint_state_hash": h.get("sprint_state_hash"),
        "decisions_count": h.get("counts", {}).get("decisions", 0),
    }
    with open(snap_path, "w") as f:
        json.dump(snap, f, indent=2)
    print(f"SNAPSHOT_OK last_dec_id={snap['last_decision_id']}")
except Exception as e:
    print(f"SNAPSHOT_FAIL: {e}")
    sys.exit(1)
PY

exit 0
