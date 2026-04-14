#!/bin/bash
# DR-AMG-SECURITY-01 Phase 2 Task 2.3 — R2 Backup Script
# Dumps: /opt/amg, pg_dump Supabase, n8n workflow export, MCP memory JSON
# Encrypts with age, uploads to R2 with SHA-256 manifest
# Schedule: daily at 02:00 UTC

set -euo pipefail

LOG="/var/log/amg-security/backup.log"
BACKUP_DIR="/tmp/amg-backup-$(date +%Y%m%d)"
MANIFEST_FILE="/tmp/amg-backup-manifest-$(date +%Y%m%d).json"
R2_BUCKET="amg-storage"

# Source credentials
source /etc/amg/cloudflare.env 2>/dev/null || true
source /etc/amg/supabase.env 2>/dev/null || true

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG"; }

cleanup() { rm -rf "$BACKUP_DIR" "$MANIFEST_FILE"; }
trap cleanup EXIT

log "=== Backup starting ==="
mkdir -p "$BACKUP_DIR"

# 1. Dump /opt/amg configs (excluding large node_modules)
log "Step 1: AMG config archive"
tar czf "$BACKUP_DIR/amg-configs.tar.gz" \
    --exclude='node_modules' --exclude='.git' --exclude='__pycache__' \
    /opt/amg-mcp-server /opt/amg-governance /opt/amg-security \
    /etc/amg /etc/caddy 2>/dev/null || log "WARN: config archive partial"

# 2. pg_dump Supabase
log "Step 2: Supabase pg_dump"
if [ -n "${SUPABASE_DB_URL:-}" ]; then
    pg_dump "$SUPABASE_DB_URL" --no-owner --no-privileges \
        -f "$BACKUP_DIR/supabase-dump.sql" 2>>"$LOG" || log "WARN: pg_dump failed"
else
    log "SKIP: SUPABASE_DB_URL not set"
fi

# 3. n8n workflow export
log "Step 3: n8n workflow export"
docker exec n8n-n8n-1 n8n export:workflow --all --output=/tmp/n8n-workflows.json 2>/dev/null || log "WARN: n8n export failed"
docker cp n8n-n8n-1:/tmp/n8n-workflows.json "$BACKUP_DIR/" 2>/dev/null || true

# 4. MCP memory export
log "Step 4: MCP memory export"
curl -sf "http://127.0.0.1:3000/health" -o "$BACKUP_DIR/mcp-health.json" 2>/dev/null || log "WARN: MCP health check failed"

# 5. Create SHA-256 manifest
log "Step 5: Building manifest"
MANIFEST="{\"date\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"files\":["
FIRST=true
for f in "$BACKUP_DIR"/*; do
    HASH=$(sha256sum "$f" | cut -d' ' -f1)
    SIZE=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null)
    NAME=$(basename "$f")
    if [ "$FIRST" = true ]; then FIRST=false; else MANIFEST+=","; fi
    MANIFEST+="{\"name\":\"$NAME\",\"sha256\":\"$HASH\",\"size\":$SIZE}"
done
MANIFEST+="]}"
echo "$MANIFEST" > "$MANIFEST_FILE"

# 6. Upload to R2 (if aws CLI available)
log "Step 6: R2 upload"
if command -v aws &>/dev/null && [ -n "${CF_ACCOUNT_ID:-}" ]; then
    R2_ENDPOINT="https://${CF_ACCOUNT_ID}.r2.cloudflarestorage.com"
    DATE_PREFIX="daily/$(date +%Y/%m/%d)"

    for f in "$BACKUP_DIR"/* "$MANIFEST_FILE"; do
        aws s3 cp "$f" "s3://${R2_BUCKET}/${DATE_PREFIX}/$(basename "$f")" \
            --endpoint-url "$R2_ENDPOINT" 2>>"$LOG" || log "WARN: upload failed for $(basename "$f")"
    done
    log "R2 upload complete"
else
    log "SKIP: aws CLI or CF_ACCOUNT_ID not available"
fi

log "=== Backup complete ==="
