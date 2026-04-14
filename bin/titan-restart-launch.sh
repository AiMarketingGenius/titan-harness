#!/usr/bin/env bash
# bin/titan-restart-launch.sh
# Invoked by ~/Library/LaunchAgents/com.amg.titan-autorestart.plist when
# the restart flag is touched by bin/titan-restart-capture.sh.
#
# Responsibilities:
#   1. Consume + clear the restart flag (idempotent).
#   2. Notify Slack: "fresh Titan session launching".
#   3. Open a Terminal/iTerm window running `claude` from the harness repo.
#      The new Claude Code session's SessionStart hook cold-boots as usual;
#      the resume-state file is read by Titan on first turn per the boot
#      prompt in bin/titan-resume-boot-prompt.md.
#
# launchd will re-fire the plist on every flag touch — this script must be
# idempotent and fast-exiting. We rate-limit via a 30-second debounce file.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLAG="$HOME/.claude/titan-restart.flag"
LAST_LAUNCH="$HOME/.claude/titan-restart.last-launch-ts"
LOG="$HOME/.claude/titan-restart.log"
DAILY_COUNT_DIR="$HOME/.claude/titan-restart.daily"
DEBOUNCE_SEC=30
DAILY_CAP="${TITAN_RESTART_DAILY_CAP:-50}"

mkdir -p "$HOME/.claude" "$DAILY_COUNT_DIR"

exec >>"$LOG" 2>&1
echo "----- $(date -u +%Y-%m-%dT%H:%M:%SZ) launch fire -----"

[[ ! -f "$FLAG" ]] && { echo "no flag — nothing to do"; exit 0; }

now=$(date +%s)
last=0
[[ -f "$LAST_LAUNCH" ]] && last="$(cat "$LAST_LAUNCH" 2>/dev/null || echo 0)"
if (( now - last < DEBOUNCE_SEC )); then
    echo "debounced (last launch ${last}; now ${now}; min interval ${DEBOUNCE_SEC}s)"
    exit 0
fi
echo -n "$now" > "$LAST_LAUNCH"

# Daily restart cap — prevents runaway loops beyond the 30s debounce.
TODAY_FILE="$DAILY_COUNT_DIR/$(date -u +%Y-%m-%d).count"
today_count="$(cat "$TODAY_FILE" 2>/dev/null || echo 0)"
if (( today_count >= DAILY_CAP )); then
    echo "DAILY CAP REACHED (${today_count}/${DAILY_CAP}) — refusing to relaunch. Fix underlying cause."
    bash "${REPO}/bin/titan-notify.sh" --title "Titan auto-restart DAILY CAP" \
        "Reached ${today_count}/${DAILY_CAP} restarts today. Refusing further relaunches. Fix loop cause, then: rm $TODAY_FILE" \
        >/dev/null 2>&1 || true
    exit 0
fi
echo -n "$((today_count + 1))" > "$TODAY_FILE"

# Clear flag first — prevents retrigger storm
rm -f "$FLAG"

# Slack
bash "${REPO}/bin/titan-notify.sh" \
  --title "Titan session restart" \
  "Fresh session spawning in 3s. Resume state: ~/.claude/titan-resume-state.json. Boot prompt: bin/titan-resume-boot-prompt.md." \
  >/dev/null 2>&1 || true

# Spawn a new Terminal window running `claude` from the harness.
# Wrapped in osascript to respect macOS Terminal/iTerm preference.
if command -v osascript >/dev/null 2>&1; then
    # Prefer tmux (headless-friendly) if TITAN_RESTART_TARGET=tmux, else iTerm if running, else Terminal
    APP="Terminal"
    if [[ "${TITAN_RESTART_TARGET:-}" == "tmux" ]] && command -v tmux >/dev/null 2>&1; then
        APP="tmux"
    elif pgrep -x iTerm2 >/dev/null 2>&1 || pgrep -f "iTerm.app" >/dev/null 2>&1; then
        APP="iTerm"
    fi
    case "$APP" in
        tmux)
            SESS="${TITAN_TMUX_SESSION:-titan}"
            if ! tmux has-session -t "$SESS" 2>/dev/null; then
                tmux new-session -d -s "$SESS" -c "$REPO"
            fi
            tmux send-keys -t "$SESS" "cd $REPO && claude" C-m
            echo "spawned tmux session '$SESS' with: cd $REPO && claude"
            ;;
        iTerm)
            osascript <<EOF 2>/dev/null || true
tell application "iTerm"
    create window with default profile
    tell current session of current window
        write text "cd $REPO && claude"
    end tell
end tell
EOF
            ;;
        Terminal)
            osascript <<EOF 2>/dev/null || true
tell application "Terminal"
    activate
    do script "cd $REPO && claude"
end tell
EOF
            ;;
    esac
    echo "spawned $APP with: cd $REPO && claude"
else
    echo "osascript unavailable — cannot auto-spawn; user must restart manually"
    exit 1
fi

exit 0
