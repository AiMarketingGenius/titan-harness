#!/usr/bin/env bash
# bin/aimg-preserve-baseline.sh
# CT-0414-09 Phase A — preserve current AIMG memories (Supabase project
# gaybcxzrzfgvcqpkbeiq) as Phase 1 audit baseline for CT-0414-06 rebuild.
#
# Run this on the VPS (or from Mac via ssh). Reads Supabase creds from
# /root/.titan-env; never echoes key values.
#
# Output: /opt/amg/aimg/audit-evidence/phase1-baseline-YYYY-MM-DD.json
#         + phase1-baseline-YYYY-MM-DD-quality-verdict.md companion

set -euo pipefail

OUT_DIR="${AIMG_AUDIT_DIR:-/opt/amg/aimg/audit-evidence}"
DATE="$(date -u +%Y-%m-%d)"
OUT_JSON="${OUT_DIR}/phase1-baseline-${DATE}.json"
OUT_MD="${OUT_DIR}/phase1-baseline-${DATE}-quality-verdict.md"

# Load creds from /root/.titan-env (VPS) or a local .env override.
ENV_FILE="${TITAN_ENV_FILE:-/root/.titan-env}"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "aimg-preserve: creds file missing at $ENV_FILE — run from VPS or set TITAN_ENV_FILE" >&2
    exit 2
fi
set -a
# shellcheck disable=SC1090
source "$ENV_FILE" >/dev/null 2>&1
set +a

AIMG_PROJECT_REF="${AIMG_SUPABASE_PROJECT:-gaybcxzrzfgvcqpkbeiq}"
AIMG_URL="https://${AIMG_PROJECT_REF}.supabase.co"

# AIMG-specific keys may be separate from shared SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY.
# Convention: AIMG_SUPABASE_SERVICE_KEY overrides shared. Fall back to shared only if
# SUPABASE_URL matches AIMG_URL (otherwise we're hitting the wrong project).
KEY="${AIMG_SUPABASE_SERVICE_KEY:-}"
if [[ -z "$KEY" ]] && [[ "${SUPABASE_URL:-}" == "$AIMG_URL" ]]; then
    KEY="${SUPABASE_SERVICE_ROLE_KEY:-}"
fi
if [[ -z "$KEY" ]]; then
    echo "aimg-preserve: no AIMG-scoped Supabase key found." >&2
    echo "   expected env: AIMG_SUPABASE_SERVICE_KEY" >&2
    echo "   fallback:     SUPABASE_SERVICE_ROLE_KEY when SUPABASE_URL == $AIMG_URL" >&2
    exit 3
fi

mkdir -p "$OUT_DIR"

# Fetch ALL rows from memories table (expected ~8). Full column projection.
TMP_JSON="$(mktemp)"
trap 'rm -f "$TMP_JSON"' EXIT

HTTP_CODE=$(curl -sS -o "$TMP_JSON" -w "%{http_code}" \
    -H "apikey: $KEY" \
    -H "Authorization: Bearer $KEY" \
    -H "Accept: application/json" \
    "${AIMG_URL}/rest/v1/memories?select=*&order=created_at.asc")

if [[ "$HTTP_CODE" != "200" ]]; then
    echo "aimg-preserve: Supabase REST returned $HTTP_CODE" >&2
    head -5 "$TMP_JSON" >&2
    exit 4
fi

# Sanity-check: valid JSON + array
python3 -c "
import json, sys
d = json.load(open('$TMP_JSON'))
assert isinstance(d, list), 'expected JSON array'
print(f'aimg-preserve: fetched {len(d)} rows', file=sys.stderr)
" || { echo "aimg-preserve: invalid JSON response" >&2; exit 5; }

# Wrap with metadata envelope so the baseline is self-describing
python3 - "$TMP_JSON" "$AIMG_PROJECT_REF" "$DATE" > "$OUT_JSON" <<'PY'
import json, sys, os
from datetime import datetime, timezone
src, project, date = sys.argv[1], sys.argv[2], sys.argv[3]
rows = json.load(open(src))
envelope = {
    "baseline_id": f"aimg-phase1-{date}",
    "captured_at_utc": datetime.now(timezone.utc).isoformat(),
    "supabase_project_ref": project,
    "table": "memories",
    "row_count": len(rows),
    "context": "CT-0414-09 Phase A baseline evidence for CT-0414-06 AIMG audit. "
               "AIMG v0.1.0 post-install dogfood sample. Quality verdict in "
               "-quality-verdict.md companion file.",
    "memories": rows,
}
print(json.dumps(envelope, indent=2, sort_keys=True))
PY

# Quality verdict companion (EOM decision text, no creds, no paths beyond the
# file we just wrote)
cat > "$OUT_MD" <<EOF
# AIMG Phase 1 Baseline — Quality Verdict (${DATE})

Companion to \`phase1-baseline-${DATE}.json\`. Reference for CT-0414-06 audit.
EOM classification as of 2026-04-14 (memories captured during AIMG v0.1.0
install + dogfood session, Perplexity threads).

## Row counts by quality tier

| Tier | Count | Notes |
|---|---|---|
| High-quality | 1 | hybrid_memory_search MCP correction — the one row the free-tier extraction got right. |
| Hard bug | 1 | Regex pattern leakage stored as ACTION-typed memory content. Extraction captured the regex source itself (\`\|next step\|action item\|need to\|i.test(content))\`) as if it were extracted text. Blocks shipping free-tier extraction without fix. |
| Noise | 6 | SQL fragments + template headers misclassified as CORRECTION/ACTION. 0.75 confidence threshold not enforced or not scored accurately. |

## Critical findings for CT-0414-06 audit

1. **Confidence threshold not enforced.** Rows below 0.75 are being stored. Either the threshold check is missing, evaluated against the wrong field, or the confidence scorer is returning high values for non-sentence fragments.
2. **Regex source captured as content.** The extractor is writing its own internal patterns to the \`content\` column. Likely a string-interpolation or eval bug in the Tier 2 rule-based free-tier path.
3. **Type misclassification at extraction.** SQL and template content tagged CORRECTION/ACTION — the classifier is pattern-matching too loosely.

## Use-of-baseline guidance

- The full JSON in the companion file is the ground-truth evidence for Phase 1 of the CT-0414-06 audit.
- DO NOT modify rows in-place; copy out for analysis.
- When CT-0414-06 rebuild ships, re-capture a post-fix baseline with this same script and diff.

## Schema captured

All columns from the \`memories\` table are preserved (memory_id, content, embedding, source_stamp, memory_type, confidence, created_at, and any others). See JSON for canonical schema.
EOF

echo "aimg-preserve: wrote $OUT_JSON"
echo "aimg-preserve: wrote $OUT_MD"
