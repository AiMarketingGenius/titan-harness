#!/bin/bash
# DR-AMG-GOVERNANCE-01 — Data Retention Cleanup (v2, 2026-04-14)
#
# Rewritten per Blocker 1 fix in sql/009+010 v2: retention policy is now
# SELECTed from public.governance_retention_policy, NOT parsed from
# pg_description / COMMENT ON TABLE.
#
# Schedule: Weekly Sunday 04:00 UTC via /etc/cron.d/amg-governance
# Input:    governance_retention_policy (source of truth)
# Action:   DELETE from each table where <timestamp_column> < now() - INTERVAL '<retention_days> days'
# Safety:   skips rows where enabled=false; validates table_name against allow-list
# Log:      /var/log/amg/governance-retention.log
set -euo pipefail

LOG="/var/log/amg/governance-retention.log"
mkdir -p "$(dirname "$LOG")"

if [ -f /etc/amg/supabase.env ]; then
    # shellcheck disable=SC1091
    source /etc/amg/supabase.env
fi

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG"; }

: "${SUPABASE_DB_URL:?SUPABASE_DB_URL must be set via /etc/amg/supabase.env}"

log "=== Governance retention cleanup starting (policy-table driven) ==="

# Allow-list: only these tables are retention-managed. Guards against accidental
# DELETE on unrelated tables if someone maliciously inserts a bogus row into
# governance_retention_policy. Script will refuse any table_name not in this list.
ALLOWED_TABLES="governance_drift_scores governance_antipattern_events governance_redteam_results governance_baseline governance_health_scores"

# Pull enabled retention policies. Psql outputs pipe-separated for easy parsing.
POLICIES=$(psql "$SUPABASE_DB_URL" -Atq -F '|' <<'SQL'
SELECT table_name, retention_days, timestamp_column
FROM public.governance_retention_policy
WHERE enabled = true
ORDER BY table_name;
SQL
)

if [ -z "$POLICIES" ]; then
    log "WARN: no enabled retention policies found in governance_retention_policy"
    log "=== Retention cleanup finished (no-op) ==="
    exit 0
fi

total_deleted=0
while IFS='|' read -r table_name retention_days timestamp_column; do
    [ -z "$table_name" ] && continue

    # Allow-list check
    if ! echo " $ALLOWED_TABLES " | grep -q " $table_name "; then
        log "SKIP: $table_name not in allow-list (possible tampering)"
        continue
    fi

    # Validate timestamp_column shape (letters/digits/underscore only; no SQL injection)
    if [[ ! "$timestamp_column" =~ ^[a-z_][a-z0-9_]*$ ]]; then
        log "SKIP: $table_name has invalid timestamp_column='$timestamp_column'"
        continue
    fi

    # Validate retention_days is a positive integer
    if [[ ! "$retention_days" =~ ^[0-9]+$ ]] || [ "$retention_days" -le 0 ]; then
        log "SKIP: $table_name has invalid retention_days='$retention_days'"
        continue
    fi

    log "CLEANUP: $table_name ($timestamp_column < now() - $retention_days days)"

    # Parameterized via psql server-side. Identifiers are allow-listed + shape-checked;
    # values go through psql's variable substitution.
    deleted=$(psql "$SUPABASE_DB_URL" -Atq -v tbl="$table_name" -v col="$timestamp_column" -v days="$retention_days" <<'SQL' 2>>"$LOG"
\set tbl_ident :tbl
\set col_ident :col
SELECT format('DELETE FROM public.%I WHERE %I < now() - (%L || '' days'')::interval RETURNING 1', :'tbl', :'col', :'days') \gexec
SQL
)
    # Count rows deleted (psql \gexec returns the RETURNING rows; count by counting lines of '1')
    deleted_count=$(echo "$deleted" | grep -c '^1$' || true)
    log "  $table_name: deleted $deleted_count rows"
    total_deleted=$((total_deleted + deleted_count))
done <<< "$POLICIES"

log "=== Retention cleanup complete (total: $total_deleted rows deleted across all tables) ==="
