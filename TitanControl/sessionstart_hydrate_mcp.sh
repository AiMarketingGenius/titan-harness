#!/bin/bash
# sessionstart_hydrate_mcp.sh — CT-0419-07 Step 1 (memory loop closure)
#
# Runs on every Claude Code SessionStart BEFORE mark_ready.
# Hydrates MCP state to ~/Library/Application Support/TitanControl/state/mcp_hydration.json
# + verifies the loop is intact (cross-session drift check against last_decision_snapshot.json).
#
# Exits non-zero + writes state="hydration_failed" to status.json on any failure so the
# mark_ready hook refuses to fire. Paranoid failure handling — no silent success.
#
# Env sources (first-wins):  ~/.titan-env  /opt/amg-titan/.env  ~/.config/titan/env
#
# Hook in ~/.claude/settings.json:
#   SessionStart → sessionstart_hydrate_mcp.sh (this) → sessionstart_mark_ready.sh → session-start.sh

set -u
umask 077

TC_DIR="${HOME}/Library/Application Support/TitanControl"
STATE_DIR="${TC_DIR}/state"
HYD_FILE="${STATE_DIR}/mcp_hydration.json"
# NOTE: write to hydrate_status.json not status.json — status.json is reserved
# for the TitanControl Unified Restart Handler state machine (killing/booting/alive/…).
STATUS_FILE="${STATE_DIR}/hydrate_status.json"
LAST_SNAP="${STATE_DIR}/last_decision_snapshot.json"
LOG_FILE="${STATE_DIR}/hydrate.log"
START_EPOCH=$(date +%s)

mkdir -p "$STATE_DIR"
touch "$LOG_FILE"

# Rotate log if >512KB
if [ -f "$LOG_FILE" ] && [ "$(wc -c <"$LOG_FILE")" -gt 524288 ]; then
  mv "$LOG_FILE" "${LOG_FILE}.1" 2>/dev/null
  : >"$LOG_FILE"
fi

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$LOG_FILE"; }

# Load env — source first file that exists (auto-export)
for f in "$HOME/.titan-env" "/opt/amg-titan/.env" "$HOME/.config/titan/env"; do
  if [ -f "$f" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$f" 2>/dev/null || true
    set +a
  fi
done

SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_KEY:-}}"
SUPABASE_URL="${SUPABASE_URL:-}"

write_status() {
  local state="$1"
  local err="${2:-}"
  local drift="${3:-false}"
  local ts
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  if ! python3 - "$STATUS_FILE" "$state" "$err" "$ts" "$drift" <<'PY' 2>/dev/null
import json, sys
path, state, err, ts, drift = sys.argv[1:6]
with open(path, "w") as f:
    json.dump({"state": state, "timestamp": ts, "error": err,
               "drift_detected": drift == "true"}, f, indent=2)
PY
  then
    printf '{"state":"%s","timestamp":"%s","error":"%s","drift_detected":%s}\n' \
      "$state" "$ts" "$err" "$drift" >"$STATUS_FILE" 2>/dev/null || true
  fi
}

post_slack() {
  local msg="$1"
  # Best-effort. No SLACK_WEBHOOK_OPS canonical yet (see CT-0419-05 rollup, Priority 2 item 5).
  # Fall back to MCP decision log via Supabase REST.
  if [ -n "${SLACK_WEBHOOK_OPS:-}" ]; then
    curl -s -m 3 -X POST "$SLACK_WEBHOOK_OPS" \
      -H 'Content-Type: application/json' \
      -d "{\"text\":\"$msg\"}" >/dev/null 2>&1 || true
  fi
  if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    local payload
    payload=$(python3 -c "import json,sys; print(json.dumps({'project_source':'titan','text':sys.argv[1],'rationale':'automated alert from sessionstart_hydrate_mcp.sh','tags':['mcp-integrity','hydration-alert','ct-0419-07']}))" "$msg")
    curl -s -m 3 -X POST "${SUPABASE_URL}/rest/v1/op_decisions" \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Content-Type: application/json" \
      -H "Prefer: return=minimal" \
      -d "$payload" >/dev/null 2>&1 || true
  fi
}

fail() {
  local msg="$1"
  log "HYDRATION_FAILED: $msg"
  write_status "hydration_failed" "$msg" "false"
  post_slack ":rotating_light: Titan hydration FAILED: $msg"
  exit 1
}

if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  fail "missing_supabase_creds"
fi

# Query 1: standing rules (table is `standing_rules`, not op_rules)
RULES_TMP=$(mktemp)
HTTP_CODE=$(curl -s -m 8 -w '%{http_code}' -o "$RULES_TMP" \
  "${SUPABASE_URL}/rest/v1/standing_rules?select=*&order=updated_at.desc&limit=50" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" 2>/dev/null) || HTTP_CODE=000
if [ "$HTTP_CODE" != "200" ]; then
  rm -f "$RULES_TMP"
  fail "rules_http_${HTTP_CODE}"
fi

# Query 2: sprint state EOM
SPRINT_TMP=$(mktemp)
HTTP_CODE=$(curl -s -m 8 -w '%{http_code}' -o "$SPRINT_TMP" \
  "${SUPABASE_URL}/rest/v1/op_sprint_state?project_id=eq.EOM&select=*&limit=1" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" 2>/dev/null) || HTTP_CODE=000
if [ "$HTTP_CODE" != "200" ]; then
  rm -f "$RULES_TMP" "$SPRINT_TMP"
  fail "sprint_http_${HTTP_CODE}"
fi

# Query 3: recent decisions (50 per task spec)
DEC_TMP=$(mktemp)
HTTP_CODE=$(curl -s -m 8 -w '%{http_code}' -o "$DEC_TMP" \
  "${SUPABASE_URL}/rest/v1/op_decisions?select=*&order=created_at.desc&limit=50" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" 2>/dev/null) || HTTP_CODE=000
if [ "$HTTP_CODE" != "200" ]; then
  rm -f "$RULES_TMP" "$SPRINT_TMP" "$DEC_TMP"
  fail "decisions_http_${HTTP_CODE}"
fi

END_EPOCH=$(date +%s)
LATENCY=$((END_EPOCH - START_EPOCH))

# Parse + validate + write mcp_hydration.json + drift check
DRIFT_FLAG=$(python3 - "$RULES_TMP" "$SPRINT_TMP" "$DEC_TMP" "$HYD_FILE" "$LAST_SNAP" "$LATENCY" <<'PY'
import json, sys, hashlib, datetime, os

rules_f, sprint_f, dec_f, out_f, snap_f, lat = sys.argv[1:]

def load(path):
    with open(path) as fp:
        return json.load(fp)

try:
    rules = load(rules_f)
    sprint = load(sprint_f)
    decs = load(dec_f)
except json.JSONDecodeError as e:
    print(f"JSON_FAIL:{e}", file=sys.stderr)
    sys.exit(2)

if not isinstance(rules, list) or not isinstance(decs, list):
    print("SCHEMA_FAIL", file=sys.stderr)
    sys.exit(3)

if not decs:
    print("EMPTY_DECISIONS", file=sys.stderr)
    sys.exit(4)

sprint_row = sprint[0] if sprint else None
sprint_hash = hashlib.sha256(
    json.dumps(sprint_row, sort_keys=True, default=str).encode()
).hexdigest()[:16]

last_dec_id = decs[0].get("id")

doc = {
    "hydrated_at": datetime.datetime.utcnow().isoformat() + "Z",
    "latency_seconds": int(lat),
    "counts": {
        "rules": len(rules),
        "sprint": 1 if sprint_row else 0,
        "decisions": len(decs),
    },
    "sprint_state_hash": sprint_hash,
    "last_decision_id": last_dec_id,
    "sprint": sprint_row,
    "rules": rules,
    "decisions": decs,
}

with open(out_f, "w") as f:
    json.dump(doc, f, indent=2, default=str)

drift = "false"
if os.path.exists(snap_f):
    try:
        with open(snap_f) as f:
            snap = json.load(f)
        prev_dec_id = snap.get("last_decision_id")
        current_ids = {d.get("id") for d in decs}
        if prev_dec_id and prev_dec_id not in current_ids:
            # Check wider window before declaring drift — fetch might just be 50-cap
            drift = "true"
            print(f"DRIFT_WARN prev={prev_dec_id} not in latest {len(current_ids)} decs",
                  file=sys.stderr)
    except (json.JSONDecodeError, OSError):
        pass

print(drift)
PY
)
PY_RC=$?

rm -f "$RULES_TMP" "$SPRINT_TMP" "$DEC_TMP"

case $PY_RC in
  0)  ;;
  2) fail "json_parse_fail" ;;
  3) fail "schema_mismatch" ;;
  4) fail "empty_decisions" ;;
  *) fail "python_rc_${PY_RC}" ;;
esac

# Widened drift verification — if initial 50-cap missed the prior id, expand to 200
# and re-check before alerting. Avoids false-positives on busy periods.
if [ "$DRIFT_FLAG" = "true" ]; then
  PREV_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("last_decision_id",""))' "$LAST_SNAP" 2>/dev/null)
  if [ -n "$PREV_ID" ]; then
    WIDE_TMP=$(mktemp)
    curl -s -m 8 -o "$WIDE_TMP" \
      "${SUPABASE_URL}/rest/v1/op_decisions?select=id&id=eq.${PREV_ID}" \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" 2>/dev/null
    FOUND=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len(d))' "$WIDE_TMP" 2>/dev/null || echo 0)
    rm -f "$WIDE_TMP"
    if [ "$FOUND" = "0" ]; then
      log "DRIFT_CONFIRMED prev_id=$PREV_ID not in MCP (widened query)"
      post_slack ":warning: Titan cross-session DRIFT: prior session decision id $PREV_ID not found in MCP. Possible data loss."
      write_status "context_loaded_with_drift" "drift_confirmed:${PREV_ID}" "true"
      exit 0
    else
      log "DRIFT_FALSE_POSITIVE prev_id=$PREV_ID visible on widened query"
      DRIFT_FLAG="false"
    fi
  fi
fi

write_status "context_loaded" "" "false"
log "HYDRATION_OK latency=${LATENCY}s decisions=$(python3 -c 'import json; print(json.load(open("'"$HYD_FILE"'"))["counts"]["decisions"])' 2>/dev/null)"
exit 0
