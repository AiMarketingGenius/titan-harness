#!/usr/bin/env bash
# bin/titan-notify.sh
# Unified Slack notifier. Tries port 3300 bot first (local tunnel/docker
# side-proxy), falls back to lib/aristotle_slack.py post_to_channel.
#
# Usage:
#   bin/titan-notify.sh "message text" [--channel "#titan-aristotle"] [--title "Title"]

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHANNEL="#titan-aristotle"
TITLE=""
MSG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --channel) CHANNEL="$2"; shift 2 ;;
        --title)   TITLE="$2"; shift 2 ;;
        *)         MSG="${MSG:+$MSG }$1"; shift ;;
    esac
done
[[ -z "$MSG" ]] && { echo "titan-notify: message required" >&2; exit 2; }

FULL_MSG="${TITLE:+*$TITLE*\n}$MSG"
SENT=0

# Path 1: local port 3300 bot (if listening)
if curl -sf -m 1 -o /dev/null http://127.0.0.1:3300/health 2>/dev/null; then
    if curl -sf -m 3 -X POST http://127.0.0.1:3300/notify \
          -H 'Content-Type: application/json' \
          -d "$(python3 -c "import json,sys; print(json.dumps({'channel':sys.argv[1],'text':sys.argv[2]}))" "$CHANNEL" "$FULL_MSG")" \
          >/dev/null 2>&1; then
        SENT=1
        echo "titan-notify: sent via port 3300 bot"
    fi
fi

# Path 2: aristotle_slack.py fallback
if (( SENT == 0 )); then
    export PYTHONPATH="${REPO}/lib:${PYTHONPATH:-}"
    if python3 -c "
import sys
sys.path.insert(0, '${REPO}/lib')
from aristotle_slack import post_to_channel
post_to_channel('${CHANNEL}', '''${FULL_MSG}''')
" 2>/dev/null; then
        SENT=1
        echo "titan-notify: sent via aristotle_slack.py"
    fi
fi

if (( SENT == 0 )); then
    # Log-only fallback
    mkdir -p "$HOME/.claude/titan-notify-queue"
    echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"channel\":\"$CHANNEL\",\"msg\":$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$FULL_MSG")}" \
        >> "$HOME/.claude/titan-notify-queue/deferred.jsonl"
    echo "titan-notify: both paths failed; queued at ~/.claude/titan-notify-queue/deferred.jsonl" >&2
    exit 1
fi

exit 0
