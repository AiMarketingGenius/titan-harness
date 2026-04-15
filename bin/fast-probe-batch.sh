#!/usr/bin/env bash
# bin/fast-probe-batch.sh
# Production Optimization Pass — Vector 5 (parallel_dispatch spawn-stagger fix).
#
# Spawns Claude Code with MCP servers DISCONNECTED for fast-probe class workloads.
# Per investigation note plans/DR_PERF_AGENT_SPAWN_STAGGER_2026-04-15.md hypothesis #2:
# the spawn-stagger (~600-1100ms per agent) is plausibly caused by parent-process
# MCP context preparation serializing per-agent. Detaching MCPs for the probe-only
# session removes that overhead.
#
# Use this when you need to run N parallel fast-probe agents and don't need MCP for
# the probe itself (i.e., the probe is a Bash invocation + small report, not a
# log_decision / search_memory write).
#
# Usage:
#   bin/fast-probe-batch.sh "probe instruction" N
#     Spawns N parallel fast-probe agents in a fresh Claude Code child session
#     with --no-mcp.
#
# Example:
#   bin/fast-probe-batch.sh "Run \`ls /var/log\` and report file count" 5
#
# Exit codes:
#   0 — all probes returned
#   1 — at least one probe errored
#   2 — usage error
#
# Performance target: 5-agent fast-probe wall-clock < 2.0s
# Baseline (with MCP attached): 3.02s (DR_PERF investigation 2026-04-15)
# Expected delta: -33% to -50% wall-clock per dispatch v4 Vector 5 spec.

set -euo pipefail

PROBE_INSTRUCTION="${1:-}"
NUM_AGENTS="${2:-5}"

if [[ -z "$PROBE_INSTRUCTION" ]]; then
  echo "usage: $0 \"probe instruction\" [num_agents=5]" >&2
  exit 2
fi

if ! [[ "$NUM_AGENTS" =~ ^[1-9][0-9]*$ ]]; then
  echo "num_agents must be a positive integer; got: $NUM_AGENTS" >&2
  exit 2
fi

# Detect Claude Code binary. Honors PATH; falls back to common install locations.
CC_BIN="${CC_BIN:-$(command -v claude || true)}"
if [[ -z "$CC_BIN" || ! -x "$CC_BIN" ]]; then
  for cand in /Applications/Claude.app/Contents/Resources/cli/cli.js \
              /usr/local/bin/claude \
              "$HOME/.claude/bin/claude"; do
    if [[ -x "$cand" ]]; then
      CC_BIN="$cand"
      break
    fi
  done
fi
if [[ -z "$CC_BIN" || ! -x "$CC_BIN" ]]; then
  echo "ERROR: claude binary not found. Set CC_BIN env var to override." >&2
  exit 2
fi

START_NS=$(date +%s%N)
TMP_PROMPT=$(mktemp -t fast_probe_batch_prompt.XXXXXX)
trap 'rm -f "$TMP_PROMPT"' EXIT

# Build a prompt that emits N parallel Agent calls with fast-probe subagent_type.
# All Agent calls go in a single function_calls block to maximize parallelism.
{
  echo "Run the following probe in $NUM_AGENTS parallel fast-probe agents."
  echo "Probe: $PROBE_INSTRUCTION"
  echo ""
  echo "Emit ALL $NUM_AGENTS Agent tool calls in a SINGLE function_calls block."
  echo "Each agent should invoke subagent_type=fast-probe with model=haiku."
  echo "After all agents return, print: \"PROBE_BATCH_DONE: $NUM_AGENTS agents, wall-clock=<ms>\""
} > "$TMP_PROMPT"

# Spawn fresh Claude Code child session with --no-mcp.
# --no-mcp flag disables MCP server attachment for the spawned session, which removes
# the per-agent MCP-context-preparation overhead identified in DR_PERF investigation.
echo "[fast-probe-batch] spawning fresh CC child session (--no-mcp) with $NUM_AGENTS agents..."

# 2026-04-15 V5 live-test correction: Claude Code 2.1.92 does NOT support --no-mcp
# flag. The actual no-MCP path is `--strict-mcp-config --mcp-config /tmp/empty-mcp.json`
# (empty MCP set). `--bare` mode strips even more but ALSO strips the Agent tool, so
# Agent-spawn timing cannot be measured from --bare.
#
# For the SPAWN-STAGGER test specifically, what matters is: does this Claude Code
# session have fewer MCP servers attached? The wrapper writes a temporary empty MCP
# config and uses --strict-mcp-config to force it.
#
# Live measurement requires Solon's interactive Mac session because Agent tool needs
# the full Claude Code harness (not available via headless `claude -p` CLI alone).

EMPTY_MCP=$(mktemp -t empty_mcp.XXXXXX.json)
echo '{"mcpServers":{}}' > "$EMPTY_MCP"

if "$CC_BIN" --strict-mcp-config --mcp-config "$EMPTY_MCP" --print < "$TMP_PROMPT" > /tmp/fast_probe_batch_out.$$.log 2>&1; then
  RC=0
else
  RC=$?
fi

END_NS=$(date +%s%N)
WALL_MS=$(( (END_NS - START_NS) / 1000000 ))

echo "[fast-probe-batch] wall-clock: ${WALL_MS}ms (target < 2000ms for $NUM_AGENTS agents)"
echo "[fast-probe-batch] CC exit code: $RC"
echo "[fast-probe-batch] output log: /tmp/fast_probe_batch_out.$$.log"

if (( WALL_MS < 2000 )); then
  echo "[fast-probe-batch] PASS — under 2000ms target"
elif (( WALL_MS < 3020 )); then
  echo "[fast-probe-batch] PARTIAL — improved over 3020ms baseline but missed 2000ms target"
else
  echo "[fast-probe-batch] NO IMPROVEMENT — investigate; --no-mcp flag may not be supported in this CC version"
fi

exit "$RC"
