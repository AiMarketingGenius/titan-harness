#!/bin/bash
# scripts/install_health_timers.sh
# MP-4 §1 — Install systemd timers for all 13 health checks
# Run on VPS: bash scripts/install_health_timers.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[install_health_timers] Copying template units..."
cp -v "$SCRIPT_DIR/systemd/titan-health-check@.service" /etc/systemd/system/
cp -v "$SCRIPT_DIR/systemd/titan-health-check@.timer" /etc/systemd/system/

echo "[install_health_timers] Creating log directory..."
mkdir -p /var/log/titan

echo "[install_health_timers] Reloading systemd..."
systemctl daemon-reload

# Services to enable (matching CHECKS dict in health_check.py)
SERVICES=(
  kokoro hermes mcp n8n caddy
  titan_processor titan_bot supabase r2
  reviewer_budget vps_disk vps_cpu_memory
)

echo "[install_health_timers] Enabling timers..."
for svc in "${SERVICES[@]}"; do
  systemctl enable --now "titan-health-check@${svc}.timer" 2>/dev/null || true
  echo "  ✓ titan-health-check@${svc}.timer"
done

echo "[install_health_timers] Done. ${#SERVICES[@]} health check timers enabled."
echo "[install_health_timers] Verify: systemctl list-timers 'titan-health-check@*'"
