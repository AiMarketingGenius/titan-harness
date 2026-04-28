#!/usr/bin/env bash
# argus-atlas-agent-probe.sh — Atlas Factory CT-0428-recovery.
# Runs every 5 min via launchd (com.amg.argus-atlas-agent.plist).
# Inspects io.aimg.atlas-agent state; raises P1 alert on exit-non-zero or dead state.
# Same failure-class detection as Email Secretary 2026-04-16.
set -uo pipefail

UID_NUM="$(id -u)"
LABEL="io.aimg.atlas-agent"
LOG=/tmp/argus-atlas-agent.log
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

note() { printf '[%s] %s\n' "$TS" "$*" >> "$LOG"; }

PRINT_OUT="$(launchctl print "gui/${UID_NUM}/${LABEL}" 2>&1 || true)"
LAST_EXIT="$(printf '%s\n' "$PRINT_OUT" | awk -F'= ' '/last exit code/ {print $2; exit}' | tr -d ' ')"
STATE="$(printf '%s\n' "$PRINT_OUT" | awk -F'= ' '/^	state =/ {print $2; exit}' | tr -d ' ')"
PID="$(printf '%s\n' "$PRINT_OUT" | awk -F'= ' '/^	pid =/ {print $2; exit}' | tr -d ' ')"

note "STATE=${STATE:-unknown} PID=${PID:-none} LAST_EXIT=${LAST_EXIT:-unknown}"

ALARM=0
REASON=""
if [ -z "$STATE" ]; then
  ALARM=1; REASON="atlas-agent not registered with launchd"
elif [ -n "${LAST_EXIT}" ] && [ "${LAST_EXIT}" != "0" ] && [ "${LAST_EXIT}" != "(never exited)" ]; then
  if [ "${STATE}" != "running" ]; then
    ALARM=1; REASON="atlas-agent dead state=${STATE} last_exit=${LAST_EXIT}"
  fi
fi

if [ "$ALARM" = "1" ]; then
  note "ALARM raised: ${REASON}"
  curl -sS --max-time 6 https://memory.aimarketinggenius.io/api/decisions \
    -X POST -H 'Content-Type: application/json' \
    -d "$(printf '{"text":"ARGUS P1: %s","project_source":"titan","tags":["argus","atlas-agent","claim_cycle_deadlock_fix","ct-0428-recovery"]}' "${REASON}")" \
    >> "$LOG" 2>&1 || note "MCP post failed (non-fatal)"
  exit 1
fi

exit 0
