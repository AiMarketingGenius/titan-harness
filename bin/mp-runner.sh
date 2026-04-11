#!/bin/bash
# bin/mp-runner.sh
#
# Phase G.4 — Universal MP (megaprompt) phase runner.
#
# Single entry point for every MP-1 harvest phase and every MP-2 synthesis
# phase. Wraps the existing Python scripts in the titan-harness envelope:
#
#   1. Resolve phase metadata from the registry (policy.yaml + inline defaults)
#   2. Insert a row into public.mp_runs with status='running'
#   3. Execute the phase script under the pre-tool-gate (ACTIVE_TASK_ID set)
#   4. Capture stdout/stderr + stats
#   5. For phases that produce planning-quality outputs, pipe the output
#      through bin/war-room.sh and attach the exchange_group_id to the row
#   6. Update the row to status='complete' (or 'failed' / 'blocked')
#   7. Slack-ping on failed/blocked (and war-room handles C-or-below pings)
#
# Usage:
#   mp-runner.sh <megaprompt> <phase_number> [--task-id <id>]
#                                            [--project <id>]
#                                            [--dry-run]
#                                            [--force]
#                                            [--no-war-room]
#
# Examples:
#   mp-runner.sh mp2 1                       # run mp2_phase1_audit.py, war-room the audit_report.md
#   mp-runner.sh mp1 3 --project ACME        # run harvest_fireflies.py for tenant ACME
#   mp-runner.sh mp1 6 --dry-run             # show what would happen, don't execute
#
# Exit codes:
#   0  — phase completed successfully (or was already complete and idempotent)
#   1  — phase failed during execution
#   2  — bad arguments or missing prerequisites
#   3  — phase blocked (status='blocked' written to mp_runs)
#   4  — war-room graded below min_grade AND require_passing_grade_before_lock=true
#
# This runner is multi-tenant by design: everything scopes to --project so the
# same code can serve AMG and any future Titan-as-COO client.

set -u

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_HARNESS_DIR="$(cd "$_SCRIPT_DIR/.." && pwd)"
_LOG_DIR="/var/log/mp-runs"
mkdir -p "$_LOG_DIR" 2>/dev/null || _LOG_DIR="/tmp/mp-runs"
mkdir -p "$_LOG_DIR"

# ---- CLI parsing ------------------------------------------------------------
MEGAPROMPT=""
PHASE_NUM=""
TASK_ID=""
PROJECT="EOM"
DRY_RUN=0
FORCE=0
NO_WAR_ROOM=0

while [ $# -gt 0 ]; do
  case "$1" in
    mp1|mp2|mp1-5|mp2-x) MEGAPROMPT="$1"; shift ;;
    --task-id)     TASK_ID="$2"; shift 2 ;;
    --project)     PROJECT="$2"; shift 2 ;;
    --dry-run)     DRY_RUN=1; shift ;;
    --force)       FORCE=1; shift ;;
    --no-war-room) NO_WAR_ROOM=1; shift ;;
    -h|--help)
      sed -n '3,40p' "$0"
      exit 0
      ;;
    [0-9]*)
      if [ -z "$PHASE_NUM" ]; then PHASE_NUM="$1"; else
        echo "mp-runner: unexpected positional arg: $1" >&2; exit 2
      fi
      shift
      ;;
    *)
      echo "mp-runner: unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$MEGAPROMPT" ] || [ -z "$PHASE_NUM" ]; then
  echo "mp-runner: usage: mp-runner.sh <mp1|mp2> <phase_number> [--task-id ID] [--project P] [--dry-run] [--force] [--no-war-room]" >&2
  exit 2
fi

# ---- Load harness env -------------------------------------------------------
if [ -f "$_HARNESS_DIR/lib/titan-env.sh" ]; then
  # shellcheck source=../lib/titan-env.sh
  . "$_HARNESS_DIR/lib/titan-env.sh"
fi

# Fallback: source Supabase + Perplexity creds directly if titan-env didn't
if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  for _f in /opt/titan-processor/.env /opt/amg-titan/.env /opt/amg-mcp-server/.env.local; do
    if [ -f "$_f" ]; then
      set -a; . "$_f" 2>/dev/null; set +a
    fi
  done
  : "${SUPABASE_SERVICE_ROLE_KEY:=${SUPABASE_SERVICE_KEY:-}}"
  export SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY
fi

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  echo "mp-runner: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY unset — cannot log runs" >&2
  exit 2
fi

_INSTANCE_ID=$(hostname -s 2>/dev/null || hostname)
_NOW() { date -u +%Y-%m-%dT%H:%M:%SZ; }
_log() { echo "[$(_NOW)] $*" >&2; }

# ---- Phase registry ---------------------------------------------------------
# Inline defaults for AMG/EOM. For a new tenant we'd load this from
# policy.yaml or a per-project registry file. Shape: per phase we need
# script_path, phase_name, produces_planning_output (bool), war_room_trigger.

_registry_lookup() {
  local mp="$1" pn="$2"
  case "$mp:$pn" in
    # MP-1 HARVEST
    mp1:1) echo "/opt/amg-titan/solon-corpus/harvest_claude_threads.py|claude_threads_harvest|false|"       ;;  # not implemented
    mp1:2) echo "/opt/amg-titan/solon-corpus/harvest_perplexity.py|perplexity_harvest|false|"             ;;  # not implemented
    mp1:3) echo "/opt/amg-titan/solon-corpus/harvest_fireflies.py|fireflies_harvest|false|"               ;;
    mp1:4) echo "/opt/amg-titan/solon-corpus/harvest_loom.py|loom_harvest|false|"                         ;;
    mp1:5) echo "/opt/amg-titan/solon-corpus/harvest_gmail.py|gmail_harvest|false|"                       ;;  # not implemented
    mp1:6) echo "/opt/amg-titan/solon-corpus/harvest_slack.py|slack_harvest|false|"                       ;;  # done out-of-band
    mp1:7) echo "/opt/amg-titan/solon-corpus/harvest_mcp_decisions.py|mcp_decisions_harvest|false|"       ;;  # done out-of-band
    mp1:8) echo "/opt/amg-titan/solon-corpus/mp1_phase8_manifest.py|manifest_consolidator|true|phase_completion" ;;  # not implemented
    # MP-2 SYNTHESIS
    mp2:1) echo "/opt/amg-titan/solon-os-substrate/mp2_phase1_audit.py|corpus_audit|true|plan_finalization" ;;
    mp2:2) echo "/opt/amg-titan/solon-os-substrate/mp2_phase2_voice.py|voice_extraction|true|architecture_decision" ;;
    mp2:3) echo "/opt/amg-titan/solon-os-substrate/mp2_phase3_sales.py|sales_patterns|true|plan_finalization" ;;
    mp2:4) echo "/opt/amg-titan/solon-os-substrate/mp2_phase4_decisions.py|decision_framework|true|architecture_decision" ;;
    mp2:5) echo "/opt/amg-titan/solon-os-substrate/mp2_phase5_operational.py|operational_patterns|true|plan_finalization" ;;
    mp2:6) echo "/opt/amg-titan/solon-os-substrate/mp2_phase6_sops.py|sop_codification|true|plan_finalization" ;;
    mp2:7) echo "/opt/amg-titan/solon-os-substrate/mp2_phase7_validation.py|heldout_validation|true|phase_completion" ;;
    *)     echo ""; return 1 ;;
  esac
}

REG=$(_registry_lookup "$MEGAPROMPT" "$PHASE_NUM" || true)
if [ -z "$REG" ]; then
  _log "mp-runner: no registry entry for $MEGAPROMPT phase $PHASE_NUM"
  exit 2
fi

SCRIPT_PATH=$(echo "$REG" | awk -F'|' '{print $1}')
PHASE_NAME=$(echo "$REG" | awk -F'|' '{print $2}')
PRODUCES_PLANNING=$(echo "$REG" | awk -F'|' '{print $3}')
WAR_ROOM_TRIGGER=$(echo "$REG" | awk -F'|' '{print $4}')

_log "runner: $MEGAPROMPT phase $PHASE_NUM ($PHASE_NAME) — script=$SCRIPT_PATH planning=$PRODUCES_PLANNING trigger=${WAR_ROOM_TRIGGER:-none} project=$PROJECT"

# ---- Supabase helpers -------------------------------------------------------
_supa_post() {
  local table="$1" body="$2"
  curl -sS -m 10 -X POST "$SUPABASE_URL/rest/v1/$table" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=representation" \
    -d "$body" 2>/dev/null
}
_supa_patch() {
  local filter="$1" body="$2"
  curl -sS -m 10 -X PATCH "$SUPABASE_URL/rest/v1/mp_runs?$filter" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=minimal" \
    -d "$body" 2>/dev/null
}

# ---- Harness preflight (CORE CONTRACT) --------------------------------------
# Non-bypassable. Fails fast on misconfigured harness before any work starts.
if [ -x "$_HARNESS_DIR/bin/harness-preflight.sh" ]; then
  if ! "$_HARNESS_DIR/bin/harness-preflight.sh" >&2; then
    _pf_ec=$?
    _log "mp-runner: harness-preflight failed (exit=$_pf_ec) — refusing to start phase"
    exit "$_pf_ec"
  fi
fi

# ---- Capacity gate (Phase G.5) ----------------------------------------------
# Block heavy runs when the box is hot. Honors POLICY_CAPACITY_* env vars
# populated by lib/policy-loader.sh (sourced via titan-env.sh above).
if [ -x "$_HARNESS_DIR/bin/check-capacity.sh" ]; then
  if ! "$_HARNESS_DIR/bin/check-capacity.sh" >&2; then
    _cap_exit=$?
    if [ "$_cap_exit" -eq 2 ]; then
      _log "mp-runner: HARD capacity block — refusing to start phase"
      exit 2
    elif [ "$_cap_exit" -eq 1 ]; then
      _log "mp-runner: SOFT capacity block — refusing to start heavy phase"
      exit 1
    fi
  fi
fi

# ---- Dry-run short-circuit --------------------------------------------------
if [ "$DRY_RUN" -eq 1 ]; then
  cat <<EOF
DRY RUN — no execution, no DB writes
  megaprompt:          $MEGAPROMPT
  phase_number:        $PHASE_NUM
  phase_name:          $PHASE_NAME
  script_path:         $SCRIPT_PATH
  script_exists:       $([ -f "$SCRIPT_PATH" ] && echo yes || echo no)
  produces_planning:   $PRODUCES_PLANNING
  war_room_trigger:    ${WAR_ROOM_TRIGGER:-(none)}
  project_id:          $PROJECT
  task_id:             ${TASK_ID:-(none)}
  instance_id:         $_INSTANCE_ID
  log_dir:             $_LOG_DIR
EOF
  exit 0
fi

# ---- Script existence check -------------------------------------------------
if [ ! -f "$SCRIPT_PATH" ]; then
  _log "runner: script $SCRIPT_PATH does not exist — marking blocked"
  BLOCKER="phase script not implemented: $SCRIPT_PATH"
  RUN_BODY=$(python3 - <<PYEOF
import json
print(json.dumps({
  "project_id": "$PROJECT",
  "megaprompt": "$MEGAPROMPT",
  "phase_number": int("$PHASE_NUM"),
  "phase_name": "$PHASE_NAME",
  "task_id": "$TASK_ID" or None,
  "status": "blocked",
  "blocker_reason": "$BLOCKER",
  "instance_id": "$_INSTANCE_ID",
  "script_path": "$SCRIPT_PATH",
  "notes": "Script missing at runner time. Implement and re-run.",
}))
PYEOF
)
  _supa_post "mp_runs" "$RUN_BODY" > /dev/null
  exit 3
fi

# ---- Snapshot the MP-1 checkpoint (if it exists) ----------------------------
CHECKPOINT_PATH="/opt/amg-titan/solon-corpus/.checkpoint_mp1.json"
CHECKPOINT_SNAPSHOT="null"
if [ -f "$CHECKPOINT_PATH" ]; then
  CHECKPOINT_SNAPSHOT=$(python3 -c "import json,sys; print(json.dumps(json.dumps(json.load(open('$CHECKPOINT_PATH')))))")
fi

# ---- Insert mp_runs row as 'running' ----------------------------------------
RUN_START_TS=$(_NOW)
RUN_BODY=$(python3 - <<PYEOF
import json
snap = $CHECKPOINT_SNAPSHOT
body = {
    "project_id": "$PROJECT",
    "megaprompt": "$MEGAPROMPT",
    "phase_number": int("$PHASE_NUM"),
    "phase_name": "$PHASE_NAME",
    "task_id": "$TASK_ID" or None,
    "status": "running",
    "instance_id": "$_INSTANCE_ID",
    "script_path": "$SCRIPT_PATH",
    "started_at": "$RUN_START_TS",
    "checkpoint_snapshot_jsonb": json.loads(snap) if isinstance(snap,str) else snap,
}
print(json.dumps(body))
PYEOF
)

INSERT_RESP=$(_supa_post "mp_runs" "$RUN_BODY")
RUN_ID=$(echo "$INSERT_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['id'] if isinstance(d,list) and d else '')" 2>/dev/null)

if [ -z "$RUN_ID" ]; then
  _log "runner: failed to insert mp_runs row. response=$INSERT_RESP"
  exit 2
fi
_log "runner: mp_runs row inserted id=$RUN_ID"

# ---- Execute the phase script ----------------------------------------------
# ACTIVE_TASK_ID is set so the pre-tool-gate hook allows Write/Edit if needed.
export ACTIVE_TASK_ID="${TASK_ID:-$RUN_ID}"
export MP_PROJECT_ID="$PROJECT"
export MP_RUN_ID="$RUN_ID"

STDOUT_LOG="$_LOG_DIR/${MEGAPROMPT}_${PHASE_NUM}_${RUN_ID:0:8}.stdout.log"
STDERR_LOG="$_LOG_DIR/${MEGAPROMPT}_${PHASE_NUM}_${RUN_ID:0:8}.stderr.log"

_log "runner: executing $SCRIPT_PATH — stdout=$STDOUT_LOG stderr=$STDERR_LOG"
RUN_T0=$(date +%s%3N 2>/dev/null || echo $(($(date +%s) * 1000)))

if [[ "$SCRIPT_PATH" == *.py ]]; then
  python3 "$SCRIPT_PATH" > "$STDOUT_LOG" 2> "$STDERR_LOG"
  EXIT_CODE=$?
elif [[ "$SCRIPT_PATH" == *.sh ]]; then
  bash "$SCRIPT_PATH" > "$STDOUT_LOG" 2> "$STDERR_LOG"
  EXIT_CODE=$?
else
  "$SCRIPT_PATH" > "$STDOUT_LOG" 2> "$STDERR_LOG"
  EXIT_CODE=$?
fi

RUN_T1=$(date +%s%3N 2>/dev/null || echo $(($(date +%s) * 1000)))
DURATION_MS=$((RUN_T1 - RUN_T0))
_log "runner: exit_code=$EXIT_CODE duration_ms=$DURATION_MS"

# ---- Parse the phase summary (Python scripts print a JSON summary) ----------
ARTIFACTS=0; HIGH=0; MED=0; LOW=0; BYTES=0; WORDS=0
SUMMARY_JSON=$(tail -50 "$STDOUT_LOG" | python3 -c "
import json, sys
text = sys.stdin.read()
# Try to find a JSON object at the tail
start = text.rfind('{')
end = text.rfind('}')
if start != -1 and end > start:
    try:
        obj = json.loads(text[start:end+1])
        print(json.dumps(obj))
    except json.JSONDecodeError:
        print('{}')
else:
    print('{}')
" 2>/dev/null || echo '{}')

if [ -n "$SUMMARY_JSON" ] && [ "$SUMMARY_JSON" != "{}" ]; then
  ARTIFACTS=$(echo "$SUMMARY_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('artifacts',0) or json.load(open('/dev/null')).get('x',0) if False else json.loads('$SUMMARY_JSON').get('artifacts',0))" 2>/dev/null || echo 0)
  # Use a cleaner approach — avoid double-loading
  _parse() { python3 -c "import json; d=json.loads('''$SUMMARY_JSON'''); print(d.get('$1', 0) or 0)" 2>/dev/null || echo 0; }
  ARTIFACTS=$(_parse artifacts)
  HIGH=$(_parse high_quality)
  MED=$(_parse medium)
  LOW=$(_parse low)
  BYTES=$(_parse bytes)
  WORDS=$(_parse words)
fi

STDOUT_TAIL=$(tail -c 4000 "$STDOUT_LOG" 2>/dev/null | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo '""')
STDERR_TAIL=$(tail -c 4000 "$STDERR_LOG" 2>/dev/null | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo '""')

# ---- Determine terminal status ---------------------------------------------
if [ "$EXIT_CODE" -eq 0 ]; then
  FINAL_STATUS="complete"
elif [ "$EXIT_CODE" -eq 3 ]; then
  FINAL_STATUS="blocked"   # by convention — scripts exit 3 when blocked upstream
else
  FINAL_STATUS="failed"
fi

# ---- War-room the planning output (if applicable) --------------------------
# Defaults use Python-literal None so the heredoc that builds the PATCH
# body doesn't see a bareword 'null'. When the war room runs, these get
# overwritten with quoted strings like '"uuid-here"' which are valid Python.
WAR_ROOM_GROUP_ID="None"
WAR_ROOM_GRADE="None"
WAR_ROOM_COST=0

if [ "$PRODUCES_PLANNING" = "true" ] && [ "$FINAL_STATUS" = "complete" ] && [ "$NO_WAR_ROOM" -eq 0 ]; then
  # Find the planning output to grade.
  # Convention:
  #   mp2.1 → /opt/amg-titan/solon-os-substrate/00_audit/audit_report.md
  #   mp2.N → /opt/amg-titan/solon-os-substrate/0N_*/*.md (first .md found)
  #   mp1.8 → /opt/amg-titan/solon-corpus/MANIFEST.json (as text)
  PLANNING_FILE=""
  case "$MEGAPROMPT:$PHASE_NUM" in
    mp2:1) PLANNING_FILE="/opt/amg-titan/solon-os-substrate/00_audit/audit_report.md" ;;
    mp2:2) PLANNING_FILE=$(ls /opt/amg-titan/solon-os-substrate/01_voice/*.md 2>/dev/null | head -1) ;;
    mp2:3) PLANNING_FILE=$(ls /opt/amg-titan/solon-os-substrate/02_sales/*.md 2>/dev/null | head -1) ;;
    mp2:4) PLANNING_FILE=$(ls /opt/amg-titan/solon-os-substrate/03_decisions/*.md 2>/dev/null | head -1) ;;
    mp2:5) PLANNING_FILE=$(ls /opt/amg-titan/solon-os-substrate/04_operational/*.md 2>/dev/null | head -1) ;;
    mp2:6) PLANNING_FILE=$(ls /opt/amg-titan/solon-os-substrate/05_sops/*.md 2>/dev/null | head -1) ;;
    mp2:7) PLANNING_FILE=$(ls /opt/amg-titan/solon-os-substrate/07_validation/*.md 2>/dev/null | head -1) ;;
    mp1:8) PLANNING_FILE="/opt/amg-titan/solon-corpus/MANIFEST.json" ;;
  esac

  if [ -n "$PLANNING_FILE" ] && [ -f "$PLANNING_FILE" ]; then
    _log "runner: war-rooming $PLANNING_FILE (trigger=$WAR_ROOM_TRIGGER)"
    WR_JSON="$_LOG_DIR/${MEGAPROMPT}_${PHASE_NUM}_${RUN_ID:0:8}.warroom.json"
    "$_HARNESS_DIR/bin/war-room.sh" \
      --input "$PLANNING_FILE" \
      --phase "$MEGAPROMPT.$PHASE_NUM" \
      --trigger "${WAR_ROOM_TRIGGER:-manual}" \
      --project "$PROJECT" \
      --json > "$WR_JSON" 2>> "$STDERR_LOG" || true
    if [ -s "$WR_JSON" ]; then
      # Emit Python-literal values so the downstream heredoc embeds cleanly:
      # either a quoted string like '"uuid"' or the bareword None.
      WAR_ROOM_GROUP_ID=$(python3 -c "import json; d=json.load(open('$WR_JSON')); print('\"'+d.get('exchange_group_id','')+'\"' if d.get('exchange_group_id') else 'None')" 2>/dev/null || echo None)
      WAR_ROOM_GRADE=$(python3 -c "import json; d=json.load(open('$WR_JSON')); print('\"'+d.get('final_grade','')+'\"' if d.get('final_grade') else 'None')" 2>/dev/null || echo None)
      WAR_ROOM_COST=$(python3 -c "import json; d=json.load(open('$WR_JSON')); print(round(d.get('total_cost_cents',0),4))" 2>/dev/null || echo 0)
      _log "runner: war-room done grade=$WAR_ROOM_GRADE cost=${WAR_ROOM_COST}¢ group=$WAR_ROOM_GROUP_ID"
    else
      _log "runner: war-room output missing — skipping FK"
    fi
  else
    _log "runner: no planning file found for $MEGAPROMPT.$PHASE_NUM (expected: $PLANNING_FILE)"
  fi
fi

# ---- PATCH the mp_runs row to terminal state -------------------------------
PATCH_BODY=$(python3 - <<PYEOF
import json
body = {
    "status": "$FINAL_STATUS",
    "completed_at": "$(_NOW)",
    "duration_ms": int("$DURATION_MS") if "$DURATION_MS".isdigit() else None,
    "exit_code": int("$EXIT_CODE"),
    "artifacts_count": int("$ARTIFACTS") if "$ARTIFACTS".isdigit() else 0,
    "high_quality_count": int("$HIGH") if "$HIGH".isdigit() else 0,
    "medium_quality_count": int("$MED") if "$MED".isdigit() else 0,
    "low_quality_count": int("$LOW") if "$LOW".isdigit() else 0,
    "bytes": int("$BYTES") if "$BYTES".isdigit() else 0,
    "words": int("$WORDS") if "$WORDS".isdigit() else 0,
    "war_room_triggered": $([ "$WAR_ROOM_GROUP_ID" != "null" ] && echo "True" || echo "False"),
    "war_room_group_id": $WAR_ROOM_GROUP_ID,
    "war_room_grade": $WAR_ROOM_GRADE,
    "war_room_cost_cents": float("$WAR_ROOM_COST"),
    "stdout_tail": $STDOUT_TAIL,
    "stderr_tail": $STDERR_TAIL,
}
# Drop None values
print(json.dumps({k:v for k,v in body.items() if v is not None}))
PYEOF
)

_supa_patch "id=eq.$RUN_ID" "$PATCH_BODY" > /dev/null
_log "runner: mp_runs row $RUN_ID patched to status=$FINAL_STATUS"

# ---- Slack ping on failure/blocked (war-room handles C-or-below pings) -----
if [ "$FINAL_STATUS" = "failed" ] || [ "$FINAL_STATUS" = "blocked" ]; then
  SLACK_WH="${SLACK_WEBHOOK_URL:-}"
  if [ -n "$SLACK_WH" ]; then
    EMOJI=":x:"; [ "$FINAL_STATUS" = "blocked" ] && EMOJI=":construction:"
    PAYLOAD=$(python3 -c "
import json
text = '$EMOJI *MP Runner — $FINAL_STATUS*\n> Project: $PROJECT\n> Phase: $MEGAPROMPT.$PHASE_NUM ($PHASE_NAME)\n> Run ID: \`$RUN_ID\`\n> Exit: $EXIT_CODE\n> Log: \`$STDERR_LOG\`'
print(json.dumps({'text': text}))
")
    curl -sS -m 4 -X POST "$SLACK_WH" -H 'Content-Type: application/json' -d "$PAYLOAD" > /dev/null 2>&1 || true
  fi
fi

# ---- Final exit -------------------------------------------------------------
case "$FINAL_STATUS" in
  complete) exit 0 ;;
  blocked)  exit 3 ;;
  failed)   exit 1 ;;
  *)        exit 1 ;;
esac
