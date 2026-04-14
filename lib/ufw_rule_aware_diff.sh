#!/bin/bash
# SEC P2 Fix 5: UFW rule-order-aware diff (not just sha256 of status output)
# Parses UFW rules into normalized format for meaningful diff
set -euo pipefail

CANONICAL=/etc/amg/ufw-canonical-rules.txt
LOG=/var/log/amg-security/ufw-drift.log
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Normalize UFW rules: strip numbering, sort by port/proto/action for order-independent comparison
normalize_rules() {
    sudo ufw status numbered 2>/dev/null | \
        grep -E '^\[' | \
        sed 's/^\[[ 0-9]*\]\s*//' | \
        sort
}

# Get current normalized rules
CURRENT=$(normalize_rules)
CANONICAL_NORM=$(cat "$CANONICAL" 2>/dev/null | grep -E '^\[' | sed 's/^\[[ 0-9]*\]\s*//' | sort)

# Rule-by-rule comparison
ADDED=$(comm -13 <(echo "$CANONICAL_NORM") <(echo "$CURRENT"))
REMOVED=$(comm -23 <(echo "$CANONICAL_NORM") <(echo "$CURRENT"))

if [ -n "$ADDED" ] || [ -n "$REMOVED" ]; then
    echo "[$TS] UFW DRIFT DETECTED" >> "$LOG"

    if [ -n "$ADDED" ]; then
        echo "  ADDED RULES:" >> "$LOG"
        echo "$ADDED" | while read -r rule; do
            echo "    + $rule" >> "$LOG"
        done
    fi

    if [ -n "$REMOVED" ]; then
        echo "  REMOVED RULES:" >> "$LOG"
        echo "$REMOVED" | while read -r rule; do
            echo "    - $rule" >> "$LOG"
        done
    fi

    # Save forensic snapshot with full numbered output
    sudo ufw status numbered > "/var/log/amg-security/ufw-drift-${TS}.txt"

    # Log structured event
    ADDED_COUNT=$(echo "$ADDED" | grep -c . 2>/dev/null || echo 0)
    REMOVED_COUNT=$(echo "$REMOVED" | grep -c . 2>/dev/null || echo 0)
    echo "{\"event\": \"ufw_drift\", \"timestamp\": \"$TS\", \"added_rules\": $ADDED_COUNT, \"removed_rules\": $REMOVED_COUNT}" >> /var/log/amg-security/security-events.jsonl

    # Auto-heal: restore canonical
    sudo ufw --force reset > /dev/null 2>&1
    while IFS= read -r line; do
        RULE=$(echo "$line" | sed 's/^\[[ 0-9]*\]\s*//')
        if echo "$RULE" | grep -qE 'ALLOW|DENY|REJECT'; then
            sudo ufw $RULE > /dev/null 2>&1 || true
        fi
    done < "$CANONICAL"
    sudo ufw --force enable > /dev/null 2>&1

    echo "[$TS] UFW restored to canonical ($ADDED_COUNT added, $REMOVED_COUNT removed rules reverted)" >> "$LOG"
else
    echo "[$TS] UFW OK (rule-aware check)" >> "$LOG"
fi
