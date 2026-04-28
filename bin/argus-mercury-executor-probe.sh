#!/usr/bin/env bash
# argus-mercury-executor-probe.sh — Atlas Factory CT-0428-recovery / mercury_phase1_patch.
# Runs every 5 min via launchd (com.amg.argus-mercury-executor.plist).
# Inspects com.amg.mercury-executor; raises P1 alert on exit-non-zero or dead state.
# Same failure-class detection as the atlas-agent probe.
set -uo pipefail

UID_NUM="$(id -u)"
LABEL="com.amg.mercury-executor"
LOG=/tmp/argus-mercury-executor.log
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
  ALARM=1; REASON="mercury-executor not registered with launchd"
elif [ -n "${LAST_EXIT}" ] && [ "${LAST_EXIT}" != "0" ] && [ "${LAST_EXIT}" != "(never exited)" ]; then
  if [ "${STATE}" != "running" ]; then
    ALARM=1; REASON="mercury-executor dead state=${STATE} last_exit=${LAST_EXIT}"
  fi
fi

if [ "$ALARM" = "1" ]; then
  note "ALARM raised: ${REASON}"
  curl -sS --max-time 6 https://memory.aimarketinggenius.io/api/decisions \
    -X POST -H 'Content-Type: application/json' \
    -d "$(printf '{"text":"ARGUS P1: %s","project_source":"titan","tags":["argus","mercury-executor","mercury_phase1_patch","ct-0428-recovery"]}' "${REASON}")" \
    >> "$LOG" 2>&1 || note "MCP post failed (non-fatal)"
  exit 1
fi

exit 0
