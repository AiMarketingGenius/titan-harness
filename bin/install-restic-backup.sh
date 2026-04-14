#!/bin/bash
# install-restic-backup.sh — deploy restic 15-min backup system on VPS
# Per plans/DR_BACKUP_SYSTEM_15MIN_RESTIC_R2.md Steps 1-11.
#
# Idempotent. Safe to re-run. Exits on any prereq gap with clear remediation.
#
# Lockout-risk gate: all 5 = NO. apt install + cron + log dir + restic init
# (writes to R2). No SSH/UFW/fail2ban/PAM touch.
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/amg}"
CRON_SRC="${REPO_ROOT}/config/cron/amg-restic-backup.cron"
CRON_DST="/etc/cron.d/amg-restic-backup"
LOG_DIR="/var/log/amg"
BACKUP_STAGE="/opt/amg-backups"
RESTIC_PASSWORD_FILE="/etc/amg/restic-password"

[[ $EUID -eq 0 ]] || { echo "ERROR: must run as root" >&2; exit 1; }

echo "[1/8] apt install restic..."
if ! command -v restic >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y restic
fi
restic version

echo "[2/8] Ensuring dirs + perms..."
mkdir -p "$LOG_DIR" "$BACKUP_STAGE"
chmod 0755 "$LOG_DIR"
chmod 0700 "$BACKUP_STAGE"

echo "[3/8] Checking prereq: /etc/amg/cloudflare.env with R2 creds..."
if [[ ! -f /etc/amg/cloudflare.env ]]; then
    cat <<EOF
ERROR: /etc/amg/cloudflare.env missing. Create with:

    CF_ACCOUNT_ID=<your-cloudflare-account-id>
    R2_ACCESS_KEY_ID=<r2-api-token-access-key>   # WRITE+LIST scoped, NO delete
    R2_SECRET_ACCESS_KEY=<r2-api-token-secret>

Create the R2 token at https://dash.cloudflare.com → R2 → Manage API Tokens.
Scope: amg-storage bucket, permissions Object Read/Write (no Delete).
EOF
    exit 2
fi
# shellcheck disable=SC1091
source /etc/amg/cloudflare.env
: "${CF_ACCOUNT_ID:?CF_ACCOUNT_ID missing in cloudflare.env}"
: "${R2_ACCESS_KEY_ID:?R2_ACCESS_KEY_ID missing}"
: "${R2_SECRET_ACCESS_KEY:?R2_SECRET_ACCESS_KEY missing}"

echo "[4/8] Generating restic password (if absent)..."
if [[ ! -f "$RESTIC_PASSWORD_FILE" ]]; then
    install -m 0600 -o root -g root /dev/null "$RESTIC_PASSWORD_FILE"
    openssl rand -base64 32 > "$RESTIC_PASSWORD_FILE"
    chmod 0400 "$RESTIC_PASSWORD_FILE"
    echo "    CREATED $RESTIC_PASSWORD_FILE — BACK IT UP IMMEDIATELY (see DR plan §8a)"
else
    echo "    exists, skipping"
fi

echo "[5/8] restic init (if repo empty)..."
export RESTIC_REPOSITORY="s3:https://${CF_ACCOUNT_ID}.r2.cloudflarestorage.com/amg-storage/restic-backups"
export RESTIC_PASSWORD_FILE
export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
if ! restic snapshots >/dev/null 2>&1; then
    restic init
    echo "    INITIALIZED $RESTIC_REPOSITORY"
else
    echo "    repo exists, skipping init"
fi

echo "[6/8] Installing cron..."
if [[ ! -f "$CRON_SRC" ]]; then
    echo "ERROR: cron source missing: $CRON_SRC" >&2
    exit 3
fi
install -m 0644 -o root -g root "$CRON_SRC" "$CRON_DST"
systemctl reload cron || systemctl reload crond || true

echo "[7/8] Making hook scripts executable..."
for f in "$REPO_ROOT/bin/restic-backup-15min.sh" \
         "$REPO_ROOT/bin/restic-pre-hook.sh" \
         "$REPO_ROOT/bin/restic-post-hook.sh"; do
    [ -f "$f" ] && chmod +x "$f"
done

echo "[8/8] Running first backup manually to verify R2 landing..."
if "$REPO_ROOT/bin/restic-backup-15min.sh"; then
    echo
    echo "✅ FIRST BACKUP SUCCEEDED. Verify on R2:"
    restic snapshots | tail -5
    echo
    echo "Cron will now run every 15 min. Tail: tail -f $LOG_DIR/backup.log"
else
    echo "❌ FIRST BACKUP FAILED. Check $LOG_DIR/backup.log" >&2
    exit 4
fi

echo
echo "DEPLOYMENT COMPLETE."
echo "Credential safety (DR plan §8a): back up $RESTIC_PASSWORD_FILE to at least 2 locations:"
echo "  1. R2 bucket amg-credentials-backup (GPG-encrypted, different key)"
echo "  2. Mac master credential doc (iCloud + FileVault)"
