#!/bin/bash
# AMG Mac memory-watchdog — runs every 5min via launchd, alerts if memory pressure >85%
# Per CT-0427-45 (Titan, 2026-04-27). Mac counterpart of /opt/amg-scripts/memory-watchdog.sh on VPS.

set -euo pipefail

LOG=$HOME/.openclaw/logs/mac_memory_watchdog.log
LOCK=/tmp/amg-mac-memory-watchdog.lock
THRESHOLD=85
SLACK_TOKEN="${SLACK_BOT_TOKEN:-xoxb-6733556195859-10863840159168-9AMfnuLnvESa9MCHW1TLphoR}"
SLACK_CHANNEL="#amg-admin"

mkdir -p "$(dirname "$LOG")"
exec 200>"$LOCK"
flock -n 200 || { echo "$(date -u +%FT%TZ) LOCK_SKIP" >> "$LOG"; exit 0; }

# Mac memory pressure: derived from vm_stat
PAGE_SIZE=$(vm_stat | head -1 | grep -oE "[0-9]+")
TOTAL_PAGES=$(sysctl -n hw.memsize | awk -v ps="$PAGE_SIZE" '{print int($1/ps)}')
USED=$(vm_stat | awk -v ps="$PAGE_SIZE" '
  /^Pages active/    { gsub("\\.",""); a=$3 }
  /^Pages wired down/{ gsub("\\.",""); w=$4 }
  /^Pages occupied by compressor/{ gsub("\\.",""); c=$5 }
  END { print a+w+c }')
PCT=$((USED * 100 / TOTAL_PAGES))
TS=$(date -u +%FT%TZ)
echo "$TS mem_pct=$PCT total_pages=$TOTAL_PAGES used_pages=$USED" >> "$LOG"

if [ "$PCT" -lt "$THRESHOLD" ]; then exit 0; fi

slack(){ curl -s -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer $SLACK_TOKEN" -H "Content-Type: application/json" \
  -d "{\"channel\":\"$SLACK_CHANNEL\",\"text\":\"$1\"}" >/dev/null 2>&1 || true; }

TOP=$(ps -axo pid,user,%mem,rss,comm 2>/dev/null | sort -k3 -rn | head -7 | sed 's/\"/\\\"/g' | awk '{printf "%s\\n", $0}')
slack ":rotating_light: mac-memory-watchdog: Mac memory at ${PCT}% (>${THRESHOLD}%). Top procs:\n${TOP}"
echo "$TS alerted pct=$PCT" >> "$LOG"
