#!/bin/bash
# titan-harness/bin/titan-night-grind.sh
#
# Night grind: aggressive drain of non-interactive RADAR work during the
# 01:00-05:00 Boston night window. Fired by root crontab at 01:07 Boston
# (06:07 UTC for EST / 05:07 UTC for EDT — use 01:07 local time in crontab
# for automatic DST handling).
#
# Relaxes SOFT capacity limits during the window (hard limits unchanged).
# Runs until 05:00 Boston or queue drained, whichever first.
#
# Never touches interactive work. See plans/PLAN_2026-04-12_vps-scheduler-night-grind.md
# for the full spec.
#
# Exit codes:
#   0 — clean (ran to window end or drained queue)
#   1 — capacity hard-blocked throughout window (no work done)
#   2 — preflight failed
#   3 — internal error

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="${TITAN_NIGHT_GRIND_LOG:-/var/log/titan-night-grind.log}"

# Night grind window cutoff (local Boston time)
NIGHT_GRIND_END_HOUR="${NIGHT_GRIND_END_HOUR:-5}"

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] night-grind: $*" >> "$LOG_FILE"
}

log "START (target cutoff: ${NIGHT_GRIND_END_HOUR}:00 local)"

# 1. preflight
if ! bash "$REPO_ROOT/bin/harness-preflight.sh" >> "$LOG_FILE" 2>&1; then
  log "preflight FAILED — aborting"
  exit 2
fi

# 2. relax soft capacity limits for the window (hard limits unchanged)
export POLICY_CAPACITY_MAX_HEAVY_TASKS=12
export POLICY_CAPACITY_MAX_WORKERS_GENERAL=14
export POLICY_CAPACITY_MAX_CONCURRENT_LLM_BATCHES=10
log "soft capacity relaxed: heavy=12 general=14 llm=10"

# 3. run the drain loop — up to NIGHT_GRIND_END_HOUR local time
WORK_DONE=0
while true; do
  CURRENT_HOUR=$(date +%H)
  if [ "$CURRENT_HOUR" -ge "$NIGHT_GRIND_END_HOUR" ] && [ "$CURRENT_HOUR" -lt 12 ]; then
    log "reached cutoff hour ${NIGHT_GRIND_END_HOUR}:00 — ending grind"
    break
  fi

  # Check capacity each iteration (hard block = stop entirely)
  bash "$REPO_ROOT/bin/check-capacity.sh" >> "$LOG_FILE" 2>&1
  CAPACITY_EXIT=$?
  if [ "$CAPACITY_EXIT" -eq 2 ]; then
    log "capacity HARD-BLOCKED — pausing 5 min"
    sleep 300
    continue
  fi

  # Run one drain pass
  python3 "$REPO_ROOT/lib/radar_drain.py" --mode=night-grind >> "$LOG_FILE" 2>&1
  DRAIN_EXIT=$?

  if [ "$DRAIN_EXIT" -eq 0 ]; then
    # Check if anything was submitted this pass (via exit code 10 = empty queue)
    python3 "$REPO_ROOT/lib/radar_drain.py" --mode=check-empty >> "$LOG_FILE" 2>&1
    if [ "$?" -eq 10 ]; then
      log "queue empty — sleeping 10 min before next check"
      sleep 600
      continue
    fi
    WORK_DONE=$((WORK_DONE + 1))
  fi

  # Throttle: max 1 drain pass every 5 minutes to avoid overloading
  sleep 300
done

# 4. reset capacity limits
unset POLICY_CAPACITY_MAX_HEAVY_TASKS
unset POLICY_CAPACITY_MAX_WORKERS_GENERAL
unset POLICY_CAPACITY_MAX_CONCURRENT_LLM_BATCHES
log "capacity limits reset to defaults"

log "END (work passes completed: $WORK_DONE)"
exit 0
