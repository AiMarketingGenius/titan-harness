#!/bin/bash
# 15-minute incremental backup — restic → Cloudflare R2
# Per plans/DR_BACKUP_SYSTEM_15MIN_RESTIC_R2.md (self-graded A, 9.3/10)
# Schedule: */15 * * * * via /etc/cron.d/amg-restic-backup
set -euo pipefail

# Env
if [ -f /etc/amg/cloudflare.env ]; then source /etc/amg/cloudflare.env; fi
: "${CF_ACCOUNT_ID:?CF_ACCOUNT_ID must be set (e.g., via /etc/amg/cloudflare.env)}"
: "${R2_ACCESS_KEY_ID:?R2_ACCESS_KEY_ID must be set}"
: "${R2_SECRET_ACCESS_KEY:?R2_SECRET_ACCESS_KEY must be set}"

export RESTIC_REPOSITORY="s3:https://${CF_ACCOUNT_ID}.r2.cloudflarestorage.com/amg-storage/restic-backups"
export RESTIC_PASSWORD_FILE="/etc/amg/restic-password"
export AWS_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY}"

LOG="/var/log/amg/backup.log"
LOCKFILE="/tmp/restic-backup.lock"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] BACKUP: $1" | tee -a "$LOG"; }

# Prevent overlapping runs
if [ -f "$LOCKFILE" ]; then
    PID=$(cat "$LOCKFILE")
    if kill -0 "$PID" 2>/dev/null; then
        log "Previous backup still running (PID $PID), skipping this tick"
        exit 0
    fi
    log "Stale lockfile from PID $PID — clearing"
fi
echo $$ > "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

log "=== 15-min backup starting ==="

# Pre-hook (pg_dump, n8n export, MCP health snapshot)
if [ -x /opt/amg/bin/restic-pre-hook.sh ]; then
    /opt/amg/bin/restic-pre-hook.sh || log "WARN: pre-hook partial"
fi

# Tier 1 paths (15-min critical state)
# Paths are what EXISTS; missing paths are silently skipped by restic. Review
# periodically against DR plan §2 to catch drift.
RESTIC_PATHS=(
    /opt/amg-mcp-server
    /opt/amg-governance
    /opt/amg-security
    /opt/amg-backups/supabase-latest.sql
    /opt/amg-backups/n8n-workflows-latest.json
    /opt/amg-backups/mcp-health-latest.json
    /etc/amg
    /etc/caddy
    /etc/fail2ban
    /opt/titan-bot
    /opt/n8n-data
    /var/log/amg
    /root/.ssh
)

# Filter to existing paths only
EXISTING=()
for p in "${RESTIC_PATHS[@]}"; do
    if [ -e "$p" ]; then EXISTING+=("$p"); fi
done

if [ ${#EXISTING[@]} -eq 0 ]; then
    log "ERROR: no backup paths exist on this host. Check DR plan §2."
    exit 2
fi

# Main backup
if restic backup "${EXISTING[@]}" \
    --exclude='node_modules' \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --tag "tier1-15min" \
    2>>"$LOG"; then
    log "restic backup OK (paths: ${#EXISTING[@]})"
else
    log "ERROR: restic backup failed (exit $?)"
    exit 3
fi

# Post-hook (integrity check, retention prune, heartbeat)
if [ -x /opt/amg/bin/restic-post-hook.sh ]; then
    /opt/amg/bin/restic-post-hook.sh || log "WARN: post-hook partial"
fi

log "=== 15-min backup complete ==="
