#!/usr/bin/env bash
# bin/update-mirror-status.sh
# Ironclad architecture §2.9 — regenerate MIRROR_STATUS.md after every event.
# Usage: update-mirror-status.sh <EVENT> <STATUS>
set -euo pipefail

HARNESS_DIR="${TITAN_HARNESS_DIR:-$HOME/titan-harness}"
EVENT="${1:-MANUAL}"
STATUS="${2:-OK}"
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

cd "$HARNESS_DIR"

MAC_SHA=$(git rev-parse --short HEAD)
BRANCH=$(git rev-parse --abbrev-ref HEAD)

STATE_DIR="$HARNESS_DIR/.harness-state"
mkdir -p "$STATE_DIR"

# Best-effort reads
VPS_TS=$(cat "$STATE_DIR/vps-last-sync.ts" 2>/dev/null || echo unknown)
VPS_SHA=$(cat "$STATE_DIR/vps-sha.txt" 2>/dev/null || echo unknown)
VPS_STATUS=$(cat "$STATE_DIR/vps-status.txt" 2>/dev/null || echo unknown)
GH_TS=$(cat "$STATE_DIR/gh-last-sync.ts" 2>/dev/null || echo unknown)
GH_SHA=$(cat "$STATE_DIR/gh-sha.txt" 2>/dev/null || echo unknown)
GH_STATUS=$(cat "$STATE_DIR/gh-status.txt" 2>/dev/null || echo unknown)
MCP_TS=$(cat "$STATE_DIR/mcp-last-sync.ts" 2>/dev/null || echo unknown)
MCP_STATUS=$(cat "$STATE_DIR/mcp-status.txt" 2>/dev/null || echo unknown)

# Stamp the leg this event touched
case "$EVENT" in
  MAC_PUSH|POST_COMMIT|TRIGGER_MIRROR)
    echo "$TS" > "$STATE_DIR/vps-last-sync.ts"
    echo "$MAC_SHA" > "$STATE_DIR/vps-sha.txt"
    echo "$STATUS" > "$STATE_DIR/vps-status.txt"
    VPS_TS="$TS"; VPS_SHA="$MAC_SHA"; VPS_STATUS="$STATUS"
    ;;
  GH_PUSH)
    echo "$TS" > "$STATE_DIR/gh-last-sync.ts"
    echo "$MAC_SHA" > "$STATE_DIR/gh-sha.txt"
    echo "$STATUS" > "$STATE_DIR/gh-status.txt"
    GH_TS="$TS"; GH_SHA="$MAC_SHA"; GH_STATUS="$STATUS"
    ;;
  MCP_EXPORT)
    echo "$TS" > "$STATE_DIR/mcp-last-sync.ts"
    echo "$STATUS" > "$STATE_DIR/mcp-status.txt"
    MCP_TS="$TS"; MCP_STATUS="$STATUS"
    ;;
esac

INCIDENTS_BLOCK=$(python3 -c "
import json, os
f = '$STATE_DIR/open-incidents.json'
if not os.path.exists(f):
    print('None')
else:
    try:
        data = json.load(open(f))
    except Exception:
        print('None'); raise SystemExit
    if not data:
        print('None')
    else:
        for x in data:
            print(f\"- [{x.get('type','?')}] {x.get('message','?')} ({x.get('ts','?')}, id={x.get('id','?')})\")
" 2>/dev/null || echo None)

LOG_TAIL=$(tail -5 "$HARNESS_DIR/logs/mirror-$(date +%Y%m%d).log" 2>/dev/null || echo "No log today")

cat > "$HARNESS_DIR/MIRROR_STATUS.md" <<EOF
# MIRROR_STATUS

> Last updated: $TS
> Last event: $EVENT → $STATUS
> Branch: $BRANCH

## Leg Status

| Leg | Last check | SHA | Status |
|---|---|---|---|
| Mac working tree | $TS | $MAC_SHA | $STATUS |
| VPS bare (origin) | $VPS_TS | $VPS_SHA | $VPS_STATUS |
| GitHub (AiMarketingGenius/titan-harness) | $GH_TS | $GH_SHA | $GH_STATUS |
| MCP export | $MCP_TS | — | $MCP_STATUS |

## Open incidents

$INCIDENTS_BLOCK

## Last 5 mirror events

\`\`\`
$LOG_TAIL
\`\`\`
EOF

echo "[MIRROR-STATUS] Wrote MIRROR_STATUS.md ($EVENT → $STATUS)"
