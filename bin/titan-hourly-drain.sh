#!/bin/bash
# titan-harness/bin/titan-hourly-drain.sh
#
# Hourly drain of non-interactive RADAR work. Fired by root crontab on VPS
# every hour at :05 (off-peak per CronCreate doctrine). Feeds eligible work
# to titan-queue-watcher.service which is the actual executor.
#
# Never touches interactive work (2FA, credentials, business decisions,
# external commitments). See plans/PLAN_2026-04-12_vps-scheduler-night-grind.md §3
# for the full non-interactive classification.
#
# Exit codes:
#   0 — clean (drained + logged, or nothing to drain)
#   1 — capacity hard-blocked (skip this tick)
#   2 — preflight failed (harness or policy)
#   3 — radar_drain.py reported an internal error

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="${TITAN_SCHEDULER_LOG:-/var/log/titan-scheduler.log}"

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] hourly-drain: $*" >> "$LOG_FILE"
}

log "START"

# 1. harness preflight
if ! bash "$REPO_ROOT/bin/harness-preflight.sh" >> "$LOG_FILE" 2>&1; then
  PREFLIGHT_EXIT=$?
  log "preflight FAILED exit=$PREFLIGHT_EXIT — skipping tick"
  exit 2
fi

# 2. check capacity (soft_block = skip heavy work, hard_block = skip entire tick)
bash "$REPO_ROOT/bin/check-capacity.sh" >> "$LOG_FILE" 2>&1
CAPACITY_EXIT=$?
if [ "$CAPACITY_EXIT" -eq 2 ]; then
  log "capacity HARD-BLOCKED — skipping tick"
  exit 1
fi
if [ "$CAPACITY_EXIT" -eq 1 ]; then
  log "capacity SOFT-BLOCKED — proceeding with light tasks only"
  export TITAN_DRAIN_LIGHT_ONLY=1
fi

# 3. run the drain (Python driver does the actual work identification)
if command -v python3 >/dev/null 2>&1; then
  python3 "$REPO_ROOT/lib/radar_drain.py" --mode=hourly >> "$LOG_FILE" 2>&1
  DRAIN_EXIT=$?
else
  log "python3 not found — cannot run radar_drain.py"
  exit 3
fi

if [ "$DRAIN_EXIT" -ne 0 ]; then
  log "radar_drain.py exit=$DRAIN_EXIT"
  exit 3
fi

log "END (clean)"
exit 0
