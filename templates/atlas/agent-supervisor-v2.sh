#!/usr/bin/env bash
# agent-supervisor-v2.sh — Atlas Factory CT-0427-98 (augmented).
# Replaces baseline v1 from CT-0427-97. Adds full Doc-2 governance hooks:
#   a) INSERT amg_shell_logs after every poll/run
#   b) Compute cost_usd from JSON usage block (or synthetic when no live invoker)
#   c) INSERT amg_cost_ledger BEFORE status update (NON-SKIPPABLE)
#   d) INSERT amg_artifact_registry status=draft
#   e) PATCH op_task_queue status='review' (NOT 'shipped' — shipped_gate_trigger blocks builders)
#   f) PATCH-01: do NOT drop cross-host flag. The amg_reviews INSERT by kimi_code
#      IS the wake signal for Achilles via Supabase Realtime.
#
# Marker line: SUPERVISOR UP v2 — used by acceptance-test grep.
#
# Invoke: bash ~/.claude/agent-supervisor.sh AGENT_NAME
set -euo pipefail

AGENT="${1:-${USER:-unknown}}"
HOMEDIR="${HOME:-/home/${AGENT}}"
CLAUDE_DIR="${HOMEDIR}/.claude"
LOG_DIR="${CLAUDE_DIR}/logs"
FLAG="${CLAUDE_DIR}/${AGENT}-wake.flag"
LOG="${LOG_DIR}/${AGENT}-supervisor.log"

# Supabase env — read-only, sourced from /etc/amg/supabase.env if readable.
SUPABASE_ENV="${SUPABASE_ENV:-/etc/amg-agents/atlas.env}"
[ -r "${SUPABASE_ENV}" ] && . "${SUPABASE_ENV}" 2>/dev/null || true

mkdir -p "${LOG_DIR}"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { printf '[%s] %s\n' "$(ts)" "$*" | tee -a "${LOG}"; }

psql_exec() {
  # Run a one-shot SQL via psql, suppressing connection chatter.
  if [ -z "${SUPABASE_DB_URL:-}" ]; then
    log "WARN no SUPABASE_DB_URL; skipping psql write: $*"
    return 0
  fi
  /usr/lib/postgresql/17/bin/psql "${SUPABASE_DB_URL}" -At -v ON_ERROR_STOP=1 -c "$1" 2>>"${LOG}" || {
    log "ERROR psql failed: $1"
    return 1
  }
}

shell_log() {
  local cmd="$1"; local stdout="${2:-}"; local exit_code="${3:-0}"; local task_id="${4:-NULL}"
  local stdout_esc; stdout_esc="$(printf '%s' "${stdout}" | sed "s/'/''/g" | head -c 500)"
  local cmd_esc; cmd_esc="$(printf '%s' "${cmd}" | sed "s/'/''/g")"
  local task_clause="NULL"
  if [ "${task_id}" != "NULL" ]; then task_clause="'${task_id}'"; fi
  psql_exec "INSERT INTO amg_shell_logs(task_id, agent, command, stdout_excerpt, exit_code) VALUES (${task_clause}, '${AGENT}', '${cmd_esc}', '${stdout_esc}', ${exit_code});" >/dev/null
}

cost_ledger() {
  local task_id="$1"; local model="$2"; local in_tok="$3"; local out_tok="$4"; local cost="$5"; local over="${6:-false}"
  psql_exec "INSERT INTO amg_cost_ledger(task_id, agent, model, input_tokens, output_tokens, cost_usd, over_budget) VALUES ('${task_id}', '${AGENT}', '${model}', ${in_tok}, ${out_tok}, ${cost}, ${over});" >/dev/null
}

artifact_register() {
  local task_id="$1"; local path="$2"; local hash="${3:-}"; local status="${4:-draft}"
  psql_exec "INSERT INTO amg_artifact_registry(task_id, builder_agent, artifact_path, artifact_hash, status) VALUES ('${task_id}', '${AGENT}', '${path}', NULLIF('${hash}',''), '${status}');" >/dev/null
}

set_review_status() {
  local task_id="$1"; local actual_cost="$2"
  psql_exec "UPDATE op_task_queue SET status='review', actual_cost_usd=${actual_cost}, last_heartbeat=NOW(), builder_agent='${AGENT}' WHERE task_id='${task_id}';" >/dev/null
}

claim_next() {
  # Look for an approved task assigned to this agent that isn't locked.
  psql_exec "
    UPDATE op_task_queue
    SET status='locked', locked_by='${AGENT}', locked_at=NOW(), started_at=NOW(),
        claimed_at=NOW(), last_heartbeat=NOW()
    WHERE task_id = (
      SELECT task_id FROM op_task_queue
      WHERE assigned_to='${AGENT}' AND status='approved' AND approval='pre_approved'
      ORDER BY created_at ASC LIMIT 1
      FOR UPDATE SKIP LOCKED
    )
    RETURNING task_id;
  " | head -1
}


# DeepSeek V4 Flash routing stub (CT-0428-08).
# Reads DEEPSEEK_API_KEY from /etc/amg-agents/atlas.env (mirrored from
# /etc/amg/deepseek.env via deploy script). Default model: deepseek-flash.
# For task_class in builder|decompose: route to DeepSeek; on non-200 fall back
# to Claude. Today this logs the routing decision; full HTTP invocation lands
# when the supervisor moves off synthetic cost (deferred from CT-0427-98).
route_model() {
  local task_id="$1"; local task_class="${2:-builder}"
  if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
    log "ROUTE task=${task_id} class=${task_class} model=claude reason=deepseek_key_unset"
    echo claude
    return 0
  fi
  case "${task_class}" in
    builder|decompose|status_synth)
      log "ROUTE task=${task_id} class=${task_class} model=deepseek-flash fallback=claude"
      echo deepseek-flash
      ;;
    review|gate|security_audit|production_deploy)
      log "ROUTE task=${task_id} class=${task_class} model=claude reason=premium_required"
      echo claude
      ;;
    *)
      log "ROUTE task=${task_id} class=${task_class} model=claude reason=default"
      echo claude
      ;;
  esac
}

process_task() {
  local TASK_ID="$1"
  local FLAG_BODY="${2:-}"
  log "PROCESS task=${TASK_ID} flag_body=${FLAG_BODY}"
  local TASK_CLASS="${TASK_CLASS:-builder}"
  local MODEL_CHOSEN; MODEL_CHOSEN="$(route_model "${TASK_ID}" "${TASK_CLASS}")"
  shell_log "model_router_choice" "model=${MODEL_CHOSEN} class=${TASK_CLASS}" 0 "${TASK_ID}"
  shell_log "process_task start" "claimed task=${TASK_ID}" 0 "${TASK_ID}"

  # In production: this would be `claude --print --output-format json '...'`.
  # Today we run in DRY mode: synthesize a minimal artifact + cost.
  local ARTIFACT="/tmp/${AGENT}-artifact-${TASK_ID}.txt"
  local CONTENT="hello world from atlas factory (agent=${AGENT}, task=${TASK_ID}, ts=$(ts))"
  printf '%s\n' "${CONTENT}" > "${ARTIFACT}"
  local ARTIFACT_HASH; ARTIFACT_HASH="$(sha256sum "${ARTIFACT}" | awk '{print $1}')"
  shell_log "synthetic artifact write" "path=${ARTIFACT} hash=${ARTIFACT_HASH}" 0 "${TASK_ID}"

  # Fake JSON usage block — replace with real `claude --print --output-format json` parse later.
  local IN_TOKENS=120
  local OUT_TOKENS=80
  local COST_USD="0.0050"
  local MODEL="kimi-k2.6-builder-baseline"

  # NON-SKIPPABLE: cost ledger first.
  cost_ledger "${TASK_ID}" "${MODEL}" "${IN_TOKENS}" "${OUT_TOKENS}" "${COST_USD}" "false"
  shell_log "amg_cost_ledger insert" "model=${MODEL} cost=${COST_USD}" 0 "${TASK_ID}"

  # Artifact registry (draft).
  artifact_register "${TASK_ID}" "${ARTIFACT}" "${ARTIFACT_HASH}" "draft"
  shell_log "amg_artifact_registry insert status=draft" "hash=${ARTIFACT_HASH}" 0 "${TASK_ID}"

  # Status -> review (NOT shipped — shipped_gate_trigger blocks non-gatekeeper).
  set_review_status "${TASK_ID}" "${COST_USD}"
  shell_log "op_task_queue PATCH status=review" "task=${TASK_ID}" 0 "${TASK_ID}"

  # PATCH-01 (CT-98 v3): no flag handoff needed — kimi_code reviewer-supervisor
  # polls op_task_queue WHERE status=review reviewer_agent=kimi_code directly.
  # The amg_reviews INSERT it eventually performs IS the wake signal.
  shell_log "review handoff (db-poll mode)" "task=${TASK_ID} reviewer waits for status=review" 0 "${TASK_ID}"
}

log "SUPERVISOR UP v2 agent=${AGENT} pid=$$ host=$(hostname) ts=$(ts)"
shell_log "supervisor boot v2" "agent=${AGENT} pid=$$" 0 NULL

while true; do
  if [ -f "${FLAG}" ]; then
    BODY="$(cat "${FLAG}" 2>/dev/null || echo '<empty>')"
    log "POLLED-WAKE body=${BODY}"
    rm -f "${FLAG}"

    # Try to claim and process.
    if [[ "${BODY}" =~ task=([A-Za-z0-9-]+) ]]; then
      TASK_ID="${BASH_REMATCH[1]}"
    else
      TASK_ID="$(claim_next || true)"
    fi
    if [ -n "${TASK_ID:-}" ]; then
      process_task "${TASK_ID}" "${BODY}"
    else
      log "no claimable task for ${AGENT}; idle"
      shell_log "supervisor idle" "no claimable task" 0 NULL
    fi
  fi
  sleep 3
done
