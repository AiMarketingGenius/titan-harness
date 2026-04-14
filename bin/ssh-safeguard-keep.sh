#!/bin/bash
# ssh-safeguard-keep.sh — cancel the pending auto-revert for ssh-safeguard.
#
# Run this from the VPS AFTER verifying SSH still works from Mac following
# an `ssh-safeguard.sh --apply` run. If you don't run this within 10 minutes
# of apply, the scheduled `at` job will fire and restore prior state.
#
# Usage:
#   sudo bin/ssh-safeguard-keep.sh                # auto-detect latest pending
#   sudo bin/ssh-safeguard-keep.sh 20260414-181500  # specific timestamp
#
# Lockout-risk gate: all 5 = NO. Only removes a pending `at` job and a
# token file. Does NOT touch sshd/UFW/fail2ban configuration.

set -euo pipefail

BACKUP_ROOT="/var/backups/amg-ssh-safeguard"
LOG_FILE="/var/log/amg/ssh-safeguard.log"

[[ $EUID -eq 0 ]] || { echo "ERROR: must run as root" >&2; exit 1; }

log() {
    local msg="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [keep] $*"
    echo "$msg"
    [[ -w "$(dirname "$LOG_FILE")" ]] && echo "$msg" >> "$LOG_FILE"
}

TIMESTAMP="${1:-}"

if [[ -z "$TIMESTAMP" ]]; then
    # Auto-detect: find most recent backup dir with a pending revert token
    TIMESTAMP=$(find "$BACKUP_ROOT" -maxdepth 2 -name 'pending-revert.token' -type f 2>/dev/null \
                | sort -r | head -1 | awk -F/ '{print $(NF-1)}')
    if [[ -z "$TIMESTAMP" ]]; then
        log "No pending ssh-safeguard revert found. Nothing to cancel."
        exit 0
    fi
    log "Auto-detected pending revert: ${TIMESTAMP}"
fi

BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"
TOKEN_FILE="${BACKUP_DIR}/pending-revert.token"
AT_JOB_ID_FILE="${BACKUP_DIR}/at-job-id"

if [[ ! -d "$BACKUP_DIR" ]]; then
    log "ERROR: backup dir not found: ${BACKUP_DIR}"
    exit 2
fi

if [[ ! -f "$TOKEN_FILE" ]]; then
    log "No pending revert token (already kept or already fired): ${TOKEN_FILE}"
    exit 0
fi

if [[ -f "$AT_JOB_ID_FILE" ]]; then
    AT_JOB_ID=$(cat "$AT_JOB_ID_FILE")
    if atq | awk '{print $1}' | grep -qx "$AT_JOB_ID"; then
        atrm "$AT_JOB_ID" && log "Cancelled at job #${AT_JOB_ID}"
    else
        log "At job #${AT_JOB_ID} not in queue (already ran or was removed). No action."
    fi
else
    log "WARNING: no at-job-id file. Scanning atq for orphaned jobs..."
    # Best-effort: list atq and let operator decide
    atq || true
fi

rm -f "$TOKEN_FILE"
log "Pending revert token removed: ${TOKEN_FILE}"
log "ssh-safeguard changes KEPT for timestamp ${TIMESTAMP}."
log "Backup dir retained at: ${BACKUP_DIR} (audit trail)"
