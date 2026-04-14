#!/bin/bash
# restic-post-hook.sh — runs after every restic backup
# Integrity check (5% sampled), heartbeat emit, Tier 3 Slack alert on failure,
# retention prune (keep-last 96 / keep-hourly 48 / keep-daily 30 / keep-weekly 4)
set -euo pipefail

LOG="/var/log/amg/backup.log"
EVENTS="/var/log/amg/security-events.jsonl"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] POST-HOOK: $1" | tee -a "$LOG"; }

# Sanity: restic env must be inherited from caller (restic-backup-15min.sh)
: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY must be set by caller}"
: "${RESTIC_PASSWORD_FILE:?RESTIC_PASSWORD_FILE must be set by caller}"

log "starting"

# 1. Integrity check (5% sampled for speed, every backup)
if restic check --read-data-subset=5% 2>>"$LOG"; then
    log "integrity check PASSED"
    STATUS="pass"
else
    log "integrity check FAILED"
    STATUS="fail"
fi

# 2. Heartbeat
echo "{\"event\":\"backup_heartbeat\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"status\":\"$STATUS\"}" >> "$EVENTS"

# 3. Slack alert on failure (Tier 3 — DM Solon via admin webhook)
if [ "$STATUS" = "fail" ] && [ -n "${SLACK_WEBHOOK_ADMIN:-}" ]; then
    curl -sf -m 5 -X POST "$SLACK_WEBHOOK_ADMIN" \
        -H 'Content-Type: application/json' \
        -d "{\"text\":\"🔴 BACKUP INTEGRITY FAILURE at $(date -u). Check ${LOG}\"}" \
        2>/dev/null || log "WARN: Slack alert post failed"
fi

# 4. Retention prune (per DR plan §1)
log "retention prune starting"
if restic forget \
    --keep-last 96 \
    --keep-hourly 48 \
    --keep-daily 30 \
    --keep-weekly 4 \
    --prune 2>>"$LOG"; then
    log "retention prune OK"
else
    log "WARN: retention prune failed"
fi

# 5. Repo-size hard cap (safety valve — halt + alert if >50 GB)
if command -v restic >/dev/null 2>&1; then
    REPO_BYTES=$(restic stats --mode raw-data --json 2>/dev/null \
                 | grep -oE '"total_size":[0-9]+' | head -1 | cut -d: -f2 || echo "0")
    if [ -n "$REPO_BYTES" ] && [ "$REPO_BYTES" -gt $((50 * 1024 * 1024 * 1024)) ]; then
        log "🔴 REPO SIZE CAP EXCEEDED: $REPO_BYTES bytes (>50GB). Investigate."
        if [ -n "${SLACK_WEBHOOK_ADMIN:-}" ]; then
            curl -sf -m 5 -X POST "$SLACK_WEBHOOK_ADMIN" \
                -H 'Content-Type: application/json' \
                -d "{\"text\":\"🔴 Restic repo >50GB ($REPO_BYTES bytes). Investigate bloat.\"}" \
                2>/dev/null || true
        fi
    fi
fi

log "complete ($STATUS)"
