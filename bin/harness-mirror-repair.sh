#!/usr/bin/env bash
# bin/harness-mirror-repair.sh
# Ironclad architecture §2.8 — force mirror legs back into sync and clear
# DRIFT_DETECTED incidents. Re-runs drift check at the end.
set -euo pipefail

HARNESS_DIR="${TITAN_HARNESS_DIR:-$HOME/titan-harness}"
BRANCH="$(git -C "$HARNESS_DIR" rev-parse --abbrev-ref HEAD)"
VPS_HOST="${TITAN_VPS_HOST:-root@170.205.37.148}"

echo "[REPAIR] Starting mirror repair at $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Leg 1: Mac → VPS bare (force-with-lease, safer than --force)
if git -C "$HARNESS_DIR" push origin "$BRANCH" --force-with-lease; then
  echo "[REPAIR:LEG1] Mac→VPS OK"
else
  echo "[REPAIR:LEG1] FAILED"
fi

# Leg 2: Mac → GitHub (direct). Skip if no github remote.
if git -C "$HARNESS_DIR" remote | grep -qx github; then
  if git -C "$HARNESS_DIR" push github "$BRANCH" --force-with-lease; then
    echo "[REPAIR:LEG2] Mac→GH OK"
  else
    echo "[REPAIR:LEG2] FAILED"
  fi
fi

# Leg 3: VPS working tree checkout + MCP export (best effort via SSH).
ssh -o ConnectTimeout=5 -o BatchMode=yes "$VPS_HOST" bash -s <<'REMOTE' || echo "[REPAIR:LEG3] SSH failed"
set -e
WORK_TREE="/opt/titan-harness-work"
GIT_DIR="/opt/titan-harness.git"
MCP_EXPORT="/opt/mcp/titan-context"
BRANCH_REMOTE=$(git -C "$GIT_DIR" symbolic-ref --short HEAD 2>/dev/null || echo master)
if [ -d "$WORK_TREE" ]; then
  GIT_WORK_TREE="$WORK_TREE" GIT_DIR="$GIT_DIR" git checkout -f "$BRANCH_REMOTE" 2>/dev/null || true
  mkdir -p "$MCP_EXPORT"
  [ -d "$WORK_TREE/mcp" ] && rsync -a --delete "$WORK_TREE/mcp/" "$MCP_EXPORT/" 2>/dev/null || true
  for f in CLAUDE.md CORE_CONTRACT.md RADAR.md policy.yaml; do
    [ -f "$WORK_TREE/$f" ] && cp "$WORK_TREE/$f" "$MCP_EXPORT/$f"
  done
  date -u +%Y-%m-%dT%H:%M:%SZ > /var/log/titan-last-mirror.ts
  echo "[VPS:REPAIR] checkout + mcp export OK"
fi
REMOTE

# Clear DRIFT_DETECTED incidents.
python3 - <<PY
import json, os
f = os.path.expanduser('$HARNESS_DIR/.harness-state/open-incidents.json')
if os.path.exists(f):
    try:
        data = json.load(open(f))
        before = len(data)
        data = [x for x in data if x.get('type') != 'DRIFT_DETECTED']
        json.dump(data, open(f, 'w'), indent=2)
        print(f"[REPAIR] DRIFT_DETECTED incidents cleared ({before} -> {len(data)})")
    except Exception as e:
        print(f"[REPAIR] incident file error: {e}")
PY

echo "[REPAIR] Re-running drift check..."
bash "$HARNESS_DIR/bin/harness-drift-check.sh" || true
