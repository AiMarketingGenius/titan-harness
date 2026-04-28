#!/usr/bin/env bash
# gemini-setup.sh — verify Gemini API key wiring + smoke test against AI Studio.
#
# Usage:
#   bin/gemini-setup.sh                 # verify only (no key arg)
#   bin/gemini-setup.sh <API_KEY>       # write key to all three env vars, then verify
#
# The canonical env file is ~/.titan-env (loaded by lib/titan-env.sh).
# Three env vars are set because lib/grader.py falls back in order:
#   GEMINI_API_KEY_AMG_GRADER → GEMINI_API_KEY_AIMG → GEMINI_API_KEY.

set -euo pipefail

ENV_FILE="$HOME/.titan-env"
KEY_ARG="${1:-}"

if [ -n "$KEY_ARG" ]; then
  if [[ ! "$KEY_ARG" =~ ^AIza[A-Za-z0-9_-]{35}$ ]]; then
    echo "ERROR: key doesn't match AI Studio pattern (AIza + 35 alphanumerics)." >&2
    echo "Are you pasting an AI Studio key, not a service account JSON or Vertex token?" >&2
    exit 2
  fi
  # Write/replace into ~/.titan-env, preserving 600 perms.
  for VAR in GEMINI_API_KEY_AMG_GRADER GEMINI_API_KEY_AIMG GEMINI_API_KEY; do
    if grep -q "^${VAR}=" "$ENV_FILE"; then
      # macOS sed -i requires empty suffix arg
      sed -i '' -e "s|^${VAR}=.*|${VAR}=${KEY_ARG}|" "$ENV_FILE"
    else
      echo "${VAR}=${KEY_ARG}" >> "$ENV_FILE"
    fi
  done
  chmod 600 "$ENV_FILE"
  echo "OK wrote key to $ENV_FILE (3 vars, 600 perms)"
fi

# Load env and verify
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

KEY="${GEMINI_API_KEY_AMG_GRADER:-${GEMINI_API_KEY_AIMG:-${GEMINI_API_KEY:-}}}"
if [ -z "$KEY" ]; then
  echo "Gemini key not set in $ENV_FILE. Rerun with: $0 <API_KEY>"
  exit 1
fi

echo "=== Gemini API smoke test ==="
# List models (cheap, confirms key + billing live)
HTTP=$(curl -s -o /tmp/gemini-models.json -w "%{http_code}" \
  "https://generativelanguage.googleapis.com/v1beta/models?key=${KEY}")
echo "GET /models → HTTP $HTTP"
if [ "$HTTP" != "200" ]; then
  echo "--- response body ---"
  cat /tmp/gemini-models.json
  echo
  case "$HTTP" in
    400) echo "Likely: malformed key" ;;
    403) echo "Likely: billing not enabled OR key restricted. Enable billing at https://aistudio.google.com → Get API key → Set up billing." ;;
    429) echo "Rate limited. Free tier quota hit — enable paid billing." ;;
    *)   echo "Unexpected error — check AI Studio console." ;;
  esac
  exit 3
fi
echo "models listed: $(python3 -c "import json;d=json.load(open('/tmp/gemini-models.json'));print(len(d.get('models',[])))")"

# Tiny generate call to confirm end-to-end path (billing + model access)
echo
echo "=== generate smoke test (gemini-2.5-flash) ==="
RESP=$(curl -s -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${KEY}" \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"parts":[{"text":"Reply with exactly: ok"}]}],"generationConfig":{"maxOutputTokens":10}}')
TEXT=$(echo "$RESP" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('candidates',[{}])[0].get('content',{}).get('parts',[{}])[0].get('text','<no text>')[:80])" 2>/dev/null || echo "<parse failed>")
echo "response: $TEXT"

echo
echo "=== PASS — Gemini API is live for Titan ==="
echo "Harness readers: lib/grader.py, lib/dual_grader.py (when enabled)"
