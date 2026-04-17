#!/usr/bin/env bash
# scripts/boot-self-heal.sh
# CT-0417-27 T2 — Titan boot-time self-heal.
#
# Runs BEFORE any user task is accepted. Verifies canonical pwd, harness
# integrity, MCP reachability; if anything is missing, attempts recovery
# from MCP-stored config or git-clone; writes a heartbeat decision to MCP.
#
# Exit codes:
#   0 = clean boot, Titan may accept tasks
#   1 = soft heal performed (e.g. cd into canonical path) — Titan may accept tasks
#   10 = hard fail — harness missing + clone failed
#   11 = hard fail — MCP unreachable after retries
#   12 = hard fail — critical files missing + recovery impossible
#
# Hard-fail path: exit non-zero, print Slack-notifiable one-liner, do NOT
# write heartbeat. Caller (systemd ExecStartPre / tmux boot command / session
# start-hook) must halt.

set -uo pipefail

# ───────── Config (per-machine) ─────────
case "$(uname -s)" in
  Darwin)  CANONICAL="${TITAN_CANONICAL_PATH:-$HOME/titan-harness}" ;;
  Linux)   CANONICAL="${TITAN_CANONICAL_PATH:-/opt/titan-harness}" ;;
  *)       echo "[boot-self-heal] unknown OS $(uname -s); aborting" >&2; exit 12 ;;
esac

MCP_URL="${MCP_URL:-https://memory.aimarketinggenius.io}"
LOG="${TITAN_BOOT_LOG:-$HOME/.claude/boot-self-heal.log}"
HEARTBEAT="${TITAN_BOOT_HEARTBEAT:-$HOME/.claude/boot-self-heal.last}"
REPO_REMOTE="${TITAN_REPO_REMOTE:-ssh://170.205.37.148/opt/titan-harness.git}"

mkdir -p "$(dirname "$LOG")" "$(dirname "$HEARTBEAT")"
exec >>"$LOG" 2>&1
echo "═════ $(date -u +%Y-%m-%dT%H:%M:%SZ) boot-self-heal fire ═════"

# Exit trap prints the final state tag for downstream parsing
final_state="UNKNOWN"
trap 'echo "[boot-self-heal] final_state=$final_state"' EXIT

slack_alert() {
  # $1 = severity (critical|warn|info), $2 = one-liner body
  local sev="$1" body="$2"
  echo "[slack-alert $sev] $body"
  if [ -n "${SLACK_WEBHOOK_BOOTHEAL:-}" ]; then
    curl -s -X POST "$SLACK_WEBHOOK_BOOTHEAL" \
      -H 'Content-Type: application/json' \
      -d "{\"text\":\"[boot-self-heal] [$sev] $body\"}" > /dev/null 2>&1 || true
  fi
}

# ───────── Step 1. pwd check + cd into canonical ─────────
CURRENT_PWD="$(pwd)"
if [ "$CURRENT_PWD" != "$CANONICAL" ]; then
  if [ -d "$CANONICAL" ]; then
    echo "[step1] pwd=$CURRENT_PWD != canonical=$CANONICAL — cd'ing into canonical"
    cd "$CANONICAL" || { echo "[step1] cd failed"; final_state="STEP1_CD_FAIL"; exit 12; }
    final_state="SOFT_HEAL_CD"
  else
    echo "[step1] canonical path $CANONICAL does not exist — attempting clone"
    if git clone "$REPO_REMOTE" "$CANONICAL"; then
      cd "$CANONICAL" || { echo "[step1] post-clone cd failed"; final_state="STEP1_POST_CLONE_CD_FAIL"; exit 10; }
      slack_alert critical "Cloned canonical harness from remote into $CANONICAL — investigate why it was missing"
      final_state="HARD_HEAL_CLONE"
    else
      echo "[step1] git clone failed"
      slack_alert critical "Canonical harness missing AND clone failed. Titan cannot boot."
      final_state="STEP1_CLONE_FAIL"
      exit 10
    fi
  fi
else
  echo "[step1] pwd matches canonical ✓"
fi

# ───────── Step 2. Critical-files preflight ─────────
# Critical-files list: settings is required; MCP config may live in any of
# several locations; doctrine + pre-commit hooks must exist.
declare -a REQUIRED=(
  ".claude/settings.local.json"
  "plans/doctrine"
  "CLAUDE.md"
  "CORE_CONTRACT.md"
  "hooks/pre-commit-tradesecret-scan.sh"
  "hooks/pre-commit-lumina-gate.sh"
)
# MCP config can live at any of these paths — require AT LEAST ONE to exist
declare -a MCP_CONFIG_CANDIDATES=(
  ".mcp.json"
  ".claude/mcp.json"
  "$HOME/.claude/mcp.json"
  "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
)
mcp_config_found=false
for cand in "${MCP_CONFIG_CANDIDATES[@]}"; do
  if [ -f "$cand" ]; then
    mcp_config_found=true
    echo "[step2] MCP config found at $cand"
    break
  fi
done
if [ "$mcp_config_found" != true ]; then
  echo "[step2] WARN: no MCP config file found in any of: ${MCP_CONFIG_CANDIDATES[*]}"
  slack_alert warn "boot-self-heal: no MCP config file found (non-blocking — CLI may have it inline)"
fi
missing=()
for rel in "${REQUIRED[@]}"; do
  [ -e "$rel" ] || missing+=("$rel")
done
if [ "${#missing[@]}" -gt 0 ]; then
  echo "[step2] missing critical files: ${missing[*]}"
  slack_alert critical "Titan boot: missing critical files: ${missing[*]}"
  final_state="STEP2_MISSING_CRITICAL"
  exit 12
fi
echo "[step2] critical files present ✓"

# Check pre-commit hook chain is installed (4-layer per CLAUDE.md §18.2)
if [ -f ".git/hooks/pre-commit" ]; then
  layers=0
  grep -q "pre-commit-tradesecret-scan.sh" .git/hooks/pre-commit 2>/dev/null && layers=$((layers+1))
  grep -q "pre-commit-lumina-gate.sh" .git/hooks/pre-commit 2>/dev/null && layers=$((layers+1))
  echo "[step2] pre-commit hook chain: $layers/2 visible layers wired"
  if [ "$layers" -lt 2 ]; then
    slack_alert warn "pre-commit hook chain appears partial ($layers/2) — investigate"
  fi
fi

# ───────── Step 3. MCP reachability ─────────
UA="titan-boot-self-heal/1.0 ($(uname -s); $(hostname))"
mcp_ok=false
for attempt in 1 2 3; do
  if curl -s --max-time 5 -A "$UA" "$MCP_URL/health" 2>/dev/null | grep -q '"status"'; then
    mcp_ok=true
    break
  fi
  sleep $((attempt * 2))
done
if [ "$mcp_ok" != "true" ]; then
  echo "[step3] MCP unreachable after 3 retries — $MCP_URL/health"
  slack_alert critical "MCP unreachable from boot-self-heal after 3 retries. Titan cannot accept tasks."
  final_state="STEP3_MCP_UNREACHABLE"
  exit 11
fi
echo "[step3] MCP reachable ✓"

# ───────── Step 4. Bootstrap context probe ─────────
# Don't require a specific payload shape (MCP evolves) — just require non-empty JSON
# Use curl with a small-payload POST that every MCP build accepts.
bootstrap_ok=false
bootstrap_resp="$(curl -s --max-time 10 -A "$UA" "$MCP_URL/api/get_sprint_state?project_id=EOM" 2>/dev/null)"
if [ -n "$bootstrap_resp" ] && echo "$bootstrap_resp" | grep -qE '(sprint_name|completion_pct|kill_chain|"EOM")'; then
  bootstrap_ok=true
  echo "[step4] bootstrap context probe ok"
else
  echo "[step4] bootstrap context probe returned unexpected shape; continuing (non-blocking)"
  slack_alert warn "Bootstrap context probe non-blocking: unexpected response shape from MCP"
fi

# ───────── Step 5. Heartbeat + MCP decision log ─────────
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "$NOW" > "$HEARTBEAT"

# Fire-and-forget MCP log — do not fail the boot if this errors
if command -v curl >/dev/null; then
  BODY=$(cat <<EOF
{
  "project_source": "EOM",
  "text": "boot-self-heal fired at $NOW. pwd=$(pwd). canonical=$CANONICAL. mcp=$mcp_ok. final_state=$final_state.",
  "tags": ["boot-self-heal", "ct-0417-27-t2", "$(uname -s | tr '[:upper:]' '[:lower:]')"]
}
EOF
)
  curl -s -X POST "$MCP_URL/api/log_decision" \
    -H 'Content-Type: application/json' \
    -A "$UA" \
    -d "$BODY" > /dev/null 2>&1 || \
    echo "[step5] MCP log_decision post failed (non-blocking)"
fi

echo "[step5] heartbeat written to $HEARTBEAT"

# ───────── Final ─────────
if [ "$final_state" = "UNKNOWN" ]; then
  final_state="CLEAN"
fi
echo "[boot-self-heal] OK — final_state=$final_state"
case "$final_state" in
  CLEAN)            exit 0  ;;
  SOFT_HEAL_CD)     exit 1  ;;
  HARD_HEAL_CLONE)  exit 1  ;;
  *)                exit 12 ;;
esac
