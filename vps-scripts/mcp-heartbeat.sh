#!/bin/bash
# mcp-heartbeat.sh — CT-0419-07 Step 2
#
# Writes a unique-nonce heartbeat decision to MCP (op_decisions), then reads it
# back via search, logs latency, and alerts on consecutive failures.
#
# Schedule: hourly via systemd timer mcp-heartbeat.timer.
# Companion: mcp-heartbeat-cleanup.service prunes heartbeats older than 7 days.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./mcp-common.sh
. "$SCRIPT_DIR/mcp-common.sh"

LOG_FILE="/opt/amg/logs/mcp-heartbeat.log"
STATE_FILE="/opt/amg/logs/mcp-heartbeat.state"
mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE" "$STATE_FILE"

# Rotate log weekly (>1MB)
if [ "$(wc -c <"$LOG_FILE")" -gt 1048576 ]; then
  mv "$LOG_FILE" "${LOG_FILE}.$(date -u +%Y%m%dT%H%M%SZ)"
  : >"$LOG_FILE"
  find "$(dirname "$LOG_FILE")" -maxdepth 1 -name 'mcp-heartbeat.log.*' -mtime +30 -delete 2>/dev/null || true
fi

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$LOG_FILE"; }

mcp_env_load
if ! mcp_require_env; then
  log "FAIL missing_env"
  exit 1
fi

NONCE="$(date -u +%Y%m%dT%H%M%SZ)-$$-$RANDOM"
TEXT="heartbeat:${NONCE}"
HOSTNAME_SHORT="$(hostname -s 2>/dev/null || hostname)"
TAGS="heartbeat,mcp-integrity,ct-0419-07"

START_NS=$(python3 -c 'import time; print(time.time_ns())')

# Write
if ! mcp_log_decision "$TEXT" "$TAGS" "hourly heartbeat from $HOSTNAME_SHORT" "titan"; then
  log "FAIL write_failed nonce=${NONCE}"
  echo "FAIL write" >>"$STATE_FILE"
  # escalate if >=2 consecutive fails
  FAILS=$(tail -n 3 "$STATE_FILE" | grep -c "FAIL" || echo 0)
  if [ "$FAILS" -ge 2 ]; then
    mcp_slack_or_log ":rotating_light: MCP heartbeat ${FAILS}x consecutive WRITE fails on ${HOSTNAME_SHORT}" "mcp-integrity,heartbeat-failure,ct-0419-07" || true
    if [ "$FAILS" -ge 5 ]; then
      mcp_flag_blocker "MCP heartbeat 5x consecutive write failures on ${HOSTNAME_SHORT} — memory loop integrity broken" "critical" "EOM" || true
    elif [ "$FAILS" -ge 2 ]; then
      mcp_flag_blocker "MCP heartbeat 2x consecutive write failures on ${HOSTNAME_SHORT}" "high" "EOM" || true
    fi
  fi
  exit 2
fi

# Wait briefly for indexing (Supabase PostgreSQL is strongly consistent, but give 500ms margin)
sleep 1

# Read back — verify roundtrip
FOUND=$(mcp_search_nonce "$NONCE" 2>/dev/null | head -1)
END_NS=$(python3 -c 'import time; print(time.time_ns())')
LATENCY_MS=$(( (END_NS - START_NS) / 1000000 ))

if [ "${FOUND:-0}" -lt 1 ]; then
  log "FAIL read_back_failed nonce=${NONCE} latency_ms=${LATENCY_MS}"
  echo "FAIL read" >>"$STATE_FILE"
  FAILS=$(tail -n 3 "$STATE_FILE" | grep -c "FAIL" || echo 0)
  if [ "$FAILS" -ge 2 ]; then
    mcp_slack_or_log ":rotating_light: MCP heartbeat ${FAILS}x consecutive READ-BACK fails on ${HOSTNAME_SHORT}" "mcp-integrity,heartbeat-failure,ct-0419-07" || true
    if [ "$FAILS" -ge 5 ]; then
      mcp_flag_blocker "MCP heartbeat 5x consecutive read-back failures on ${HOSTNAME_SHORT}" "critical" "EOM" || true
    else
      mcp_flag_blocker "MCP heartbeat 2x consecutive read-back failures on ${HOSTNAME_SHORT}" "high" "EOM" || true
    fi
  fi
  exit 3
fi

# Latency hard-cap: >10s = warning
if [ "$LATENCY_MS" -gt 10000 ]; then
  log "WARN high_latency_${LATENCY_MS}ms nonce=${NONCE}"
  mcp_slack_or_log ":warning: MCP heartbeat high latency ${LATENCY_MS}ms on ${HOSTNAME_SHORT}" "mcp-integrity,heartbeat-latency,ct-0419-07" || true
fi

log "OK nonce=${NONCE} latency_ms=${LATENCY_MS} found=${FOUND}"
echo "OK" >>"$STATE_FILE"

# Keep state file to last 20 lines
if [ "$(wc -l <"$STATE_FILE")" -gt 20 ]; then
  tail -n 20 "$STATE_FILE" >"${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"
fi

exit 0
