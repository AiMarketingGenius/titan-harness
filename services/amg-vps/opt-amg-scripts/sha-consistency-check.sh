#!/bin/bash
# /opt/amg/scripts/sha-consistency-check.sh — DELTA-D (2026-04-14)
# Canonical source: ~/titan-harness/services/amg-vps/opt-amg-scripts/sha-consistency-check.sh
#
# Weekly check: compares VPS-side expected SHA file (/opt/amg/.sha256-expected.txt)
# against harness-side expected SHA file (/opt/titan-harness/services/amg-vps/sha256-expected.txt).
# Catches silent tampering of the VPS-side file itself — someone bypassing git
# to edit /opt/amg/.sha256-expected.txt to hide a real drift.
#
# If divergent: Tier 2 — security event, VPS expected file has been altered
# outside the harness deploy pipeline.
#
# Reversible by: scp harness copy → VPS. But first determine if VPS-side was
# tampered OR harness-side is behind on a legitimate update.

set -uo pipefail
VPS_EXPECTED="/opt/amg/.sha256-expected.txt"
HARNESS_EXPECTED="/opt/titan-harness/services/amg-vps/sha256-expected.txt"
LOG="/var/log/amg/watchdog.jsonl"

ts() { date -u +%Y-%m-%dT%H:%M:%S.%3NZ; }

emit() {
  local event="$1" detail="$2" tier="$3"
  local escaped_detail="${detail//\"/\\\"}"
  echo "{\"ts\":\"$(ts)\",\"domain\":\"sha_consistency\",\"event\":\"$event\",\"detail\":\"$escaped_detail\",\"tier\":$tier,\"metrics\":{}}" >> "$LOG"
}

if [[ ! -f "$VPS_EXPECTED" ]]; then
  emit "VPS_EXPECTED_MISSING" "$VPS_EXPECTED absent — drift checkers cannot function" 2
  exit 1
fi

if [[ ! -f "$HARNESS_EXPECTED" ]]; then
  emit "HARNESS_EXPECTED_MISSING" "$HARNESS_EXPECTED absent — harness mirror may be broken" 2
  exit 1
fi

# Check harness mirror freshness first
cd /opt/titan-harness 2>/dev/null || {
  emit "HARNESS_MIRROR_MISSING" "/opt/titan-harness is not a git repo" 2
  exit 1
}

# Pull latest from origin (bare repo on same VPS) — non-blocking, tolerate failures
git fetch origin master 2>/dev/null || true
BEHIND=$(git rev-list --count HEAD..origin/master 2>/dev/null || echo "unknown")
if [[ "$BEHIND" != "0" && "$BEHIND" != "unknown" ]]; then
  git merge --ff-only origin/master 2>/dev/null || true
fi

# Now compare
VPS_SHA=$(sha256sum "$VPS_EXPECTED" | awk '{print $1}')
HARNESS_SHA=$(sha256sum "$HARNESS_EXPECTED" | awk '{print $1}')

if [[ "$VPS_SHA" == "$HARNESS_SHA" ]]; then
  emit "SHA_CONSISTENCY_OK" "VPS ↔ harness expected-SHA files match (${VPS_SHA:0:12}...)" 0
  exit 0
fi

emit "SHA_EXPECTED_DIVERGENCE" "VPS $VPS_EXPECTED ($VPS_SHA) != harness $HARNESS_EXPECTED ($HARNESS_SHA) — possible VPS-side tampering OR harness update not deployed" 2
exit 1
