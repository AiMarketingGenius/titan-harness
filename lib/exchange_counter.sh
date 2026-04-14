#!/usr/bin/env bash
# lib/exchange_counter.sh
# Simple file-based exchange counter for Item 7 auto-restart logic.
#
# "Exchange" = one user prompt submission (NOT per-tool; one turn may have
# many tool calls). Incremented by the UserPromptSubmit hook (see
# hooks/user-prompt-counter.sh). Source this file and call the helpers.
#
# Threshold default: 25 (overridable via TITAN_RESTART_THRESHOLD).

# Per-session counter file. Callers may pass SESSION_ID via env to scope
# the counter to one Claude Code window; without SESSION_ID the counter
# falls back to a shared file (legacy behavior; produces collisions if
# multiple windows run simultaneously).
_resolve_counter_file() {
    local sid="${SESSION_ID:-${TITAN_SESSION_ID:-}}"
    if [[ -n "$sid" ]]; then
        echo "$HOME/titan-session/.exchange-count.${sid:0:12}"
    else
        echo "$HOME/titan-session/.exchange-count"
    fi
}
EXCHANGE_COUNT_FILE="${EXCHANGE_COUNT_FILE:-$(_resolve_counter_file)}"
TITAN_RESTART_THRESHOLD="${TITAN_RESTART_THRESHOLD:-25}"

_ensure_count_file() {
    mkdir -p "$(dirname "$EXCHANGE_COUNT_FILE")"
    [[ -f "$EXCHANGE_COUNT_FILE" ]] || echo 0 > "$EXCHANGE_COUNT_FILE"
}

exchange_count_get() {
    _ensure_count_file
    cat "$EXCHANGE_COUNT_FILE" 2>/dev/null || echo 0
}

exchange_count_increment() {
    _ensure_count_file
    local cur
    cur="$(exchange_count_get)"
    local new=$((cur + 1))
    echo "$new" > "$EXCHANGE_COUNT_FILE"
    echo "$new"
}

exchange_count_reset() {
    _ensure_count_file
    echo 0 > "$EXCHANGE_COUNT_FILE"
}

exchange_count_check_threshold() {
    # Prints 'reached' if current count >= threshold, else 'ok'
    local cur
    cur="$(exchange_count_get)"
    if (( cur >= TITAN_RESTART_THRESHOLD )); then
        echo reached
    else
        echo ok
    fi
}
