#!/usr/bin/env bash
# bin/opa-guard.sh
# Gate #4 v1.2 — OPA-gated command wrapper.
#
# Usage:
#   opa-guard.sh --baseline <path> --incident <ID> -- <command...>
#
# Builds OPA input (cmd + baseline_sha256 + baseline_age_sec + incident_id
# + escape_hatch_all_green + chrony_synced), queries OPA, and:
#   - mode=audit    : logs decision to /var/log/amg/opa-decisions.jsonl; always exits 0
#   - mode=enforce  : exits 1 + alerts if policy denies
#
# Mode file: /etc/amg/opa-mode (audit | enforce)
# Exit 2 on usage error, 3 on OPA unreachable (fail-closed in enforce mode).

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE_FILE="/etc/amg/opa-mode"
LOG="/var/log/amg/opa-decisions.jsonl"
POLICY_DIR="${REPO}/opa/policies"

BASELINE=""
INCIDENT=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --baseline)  BASELINE="$2"; shift 2 ;;
        --incident)  INCIDENT="$2"; shift 2 ;;
        --)          shift; break ;;
        -h|--help)   sed -n '2,14p' "$0"; exit 0 ;;
        *) echo "opa-guard: unknown arg: $1" >&2; exit 2 ;;
    esac
done
CMD="$*"
[[ -z "$CMD" ]]       && { echo "opa-guard: command required after --" >&2; exit 2; }
[[ -z "$BASELINE" ]]  && { echo "opa-guard: --baseline required" >&2; exit 2; }
[[ -z "$INCIDENT" ]]  && { echo "opa-guard: --incident required" >&2; exit 2; }

MODE="$(cat "$MODE_FILE" 2>/dev/null || echo audit)"
BSHA=""
BAGE=99999
if [[ -f "$BASELINE" ]]; then
    BSHA="$(shasum -a 256 "$BASELINE" 2>/dev/null | awk '{print $1}' || sha256sum "$BASELINE" | awk '{print $1}')"
    MT="$(stat -f %m "$BASELINE" 2>/dev/null || stat -c %Y "$BASELINE")"
    BAGE=$(( $(date +%s) - MT ))
fi

ESC_JSON="$("${REPO}/bin/escape-hatch-verify.sh" --json 2>/dev/null || echo '{"all_green":false}')"
ESC_GREEN="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('all_green', False))" "$ESC_JSON" 2>/dev/null || echo False)"
ESC_GREEN="$([[ "$ESC_GREEN" == "True" ]] && echo true || echo false)"

CHRONY_JSON="$("${REPO}/bin/opa-chrony-check.sh" --json 2>/dev/null || echo '{"ok":false}')"
CHRONY_OK="$(python3 -c "import json,sys; print(str(json.loads(sys.argv[1]).get('ok', False)).lower())" "$CHRONY_JSON" 2>/dev/null || echo false)"

INPUT="$(python3 -c "
import json, sys
print(json.dumps({
  'cmd': sys.argv[1],
  'baseline_sha256': sys.argv[2],
  'baseline_age_sec': int(sys.argv[3]),
  'incident_id': sys.argv[4],
  'escape_hatch_all_green': sys.argv[5] == 'true',
  'chrony_synced': sys.argv[6] == 'true',
  'mode': sys.argv[7],
}))
" "$CMD" "$BSHA" "$BAGE" "$INCIDENT" "$ESC_GREEN" "$CHRONY_OK" "$MODE")"

if ! command -v opa >/dev/null 2>&1; then
    # Fail-closed when OPA not installed in enforce mode
    if [[ "$MODE" == "enforce" ]]; then
        echo "opa-guard: opa binary not found — fail-closed in enforce" >&2
        exit 3
    fi
    ALLOW="null (opa not installed)"
else
    ALLOW="$(echo "$INPUT" | opa eval -d "$POLICY_DIR" -I 'data.amg.ssh.allow' -f pretty 2>/dev/null | tail -1 || echo false)"
fi

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mkdir -p "$(dirname "$LOG")" 2>/dev/null || true
python3 -c "
import json,sys
d={'ts':sys.argv[1],'mode':sys.argv[2],'allow':sys.argv[3],'input':json.loads(sys.argv[4])}
print(json.dumps(d))
" "$TS" "$MODE" "$ALLOW" "$INPUT" >> "$LOG" 2>/dev/null || true

if [[ "$MODE" == "enforce" && "$ALLOW" != "true" ]]; then
    echo "opa-guard: DENY ($ALLOW) — cmd='$CMD'" >&2
    python3 - <<PY 2>/dev/null || true
import sys, os
sys.path.insert(0, "${REPO}/lib")
try:
    from aristotle_slack import post_to_channel
    post_to_channel("#titan-aristotle", f":no_entry: Gate #4 ENFORCE DENY — {os.environ.get('CMD','?')[:200]}")
except Exception: pass
PY
    exit 1
fi

# allowed (or audit mode): run the command
eval "$CMD"
