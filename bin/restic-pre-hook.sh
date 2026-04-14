#!/bin/bash
# restic-pre-hook.sh — runs before every restic backup
# pg_dump Supabase, n8n workflow export, MCP health snapshot
# Output: /opt/amg-backups/*-latest.{sql,json}  (restic then picks these up)
set -euo pipefail

BACKUP_STAGE="/opt/amg-backups"
LOG="/var/log/amg/backup.log"
mkdir -p "$BACKUP_STAGE" "$(dirname "$LOG")"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] PRE-HOOK: $1" | tee -a "$LOG"; }

log "starting"

# 1. Postgres dump (consistent via pg_dump's own MVCC snapshot)
if [ -f /etc/amg/supabase.env ]; then
    # shellcheck disable=SC1091
    source /etc/amg/supabase.env
fi
if [ -n "${SUPABASE_DB_URL:-}" ]; then
    log "pg_dump Supabase -> supabase-latest.sql"
    if pg_dump "$SUPABASE_DB_URL" --no-owner --no-privileges \
        -f "${BACKUP_STAGE}/supabase-latest.sql" 2>>"$LOG"; then
        log "pg_dump OK ($(wc -l < "${BACKUP_STAGE}/supabase-latest.sql") lines)"
    else
        log "WARN: pg_dump failed — backup proceeds without DB dump"
    fi
else
    log "SKIP: SUPABASE_DB_URL not set"
fi

# 2. n8n workflow export
if docker ps --format '{{.Names}}' | grep -q '^n8n-n8n-1$'; then
    log "n8n workflow export"
    docker exec n8n-n8n-1 sh -c \
        'n8n export:workflow --all --output=/tmp/n8n-workflows-latest.json' 2>>"$LOG" \
        || log "WARN: n8n export command failed"
    docker cp n8n-n8n-1:/tmp/n8n-workflows-latest.json \
        "${BACKUP_STAGE}/n8n-workflows-latest.json" 2>>"$LOG" \
        || log "WARN: n8n cp failed"
else
    log "SKIP: n8n-n8n-1 container not running"
fi

# 3. MCP health snapshot (non-blocking, best-effort)
if curl -sf -m 3 "http://127.0.0.1:3000/health" \
    -o "${BACKUP_STAGE}/mcp-health-latest.json" 2>>"$LOG"; then
    log "MCP health OK"
else
    log "WARN: MCP health check failed or MCP down"
fi

log "complete"
