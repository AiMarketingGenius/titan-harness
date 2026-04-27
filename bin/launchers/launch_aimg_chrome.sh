#!/bin/bash
# AIMG D2 launcher (Chrome 147 reality).
#
# Google deprecated --load-extension in Chrome 137 (silently ignored in 147+).
# Workaround: launch dedicated Chrome profile with chrome://extensions tab open
# on first run; Solon drag-drops ~/AMG/aimg-extension once. Profile remembers
# the unpacked install across all future launches — only first run shows the
# install prompt.
set -euo pipefail

EXTENSION_DIR="$HOME/AMG/aimg-extension"
PROFILE_DIR="$HOME/.aimg-chrome-profile"
FIRST_RUN_MARKER="$PROFILE_DIR/.aimg-installed"
LOG="$HOME/.openclaw/logs/aimg_chrome.log"
mkdir -p "$(dirname "$LOG")" "$PROFILE_DIR"

if [ ! -f "$EXTENSION_DIR/manifest.json" ]; then
  osascript -e "display dialog \"AIMG extension not found at $EXTENSION_DIR. Install ~/Downloads/AI_Memory_Guard_v0.2.1 first.\" buttons {\"OK\"}"
  exit 1
fi

# Pre-seed developer_mode=true so chrome://extensions has the toggle on
mkdir -p "$PROFILE_DIR/Default"
PREFS="$PROFILE_DIR/Default/Preferences"
if [ -f "$PREFS" ]; then
  /opt/homebrew/bin/python3 -c "
import json
p = json.load(open('$PREFS'))
ext = p.setdefault('extensions', {}).setdefault('ui', {})
ext['developer_mode'] = True
json.dump(p, open('$PREFS', 'w'))
" 2>/dev/null || true
else
  echo '{"extensions":{"ui":{"developer_mode":true}}}' > "$PREFS"
fi

# Kill any prior Chrome on this profile (clean restart)
PRIOR=$(pgrep -f "user-data-dir=$PROFILE_DIR" 2>/dev/null || true)
if [ -n "$PRIOR" ]; then
  kill $PRIOR 2>/dev/null || true
  sleep 0.5
  PRIOR=$(pgrep -f "user-data-dir=$PROFILE_DIR" 2>/dev/null || true)
  [ -n "$PRIOR" ] && kill -9 $PRIOR 2>/dev/null || true
fi

echo "[$(date -Iseconds)] launching AIMG Chrome (first_run=$([ -f "$FIRST_RUN_MARKER" ] && echo no || echo yes))" >> "$LOG"

# First run: open claude.ai then add chrome://extensions as a 2nd tab via AppleScript.
# (Chrome 147 silently drops chrome:// URLs passed via command-line args.)
if [ ! -f "$FIRST_RUN_MARKER" ]; then
  echo "$EXTENSION_DIR" | pbcopy 2>/dev/null || true
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --user-data-dir="$PROFILE_DIR" \
    --no-first-run --no-default-browser-check \
    --window-size=1280,900 --window-position=120,80 \
    "https://claude.ai/" \
    >> "$LOG" 2>&1 &
  disown
  sleep 4
  osascript <<APPLESCRIPT 2>>"$LOG" || true
tell application "Google Chrome"
  if (count of windows) > 0 then
    tell window 1 to make new tab at end of tabs with properties {URL:"chrome://extensions/"}
  end if
end tell
APPLESCRIPT
  sleep 1
  osascript <<APPLESCRIPT 2>/dev/null || true
display notification "Drag the folder path (already on your clipboard) onto the Extensions page. Developer Mode is already on. After Load Unpacked, future launches just open claude.ai." with title "AIMG First-Run Install" subtitle "$EXTENSION_DIR"
APPLESCRIPT
  # Mark first-run done — Chrome will remember the extension across future launches
  touch "$FIRST_RUN_MARKER"
else
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --user-data-dir="$PROFILE_DIR" \
    --no-first-run --no-default-browser-check \
    --window-size=1280,900 --window-position=120,80 \
    "https://claude.ai/" \
    >> "$LOG" 2>&1 &
  disown
fi

echo "[$(date -Iseconds)] AIMG Chrome backgrounded; profile=$PROFILE_DIR" >> "$LOG"
