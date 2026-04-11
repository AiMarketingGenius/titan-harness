-- titan-harness/sql/006_payment_link_tests.sql
-- Purpose: audit table for end-to-end payment URL tests.
-- Every payment link Titan ships to a client MUST have a passing row here
-- within the last 24 hours, enforced at build time by scripts/build_proposal.py
-- Gate 3 and at runtime by the email drafting pipeline.
--
-- Born from the JDJ Lavar incident (2026-04-10) where a legacy PayPal
-- plan_id subscribe URL was shipped to a client without end-to-end
-- browser testing. The URL technically "worked" but displayed the wrong
-- brand name ("Credit Repair Hawk LLC dba Dr. SEO" instead of "AI
-- Marketing Genius"), causing the client to back out thinking it was a
-- scam. This table makes that class of failure auditable + blockable.
--
-- Run once in Supabase SQL Editor. Safe to re-run (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS public.payment_link_tests (
  id                       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Multi-tenant scoping (Titan-as-COO productization)
  project_id               text        NOT NULL DEFAULT 'EOM',

  -- What was tested
  url                      text        NOT NULL,
  url_kind                 text        CHECK (url_kind IN ('legacy_plan_id','ba_token','redirector','stripe_checkout','paddle_checkout','other')),
  processor                text        CHECK (processor IN ('paypal','paddle','stripe','square','other')),
  plan_id                  text,                                -- e.g. P-40456056SB832583SNHL7VCI
  product_id               text,                                -- e.g. PROD-40X325956U532253E
  expected_brand_name      text,                                -- what Titan expects to see, e.g. 'AI Marketing Genius'
  expected_price_label     text,                                -- e.g. '$500.00'

  -- What was observed
  observed_brand_name      text,                                -- scraped from the rendered page
  observed_price_label     text,
  page_title               text,
  url_after_redirect       text,                                -- where the browser ended up
  body_excerpt             text,                                -- first 2000 chars of visible text
  iframe_excerpt           text,                                -- PayPal embeds checkout in iframes
  screenshot_path          text,                                -- local file path on the test runner

  -- Verdict
  status                   text        NOT NULL CHECK (status IN ('pass','fail','inconclusive','captcha_blocked','error')),
  fail_reason              text,                                -- null on pass
  brand_match              boolean,                             -- observed_brand_name == expected_brand_name?

  -- Runtime identity
  tested_by                text        NOT NULL,                -- Titan instance id / hostname
  tested_at                timestamptz NOT NULL DEFAULT now(),
  test_duration_ms         int,
  playwright_user_agent    text,

  -- Housekeeping
  notes                    text,
  tags                     text[]      DEFAULT '{}',
  created_at               timestamptz NOT NULL DEFAULT now()
);

-- Indexes for the gate queries
-- Gate 3 query: "does this URL have a passing test in the last 24 hours?"
CREATE INDEX IF NOT EXISTS payment_link_tests_url_recent_idx
  ON public.payment_link_tests (url, tested_at DESC)
  WHERE status = 'pass';

-- Per-plan rollup queries
CREATE INDEX IF NOT EXISTS payment_link_tests_plan_idx
  ON public.payment_link_tests (project_id, plan_id, tested_at DESC);

-- Status dashboards
CREATE INDEX IF NOT EXISTS payment_link_tests_status_idx
  ON public.payment_link_tests (status, tested_at DESC)
  WHERE status IN ('fail','captcha_blocked','error');

-- Project-wide chronological
CREATE INDEX IF NOT EXISTS payment_link_tests_project_created_idx
  ON public.payment_link_tests (project_id, created_at DESC);

-- Enable RLS with same pattern as the other harness tables (sql/005)
ALTER TABLE public.payment_link_tests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS payment_link_tests_service_role_full_access
  ON public.payment_link_tests;
CREATE POLICY payment_link_tests_service_role_full_access
  ON public.payment_link_tests
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

DROP POLICY IF EXISTS payment_link_tests_project_tenant_isolation
  ON public.payment_link_tests;
CREATE POLICY payment_link_tests_project_tenant_isolation
  ON public.payment_link_tests
  FOR ALL
  TO authenticated
  USING (
    project_id = COALESCE(
      current_setting('request.jwt.claim.project_id', true),
      project_id
    )
  )
  WITH CHECK (
    project_id = COALESCE(
      current_setting('request.jwt.claim.project_id', true),
      project_id
    )
  );

-- Comments
COMMENT ON TABLE  public.payment_link_tests
  IS 'End-to-end browser test audit for payment URLs. Build-time Gate 3 in build_proposal.py requires a passing row within 24h for every URL in the rendered contract. Born from JDJ Lavar 2026-04-10 wrong-brand-name incident.';
COMMENT ON COLUMN public.payment_link_tests.brand_match
  IS 'True iff the scraped brand name on the rendered checkout page matches expected_brand_name. A URL that renders successfully but shows the wrong brand name is still a FAIL — that is what caused the Lavar incident.';
COMMENT ON COLUMN public.payment_link_tests.url_kind
  IS 'legacy_plan_id = PayPal /plans/subscribe?plan_id= (brand name fixed by account, unreliable). ba_token = PayPal /billing/subscriptions?ba_token= (brand name overridable via application_context). redirector = Titan-controlled URL that creates fresh ba_token on click.';
