-- =============================================================================
-- THREE-JUDGE QUALITY GATE — Phase 1.1 DDL (per spec v1.0 §10)
-- Date: 2026-04-28 | Owner: Titan | Scope: Tier 1 gate tables
-- Tables: eom_judgments, eom_judgment_scores, amg_judge_override
-- =============================================================================
\set ON_ERROR_STOP on
\timing on

BEGIN;

-- ---------------------------------------------------------------------------
-- §10.1 eom_judgments — one row per directive submission, lifecycle-tracked.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eom_judgments (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  directive_md                TEXT NOT NULL,
  directive_hash              TEXT NOT NULL,
  directive_class             TEXT NOT NULL CHECK (directive_class IN ('CLASS_A','CLASS_B','CLASS_C')),
  rubric_version              TEXT NOT NULL DEFAULT 'v1.0',
  iteration                   INTEGER NOT NULL DEFAULT 1 CHECK (iteration BETWEEN 1 AND 3),
  parent_judgment_id          UUID REFERENCES eom_judgments(id) ON DELETE SET NULL,
  status                      TEXT NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending','in_review','revision_needed','approved','rejected_max_iter','escalated')),
  composite_min               NUMERIC(4,2),
  composite_max               NUMERIC(4,2),
  composite_mean              NUMERIC(4,2),
  score_spread                NUMERIC(4,2) GENERATED ALWAYS AS (composite_max - composite_min) STORED,
  contested                   BOOLEAN GENERATED ALWAYS AS (
                                composite_max IS NOT NULL
                                AND composite_min IS NOT NULL
                                AND (composite_max - composite_min) >= 1.5
                              ) STORED,
  iteration_failures          JSONB NOT NULL DEFAULT '{}'::jsonb,
  dispatched_at               TIMESTAMPTZ,
  final_directive_sha         TEXT,
  force_approve_override_id   UUID,                      -- FK added after amg_judge_override exists
  judges_required             TEXT[] NOT NULL DEFAULT ARRAY['perplexity','grok','kimi'],
  threshold                   NUMERIC(3,1) NOT NULL DEFAULT 9.3,
  authored_by                 TEXT NOT NULL DEFAULT 'eom',
  target_agent                TEXT CHECK (target_agent IN ('titan','achilles','both'))
);
CREATE INDEX IF NOT EXISTS idx_eom_judgments_status        ON eom_judgments(status);
CREATE INDEX IF NOT EXISTS idx_eom_judgments_hash          ON eom_judgments(directive_hash);
CREATE INDEX IF NOT EXISTS idx_eom_judgments_created       ON eom_judgments(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_eom_judgments_parent        ON eom_judgments(parent_judgment_id) WHERE parent_judgment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_eom_judgments_pending_lane  ON eom_judgments(status, created_at) WHERE status IN ('pending','in_review','revision_needed');

-- updated_at maintenance
CREATE OR REPLACE FUNCTION eom_judgments_touch_updated_at() RETURNS TRIGGER AS $fn$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS eom_judgments_touch_updated_at ON eom_judgments;
CREATE TRIGGER eom_judgments_touch_updated_at
  BEFORE UPDATE ON eom_judgments
  FOR EACH ROW EXECUTE FUNCTION eom_judgments_touch_updated_at();

-- ---------------------------------------------------------------------------
-- §10.2 eom_judgment_scores — one row per (judgment, judge, iteration).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eom_judgment_scores (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  judgment_id              UUID NOT NULL REFERENCES eom_judgments(id) ON DELETE CASCADE,
  judge_name               TEXT NOT NULL CHECK (judge_name IN ('perplexity','grok','kimi','haiku-proxy','sonar-basic','amg-inhouse')),
  iteration                INTEGER NOT NULL CHECK (iteration BETWEEN 1 AND 3),
  composite                NUMERIC(4,2),
  score_clarity            NUMERIC(4,2),
  score_technical          NUMERIC(4,2),
  score_completeness       NUMERIC(4,2),
  score_risk               NUMERIC(4,2),
  score_amg_fit            NUMERIC(4,2),
  score_acceptance         NUMERIC(4,2),
  score_idempotency        NUMERIC(4,2),
  verdict                  TEXT CHECK (verdict IN ('PASS','REVISE','FORMAT_VIOLATION','ESCALATE')),
  confidence               TEXT CHECK (confidence IN ('HIGH','MEDIUM','LOW')),
  top_issues               JSONB NOT NULL DEFAULT '[]'::jsonb,
  revision_hints           JSONB NOT NULL DEFAULT '[]'::jsonb,
  judge_status             TEXT NOT NULL DEFAULT 'pending'
                             CHECK (judge_status IN (
                               'pending','in_flight','scored','parse_failed','timeout',
                               'session_expired','selector_mismatch','rate_limited','unavailable','escalate'
                             )),
  response_latency_seconds INTEGER,
  raw_response_hash        TEXT,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (judgment_id, judge_name, iteration)
);
CREATE INDEX IF NOT EXISTS idx_judgment_scores_judgment   ON eom_judgment_scores(judgment_id);
CREATE INDEX IF NOT EXISTS idx_judgment_scores_judge      ON eom_judgment_scores(judge_name);
CREATE INDEX IF NOT EXISTS idx_judgment_scores_status     ON eom_judgment_scores(judge_status);

-- ---------------------------------------------------------------------------
-- §10.3 amg_judge_override — Solon-only force-approve audit trail.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS amg_judge_override (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  judgment_id   UUID NOT NULL REFERENCES eom_judgments(id) ON DELETE CASCADE,
  invoked_by    TEXT NOT NULL DEFAULT 'solon',
  reason        TEXT NOT NULL CHECK (length(reason) >= 8),  -- "P0 outage" etc., never blank
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_judge_override_judgment ON amg_judge_override(judgment_id);

-- Now wire the deferred FK from eom_judgments → amg_judge_override.
ALTER TABLE eom_judgments
  DROP CONSTRAINT IF EXISTS eom_judgments_force_approve_fk;
ALTER TABLE eom_judgments
  ADD  CONSTRAINT eom_judgments_force_approve_fk
       FOREIGN KEY (force_approve_override_id) REFERENCES amg_judge_override(id) ON DELETE SET NULL;

-- ---------------------------------------------------------------------------
-- RLS — enable on all 3 tables, service_role full access (matches CT-0427-95
-- governance pattern). Anonymization for EOM consumption is enforced at the
-- MCP tool layer (get_pending_judgments deduplicates + drops per-judge keys).
-- ---------------------------------------------------------------------------
DO $rls$
DECLARE t TEXT;
BEGIN
  FOR t IN SELECT unnest(ARRAY['eom_judgments','eom_judgment_scores','amg_judge_override']) LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS %I_service_all ON %I', t, t);
    EXECUTE format('CREATE POLICY %I_service_all ON %I FOR ALL TO service_role USING (true) WITH CHECK (true)', t, t);
  END LOOP;
END
$rls$;

-- ---------------------------------------------------------------------------
-- §6 anonymized aggregate view — used by get_pending_judgments. Returns
-- aggregated TOP_ISSUES / REVISION_HINTS / dimension fail-counts for EOM
-- without leaking which judge produced which signal.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW eom_judgment_aggregate AS
SELECT
  j.id                                                      AS judgment_id,
  j.iteration,
  j.status,
  j.directive_class,
  j.directive_hash,
  j.composite_min,
  j.composite_max,
  j.composite_mean,
  j.score_spread,
  j.contested,
  -- dimension fail-counts (any judge below 9.0 on that dim).
  jsonb_build_object(
    'clarity',     COALESCE((SELECT count(*)::int FROM eom_judgment_scores s WHERE s.judgment_id=j.id AND s.iteration=j.iteration AND s.score_clarity     < 9.0), 0),
    'technical',   COALESCE((SELECT count(*)::int FROM eom_judgment_scores s WHERE s.judgment_id=j.id AND s.iteration=j.iteration AND s.score_technical   < 9.0), 0),
    'completeness',COALESCE((SELECT count(*)::int FROM eom_judgment_scores s WHERE s.judgment_id=j.id AND s.iteration=j.iteration AND s.score_completeness< 9.0), 0),
    'risk',        COALESCE((SELECT count(*)::int FROM eom_judgment_scores s WHERE s.judgment_id=j.id AND s.iteration=j.iteration AND s.score_risk        < 9.0), 0),
    'amg_fit',     COALESCE((SELECT count(*)::int FROM eom_judgment_scores s WHERE s.judgment_id=j.id AND s.iteration=j.iteration AND s.score_amg_fit     < 9.0), 0),
    'acceptance',  COALESCE((SELECT count(*)::int FROM eom_judgment_scores s WHERE s.judgment_id=j.id AND s.iteration=j.iteration AND s.score_acceptance  < 9.0), 0),
    'idempotency', COALESCE((SELECT count(*)::int FROM eom_judgment_scores s WHERE s.judgment_id=j.id AND s.iteration=j.iteration AND s.score_idempotency < 9.0), 0)
  )                                                         AS dimensions_failing,
  -- aggregated top_issues (deduplicated, all judges, this iteration).
  -- Postgres requires ORDER BY in jsonb_agg(DISTINCT ...) to match the arg
  -- expression — so we deduplicate inside a subquery, then order by severity
  -- in an outer aggregate that does NOT use DISTINCT.
  COALESCE((
    SELECT jsonb_agg(issue ORDER BY (issue->>'severity') DESC)
    FROM (
      SELECT DISTINCT ON (issue::text) issue
      FROM eom_judgment_scores s, jsonb_array_elements(COALESCE(s.top_issues,'[]'::jsonb)) issue
      WHERE s.judgment_id = j.id AND s.iteration = j.iteration
    ) deduped
  ), '[]'::jsonb)                                           AS aggregated_top_issues,
  COALESCE((
    SELECT jsonb_agg(hint)
    FROM (
      SELECT DISTINCT ON (hint::text) hint
      FROM eom_judgment_scores s, jsonb_array_elements(COALESCE(s.revision_hints,'[]'::jsonb)) hint
      WHERE s.judgment_id = j.id AND s.iteration = j.iteration
    ) deduped
  ), '[]'::jsonb)                                           AS aggregated_revision_hints,
  -- confidence summary.
  jsonb_build_object(
    'high',   COALESCE((SELECT count(*)::int FROM eom_judgment_scores s WHERE s.judgment_id=j.id AND s.iteration=j.iteration AND s.confidence='HIGH'), 0),
    'medium', COALESCE((SELECT count(*)::int FROM eom_judgment_scores s WHERE s.judgment_id=j.id AND s.iteration=j.iteration AND s.confidence='MEDIUM'), 0),
    'low',    COALESCE((SELECT count(*)::int FROM eom_judgment_scores s WHERE s.judgment_id=j.id AND s.iteration=j.iteration AND s.confidence='LOW'), 0)
  )                                                         AS confidence_summary,
  j.created_at,
  j.updated_at
FROM eom_judgments j;

COMMIT;

\echo '== confirmation =='
SELECT
  (SELECT count(*) FROM information_schema.tables  WHERE table_schema='public' AND table_name IN ('eom_judgments','eom_judgment_scores','amg_judge_override')) AS new_tables_present,
  (SELECT count(*) FROM information_schema.views   WHERE table_schema='public' AND table_name='eom_judgment_aggregate')                                       AS aggregate_view_present,
  (SELECT count(*) FROM pg_constraint              WHERE conname='eom_judgments_force_approve_fk')                                                            AS deferred_fk_present,
  (SELECT count(*) FROM pg_trigger                 WHERE tgname='eom_judgments_touch_updated_at')                                                             AS updated_at_trigger_present;
