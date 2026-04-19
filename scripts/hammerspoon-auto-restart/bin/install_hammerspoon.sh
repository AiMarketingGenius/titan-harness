#!/bin/bash
# scripts/hammerspoon-auto-restart/bin/install_hammerspoon.sh
#
# Idempotent installer for the Titan auto-restart Hammerspoon module.
# Copies titan_auto_restart.lua to ~/.hammerspoon/ + appends the loader
# block to ~/.hammerspoon/init.lua if not already present + reloads.

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_LUA="$ROOT/hammerspoon-auto-restart/titan_auto_restart.lua"
# Support being called from scripts/hammerspoon-auto-restart/bin/ or its parent
if [ ! -f "$SRC_LUA" ]; then
  SRC_LUA="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/titan_auto_restart.lua"
fi
if [ ! -f "$SRC_LUA" ]; then
  echo "FAIL: titan_auto_restart.lua not found at $SRC_LUA"
  exit 2
fi

HS_DIR="$HOME/.hammerspoon"
INIT="$HS_DIR/init.lua"
mkdir -p "$HS_DIR"

# Copy module.
cp "$SRC_LUA" "$HS_DIR/titan_auto_restart.lua"
echo "installed: $HS_DIR/titan_auto_restart.lua"

# Append loader block to init.lua if missing.
MARKER="-- titan_auto_restart module loader (CT-0418-08)"
if [ -f "$INIT" ] && grep -qF "$MARKER" "$INIT"; then
  echo "init.lua loader already present — skipping append"
else
  cat >> "$INIT" <<LUA

$MARKER
local ok3, titan_auto = pcall(require, "titan_auto_restart")
if ok3 and titan_auto and titan_auto.start then
  titan_auto.start()
  hs.alert.show("Titan auto-restart armed")
else
  hs.alert.show("Titan auto-restart load failed: " .. tostring(titan_auto))
end
LUA
  echo "appended loader block to $INIT"
fi

# Reload Hammerspoon.
if command -v hs >/dev/null 2>&1; then
  hs -c 'hs.reload()' >/dev/null 2>&1 || true
  echo "hs reload requested via CLI"
else
  if command -v open >/dev/null 2>&1; then
    open "hammerspoon://reload" >/dev/null 2>&1 || true
    echo "hs reload requested via URL scheme"
  fi
fi

echo "install complete — auto-restart armed on next Hammerspoon load"
