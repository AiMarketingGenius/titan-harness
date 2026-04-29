#!/bin/bash
# sync-agent-si.sh — DIR-009 Phase 3B: atomic three-location SI sync.
#
# Reads a canonical SI markdown file and pushes it to all three locations
# atomically:
#   1. VPS shared folder /opt/amg-docs/agents/<agent>/SI.md
#   2. Supabase agent_config.system_prompt (existing client-facing 7 + new
#      internal agents — Claude.ai project SI is opted-in for the 7
#      client-facing only; new internal agents are Supabase-only).
#   3. Claude.ai project SI export reference (out-of-band — this script
#      writes the export-ready file to /opt/amg-docs/agents/<agent>/SI-CLAUDE-AI.md
#      for Solon's manual paste; full Claude.ai automation is gated behind
#      Stagehand which doesn't fit a pre-Phase 11 ship).
#
# Atomic semantics: all-or-nothing across writeable surfaces (1 + 2). If
# either fails, both are rolled back. Surface 3 is best-effort export.
#
# Usage:
#   bash bin/sync-agent-si.sh <agent_id> <si_markdown_file> [--dry-run]
#
# Inputs:
#   <agent_id>            agent_config.agent_id (e.g., alex, maya, ops)
#   <si_markdown_file>    Source SI file (read once, hashed)
#
# Reads:
#   $SUPABASE_URL + $SUPABASE_SERVICE_ROLE_KEY
#   /etc/amg/cloudflare.env (only if accessing the VPS surface remotely;
#   else direct write via SSH or local on-VPS execution)
#   $TITAN_VPS_HOST  (default root@170.205.37.148)
#
# Doctrine: this is the operator-side SI sync; the agent-runtime side
# refreshes via agent_context_loader cached prefix (Phase 3C).
set -uo pipefail

AGENT_ID="${1:-}"
SI_FILE="${2:-}"
DRY_RUN="${3:-}"

if [ -z "$AGENT_ID" ] || [ -z "$SI_FILE" ]; then
  echo "Usage: $0 <agent_id> <si_markdown_file> [--dry-run]" >&2
  exit 2
fi

if [ ! -f "$SI_FILE" ]; then
  echo "sync-agent-si: ERROR — SI file not found: $SI_FILE" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$REPO_ROOT/lib/titan-env.sh" ] && source "$REPO_ROOT/lib/titan-env.sh"
[ -f "$HOME/.titan-env" ] && set -a && source "$HOME/.titan-env" && set +a

VPS_HOST="${TITAN_VPS_HOST:-root@170.205.37.148}"
SI_HASH=$(shasum -a 256 "$SI_FILE" 2>/dev/null | cut -c1-12 || sha256sum "$SI_FILE" | cut -c1-12)
TS=$(date -u +%Y%m%dT%H%M%SZ)

echo "sync-agent-si: agent=$AGENT_ID si_file=$SI_FILE hash=$SI_HASH ts=$TS"

if [ "$DRY_RUN" = "--dry-run" ]; then
  echo "DRY RUN — no writes will happen"
  echo "Would write VPS  : $VPS_HOST:/opt/amg-docs/agents/$AGENT_ID/SI.md (hash=$SI_HASH)"
  echo "Would update     : agent_config.system_prompt where agent_id='$AGENT_ID'"
  echo "Would export     : /opt/amg-docs/agents/$AGENT_ID/SI-CLAUDE-AI.md (best-effort)"
  exit 0
fi

# Capture current state for rollback (named stash)
echo "Capturing rollback state..."
STASH_DIR="/tmp/sync-agent-si-stash-$AGENT_ID-$TS"
mkdir -p "$STASH_DIR"

# Pull current Supabase row
CURRENT_PROMPT=$(curl -s -m 10 "$SUPABASE_URL/rest/v1/agent_config?agent_id=eq.$AGENT_ID&select=system_prompt" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY")
echo "$CURRENT_PROMPT" > "$STASH_DIR/supabase-current.json"

# Pull current VPS file (if exists)
ssh -o ConnectTimeout=8 "$VPS_HOST" "cat /opt/amg-docs/agents/$AGENT_ID/SI.md 2>/dev/null" \
  > "$STASH_DIR/vps-current.md" 2>/dev/null || touch "$STASH_DIR/vps-current.md"

echo "Rollback stash: $STASH_DIR"

# Apply VPS write
echo "Writing VPS surface..."
ssh -o ConnectTimeout=10 "$VPS_HOST" "mkdir -p /opt/amg-docs/agents/$AGENT_ID && cat > /opt/amg-docs/agents/$AGENT_ID/SI.md.tmp" < "$SI_FILE"
ssh -o ConnectTimeout=10 "$VPS_HOST" "mv /opt/amg-docs/agents/$AGENT_ID/SI.md.tmp /opt/amg-docs/agents/$AGENT_ID/SI.md"
VPS_EXIT=$?

if [ $VPS_EXIT -ne 0 ]; then
  echo "sync-agent-si: VPS write failed (exit $VPS_EXIT). No further writes attempted."
  exit 3
fi

# Apply Supabase write
echo "Writing Supabase surface..."
SI_CONTENT=$(python3 -c "import json,sys; print(json.dumps(open('$SI_FILE').read()))")
SUPA_RESP=$(curl -s -m 15 -X PATCH "$SUPABASE_URL/rest/v1/agent_config?agent_id=eq.$AGENT_ID" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  --data "{\"system_prompt\": $SI_CONTENT, \"updated_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}")
SUPA_EXIT=$?

if [ $SUPA_EXIT -ne 0 ] || [ -z "$SUPA_RESP" ] || echo "$SUPA_RESP" | grep -q '"error"'; then
  echo "sync-agent-si: Supabase write failed. Rolling back VPS..."
  ssh -o ConnectTimeout=10 "$VPS_HOST" "cat > /opt/amg-docs/agents/$AGENT_ID/SI.md" < "$STASH_DIR/vps-current.md"
  echo "VPS rollback applied. Stash kept at $STASH_DIR"
  echo "Supabase response: $SUPA_RESP"
  exit 4
fi

# Best-effort Claude.ai export
ssh -o ConnectTimeout=10 "$VPS_HOST" "cat > /opt/amg-docs/agents/$AGENT_ID/SI-CLAUDE-AI.md.tmp && mv /opt/amg-docs/agents/$AGENT_ID/SI-CLAUDE-AI.md.tmp /opt/amg-docs/agents/$AGENT_ID/SI-CLAUDE-AI.md" < "$SI_FILE" \
  && echo "Claude.ai export written (manual paste required)" \
  || echo "Claude.ai export skipped (best-effort)"

# Cleanup stash on success
echo "sync-agent-si: SUCCESS — agent=$AGENT_ID hash=$SI_HASH"
echo "Removing stash $STASH_DIR (sync confirmed atomic)"
rm -rf "$STASH_DIR"
