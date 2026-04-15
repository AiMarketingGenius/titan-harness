#!/usr/bin/env bash
# bin/enforcement-status.sh
# Gate #4 v1.4 — one-line enforcement-status reader.
#
# Reports current ENFORCEMENT state as one of:
#   audit           — Gate #4 OPA loaded, mode=audit (allow-with-warn on scope)
#   enforce         — Gate #4 OPA loaded, mode=enforce (deny on scope absent all guards)
#   reverting       — auto-revert-tick currently processing an abort within 7-day tail
#   auto-reverted   — last auto-revert-tick downgraded enforce→audit; state persists
#   unknown         — no mode file / OPA not installed / probe failed
#
# Exit codes:
#   0  — status printed (any state)
#   2  — probe failure (cannot reach VPS)
#
# Usage:
#   bin/enforcement-status.sh               # prints one line: "ENFORCEMENT: <state>"
#   bin/enforcement-status.sh --json        # machine-parseable JSON
#   bin/enforcement-status.sh --verbose     # adds mode_file, last_change_ts, auto_revert_ts
#
# v1.4 delta: adds pre_proposal_hash check to the probe (reports whether hash pool exists).

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VPS_HOST="${AMG_VPS_HOST:-root@170.205.37.148}"
VPS_PORT="${AMG_VPS_PORT:-2222}"
VPS_KEY="${AMG_VPS_KEY:-$HOME/.ssh/id_ed25519_amg}"
SSH_OPTS=(-4 -p "$VPS_PORT" -i "$VPS_KEY" -o ConnectTimeout=8 -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

JSON=0
VERBOSE=0
for a in "$@"; do
  case "$a" in
    --json)    JSON=1 ;;
    --verbose) VERBOSE=1 ;;
    -h|--help)
      sed -n '2,25p' "$0"
      exit 0
      ;;
  esac
done

# Remote probe: read /etc/amg/gate4.mode + /var/log/amg/opa-mode-changes.jsonl tail.
# Fails safe: missing files → state=unknown (not an error).
probe() {
  ssh "${SSH_OPTS[@]}" "$VPS_HOST" bash -s <<'REMOTE' 2>/dev/null
set -u
MODE_FILE="/etc/amg/gate4.mode"
CHANGE_LOG="/var/log/amg/opa-mode-changes.jsonl"
HASH_POOL="/etc/amg/approved-hashes.json"

STATE="unknown"
MODE_VAL=""
LAST_CHANGE=""
AUTO_REVERT_TS=""
HASH_POOL_SIZE=0

if [[ -f "$MODE_FILE" ]]; then
  MODE_VAL="$(tr -d '[:space:]' < "$MODE_FILE" | tr '[:upper:]' '[:lower:]')"
  case "$MODE_VAL" in
    audit)     STATE="audit" ;;
    enforce)   STATE="enforce" ;;
    reverting) STATE="reverting" ;;
  esac
fi

if [[ -f "$CHANGE_LOG" ]]; then
  LAST_LINE="$(tail -1 "$CHANGE_LOG" 2>/dev/null || echo '')"
  if [[ -n "$LAST_LINE" ]]; then
    LAST_CHANGE="$(echo "$LAST_LINE" | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('ts',''))" 2>/dev/null || echo '')"
    # Detect auto-reverted: last change was type=auto_revert AND mode is now audit
    LAST_TYPE="$(echo "$LAST_LINE" | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('type',''))" 2>/dev/null || echo '')"
    if [[ "$LAST_TYPE" == "auto_revert" ]] && [[ "$STATE" == "audit" ]]; then
      STATE="auto-reverted"
      AUTO_REVERT_TS="$LAST_CHANGE"
    fi
  fi
fi

if [[ -f "$HASH_POOL" ]]; then
  HASH_POOL_SIZE="$(python3 -c "import json; print(len(json.load(open('$HASH_POOL')).get('approved_hashes',[])))" 2>/dev/null || echo 0)"
fi

printf '%s|%s|%s|%s|%s\n' "$STATE" "$MODE_VAL" "$LAST_CHANGE" "$AUTO_REVERT_TS" "$HASH_POOL_SIZE"
REMOTE
}

RESULT="$(probe || true)"
if [[ -z "$RESULT" ]]; then
  if (( JSON == 1 )); then
    echo '{"state":"unknown","error":"probe_failed","ts_utc":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"}'
  else
    echo "ENFORCEMENT: unknown (probe failed — cannot reach $VPS_HOST:$VPS_PORT)"
  fi
  exit 2
fi

IFS='|' read -r STATE MODE_VAL LAST_CHANGE AUTO_REVERT_TS HASH_POOL_SIZE <<< "$RESULT"
STATE="${STATE:-unknown}"

if (( JSON == 1 )); then
  python3 - <<PY
import json
print(json.dumps({
    "state": "$STATE",
    "mode_file_value": "$MODE_VAL",
    "last_change_ts": "$LAST_CHANGE",
    "auto_revert_ts": "$AUTO_REVERT_TS",
    "hash_pool_size": int("${HASH_POOL_SIZE:-0}" or 0),
    "probed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "policy_version": "v1.4",
}, indent=2))
PY
  exit 0
fi

echo "ENFORCEMENT: $STATE"
if (( VERBOSE == 1 )); then
  echo "  mode_file_value: ${MODE_VAL:-<empty>}"
  echo "  last_change_ts:  ${LAST_CHANGE:-<none>}"
  echo "  auto_revert_ts:  ${AUTO_REVERT_TS:-<none>}"
  echo "  hash_pool_size:  ${HASH_POOL_SIZE:-0}"
  echo "  policy_version:  v1.4"
fi
