#!/usr/bin/env bash
# scripts/disk-health-tracker.sh
# POST-R3 Phase 3 — Disk usage + days-to-full metric
#
# Appends {"ts","pct_used","bytes_used","bytes_total","days_to_full"} to
# /var/log/titan/disk-health.jsonl on each run.
#
# days_to_full is calculated from the growth delta across the last 7 JSONL
# entries. Writes null if fewer than 2 entries exist.

set -euo pipefail

LOG_DIR="${TITAN_HEALTH_LOG_DIR:-/var/log/titan}"
JSONL="$LOG_DIR/disk-health.jsonl"

mkdir -p "$LOG_DIR"

# --- current disk state ---
# df --output= omits filesystem/mount columns; fields are just the requested ones
read -r size used avail pct < <(df --output=size,used,avail,pcent / | tail -1 | sed 's/%//g')
# df --output values are in 1K blocks
bytes_used=$((used * 1024))
bytes_total=$((size * 1024))
pct_used=$((pct))
ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# --- days_to_full from last 7 entries ---
days_to_full="null"
if [ -f "$JSONL" ]; then
  entry_count=$(wc -l < "$JSONL" | tr -d ' ')
  if [ "$entry_count" -ge 2 ]; then
    # grab last 7 (or fewer) entries
    recent=$(tail -7 "$JSONL")
    first_ts=$(echo "$recent" | head -1 | python3 -c "import sys,json; print(json.loads(sys.stdin.readline())['ts'])" 2>/dev/null || echo "")
    first_used=$(echo "$recent" | head -1 | python3 -c "import sys,json; print(json.loads(sys.stdin.readline())['bytes_used'])" 2>/dev/null || echo "0")
    last_ts="$ts"
    last_used="$bytes_used"

    if [ -n "$first_ts" ] && [ "$first_used" != "0" ]; then
      days_to_full=$(python3 -c "
from datetime import datetime
t0 = datetime.fromisoformat('${first_ts}'.replace('Z','+00:00'))
t1 = datetime.fromisoformat('${last_ts}'.replace('Z','+00:00'))
delta_sec = (t1 - t0).total_seconds()
delta_bytes = ${last_used} - ${first_used}
total = ${bytes_total}
if delta_sec > 0 and delta_bytes > 0:
    rate = delta_bytes / delta_sec
    remaining = total - ${last_used}
    days = remaining / rate / 86400
    print(f'{days:.1f}')
else:
    print('null')
" 2>/dev/null || echo "null")
    fi
  fi
fi

# --- append JSONL entry ---
if [ "$days_to_full" = "null" ]; then
  echo "{\"ts\":\"$ts\",\"pct_used\":$pct_used,\"bytes_used\":$bytes_used,\"bytes_total\":$bytes_total,\"days_to_full\":null}" >> "$JSONL"
else
  echo "{\"ts\":\"$ts\",\"pct_used\":$pct_used,\"bytes_used\":$bytes_used,\"bytes_total\":$bytes_total,\"days_to_full\":$days_to_full}" >> "$JSONL"
fi

echo "disk-health: ${pct_used}% used, days_to_full=${days_to_full}"
