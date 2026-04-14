#!/bin/bash
# ssh-safeguard.sh — POST-LOCKOUT FAIL2BAN/UFW SAFEGUARD (HARDENED)
#
# Original version (archived in git history) was auto-run with no mitigations.
# This hardened version (2026-04-14) enforces all 8 mitigations required by
# the lockout-risk gate (CLAUDE.md §P10 + carryover 2026-04-14):
#
#   1. Requires 2+ active SSH sessions (escape hatch)
#   2. Requires --i-understand-lockout-risk flag (explicit acknowledgement)
#   3. Requires --apply OR --dry-run (no implicit default)
#   4. Backs up prior state before any write
#   5. Schedules auto-revert via `at now + 10 min` before any write
#   6. Hardened IP detection: $SSH_CLIENT primary, `last` fallback,
#      private-range rejection unless --allow-private
#   7. Full logging to /var/log/amg/ssh-safeguard.log
#   8. Versioned canonical snapshots (not overwrite)
#
# Lockout-risk gate: all 8 mitigations required BEFORE any firewall/fail2ban write.
# No self-healing. One-shot only. Not registered as systemd unit or cron.
#
# Companion: bin/ssh-safeguard-keep.sh — cancels auto-revert after verified OK.

set -euo pipefail

# ============================================================
# Constants
# ============================================================
SCRIPT_NAME="ssh-safeguard"
LOG_DIR="/var/log/amg"
LOG_FILE="${LOG_DIR}/${SCRIPT_NAME}.log"
BACKUP_ROOT="/var/backups/amg-ssh-safeguard"
TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"
CANONICAL_DIR="/etc/amg"
WHITELIST_FILE="/etc/fail2ban/jail.d/whitelist.conf"
REVERT_TOKEN_FILE="${BACKUP_DIR}/pending-revert.token"
AT_QUEUE="a"   # Use `at -q a` for our jobs

# ============================================================
# Flags
# ============================================================
MODE=""                    # "apply" or "dry-run"
ACKNOWLEDGE_RISK=false
ALLOW_PRIVATE_IP=false
YES_MODE=false
EXPECTED_IP=""             # Optional --expected-ip override

# ============================================================
# Helpers
# ============================================================
log() {
    local msg="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
    echo "$msg"
    if [[ -w "$LOG_DIR" ]] || [[ -w "$(dirname "$LOG_FILE")" ]]; then
        echo "$msg" | sudo tee -a "$LOG_FILE" >/dev/null 2>&1 || true
    fi
}

die() {
    log "FATAL: $*"
    exit 1
}

usage() {
    cat <<EOF
Usage: $0 {--dry-run | --apply} --i-understand-lockout-risk [OPTIONS]

Required:
  --dry-run                      Show proposed changes; make no writes.
  --apply                        Apply changes (requires all mitigations).
  --i-understand-lockout-risk    Explicit risk acknowledgement. Mandatory.

Optional:
  --expected-ip X.X.X.X          Verify detected IP matches this. Safety belt.
  --allow-private                Allow private-range IPs (10/8, 172.16/12, 192.168/16).
                                 Default: rejects private IPs to prevent whitelisting
                                 a NAT gateway instead of the real client.
  --yes                          Skip interactive confirmation prompt.
  --help                         Show this help.

Mitigations enforced:
  - Requires 2+ active SSH sessions (escape hatch)
  - Backs up current state to ${BACKUP_ROOT}/<timestamp>/ before any write
  - Schedules auto-revert via \`at now + 10 min\` (cancel with bin/ssh-safeguard-keep.sh)
  - Versioned canonical snapshot (no overwrite)

Companion:
  bin/ssh-safeguard-keep.sh      Cancel pending auto-revert when verified OK.
EOF
}

# ============================================================
# Arg parsing
# ============================================================
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)                      MODE="dry-run"; shift ;;
        --apply)                        MODE="apply"; shift ;;
        --i-understand-lockout-risk)    ACKNOWLEDGE_RISK=true; shift ;;
        --allow-private)                ALLOW_PRIVATE_IP=true; shift ;;
        --yes)                          YES_MODE=true; shift ;;
        --expected-ip)                  EXPECTED_IP="$2"; shift 2 ;;
        --help|-h)                      usage; exit 0 ;;
        *)                              die "Unknown arg: $1 (see --help)" ;;
    esac
done

[[ -z "$MODE" ]] && { usage; die "Must pass --dry-run or --apply"; }
[[ "$ACKNOWLEDGE_RISK" != "true" ]] && die "Must pass --i-understand-lockout-risk"

# ============================================================
# GUARD 1 — Require root
# ============================================================
[[ $EUID -eq 0 ]] || die "Must run as root (try: sudo $0 ...)"

# ============================================================
# GUARD 2 — Escape hatch: require 2+ active SSH sessions
# ============================================================
SSH_SESSIONS=$(who | awk '$0 ~ /pts/' | wc -l)
if [[ "$SSH_SESSIONS" -lt 2 ]]; then
    log "ABORT: only ${SSH_SESSIONS} SSH session(s) detected."
    log "       Required: at least 2 (this + independent escape-hatch)."
    log "       Open a second SSH session from a different terminal BEFORE retrying."
    exit 10
fi
log "GUARD: ${SSH_SESSIONS} SSH sessions active (escape hatch confirmed)."

# ============================================================
# GUARD 3 — Hardened IP detection
# ============================================================
detect_ip() {
    local ip=""

    # Primary: $SSH_CLIENT (space-separated: "client_ip client_port server_port")
    if [[ -n "${SSH_CLIENT:-}" ]]; then
        ip=$(echo "$SSH_CLIENT" | awk '{print $1}')
    fi

    # Fallback: last -i -n 1 <user>
    if [[ -z "$ip" ]]; then
        local invoking_user="${SUDO_USER:-$USER}"
        ip=$(last -i -n 1 "$invoking_user" 2>/dev/null | head -1 | awk '{print $3}')
    fi

    # Last resort: who am i (weakest, often blank under sudo)
    if [[ -z "$ip" ]]; then
        ip=$(who am i 2>/dev/null | awk '{print $NF}' | tr -d '()')
    fi

    echo "$ip"
}

is_private_ip() {
    local ip="$1"
    [[ "$ip" =~ ^10\. ]] && return 0
    [[ "$ip" =~ ^192\.168\. ]] && return 0
    [[ "$ip" =~ ^172\.(1[6-9]|2[0-9]|3[01])\. ]] && return 0
    [[ "$ip" =~ ^127\. ]] && return 0
    return 1
}

DETECTED_IP=$(detect_ip)
[[ -z "$DETECTED_IP" ]] && die "Could not detect connecting IP. Pass --expected-ip X.X.X.X explicitly."

# Validate IPv4 shape
if [[ ! "$DETECTED_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    die "Detected IP '${DETECTED_IP}' does not match IPv4 shape. Pass --expected-ip explicitly."
fi

if is_private_ip "$DETECTED_IP" && [[ "$ALLOW_PRIVATE_IP" != "true" ]]; then
    die "Detected IP '${DETECTED_IP}' is private-range. Would whitelist NAT gateway instead of real client. Pass --allow-private to override (only if you understand)."
fi

if [[ -n "$EXPECTED_IP" ]] && [[ "$DETECTED_IP" != "$EXPECTED_IP" ]]; then
    die "Detected IP '${DETECTED_IP}' does not match --expected-ip '${EXPECTED_IP}'. Aborting out of caution."
fi

log "GUARD: detected IP = ${DETECTED_IP}"

# ============================================================
# Confirmation prompt (unless --yes)
# ============================================================
if [[ "$MODE" == "apply" ]] && [[ "$YES_MODE" != "true" ]]; then
    echo
    echo "About to APPLY changes:"
    echo "  Whitelist IP:   ${DETECTED_IP}"
    echo "  fail2ban:       /etc/fail2ban/jail.d/whitelist.conf (new/updated)"
    echo "  UFW:            allow 2222/tcp (if missing)"
    echo "  Canonical:      /etc/amg/ufw-canonical-rules-${TIMESTAMP}.txt"
    echo "  Auto-revert:    scheduled at now + 10 min (cancel: bin/ssh-safeguard-keep.sh)"
    echo
    read -rp "Proceed? Type exactly 'APPLY' to continue: " CONFIRM
    [[ "$CONFIRM" == "APPLY" ]] || die "Confirmation not given; aborting."
fi

# ============================================================
# Backup current state (both modes — dry-run prints backup path)
# ============================================================
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
log "BACKUP DIR: ${BACKUP_DIR}"

if [[ -f "$WHITELIST_FILE" ]]; then
    cp -a "$WHITELIST_FILE" "${BACKUP_DIR}/whitelist.conf.pre" || die "Failed to back up whitelist.conf"
else
    : > "${BACKUP_DIR}/whitelist.conf.pre"   # touch marker; file was absent
    echo "__ABSENT__" > "${BACKUP_DIR}/whitelist.conf.pre.marker"
fi

mkdir -p "$CANONICAL_DIR"
if [[ -f "${CANONICAL_DIR}/ufw-canonical-rules.txt" ]]; then
    cp -a "${CANONICAL_DIR}/ufw-canonical-rules.txt" "${BACKUP_DIR}/ufw-canonical-rules.txt.pre"
fi

# Dump current UFW status + fail2ban ignoreip for audit trail
ufw status numbered > "${BACKUP_DIR}/ufw-status-before.txt" 2>/dev/null || true
fail2ban-client get sshd ignoreip > "${BACKUP_DIR}/fail2ban-ignoreip-before.txt" 2>/dev/null || true

# ============================================================
# Compute proposed new state
# ============================================================
NEW_WHITELIST_CONTENT="[DEFAULT]
ignoreip = 127.0.0.1/8 ::1 ${DETECTED_IP} 2607:fb90:6880::/48
"

# ============================================================
# DRY-RUN: show diff, exit
# ============================================================
if [[ "$MODE" == "dry-run" ]]; then
    log "DRY-RUN: no changes applied."
    echo
    echo "=== Proposed whitelist.conf diff ==="
    if [[ -s "${BACKUP_DIR}/whitelist.conf.pre" ]]; then
        diff -u "${BACKUP_DIR}/whitelist.conf.pre" <(echo "$NEW_WHITELIST_CONTENT") || true
    else
        echo "(current file absent; would create with content:)"
        echo "$NEW_WHITELIST_CONTENT"
    fi
    echo
    echo "=== UFW 2222/tcp allow needed? ==="
    if ufw status | grep -q "2222.*ALLOW"; then
        echo "Already present. No UFW change."
    else
        echo "Would add: ufw allow 2222/tcp"
    fi
    echo
    echo "=== Canonical snapshot target ==="
    echo "${CANONICAL_DIR}/ufw-canonical-rules-${TIMESTAMP}.txt (new, symlinked from ufw-canonical-rules.txt)"
    echo
    log "DRY-RUN complete. Backup dir created for audit: ${BACKUP_DIR}"
    exit 0
fi

# ============================================================
# APPLY MODE — schedule auto-revert FIRST, then write
# ============================================================
log "APPLY: scheduling auto-revert in 10 minutes..."

# Create revert script inside backup dir
REVERT_SCRIPT="${BACKUP_DIR}/revert.sh"
cat > "$REVERT_SCRIPT" <<REVERT_EOF
#!/bin/bash
# Auto-revert for ssh-safeguard ${TIMESTAMP}
# Fires unless bin/ssh-safeguard-keep.sh is run first.
set -e
BK="${BACKUP_DIR}"
LOG="${LOG_FILE}"

log_r() { echo "[\$(date -u +%FT%TZ)] [auto-revert ${TIMESTAMP}] \$*" | tee -a "\$LOG"; }

log_r "AUTO-REVERT FIRING"

if [[ -f "\$BK/whitelist.conf.pre.marker" ]]; then
    rm -f "${WHITELIST_FILE}"
    log_r "Restored: whitelist.conf deleted (was absent before)"
else
    cp -a "\$BK/whitelist.conf.pre" "${WHITELIST_FILE}"
    log_r "Restored: ${WHITELIST_FILE} from pre-backup"
fi

systemctl reload fail2ban
log_r "fail2ban reloaded"

if [[ -f "\$BK/ufw-canonical-rules.txt.pre" ]]; then
    cp -a "\$BK/ufw-canonical-rules.txt.pre" "${CANONICAL_DIR}/ufw-canonical-rules.txt"
    log_r "Restored: ufw-canonical-rules.txt from pre-backup"
fi

rm -f "${REVERT_TOKEN_FILE}"
log_r "AUTO-REVERT COMPLETE"
REVERT_EOF
chmod 700 "$REVERT_SCRIPT"

# Token file — ssh-safeguard-keep.sh deletes this to cancel
touch "$REVERT_TOKEN_FILE"

# Schedule via `at`
if ! command -v at >/dev/null 2>&1; then
    rm -f "$REVERT_TOKEN_FILE"
    die "\`at\` command not available. Install atd (apt install at) and start atd.service, or do not proceed."
fi

AT_JOB_ID=$(echo "bash ${REVERT_SCRIPT}" | at -q "${AT_QUEUE}" "now + 10 minutes" 2>&1 | awk '/^job/ {print $2}')
[[ -n "$AT_JOB_ID" ]] || { rm -f "$REVERT_TOKEN_FILE"; die "Failed to schedule auto-revert via at"; }

echo "$AT_JOB_ID" > "${BACKUP_DIR}/at-job-id"
log "Auto-revert scheduled: at job #${AT_JOB_ID}, fires in 10 min."

# ============================================================
# Now actually apply changes
# ============================================================
log "APPLY: writing new whitelist.conf..."
echo "$NEW_WHITELIST_CONTENT" > "$WHITELIST_FILE"
chmod 0644 "$WHITELIST_FILE"

log "APPLY: reloading fail2ban..."
systemctl reload fail2ban

log "APPLY: unbanning ${DETECTED_IP}..."
fail2ban-client unban "${DETECTED_IP}" 2>/dev/null || true

log "APPLY: checking UFW 2222/tcp..."
if ! ufw status | grep -q "2222.*ALLOW"; then
    ufw allow 2222/tcp
    log "APPLY: UFW added 2222/tcp allow"
else
    log "APPLY: UFW 2222/tcp already present, skipped"
fi

log "APPLY: versioned canonical snapshot..."
NEW_SNAPSHOT="${CANONICAL_DIR}/ufw-canonical-rules-${TIMESTAMP}.txt"
ufw status numbered > "$NEW_SNAPSHOT"
sha256sum "$NEW_SNAPSHOT" | cut -d' ' -f1 > "${NEW_SNAPSHOT}.sha256"
ln -sf "$NEW_SNAPSHOT" "${CANONICAL_DIR}/ufw-canonical-rules.txt"
ln -sf "${NEW_SNAPSHOT}.sha256" "${CANONICAL_DIR}/ufw-canonical-rules.sha256"

# Prune: keep last 30 snapshots
find "$CANONICAL_DIR" -maxdepth 1 -name 'ufw-canonical-rules-*.txt' -type f \
    | sort -r | tail -n +31 | xargs -r rm -f
find "$CANONICAL_DIR" -maxdepth 1 -name 'ufw-canonical-rules-*.txt.sha256' -type f \
    | sort -r | tail -n +31 | xargs -r rm -f

log "APPLY: verification..."
systemctl status sshd --no-pager | head -3 | tee -a "$LOG_FILE"
ss -tlnp | grep 2222 | tee -a "$LOG_FILE" || true
fail2ban-client get sshd ignoreip | tee -a "$LOG_FILE"

echo
log "===================================================================="
log "SSH-SAFEGUARD APPLIED. AUTO-REVERT WILL FIRE IN 10 MINUTES."
log "===================================================================="
log ""
log "If SSH still works from Mac after this, run on VPS:"
log "  sudo bin/ssh-safeguard-keep.sh ${TIMESTAMP}"
log ""
log "Or just: sudo bin/ssh-safeguard-keep.sh  (auto-detects latest)"
log ""
log "If SSH breaks, auto-revert will restore state in 10 min."
log "Backup dir: ${BACKUP_DIR}"
log "At job id:  ${AT_JOB_ID}"
log "===================================================================="

exit 0
