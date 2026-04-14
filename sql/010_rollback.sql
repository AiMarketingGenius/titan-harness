-- DR-AMG-GOVERNANCE-01 Phase 3 — Rollback for 010_governance_retention.sql
-- Migration: 010_rollback.sql
--
-- Blocker 4 fix: rollback path for 010. Reverts retention policy entries
-- and drops the policy table. Does NOT touch the 009 schema (use a
-- companion 009_rollback.sql if full revert needed).
--
-- Use: psql < sql/010_rollback.sql
-- Verify post-rollback:
--   SELECT * FROM public.governance_retention_policy;   -- expect: relation does not exist
--   SELECT obj_description('public.governance_drift_scores'::regclass, 'pg_class');

BEGIN;

-- Drop seeded rows first (defensive — table itself is dropped next, but this
-- makes partial rollback possible if someone only wants to reset seeds).
DELETE FROM public.governance_retention_policy
WHERE table_name IN (
    'governance_drift_scores',
    'governance_antipattern_events',
    'governance_redteam_results',
    'governance_baseline',
    'governance_health_scores'
);

-- Drop trigger + table
DROP TRIGGER IF EXISTS trg_gov_retention_policy_updated_at ON public.governance_retention_policy;
DROP TABLE  IF EXISTS public.governance_retention_policy CASCADE;

-- Restore pre-v2 informational comments (best-effort; original text preserved below)
COMMENT ON TABLE public.governance_drift_scores         IS NULL;
COMMENT ON TABLE public.governance_antipattern_events   IS NULL;
COMMENT ON TABLE public.governance_redteam_results      IS NULL;
COMMENT ON TABLE public.governance_baseline             IS NULL;
COMMENT ON TABLE public.governance_health_scores        IS NULL;

COMMIT;
