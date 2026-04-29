#!/bin/bash
# phase-grade-hook.sh — DIR-009 interim phase grader (single-judge DeepSeek V4 Pro).
#
# Usage:
#   bash bin/phase-grade-hook.sh <phase_number> <artifact_path> [<artifact_path>...]
#
# Wraps lib/phase_gate.py. Reads /etc/amg/deepseek.env or ~/.titan-env for creds.
# $5/day budget cap enforced via the helper. Exit 0 = pass (composite >= 9.5 +
# no dim < 9.0). Exit 1 = fail. Exit 2 = error.
#
# Per Doctrine v1.4 + DIR-009 update 2026-04-29: this is the interim mechanism
# until Phase 12+13 ship /api/v1/judge/phase-grade. Once that endpoint is live,
# both Titan and Achilles harness hooks swap to dual-judge mode (≥9.3 + no
# dim < 9.0) using the same canonical engine.
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$REPO_ROOT/lib/phase_gate.py"

if [ ! -f "$HELPER" ]; then
  echo "phase-grade-hook: ERROR — lib/phase_gate.py missing" >&2
  exit 2
fi

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <phase_number> <artifact_path> [<artifact_path>...]" >&2
  exit 2
fi

PHASE="$1"; shift
ARTIFACTS=("$@")

# Source env so DEEPSEEK_API_KEY is set for the helper
[ -f /etc/amg/deepseek.env ] && set -a && source /etc/amg/deepseek.env && set +a
[ -f "$HOME/.titan-env" ] && set -a && source "$HOME/.titan-env" && set +a

python3 "$HELPER" \
  --phase "$PHASE" \
  --task "${PARENT_TASK_ID:-CT-0429-04}" \
  --artifacts "${ARTIFACTS[@]}" \
  --output-dir "$REPO_ROOT/plans/dir-009" \
  --vps-output-dir "/opt/amg-titan/reports/dir-009" \
  --threshold "${GRADE_THRESHOLD:-9.5}" \
  --model "${DEEPSEEK_MODEL:-deepseek-chat}" \
  --budget-cap-cents "${GRADE_BUDGET_CAP_CENTS:-500}"
