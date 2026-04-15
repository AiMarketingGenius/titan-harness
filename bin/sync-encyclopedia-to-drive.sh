#!/usr/bin/env bash
# bin/sync-encyclopedia-to-drive.sh
# CT-0414-07-adjacent — keeps Google Drive copy of plans/DOCTRINE_AMG_ENCYCLOPEDIA.md in sync
# so EOM (Claude.ai project) can read the latest via Drive MCP.
#
# Two paths:
#   1. Mac (preferred): uses Titan's Drive MCP via a one-line `claude` invocation OR
#      rclone if user has it configured.
#   2. VPS: runs nightly via cron, uploads via gcloud storage cp OR rclone.
#
# Triggered automatically by post-commit hook on harness commits that touch
# plans/DOCTRINE_AMG_ENCYCLOPEDIA.md.
#
# Usage:
#   bin/sync-encyclopedia-to-drive.sh           # one-shot push to Drive
#   bin/sync-encyclopedia-to-drive.sh --check   # dry-run, prints what would happen

set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/plans/DOCTRINE_AMG_ENCYCLOPEDIA.md"
DRIVE_FILE_ID_FILE="$REPO/.harness-state/encyc_drive_file_id"

[[ -f "$SRC" ]] || { echo "encyclopedia missing: $SRC" >&2; exit 2; }

if [[ "${1:-}" == "--check" ]]; then
    echo "src: $SRC ($(wc -l < "$SRC") lines, $(wc -c < "$SRC") bytes)"
    echo "drive_file_id: $(cat "$DRIVE_FILE_ID_FILE" 2>/dev/null || echo 'not yet recorded')"
    echo "would: rclone copy or Drive API PUT"
    exit 0
fi

# Path 1: rclone if available (preferred for cron + post-commit hook)
if command -v rclone >/dev/null 2>&1 && rclone listremotes 2>/dev/null | grep -qE "^(gdrive|drive):"; then
    REMOTE=$(rclone listremotes 2>/dev/null | grep -E "^(gdrive|drive):" | head -1)
    rclone copy "$SRC" "${REMOTE}AMG-Encyclopedia/" 2>&1 | head -5
    echo "[encyc-sync] rclone push complete to $REMOTE"
    exit 0
fi

# Path 2: gcloud (some users have it)
if command -v gcloud >/dev/null 2>&1; then
    echo "[encyc-sync] gcloud path not yet implemented — install rclone OR use Titan inline 'sync encyclopedia' command"
    exit 1
fi

# Path 3: instruct Titan to do it via Drive MCP next session
echo "[encyc-sync] no rclone or gcloud available locally."
echo "[encyc-sync] flagging for next Titan session: ask Titan 'sync encyclopedia to drive'."
echo "[encyc-sync] OR install rclone: brew install rclone && rclone config (add gdrive remote)"
exit 0
