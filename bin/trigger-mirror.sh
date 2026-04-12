#!/usr/bin/env bash
# bin/trigger-mirror.sh
# Ironclad architecture §2.4 — manual mirror trigger.
# Wraps the same logic the post-commit hook runs, so you can re-fire a mirror
# without making a new commit (e.g., after installing hooks for the first time).
set -euo pipefail

HARNESS_DIR="${TITAN_HARNESS_DIR:-$HOME/titan-harness}"
BRANCH="$(git -C "$HARNESS_DIR" rev-parse --abbrev-ref HEAD)"
LOG="$HARNESS_DIR/logs/mirror-$(date +%Y%m%d).log"
mkdir -p "$HARNESS_DIR/logs"

echo "[TRIGGER-MIRROR] $(date -u +%Y-%m-%dT%H:%M:%SZ) branch=$BRANCH" | tee -a "$LOG"

cd "$HARNESS_DIR"

# Leg 1: Mac → VPS bare (origin)
if git push origin "$BRANCH" 2>&1 | tee -a "$LOG"; then
  echo "[MIRROR:MAC→VPS] OK" | tee -a "$LOG"
  MAC_VPS=OK
else
  echo "[MIRROR:MAC→VPS] FAILED" | tee -a "$LOG"
  MAC_VPS=FAIL
fi

# Leg 1b: Mac → GitHub (fallback OR parallel, depending on MAC_VPS state)
if git remote | grep -qx github; then
  if git push github "$BRANCH" 2>&1 | tee -a "$LOG"; then
    echo "[MIRROR:MAC→GH] OK" | tee -a "$LOG"
    MAC_GH=OK
  else
    echo "[MIRROR:MAC→GH] FAILED" | tee -a "$LOG"
    MAC_GH=FAIL
  fi
else
  MAC_GH=SKIP
fi

# Incident logic
if [[ "$MAC_VPS" = "FAIL" && "$MAC_GH" != "OK" ]]; then
  bash "$HARNESS_DIR/bin/harness-incident.sh" "MIRROR_TOTAL_FAILURE" "Both origin and github pushes failed" "CRITICAL"
  bash "$HARNESS_DIR/bin/update-mirror-status.sh" "TRIGGER_MIRROR" "FAIL" || true
  exit 1
elif [[ "$MAC_VPS" = "FAIL" && "$MAC_GH" = "OK" ]]; then
  bash "$HARNESS_DIR/bin/harness-incident.sh" "VPS_UNREACHABLE" "origin unreachable, github OK" "HIGH"
fi

bash "$HARNESS_DIR/bin/update-mirror-status.sh" "TRIGGER_MIRROR" "OK" || true
echo "[TRIGGER-MIRROR] done" | tee -a "$LOG"
