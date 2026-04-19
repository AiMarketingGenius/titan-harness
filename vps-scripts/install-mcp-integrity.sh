#!/bin/bash
# install-mcp-integrity.sh — CT-0419-07 one-shot installer (run on VPS)
#
# Steps:
#   1. Generate age keypair (if not exists)
#   2. Create private amg-mcp-archive GitHub repo (if not exists)
#   3. Push scripts to /opt/amg/scripts/
#   4. Install systemd units
#   5. Enable + start timers
#
# Idempotent — safe to re-run.

set -eu

SCRIPT_SRC="${SCRIPT_SRC:-/opt/amg/scripts}"
REPO_OWNER="AiMarketingGenius"
REPO_NAME="amg-mcp-archive"

# ---- 1. age keypair ----
AGE_KEY_PRIV=/etc/amg/mcp-archive.age
AGE_KEY_PUB=/etc/amg/mcp-archive.age.pub
if [ ! -f "$AGE_KEY_PRIV" ]; then
  echo "[1] Generating age keypair..."
  umask 077
  age-keygen -o "$AGE_KEY_PRIV"
  age-keygen -y "$AGE_KEY_PRIV" > "$AGE_KEY_PUB"
  chmod 400 "$AGE_KEY_PRIV"
  chmod 444 "$AGE_KEY_PUB"
  chown root:root "$AGE_KEY_PRIV" "$AGE_KEY_PUB"
  echo "  priv: $AGE_KEY_PRIV (chmod 400)"
  echo "  pub:  $AGE_KEY_PUB (chmod 444)"
else
  echo "[1] age keypair already exists"
fi

# ---- 2. GitHub private repo ----
if gh repo view "${REPO_OWNER}/${REPO_NAME}" >/dev/null 2>&1; then
  echo "[2] GitHub repo ${REPO_OWNER}/${REPO_NAME} already exists"
else
  echo "[2] Creating private GitHub repo ${REPO_OWNER}/${REPO_NAME}..."
  gh repo create "${REPO_OWNER}/${REPO_NAME}" \
    --private \
    --description "CT-0419-07 age-encrypted MCP decision archive (L3 long-term store)" \
    --confirm 2>/dev/null || gh repo create "${REPO_OWNER}/${REPO_NAME}" --private --description "CT-0419-07 age-encrypted MCP decision archive (L3)"
fi

# ---- 3. Verify scripts present ----
for s in mcp-common.sh mcp-heartbeat.sh mcp-heartbeat-cleanup.sh mcp-archive-daily.sh mcp-archive-github.sh; do
  if [ ! -x "$SCRIPT_SRC/$s" ]; then
    echo "[3] FAIL: $SCRIPT_SRC/$s missing or not executable"
    exit 1
  fi
done
echo "[3] Scripts verified in $SCRIPT_SRC"

# ---- 4. systemd units ----
for unit in mcp-heartbeat.service mcp-heartbeat.timer mcp-heartbeat-cleanup.service mcp-heartbeat-cleanup.timer mcp-archive-daily.service mcp-archive-daily.timer mcp-archive-github.service mcp-archive-github.timer; do
  if [ ! -f "/etc/systemd/system/$unit" ]; then
    echo "[4] FAIL: /etc/systemd/system/$unit missing"
    exit 2
  fi
done
systemctl daemon-reload

# ---- 5. Enable + start timers ----
for t in mcp-heartbeat.timer mcp-heartbeat-cleanup.timer mcp-archive-daily.timer mcp-archive-github.timer; do
  systemctl enable --now "$t"
done
echo "[5] Timers enabled + active"

systemctl list-timers mcp-*.timer --no-pager

echo ""
echo "DONE. age pub key for reference:"
cat "$AGE_KEY_PUB"
