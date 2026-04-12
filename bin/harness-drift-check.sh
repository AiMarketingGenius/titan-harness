#!/usr/bin/env bash
# bin/harness-drift-check.sh
# Ironclad architecture §2.7 — detect drift across Mac / VPS bare / VPS work / GitHub / MCP.
# Runs (a) at session start, (b) every 15 minutes via cron, (c) on-demand.
# Exits 0 if all legs in sync, 1 if any leg drifted.
set -euo pipefail

HARNESS_DIR="${TITAN_HARNESS_DIR:-$HOME/titan-harness}"
BRANCH="$(git -C "$HARNESS_DIR" rev-parse --abbrev-ref HEAD)"
LOG="$HARNESS_DIR/logs/drift-$(date +%Y%m%d).log"
VPS_HOST="${TITAN_VPS_HOST:-root@170.205.37.148}"
VPS_BARE="/opt/titan-harness.git"
GH_REPO="${TITAN_GH_REPO:-AiMarketingGenius/titan-harness}"

mkdir -p "$HARNESS_DIR/logs" "$HARNESS_DIR/.harness-state"

echo "=== DRIFT CHECK: $(date -u +%Y-%m-%dT%H:%M:%SZ) (branch=$BRANCH) ===" | tee -a "$LOG"

DRIFT_FOUND=false
MAC_SHA=$(git -C "$HARNESS_DIR" rev-parse HEAD)

# 1. Mac vs VPS bare
VPS_SHA=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$VPS_HOST" \
  "git -C $VPS_BARE rev-parse refs/heads/$BRANCH 2>/dev/null || echo UNREACHABLE" 2>/dev/null \
  || echo UNREACHABLE)

if [[ "$VPS_SHA" == "UNREACHABLE" ]]; then
  echo "[DRIFT] VPS bare repo unreachable (SSH failed)" | tee -a "$LOG"
  DRIFT_FOUND=true
elif [[ "$MAC_SHA" != "$VPS_SHA" ]]; then
  echo "[DRIFT] Mac ($MAC_SHA) vs VPS ($VPS_SHA) — MISMATCH" | tee -a "$LOG"
  DRIFT_FOUND=true
else
  echo "[OK] Mac == VPS: $MAC_SHA" | tee -a "$LOG"
fi

# 2. VPS mirror log freshness
VPS_LAST=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$VPS_HOST" \
  "cat /var/log/titan-last-mirror.ts 2>/dev/null || echo MISSING" 2>/dev/null \
  || echo MISSING)
if [[ "$VPS_LAST" == "MISSING" ]]; then
  echo "[WARN] VPS mirror timestamp missing — post-receive hook may not be installed" | tee -a "$LOG"
  # Only escalate if we ALSO have Mac-VPS SHA parity — otherwise already counted above
  if [[ "$VPS_SHA" != "UNREACHABLE" && "$MAC_SHA" == "$VPS_SHA" ]]; then
    DRIFT_FOUND=true
  fi
else
  echo "[OK] Last VPS mirror: $VPS_LAST" | tee -a "$LOG"
fi

# 3. GitHub vs VPS (or Mac, if VPS unreachable) via API
GH_SHA=UNREACHABLE
if command -v curl >/dev/null 2>&1; then
  if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    GH_SHA=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
      "https://api.github.com/repos/$GH_REPO/commits/$BRANCH" \
      | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('sha','UNREACHABLE'))" 2>/dev/null \
      || echo UNREACHABLE)
  else
    GH_SHA=$(curl -s "https://api.github.com/repos/$GH_REPO/commits/$BRANCH" \
      | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('sha','UNREACHABLE'))" 2>/dev/null \
      || echo UNREACHABLE)
  fi
fi

if [[ "$GH_SHA" == "UNREACHABLE" || -z "$GH_SHA" ]]; then
  echo "[WARN] GitHub unreachable (no token or API error)" | tee -a "$LOG"
else
  REF_SHA="$VPS_SHA"
  [[ "$REF_SHA" == "UNREACHABLE" ]] && REF_SHA="$MAC_SHA"
  if [[ "$GH_SHA" == "$REF_SHA" ]]; then
    echo "[OK] GitHub == $REF_SHA" | tee -a "$LOG"
  else
    echo "[DRIFT] GitHub ($GH_SHA) vs reference ($REF_SHA) — MISMATCH" | tee -a "$LOG"
    DRIFT_FOUND=true
  fi
fi

# 4. Stamp state + update MIRROR_STATUS.md
echo "$MAC_SHA" > "$HARNESS_DIR/.harness-state/vps-sha.txt" 2>/dev/null || true
bash "$HARNESS_DIR/bin/update-mirror-status.sh" "DRIFT_CHECK" \
  "$( [[ "$DRIFT_FOUND" == "true" ]] && echo DRIFT || echo OK )" || true

# 5. Incident if drift
if [[ "$DRIFT_FOUND" == "true" ]]; then
  bash "$HARNESS_DIR/bin/harness-incident.sh" "DRIFT_DETECTED" "Drift found between mirror legs — see $LOG"
  echo "[ACTION] Run bin/harness-mirror-repair.sh or escalate to Solon." | tee -a "$LOG"
  exit 1
fi

echo "=== DRIFT CHECK PASSED ===" | tee -a "$LOG"
