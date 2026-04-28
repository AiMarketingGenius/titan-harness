#!/bin/bash
# titan-harness/bin/alexandria-preflight.sh
#
# Library of Alexandria placement check: warns when doctrine files
# (Markdown) land outside the approved tree per CORE_CONTRACT §0.5.
#
# Approved locations:
#   plans/                           — DRs, blueprints, control-loop, briefs
#   baselines/                       — perf + capacity baselines
#   templates/                       — proposal templates, brand voice
#   library_of_alexandria/           — catalog manifests + promoted artifacts
#   docs/                            — architecture, megaprompts, source-of-truth
#   repo root                        — only for CORE_CONTRACT/CLAUDE/INVENTORY/
#                                       RADAR/README/RELAUNCH_*/SESSION_PROMPT/
#                                       IDEA_TO_EXECUTION_PIPELINE/ALEXANDRIA_INDEX
#   /opt/amg-titan/solon-corpus/     — harvested raw corpus (VPS only)
#
# Non-doctrine path classes (skipped, per CT-0428-38 Fix 2):
#   reports/                         — ops outputs / evidence packets / overnight runs
#   scratch/                         — WIP / drafts / scratch docs
#   migrations/                      — SQL/data migration notes (own lifecycle)
#   lib/, scripts/, bin/, sql/,      — code/tooling, not doctrine
#   hooks/, deploy/
#
# Runs as:
#   - a git pre-commit step (informational, WARN not BLOCK)
#   - on-demand: `bin/alexandria-preflight.sh`
#   - inside harness-preflight.sh as a non-blocking check
#
# Exit codes:
#   0 — clean (no violations)
#   1 — violations found (WARN printed to stderr; does NOT block commits by default)
#
# Set ALEXANDRIA_PREFLIGHT_STRICT=1 to exit 2 on violations (block commits).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT" || exit 0

# Use python helper for the actual scan (single source of truth)
OUTPUT=$(python3 "$REPO_ROOT/lib/alexandria.py" --preflight 2>&1)
EXIT=$?

echo "$OUTPUT" >&2

if [ "$EXIT" -ne 0 ]; then
  if [ "${ALEXANDRIA_PREFLIGHT_STRICT:-0}" = "1" ]; then
    echo "" >&2
    echo "⛔ ALEXANDRIA_PREFLIGHT_STRICT=1 — blocking commit." >&2
    echo "   Move the file(s) above into an approved location, or unset the env var." >&2
    exit 2
  fi
  echo "" >&2
  echo "⚠️  (warn only — commit not blocked. Set ALEXANDRIA_PREFLIGHT_STRICT=1 to block)" >&2
  exit 1
fi

exit 0
