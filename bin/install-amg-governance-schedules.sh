#!/bin/bash
# install-amg-governance-schedules.sh
# DR-AMG-GOVERNANCE-01 — idempotent installer for governance crons
#
# Installs:
#   - /etc/cron.d/amg-governance  (from config/cron/amg-governance.cron)
#   - Creates /var/log/amg/ if missing
#
# Prereqs:
#   - sql/009 + sql/010 applied to Supabase (governance_retention_policy table exists)
#   - /etc/amg/supabase.env contains SUPABASE_DB_URL
#
# Lockout-risk gate: all 5 = NO. Cron + log dir only. No SSH/firewall/auth.
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/amg}"
CRON_SRC="${REPO_ROOT}/config/cron/amg-governance.cron"
CRON_DST="/etc/cron.d/amg-governance"
LOG_DIR="/var/log/amg"

[[ $EUID -eq 0 ]] || { echo "ERROR: must run as root" >&2; exit 1; }

echo "[1/3] Ensuring ${LOG_DIR}..."
mkdir -p "$LOG_DIR"
chmod 0755 "$LOG_DIR"

echo "[2/3] Checking prereq: /etc/amg/supabase.env..."
if [[ ! -f /etc/amg/supabase.env ]]; then
    echo "ERROR: /etc/amg/supabase.env missing — create with SUPABASE_DB_URL before installing" >&2
    exit 2
fi

echo "[3/3] Installing cron..."
if [[ ! -f "$CRON_SRC" ]]; then
    echo "ERROR: cron source missing: $CRON_SRC" >&2
    exit 3
fi
install -m 0644 -o root -g root "$CRON_SRC" "$CRON_DST"
systemctl reload cron || systemctl reload crond || true

echo
echo "DONE. Verify:"
echo "  sudo cat /etc/cron.d/amg-governance"
echo "  sudo tail -f /var/log/amg/governance-*.log"
echo
echo "REMINDER: apply sql/009 + sql/010 to Supabase before first cron tick,"
echo "          else retention cron will exit no-op (no policies found)."
