#!/bin/bash
# install-titan-control-hydration.sh — CT-0419-07 installer
#
# Idempotent. Installs the hydration scripts from the harness repo to
# ~/Library/Application Support/TitanControl/ and preps state/ dir.
#
# Does NOT touch status.json / ready.json / context-ready / request_restart.sh —
# those belong to the TitanControl Unified Restart Handler (separate ship).

set -eu

HARNESS="${HARNESS:-/Users/solonzafiropoulos1/titan-harness}"
SRC_DIR="$HARNESS/TitanControl"
TC_DIR="$HOME/Library/Application Support/TitanControl"
STATE_DIR="$TC_DIR/state"

[ -d "$SRC_DIR" ] || { echo "ERR: harness source $SRC_DIR not found" >&2; exit 1; }

mkdir -p "$TC_DIR" "$STATE_DIR"

FILES=(
  sessionstart_hydrate_mcp.sh
  sessionstart_hydrate_gate.sh
  stop_hook_drift_snapshot.sh
  boot_verification_prompt.txt
)

for f in "${FILES[@]}"; do
  src="$SRC_DIR/$f"
  dst="$TC_DIR/$f"
  if [ ! -f "$src" ]; then
    echo "ERR: source $src missing" >&2; exit 1
  fi
  cp -f "$src" "$dst"
  case "$f" in
    *.sh) chmod 755 "$dst" ;;
    *) chmod 644 "$dst" ;;
  esac
done

echo "Installed CT-0419-07 hydration scripts to $TC_DIR"
echo "State dir: $STATE_DIR"
ls -la "$TC_DIR"
