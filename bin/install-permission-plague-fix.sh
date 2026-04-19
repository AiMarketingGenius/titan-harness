#!/usr/bin/env bash
# bin/install-permission-plague-fix.sh — CT-0419-08 idempotent re-installer.
# Restores all four layers after a Claude Code update / fresh Mac setup.
#
# L1: settings.json allow + bypassPermissions (manual — see CLAUDE.md §20.1)
# L2: run_titan_session.sh flag (handled by bin/install-titan-control.sh)
# L3: Hammerspoon auto_approve module + launchd sidecar (this script)
# L4: CLAUDE.md §20 (already in repo)

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HS_DIR="$HOME/.hammerspoon"
LAUNCHAGENTS="$HOME/Library/LaunchAgents"
PLIST="$LAUNCHAGENTS/io.aimg.auto-approve-ingest.plist"
LABEL="io.aimg.auto-approve-ingest"

echo "[permission-plague-fix] installing L3 Hammerspoon module + sidecar…"
mkdir -p "$HS_DIR" "$LAUNCHAGENTS" "$HOME/titan-harness/logs/auto_approve_queue"
cp "$REPO/TitanControl/auto_approve_claude_prompts.lua" "$HS_DIR/auto_approve_claude_prompts.lua"
cp "$REPO/TitanControl/io.aimg.auto-approve-ingest.plist" "$PLIST"

# Ensure init.lua loads the module (idempotent)
INIT="$HS_DIR/init.lua"
if [ -f "$INIT" ] && ! grep -qF 'require, "auto_approve_claude_prompts"' "$INIT"; then
  cat >> "$INIT" <<'EOF'

-- auto_approve_claude_prompts module loader (CT-0419-08 Layer 3 + TCC Layer B)
local ok_auto, auto = pcall(require, "auto_approve_claude_prompts")
if ok_auto and auto and auto.start then
  auto.start()
  hs.alert.show("auto-approve armed")
else
  hs.alert.show("auto-approve load failed: " .. tostring(auto))
end
EOF
  echo "[permission-plague-fix] appended loader to $INIT"
fi

# Launchd bootstrap (idempotent — bootout if already running, then bootstrap)
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "[permission-plague-fix] launchd job $LABEL (re-)bootstrapped"

# Reload Hammerspoon
open hammerspoon://reload 2>/dev/null || true
echo "[permission-plague-fix] requested Hammerspoon reload"

echo "[permission-plague-fix] done."
echo ""
echo "Verify:"
echo "  1. ~/titan-harness/logs/auto_approve.log shows 'started poll=0.8s'"
echo "  2. launchctl print gui/\$(id -u)/$LABEL — state=running or xpcproxy"
echo "  3. After a trigger, MCP shows tag=auto-approve row in op_decisions"
