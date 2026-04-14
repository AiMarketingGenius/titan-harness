-- DR-AMG-GOVERNANCE-01 Phase 3 — Retention Policies (v2, 2026-04-14)
-- Migration: 010_governance_retention.sql
--
-- REVISION LOG (2026-04-14): Blocker 1 addressed. Retention no longer parsed
-- from COMMENT ON TABLE (fragile). A dedicated governance_retention_policy
-- table is the source of truth. gov-retention-cron.sh MUST read from this
-- table via SELECT, not from pg_description.
--
-- Rollback: sql/010_rollback.sql reverses this migration.

BEGIN;

-- ============================================================
-- Retention Policy table — machine-readable source of truth
-- ============================================================
CREATE TABLE IF NOT EXISTS public.governance_retention_policy (
    table_name          TEXT PRIMARY KEY,
    retention_days      INTEGER NOT NULL CHECK (retention_days > 0),
    timestamp_column    TEXT NOT NULL,
    enabled             BOOLEAN NOT NULL DEFAULT true,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed policies
INSERT INTO public.governance_retention_policy (table_name, retention_days, timestamp_column, notes) VALUES
    ('governance_drift_scores',         180, 'scored_at',   'Drift metrics retained 6 months for trend analysis'),
    ('governance_antipattern_events',    90, 'detected_at', '90-day window for unresolved + resolved event audit'),
    ('governance_redteam_results',      365, 'run_at',      'Quarterly red team results kept 1 year'),
    ('governance_baseline',              90, 'captured_at', 'Rolling 14-day baseline, 90-day historical window'),
    ('governance_health_scores',        365, 'scored_at',   'Weekly GHS retained 1 year for annual review')
ON CONFLICT (table_name) DO UPDATE
    SET retention_days   = EXCLUDED.retention_days,
        timestamp_column = EXCLUDED.timestamp_column,
        notes            = EXCLUDED.notes,
        updated_at       = now();

ALTER TABLE public.governance_retention_policy ENABLE ROW LEVEL SECURITY;
CREATE POLICY retention_policy_service_all ON public.governance_retention_policy
    FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY retention_policy_authenticated_select ON public.governance_retention_policy
    FOR SELECT TO authenticated USING (true);
CREATE POLICY retention_policy_anon_deny ON public.governance_retention_policy
    FOR ALL TO anon USING (false);

-- Touch trigger reuses generic gov_touch_updated_at() from 009
DROP TRIGGER IF EXISTS trg_gov_retention_policy_updated_at ON public.governance_retention_policy;
CREATE TRIGGER trg_gov_retention_policy_updated_at
    BEFORE UPDATE ON public.governance_retention_policy
    FOR EACH ROW EXECUTE FUNCTION public.gov_touch_updated_at();

-- Informational comments (non-authoritative; actual policy in table above)
COMMENT ON TABLE public.governance_retention_policy IS
    'Authoritative retention policy. gov-retention-cron.sh MUST read from here, not from pg_description.';
COMMENT ON TABLE public.governance_drift_scores         IS 'See governance_retention_policy for retention window';
COMMENT ON TABLE public.governance_antipattern_events   IS 'See governance_retention_policy for retention window';
COMMENT ON TABLE public.governance_redteam_results      IS 'See governance_retention_policy for retention window';
COMMENT ON TABLE public.governance_baseline             IS 'See governance_retention_policy for retention window';
COMMENT ON TABLE public.governance_health_scores        IS 'See governance_retention_policy for retention window';

COMMIT;
