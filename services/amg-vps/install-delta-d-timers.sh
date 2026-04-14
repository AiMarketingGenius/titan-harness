#!/bin/bash
# install-delta-d-timers.sh — DELTA-D systemd timer installer (2026-04-14)
# Canonical source: ~/titan-harness/services/amg-vps/install-delta-d-timers.sh
# Runs on VPS. Installs 5 amg-* timers with per-timer test gate before enable.
#
# Usage:
#   ./install-delta-d-timers.sh                    # install + test + enable
#   ./install-delta-d-timers.sh --rollback         # disable + remove all amg-* timers
#   ./install-delta-d-timers.sh --skip-test        # install + enable without service test
#
# Safety:
#   - Each service is manually invoked BEFORE its timer is enabled
#   - Service exit non-zero → timer NOT enabled → script exits non-zero
#   - --rollback is idempotent and removes all DELTA-D timers cleanly

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMERS=(amg-git-heal amg-disk-heal amg-doctrine-drift amg-config-drift amg-sha-consistency)
UNIT_DIR="/etc/systemd/system"
SRC_UNIT_DIR="${SCRIPT_DIR}/etc-systemd"

say() { echo "[install-delta-d] $*"; }

rollback() {
  say "ROLLBACK: disabling + removing all DELTA-D timers"
  for t in "${TIMERS[@]}"; do
    systemctl disable --now "${t}.timer" 2>/dev/null || true
    systemctl stop "${t}.service" 2>/dev/null || true
    rm -fv "${UNIT_DIR}/${t}.timer" "${UNIT_DIR}/${t}.service"
  done
  systemctl daemon-reload
  say "ROLLBACK complete"
  exit 0
}

if [[ "${1:-}" == "--rollback" ]]; then
  rollback
fi

SKIP_TEST=false
if [[ "${1:-}" == "--skip-test" ]]; then
  SKIP_TEST=true
fi

# Pre-flight: source units exist + scripts they reference exist + executable
MISSING=()
for t in "${TIMERS[@]}"; do
  [[ -f "${SRC_UNIT_DIR}/${t}.service" ]] || MISSING+=("${SRC_UNIT_DIR}/${t}.service")
  [[ -f "${SRC_UNIT_DIR}/${t}.timer" ]] || MISSING+=("${SRC_UNIT_DIR}/${t}.timer")
done
for S in /opt/amg/scripts/git-heal.sh /opt/amg/scripts/disk-heal.sh \
         /opt/amg/scripts/doctrine-drift-check.sh /opt/amg/scripts/config-drift-check.sh \
         /opt/amg/scripts/sha-consistency-check.sh; do
  [[ -x "$S" ]] || MISSING+=("$S (not executable or missing)")
done
if [[ ${#MISSING[@]} -gt 0 ]]; then
  say "FAIL: preflight — missing sources:"
  printf '  %s\n' "${MISSING[@]}"
  exit 2
fi

# Ensure /opt/amg/.sha256-expected.txt exists (drift scripts need it)
if [[ ! -f /opt/amg/.sha256-expected.txt ]]; then
  say "FAIL: /opt/amg/.sha256-expected.txt missing — drift scripts would fail"
  say "      deploy it from harness first: scp .../sha256-expected.txt VPS:/opt/amg/.sha256-expected.txt"
  exit 2
fi

# Install phase
say "Installing 5 timer units + 5 service units to ${UNIT_DIR}"
for t in "${TIMERS[@]}"; do
  cp -v "${SRC_UNIT_DIR}/${t}.service" "${UNIT_DIR}/${t}.service"
  cp -v "${SRC_UNIT_DIR}/${t}.timer" "${UNIT_DIR}/${t}.timer"
done
systemctl daemon-reload
say "daemon-reload complete"

# Test phase — invoke each service ONCE manually; if it fails, halt
if [[ "$SKIP_TEST" == "false" ]]; then
  FAILED=()
  for t in "${TIMERS[@]}"; do
    say "TEST: systemctl start ${t}.service (oneshot)"
    if systemctl start "${t}.service"; then
      # oneshot services exit after run — check result
      STATUS=$(systemctl show "${t}.service" --property=Result --value)
      EXIT_CODE=$(systemctl show "${t}.service" --property=ExecMainStatus --value)
      say "  result=$STATUS exit=$EXIT_CODE"
      # drift-check scripts exit 1 on drift (expected for doctrine if drift exists); accept 0 AND 1 as "executed"
      case "$t" in
        amg-doctrine-drift|amg-config-drift|amg-sha-consistency)
          [[ "$STATUS" == "success" || "$EXIT_CODE" == "1" ]] || FAILED+=("$t")
          ;;
        *)
          [[ "$STATUS" == "success" ]] || FAILED+=("$t")
          ;;
      esac
    else
      FAILED+=("$t")
    fi
  done

  if [[ ${#FAILED[@]} -gt 0 ]]; then
    say "FAIL: test phase — these services did not run cleanly:"
    printf '  %s\n' "${FAILED[@]}"
    say "Units installed but NO timers enabled. Investigate or run --rollback."
    exit 3
  fi
  say "TEST phase: all 5 services exited successfully"
else
  say "--skip-test: bypassing test phase"
fi

# Enable phase
for t in "${TIMERS[@]}"; do
  say "ENABLE: ${t}.timer"
  systemctl enable --now "${t}.timer"
done
say "All 5 timers enabled + started"

# Summary
say "==== SUMMARY ===="
systemctl list-timers --all | grep -E "^(NEXT|amg-)" | head -10
say "================="
exit 0
