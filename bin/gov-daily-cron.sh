#!/bin/bash
# DR-AMG-GOVERNANCE-01 Phase 3 — Daily Governance Cron
# Runs: behavioral baseline capture, drift scoring, anti-pattern monitoring
# Schedule: daily at 06:00 UTC via crontab

set -uo pipefail

LOG="/var/log/amg-governance-daily.log"
GOV_DIR="/opt/amg-governance"
FAILURES=0

if [ -f /etc/amg/supabase.env ]; then
    source /etc/amg/supabase.env
fi
export SUPABASE_DB_URL="${SUPABASE_DB_URL:-}"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG"; }

log "=== Daily governance cron starting ==="

# 1. Capture behavioral baseline (last 24h window)
log "Step 1: Behavioral baseline capture"
if ! sudo SUPABASE_DB_URL="$SUPABASE_DB_URL" python3 "$GOV_DIR/behavioral_baseline.py" --capture --session-id "daily-cron-$(date +%Y%m%d)" --window-hours 24 >> "$LOG" 2>&1; then
    log "ERROR: baseline capture FAILED"
    FAILURES=$((FAILURES + 1))
fi

# 2. Refresh rolling baseline markers
log "Step 2: Refresh rolling baseline"
if ! sudo SUPABASE_DB_URL="$SUPABASE_DB_URL" python3 "$GOV_DIR/behavioral_baseline.py" --refresh >> "$LOG" 2>&1; then
    log "ERROR: baseline refresh FAILED"
    FAILURES=$((FAILURES + 1))
fi

# 3. Run drift scoring
log "Step 3: Drift scoring"
if ! sudo SUPABASE_DB_URL="$SUPABASE_DB_URL" python3 "$GOV_DIR/drift_scoring.py" --score >> "$LOG" 2>&1; then
    log "ERROR: drift scoring FAILED"
    FAILURES=$((FAILURES + 1))
fi

# 4. Run anti-pattern monitoring
log "Step 4: Anti-pattern monitoring"
if ! sudo SUPABASE_DB_URL="$SUPABASE_DB_URL" python3 "$GOV_DIR/antipattern_monitor.py" >> "$LOG" 2>&1; then
    log "ERROR: antipattern monitor FAILED"
    FAILURES=$((FAILURES + 1))
fi

# Track consecutive failures for alerting
FAIL_TRACKER="/var/log/amg-governance-daily-failures.count"
if [ "$FAILURES" -gt 0 ]; then
    PREV_FAILS=$(cat "$FAIL_TRACKER" 2>/dev/null || echo 0)
    TOTAL_CONSEC=$((PREV_FAILS + 1))
    echo "$TOTAL_CONSEC" > "$FAIL_TRACKER"
    log "ERROR: $FAILURES step(s) failed. Consecutive failure days: $TOTAL_CONSEC"
    if [ "$TOTAL_CONSEC" -ge 2 ]; then
        log "ALERT: 2+ consecutive daily cron failures — governance loop degraded"
    fi
else
    echo 0 > "$FAIL_TRACKER"
    log "All steps completed successfully"
fi

log "=== Daily governance cron complete (failures: $FAILURES) ==="
exit "$FAILURES"
