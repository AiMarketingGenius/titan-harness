#!/usr/bin/env bash
# bin/install-titan-autorestart.sh
# Installs ~/Library/LaunchAgents/com.amg.titan-autorestart.plist.
# Replaces __HOME__ and __TITAN_HARNESS__ placeholders with real paths,
# loads the plist. Idempotent.
#
# Usage:
#   bin/install-titan-autorestart.sh                  # install + load
#   bin/install-titan-autorestart.sh --uninstall      # unload + remove
#   bin/install-titan-autorestart.sh --reload         # bounce (unload+load)

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/launchd/com.amg.titan-autorestart.plist"
DST="$HOME/Library/LaunchAgents/com.amg.titan-autorestart.plist"
LABEL="com.amg.titan-autorestart"

ACTION="install"
for a in "$@"; do
    case "$a" in
        --uninstall) ACTION="uninstall" ;;
        --reload)    ACTION="reload" ;;
        *) echo "unknown arg: $a" >&2; exit 2 ;;
    esac
done

unload_if_loaded() {
    if launchctl list 2>/dev/null | awk '{print $3}' | grep -qx "$LABEL"; then
        launchctl unload "$DST" 2>/dev/null || true
        echo "[install-autorestart] unloaded $LABEL"
    fi
}

case "$ACTION" in
    uninstall)
        unload_if_loaded
        rm -f "$DST"
        echo "[install-autorestart] removed $DST"
        ;;

    install|reload)
        mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.claude"
        [[ -f "$SRC" ]] || { echo "source plist missing: $SRC" >&2; exit 3; }

        sed -e "s|__HOME__|$HOME|g" -e "s|__TITAN_HARNESS__|$REPO|g" "$SRC" > "$DST"
        chmod 0644 "$DST"
        echo "[install-autorestart] wrote $DST"

        # Register UserPromptSubmit hook (user-prompt-counter.sh) in ~/.claude/settings.json.
        # Merges additively; preserves any existing entries.
        SETTINGS="$HOME/.claude/settings.json"
        HOOK_CMD="${REPO}/hooks/user-prompt-counter.sh"
        python3 - "$SETTINGS" "$HOOK_CMD" <<'PY'
import json, os, sys
path, cmd = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(path):
    try: data = json.load(open(path))
    except Exception: data = {}
hooks = data.setdefault("UserPromptSubmit", [])
# Check if our command is already registered
already = False
for group in hooks:
    for h in group.get("hooks", []):
        if h.get("command") == cmd: already = True
if not already:
    hooks.append({"hooks": [{"type": "command", "command": cmd, "timeout": 5}]})
    backup = path + ".bak-" + __import__('time').strftime('%Y%m%d-%H%M%S')
    if os.path.exists(path):
        import shutil; shutil.copy(path, backup)
    json.dump(data, open(path, "w"), indent=2)
    print(f"[install-autorestart] registered UserPromptSubmit hook in {path} (backup: {backup if os.path.exists(path) else 'none'})")
else:
    print(f"[install-autorestart] UserPromptSubmit hook already registered")
PY

        unload_if_loaded
        launchctl load -w "$DST"
        echo "[install-autorestart] loaded $LABEL"

        # Sanity check
        launchctl list "$LABEL" 2>/dev/null | head -10 || true

        cat <<EOF

[install-autorestart] smoke test:
    touch ~/.claude/titan-restart.flag
    # wait 2s — should see a new Terminal/iTerm window launch 'claude'
    # check ~/.claude/titan-restart.log for launch evidence

[install-autorestart] to trigger manually from Titan:
    bin/titan-restart-capture.sh --now
EOF
        ;;
esac
