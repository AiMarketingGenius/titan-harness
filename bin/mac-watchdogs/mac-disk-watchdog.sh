#!/bin/bash
# AMG Mac disk-watchdog — runs every 15min via launchd, threshold-triggered cleanup
# Per CT-0427-45 (Titan, 2026-04-27). Mac counterpart of /opt/amg-scripts/disk-watchdog.sh on VPS.

set -euo pipefail

LOG=$HOME/.openclaw/logs/mac_disk_watchdog.log
LOCK=/tmp/amg-mac-disk-watchdog.lock
THRESHOLD=85
SLACK_TOKEN="${SLACK_BOT_TOKEN:-xoxb-6733556195859-10863840159168-9AMfnuLnvESa9MCHW1TLphoR}"
SLACK_CHANNEL="#amg-admin"

mkdir -p "$(dirname "$LOG")"
exec 200>"$LOCK"
flock -n 200 || { echo "$(date -u +%FT%TZ) LOCK_SKIP" >> "$LOG"; exit 0; }

PCT=$(df ~ | awk 'NR==2{ gsub("%","",$5); print int($5)}')
TS=$(date -u +%FT%TZ)
echo "$TS disk_pct=$PCT threshold=$THRESHOLD" >> "$LOG"

slack(){ curl -s -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer $SLACK_TOKEN" -H "Content-Type: application/json" \
  -d "{\"channel\":\"$SLACK_CHANNEL\",\"text\":\"$1\"}" >/dev/null 2>&1 || true; }

if [ "$PCT" -lt "$THRESHOLD" ]; then exit 0; fi

slack ":rotating_light: mac-disk-watchdog: Mac data volume at ${PCT}% (>${THRESHOLD}%). Running safe-prune playbook."
echo "$TS triggered_prune pct=$PCT" >> "$LOG"

# === SAFE AUTO-PRUNE (no greenlight needed) ===
# 1. Caches >30 days mtime
find "$HOME/Library/Caches" -type f -mtime +30 -delete 2>/dev/null || true
# 2. Logs >14 days
find "$HOME/Library/Logs" -type f -mtime +14 -delete 2>/dev/null || true
# 3. Trash NOT auto-cleared — Solon keeps for content repurposing (2026-04-27 directive)
# 4. Time Machine local snapshots (delete oldest if any)
SNAPS=$(tmutil listlocalsnapshots / 2>/dev/null | grep -c "com.apple")
if [ "$SNAPS" -gt 0 ]; then
  tmutil thinlocalsnapshots / 1000000000 1 2>/dev/null || true  # thin to 1GB urgency
  echo "$TS thinned_snapshots count_was=$SNAPS" >> "$LOG"
fi
# 5. Xcode simulators (if Xcode present)
if command -v xcrun >/dev/null 2>&1; then
  xcrun simctl delete unavailable >/dev/null 2>&1 || true
fi

PCT_AFTER=$(df ~ | awk 'NR==2{ gsub("%","",$5); print int($5)}')
echo "$TS disk_pct_after=$PCT_AFTER" >> "$LOG"

if [ "$PCT_AFTER" -ge "$THRESHOLD" ]; then
  TOP_DOWNLOADS=$(du -shx "$HOME/Downloads"/* 2>/dev/null | sort -rh | head -5 | sed 's/\t/ /g; s/\"/\\\"/g' | awk '{printf "%s\\n", $0}')
  TOP_LIB=$(du -shx "$HOME/Library/Application Support"/* 2>/dev/null | sort -rh | head -5 | sed 's/\t/ /g; s/\"/\\\"/g' | awk '{printf "%s\\n", $0}')
  slack ":warning: mac-disk-watchdog: still ${PCT_AFTER}% after safe-prune. Greenlight needed.\n*Top Downloads candidates:*\n${TOP_DOWNLOADS}\n*Top Library/Application Support:*\n${TOP_LIB}\n*Action:* tap a number in Slack to authorize delete, or run iCloud 'Optimize Mac Storage' if Library/Mobile Documents is the bulk."
else
  slack ":white_check_mark: mac-disk-watchdog: ${PCT}% → ${PCT_AFTER}% via safe-prune."
fi
