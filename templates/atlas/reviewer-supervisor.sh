#!/usr/bin/env bash
# reviewer-supervisor.sh — Atlas Factory CT-0427-98 v3 (kimi_code lane).
# Replaces flag-handoff with DB-poll per PATCH-01 design intent: builders set
# op_task_queue.status='review'; this reviewer polls and INSERTs amg_reviews.
# That INSERT IS the wake signal Achilles's Mac receiver listens for via
# Supabase Realtime — no flag drop, no SSH, no Tailscale.
#
# Marker: REVIEWER UP v2 — used by acceptance-test grep.
set -euo pipefail

AGENT="${1:-${USER:-kimi_code}}"
HOMEDIR="${HOME:-/home/${AGENT}}"
CLAUDE_DIR="${HOMEDIR}/.claude"
LOG_DIR="${CLAUDE_DIR}/logs"
LOG="${LOG_DIR}/${AGENT}-supervisor.log"

SUPABASE_ENV="${SUPABASE_ENV:-/etc/amg-agents/atlas.env}"
[ -r "${SUPABASE_ENV}" ] && . "${SUPABASE_ENV}" 2>/dev/null || true

mkdir -p "${LOG_DIR}"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { printf '[%s] %s\n' "$(ts)" "$*" | tee -a "${LOG}"; }

PSQL=/usr/lib/postgresql/17/bin/psql

psql_exec() {
  if [ -z "${SUPABASE_DB_URL:-}" ]; then
    log "WARN no SUPABASE_DB_URL; skipping: $1"
    return 0
  fi
  "${PSQL}" "${SUPABASE_DB_URL}" -At -v ON_ERROR_STOP=1 -c "$1" 2>>"${LOG}" || {
    log "ERROR psql failed: $1"
    return 1
  }
}

shell_log() {
  local cmd="$1"; local stdout="${2:-}"; local task_id="${3:-NULL}"
  local stdout_esc; stdout_esc="$(printf '%s' "${stdout}" | sed "s/'/''/g" | head -c 500)"
  local cmd_esc; cmd_esc="$(printf '%s' "${cmd}" | sed "s/'/''/g")"
  local task_clause="NULL"
  if [ "${task_id}" != "NULL" ]; then task_clause="'${task_id}'"; fi
  psql_exec "INSERT INTO amg_shell_logs(task_id, agent, command, stdout_excerpt, exit_code) VALUES (${task_clause}, '${AGENT}', '${cmd_esc}', '${stdout_esc}', 0);" >/dev/null
}

review_task() {
  local TASK_ID="$1"; local BUILDER_AGENT="$2"; local ARTIFACT="$3"
  log "REVIEW task=${TASK_ID} builder=${BUILDER_AGENT} artifact=${ARTIFACT}"

  local FILE_OK="false" CONTENT_OK="false"
  if [ -n "${ARTIFACT}" ] && [ -f "${ARTIFACT}" ]; then
    FILE_OK="true"
    if grep -q "hello world from atlas factory" "${ARTIFACT}" 2>/dev/null; then
      CONTENT_OK="true"
    fi
  fi

  local VERDICT="REVISE"
  local RATIONALE="file_exists=${FILE_OK} content_match=${CONTENT_OK}"
  if [ "${FILE_OK}" = "true" ] && [ "${CONTENT_OK}" = "true" ]; then
    VERDICT="PASS"
  fi
  log "verdict=${VERDICT} rationale=${RATIONALE}"

  psql_exec "INSERT INTO amg_reviews(task_id, builder_agent, reviewer_agent, verdict, rationale, proof_spec_passed) VALUES ('${TASK_ID}', '${BUILDER_AGENT}', '${AGENT}', '${VERDICT}', '${RATIONALE}', ${CONTENT_OK});" >/dev/null
  shell_log "amg_reviews INSERT" "task=${TASK_ID} verdict=${VERDICT}" "${TASK_ID}"
  log "amg_reviews INSERTED — Realtime wake signal sent for Achilles Mac receiver"
}

poll_review_queue() {
  if [ -z "${SUPABASE_DB_URL:-}" ]; then return 0; fi
  # Find tasks status=review reviewer_agent=this with no existing review.
  "${PSQL}" "${SUPABASE_DB_URL}" -At -F '|' -v ON_ERROR_STOP=1 -c "
    SELECT q.task_id, q.builder_agent, COALESCE(a.artifact_path,'')
    FROM op_task_queue q
    LEFT JOIN LATERAL (
      SELECT artifact_path FROM amg_artifact_registry
      WHERE task_id = q.task_id AND builder_agent = q.builder_agent AND status='draft'
      ORDER BY ts DESC LIMIT 1
    ) a ON TRUE
    WHERE q.status='review'
      AND q.reviewer_agent='${AGENT}'
      AND NOT EXISTS (SELECT 1 FROM amg_reviews r WHERE r.task_id = q.task_id)
    ORDER BY q.last_heartbeat DESC NULLS LAST LIMIT 5;
  " 2>>"${LOG}" || true
}

log "REVIEWER UP v2 agent=${AGENT} pid=$$ host=$(hostname) ts=$(ts) mode=db-poll"
shell_log "reviewer boot v2" "agent=${AGENT} pid=$$ mode=db-poll" NULL

while true; do
  ROWS="$(poll_review_queue)"
  if [ -n "${ROWS}" ]; then
    while IFS='|' read -r TASK_ID BUILDER ARTIFACT; do
      [ -n "${TASK_ID}" ] || continue
      review_task "${TASK_ID}" "${BUILDER}" "${ARTIFACT}"
    done <<<"${ROWS}"
  fi
  sleep 3
done
