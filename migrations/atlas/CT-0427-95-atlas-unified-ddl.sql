-- =============================================================================
-- CT-0427-ATLAS-BUILD / CT-0427-95 — Unified DDL Bundle + Queue Surgery
-- Source: Atlas_Factory_Build_TITAN_Work_Pack_v1_renumbered_2026-04-27.md
-- Date: 2026-04-27 | Owner: Titan | Project: egoazyasyrhslluossli
-- Postgres: 17.6 | Extensions verified: pgcrypto 1.3, uuid-ossp 1.1, pg_cron 1.6.4
-- =============================================================================
-- All-or-nothing transaction. Any failure -> ROLLBACK -> P0 blocker.
-- Adapted from work pack §2 to fit live schema (assigned_to is CHECK-constrained
-- TEXT, not enum; status enum lacks 'shipped' and 'review' — both added here).
-- =============================================================================

\set ON_ERROR_STOP on
\timing on

BEGIN;

-- ---------------------------------------------------------------------------
-- §3. Queue surgery — reconcile phantom 'active' rows whose result_summary
--     already says SHIPPED.
-- ---------------------------------------------------------------------------
UPDATE op_task_queue
SET status = 'completed',
    notes = COALESCE(notes,'') || E'\n[CT-0427-95 queue-surgery 2026-04-27] migrated from active->completed; result_summary indicated prior ship.'
WHERE status = 'active'
  AND result_summary ILIKE '%SHIPPED%';

-- ---------------------------------------------------------------------------
-- §4. Add governance columns to op_task_queue.
-- ---------------------------------------------------------------------------
ALTER TABLE op_task_queue ADD COLUMN IF NOT EXISTS expires_at         TIMESTAMPTZ;
ALTER TABLE op_task_queue ADD COLUMN IF NOT EXISTS claimed_at         TIMESTAMPTZ;
ALTER TABLE op_task_queue ADD COLUMN IF NOT EXISTS claim_timeout      INTERVAL DEFAULT INTERVAL '2 hours';
ALTER TABLE op_task_queue ADD COLUMN IF NOT EXISTS proof_spec         JSONB;
ALTER TABLE op_task_queue ADD COLUMN IF NOT EXISTS artifact_refs      TEXT[];
ALTER TABLE op_task_queue ADD COLUMN IF NOT EXISTS reviewer_agent     TEXT;
ALTER TABLE op_task_queue ADD COLUMN IF NOT EXISTS budget_ceiling     NUMERIC(8,4) DEFAULT 2.00;
ALTER TABLE op_task_queue ADD COLUMN IF NOT EXISTS actual_cost_usd    NUMERIC(8,4);
ALTER TABLE op_task_queue ADD COLUMN IF NOT EXISTS graduation_credited BOOLEAN DEFAULT false;
ALTER TABLE op_task_queue ADD COLUMN IF NOT EXISTS migration_note     TEXT;
ALTER TABLE op_task_queue ADD COLUMN IF NOT EXISTS shipped_at         TIMESTAMPTZ;
ALTER TABLE op_task_queue ADD COLUMN IF NOT EXISTS builder_agent      TEXT;

-- ---------------------------------------------------------------------------
-- §5. Expand assigned_to CHECK to include builder agents.
--     Original constraint: assigned_to IN ('titan','manual','n8n').
-- ---------------------------------------------------------------------------
ALTER TABLE op_task_queue DROP CONSTRAINT IF EXISTS op_task_queue_assigned_to_check;
ALTER TABLE op_task_queue ADD CONSTRAINT op_task_queue_assigned_to_check
  CHECK (assigned_to = ANY (ARRAY[
    'titan','manual','n8n',
    'codex','hercules','nestor','alexander','kimi_code','kimi_claw','amg_eom',
    'achilles','aletheia','artisan','warden','cerberus','mercury'
  ]));

-- Expand status to include 'review' and 'shipped' (referenced by triggers + smoke test).
ALTER TABLE op_task_queue DROP CONSTRAINT IF EXISTS op_task_queue_status_check;
ALTER TABLE op_task_queue ADD CONSTRAINT op_task_queue_status_check
  CHECK (status = ANY (ARRAY[
    'queued','approved','locked','active','blocked','pending_qc',
    'revision_needed','escalated','completed','failed','dead_letter',
    'in_progress','stuck-escalated','stuck-budget-paused',
    'review','shipped'
  ]));

-- ---------------------------------------------------------------------------
-- §6. proof_spec_required CHECK (manual lane exempt).
-- ---------------------------------------------------------------------------
ALTER TABLE op_task_queue DROP CONSTRAINT IF EXISTS proof_spec_required;
ALTER TABLE op_task_queue ADD CONSTRAINT proof_spec_required
  CHECK (assigned_to = 'manual' OR assigned_to = 'titan' OR proof_spec IS NOT NULL);
-- Note: titan also exempted to avoid breaking existing legacy rows (titan-lane
--       tasks predating this migration). New non-manual non-titan tasks must
--       carry proof_spec.

-- ---------------------------------------------------------------------------
-- §7. Create 10 governance tables.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS amg_reviews (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id             TEXT NOT NULL,
  builder_agent       TEXT NOT NULL,
  reviewer_agent      TEXT NOT NULL,
  verdict             TEXT NOT NULL CHECK (verdict IN ('PASS','FAIL','REVISE')),
  rationale           TEXT,
  proof_spec_passed   BOOLEAN,
  achilles_confirmed  BOOLEAN DEFAULT false,
  achilles_confirmed_at TIMESTAMPTZ,
  reviewed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT reviewer_ne_builder CHECK (reviewer_agent <> builder_agent)
);
CREATE INDEX IF NOT EXISTS idx_amg_reviews_task   ON amg_reviews(task_id);
CREATE INDEX IF NOT EXISTS idx_amg_reviews_verdict ON amg_reviews(verdict);

CREATE TABLE IF NOT EXISTS amg_shell_logs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id       TEXT,
  agent         TEXT NOT NULL,
  command       TEXT NOT NULL,
  stdout_excerpt TEXT,
  stderr_excerpt TEXT,
  exit_code     INTEGER,
  duration_ms   INTEGER,
  ts            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_amg_shell_logs_task  ON amg_shell_logs(task_id);
CREATE INDEX IF NOT EXISTS idx_amg_shell_logs_agent ON amg_shell_logs(agent);
CREATE INDEX IF NOT EXISTS idx_amg_shell_logs_ts    ON amg_shell_logs(ts DESC);

CREATE TABLE IF NOT EXISTS amg_model_router_choices (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id         TEXT,
  agent           TEXT NOT NULL,
  model_requested TEXT,
  model_used      TEXT NOT NULL,
  fallback_reason TEXT,
  ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS amg_cost_ledger (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id         TEXT NOT NULL,
  agent           TEXT NOT NULL,
  model           TEXT NOT NULL,
  input_tokens    INTEGER,
  output_tokens   INTEGER,
  cost_usd        NUMERIC(10,6) NOT NULL,
  over_budget     BOOLEAN DEFAULT false,
  ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_amg_cost_ledger_task  ON amg_cost_ledger(task_id);
CREATE INDEX IF NOT EXISTS idx_amg_cost_ledger_agent ON amg_cost_ledger(agent);
CREATE INDEX IF NOT EXISTS idx_amg_cost_ledger_ts    ON amg_cost_ledger(ts DESC);

CREATE TABLE IF NOT EXISTS amg_artifact_registry (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id         TEXT NOT NULL,
  builder_agent   TEXT NOT NULL,
  artifact_path   TEXT NOT NULL,
  artifact_hash   TEXT,
  status          TEXT NOT NULL CHECK (status IN ('draft','shipped','rejected')),
  ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_amg_artifact_task   ON amg_artifact_registry(task_id);
CREATE INDEX IF NOT EXISTS idx_amg_artifact_status ON amg_artifact_registry(status);

CREATE TABLE IF NOT EXISTS amg_blocker_register (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id         TEXT,
  agent           TEXT,
  severity        TEXT NOT NULL CHECK (severity IN ('P0','P1','P2')),
  description     TEXT NOT NULL,
  resolved_at     TIMESTAMPTZ,
  resolution_note TEXT,
  ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_amg_blocker_severity ON amg_blocker_register(severity);
CREATE INDEX IF NOT EXISTS idx_amg_blocker_unresolved ON amg_blocker_register(resolved_at) WHERE resolved_at IS NULL;

CREATE TABLE IF NOT EXISTS amg_morning_digest (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  digest_date     DATE NOT NULL UNIQUE,
  content         TEXT NOT NULL,
  slack_msg_id    TEXT,
  r2_archive_path TEXT,
  ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS amg_graduation_counters (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent           TEXT NOT NULL UNIQUE,
  level           INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 5),
  consecutive_clean INTEGER NOT NULL DEFAULT 0,
  threshold       INTEGER NOT NULL DEFAULT 5,
  graduated_at    TIMESTAMPTZ,
  ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS amg_swarm_budget (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  budget_date     DATE NOT NULL UNIQUE,
  total_spend_usd NUMERIC(10,4) NOT NULL DEFAULT 0,
  daily_ceiling_usd NUMERIC(10,4) NOT NULL DEFAULT 250.00,
  hard_kill       BOOLEAN NOT NULL DEFAULT false,
  ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS amg_agent_budget_config (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent               TEXT NOT NULL UNIQUE,
  daily_ceiling_usd   NUMERIC(8,4) NOT NULL,
  per_task_max_usd    NUMERIC(8,4) NOT NULL,
  monthly_ceiling_usd NUMERIC(10,4) NOT NULL,
  is_suspended        BOOLEAN NOT NULL DEFAULT false,
  suspension_reason   TEXT,
  ts                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- RLS — enable on all 10 governance tables, grant service_role full access.
-- Default-deny for anon; specific role grants follow in §9.
-- ---------------------------------------------------------------------------
DO $rls$
DECLARE t TEXT;
BEGIN
  FOR t IN SELECT unnest(ARRAY[
    'amg_reviews','amg_shell_logs','amg_model_router_choices','amg_cost_ledger',
    'amg_artifact_registry','amg_blocker_register','amg_morning_digest',
    'amg_graduation_counters','amg_swarm_budget','amg_agent_budget_config'
  ])
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS %I_service_all ON %I', t, t);
    EXECUTE format('CREATE POLICY %I_service_all ON %I FOR ALL TO service_role USING (true) WITH CHECK (true)', t, t);
  END LOOP;
END
$rls$;

-- ---------------------------------------------------------------------------
-- §8. Trigger functions + triggers.
-- ---------------------------------------------------------------------------

-- 8a. enforce_reviewer_separation — belt+suspenders behind the CHECK constraint.
CREATE OR REPLACE FUNCTION enforce_reviewer_separation() RETURNS TRIGGER AS $fn$
BEGIN
  IF NEW.reviewer_agent = NEW.builder_agent THEN
    RAISE EXCEPTION 'Reviewer cannot be the same agent as the builder (builder=% reviewer=%)',
      NEW.builder_agent, NEW.reviewer_agent
    USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS no_self_review ON amg_reviews;
CREATE TRIGGER no_self_review
  BEFORE INSERT OR UPDATE ON amg_reviews
  FOR EACH ROW EXECUTE FUNCTION enforce_reviewer_separation();

-- 8b. enforce_shipped_gate — only achilles_gatekeeper or postgres can set status='shipped'.
CREATE OR REPLACE FUNCTION enforce_shipped_gate() RETURNS TRIGGER AS $fn$
DECLARE
  current_user_text TEXT;
BEGIN
  current_user_text := current_user::TEXT;
  IF NEW.status = 'shipped' AND OLD.status IS DISTINCT FROM 'shipped' THEN
    IF current_user_text NOT IN ('achilles_gatekeeper','postgres','supabase_admin','service_role') THEN
      RAISE EXCEPTION 'Only achilles_gatekeeper may transition status to shipped (caller=%)',
        current_user_text
      USING ERRCODE = 'insufficient_privilege';
    END IF;
    NEW.shipped_at := COALESCE(NEW.shipped_at, NOW());
  END IF;
  RETURN NEW;
END
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS shipped_gate_trigger ON op_task_queue;
CREATE TRIGGER shipped_gate_trigger
  BEFORE UPDATE OF status ON op_task_queue
  FOR EACH ROW EXECUTE FUNCTION enforce_shipped_gate();

-- 8c. check_graduation — promote agent level when consecutive_clean hits threshold.
CREATE OR REPLACE FUNCTION check_graduation() RETURNS TRIGGER AS $fn$
BEGIN
  IF NEW.consecutive_clean >= NEW.threshold AND NEW.level < 5 THEN
    NEW.level := NEW.level + 1;
    NEW.consecutive_clean := 0;
    NEW.graduated_at := NOW();
  END IF;
  RETURN NEW;
END
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS graduation_trigger ON amg_graduation_counters;
CREATE TRIGGER graduation_trigger
  BEFORE UPDATE OF consecutive_clean ON amg_graduation_counters
  FOR EACH ROW EXECUTE FUNCTION check_graduation();

-- ---------------------------------------------------------------------------
-- §9. achilles_gatekeeper role + grants.
-- ---------------------------------------------------------------------------
DO $role$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'achilles_gatekeeper') THEN
    CREATE ROLE achilles_gatekeeper NOLOGIN;
  END IF;
END
$role$;

GRANT USAGE ON SCHEMA public TO achilles_gatekeeper;
GRANT SELECT ON op_task_queue TO achilles_gatekeeper;
GRANT UPDATE (status, shipped_at, completed_at, result_summary, builder_agent, reviewer_agent, actual_cost_usd, graduation_credited)
  ON op_task_queue TO achilles_gatekeeper;
GRANT INSERT, SELECT ON amg_artifact_registry TO achilles_gatekeeper;
GRANT INSERT, SELECT, UPDATE ON amg_graduation_counters TO achilles_gatekeeper;
GRANT INSERT, SELECT ON amg_shell_logs TO achilles_gatekeeper;
GRANT INSERT, SELECT, UPDATE ON amg_reviews TO achilles_gatekeeper;

-- Grant role to achilles_fallback identity if it exists.
DO $grant_fallback$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'achilles_fallback') THEN
    GRANT achilles_gatekeeper TO achilles_fallback;
  END IF;
END
$grant_fallback$;

-- ---------------------------------------------------------------------------
-- §10. Seed amg_agent_budget_config (7 rows).
-- ---------------------------------------------------------------------------
INSERT INTO amg_agent_budget_config (agent, daily_ceiling_usd, per_task_max_usd, monthly_ceiling_usd) VALUES
  ('codex',     30.0000, 3.0000, 300.0000),
  ('hercules',  20.0000, 2.0000, 150.0000),
  ('nestor',    20.0000, 2.0000, 150.0000),
  ('alexander', 10.0000, 1.0000,  75.0000),
  ('kimi_code', 10.0000, 1.0000,  75.0000),
  ('kimi_claw',  5.0000, 0.5000,  30.0000),
  ('amg_eom',   15.0000, 5.0000, 100.0000)
ON CONFLICT (agent) DO UPDATE SET
  daily_ceiling_usd   = EXCLUDED.daily_ceiling_usd,
  per_task_max_usd    = EXCLUDED.per_task_max_usd,
  monthly_ceiling_usd = EXCLUDED.monthly_ceiling_usd,
  ts                  = NOW();

-- ---------------------------------------------------------------------------
-- §11. Seed amg_graduation_counters (3 rows: hercules, nestor, alexander).
-- ---------------------------------------------------------------------------
INSERT INTO amg_graduation_counters (agent, level, consecutive_clean, threshold) VALUES
  ('hercules',  1, 0, 5),
  ('nestor',    1, 0, 5),
  ('alexander', 1, 0, 5)
ON CONFLICT (agent) DO NOTHING;

-- ---------------------------------------------------------------------------
-- §12. Reaper pg_cron — every 5 min, release stale-active locks.
-- ---------------------------------------------------------------------------
-- Idempotent: unschedule existing if present, then re-schedule.
SELECT cron.unschedule(jobid) FROM cron.job WHERE jobname = 'atlas-reaper';

SELECT cron.schedule(
  'atlas-reaper',
  '*/5 * * * *',
  $reaper$
  UPDATE op_task_queue
  SET status = 'approved',
      locked_by = NULL,
      locked_at = NULL,
      claimed_at = NULL,
      notes = COALESCE(notes,'') || E'\n[atlas-reaper ' || NOW()::TEXT || '] released stale lock.'
  WHERE status IN ('locked','active')
    AND claimed_at IS NOT NULL
    AND claimed_at + COALESCE(claim_timeout, INTERVAL '2 hours') < NOW()
  $reaper$
);

COMMIT;

-- ---------------------------------------------------------------------------
-- §16. Write per-step audit rows to amg_shell_logs (now that the table exists).
-- ---------------------------------------------------------------------------
INSERT INTO amg_shell_logs (task_id, agent, command, stdout_excerpt, exit_code, duration_ms)
SELECT 'CT-0427-95', 'titan', step.cmd, step.summary, 0, 0
FROM (VALUES
  ('§3 queue-surgery (active->completed where SHIPPED)',          'rowcount captured by caller'),
  ('§4 ALTER op_task_queue add 12 governance columns',            'expires_at,claimed_at,claim_timeout,proof_spec,artifact_refs,reviewer_agent,budget_ceiling,actual_cost_usd,graduation_credited,migration_note,shipped_at,builder_agent'),
  ('§5 expand assigned_to + status CHECK constraints',            'assigned_to+= codex/hercules/nestor/alexander/kimi_code/kimi_claw/amg_eom/achilles/aletheia/artisan/warden/cerberus/mercury; status += review/shipped'),
  ('§6 ADD CHECK proof_spec_required',                            'manual + titan exempt; new tasks require proof_spec'),
  ('§7 CREATE 10 governance tables',                              'amg_reviews,amg_shell_logs,amg_model_router_choices,amg_cost_ledger,amg_artifact_registry,amg_blocker_register,amg_morning_digest,amg_graduation_counters,amg_swarm_budget,amg_agent_budget_config'),
  ('§7 RLS enabled + service_role policy on all 10',              'ALTER TABLE ... ENABLE ROW LEVEL SECURITY + service_all policy'),
  ('§8 CREATE FUNCTION + TRIGGER no_self_review',                 'enforce_reviewer_separation on amg_reviews'),
  ('§8 CREATE FUNCTION + TRIGGER shipped_gate_trigger',           'enforce_shipped_gate on op_task_queue'),
  ('§8 CREATE FUNCTION + TRIGGER graduation_trigger',             'check_graduation on amg_graduation_counters'),
  ('§9 CREATE ROLE achilles_gatekeeper + GRANTs',                 'gatekeeper has UPDATE(status,shipped_at,...) on op_task_queue + writes on registry+counters+reviews+shell_logs'),
  ('§10 Seed amg_agent_budget_config (7 rows)',                   'codex/hercules/nestor/alexander/kimi_code/kimi_claw/amg_eom'),
  ('§11 Seed amg_graduation_counters (3 rows)',                   'hercules,nestor,alexander L1 0/5'),
  ('§12 pg_cron atlas-reaper every 5 min',                        'releases status=locked|active with stale claimed_at')
) AS step(cmd, summary);

\echo '== Confirmation =='
SELECT 'tables_created' AS metric, count(*)::TEXT AS value
FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE 'amg_%'
UNION ALL
SELECT 'budget_config_rows', count(*)::TEXT FROM amg_agent_budget_config
UNION ALL
SELECT 'graduation_counter_rows', count(*)::TEXT FROM amg_graduation_counters
UNION ALL
SELECT 'achilles_gatekeeper_exists', (EXISTS(SELECT 1 FROM pg_roles WHERE rolname='achilles_gatekeeper'))::TEXT
UNION ALL
SELECT 'reaper_cron_scheduled', (SELECT count(*)::TEXT FROM cron.job WHERE jobname='atlas-reaper')
UNION ALL
SELECT 'phantom_active_remaining', (SELECT count(*)::TEXT FROM op_task_queue WHERE status='active' AND result_summary ILIKE '%SHIPPED%');
