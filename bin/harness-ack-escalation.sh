#!/usr/bin/env bash
# bin/harness-ack-escalation.sh
# Ironclad architecture §5.4 — Solon acknowledges an ESCALATE.md hard-stop.
# Usage: harness-ack-escalation.sh [incident-id]
#
# Clears ESCALATE.md and (optionally) removes the matching incident from
# open-incidents.json. Without an incident-id, clears ALL incidents that
# match the types in the current ESCALATE.md.
set -euo pipefail

INCIDENT_ID="${1:-}"
HARNESS_DIR="${TITAN_HARNESS_DIR:-$HOME/titan-harness}"
ESC="$HARNESS_DIR/ESCALATE.md"
INCIDENT_FILE="$HARNESS_DIR/.harness-state/open-incidents.json"

if [[ ! -f "$ESC" ]]; then
  echo "[ACK] No ESCALATE.md present — nothing to acknowledge."
  exit 0
fi

echo "[ACK] Current ESCALATE.md:"
echo "---"
cat "$ESC"
echo "---"

if [[ -n "$INCIDENT_ID" ]]; then
  python3 - <<PY
import json, os
f = "$INCIDENT_FILE"
if os.path.exists(f):
    data = json.load(open(f))
    before = len(data)
    data = [x for x in data if x.get('id') != "$INCIDENT_ID"]
    json.dump(data, open(f, 'w'), indent=2)
    print(f"[ACK] Incident $INCIDENT_ID cleared ({before} -> {len(data)} remaining)")
PY
else
  # Clear every incident matching the ESCALATE doc's types.
  if [[ -f "$INCIDENT_FILE" ]]; then
    python3 - <<PY
import json, os, re
f = "$INCIDENT_FILE"
esc = open("$ESC").read()
types = set(re.findall(r'Incident:\s*([A-Z_]+)', esc))
if os.path.exists(f):
    data = json.load(open(f))
    before = len(data)
    data = [x for x in data if x.get('type') not in types]
    json.dump(data, open(f, 'w'), indent=2)
    print(f"[ACK] Cleared incidents of types {sorted(types)} ({before} -> {len(data)} remaining)")
PY
  fi
fi

# Archive the escalation for audit and remove the block file.
mkdir -p "$HARNESS_DIR/logs/escalations"
ARCHIVE="$HARNESS_DIR/logs/escalations/ESCALATE_$(date +%Y%m%d_%H%M%S).md"
mv "$ESC" "$ARCHIVE"
echo "[ACK] ESCALATE.md archived to $ARCHIVE"
echo "[ACK] Harness unblocked."
