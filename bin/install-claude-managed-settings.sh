#!/usr/bin/env bash
# bin/install-claude-managed-settings.sh
# CT-0415-05 Layer-4 fix v2.
#
# Installs config/claude-managed-settings.json to the system-level path
# /Library/Application Support/ClaudeCode/managed-settings.json on macOS.
# Requires sudo. This is the strongest policy tier — overrides user and
# project settings per Anthropic docs (code.claude.com/docs/en/permissions).
#
# After install, restart the Claude.app to pick up the new managed settings.
#
# Usage:
#   bin/install-claude-managed-settings.sh           # install (prompts sudo)
#   bin/install-claude-managed-settings.sh --dry-run # show what would happen
#   bin/install-claude-managed-settings.sh --uninstall  # remove the managed file

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/config/claude-managed-settings.json"
DST_DIR="/Library/Application Support/ClaudeCode"
DST="$DST_DIR/managed-settings.json"

case "${1:-install}" in
    --dry-run)
        echo "WOULD: sudo mkdir -p \"$DST_DIR\""
        echo "WOULD: sudo cp \"$SRC\" \"$DST\""
        echo "WOULD: sudo chown root:wheel \"$DST\""
        echo "WOULD: sudo chmod 0644 \"$DST\""
        echo "WOULD: restart Claude.app"
        echo
        echo "Source content:"; cat "$SRC"
        ;;
    --uninstall)
        sudo rm -f "$DST"
        echo "[managed-settings] removed $DST"
        ;;
    install)
        [[ -f "$SRC" ]] || { echo "source missing: $SRC" >&2; exit 2; }
        sudo mkdir -p "$DST_DIR"
        sudo cp "$SRC" "$DST"
        sudo chown root:wheel "$DST"
        sudo chmod 0644 "$DST"
        echo "[managed-settings] installed to $DST"
        ls -la "$DST"
        echo
        echo "[managed-settings] Restart Claude.app to pick up the new policy:"
        echo "    osascript -e 'tell application \"Claude\" to quit' && sleep 2 && open -a Claude"
        echo
        echo "[managed-settings] Verification: open Claude, run a Bash + Edit + Write tool — should not prompt."
        echo "If a tool DOES prompt, capture the exact prompt wording so we can add the missing scope."
        ;;
    *) echo "usage: $0 [install|--dry-run|--uninstall]" >&2; exit 2 ;;
esac
