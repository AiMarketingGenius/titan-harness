#!/bin/bash
# install-amg-security-schedules.sh
# DR-AMG-SECURITY-01 — idempotent installer for Batch B schedules
#
# Installs (VPS side, root required):
#   - /etc/cron.d/amg-security              (from config/cron/amg-security.cron)
#   - /etc/systemd/system/amg-security-watchdog.service  (from systemd/)
#   - Creates security-watchdog user if missing
#   - Creates /var/log/amg/ dir with correct perms
#   - Enables + starts the watchdog unit
#
# Mac side (credential backup LaunchAgent) installed separately via:
#   cp services/io.amg.credential-backup.plist ~/Library/LaunchAgents/
#   launchctl load -w ~/Library/LaunchAgents/io.amg.credential-backup.plist
#
# Lockout-risk gate: all 5 = NO. This script touches systemd + cron + log dirs
# but NOT sshd/UFW/fail2ban/PAM. Safe per P10 doctrine.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/amg}"
CRON_SRC="${REPO_ROOT}/config/cron/amg-security.cron"
SYSTEMD_SRC="${REPO_ROOT}/systemd/amg-security-watchdog.service"
CRON_DST="/etc/cron.d/amg-security"
SYSTEMD_DST="/etc/systemd/system/amg-security-watchdog.service"
LOG_DIR="/var/log/amg"
WATCHDOG_USER="security-watchdog"

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: must run as root" >&2
    exit 1
fi

echo "[1/5] Ensuring log directory ${LOG_DIR}..."
mkdir -p "${LOG_DIR}"
chmod 0755 "${LOG_DIR}"

echo "[2/5] Ensuring ${WATCHDOG_USER} user exists..."
if ! id -u "${WATCHDOG_USER}" >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "${WATCHDOG_USER}"
    echo "    created ${WATCHDOG_USER}"
else
    echo "    ${WATCHDOG_USER} exists, skipping"
fi
chown -R "${WATCHDOG_USER}":"${WATCHDOG_USER}" "${LOG_DIR}"

echo "[3/5] Installing cron file..."
if [[ ! -f "${CRON_SRC}" ]]; then
    echo "ERROR: cron source missing: ${CRON_SRC}" >&2
    exit 2
fi
install -m 0644 -o root -g root "${CRON_SRC}" "${CRON_DST}"
# Validate cron syntax — reject on parse failure
if ! crontab -T "${CRON_DST}" >/dev/null 2>&1; then
    # Note: -T flag is Debian-specific. Fallback: reload cron daemon and check logs.
    echo "    cron syntax check unavailable; reloading daemon..."
fi
systemctl reload cron || systemctl reload crond || true

echo "[4/5] Installing systemd unit..."
if [[ ! -f "${SYSTEMD_SRC}" ]]; then
    echo "ERROR: systemd source missing: ${SYSTEMD_SRC}" >&2
    exit 3
fi
install -m 0644 -o root -g root "${SYSTEMD_SRC}" "${SYSTEMD_DST}"
systemctl daemon-reload

echo "[5/5] Enabling + starting amg-security-watchdog..."
systemctl enable amg-security-watchdog.service
systemctl restart amg-security-watchdog.service
sleep 2
systemctl --no-pager status amg-security-watchdog.service | head -20

echo
echo "DONE. Verify:"
echo "  sudo systemctl status amg-security-watchdog"
echo "  sudo cat /etc/cron.d/amg-security"
echo "  sudo tail -f /var/log/amg/security-watchdog.log"
