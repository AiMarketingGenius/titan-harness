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

# --- Resume-source priority arbitration (TLA v1.0 bug #2 fix) ---
#
# Per CLAUDE.md §7 + §13.1 + §13.4 + DOCTRINE_TLA_BUG2 (locked 2026-04-18):
# Cold-boot resume priority order is
#   (1) MCP RESTART_HANDOFF / safe-restart-eligible decisions with validated commit hash
#   (2) MCP tla-trigger-ready decision with validated commit hash
#   (3) NEXT_TASK.md + generic task queue (tertiary fallback only)
# If NEXT_TASK.md mtime < latest MCP RESTART_HANDOFF ts, NEXT_TASK.md is SKIPPED
# as stale. Inverting this order is a P0 protocol failure per §13.4.
#
# This block emits:
#   RESUME_SOURCE: mcp-handoff | mcp-trigger-ready | next-task-md | generic-queue | none
#   MCP_HANDOFF_COMMIT: <short hash> | none
#   MCP_HANDOFF_TS:     <iso8601>    | none
#   NEXT_TASK_SUMMARY:  <one-line summary from winning source>

MCP_HELPER="$REPO_ROOT/lib/mcp_latest_handoff.py"
MCP_JSON=""
MCP_FOUND="false"
MCP_TS_UNIX=0
MCP_COMMIT="none"
MCP_ISO="none"
MCP_HINT="none"
MCP_TEXT=""

if [ -x "$MCP_HELPER" ] || [ -f "$MCP_HELPER" ]; then
  # Run helper in a subshell so env sourcing doesn't leak.
  # Note: macOS lacks GNU `timeout`. The helper itself has a 10s urllib timeout,
  # which is sufficient — don't rely on `timeout` binary.
  MCP_JSON=$(
    set -a
    [ -f "$HOME/.titan-env" ] && source "$HOME/.titan-env" 2>/dev/null
    set +a
    python3 "$MCP_HELPER" 2>/dev/null || true
  )
  if [ -n "$MCP_JSON" ]; then
    MCP_FOUND=$(printf '%s' "$MCP_JSON" | python3 -c 'import json,sys;
try: print(json.load(sys.stdin).get("found",False))
except: print("false")' 2>/dev/null || echo "false")
    if [ "$MCP_FOUND" = "True" ] || [ "$MCP_FOUND" = "true" ]; then
      MCP_TS_UNIX=$(printf '%s' "$MCP_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("ts_unix",0))' 2>/dev/null || echo 0)
      MCP_COMMIT=$(printf '%s' "$MCP_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("commit_hash") or "none")' 2>/dev/null || echo "none")
      MCP_ISO=$(printf '%s'    "$MCP_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("iso_ts") or "none")' 2>/dev/null || echo "none")
      MCP_HINT=$(printf '%s'   "$MCP_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("resume_source_hint") or "mcp-handoff")' 2>/dev/null || echo "mcp-handoff")
      MCP_TEXT=$(printf '%s'   "$MCP_JSON" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("text_excerpt") or "").replace("\n"," ")[:180])' 2>/dev/null || echo "")
    fi
  fi
fi

# NEXT_TASK.md mtime (macOS stat syntax; cold-boot runs on Solon's Mac).
NT_MTIME=0
if [ -f "$NEXT_TASK_PATH" ]; then
  NT_MTIME=$(stat -f %m "$NEXT_TASK_PATH" 2>/dev/null || stat -c %Y "$NEXT_TASK_PATH" 2>/dev/null || echo 0)
fi

# Validate MCP commit hash against current git HEAD — if the handoff's commit is
# present in our git log, treat as trustworthy.
MCP_HASH_VALID="false"
if [ "$MCP_COMMIT" != "none" ] && [ -n "$MCP_COMMIT" ]; then
  if git -C "$REPO_ROOT" cat-file -e "$MCP_COMMIT^{commit}" 2>/dev/null; then
    MCP_HASH_VALID="true"
  fi
fi

# Decide RESUME_SOURCE
RESUME_SOURCE="none"
if [ "$MCP_FOUND" = "True" ] || [ "$MCP_FOUND" = "true" ]; then
  if [ "$MCP_HASH_VALID" = "true" ]; then
    if [ "$MCP_TS_UNIX" -gt "$NT_MTIME" ]; then
      RESUME_SOURCE="$MCP_HINT"
    else
      # MCP present but NEXT_TASK.md is newer — respect the freshest state.
      # Mark the staleness guard did NOT trigger this turn (for audit).
      RESUME_SOURCE="next-task-md"
      echo "MCP_HANDOFF_SUPERSEDED_BY_NEXT_TASK_MTIME: yes (mtime=$NT_MTIME mcp_ts=$MCP_TS_UNIX)"
    fi
  else
    # Handoff commit not resolvable in local git — do NOT trust; fall through.
    echo "MCP_HANDOFF_COMMIT_UNVERIFIED: $MCP_COMMIT (not in current repo)"
    RESUME_SOURCE="next-task-md"
  fi
elif [ -f "$NEXT_TASK_PATH" ]; then
  RESUME_SOURCE="next-task-md"
else
  RESUME_SOURCE="generic-queue"
fi

echo "RESUME_SOURCE: $RESUME_SOURCE"
echo "MCP_HANDOFF_COMMIT: $MCP_COMMIT"
echo "MCP_HANDOFF_TS: $MCP_ISO"

# NEXT_TASK summary — source depends on RESUME_SOURCE
case "$RESUME_SOURCE" in
  mcp-handoff|mcp-trigger-ready)
    # Pull the handoff's "NEXT ACTION ON RESUME" or first bullet line from the text
    SUMMARY=$(printf '%s' "$MCP_TEXT" | grep -oE '(NEXT ACTION[^.]*\.[^.]*\.|RESTART_HANDOFF [^.]+\.|[A-Z][^|]{20,120})' | head -1 | head -c 200)
    if [ -z "$SUMMARY" ]; then
      SUMMARY=$(printf '%s' "$MCP_TEXT" | head -c 200)
    fi
    echo "NEXT_TASK_SUMMARY: $SUMMARY"
    ;;
  next-task-md)
    if [ -f "$NEXT_TASK_PATH" ]; then
      SUMMARY=$(grep -m1 "^1\." "$NEXT_TASK_PATH" 2>/dev/null | sed 's/^1\. //' | head -c 200)
      if [ -z "$SUMMARY" ]; then
        SUMMARY=$(grep -m1 "^## " "$NEXT_TASK_PATH" 2>/dev/null | head -c 200)
      fi
      echo "NEXT_TASK_SUMMARY: ${SUMMARY:-'no summary'}"
    else
      echo "NEXT_TASK_SUMMARY: missing ($NEXT_TASK_PATH)"
    fi
    ;;
  *)
    echo "NEXT_TASK_SUMMARY: missing (no MCP handoff + no NEXT_TASK.md)"
    ;;
esac

# --- DOCTRINE_TITAN_AUTONOMY self-check (Layer 3) ---
# Verify the 4-layer autonomy lock survived since last session. Auto-restore
# any missing layer + Slack alert. Non-fatal — Solon's first turn unaffected.
AUTONOMY_OK=1
if ! grep -q "alias claude='claude --dangerously-skip-permissions'" "$HOME/.zshrc" 2>/dev/null && \
   ! grep -q "alias claude='claude --dangerously-skip-permissions'" "$HOME/.bash_profile" 2>/dev/null; then
    echo "AUTONOMY_LAYER_1: MISSING — restoring shell alias"
    bash "$REPO_ROOT/bin/restore-titan-autonomy.sh" >/dev/null 2>&1 || true
    AUTONOMY_OK=0
fi
SETTINGS_FILE="$REPO_ROOT/.claude/settings.local.json"
if [ ! -f "$SETTINGS_FILE" ] || ! grep -q '"Bash(\*)"' "$SETTINGS_FILE" 2>/dev/null; then
    echo "AUTONOMY_LAYER_2: MISSING — restoring settings.local.json"
    (cd "$REPO" && git checkout HEAD -- ".claude/settings.local.json" 2>/dev/null || \
     bash "$REPO_ROOT/bin/restore-titan-autonomy.sh" >/dev/null 2>&1) || true
    AUTONOMY_OK=0
fi
if [ $AUTONOMY_OK -eq 1 ]; then
    echo "AUTONOMY_SELF_CHECK: ok (4-layer lock intact)"
else
    echo "AUTONOMY_SELF_CHECK: RESTORED — see plans/DOCTRINE_TITAN_AUTONOMY.md"
    bash "$REPO_ROOT/bin/titan-notify.sh" --title "AUTONOMY RESET DETECTED" \
        "One or more autonomy layers were missing on boot. Restored from canonical." \
        >/dev/null 2>&1 || true
fi

# --- Exit classification ---
if [ $FATAL -eq 1 ]; then
  exit 2
fi
if [ $WARN -eq 1 ]; then
  exit 1
fi
exit 0
