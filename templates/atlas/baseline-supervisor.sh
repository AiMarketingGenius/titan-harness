#!/usr/bin/env bash
# agent-supervisor.sh (BASELINE — CT-0427-97).
# Augmented v2 (CT-0427-98) replaces this body with cost-ledger + artifact-registry
# + amg_reviews handoff hooks. Until then this baseline polls for wake flags +
# logs the wake event so the systemd .path unit smoke test can verify.
#
# Invoke via: bash ~/.claude/agent-supervisor.sh AGENT_NAME
set -euo pipefail

AGENT="${1:-${USER:-unknown}}"
HOMEDIR="${HOME:-/home/${AGENT}}"
CLAUDE_DIR="${HOMEDIR}/.claude"
LOG_DIR="${CLAUDE_DIR}/logs"
FLAG="${CLAUDE_DIR}/${AGENT}-wake.flag"
LOG="${LOG_DIR}/${AGENT}-supervisor.log"

mkdir -p "${LOG_DIR}"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] SUPERVISOR UP v1 agent=${AGENT} pid=$$ host=$(hostname)" | tee -a "${LOG}"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Watching ${FLAG} (poll every 3s)" | tee -a "${LOG}"

# Poll. Real claim/cost/review work happens in v2 (CT-0427-98).
while true; do
  if [ -f "${FLAG}" ]; then
    BODY="$(cat "${FLAG}" 2>/dev/null || echo '<empty>')"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] POLLED-WAKE body=${BODY}" | tee -a "${LOG}"
    rm -f "${FLAG}"
  fi
  sleep 3
done
