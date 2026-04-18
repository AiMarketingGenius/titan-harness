#!/usr/bin/env bash
# slack-dispatch — thin client for AMG Slack Dispatcher
# Usage:
#   slack-dispatch --severity P2 --source idea-drain --message "idea locked: foo" [--fingerprint <hex>]
# or pipe the message:
#   echo "...long text..." | slack-dispatch -s P1 --source mp-runner
#
# Fails open: if dispatcher unreachable, logs to stderr + exits 0 (never break the caller).

set -u

DISPATCHER_URL="${SLACK_DISPATCHER_URL:-http://127.0.0.1:9877/dispatch}"
SEVERITY=""
SOURCE=""
MESSAGE=""
FINGERPRINT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -s|--severity)   SEVERITY="$2"; shift 2 ;;
    --source)        SOURCE="$2";   shift 2 ;;
    -m|--message)    MESSAGE="$2";  shift 2 ;;
    -f|--fingerprint) FINGERPRINT="$2"; shift 2 ;;
    -h|--help)
      grep '^# ' "$0" | sed 's/^# //'
      exit 0 ;;
    *) echo "slack-dispatch: unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$MESSAGE" && ! -t 0 ]]; then
  MESSAGE=$(cat)
fi

if [[ -z "$SEVERITY" ]] || [[ -z "$SOURCE" ]] || [[ -z "$MESSAGE" ]]; then
  echo "slack-dispatch: --severity, --source, and --message required" >&2
  exit 2
fi

# Minimal JSON builder (stdlib: python3)
json=$(SEV="$SEVERITY" SRC="$SOURCE" MSG="$MESSAGE" FP="$FINGERPRINT" python3 -c '
import json, os
d = {"severity": os.environ["SEV"], "source": os.environ["SRC"], "message": os.environ["MSG"]}
fp = os.environ.get("FP", "")
if fp:
    d["fingerprint"] = fp
print(json.dumps(d))
')

resp=$(curl -sS --max-time 4 -X POST -H "Content-Type: application/json" -d "$json" "$DISPATCHER_URL" 2>/dev/null || true)
if [[ -z "$resp" ]]; then
  echo "slack-dispatch: dispatcher unreachable at $DISPATCHER_URL, msg not sent" >&2
  exit 0
fi
echo "$resp"
