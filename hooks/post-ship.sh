#!/bin/bash
# post-ship.sh — fires after every log_decision call with a *_shipped|*_complete|*_done tag.
# Re-queries MCP get_task_queue for the current agent, rewrites NEXT_TASK.md so the
# agent always reads authoritative queue state on next claim cycle.
#
# Doctrine: DIR-009 Phase 1 / CT-0428-40 universal queue-requery hooks — see
# plans/dir-009/DOCTRINE_AGENT_QUEUE_REQUERY_v1.md
#
# Inputs (env, optional):
#   AGENT_NAME — defaults to "titan"
#   TITAN_SESSION_DIR — destination for NEXT_TASK.md (defaults to ~/titan-session)
#   POST_SHIP_TAG — the tag that triggered this hook (logged for audit)
#
# Idempotent: safe to call multiple times per ship. No external state mutation
# beyond NEXT_TASK.md rewrite.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_NAME="${AGENT_NAME:-titan}"
SESSION_DIR="${TITAN_SESSION_DIR:-$HOME/${AGENT_NAME}-session}"
TAG="${POST_SHIP_TAG:-unknown}"

mkdir -p "$SESSION_DIR"
LOG="$SESSION_DIR/post-ship-hook.log"

if [ -f "$SCRIPT_DIR/../lib/titan-env.sh" ]; then
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/../lib/titan-env.sh"
fi

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

echo "[$(ts)] post-ship-hook fired: agent=$AGENT_NAME tag=$TAG" >> "$LOG"

# Re-query MCP via the queue-requery helper. Falls through silently if MCP is
# unreachable — the agent's next claim cycle will still hit MCP directly.
QUERY_HELPER="$SCRIPT_DIR/../lib/queue_requery.py"
if [ -x "$QUERY_HELPER" ] || [ -f "$QUERY_HELPER" ]; then
  python3 "$QUERY_HELPER" --agent "$AGENT_NAME" --output "$SESSION_DIR/NEXT_TASK.md" \
    >> "$LOG" 2>&1 || echo "[$(ts)] queue_requery failed (non-fatal)" >> "$LOG"
else
  echo "[$(ts)] WARN: lib/queue_requery.py missing — skipping refresh" >> "$LOG"
fi

exit 0
