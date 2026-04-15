#!/usr/bin/env bash
# bin/install-titan-nosleep-mac.sh
# CT-0415-05 Phase 3 — keep Mac awake on AC so SSH/Tailscale stays reachable.
#
# Two parts:
#   1. Idempotent caffeinate launchd agent (~/Library/LaunchAgents/io.titan.nosleep.plist).
#   2. pmset directives for power assertions (requires sudo). Solon runs the pmset
#      block once with the prompted sudo password.
#
# Usage:
#   bin/install-titan-nosleep-mac.sh           # install agent + print pmset commands
#   bin/install-titan-nosleep-mac.sh --apply-pmset    # also runs pmset (needs sudo)
#   bin/install-titan-nosleep-mac.sh --uninstall      # unload + remove

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/launchd/io.titan.nosleep.plist"
DST="$HOME/Library/LaunchAgents/io.titan.nosleep.plist"
LABEL="io.titan.nosleep"

case "${1:-install}" in
    --uninstall)
        launchctl list 2>/dev/null | awk '{print $3}' | grep -qx "$LABEL" && launchctl unload "$DST" 2>/dev/null || true
        rm -f "$DST"
        echo "[nosleep] removed $DST"
        exit 0
        ;;
    install|--apply-pmset)
        mkdir -p "$HOME/Library/LaunchAgents"
        sed -e "s|__HOME__|$HOME|g" "$SRC" > "$DST"
        chmod 0644 "$DST"
        # Bounce
        launchctl list 2>/dev/null | awk '{print $3}' | grep -qx "$LABEL" && launchctl unload "$DST" 2>/dev/null || true
        launchctl load -w "$DST"
        echo "[nosleep] loaded $LABEL — Mac will stay awake via caffeinate -s"

        if [[ "${1:-}" == "--apply-pmset" ]]; then
            echo "[nosleep] applying pmset (sudo will prompt)..."
            sudo pmset -c sleep 0 disksleep 0 displaysleep 0 womp 1
            sudo pmset -a womp 1
            echo "[nosleep] pmset applied"
        else
            cat <<EOF

[nosleep] To finish, run ONCE with sudo:
    sudo pmset -c sleep 0 disksleep 0 displaysleep 0 womp 1
    sudo pmset -a womp 1

  -c    on AC power: never sleep, never disk-sleep, never display-sleep,
        wake on magic packet
  -a    all power sources: wake on magic packet

These are the documented Solon-side prerequisites per CT-0415-05 task.
Display sleep can stay enabled — SSH still works with display off, the
key is that the SYSTEM doesn't sleep.
EOF
        fi
        ;;
    *)
        echo "usage: $0 [--apply-pmset|--uninstall]" >&2; exit 2 ;;
esac
