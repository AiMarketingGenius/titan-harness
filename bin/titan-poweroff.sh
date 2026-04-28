#!/bin/bash
# titan-harness/bin/titan-poweroff.sh
#
# SOLON OS POWER OFF — clean shutdown sequence for the titan-harness
# session. Triggered by Solon saying "power off", "shutdown", or "power
# down" in any session on ~/titan-harness. Per CLAUDE.md §11.
#
# What it does:
#   1. Flush state
#      - Refresh RADAR.md timestamp + counts (scripts/radar_refresh.py)
#      - Refresh ALEXANDRIA_INDEX.md (lib/alexandria.py --refresh)
#      - Refresh any open progress notes in plans/control-loop/
#   2. Preflights
#      - bin/alexandria-preflight.sh (doctrine placement clean)
#      - bin/harness-preflight.sh (capacity CORE_CONTRACT)
#   3. Auto-Mirror verification
#      - Check working tree clean (git status --porcelain)
#      - Check mirror drift: Mac vs VPS working vs VPS bare
#      - If drift → run the mirror sequence (push + VPS ff-merge) and
#        verify /var/log/titan-harness-mirror.log shows "mirror push OK"
#
# Output format (one KEY: value per line on stdout — same shape as
# titan-boot-audit.sh so Titan can parse either):
#   HEAD: <short hash>
#   BRANCH: <branch>
#   WORKING_TREE_CLEAN: yes|no
#   RADAR_REFRESHED: yes|no
#   ALEXANDRIA_REFRESHED: yes|no
#   ALEXANDRIA_PREFLIGHT: clean|violations=N
#   HARNESS_PREFLIGHT: ok|failed:<code>
#   MIRROR_DRIFT: no|yes (fixed)|yes (could not fix)
#   GITHUB_MIRROR: ok|stale|unknown
#   FLUSH_STATE: ok|partial|failed
#
# Exit codes:
#   0 — clean shutdown (safe to say "Power off complete. All state flushed and mirrored.")
#   1 — non-fatal warnings (shutdown proceeded but something needs attention)
#   2 — fatal (cannot flush or mirror; DO NOT emit the standard reply)

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VPS_HOST="${TITAN_VPS_HOST:-root@170.205.37.148}"
VPS_PATH="/opt/titan-harness"

cd "$REPO_ROOT" || { echo "FLUSH_STATE: failed (cannot cd $REPO_ROOT)"; exit 2; }

WARN=0
FATAL=0

# --- HEAD + branch ---
HEAD=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
echo "HEAD: $HEAD"
echo "BRANCH: $BRANCH"

# --- Step 1: Flush state ---

# 1a. RADAR refresh
RADAR_REFRESHED="no"
if [ -x "$REPO_ROOT/scripts/radar_refresh.py" ]; then
  if python3 "$REPO_ROOT/scripts/radar_refresh.py" >/dev/null 2>&1; then
    RADAR_REFRESHED="yes"
  fi
fi
echo "RADAR_REFRESHED: $RADAR_REFRESHED"

# 1b. Alexandria refresh
# CT-0428-38 Fix 3b: refresh writes a "Last index refresh" timestamp into the
# tracked ALEXANDRIA_INDEX.md, which dirties the tree even when nothing
# material changed. After refresh, if the ONLY diff is the timestamp line,
# revert the file to keep the tree clean. Real count changes still propagate
# (they leave non-timestamp +/- lines in the diff). This is the
# "separate refresh from check" pattern (also CT-0428-16).
ALEXANDRIA_REFRESHED="no"
if [ -f "$REPO_ROOT/lib/alexandria.py" ]; then
  if python3 "$REPO_ROOT/lib/alexandria.py" --refresh >/dev/null 2>&1; then
    ALEXANDRIA_REFRESHED="yes"
    INDEX_DIFF=$(git -C "$REPO_ROOT" diff --no-color library_of_alexandria/ALEXANDRIA_INDEX.md 2>/dev/null)
    if [ -n "$INDEX_DIFF" ]; then
      MEANINGFUL=$(echo "$INDEX_DIFF" \
        | grep -E "^[+-]" \
        | grep -vE "^(\+\+\+|---|[+-].*Last index refresh:)" \
        | wc -l | tr -d ' ')
      if [ "$MEANINGFUL" = "0" ]; then
        git -C "$REPO_ROOT" checkout -- library_of_alexandria/ALEXANDRIA_INDEX.md 2>/dev/null || true
      fi
    fi
  fi
fi
echo "ALEXANDRIA_REFRESHED: $ALEXANDRIA_REFRESHED"

# --- Step 2: Preflights ---

# 2a. Alexandria preflight (doctrine placement)
if [ -x "$REPO_ROOT/bin/alexandria-preflight.sh" ]; then
  AP_OUT=$(bash "$REPO_ROOT/bin/alexandria-preflight.sh" 2>&1)
  AP_EXIT=$?
  if [ $AP_EXIT -eq 0 ]; then
    echo "ALEXANDRIA_PREFLIGHT: clean"
  else
    VIOLATIONS=$(echo "$AP_OUT" | grep -c "doctrine file outside" 2>/dev/null || echo 0)
    echo "ALEXANDRIA_PREFLIGHT: violations=$VIOLATIONS"
    WARN=1
  fi
else
  echo "ALEXANDRIA_PREFLIGHT: skipped"
fi

# 2b. Harness preflight (capacity CORE_CONTRACT)
if [ -x "$REPO_ROOT/bin/harness-preflight.sh" ]; then
  HP_OUT=$(bash "$REPO_ROOT/bin/harness-preflight.sh" 2>&1)
  HP_EXIT=$?
  if [ $HP_EXIT -eq 0 ]; then
    echo "HARNESS_PREFLIGHT: ok"
  else
    echo "HARNESS_PREFLIGHT: failed:$HP_EXIT"
    # 10/11/12 = fatal per CORE_CONTRACT §1-§2
    if [ $HP_EXIT -ge 10 ] && [ $HP_EXIT -le 12 ]; then
      FATAL=1
    else
      WARN=1
    fi
  fi
else
  echo "HARNESS_PREFLIGHT: skipped"
fi

# --- Step 3: Auto-Mirror verification ---

# 3a. Working tree clean check
if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
  echo "WORKING_TREE_CLEAN: yes"
else
  echo "WORKING_TREE_CLEAN: no"
  # Not fatal — Solon may have intentional uncommitted changes. Warn only.
  WARN=1
fi

# 3b. Mirror drift detection + auto-fix
MAC_HEAD_FULL=$(git rev-parse HEAD 2>/dev/null || echo "")
DRIFT_STATUS="no"
GITHUB_STATUS="unknown"

if [ -n "$MAC_HEAD_FULL" ]; then
  # VPS working tree
  VPS_WORK_HEAD=$(ssh -o ConnectTimeout=3 -o BatchMode=yes "$VPS_HOST" \
    "git -C $VPS_PATH rev-parse HEAD 2>/dev/null" 2>/dev/null || echo "unreachable")
  # VPS bare
  VPS_BARE_HEAD=$(ssh -o ConnectTimeout=3 -o BatchMode=yes "$VPS_HOST" \
    "git -C ${VPS_PATH}.git rev-parse master 2>/dev/null" 2>/dev/null || echo "unreachable")

  DRIFT_DETECTED=0
  if [ "$VPS_WORK_HEAD" != "unreachable" ] && [ "$VPS_WORK_HEAD" != "$MAC_HEAD_FULL" ]; then
    DRIFT_DETECTED=1
  fi
  if [ "$VPS_BARE_HEAD" != "unreachable" ] && [ "$VPS_BARE_HEAD" != "$MAC_HEAD_FULL" ]; then
    DRIFT_DETECTED=1
  fi

  if [ $DRIFT_DETECTED -eq 1 ]; then
    # Auto-fix: push from Mac + ff-merge on VPS
    PUSH_OK=0
    if git push origin master >/dev/null 2>&1; then
      PUSH_OK=1
    fi
    VPS_SYNC_OK=0
    if [ $PUSH_OK -eq 1 ]; then
      if ssh -o ConnectTimeout=5 -o BatchMode=yes "$VPS_HOST" \
         "cd $VPS_PATH && git fetch origin && git merge --ff-only origin/master" \
         >/dev/null 2>&1; then
        VPS_SYNC_OK=1
      fi
    fi
    if [ $PUSH_OK -eq 1 ] && [ $VPS_SYNC_OK -eq 1 ]; then
      DRIFT_STATUS="yes (fixed)"
    else
      DRIFT_STATUS="yes (could not fix)"
      FATAL=1
    fi
  fi

  # GitHub mirror check — primary: direct GitHub API SHA compare (matches
  # harness-drift-check.sh leg 3). Falls back to MIRROR_STATUS.md row, then
  # to post-receive log tail. CT-0428-38 Fix 3.
  GH_REPO="${TITAN_GH_REPO:-AiMarketingGenius/titan-harness}"
  GH_SHA=""
  if command -v curl >/dev/null 2>&1; then
    if [ -n "${GITHUB_TOKEN:-}" ]; then
      GH_SHA=$(curl -s -m 5 -H "Authorization: token $GITHUB_TOKEN" \
        "https://api.github.com/repos/$GH_REPO/commits/$BRANCH" 2>/dev/null \
        | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('sha',''))" 2>/dev/null \
        || echo "")
    else
      GH_SHA=$(curl -s -m 5 "https://api.github.com/repos/$GH_REPO/commits/$BRANCH" 2>/dev/null \
        | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('sha',''))" 2>/dev/null \
        || echo "")
    fi
  fi

  if [ -n "$GH_SHA" ] && [ "$GH_SHA" = "$MAC_HEAD_FULL" ]; then
    GITHUB_STATUS="ok"
  elif [ -n "$GH_SHA" ] && [ "$GH_SHA" != "$MAC_HEAD_FULL" ]; then
    GITHUB_STATUS="stale"
    WARN=1
  else
    # Fallback 1: MIRROR_STATUS.md SHA row for GitHub
    if [ -f "$REPO_ROOT/MIRROR_STATUS.md" ]; then
      MS_GH_LINE=$(grep -E "^\| GitHub" "$REPO_ROOT/MIRROR_STATUS.md" 2>/dev/null | head -1)
      if echo "$MS_GH_LINE" | grep -q "$MAC_HEAD_FULL"; then
        GITHUB_STATUS="ok"
      fi
    fi
    # Fallback 2: post-receive log tail with broader pattern matching
    if [ "$GITHUB_STATUS" = "unknown" ]; then
      GITHUB_TAIL=$(ssh -o ConnectTimeout=3 -o BatchMode=yes "$VPS_HOST" \
        "tail -50 /var/log/titan-harness-mirror.log 2>/dev/null" 2>/dev/null || echo "")
      if echo "$GITHUB_TAIL" | grep -qE "(mirror push OK|MIRROR:.*OK|GitHub.*OK)"; then
        GITHUB_STATUS="ok"
      elif echo "$GITHUB_TAIL" | grep -qE "(mirror push FAILED|MIRROR:.*FAIL|GitHub.*FAIL)"; then
        GITHUB_STATUS="stale"
        WARN=1
      elif [ "$DRIFT_STATUS" = "no" ] && [ -n "$GITHUB_TAIL" ]; then
        # Last resort: 3-leg local sync green AND log readable AND no FAILED
        # entries — infer ok (same SHA on bare implies post-receive ran).
        # Tag as "ok (inferred)" so it's distinguishable in reports.
        GITHUB_STATUS="ok (inferred)"
      fi
    fi
  fi
fi

echo "MIRROR_DRIFT: $DRIFT_STATUS"
echo "GITHUB_MIRROR: $GITHUB_STATUS"

# --- Flush state summary ---
if [ $FATAL -eq 1 ]; then
  echo "FLUSH_STATE: failed"
  exit 2
fi
if [ $WARN -eq 1 ]; then
  echo "FLUSH_STATE: partial"
  exit 1
fi
echo "FLUSH_STATE: ok"
exit 0
