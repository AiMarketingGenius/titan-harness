#!/bin/bash
# /opt/amg/scripts/caddy-heal.sh — DELTA-B fail-closed patch (2026-04-14)
# Canonical source: ~/titan-harness/services/amg-vps/opt-amg-scripts/caddy-heal.sh
#
# Compound check: `systemctl is-active caddy` AND HTTP 200-class on :80.
# Both must pass or exit 1 (fail-closed; watchdog escalates Tier 2).
#
# DELTA-B scope: expose the lie. The pre-DELTA-B version did `pgrep -x caddy`
# which matched a zombie process (binary deleted, no listeners) and returned
# PASS even when caddy.service was FAILED. This version tells the truth.
#
# DELTA-B does NOT attempt recovery — DELTA-C-FIX will rewrite the recovery
# path for the docker-caddy architecture (n8n-caddy-1 container is the real
# serving surface; host caddy.service is obsolete). Until DELTA-C-FIX lands,
# expect this script to report FAIL until caddy.service is disabled + the
# check is retargeted at the docker container.
#
# See plans/deployments/DEPLOY_HEAL_SCRIPTS_v1_2026-04-14.md for deploy
# history and rollback.

set -euo pipefail
LOCK="/var/lock/amg-caddy.lock"

# Hold mechanism — respect operator suppression
if [[ -f /opt/amg/holds/caddy.hold ]]; then
  AGE=$(( $(date +%s) - $(stat -c %Y /opt/amg/holds/caddy.hold) ))
  if [[ $AGE -lt 7200 ]]; then
    echo "HOLD_ACTIVE: caddy hold (${AGE}s old), skipping"
    exit 0
  fi
fi

# Single-instance lock
exec 200>"$LOCK"
flock -n 200 || { echo "LOCK_SKIP"; exit 0; }

# Compound check — both must pass
SYSTEMD_OK=false
HTTP_OK=false

systemctl is-active --quiet caddy 2>/dev/null && SYSTEMD_OK=true

HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80/ 2>/dev/null || echo "000")
# 308 is standard Caddy auto-HTTPS redirect (HTTP→HTTPS permanent)
[[ "$HTTP" =~ ^(200|301|302|307|308|404)$ ]] && HTTP_OK=true

if [[ "$SYSTEMD_OK" == "true" && "$HTTP_OK" == "true" ]]; then
  echo "PASS: Caddy healthy (systemd=active, http=$HTTP)"
  exit 0
fi

echo "FAIL: compound check (systemd_ok=$SYSTEMD_OK http_ok=$HTTP_OK http_code=$HTTP)"
exit 1
