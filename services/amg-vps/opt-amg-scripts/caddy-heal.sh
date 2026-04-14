#!/bin/bash
# /opt/amg/scripts/caddy-heal.sh — DELTA-B-v2.1 (2026-04-14)
# Canonical source: ~/titan-harness/services/amg-vps/opt-amg-scripts/caddy-heal.sh
#
# Fixes applied after INC-2026-04-14-01 docker-caddy outage:
#
# Fix A (service presence check): host caddy.service is intentionally masked
# post-incident — systemctl is-active will always report inactive. Check the
# real serving layer instead: `docker inspect n8n-caddy-1 State.Running`.
#
# Fix B (pre-restart validate): NEVER docker restart until on-disk Caddyfile
# passes `caddy validate` via docker exec. A restart forces config re-parse;
# if the on-disk file is corrupt, restart → crash-loop → outage. Validate
# gates the recovery path. On validate fail: emit FAIL, preserve the running-
# but-stale state, escalate to Tier 2 (operator must fix on-disk file before
# healer can act).
#
# v2.1 change: localhost:443 probe dropped (unreliable — Caddy's TLS handshake
# requires SNI that curl to `localhost` can't supply cleanly). HTTP :80 return
# code 308 proves Caddy is running its auto-HTTPS redirect chain, which is
# sufficient evidence Caddy is alive. Full end-to-end HTTPS verification is
# the watchdog's external probe job (Uptime Robot), not this internal healer.
#
# Compound check:
#   1. docker inspect n8n-caddy-1 State.Running == true
#   2. HTTP :80 returns 200/301/302/307/308/404
# Both must pass or recovery path evaluates.
#
# Recovery path (only if DOCKER_OK + validate passes):
#   docker restart n8n-caddy-1 → re-check. Single-instance lock via flock.
#
# See plans/deployments/INCIDENT_CADDY_OUTAGE_2026-04-14.md for root cause
# and lessons that drove this version.

set -uo pipefail
LOCK="/var/lock/amg-caddy.lock"
CONTAINER="n8n-caddy-1"
ACCEPT_RE='^(200|301|302|307|308|404)$'
CADDYFILE_IN_CONTAINER="/etc/caddy/Caddyfile"

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

DOCKER_OK=false
HTTP_OK=false

# Check 1: container must be running (Fix A — the real serving layer)
if docker inspect --format='{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q true; then
  DOCKER_OK=true
fi

# Check 2: HTTP :80 responds with expected redirect/success code
HTTP=$(curl -s --connect-timeout 5 -o /dev/null -w "%{http_code}" http://localhost:80/ 2>/dev/null)
[[ -z "$HTTP" ]] && HTTP="000"
[[ "$HTTP" =~ $ACCEPT_RE ]] && HTTP_OK=true

if [[ "$DOCKER_OK" == "true" && "$HTTP_OK" == "true" ]]; then
  echo "PASS: Caddy healthy (container=running, http=$HTTP)"
  exit 0
fi

# Something is broken — evaluate recovery path with Fix B validate gate
echo "WARN: compound check failed (docker=$DOCKER_OK http=$HTTP_OK http_code=$HTTP)"

# If container is down entirely, do not auto-recover — operator required
# (automated compose-up would pull potentially bad Caddyfile from disk;
#  human action: ssh + cd /opt/n8n && docker compose up -d caddy)
if [[ "$DOCKER_OK" == "false" ]]; then
  echo "FAIL: container not running — recovery requires operator"
  exit 1
fi

# Container IS running but :80 is stale → validate on-disk config before restart
echo "INFO: container up but :80 stale — running pre-restart validate"
VALIDATE_OUT=$(timeout 10 docker exec "$CONTAINER" caddy validate --config "$CADDYFILE_IN_CONTAINER" --adapter caddyfile 2>&1)
VALIDATE_EXIT=$?

if [[ $VALIDATE_EXIT -ne 0 ]]; then
  echo "FAIL: caddy validate rejected on-disk Caddyfile (exit=$VALIDATE_EXIT)"
  echo "      preserving running-but-stale container state (DO NOT restart)"
  echo "      operator must fix /opt/n8n/Caddyfile before healer can act"
  echo "      validate output (trunc): $(echo "$VALIDATE_OUT" | head -c 400)"
  exit 1
fi

# Validate passed — safe to restart
echo "INFO: validate passed, restarting $CONTAINER"
docker restart "$CONTAINER" >/dev/null 2>&1 || true
sleep 10

# Re-probe after restart
HTTP=$(curl -s --connect-timeout 5 -o /dev/null -w "%{http_code}" http://localhost:80/ 2>/dev/null)
[[ -z "$HTTP" ]] && HTTP="000"
if [[ "$HTTP" =~ $ACCEPT_RE ]]; then
  echo "RECOVERED: Caddy healthy post-restart (http=$HTTP)"
  exit 0
fi

echo "FAIL: still unhealthy after restart (http=$HTTP)"
exit 1
