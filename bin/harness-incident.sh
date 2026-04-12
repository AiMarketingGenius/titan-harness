#!/usr/bin/env bash
# bin/harness-incident.sh
# Ironclad architecture §5.3 — append an incident record to open-incidents.json.
# Usage: harness-incident.sh <TYPE> <MESSAGE> [severity]
#
# Types used by the harness: DRIFT_DETECTED, VPS_UNREACHABLE, GH_PUSH_FAILED,
# MIRROR_TOTAL_FAILURE, CONFLICT, ROLLBACK_EXECUTED, BATCH_DLQ_HIGH,
# CAPACITY_HARD_BREACH, POST_RECEIVE_MISSING.
set -euo pipefail

TYPE="${1:-}"
MSG="${2:-}"
SEV="${3:-HIGH}"
HARNESS_DIR="${TITAN_HARNESS_DIR:-$HOME/titan-harness}"
INCIDENT_FILE="$HARNESS_DIR/.harness-state/open-incidents.json"

if [[ -z "$TYPE" || -z "$MSG" ]]; then
  echo "usage: harness-incident.sh <TYPE> <MESSAGE> [severity]" >&2
  exit 2
fi

mkdir -p "$HARNESS_DIR/.harness-state"

python3 - <<PY
import json, os, datetime, uuid
f = "$INCIDENT_FILE"
data = []
if os.path.exists(f):
    try:
        data = json.load(open(f))
        if not isinstance(data, list):
            data = []
    except Exception:
        data = []
data.append({
  'id': str(uuid.uuid4())[:8],
  'ts': datetime.datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'type': "$TYPE",
  'severity': "$SEV",
  'message': """$MSG""",
})
json.dump(data, open(f, 'w'), indent=2)
print(f"[INCIDENT] Logged {data[-1]['id']} type=$TYPE sev=$SEV")
PY

# Mirror to the VPS incident log shape for parity (local file).
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"type\":\"$TYPE\",\"severity\":\"$SEV\",\"message\":\"$MSG\"}" \
  >> "$HARNESS_DIR/logs/titan-incidents.log"
