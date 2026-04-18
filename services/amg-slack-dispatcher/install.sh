#!/usr/bin/env bash
# install.sh — idempotent installer for amg-slack-dispatcher on VPS.
# Usage (run on VPS as root):
#   bash /opt/titan-harness/services/amg-slack-dispatcher/install.sh
#
# Installs:
#   /opt/amg-slack-dispatcher/dispatcher.py
#   /etc/systemd/system/amg-slack-dispatcher.service
#   /usr/local/bin/slack-dispatch
#   /etc/amg/slack-dispatcher.env (created with defaults if absent; preserved if exists)
#   /var/lib/amg-slack-dispatcher/ (state dir)
#
# Enables + starts the service.
set -euo pipefail

HARNESS_DIR="${HARNESS_DIR:-/opt/titan-harness}"
SRC_DIR="$HARNESS_DIR/services/amg-slack-dispatcher"

install -d -m 0755 /opt/amg-slack-dispatcher
install -m 0755 "$SRC_DIR/dispatcher.py" /opt/amg-slack-dispatcher/dispatcher.py

install -d -m 0755 /var/lib/amg-slack-dispatcher

install -d -m 0755 /etc/amg
if [[ ! -f /etc/amg/slack-dispatcher.env ]]; then
  cat > /etc/amg/slack-dispatcher.env <<'EOF'
# amg-slack-dispatcher config
# Source Slack webhook + Ntfy topic from existing security-watchdog.env or mcp-server.env at install time.

# Required:
SLACK_WEBHOOK_URL=""
NTFY_TOPIC="amg-sec-e5e9b77d"

# Optional (defaults shown):
# SLACK_DAILY_CAP=50
# SLACK_PER_SOURCE_CAP=10
# SLACK_MONTHLY_CAP=500
# DEDUP_WINDOW_SEC=600
# MCP_TAG_CHECK_INTERVAL=60
# SLACK_DISPATCHER_PORT=9876

# Supabase (for maintenance-mode-active MCP tag check):
SUPABASE_URL=""
SUPABASE_SERVICE_ROLE_KEY=""
EOF
  chmod 0600 /etc/amg/slack-dispatcher.env
  echo "[install] created /etc/amg/slack-dispatcher.env — EDIT to populate SLACK_WEBHOOK_URL + SUPABASE_*"
fi

# Try to auto-populate SLACK_WEBHOOK_URL from existing security-watchdog.env if unset
if ! grep -qE '^SLACK_WEBHOOK_URL="[^"]+' /etc/amg/slack-dispatcher.env 2>/dev/null; then
  existing=$(grep -hE '^SLACK_SECURITY_WEBHOOK=|^SLACK_WATCHDOG_WEBHOOK=' /etc/amg/*.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"')
  if [[ -n "$existing" ]]; then
    sed -i "s|^SLACK_WEBHOOK_URL=.*|SLACK_WEBHOOK_URL=\"${existing}\"|" /etc/amg/slack-dispatcher.env
    echo "[install] auto-populated SLACK_WEBHOOK_URL from existing watchdog webhook"
  fi
fi

# Try to auto-populate Supabase from mcp-server.env
if ! grep -qE '^SUPABASE_URL="[^"]+' /etc/amg/slack-dispatcher.env 2>/dev/null; then
  sb_url=$(grep -hE '^SUPABASE_URL=' /etc/amg/mcp-server.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"')
  sb_key=$(grep -hE '^SUPABASE_SERVICE_ROLE_KEY=' /etc/amg/mcp-server.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"')
  if [[ -n "$sb_url" ]]; then
    sed -i "s|^SUPABASE_URL=.*|SUPABASE_URL=\"${sb_url}\"|" /etc/amg/slack-dispatcher.env
  fi
  if [[ -n "$sb_key" ]]; then
    sed -i "s|^SUPABASE_SERVICE_ROLE_KEY=.*|SUPABASE_SERVICE_ROLE_KEY=\"${sb_key}\"|" /etc/amg/slack-dispatcher.env
  fi
fi

install -m 0755 "$SRC_DIR/slack-dispatch.sh" /usr/local/bin/slack-dispatch

install -m 0644 "$SRC_DIR/amg-slack-dispatcher.service" /etc/systemd/system/amg-slack-dispatcher.service

systemctl daemon-reload
systemctl enable --now amg-slack-dispatcher.service

sleep 1
systemctl is-active amg-slack-dispatcher.service && echo "[install] service active"

# Health check
curl -sS --max-time 3 http://127.0.0.1:9876/health || echo "[install] health check FAILED"
echo
echo "[install] done"
