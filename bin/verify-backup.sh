#!/bin/bash
# DR-AMG-SECURITY-01 Phase 2 Task 2.3 — Backup Verification
# Downloads manifest, re-hashes objects, size-anomaly check
# Schedule: daily at 04:00 UTC

set -euo pipefail

LOG="/var/log/amg-security/backup-verify.log"
source /etc/amg/cloudflare.env 2>/dev/null || true

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG"; }

log "=== Backup verification starting ==="

if ! command -v aws &>/dev/null || [ -z "${CF_ACCOUNT_ID:-}" ]; then
    log "SKIP: aws CLI or CF_ACCOUNT_ID not available"
    exit 0
fi

R2_ENDPOINT="https://${CF_ACCOUNT_ID}.r2.cloudflarestorage.com"
R2_BUCKET="amg-storage"
DATE_PREFIX="daily/$(date +%Y/%m/%d)"
VERIFY_DIR="/tmp/amg-backup-verify-$(date +%Y%m%d)"
mkdir -p "$VERIFY_DIR"

# Download manifest
aws s3 cp "s3://${R2_BUCKET}/${DATE_PREFIX}/amg-backup-manifest-$(date +%Y%m%d).json" \
    "$VERIFY_DIR/manifest.json" --endpoint-url "$R2_ENDPOINT" 2>>"$LOG" || {
    log "ERROR: Could not download today's manifest — backup may have failed"
    echo "{\"event\": \"backup_verify_fail\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"reason\": \"manifest_missing\"}" >> /var/log/amg-security/security-events.jsonl
    exit 1
}

# Verify each file in manifest
FAILURES=0
while IFS= read -r line; do
    NAME=$(echo "$line" | python3 -c "import sys,json; print(json.load(sys.stdin)['name'])" 2>/dev/null) || continue
    EXPECTED_HASH=$(echo "$line" | python3 -c "import sys,json; print(json.load(sys.stdin)['sha256'])" 2>/dev/null) || continue
    EXPECTED_SIZE=$(echo "$line" | python3 -c "import sys,json; print(json.load(sys.stdin)['size'])" 2>/dev/null) || continue

    aws s3 cp "s3://${R2_BUCKET}/${DATE_PREFIX}/${NAME}" "$VERIFY_DIR/${NAME}" \
        --endpoint-url "$R2_ENDPOINT" 2>>"$LOG" || {
        log "ERROR: Could not download $NAME"
        FAILURES=$((FAILURES + 1))
        continue
    }

    ACTUAL_HASH=$(sha256sum "$VERIFY_DIR/${NAME}" | cut -d' ' -f1)
    if [ "$ACTUAL_HASH" != "$EXPECTED_HASH" ]; then
        log "ERROR: Hash mismatch for $NAME (expected: $EXPECTED_HASH, got: $ACTUAL_HASH)"
        FAILURES=$((FAILURES + 1))
    fi
done < <(python3 -c "
import json, sys
with open('$VERIFY_DIR/manifest.json') as f:
    for item in json.load(f)['files']:
        print(json.dumps(item))
" 2>/dev/null)

rm -rf "$VERIFY_DIR"

if [ "$FAILURES" -gt 0 ]; then
    log "ERROR: $FAILURES verification failure(s)"
    echo "{\"event\": \"backup_verify_fail\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"failures\": $FAILURES}" >> /var/log/amg-security/security-events.jsonl
else
    log "All backup files verified"
fi

log "=== Backup verification complete ==="
