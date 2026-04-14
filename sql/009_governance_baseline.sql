-- DR-AMG-GOVERNANCE-01 Phase 3 — Behavioral Baseline + supporting tables (v2, 2026-04-14)
-- Migration: 009_governance_baseline.sql
--
-- REVISION LOG (2026-04-14): addresses 7 blockers from provisional dual-review
-- (sonar-pro spec=B, sonar-pro adversarial=C). Target re-grade: Perplexity A.
--
--   Blocker 1: COMMENT-based retention → explicit governance_retention_policy table (moved to 010)
--   Blocker 2: M2-M7 hardcoded CHECK → governance_antipattern_catalog with FK
--   Blocker 3: NUMERIC(5,2) pct overflow → NUMERIC(6,3) + range CHECKs
--   Blocker 4: No rollback → companion 010_rollback.sql + transaction-wrapped migration
--   Blocker 5: No FK from drift_scores → session/baseline → added baseline_id + session_id
--   Blocker 6: No audit trail on resolved flag → BEFORE UPDATE trigger + updated_at columns
--   Blocker 7: No authenticated-role RLS for dashboard readers → SELECT policies added
--   Bonus:    UNIQUE (quarter, attack_vector) on redteam to prevent double-record

BEGIN;

-- ============================================================
-- 3.1: Behavioral Baseline Table
-- Captures per-session distributions (action ratios, timing, reviewer grades, tool picks).
-- ============================================================
CREATE TABLE IF NOT EXISTS public.governance_baseline (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_id      TEXT NOT NULL,
    window_start    TIMESTAMPTZ NOT NULL,
    window_end      TIMESTAMPTZ NOT NULL,

    -- Action type counts per hour
    bash_actions        INTEGER NOT NULL DEFAULT 0 CHECK (bash_actions >= 0),
    git_actions         INTEGER NOT NULL DEFAULT 0 CHECK (git_actions >= 0),
    mcp_read_actions    INTEGER NOT NULL DEFAULT 0 CHECK (mcp_read_actions >= 0),
    mcp_write_actions   INTEGER NOT NULL DEFAULT 0 CHECK (mcp_write_actions >= 0),
    api_call_actions    INTEGER NOT NULL DEFAULT 0 CHECK (api_call_actions >= 0),

    -- Timing metrics
    time_to_first_action_s  NUMERIC(10,2) CHECK (time_to_first_action_s IS NULL OR time_to_first_action_s >= 0),
    avg_diff_size_lines     NUMERIC(10,2) CHECK (avg_diff_size_lines     IS NULL OR avg_diff_size_lines     >= 0),

    -- Reviewer metrics (Blocker 3: NUMERIC(6,3) + explicit range CHECK)
    reviewer_grade_a_pct    NUMERIC(6,3) CHECK (reviewer_grade_a_pct    IS NULL OR (reviewer_grade_a_pct    BETWEEN 0 AND 100)),
    reviewer_grade_b_pct    NUMERIC(6,3) CHECK (reviewer_grade_b_pct    IS NULL OR (reviewer_grade_b_pct    BETWEEN 0 AND 100)),
    reviewer_grade_fail_pct NUMERIC(6,3) CHECK (reviewer_grade_fail_pct IS NULL OR (reviewer_grade_fail_pct BETWEEN 0 AND 100)),
    override_count          INTEGER NOT NULL DEFAULT 0 CHECK (override_count >= 0),

    -- Tool selection
    cli_actions         INTEGER NOT NULL DEFAULT 0 CHECK (cli_actions >= 0),
    stagehand_actions   INTEGER NOT NULL DEFAULT 0 CHECK (stagehand_actions >= 0),

    -- Rolling window marker
    is_rolling_baseline BOOLEAN NOT NULL DEFAULT false,

    -- Window sanity
    CONSTRAINT baseline_window_order CHECK (window_end > window_start)
);

CREATE INDEX IF NOT EXISTS idx_gov_baseline_window
    ON public.governance_baseline (window_start DESC, window_end DESC);

CREATE INDEX IF NOT EXISTS idx_gov_baseline_session
    ON public.governance_baseline (session_id);

CREATE INDEX IF NOT EXISTS idx_gov_baseline_captured
    ON public.governance_baseline (captured_at DESC);

ALTER TABLE public.governance_baseline ENABLE ROW LEVEL SECURITY;

CREATE POLICY baseline_service_insert ON public.governance_baseline
    FOR INSERT TO service_role WITH CHECK (true);
CREATE POLICY baseline_service_select ON public.governance_baseline
    FOR SELECT TO service_role USING (true);

-- Blocker 7: dashboard users (authenticated role) get read-only access
CREATE POLICY baseline_authenticated_select ON public.governance_baseline
    FOR SELECT TO authenticated USING (true);

CREATE POLICY baseline_anon_deny ON public.governance_baseline
    FOR ALL TO anon USING (false);

-- ============================================================
-- 3.5a: Anti-Pattern Catalog (extensibility table — Blocker 2)
-- Catalog replaces hardcoded CHECK constraint on pattern_code.
-- New patterns added by INSERT, no migration required.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.governance_antipattern_catalog (
    pattern_code        TEXT PRIMARY KEY,
    description         TEXT NOT NULL,
    severity_default    TEXT NOT NULL CHECK (severity_default IN ('SEV1','SEV2','INFO')),
    active              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO public.governance_antipattern_catalog (pattern_code, description, severity_default) VALUES
    ('M2', 'Audit Log Manipulation (hash chain break)',        'SEV1'),
    ('M3', 'Reviewer override without justification',           'SEV2'),
    ('M4', 'Mirror drift unacknowledged > 15 min',              'SEV2'),
    ('M5', 'Rubber-stamp grading (identical grade N+ in a row)','SEV2'),
    ('M6', 'Stale state (session_state not updated > 24h)',     'INFO'),
    ('M7', 'Hard-stop recurrence (same stop fired 3x in week)', 'SEV1')
ON CONFLICT (pattern_code) DO NOTHING;

ALTER TABLE public.governance_antipattern_catalog ENABLE ROW LEVEL SECURITY;
CREATE POLICY antipattern_catalog_service_all ON public.governance_antipattern_catalog
    FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY antipattern_catalog_authenticated_select ON public.governance_antipattern_catalog
    FOR SELECT TO authenticated USING (true);
CREATE POLICY antipattern_catalog_anon_deny ON public.governance_antipattern_catalog
    FOR ALL TO anon USING (false);

-- ============================================================
-- 3.2: Drift Scoring Table (Blocker 5: FK to baseline + session_id)
-- FK choice: ON DELETE SET NULL preserves drift history when a baseline
-- row is deleted under retention policy — the score remains queryable
-- as orphaned-historical rather than being cascaded away. Switch to
-- CASCADE only if baseline deletions should wipe downstream drift.
-- Isolation: assumes READ COMMITTED (Postgres default). Concurrent
-- baseline writes + drift scoring are serialized at the app layer
-- (gov-daily-cron.sh) to prevent read-then-compute races.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.governance_drift_scores (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scored_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    dimension       TEXT NOT NULL,

    -- Blocker 5: traceability back to source
    baseline_id     BIGINT REFERENCES public.governance_baseline(id) ON DELETE SET NULL,
    session_id      TEXT,

    baseline_mean   NUMERIC(12,4),
    baseline_stddev NUMERIC(12,4) CHECK (baseline_stddev IS NULL OR baseline_stddev >= 0),
    recent_value    NUMERIC(12,4),
    z_score         NUMERIC(8,4),
    ks_statistic    NUMERIC(8,6) CHECK (ks_statistic IS NULL OR (ks_statistic BETWEEN 0 AND 1)),
    ks_p_value      NUMERIC(8,6) CHECK (ks_p_value   IS NULL OR (ks_p_value   BETWEEN 0 AND 1)),
    drift_level     TEXT NOT NULL CHECK (drift_level IN ('normal', 'warning', 'critical')),
    alert_fired     BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_gov_drift_scored_at
    ON public.governance_drift_scores (scored_at DESC);
CREATE INDEX IF NOT EXISTS idx_gov_drift_dimension
    ON public.governance_drift_scores (dimension);
CREATE INDEX IF NOT EXISTS idx_gov_drift_baseline
    ON public.governance_drift_scores (baseline_id);
CREATE INDEX IF NOT EXISTS idx_gov_drift_session
    ON public.governance_drift_scores (session_id);

ALTER TABLE public.governance_drift_scores ENABLE ROW LEVEL SECURITY;

CREATE POLICY drift_service_insert ON public.governance_drift_scores
    FOR INSERT TO service_role WITH CHECK (true);
CREATE POLICY drift_service_select ON public.governance_drift_scores
    FOR SELECT TO service_role USING (true);
CREATE POLICY drift_authenticated_select ON public.governance_drift_scores
    FOR SELECT TO authenticated USING (true);
CREATE POLICY drift_anon_deny ON public.governance_drift_scores
    FOR ALL TO anon USING (false);

-- ============================================================
-- 3.4: Governance Health Score Table (Blocker 6: updated_at + trigger)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.governance_health_scores (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scored_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    week_start      DATE NOT NULL,
    week_end        DATE NOT NULL,

    violation_rate_score        NUMERIC(5,4) NOT NULL CHECK (violation_rate_score        BETWEEN 0 AND 1),
    hash_chain_score            NUMERIC(5,4) NOT NULL CHECK (hash_chain_score            BETWEEN 0 AND 1),
    auditor_uptime_score        NUMERIC(5,4) NOT NULL CHECK (auditor_uptime_score        BETWEEN 0 AND 1),
    rubber_stamp_score          NUMERIC(5,4) NOT NULL CHECK (rubber_stamp_score          BETWEEN 0 AND 1),
    mirror_drift_score          NUMERIC(5,4) NOT NULL CHECK (mirror_drift_score          BETWEEN 0 AND 1),
    stale_state_score           NUMERIC(5,4) NOT NULL CHECK (stale_state_score           BETWEEN 0 AND 1),
    hard_stop_recurrence_score  NUMERIC(5,4) NOT NULL CHECK (hard_stop_recurrence_score  BETWEEN 0 AND 1),
    alert_budget_score          NUMERIC(5,4) NOT NULL CHECK (alert_budget_score          BETWEEN 0 AND 1),

    ghs_composite           NUMERIC(6,3) NOT NULL CHECK (ghs_composite BETWEEN 0 AND 100),

    review_triggered    BOOLEAN NOT NULL DEFAULT false,
    posted_to_slack     BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT ghs_week_order CHECK (week_end >= week_start),
    UNIQUE (week_start, week_end)
);

CREATE INDEX IF NOT EXISTS idx_gov_ghs_week
    ON public.governance_health_scores (week_start DESC);

ALTER TABLE public.governance_health_scores ENABLE ROW LEVEL SECURITY;
CREATE POLICY ghs_service_insert ON public.governance_health_scores
    FOR INSERT TO service_role WITH CHECK (true);
CREATE POLICY ghs_service_update ON public.governance_health_scores
    FOR UPDATE TO service_role USING (true) WITH CHECK (true);
CREATE POLICY ghs_service_select ON public.governance_health_scores
    FOR SELECT TO service_role USING (true);
CREATE POLICY ghs_authenticated_select ON public.governance_health_scores
    FOR SELECT TO authenticated USING (true);
CREATE POLICY ghs_anon_deny ON public.governance_health_scores
    FOR ALL TO anon USING (false);

-- ============================================================
-- 3.5b: Anti-Pattern Monitoring Events (Blocker 2: FK to catalog; Blocker 6: trigger)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.governance_antipattern_events (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Blocker 2: FK to catalog replaces hardcoded CHECK
    pattern_code    TEXT NOT NULL REFERENCES public.governance_antipattern_catalog(pattern_code),

    severity        TEXT NOT NULL CHECK (severity IN ('SEV1','SEV2','INFO')),
    description     TEXT NOT NULL,
    evidence        JSONB,
    resolved        BOOLEAN NOT NULL DEFAULT false,
    resolved_at     TIMESTAMPTZ,

    -- Consistency: resolved_at must match resolved flag
    CONSTRAINT antipattern_resolved_consistency
      CHECK ((resolved = true  AND resolved_at IS NOT NULL)
          OR (resolved = false AND resolved_at IS NULL))
);

CREATE INDEX IF NOT EXISTS idx_gov_antipattern_detected
    ON public.governance_antipattern_events (detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_gov_antipattern_unresolved
    ON public.governance_antipattern_events (detected_at DESC) WHERE NOT resolved;
CREATE INDEX IF NOT EXISTS idx_gov_antipattern_pattern
    ON public.governance_antipattern_events (pattern_code);
CREATE INDEX IF NOT EXISTS idx_gov_antipattern_evidence_gin
    ON public.governance_antipattern_events USING GIN (evidence);

ALTER TABLE public.governance_antipattern_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY antipattern_service_all ON public.governance_antipattern_events
    FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY antipattern_authenticated_select ON public.governance_antipattern_events
    FOR SELECT TO authenticated USING (true);
CREATE POLICY antipattern_anon_deny ON public.governance_antipattern_events
    FOR ALL TO anon USING (false);

-- ============================================================
-- 3.8: Red Team Results (bonus: UNIQUE constraint to prevent double-record)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.governance_redteam_results (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- quarter: ISO-8601-style fiscal quarter, e.g. "2026-Q1", "2026-Q2" ...
    quarter             TEXT NOT NULL CHECK (quarter ~ '^[0-9]{4}-Q[1-4]$'),
    attack_vector       TEXT NOT NULL,
    targeted_mechanism  TEXT NOT NULL,
    defense             TEXT NOT NULL,
    result              TEXT NOT NULL CHECK (result IN ('caught','partial','missed')),
    residual_gap        TEXT,
    evidence            JSONB,

    -- Bonus: one record per (quarter, attack_vector) — prevents double-record skewing metrics
    UNIQUE (quarter, attack_vector)
);

CREATE INDEX IF NOT EXISTS idx_gov_redteam_run
    ON public.governance_redteam_results (run_at DESC);
CREATE INDEX IF NOT EXISTS idx_gov_redteam_quarter
    ON public.governance_redteam_results (quarter);
CREATE INDEX IF NOT EXISTS idx_gov_redteam_evidence_gin
    ON public.governance_redteam_results USING GIN (evidence);

ALTER TABLE public.governance_redteam_results ENABLE ROW LEVEL SECURITY;
CREATE POLICY redteam_service_insert ON public.governance_redteam_results
    FOR INSERT TO service_role WITH CHECK (true);
CREATE POLICY redteam_service_select ON public.governance_redteam_results
    FOR SELECT TO service_role USING (true);
CREATE POLICY redteam_authenticated_select ON public.governance_redteam_results
    FOR SELECT TO authenticated USING (true);
CREATE POLICY redteam_anon_deny ON public.governance_redteam_results
    FOR ALL TO anon USING (false);

-- ============================================================
-- Blocker 6: Trigger functions for audit trail on mutable flags
-- ============================================================

-- Antipattern: set/clear resolved_at based on resolved flag flip
CREATE OR REPLACE FUNCTION public.gov_antipattern_set_resolved_at() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.resolved = true AND (OLD.resolved IS DISTINCT FROM true) THEN
        NEW.resolved_at := now();
    ELSIF NEW.resolved = false THEN
        NEW.resolved_at := NULL;
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_gov_antipattern_resolved_at ON public.governance_antipattern_events;
CREATE TRIGGER trg_gov_antipattern_resolved_at
    BEFORE UPDATE ON public.governance_antipattern_events
    FOR EACH ROW EXECUTE FUNCTION public.gov_antipattern_set_resolved_at();

-- Generic "touch updated_at" function reused across governance tables that
-- carry an updated_at column (health_scores, antipattern_catalog,
-- retention_policy). Named _touch_ (not _ghs_) to reflect generic use;
-- earlier naming kept as a CREATE OR REPLACE alias for backward compat.
CREATE OR REPLACE FUNCTION public.gov_touch_updated_at() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

-- Alias kept for any already-referencing migrations / triggers.
CREATE OR REPLACE FUNCTION public.gov_ghs_touch_updated_at() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_gov_ghs_updated_at ON public.governance_health_scores;
CREATE TRIGGER trg_gov_ghs_updated_at
    BEFORE UPDATE ON public.governance_health_scores
    FOR EACH ROW EXECUTE FUNCTION public.gov_touch_updated_at();

-- Catalog: bump updated_at on any change
DROP TRIGGER IF EXISTS trg_gov_antipattern_catalog_updated_at ON public.governance_antipattern_catalog;
CREATE TRIGGER trg_gov_antipattern_catalog_updated_at
    BEFORE UPDATE ON public.governance_antipattern_catalog
    FOR EACH ROW EXECUTE FUNCTION public.gov_touch_updated_at();

COMMIT;
