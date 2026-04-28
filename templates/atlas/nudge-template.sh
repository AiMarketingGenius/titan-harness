#!/usr/bin/env bash
# nudge-AGENT_NAME.sh — Atlas Factory CT-0427-97 baseline.
# Runs as AGENT_NAME via systemd oneshot when /home/AGENT_NAME/.claude/AGENT_NAME-wake.flag appears.
# Reads flag, archives + deletes it, signals the tmux supervisor session.
set -euo pipefail

AGENT='AGENT_NAME'
HOMEDIR="/home/${AGENT}"
CLAUDE_DIR="${HOMEDIR}/.claude"
LOG_DIR="${CLAUDE_DIR}/logs"
FLAG="${CLAUDE_DIR}/${AGENT}-wake.flag"
SUPERVISOR_LOG="${LOG_DIR}/${AGENT}-supervisor.log"
NUDGE_LOG="${LOG_DIR}/${AGENT}-nudge.log"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "${LOG_DIR}"

if [ ! -f "${FLAG}" ]; then
  echo "[${TS}] WARN no flag at ${FLAG}; spurious wake" | tee -a "${NUDGE_LOG}"
  exit 0
fi

FLAG_BODY="$(cat "${FLAG}" 2>/dev/null || echo '<empty>')"
echo "[${TS}] POLLED-WAKE flag=${FLAG} body=${FLAG_BODY}" | tee -a "${NUDGE_LOG}" "${SUPERVISOR_LOG}"

# Archive then delete so the .path unit can re-arm.
ARCHIVE="${LOG_DIR}/wake-archive-$(date -u +%Y%m%d).log"
{ echo "[${TS}] ${FLAG_BODY}"; } >> "${ARCHIVE}"
rm -f "${FLAG}"

# If a tmux session is running for this agent, send a no-op key so the supervisor
# loop wakes immediately instead of waiting on its sleep cycle.
if command -v tmux >/dev/null 2>&1 && tmux -L "${AGENT}-agent" has-session -t "${AGENT}-agent" 2>/dev/null; then
  tmux -L "${AGENT}-agent" send-keys -t "${AGENT}-agent" '' '' 2>/dev/null || true
fi

exit 0
