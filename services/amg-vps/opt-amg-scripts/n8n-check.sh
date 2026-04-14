#!/bin/bash
# /opt/amg/scripts/n8n-check.sh — DELTA-B fail-closed patch (2026-04-14)
# Canonical source: ~/titan-harness/services/amg-vps/opt-amg-scripts/n8n-check.sh
#
# Compound check: docker container n8n-n8n-1 must be running AND HTTP 200 on
# /healthz. Both must pass or exit 1.
#
# DELTA-B scope: the pre-DELTA-B version used docker check only as a fallback
# after HTTP failed — so if curl returned 200 from any service bound to :5678
# (stale cache, imposter, future misconfig), the script returned PASS without
# verifying the n8n container was actually the responder. This version makes
# docker-inspect the primary truth source.
#
# Recovery: if container is running but HTTP is stale, docker restart (safe —
# re-creates same port bindings, no :5678 conflict risk). If container is
# down, exit 1 (watchdog escalates Tier 2).
#
# See plans/deployments/DEPLOY_HEAL_SCRIPTS_v1_2026-04-14.md for deploy
# history and rollback.

set -euo pipefail
LOCK="/var/lock/amg-n8n.lock"
CONTAINER="n8n-n8n-1"

# Hold mechanism — respect operator suppression
if [[ -f /opt/amg/holds/n8n.hold ]]; then
  AGE=$(( $(date +%s) - $(stat -c %Y /opt/amg/holds/n8n.hold) ))
  if [[ $AGE -lt 7200 ]]; then
    echo "HOLD_ACTIVE: n8n hold (${AGE}s old), skipping"
    exit 0
  fi
fi

# Single-instance lock
exec 200>"$LOCK"
flock -n 200 || { echo "LOCK_SKIP"; exit 0; }

DOCKER_OK=false
HTTP_OK=false

# Docker container must be running (primary truth source)
if docker inspect --format='{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q true; then
  DOCKER_OK=true
fi

# HTTP health endpoint must respond 200
HTTP=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:5678/healthz 2>/dev/null || echo "000")
[[ "$HTTP" == "200" ]] && HTTP_OK=true

if [[ "$DOCKER_OK" == "true" && "$HTTP_OK" == "true" ]]; then
  echo "PASS: n8n healthy (container=running, http=200)"
  exit 0
fi

# Recovery: container up but HTTP stale → restart container
if [[ "$DOCKER_OK" == "true" && "$HTTP_OK" == "false" ]]; then
  echo "WARN: container up but HTTP=$HTTP — restarting $CONTAINER"
  docker restart "$CONTAINER" >/dev/null 2>&1 || true
  sleep 15
  HTTP=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:5678/healthz 2>/dev/null || echo "000")
  if [[ "$HTTP" == "200" ]]; then
    echo "RECOVERED: n8n HTTP=200 post-restart"
    exit 0
  fi
fi

echo "FAIL: compound check (docker_ok=$DOCKER_OK http_ok=$HTTP_OK http_code=$HTTP)"
exit 1
