#!/bin/bash
# DR-AMG-GOVERNANCE-01 Phase 3 — Weekly Governance Cron
# Runs: GHS computation, weekly review data generation
# Schedule: Mondays at 07:30 UTC via crontab

set -uo pipefail

LOG="/var/log/amg-governance-weekly.log"
GOV_DIR="/opt/amg-governance"
FAILURES=0

if [ -f /etc/amg/supabase.env ]; then source /etc/amg/supabase.env; fi
export SUPABASE_DB_URL="${SUPABASE_DB_URL:-}"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG"; }

log "=== Weekly governance cron starting ==="

# 1. Compute Governance Health Score
log "Step 1: GHS computation"
if ! sudo SUPABASE_DB_URL="$SUPABASE_DB_URL" python3 "$GOV_DIR/governance_health_score.py" >> "$LOG" 2>&1; then
    log "ERROR: GHS computation FAILED"
    FAILURES=$((FAILURES + 1))
fi

# 2. Generate dashboard snapshot for weekly review
log "Step 2: Dashboard snapshot"
if ! sudo SUPABASE_DB_URL="$SUPABASE_DB_URL" python3 "$GOV_DIR/governance_dashboard.py" > "/tmp/gov-dashboard-$(date +%Y%m%d).json" 2>> "$LOG"; then
    log "ERROR: dashboard snapshot FAILED"
    FAILURES=$((FAILURES + 1))
fi

if [ "$FAILURES" -gt 0 ]; then
    log "ALERT: $FAILURES weekly cron step(s) failed — GHS may be stale"
fi

log "=== Weekly governance cron complete (failures: $FAILURES) ==="
exit "$FAILURES"
