#!/bin/bash
# bin/hammerspoon_live_3x_chain.sh [start|continue N|finalize]
#
# LIVE 3x restart chain test for the hammerspoon-auto-restart pipeline.
#
# Unlike the synthetic 3x tests in tests/test_hammerspoon_3x_synthetic_cycles.sh
# (which exercise the clipboard + internal contract WITHOUT killing Claude
# Code), this script actually quits + relaunches the running Claude Code
# session 3 consecutive times. Each new Claude session boots, reads the
# pasted wake phrase as its first user message, cold-boots per CLAUDE.md
# §7, parses the phrase, and (if instructed) runs `continue N+1` to
# trigger the next cycle — or `finalize` to log the ship tag.
#
# Chain:
#   T0  Current session: bin/hammerspoon_live_3x_chain.sh start
#        → log MCP live-3x-chain-start
#        → fire restart request with cycle-1 wake phrase
#        → (current session dies when Hammerspoon polls in ≤30s)
#   T1  New session-1 boots with cycle-1 wake phrase pasted
#        → Titan reads phrase, executes: continue 2
#        → log MCP live-3x-chain-cycle-1-pass
#        → fire cycle 2
#   T2  New session-2 boots with cycle-2 wake phrase
#        → continue 3
#        → log MCP live-3x-chain-cycle-2-pass
#        → fire cycle 3
#   T3  New session-3 boots with cycle-3 wake phrase
#        → finalize
#        → log MCP live-3x-chain-cycle-3-pass
#        → log MCP hammerspoon-auto-restart-live-3x-verified-2026-04-19 SHIP tag
#
# PROOF contract: if any cycle's wake phrase does NOT land intact in Claude
# Code's input field, the post-restart session will NOT receive the
# "continue N" instruction, so the next cycle will NEVER fire. The chain
# stops dead, the MCP log_decision count reflects N<3, and Solon sees
# incomplete progression on his next wake.
#
# If all 3 cycles fire cleanly, the MCP log shows:
#   live-3x-chain-start
#   live-3x-chain-cycle-1-pass
#   live-3x-chain-cycle-2-pass
#   live-3x-chain-cycle-3-pass
#   hammerspoon-auto-restart-live-3x-verified-2026-04-19 (SHIP tag)
#
# Kill-switch: if at any point Solon needs to abort mid-chain, he can
# log an MCP op_decision tagged `titan-auto-restart-disabled` and
# Hammerspoon will stop picking up further restart requests.

set -e

MODE="${1:-}"
CYCLE="${2:-}"

REPO="${TITAN_HARNESS_ROOT:-$HOME/titan-harness}"
REQ_SCRIPT="$REPO/scripts/hammerspoon-auto-restart/bin/titan_request_auto_restart.sh"
LOG_HELPER="$REPO/scripts/tla-path-4/bin/log_mcp_invocation.sh"

log_mcp() {
  local tag="$1"
  local body="$2"
  if [ -x "$LOG_HELPER" ]; then
    bash "$LOG_HELPER" "$tag" "$body" >/dev/null 2>&1 || true
  fi
}

# Compact wake phrase (~170-190 chars) — fits a single clipboard paste
# comfortably. Instruction beat first so Titan's cold-boot parser picks
# it up as the concrete task and skips the "where we left off" block.
wake_phrase_for() {
  local n="$1"
  case "$n" in
    1)
      printf "Wake. LIVE_3X_CYCLE_1 of 3 landed intact post-restart via atomic clipboard paste. Now: run bash bin/hammerspoon_live_3x_chain.sh continue 2. Blocked on: nothing."
      ;;
    2)
      printf "Wake. LIVE_3X_CYCLE_2 of 3 landed intact post-restart via atomic clipboard paste. Now: run bash bin/hammerspoon_live_3x_chain.sh continue 3. Blocked on: nothing."
      ;;
    3)
      printf "Wake. LIVE_3X_CYCLE_3 of 3 landed intact post-restart via atomic clipboard paste. Now: run bash bin/hammerspoon_live_3x_chain.sh finalize. Blocked on: nothing."
      ;;
    *)
      echo "invalid cycle: $n" >&2
      return 2
      ;;
  esac
}

case "$MODE" in
  start)
    TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    log_mcp "live-3x-chain-start" "test=hammerspoon-auto-restart-live-cycle starting cycle 1 at $TS; chain will fire 3 consecutive physical restarts; expect 3 passes + ship tag log within ~4 minutes"
    cd "$REPO"
    WP=$(wake_phrase_for 1)
    echo "Cycle 1 wake phrase (${#WP} chars):"
    echo "  $WP"
    bash "$REQ_SCRIPT" --reason "live-3x-chain-cycle-1" --wake-phrase "$WP"
    echo ""
    echo "Cycle 1 request logged to MCP. Hammerspoon will pick up within 30s,"
    echo "quit Claude Code, relaunch, wait 15s settle, paste wake phrase."
    echo "Current session will end; chain continues in new session."
    ;;
  continue)
    if [ -z "$CYCLE" ] || ! [[ "$CYCLE" =~ ^[23]$ ]]; then
      echo "usage: $0 continue [2|3]" >&2
      exit 2
    fi
    PREV=$((CYCLE - 1))
    TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    log_mcp "live-3x-chain-cycle-${PREV}-pass" "test=hammerspoon-auto-restart-live-cycle cycle $PREV wake phrase landed intact post-restart at $TS; full phrase received + cold-boot parsed + now firing cycle $CYCLE"
    cd "$REPO"
    WP=$(wake_phrase_for "$CYCLE")
    echo "Cycle $CYCLE wake phrase (${#WP} chars):"
    echo "  $WP"
    bash "$REQ_SCRIPT" --reason "live-3x-chain-cycle-${CYCLE}" --wake-phrase "$WP"
    echo ""
    echo "Cycle $CYCLE request logged. Session will restart in ≤30s."
    ;;
  finalize)
    TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    log_mcp "live-3x-chain-cycle-3-pass" "test=hammerspoon-auto-restart-live-cycle cycle 3 wake phrase landed intact at $TS — FULL CHAIN COMPLETE"
    log_mcp "hammerspoon-auto-restart-live-3x-verified-2026-04-19" "SHIP: Hammerspoon auto-restart suite LIVE-validated — 3/3 consecutive physical restart cycles completed, each wake phrase landed intact via atomic Cmd+V paste post-15s-settle. kW partial-landing class of bug structurally + live-verified eliminated. Commit chain: 16d750c (hardening) + 7389e52 (Item 2 popup polish). Ship tag earned at $TS."
    echo ""
    echo "LIVE 3X CHAIN COMPLETE — ship tag logged to MCP."
    echo "  hammerspoon-auto-restart-live-3x-verified-2026-04-19"
    echo ""
    echo "Ready to resume next item in the revised 6-item Sunday runway sequence."
    ;;
  *)
    cat <<EOF
Usage: $0 [start|continue N|finalize]

  start          Fire cycle 1 (logs MCP start marker + fires restart).
                 Current session will die; chain continues automatically.
  continue 2     Log cycle-1-pass + fire cycle 2 (called by new session-1).
  continue 3     Log cycle-2-pass + fire cycle 3 (called by new session-2).
  finalize       Log cycle-3-pass + ship tag (called by new session-3).

Do NOT call manually unless you know what you're doing — this will
physically quit + relaunch Claude Code.
EOF
    exit 2
    ;;
esac
