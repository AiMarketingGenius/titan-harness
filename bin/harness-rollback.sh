#!/usr/bin/env bash
# bin/harness-rollback.sh
# Ironclad architecture §5.2 — reset to a freeze tag or SHA, propagate to
# all mirror legs, log as an incident so the next session sees it.
# Usage: harness-rollback.sh <tag-or-sha>
set -euo pipefail

HARNESS_DIR="${TITAN_HARNESS_DIR:-$HOME/titan-harness}"
TARGET="${1:-}"
BRANCH="$(git -C "$HARNESS_DIR" rev-parse --abbrev-ref HEAD)"

if [[ -z "$TARGET" ]]; then
  echo "usage: harness-rollback.sh <tag-or-sha>" >&2
  exit 2
fi

echo "[ROLLBACK] Branch: $BRANCH"
echo "[ROLLBACK] Current HEAD: $(git -C "$HARNESS_DIR" rev-parse HEAD)"
echo "[ROLLBACK] Target: $TARGET"

# 1. Freeze current state before rollback.
bash "$HARNESS_DIR/bin/harness-freeze.sh"

# 2. Reset to target.
git -C "$HARNESS_DIR" reset --hard "$TARGET"
echo "[ROLLBACK] Reset to $TARGET"

# 3. Propagate to all remotes.
if git -C "$HARNESS_DIR" push origin "$BRANCH" --force-with-lease; then
  echo "[ROLLBACK:MAC→VPS] OK"
else
  echo "[ROLLBACK:MAC→VPS] FAILED"
fi
if git -C "$HARNESS_DIR" remote | grep -qx github; then
  if git -C "$HARNESS_DIR" push github "$BRANCH" --force-with-lease; then
    echo "[ROLLBACK:MAC→GH] OK"
  else
    echo "[ROLLBACK:MAC→GH] FAILED"
  fi
fi

# 4. Log the rollback as a hard-stop incident. Solon must ack before new writes.
bash "$HARNESS_DIR/bin/harness-incident.sh" "ROLLBACK_EXECUTED" "Rolled back $BRANCH to $TARGET" "HIGH"

# 5. Write ESCALATE.md so any following session stops.
cat > "$HARNESS_DIR/ESCALATE.md" <<EOF
# ESCALATE — Action Required from Solon

> Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
> Incident: ROLLBACK_EXECUTED
> Severity: HIGH

## What Titan detected
Rolled back $BRANCH to $TARGET. The current HEAD is now $(git -C "$HARNESS_DIR" rev-parse --short HEAD).

## What is blocked
All new STRUCTURAL / PLAN writes until Solon acknowledges this rollback.

## Recommended fix
Review the rollback, confirm downstream systems (VPS working tree, GitHub, MCP) match, then run:

    bin/harness-ack-escalation.sh
EOF

echo "[ROLLBACK] ESCALATE.md written. Run bin/harness-ack-escalation.sh to unblock."
