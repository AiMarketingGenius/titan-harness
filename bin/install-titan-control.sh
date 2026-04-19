#!/bin/bash
# install-titan-control.sh — TitanControl Unified Restart Handler v1.0 installer
# Idempotent. Run from harness root.
#
# Steps:
#   1. rsync TitanControl/ scripts to ~/Library/Application Support/TitanControl/
#   2. rsync titan.lua to ~/.hammerspoon/ + ensure require("titan") in init.lua
#   3. Generate HMAC secret at ~/.config/titan-control.secret (if missing)
#   4. Install LaunchAgents from launchd/ to ~/Library/LaunchAgents/
#   5. Bootstrap + kickstart LaunchAgents via launchctl
#
# Does NOT touch ~/.claude/settings.json — that's done by install-titan-control-hydration.sh
# during CT-0419-07 + a settings.json patch during this install.

set -eu

HARNESS="${HARNESS:-/Users/solonzafiropoulos1/titan-harness}"
TC_SRC="$HARNESS/TitanControl"
TC_DIR="$HOME/Library/Application Support/TitanControl"
STATE_DIR="$TC_DIR/state"
LOG_DIR="$TC_DIR/logs"
HAMMERSPOON_DIR="$HOME/.hammerspoon"
LA_DIR="$HOME/Library/LaunchAgents"

[ -d "$TC_SRC" ] || { echo "ERR: $TC_SRC missing" >&2; exit 1; }

# ---- 1. Install TitanControl scripts ----
echo "[1] installing TitanControl scripts..."
mkdir -p "$TC_DIR" "$STATE_DIR" "$LOG_DIR"
FILES=(
  request_restart.sh
  run_titan_session.sh
  sessionstart_mark_ready.sh
  stop_hook_restart_gate.sh
  stopfailure_hook_restart.sh
  watch_claude_debug.sh
  boot_prompt.txt
  # CT-0419-07 hydration files (coexist)
  sessionstart_hydrate_mcp.sh
  sessionstart_hydrate_gate.sh
  stop_hook_drift_snapshot.sh
  boot_verification_prompt.txt
)
for f in "${FILES[@]}"; do
  src="$TC_SRC/$f"
  dst="$TC_DIR/$f"
  [ -f "$src" ] || { echo "  WARN: $src missing — skipping"; continue; }
  cp -f "$src" "$dst"
  case "$f" in
    *.sh) chmod 755 "$dst" ;;
    *) chmod 644 "$dst" ;;
  esac
done
echo "  installed to $TC_DIR"

# ---- 2. Hammerspoon module ----
echo "[2] installing Hammerspoon titan.lua..."
mkdir -p "$HAMMERSPOON_DIR"
cp -f "$TC_SRC/titan.lua" "$HAMMERSPOON_DIR/titan.lua"
chmod 644 "$HAMMERSPOON_DIR/titan.lua"

INIT_LUA="$HAMMERSPOON_DIR/init.lua"
if [ -f "$INIT_LUA" ]; then
  if ! grep -q '^require("titan")' "$INIT_LUA" && ! grep -q "^require('titan')" "$INIT_LUA"; then
    echo '' >> "$INIT_LUA"
    echo '-- TitanControl Unified Restart Handler v1.0 HTTP ingress' >> "$INIT_LUA"
    echo 'require("titan")' >> "$INIT_LUA"
    echo "  appended require(\"titan\") to init.lua"
  else
    echo "  require(\"titan\") already in init.lua"
  fi
else
  echo '-- TitanControl minimal init' > "$INIT_LUA"
  echo 'require("titan")' >> "$INIT_LUA"
  echo "  created new init.lua"
fi

# Reload Hammerspoon if running
if pgrep -x Hammerspoon >/dev/null 2>&1; then
  /usr/bin/osascript -e 'tell application "Hammerspoon" to execute lua code "hs.reload()"' >/dev/null 2>&1 || true
  echo "  reloaded Hammerspoon config"
fi

# ---- 3. HMAC secret ----
echo "[3] HMAC secret at ~/.config/titan-control.secret..."
mkdir -p "$HOME/.config"
SECRET_FILE="$HOME/.config/titan-control.secret"
if [ ! -s "$SECRET_FILE" ]; then
  openssl rand -base64 48 | tr -d '\n' > "$SECRET_FILE"
  chmod 600 "$SECRET_FILE"
  echo "  generated ($(wc -c <"$SECRET_FILE") bytes)"
else
  echo "  already exists ($(wc -c <"$SECRET_FILE") bytes, untouched)"
fi

# ---- 4. LaunchAgents ----
echo "[4] LaunchAgents..."
mkdir -p "$LA_DIR"
for plist in io.aimg.hammerspoon.plist io.aimg.titan-logwatch.plist; do
  src="$HARNESS/launchd/$plist"
  dst="$LA_DIR/$plist"
  [ -f "$src" ] || { echo "  WARN: $src missing — skipping"; continue; }
  # Substitute __HOME__ with actual path (launchd doesn't expand ~)
  sed "s|__HOME__|$HOME|g" "$src" > "$dst"
  chmod 644 "$dst"
  echo "  $plist installed"
done

# ---- 5. Bootstrap LaunchAgents ----
echo "[5] bootstrapping LaunchAgents..."
UID_GUI="gui/$(id -u)"
for label in io.aimg.hammerspoon io.aimg.titan-logwatch; do
  # Unload if exists (idempotent)
  launchctl bootout "$UID_GUI/$label" 2>/dev/null || true
  launchctl bootstrap "$UID_GUI" "$LA_DIR/${label}.plist" 2>&1 | grep -v 'already loaded' || true
  launchctl enable "$UID_GUI/$label" 2>/dev/null || true
  launchctl kickstart -k "$UID_GUI/$label" 2>/dev/null || true
done
echo "  loaded"

launchctl list | grep -i 'io\.aimg' || echo "  WARN: no io.aimg agents visible in list"

echo ""
echo "DONE. TitanControl Unified Restart Handler v1.0 installed."
echo ""
echo "Next: ~/.claude/settings.json needs Stop + StopFailure + SessionStart hook chain updates."
echo "Run: bash bin/install-titan-control-settings.sh"
