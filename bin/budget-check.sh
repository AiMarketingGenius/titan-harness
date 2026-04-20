#!/bin/bash
# bin/budget-check.sh — Fix-4: Budget-aware restart gate (CT-0420-02)
# Reads watchdog.conf for threshold; if Claude weekly budget >= threshold,
# delays restart and posts Slack alert instead of looping.
# Exit 0 = OK to restart. Exit 1 = budget too high, skip restart.

CONF_FILE="${WATCHDOG_CONF:-/etc/amg/watchdog.conf}"
LOG="$HOME/.claude/titan-restart.log"
SLACK_ALERT_ONLY=0

# Defaults (overridden by watchdog.conf if present)
BUDGET_THRESHOLD_PCT="${BUDGET_THRESHOLD_PCT:-90}"
RESTART_DELAY_MIN="${RESTART_DELAY_MIN:-30}"

if [[ -f "$CONF_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONF_FILE" 2>/dev/null || true
fi

# Read weekly usage from Claude Code usage file
USAGE_FILE="$HOME/.claude/USAGE.json"
if [[ ! -f "$USAGE_FILE" ]]; then
    # No usage file = can't check; allow restart (fail-open)
    exit 0
fi

PCT=$(python3 - "$USAGE_FILE" << 'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    # Claude Code usage format: { "weeklyUsage": { "percentUsed": 87.3 } }
    pct = d.get("weeklyUsage", {}).get("percentUsed") \
       or d.get("percent_used") \
       or d.get("pct") \
       or None
    if pct is None:
        # Try costCents approach
        used = d.get("costCents", 0)
        limit = d.get("limitCents", 1)
        pct = (used / limit * 100) if limit else 0
    print(f"{float(pct):.1f}")
except Exception:
    print("0")
PY
)

THRESHOLD="${BUDGET_THRESHOLD_PCT:-90}"
IS_HIGH=$(python3 -c "print('1' if float('${PCT:-0}') >= float('${THRESHOLD}') else '0')" 2>/dev/null || echo "0")

if [[ "$IS_HIGH" == "1" ]]; then
    TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    MSG="Titan auto-restart SUPPRESSED at ${TS}. Claude weekly budget ${PCT}% >= ${THRESHOLD}% threshold. Next retry in ${RESTART_DELAY_MIN}min. Fix: complete current session normally or reduce spend."
    echo "$TS $MSG" >> "$LOG"

    # Post Slack alert
    WEBHOOK=""
    for f in ~/.titan-env /opt/amg-titan/.env ~/.config/titan/env; do
        [[ -f "$f" ]] && WEBHOOK=$(grep 'SLACK_WEBHOOK' "$f" 2>/dev/null | head -1 | cut -d= -f2 | tr -d '"') && [[ -n "$WEBHOOK" ]] && break
    done
    [[ -n "$WEBHOOK" ]] && curl -s --max-time 5 -X POST "$WEBHOOK" \
        -H 'Content-Type: application/json' \
        -d "{\"text\":\":warning: $MSG\"}" >/dev/null 2>&1 || true

    exit 1
fi

exit 0
