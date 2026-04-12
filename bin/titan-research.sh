#!/usr/bin/env bash
# bin/titan-research.sh
# Ironclad architecture §3.2 — Perplexity research-to-doctrine pipeline.
# Usage: titan-research.sh "<topic>" [directive_class]
#
# 1. Pull Perplexity sonar-pro (via lib/research_query.py, routed through model_router)
# 2. Save raw output to plans/research/YYYY-MM-DD_<slug>.md
# 3. Extract doctrine-relevant deltas via Haiku 4.5 (lib/doctrine_extractor.py)
# 4. Run harness-conflict-check.sh on the new file
# 5. Commit + trigger mirror
set -euo pipefail

HARNESS_DIR="${TITAN_HARNESS_DIR:-$HOME/titan-harness}"
TOPIC="${1:-}"
CLASS="${2:-RESEARCH}"

if [[ -z "$TOPIC" ]]; then
  echo "usage: titan-research.sh \"<topic>\" [class]" >&2
  exit 2
fi

SLUG=$(printf '%s' "$TOPIC" | tr '[:upper:] ' '[:lower:]-' | sed 's/[^a-z0-9-]//g' | cut -c1-60)
DATE=$(date +%Y-%m-%d)
REL_OUT="plans/research/${DATE}_${SLUG}.md"
OUT="$HARNESS_DIR/$REL_OUT"

echo "[RESEARCH] Topic: $TOPIC"
echo "[RESEARCH] Class: $CLASS"
echo "[RESEARCH] Output: $REL_OUT"

mkdir -p "$HARNESS_DIR/plans/research"

# 1. Pull Perplexity sonar-pro via model router.
python3 "$HARNESS_DIR/lib/research_query.py" \
  --topic "$TOPIC" \
  --model sonar-pro \
  --output "$OUT"

echo "[RESEARCH] Raw output saved: $REL_OUT"

# 2. Extract doctrine deltas.
python3 "$HARNESS_DIR/lib/doctrine_extractor.py" \
  --input "$OUT" \
  --class "$CLASS" \
  --harness "$HARNESS_DIR" || echo "[RESEARCH] doctrine_extractor had non-fatal errors"

# 3. Conflict check the new research file.
bash "$HARNESS_DIR/bin/harness-conflict-check.sh" "$REL_OUT" "$CLASS"

# 4. Commit + mirror.
cd "$HARNESS_DIR"
git add "plans/research/" 2>/dev/null || true
if git diff --cached --quiet; then
  echo "[RESEARCH] Nothing new to commit"
else
  git commit -m "[RESEARCH: $TOPIC] Raw pull + doctrine extract | $DATE"
  bash "$HARNESS_DIR/bin/trigger-mirror.sh" || true
fi

echo "[RESEARCH] Done. See $REL_OUT"
