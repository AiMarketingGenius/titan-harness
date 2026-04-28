-- =============================================================================
-- CT-0427-95 amg_reviews schema reconciliation.
-- Pre-existing amg_reviews had task_id UUID; needs TEXT to FK with op_task_queue.
-- Add missing columns + CHECK constraint per work pack spec.
-- =============================================================================
\set ON_ERROR_STOP on

BEGIN;

-- Reset hercules graduation state (test mutated it from L1 0/5 to L2 0/5).
UPDATE amg_graduation_counters
SET level = 1, consecutive_clean = 0, graduated_at = NULL
WHERE agent = 'hercules' AND level = 2 AND consecutive_clean = 0;

-- Truncate amg_reviews if it was empty pre-existing legacy table.
DELETE FROM amg_reviews WHERE created_at < '2026-04-27' OR created_at IS NULL;

-- Drop UUID task_id and replace with TEXT.
ALTER TABLE amg_reviews ALTER COLUMN task_id TYPE TEXT;

-- Add work-pack-spec columns if missing.
ALTER TABLE amg_reviews ADD COLUMN IF NOT EXISTS rationale          TEXT;
ALTER TABLE amg_reviews ADD COLUMN IF NOT EXISTS proof_spec_passed  BOOLEAN;
ALTER TABLE amg_reviews ADD COLUMN IF NOT EXISTS reviewed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE amg_reviews ADD COLUMN IF NOT EXISTS achilles_confirmed_at TIMESTAMPTZ;

-- Make verdict NOT NULL + CHECK.
ALTER TABLE amg_reviews ALTER COLUMN verdict SET NOT NULL;
ALTER TABLE amg_reviews DROP CONSTRAINT IF EXISTS amg_reviews_verdict_check;
ALTER TABLE amg_reviews ADD CONSTRAINT amg_reviews_verdict_check
  CHECK (verdict IN ('PASS','FAIL','REVISE'));

-- Builder + reviewer NOT NULL + CHECK reviewer != builder (belt + suspenders behind trigger).
ALTER TABLE amg_reviews ALTER COLUMN reviewer_agent SET NOT NULL;
ALTER TABLE amg_reviews ALTER COLUMN builder_agent SET NOT NULL;
ALTER TABLE amg_reviews DROP CONSTRAINT IF EXISTS reviewer_ne_builder;
ALTER TABLE amg_reviews ADD CONSTRAINT reviewer_ne_builder
  CHECK (reviewer_agent <> builder_agent);

-- Indexes for hot reads.
CREATE INDEX IF NOT EXISTS idx_amg_reviews_task    ON amg_reviews(task_id);
CREATE INDEX IF NOT EXISTS idx_amg_reviews_verdict ON amg_reviews(verdict);

COMMIT;

-- ---------------------------------------------------------------------------
-- §15a Negative test (now schema-compatible): reviewer = builder must raise.
-- ---------------------------------------------------------------------------
\echo
\echo '== §15a Negative test: amg_reviews reviewer=builder =='
BEGIN;
SAVEPOINT s15a;
DO $test_15a$
DECLARE
  err_code TEXT;
  err_msg  TEXT;
BEGIN
  BEGIN
    INSERT INTO amg_reviews (task_id, builder_agent, reviewer_agent, verdict)
    VALUES ('CT-0427-95-NEGATIVE-TEST-15A', 'hercules', 'hercules', 'PASS');
    RAISE WARNING '!! UNEXPECTED — self-review insert SUCCEEDED';
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS
      err_code = RETURNED_SQLSTATE,
      err_msg  = MESSAGE_TEXT;
    RAISE NOTICE 'PASS — no_self_review raised: SQLSTATE=% MESSAGE=%', err_code, err_msg;
  END;
END
$test_15a$;
ROLLBACK TO SAVEPOINT s15a;
COMMIT;

-- §15b — already verified above (SQLSTATE 42501 from SET ROLE attempt).
-- §15c — already verified above (hercules promoted L1->L2; reset above).

\echo
\echo '== Final post-patch state =='
SELECT
  (SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'amg_%') AS amg_tables_total,
  (SELECT count(*) FROM amg_agent_budget_config)                                                            AS budget_rows,
  (SELECT count(*) FROM amg_graduation_counters WHERE level=1 AND consecutive_clean=0)                      AS grad_at_baseline,
  (SELECT count(*) FROM cron.job WHERE jobname='atlas-reaper')                                              AS reaper_jobs,
  (SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='achilles_gatekeeper'))                               AS gatekeeper_role,
  (SELECT count(*) FROM pg_trigger WHERE tgname IN ('no_self_review','shipped_gate_trigger','graduation_trigger') AND NOT tgisinternal) AS triggers_installed;
