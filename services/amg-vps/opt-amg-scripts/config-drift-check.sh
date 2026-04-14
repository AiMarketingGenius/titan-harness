#!/bin/bash
# /opt/amg/scripts/config-drift-check.sh — DELTA-D (2026-04-14)
# Canonical source: ~/titan-harness/services/amg-vps/opt-amg-scripts/config-drift-check.sh
#
# Checks 6 production config files against expected SHAs (harness-tracked,
# deployed to /opt/amg/.sha256-expected.txt). Emits per-file drift events
# with appropriate tier. Read-only — does NOT auto-revert (drift may be
# legitimate edit; operator decides).
#
# Tier mapping:
#   Tier 2 (immediate Slack) — security-critical:
#     /etc/ssh/sshd_config
#     /etc/amg/ufw-canonical-commands.sh
#     /etc/fail2ban/jail.local
#     /etc/fail2ban/jail.d/whitelist.conf
#   Tier 1 (digest) — operational:
#     /opt/n8n/Caddyfile
#     /opt/n8n/docker-compose.yml
#
# Doctrine is NOT checked here — see doctrine-drift-check.sh (separate timer).

set -uo pipefail
EXPECTED_FILE="/opt/amg/.sha256-expected.txt"
LOG="/var/log/amg/watchdog.jsonl"

# Files to check + tier on drift
declare -A TIER_MAP=(
  ["/etc/ssh/sshd_config"]=2
  ["/etc/amg/ufw-canonical-commands.sh"]=2
  ["/etc/fail2ban/jail.local"]=2
  ["/etc/fail2ban/jail.d/whitelist.conf"]=2
  ["/opt/n8n/Caddyfile"]=1
  ["/opt/n8n/docker-compose.yml"]=1
)

ts() { date -u +%Y-%m-%dT%H:%M:%S.%3NZ; }

emit() {
  local event="$1" detail="$2" tier="$3"
  local escaped_detail="${detail//\"/\\\"}"
  echo "{\"ts\":\"$(ts)\",\"domain\":\"config_drift\",\"event\":\"$event\",\"detail\":\"$escaped_detail\",\"tier\":$tier,\"metrics\":{}}" >> "$LOG"
}

if [[ ! -f "$EXPECTED_FILE" ]]; then
  emit "EXPECTED_SHA_MISSING" "$EXPECTED_FILE absent — cannot verify any config drift" 2
  exit 1
fi

ANY_DRIFT=false

for F in "${!TIER_MAP[@]}"; do
  TIER="${TIER_MAP[$F]}"

  if [[ ! -f "$F" ]]; then
    emit "CONFIG_MISSING" "$F absent" "$TIER"
    ANY_DRIFT=true
    continue
  fi

  EXPECTED=$(grep -F "  $F" "$EXPECTED_FILE" 2>/dev/null | awk '{print $1}')
  if [[ -z "$EXPECTED" ]]; then
    emit "EXPECTED_SHA_NOT_LISTED" "$F not in $EXPECTED_FILE" 1
    continue
  fi

  ACTUAL=$(sha256sum "$F" | awk '{print $1}')

  if [[ "$ACTUAL" != "$EXPECTED" ]]; then
    emit "CONFIG_DRIFT" "$F expected=${EXPECTED:0:12}... actual=${ACTUAL:0:12}... — operator review required" "$TIER"
    ANY_DRIFT=true
  fi
done

if [[ "$ANY_DRIFT" == "false" ]]; then
  emit "CONFIG_SHA_ALL_OK" "all 6 tracked configs match expected SHAs" 0
  exit 0
fi

exit 1
