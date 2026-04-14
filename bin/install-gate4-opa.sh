#!/usr/bin/env bash
# bin/install-gate4-opa.sh
# Installer for Gate #4 v1.2. Deploys OPA policies + systemd + secrets.
#
# Usage:
#   bin/install-gate4-opa.sh --mac                      # Mac-side prep (test tools + secret stub)
#   bin/install-gate4-opa.sh --vps                      # VPS install (OPA binary + systemd units)
#   bin/install-gate4-opa.sh --vps --rotate-secret      # rotate gate4.secret on VPS
#   bin/install-gate4-opa.sh --install-opa              # attempt to install OPA binary on VPS
#   bin/install-gate4-opa.sh --test                     # run policy tests only

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DO_MAC=0; DO_VPS=0; ROTATE=0; INSTALL_OPA=0; ONLY_TEST=0
for a in "$@"; do
    case "$a" in
        --mac) DO_MAC=1 ;;
        --vps) DO_VPS=1 ;;
        --rotate-secret) ROTATE=1 ;;
        --install-opa) INSTALL_OPA=1 ;;
        --test) ONLY_TEST=1 ;;
        *) echo "unknown arg: $a" >&2; exit 2 ;;
    esac
done

if (( ONLY_TEST == 1 )); then
    exec "${REPO}/bin/test-policies.sh"
fi

# --- Mac prep ---
if (( DO_MAC == 1 )); then
    # Rego tests locally if opa available
    if command -v opa >/dev/null 2>&1; then
        "${REPO}/bin/test-policies.sh" || exit 1
    else
        echo "[install-gate4] opa binary not installed on Mac — skipping local tests."
        echo "                install via: brew install opa"
    fi
    # Stub secret on Mac (not used for gating, but for round-trip tests)
    MACSEC="$HOME/.amg/gate4.secret"
    if [[ ! -f "$MACSEC" ]] || (( ROTATE == 1 )); then
        mkdir -p "$(dirname "$MACSEC")"
        umask 077
        openssl rand -hex 32 > "$MACSEC"
        chmod 0400 "$MACSEC"
        echo "[install-gate4] Mac test secret written to $MACSEC"
    fi
fi

# --- VPS deploy ---
if (( DO_VPS == 1 )); then
    VPS="${AMG_VPS_HOST:-root@170.205.37.148}"
    PORT="${AMG_VPS_PORT:-2222}"
    KEY="${AMG_VPS_KEY:-$HOME/.ssh/id_ed25519_amg}"
    SSH=(-4 -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=accept-new)

    scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=accept-new \
        "$REPO/systemd/amg-opa-auto-revert.service" \
        "$REPO/systemd/amg-opa-auto-revert.timer" \
        "$VPS:/etc/systemd/system/"

    ssh "${SSH[@]}" "$VPS" bash -s -- "$ROTATE" "$INSTALL_OPA" <<'REMOTE'
set -euo pipefail
ROTATE="$1"; INSTALL_OPA="$2"
mkdir -p /etc/amg /var/log/amg
touch /var/log/amg/opa-decisions.jsonl /var/log/amg/opa-auto-revert.log /var/log/amg/opa-mode-changes.jsonl
chmod 0600 /var/log/amg/opa-*.log /var/log/amg/opa-*.jsonl 2>/dev/null || true
touch /etc/amg/gate4-ack-nonces.used; chmod 0600 /etc/amg/gate4-ack-nonces.used

if [[ "$ROTATE" == "1" ]] || [[ ! -s /etc/amg/gate4.secret ]]; then
    umask 077
    openssl rand -hex 32 > /etc/amg/gate4.secret
    chown root:root /etc/amg/gate4.secret
    chmod 0400 /etc/amg/gate4.secret
    echo "[install-gate4] VPS gate4.secret written"
fi

if [[ "$INSTALL_OPA" == "1" ]] && ! command -v opa >/dev/null 2>&1; then
    curl -fsSL -o /usr/local/bin/opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64_static
    chmod +x /usr/local/bin/opa
    echo "[install-gate4] OPA binary installed"
fi

systemctl daemon-reload
systemctl enable --now amg-opa-auto-revert.timer
systemctl status amg-opa-auto-revert.timer --no-pager | head -8
REMOTE
fi

echo "[install-gate4] done."
echo "  Next steps:"
echo "    1. bin/opa-deploy.sh --phase1-audit            (begin 24h audit)"
echo "    2. after 24h: bin/opa-deploy.sh --generate-observe-report"
echo "    3. bin/opa-confirm-enforce.sh --report <path>  (Solon typed ack)"
echo "    4. bin/opa-deploy.sh --consume-ack             (flip to enforce, 7d tail)"
