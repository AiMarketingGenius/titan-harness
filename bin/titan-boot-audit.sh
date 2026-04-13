#!/bin/bash
# titan-harness/bin/titan-boot-audit.sh
#
# SOLON OS COLD BOOT audit — one-shot script run at the start of every
# new Claude Code session on ~/titan-harness. Produces a compact status
# block Titan parses to emit the boot greeting.
#
# Invoked by Titan automatically per CLAUDE.md §7. Can also be run
# manually: `bash bin/titan-boot-audit.sh`
#
# Output format (stdout, one KEY: value per line):
#   HEAD: <commit hash>
#   BRANCH: <branch>
#   MIRROR_DRIFT: yes|no
#   WORKING_TREE_CLEAN: yes|no
#   ALEXANDRIA_PREFLIGHT: clean|violations=N
#   HARNESS_PREFLIGHT: ok|failed:<code>
#   CAPACITY: ok|soft_block|hard_block
#   RADAR_OPEN_ITEMS: N
#   BLOCKED_ON_SOLON: N
#   NEXT_TASK_SUMMARY: <one-line summary or 'missing'>
#
# Exit codes:
#   0 — all checks clean
#   1 — one or more non-fatal warnings (drift, dirty tree, placement violations)
#   2 — fatal boot failure (harness preflight exit 10/11/12)

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VPS_HOST="${TITAN_VPS_HOST:-root@170.205.37.148}"
VPS_WORK_PATH="/opt/titan-harness-work"
VPS_BARE_PATH="/opt/titan-harness.git"
NEXT_TASK_PATH="${TITAN_SESSION_DIR:-$HOME/titan-session}/NEXT_TASK.md"

cd "$REPO_ROOT" || { echo "BOOT_FAILED: cannot cd to $REPO_ROOT" >&2; exit 2; }

WARN=0
FATAL=0

# --- HEAD + branch ---
HEAD=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
echo "HEAD: $HEAD"
echo "BRANCH: $BRANCH"

# --- Working tree clean ---
# Exclude files that are expected to be dirty after boot (refreshed by this script or post-commit hook)
DIRTY=$(git status --porcelain 2>/dev/null | grep -v 'MIRROR_STATUS.md' | grep -v '^ M RADAR.md$' || true)
if [ -z "$DIRTY" ]; then
  echo "WORKING_TREE_CLEAN: yes"
else
  echo "WORKING_TREE_CLEAN: no"
  WARN=1
fi

# --- Mirror drift detection ---
# Compare Mac HEAD vs VPS working tree + bare + GitHub (via git ls-remote)
MAC_HEAD_FULL=$(git rev-parse HEAD 2>/dev/null || echo "")
DRIFT="no"
if [ -n "$MAC_HEAD_FULL" ]; then
  # Try VPS working tree via ssh (short timeout — don't block boot)
  VPS_WORK_HEAD=$(ssh -o ConnectTimeout=3 -o BatchMode=yes "$VPS_HOST" \
    "git -C $VPS_WORK_PATH rev-parse HEAD 2>/dev/null" 2>/dev/null || echo "unreachable")
  VPS_BARE_HEAD=$(ssh -o ConnectTimeout=3 -o BatchMode=yes "$VPS_HOST" \
    "git -C $VPS_BARE_PATH rev-parse master 2>/dev/null" 2>/dev/null || echo "unreachable")

  if [ "$VPS_WORK_HEAD" != "unreachable" ] && [ "$VPS_WORK_HEAD" != "$MAC_HEAD_FULL" ]; then
    DRIFT="yes (VPS working tree at ${VPS_WORK_HEAD:0:7})"
  fi
  if [ "$VPS_BARE_HEAD" != "unreachable" ] && [ "$VPS_BARE_HEAD" != "$MAC_HEAD_FULL" ] && [ "$DRIFT" = "no" ]; then
    DRIFT="yes (VPS bare at ${VPS_BARE_HEAD:0:7})"
  fi
fi
echo "MIRROR_DRIFT: $DRIFT"
if [ "$DRIFT" != "no" ]; then
  WARN=1
fi

# --- Alexandria preflight (doctrine placement) ---
if [ -x "$REPO_ROOT/bin/alexandria-preflight.sh" ]; then
  AP_OUT=$(bash "$REPO_ROOT/bin/alexandria-preflight.sh" 2>&1)
  AP_EXIT=$?
  if [ $AP_EXIT -eq 0 ]; then
    echo "ALEXANDRIA_PREFLIGHT: clean"
  else
    VIOLATIONS=$(echo "$AP_OUT" | grep -c "doctrine file outside" || true)
    echo "ALEXANDRIA_PREFLIGHT: violations=$VIOLATIONS"
    WARN=1
  fi
else
  echo "ALEXANDRIA_PREFLIGHT: skipped (script missing)"
fi

# --- Harness preflight (capacity CORE_CONTRACT) ---
if [ -x "$REPO_ROOT/bin/harness-preflight.sh" ]; then
  HP_OUT=$(bash "$REPO_ROOT/bin/harness-preflight.sh" 2>&1)
  HP_EXIT=$?
  if [ $HP_EXIT -eq 0 ]; then
    echo "HARNESS_PREFLIGHT: ok"
  else
    echo "HARNESS_PREFLIGHT: failed:$HP_EXIT"
    # Exit codes 10, 11, 12 are fatal per CORE_CONTRACT
    if [ $HP_EXIT -ge 10 ] && [ $HP_EXIT -le 12 ]; then
      FATAL=1
    fi
  fi
else
  echo "HARNESS_PREFLIGHT: skipped (script missing)"
fi

# --- Capacity check (live CPU/RAM) ---
if [ -x "$REPO_ROOT/bin/check-capacity.sh" ]; then
  CC_OUT=$(bash "$REPO_ROOT/bin/check-capacity.sh" 2>&1)
  CC_EXIT=$?
  case $CC_EXIT in
    0) echo "CAPACITY: ok" ;;
    1) echo "CAPACITY: soft_block"; WARN=1 ;;
    2) echo "CAPACITY: hard_block"; FATAL=1 ;;
    *) echo "CAPACITY: unknown:$CC_EXIT" ;;
  esac
else
  echo "CAPACITY: skipped (script missing)"
fi

# --- RADAR refresh + counts ---
if [ -x "$REPO_ROOT/scripts/radar_refresh.py" ]; then
  python3 "$REPO_ROOT/scripts/radar_refresh.py" >/dev/null 2>&1 || true
fi
if [ -f "$REPO_ROOT/RADAR.md" ]; then
  OPEN_MPS=$(grep -c "^- " "$REPO_ROOT/RADAR.md" 2>/dev/null || echo 0)
  BLOCKED=$(awk '/^## Blocked on Solon/,/^## /' "$REPO_ROOT/RADAR.md" 2>/dev/null | grep -c "^[0-9]\+\." || echo 0)
  echo "RADAR_OPEN_ITEMS: $OPEN_MPS"
  echo "BLOCKED_ON_SOLON: $BLOCKED"
else
  echo "RADAR_OPEN_ITEMS: 0"
  echo "BLOCKED_ON_SOLON: 0"
fi

# --- NEXT_TASK one-line summary ---
if [ -f "$NEXT_TASK_PATH" ]; then
  # Pull the first non-empty line after "FIRST MESSAGE TO SEND ME" block,
  # or the "Immediate next actions" section, whichever appears first
  SUMMARY=$(grep -m1 "^1\." "$NEXT_TASK_PATH" 2>/dev/null | sed 's/^1\. //' | head -c 200)
  if [ -z "$SUMMARY" ]; then
    SUMMARY=$(grep -m1 "^## " "$NEXT_TASK_PATH" 2>/dev/null | head -c 200)
  fi
  echo "NEXT_TASK_SUMMARY: ${SUMMARY:-'no summary'}"
else
  echo "NEXT_TASK_SUMMARY: missing ($NEXT_TASK_PATH)"
fi

# --- Exit classification ---
if [ $FATAL -eq 1 ]; then
  exit 2
fi
if [ $WARN -eq 1 ]; then
  exit 1
fi
exit 0
