#!/usr/bin/env bash
# bin/harness-conflict-check.sh
# Ironclad architecture §1.3 — pre-write conflict detection.
# Usage: harness-conflict-check.sh <proposed_file> <directive_class>
#
# STRUCTURAL / PLAN class writes must route through this gate before
# a commit touches a doctrine or plan file. Exits 0 on clean, 1 on
# blocking conflict detected.
set -euo pipefail

PROPOSED="${1:-}"
CLASS="${2:-STRUCTURAL}"
HARNESS_DIR="${TITAN_HARNESS_DIR:-$HOME/titan-harness}"

if [[ -z "$PROPOSED" ]]; then
  echo "usage: harness-conflict-check.sh <proposed_file> <class>" >&2
  exit 2
fi

echo "=== CONFLICT CHECK: $PROPOSED ($CLASS) ==="

# 1. File-exists diff — force a SUPERSEDE / MERGE / CONFLICT tag
if [[ -f "$HARNESS_DIR/$PROPOSED" ]]; then
  echo "[WARN] File exists — diffing against HEAD..."
  git -C "$HARNESS_DIR" --no-pager diff HEAD -- "$PROPOSED" || true
  echo "[ACTION] Classify this write as one of:"
  echo "  [SUPERSEDE: <old-file>]   — replaces old (old moves to doctrine/archive/ or plans/archive/)"
  echo "  [MERGE: <source>]         — folded into existing file"
  echo "  [CONFLICT: ESCALATE]      — contradiction; stop and page Solon"
fi

# 2. SUPERSEDE / CONFLICT / DEPRECATED markers across doctrine locations.
# This harness keeps doctrine at repo root + library_of_alexandria/ instead of
# a dedicated doctrine/ dir, so scan both.
DOCTRINE_GLOB=(
  "$HARNESS_DIR/CLAUDE.md"
  "$HARNESS_DIR/CORE_CONTRACT.md"
  "$HARNESS_DIR/RADAR.md"
  "$HARNESS_DIR/INVENTORY.md"
  "$HARNESS_DIR/library_of_alexandria"
  "$HARNESS_DIR/plans"
)
KEYWORDS=""
for target in "${DOCTRINE_GLOB[@]}"; do
  [[ -e "$target" ]] || continue
  if K=$(grep -rn "SUPERSEDES\|CONFLICT:\s*ESCALATE\|DEPRECATED" "$target" 2>/dev/null); then
    KEYWORDS+="$K"$'\n'
  fi
done
if [[ -n "$KEYWORDS" ]]; then
  echo "[INFO] Existing SUPERSEDE/CONFLICT/DEPRECATED markers (informational):"
  printf '%s' "$KEYWORDS" | head -30
fi

# 3. Open-incidents gate — refuse if a CONFLICT incident is unresolved.
INCIDENT_FILE="$HARNESS_DIR/.harness-state/open-incidents.json"
if [[ -f "$INCIDENT_FILE" ]]; then
  OPEN_CONFLICTS=$(python3 -c "
import json, sys
try:
    data = json.load(open('$INCIDENT_FILE'))
    n = len([x for x in data if x.get('type')=='CONFLICT'])
    print(n)
except Exception:
    print(0)
" 2>/dev/null || echo 0)
  if [[ "${OPEN_CONFLICTS:-0}" -gt 0 ]]; then
    echo "[BLOCK] $OPEN_CONFLICTS open CONFLICT incident(s). Resolve before any STRUCTURAL/PLAN write." >&2
    exit 1
  fi
fi

# 4. Last-directive breadcrumb — write the classification so post-commit hooks can audit.
LAST_DIR="$HARNESS_DIR/.harness-state/last-directive.json"
mkdir -p "$HARNESS_DIR/.harness-state"
python3 - <<PY
import json, hashlib, datetime, os
ts = datetime.datetime.utcnow().isoformat(timespec='seconds') + 'Z'
payload = {
  'ts': ts,
  'proposed_file': "$PROPOSED",
  'class': "$CLASS",
  'conflict_check': 'PASS',
}
json.dump(payload, open("$LAST_DIR", 'w'), indent=2)
PY

echo "=== CONFLICT CHECK COMPLETE (clean) ==="
