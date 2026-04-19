#!/bin/zsh
# sessionstart_mark_ready.sh — TitanControl Restart Handler v1.0
# Writes status.json state=context_loaded + drops context-ready marker.
#
# Part of the RESTART state machine — NOT the CT-0419-07 hydration gate
# (that one is sessionstart_hydrate_gate.sh + writes hydrate_status.json).
# Both hooks coexist safely in the SessionStart chain.

set -euo pipefail

STATE_DIR="$HOME/Library/Application Support/TitanControl/state"
STATUS_FILE="$STATE_DIR/status.json"

mkdir -p "$STATE_DIR"
touch "$STATE_DIR/context-ready"

python3 - "$STATUS_FILE" <<'PY'
import json, os, sys, time
path = sys.argv[1]
req_path = os.path.expanduser("~/Library/Application Support/TitanControl/state/request_id")
req = open(req_path).read().strip() if os.path.exists(req_path) else ""
data = {
  "request_id": req,
  "state": "context_loaded",
  "note": "sessionstart_ok",
  "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
tmp = path + ".tmp"
with open(tmp, "w") as f: json.dump(data, f)
os.replace(tmp, path)
PY
