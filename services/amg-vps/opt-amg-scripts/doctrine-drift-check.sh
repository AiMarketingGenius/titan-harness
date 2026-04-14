#!/bin/bash
# /opt/amg/scripts/doctrine-drift-check.sh — DELTA-D (2026-04-14)
# Canonical source: ~/titan-harness/services/amg-vps/opt-amg-scripts/doctrine-drift-check.sh
#
# Checks the AMG Self-Healing Doctrine v1 file SHA against expected (harness-
# tracked, deployed to VPS at /opt/amg/.sha256-expected.txt). Emits
# DOCTRINE_DRIFT Tier-1 event to watchdog.jsonl on mismatch. Read-only — does
# NOT auto-revert (drift may be a legitimate doctrine update).
#
# Tier 1 = digest. Operational drift, low urgency. For security-critical
# drift see config-drift-check.sh.

set -uo pipefail
EXPECTED_FILE="/opt/amg/.sha256-expected.txt"
DOCTRINE="/opt/amg/docs/amg-self-healing-doctrine-v1.md"
LOG="/var/log/amg/watchdog.jsonl"

ts() { date -u +%Y-%m-%dT%H:%M:%S.%3NZ; }

emit() {
  local event="$1" detail="$2" tier="$3"
  # Escape double quotes in detail for JSON
  local escaped_detail="${detail//\"/\\\"}"
  echo "{\"ts\":\"$(ts)\",\"domain\":\"doctrine\",\"event\":\"$event\",\"detail\":\"$escaped_detail\",\"tier\":$tier,\"metrics\":{}}" >> "$LOG"
}

if [[ ! -f "$DOCTRINE" ]]; then
  emit "DOCTRINE_MISSING" "$DOCTRINE absent" 2
  exit 1
fi

if [[ ! -f "$EXPECTED_FILE" ]]; then
  emit "EXPECTED_SHA_MISSING" "$EXPECTED_FILE absent — cannot verify drift" 1
  exit 1
fi

EXPECTED=$(grep "$DOCTRINE" "$EXPECTED_FILE" 2>/dev/null | awk '{print $1}')
if [[ -z "$EXPECTED" ]]; then
  emit "EXPECTED_SHA_NOT_LISTED" "$DOCTRINE not in $EXPECTED_FILE" 1
  exit 1
fi

ACTUAL=$(sha256sum "$DOCTRINE" | awk '{print $1}')

if [[ "$ACTUAL" == "$EXPECTED" ]]; then
  emit "DOCTRINE_SHA_OK" "matches expected ${EXPECTED:0:12}..." 0
  exit 0
fi

emit "DOCTRINE_DRIFT" "expected=${EXPECTED:0:12}... actual=${ACTUAL:0:12}... — operator review required" 1
exit 1
