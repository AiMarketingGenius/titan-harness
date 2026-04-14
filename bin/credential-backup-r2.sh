#!/bin/bash
# Credential Inventory → GPG-encrypted → R2 nightly backup
# Schedule: Mac cron, daily 23:00 local
# Bucket: amg-credentials-backup (separate from main storage)
# Retention: 30 versions
set -euo pipefail

CANONICAL="$HOME/Library/Mobile Documents/com~apple~CloudDocs/4TB EasySto BACKUP/My Mac Desktop Folder 2025/Businesses/LeadGen/Flat Fee Mastery/AMG_Agent_Folders/AMG_MASTER_CREDENTIAL_AND_INFRASTRUCTURE_INVENTORY.md"
LOG="$HOME/.titan-credential-backup.log"
R2_BUCKET="amg-credentials-backup"
DATE=$(date +%Y%m%d-%H%M%S)
TMP_DIR=$(mktemp -d)

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG"; }

cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

log "=== Credential backup starting ==="

# 1. Verify source exists
if [ ! -f "$CANONICAL" ]; then
    log "ERROR: Canonical credential doc not found"
    exit 1
fi

# 2. GPG encrypt (symmetric — Solon's passphrase from env)
GPG_PASSPHRASE="${CREDENTIAL_BACKUP_PASSPHRASE:-}"
if [ -z "$GPG_PASSPHRASE" ]; then
    log "ERROR: CREDENTIAL_BACKUP_PASSPHRASE not set in env"
    exit 1
fi

gpg --batch --yes --passphrase "$GPG_PASSPHRASE" --symmetric --cipher-algo AES256 \
    -o "$TMP_DIR/credentials-${DATE}.md.gpg" "$CANONICAL"

log "Encrypted: credentials-${DATE}.md.gpg ($(stat -f%z "$TMP_DIR/credentials-${DATE}.md.gpg") bytes)"

# 3. Upload to R2
if command -v aws &>/dev/null; then
    CF_ACCOUNT_ID="${CF_ACCOUNT_ID:-}"
    if [ -n "$CF_ACCOUNT_ID" ]; then
        R2_ENDPOINT="https://${CF_ACCOUNT_ID}.r2.cloudflarestorage.com"
        aws s3 cp "$TMP_DIR/credentials-${DATE}.md.gpg" \
            "s3://${R2_BUCKET}/credentials-${DATE}.md.gpg" \
            --endpoint-url "$R2_ENDPOINT" 2>>"$LOG"
        log "Uploaded to R2: ${R2_BUCKET}/credentials-${DATE}.md.gpg"

        # Prune to last 30 versions
        VERSIONS=$(aws s3 ls "s3://${R2_BUCKET}/" --endpoint-url "$R2_ENDPOINT" 2>/dev/null | sort -r | tail -n +31 | awk '{print $4}')
        for OLD in $VERSIONS; do
            aws s3 rm "s3://${R2_BUCKET}/${OLD}" --endpoint-url "$R2_ENDPOINT" 2>>"$LOG"
            log "Pruned old version: $OLD"
        done
    else
        log "SKIP: CF_ACCOUNT_ID not set"
    fi
else
    log "SKIP: aws CLI not installed on Mac"
fi

log "=== Credential backup complete ==="
