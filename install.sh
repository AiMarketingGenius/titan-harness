#!/bin/bash
# titan-harness install.sh — idempotent installer for any Claude Code instance
# Usage: bash install.sh [--instance NAME]
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse --instance flag
TITAN_INSTANCE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --instance) TITAN_INSTANCE="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# OS detection
case "$(uname -s)" in
  Darwin*) OS=macos ;;
  Linux*)  OS=linux ;;
  *) echo "Unsupported OS: $(uname -s)"; exit 1 ;;
esac

# Session dir
if [ "$OS" = "linux" ] && [ "$EUID" -eq 0 ]; then
  SESSION_DIR=/opt/titan-session
else
  SESSION_DIR="$HOME/titan-session"
fi
mkdir -p "$SESSION_DIR"

# Claude settings.json location
CLAUDE_DIR="$HOME/.claude"
mkdir -p "$CLAUDE_DIR"
SETTINGS="$CLAUDE_DIR/settings.json"

echo "===== titan-harness install ====="
echo "OS: $OS"
echo "Repo: $REPO_DIR"
echo "Session dir: $SESSION_DIR"
echo "Settings: $SETTINGS"
echo "Instance: ${TITAN_INSTANCE:-(auto from hostname)}"

# Backup existing settings
if [ -f "$SETTINGS" ]; then
  cp "$SETTINGS" "${SETTINGS}.bak.$(date +%s)"
fi

# Persist instance name via ~/.titan-env
if [ -n "$TITAN_INSTANCE" ]; then
  mkdir -p "$HOME"
  if ! grep -q "^TITAN_INSTANCE=" "$HOME/.titan-env" 2>/dev/null; then
    echo "TITAN_INSTANCE=$TITAN_INSTANCE" >> "$HOME/.titan-env"
  else
    sed -i.bak "s|^TITAN_INSTANCE=.*|TITAN_INSTANCE=$TITAN_INSTANCE|" "$HOME/.titan-env"
  fi
fi

# Merge hooks into settings.json
python3 << PY
import json, os
settings_path = "$SETTINGS"
repo = "$REPO_DIR"

hooks = {
  "SessionStart": [{"hooks": [{"type": "command", "command": f"{repo}/hooks/session-start.sh"}]}],
  "PreToolUse":   [{"hooks": [{"type": "command", "command": f"{repo}/hooks/pre-tool-gate.sh"}]}],
  "PostToolUse":  [{"hooks": [{"type": "command", "command": f"{repo}/hooks/post-tool-log.sh"}]}],
  "SessionEnd":   [{"hooks": [{"type": "command", "command": f"{repo}/hooks/session-end.sh"}]}],
}

data = {}
if os.path.exists(settings_path):
  try:
    with open(settings_path) as f:
      data = json.load(f)
  except: data = {}

data["hooks"] = hooks
with open(settings_path, "w") as f:
  json.dump(data, f, indent=2)
print(f"Installed 4 hooks into {settings_path}")
PY

# Initialize cache files
touch "$SESSION_DIR/audit.log"
[ ! -f "$SESSION_DIR/HANDOVER.md" ] && cat > "$SESSION_DIR/HANDOVER.md" << HDR
# Titan Session Handover Log (local cache)
Source of truth: Supabase session_handover table.
HDR

echo "OK — titan-harness installed on $OS instance '${TITAN_INSTANCE:-$(hostname -s)}'"
echo ""
echo "To test: open a new Claude Code session and verify SessionStart runs."
