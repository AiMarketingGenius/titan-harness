#!/usr/bin/env bash
# bin/opa-auto-revert-tick.sh
# Gate #4 v1.2 — systemd-invoked tick (every 15min).
# Flips mode enforce → audit on any of:
#   - chrony drift out of spec
#   - escape-hatch red
#   - 7d enforce expiry (enforce becomes permanent after; next cycle requires fresh ack)
#   - presence of /etc/amg/gate4-reverse-ack.flag

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE_FILE="/etc/amg/opa-mode"
ENFORCE_START="/etc/amg/opa-enforce-start.ts"
REVERSE_FLAG="/etc/amg/gate4-reverse-ack.flag"
LOG="/var/log/amg/opa-auto-revert.log"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

revert() {
    local reason="$1"
    "${REPO}/bin/opa-deploy.sh" --revert >/dev/null 2>&1 || true
    echo "$TS auto-revert: $reason" >> "$LOG"
    python3 - <<PY 2>/dev/null || true
import sys
sys.path.insert(0, "${REPO}/lib")
try:
    from aristotle_slack import post_to_channel
    post_to_channel("#titan-aristotle", f":leftwards_arrow_with_hook: Gate #4 AUTO-REVERT — reason: {sys.argv[1]}")
except Exception: pass
PY
    exit 0
}

MODE="$(cat "$MODE_FILE" 2>/dev/null || echo audit)"
[[ "$MODE" != "enforce" ]] && exit 0

# Reverse-ack flag wins immediately
[[ -f "$REVERSE_FLAG" ]] && { rm -f "$REVERSE_FLAG"; revert "reverse-ack flag present"; }

# Chrony drift
if ! "${REPO}/bin/opa-chrony-check.sh" --json >/tmp/chrony.json 2>/dev/null; then
    revert "chrony drift (see /tmp/chrony.json)"
fi

# Escape-hatch red
if ! "${REPO}/bin/escape-hatch-verify.sh" --json >/tmp/eh.json 2>/dev/null; then
    GREEN="$(python3 -c "import json;print(json.load(open('/tmp/eh.json')).get('all_green', False))" 2>/dev/null || echo False)"
    [[ "$GREEN" == "False" ]] && revert "escape-hatch red"
fi

# 7d enforce tail expiry (becomes permanent: write a marker, keep mode=enforce)
if [[ -f "$ENFORCE_START" ]]; then
    START="$(cat "$ENFORCE_START")"
    AGE=$(( $(date +%s) - START ))
    if (( AGE > 604800 )); then
        touch /etc/amg/gate4-enforce-permanent.flag
        echo "$TS enforce permanent after 7d clean observe-tail" >> "$LOG"
        # Don't revert — keep enforce. Mode stays. Next audit cycle requires fresh ack.
    fi
fi

exit 0
