#!/usr/bin/env bash
# bin/install-gate2.sh
# Installer for Gate #2 v1.1. Local (Mac) usage by default; --vps to deploy
# the timer + secret on VPS.
#
# Usage:
#   bin/install-gate2.sh                     # create Mac secret only
#   bin/install-gate2.sh --vps               # deploy timer + service to VPS
#   bin/install-gate2.sh --vps --rotate-secret   # also rotate HMAC secret

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DO_VPS=0
ROTATE=0

for a in "$@"; do
  case "$a" in
    --vps) DO_VPS=1 ;;
    --rotate-secret) ROTATE=1 ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done

MAC_SECRET="$HOME/.amg/gate2.secret"
if [[ ! -f "$MAC_SECRET" ]] || (( ROTATE == 1 )); then
  mkdir -p "$(dirname "$MAC_SECRET")"
  umask 077
  openssl rand -hex 32 > "$MAC_SECRET"
  chmod 0400 "$MAC_SECRET"
  echo "[install-gate2] Mac secret written to $MAC_SECRET"
fi

if (( DO_VPS == 1 )); then
  VPS="${AMG_VPS_HOST:-root@170.205.37.148}"
  PORT="${AMG_VPS_PORT:-2222}"
  KEY="${AMG_VPS_KEY:-$HOME/.ssh/id_ed25519_amg}"
  SSH=(-4 -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=accept-new)

  echo "[install-gate2] deploying systemd units + secret to $VPS"
  scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=accept-new \
      "$REPO/systemd/amg-hypothesis-timer.service" \
      "$REPO/systemd/amg-hypothesis-timer.timer" \
      "$VPS:/etc/systemd/system/"

  SECRET_CONTENT="$(cat "$MAC_SECRET")"
  ssh "${SSH[@]}" "$VPS" bash -s -- "$SECRET_CONTENT" <<'REMOTE'
set -euo pipefail
secret="$1"
mkdir -p /etc/amg
umask 077
if [[ ! -s /etc/amg/gate2.secret ]] || [[ "$2" == "rotate" ]]; then
  echo -n "$secret" > /etc/amg/gate2.secret
  chown root:root /etc/amg/gate2.secret
  chmod 0400 /etc/amg/gate2.secret
  echo "[install-gate2] VPS gate2.secret installed"
fi
mkdir -p /var/log/amg
touch /var/log/amg/hypothesis-timer.log
chmod 0600 /var/log/amg/hypothesis-timer.log
systemctl daemon-reload
systemctl enable --now amg-hypothesis-timer.timer
systemctl status amg-hypothesis-timer.timer --no-pager | head -10
REMOTE
fi

echo "[install-gate2] done. Verify locally:"
echo "    bin/hypothesis-track.sh status"
