#!/usr/bin/env bash
# deploy-amg-titanium.sh — sync opt-amg-titanium/ to VPS /opt/amg-titanium/
# + install systemd units + enable timers.
#
# One-shot for first deploy; idempotent thereafter.

set -euo pipefail

readonly REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly SRC="$REPO/opt-amg-titanium"
VPS_HOST="${VPS_HOST:-root@170.205.37.148}"

echo "[deploy-amg-titanium] syncing $SRC → $VPS_HOST:/opt/amg-titanium/"
rsync -avz --delete --exclude='proposals/' --exclude='*.log' \
  "$SRC/" "$VPS_HOST:/opt/amg-titanium/"

echo "[deploy-amg-titanium] installing systemd units"
ssh "$VPS_HOST" bash -s <<'VPS'
set -euo pipefail
install -m 644 /opt/amg-titanium/systemd/*.service /etc/systemd/system/
install -m 644 /opt/amg-titanium/systemd/*.timer   /etc/systemd/system/
chmod +x /opt/amg-titanium/*.sh
systemctl daemon-reload
systemctl enable --now amg-titanium-post-mortem.timer
systemctl enable --now amg-titanium-regression-probe.timer
systemctl enable --now amg-titanium-stale-sweeper.timer
systemctl list-timers amg-titanium-* --no-pager
VPS

echo "[deploy-amg-titanium] done"
