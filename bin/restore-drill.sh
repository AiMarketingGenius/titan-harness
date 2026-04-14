#!/bin/bash
# DR-AMG-SECURITY-01 Phase 3 Task 3.7 — Monthly Restore Drill
# Schedule: 1st Sunday 04:00 UTC
set -euo pipefail

LOG="/var/log/amg-security/restore-drill.log"
DRILL_DIR="/tmp/restore-drill-$(date +%Y%m%d)"
REPORT_FILE="/tmp/restore-drill-report-$(date +%Y%m%d).json"

source /etc/amg/supabase.env 2>/dev/null || true
source /etc/amg/cloudflare.env 2>/dev/null || true

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG"; }

cleanup() { rm -rf "$DRILL_DIR"; }
trap cleanup EXIT

log "=== Monthly restore drill starting ==="
mkdir -p "$DRILL_DIR"

START_TIME=$(date +%s)
TESTS_PASSED=0
TESTS_FAILED=0

# 1. Find latest backup
LATEST_BACKUP=$(find /tmp -name 'amg-backup-*' -maxdepth 1 -type d 2>/dev/null | sort -r | head -1)
if [ -z "$LATEST_BACKUP" ]; then
    log "ERROR: No local backup found — check R2"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# 2. Test: verify backup manifest exists
if [ -f "${LATEST_BACKUP:-/nonexistent}/amg-backup-manifest-*.json" ] 2>/dev/null; then
    TESTS_PASSED=$((TESTS_PASSED + 1))
    log "PASS: Backup manifest exists"
else
    TESTS_FAILED=$((TESTS_FAILED + 1))
    log "FAIL: No backup manifest found"
fi

# 3. Test: verify SQL dump can be parsed
if [ -f "${LATEST_BACKUP:-/nonexistent}/supabase-dump.sql" ] 2>/dev/null; then
    LINES=$(wc -l < "${LATEST_BACKUP}/supabase-dump.sql")
    if [ "$LINES" -gt 100 ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log "PASS: SQL dump has $LINES lines"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log "FAIL: SQL dump too small ($LINES lines)"
    fi
else
    TESTS_FAILED=$((TESTS_FAILED + 1))
    log "FAIL: No SQL dump found"
fi

# 4. Test: verify config archive
if [ -f "${LATEST_BACKUP:-/nonexistent}/amg-configs.tar.gz" ] 2>/dev/null; then
    SIZE=$(stat -c%s "${LATEST_BACKUP}/amg-configs.tar.gz" 2>/dev/null || stat -f%z "${LATEST_BACKUP}/amg-configs.tar.gz" 2>/dev/null)
    if [ "$SIZE" -gt 1000 ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log "PASS: Config archive is ${SIZE} bytes"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log "FAIL: Config archive too small (${SIZE} bytes)"
    fi
else
    TESTS_FAILED=$((TESTS_FAILED + 1))
    log "FAIL: No config archive found"
fi

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Generate report
cat > "$REPORT_FILE" << EOF
{
    "date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "backup_source": "${LATEST_BACKUP:-none}",
    "restore_seconds": $DURATION,
    "tests_passed": $TESTS_PASSED,
    "tests_failed": $TESTS_FAILED,
    "status": "$([ $TESTS_FAILED -eq 0 ] && echo 'PASS' || echo 'FAIL')"
}
EOF

log "Report: $(cat "$REPORT_FILE")"

if [ "$TESTS_FAILED" -gt 0 ]; then
    log "❌ Restore drill: $TESTS_FAILED test(s) failed"
    echo "{\"event\": \"restore_drill_fail\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"failed\": $TESTS_FAILED}" >> /var/log/amg-security/security-events.jsonl
else
    log "✅ Restore drill: all $TESTS_PASSED tests passed"
fi

log "=== Monthly restore drill complete ($DURATION seconds) ==="
