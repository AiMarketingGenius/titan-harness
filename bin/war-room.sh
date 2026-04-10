#!/bin/bash
# bin/war-room.sh — CLI wrapper around lib/war_room.py
#
# Phase G.3. Grades Titan output via Perplexity sonar-pro and (if grade
# < min_acceptable) auto-refines via Claude Haiku, up to max_refinement_rounds.
# Every round logged to Supabase public.war_room_exchanges.
#
# Usage:
#   war-room.sh --phase G.3 --trigger phase_completion --input out.md
#   cat plan.md | war-room.sh --phase MP-1 --trigger plan_finalization --output refined.md
#   war-room.sh --phase G.3 --trigger architecture_decision -i spec.md --json
#
# Exit codes:
#   0 — ran successfully (grade may still be low unless --exit-nonzero-on-fail)
#   1 — final grade < min_acceptable_grade AND --exit-nonzero-on-fail passed
#   2 — bad arguments or I/O error
#
# Behavior if war_room.enabled=false in policy.yaml:
#   Prints a skip notice to stderr, copies --input to --output unchanged,
#   and exits 0. This lets callers wire it into pipelines unconditionally.

set -u

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_HARNESS_DIR="$(cd "$_SCRIPT_DIR/.." && pwd)"
_LIB_PY="$_HARNESS_DIR/lib/war_room.py"

if [ ! -f "$_LIB_PY" ]; then
  echo "war-room.sh: lib/war_room.py not found at $_LIB_PY" >&2
  exit 2
fi

# Load harness env (Supabase + Perplexity + policy exports)
if [ -f "$_HARNESS_DIR/lib/titan-env.sh" ]; then
  # shellcheck source=../lib/titan-env.sh
  . "$_HARNESS_DIR/lib/titan-env.sh"
fi

# Also pull PERPLEXITY_API_KEY and ANTHROPIC_API_KEY from fallback envs
# if not already exported (war_room.py does this too, but we want the CLI
# to fail loudly and early instead of waiting for a 0-grade response).
if [ -z "${PERPLEXITY_API_KEY:-}" ]; then
  for _f in \
      /opt/titan-processor/.env \
      /opt/amg-mcp-server/.env.local \
      /opt/amg-titan/.env \
      "$HOME/.titan-env"; do
    if [ -f "$_f" ]; then
      _k=$(grep -E '^PERPLEXITY_API_KEY=' "$_f" 2>/dev/null \
           | head -1 | cut -d= -f2- | tr -d '"'"'")
      if [ -n "$_k" ]; then
        export PERPLEXITY_API_KEY="$_k"
        break
      fi
    fi
  done
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  for _f in \
      /opt/titan-processor/.env \
      /opt/amg-mcp-server/.env.local \
      /opt/amg-titan/.env \
      "$HOME/.titan-env"; do
    if [ -f "$_f" ]; then
      _k=$(grep -E '^ANTHROPIC_API_KEY=' "$_f" 2>/dev/null \
           | head -1 | cut -d= -f2- | tr -d '"'"'")
      if [ -n "$_k" ]; then
        export ANTHROPIC_API_KEY="$_k"
        break
      fi
    fi
  done
fi

# Early hard fail — no Perplexity key = no war room.
# BUT allow --help / -h to pass through so argparse can show usage.
_wants_help=0
for _a in "$@"; do
  case "$_a" in
    -h|--help) _wants_help=1 ;;
  esac
done

if [ "$_wants_help" -eq 0 ] && [ -z "${PERPLEXITY_API_KEY:-}" ]; then
  echo "war-room.sh: PERPLEXITY_API_KEY not found in env or any fallback .env" >&2
  echo "             checked: /opt/titan-processor/.env /opt/amg-mcp-server/.env.local /opt/amg-titan/.env ~/.titan-env" >&2
  exit 2
fi

# Delegate to python. All argv forwarded.
exec python3 "$_LIB_PY" "$@"
