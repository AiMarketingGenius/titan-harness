#!/bin/bash
# hooks/user-prompt-counter.sh — UserPromptSubmit hook
# Increments the exchange counter. When threshold reached, writes a hint
# file that Titan checks at turn end. Does NOT force Claude to exit —
# exit is Titan's decision (it can finish the turn then say "restarting now").
#
# Activated by .claude/settings.json "UserPromptSubmit" hook registration.

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/titan-env.sh" 2>/dev/null || true

# Pull session_id from hook payload (UserPromptSubmit provides it via stdin JSON).
INPUT="$(cat 2>/dev/null || echo '{}')"
SESSION_ID="$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null || echo '')"
export SESSION_ID

source "$SCRIPT_DIR/../lib/exchange_counter.sh"

NEW_COUNT="$(exchange_count_increment)"

# Don't block the prompt — always exit 0.
# Write hint when threshold reached.
if [[ "$NEW_COUNT" -ge "$TITAN_RESTART_THRESHOLD" ]]; then
    mkdir -p "$HOME/.claude"
    echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"count\":$NEW_COUNT,\"threshold\":$TITAN_RESTART_THRESHOLD}" \
        > "$HOME/.claude/titan-exchange-threshold-reached.json"
    # Surface the hint back to Claude via stdout (if hook supports it)
    echo "[exchange-counter] count=$NEW_COUNT threshold=$TITAN_RESTART_THRESHOLD — wrap up + run bin/titan-restart-capture.sh"
fi

exit 0
