#!/bin/bash
# scripts/tla-path-4/bin/generate_hmac_secret.sh
#
# Generates a fresh 32-byte hex HMAC secret, stores it in macOS Keychain
# under service/account `titan-tla-nudge`, and prints it once for n8n env
# configuration. On VPS-side it's stored in /etc/amg/tla-nudge.env (root:root 0600)
# for the n8n container to mount.
#
# Usage: bash generate_hmac_secret.sh [--rotate]
# On --rotate: deletes existing Keychain entry + re-creates. Safe.

set -e

SERVICE="titan-tla-nudge"
ACCOUNT="titan-tla-nudge"

if [ "$1" = "--rotate" ]; then
  /usr/bin/security delete-generic-password -a "$ACCOUNT" -s "$SERVICE" 2>/dev/null || true
fi

# Refuse to overwrite without --rotate
if /usr/bin/security find-generic-password -a "$ACCOUNT" -s "$SERVICE" -w >/dev/null 2>&1; then
  echo "[WARN] Keychain entry already exists. Use --rotate to replace." >&2
  exit 2
fi

SECRET=$(openssl rand -hex 32)

/usr/bin/security add-generic-password \
  -a "$ACCOUNT" \
  -s "$SERVICE" \
  -w "$SECRET" \
  -T /Applications/Hammerspoon.app \
  -U

echo "HMAC secret generated + stored in Keychain ($SERVICE/$ACCOUNT)."
echo
echo "Paste the following into /etc/amg/tla-nudge.env on VPS (root:root 0600):"
echo "  TLA_NUDGE_HMAC_SECRET=$SECRET"
echo
echo "Also set TLA_NUDGE_ENDPOINT in n8n env to the reachable URL for this Mac"
echo "(if Mac is behind NAT, use Tailscale 100.x IP; if running n8n on same Mac,"
echo "default http://127.0.0.1:41710/nudge works)."
