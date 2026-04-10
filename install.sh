#!/bin/bash
# titan-harness install.sh — idempotent installer for any Claude Code instance
# Usage:
#   bash install.sh [--instance NAME] [--test]
#     --instance NAME  override hostname-derived instance tag
#     --test           run post-install verification (mock idea capture + DB check)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse flags
TITAN_INSTANCE_OVERRIDE=""
RUN_TEST=0
while [ $# -gt 0 ]; do
  case "$1" in
    --instance) TITAN_INSTANCE_OVERRIDE="$2"; shift 2 ;;
    --test)     RUN_TEST=1; shift ;;
    -h|--help)
      echo "Usage: bash install.sh [--instance NAME] [--test]"
      exit 0 ;;
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
if [ "$OS" = "linux" ] && [ "${EUID:-$(id -u)}" -eq 0 ]; then
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
echo "OS:           $OS"
echo "Repo:         $REPO_DIR"
echo "Session dir:  $SESSION_DIR"
echo "Settings:     $SETTINGS"
echo "Instance:     ${TITAN_INSTANCE_OVERRIDE:-(auto from hostname)}"
echo "Test mode:    $([ "$RUN_TEST" -eq 1 ] && echo yes || echo no)"
echo ""

# Backup existing settings
if [ -f "$SETTINGS" ]; then
  cp "$SETTINGS" "${SETTINGS}.bak.$(date +%s)"
fi

# Persist instance name via ~/.titan-env
if [ -n "$TITAN_INSTANCE_OVERRIDE" ]; then
  if ! grep -q "^TITAN_INSTANCE=" "$HOME/.titan-env" 2>/dev/null; then
    echo "TITAN_INSTANCE=$TITAN_INSTANCE_OVERRIDE" >> "$HOME/.titan-env"
  else
    sed -i.bak "s|^TITAN_INSTANCE=.*|TITAN_INSTANCE=$TITAN_INSTANCE_OVERRIDE|" "$HOME/.titan-env"
  fi
fi

# Merge hooks into settings.json (includes new UserPromptSubmit idea hook)
python3 << PY
import json, os
settings_path = "$SETTINGS"
repo = "$REPO_DIR"

hooks = {
  "SessionStart":      [{"hooks": [{"type": "command", "command": f"{repo}/hooks/session-start.sh",     "timeout": 10}]}],
  "PreToolUse":        [{"hooks": [{"type": "command", "command": f"{repo}/hooks/pre-tool-gate.sh",     "timeout": 5}]}],
  "PostToolUse":       [{"hooks": [{"type": "command", "command": f"{repo}/hooks/post-tool-log.sh",     "timeout": 5}]}],
  "UserPromptSubmit":  [{"hooks": [{"type": "command", "command": f"{repo}/hooks/user-prompt-idea.sh",  "timeout": 5}]}],
  "SessionEnd":        [{"hooks": [{"type": "command", "command": f"{repo}/hooks/session-end.sh",       "timeout": 10}]}],
}

data = {}
if os.path.exists(settings_path):
  try:
    with open(settings_path) as f:
      data = json.load(f)
  except Exception:
    data = {}

data["hooks"] = hooks
with open(settings_path, "w") as f:
  json.dump(data, f, indent=2)
print(f"Installed 5 hooks into {settings_path}")
PY

# Initialize cache files
touch "$SESSION_DIR/audit.log"
touch "$SESSION_DIR/ideas-queue.jsonl"
touch "$SESSION_DIR/ideas-drain.log"

[ ! -f "$SESSION_DIR/HANDOVER.md" ] && cat > "$SESSION_DIR/HANDOVER.md" << HDR
# Titan Session Handover Log (local cache)
Source of truth: Supabase session_handover table.
HDR

# Install the drainer (OS-specific)
echo ""
echo "--- Installing idea drainer ---"
case "$OS" in
  macos)
    PLIST_SRC="$REPO_DIR/services/com.titan.ideas.drain.plist"
    PLIST_DST="$HOME/Library/LaunchAgents/com.titan.ideas.drain.plist"
    mkdir -p "$HOME/Library/LaunchAgents"
    # Substitute placeholders
    sed -e "s|__HARNESS_PATH__|$REPO_DIR|g" \
        -e "s|__SESSION_DIR__|$SESSION_DIR|g" \
        "$PLIST_SRC" > "$PLIST_DST"
    # Unload if already loaded (idempotent)
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    launchctl load "$PLIST_DST"
    echo "launchd agent loaded: com.titan.ideas.drain (runs every 60s)"
    ;;
  linux)
    if [ "${EUID:-$(id -u)}" -eq 0 ]; then
      cp "$REPO_DIR/services/titan-ideas-drain.service" /etc/systemd/system/
      cp "$REPO_DIR/services/titan-ideas-drain.timer"   /etc/systemd/system/
      systemctl daemon-reload
      systemctl enable --now titan-ideas-drain.timer
      echo "systemd timer enabled: titan-ideas-drain.timer (runs every 60s)"
    else
      echo "WARN: not running as root — skipping systemd service install"
      echo "  To install manually: sudo cp services/titan-ideas-drain.{service,timer} /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now titan-ideas-drain.timer"
    fi
    ;;
esac

echo ""
echo "OK — titan-harness installed on $OS instance '${TITAN_INSTANCE_OVERRIDE:-$(hostname -s 2>/dev/null || hostname)}'"
echo ""
echo "Active hooks:"
echo "  1. SessionStart    → session-start.sh"
echo "  2. PreToolUse      → pre-tool-gate.sh (blocks Write/Edit without ACTIVE_TASK_ID)"
echo "  3. PostToolUse     → post-tool-log.sh"
echo "  4. UserPromptSubmit → user-prompt-idea.sh (NEW: 'lock it' / 🔒 trigger)"
echo "  5. SessionEnd      → session-end.sh"
echo ""

# --- Test mode ---
if [ "$RUN_TEST" -eq 1 ]; then
  echo "==================================================="
  echo "Running install verification (--test)"
  echo "==================================================="

  # Load env
  # shellcheck source=/dev/null
  [ -f "$HOME/.titan-env" ] && . "$HOME/.titan-env"
  [ -f "/opt/amg-titan/.env" ] && . "/opt/amg-titan/.env"

  if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
    echo "✗ SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing — cannot run test"
    exit 1
  fi

  # Generate a unique idea text so we can find it after
  TEST_MARKER="INSTALL_TEST_$(date +%s)_$$"
  TEST_PROMPT="install verification: lock it: $TEST_MARKER"

  echo ""
  echo "Step 1: Fire mock prompt through user-prompt-idea.sh"
  MOCK_INPUT=$(python3 -c "
import json, sys
sys.stdout.write(json.dumps({
  'hook_event_name': 'UserPromptSubmit',
  'session_id': 'install-test-$(date +%s)',
  'prompt': '$TEST_PROMPT',
  'cwd': '$PWD',
}))
")
  printf '%s' "$MOCK_INPUT" | "$REPO_DIR/hooks/user-prompt-idea.sh" || {
    echo "✗ hook returned non-zero exit"
    exit 1
  }

  # Verify queue line appeared
  if grep -q "$TEST_MARKER" "$SESSION_DIR/ideas-queue.jsonl" 2>/dev/null; then
    echo "  ✓ queue line written"
  else
    echo "  ✗ queue line NOT found in $SESSION_DIR/ideas-queue.jsonl"
    exit 1
  fi

  echo ""
  echo "Step 2: Run drainer to push queue to Supabase"
  "$REPO_DIR/bin/idea-drain.sh" || {
    echo "✗ drainer returned non-zero"
    exit 1
  }
  sleep 1

  echo ""
  echo "Step 3: Query Supabase for the test row"
  ROW_CHECK=$(curl -sS -m 6 \
    -G "$SUPABASE_URL/rest/v1/ideas" \
    --data-urlencode "select=id,idea_title,status,instance_id" \
    --data-urlencode "idea_title=like.*${TEST_MARKER}*" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY")

  TEST_ID=$(printf '%s' "$ROW_CHECK" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    if isinstance(d, list) and len(d) > 0:
        print(d[0].get('id',''), end='')
except Exception:
    pass
")

  if [ -n "$TEST_ID" ]; then
    echo "  ✓ Supabase row created: id=$TEST_ID"
  else
    echo "  ✗ Test row NOT found in Supabase"
    echo "  Response: $ROW_CHECK"
    exit 1
  fi

  echo ""
  echo "Step 4: Clean up test row"
  CLEANUP=$(curl -sS -w "%{http_code}" -m 6 -o /dev/null \
    -X DELETE "$SUPABASE_URL/rest/v1/ideas?id=eq.$TEST_ID" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY")
  if [ "$CLEANUP" = "204" ] || [ "$CLEANUP" = "200" ]; then
    echo "  ✓ test row deleted (HTTP $CLEANUP)"
  else
    echo "  ⚠ cleanup returned HTTP $CLEANUP — manually delete id=$TEST_ID"
  fi

  echo ""
  echo "==================================================="
  echo "✓ ALL TESTS PASSED — idea capture pipeline verified"
  echo "==================================================="
  echo ""
  echo "To use: in any Claude Code session, end your message with:"
  echo "   lock it: <your idea text>"
  echo "   🔒 <your idea text>"
fi

echo ""
echo "Done."
