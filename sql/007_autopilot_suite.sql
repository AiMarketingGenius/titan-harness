-- titan-harness/sql/007_autopilot_suite.sql
-- Schema for the 5-thread Autopilot Suite shipped 2026-04-11 overnight.
-- Threads: (1) sales inbox + CRM agent, (2) proposal spec generator gap,
-- (3) recurring marketing engine, (4) back-office autopilot, (5) client
-- reporting autopilot.
--
-- Safe to apply in any order against an existing harness schema. All tables
-- use CREATE IF NOT EXISTS. All RLS policies use DROP POLICY IF EXISTS.
--
-- Apply in Supabase SQL Editor (Browser-to-SQL-Editor per Solon's standing
-- migration channel).

-- =========================================================================
-- THREAD 1 — Sales Inbox + CRM Agent
-- =========================================================================

CREATE TABLE IF NOT EXISTS public.leads (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id            text        NOT NULL DEFAULT 'EOM',
  email                 text        NOT NULL,
  full_name             text,
  company               text,
  domain                text,
  source                text        CHECK (source IN ('gmail','slack_dm','manual','webform','other')),
  stage                 text        NOT NULL DEFAULT 'new'
                        CHECK (stage IN ('new','qualified','hot','stalled','cold','closed_won','closed_lost')),
  score                 int         NOT NULL DEFAULT 0 CHECK (score BETWEEN 0 AND 100),
  first_seen_at         timestamptz NOT NULL DEFAULT now(),
  last_activity_at      timestamptz NOT NULL DEFAULT now(),
  last_outbound_at      timestamptz,
  next_nudge_due        timestamptz,
  tags                  text[]      DEFAULT '{}',
  notes                 text,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, email)
);

CREATE INDEX IF NOT EXISTS leads_stage_idx ON public.leads (project_id, stage, last_activity_at DESC);
CREATE INDEX IF NOT EXISTS leads_score_idx ON public.leads (project_id, score DESC, last_activity_at DESC);
CREATE INDEX IF NOT EXISTS leads_nudge_idx ON public.leads (next_nudge_due) WHERE next_nudge_due IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.sales_threads (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id            text        NOT NULL DEFAULT 'EOM',
  lead_id               uuid        REFERENCES public.leads(id) ON DELETE CASCADE,
  source                text        NOT NULL CHECK (source IN ('gmail','slack_dm')),
  source_thread_id      text        NOT NULL,
  subject               text,
  participants          text[]      NOT NULL DEFAULT '{}',
  message_count         int         NOT NULL DEFAULT 0,
  first_message_at      timestamptz NOT NULL DEFAULT now(),
  last_message_at       timestamptz NOT NULL DEFAULT now(),
  last_inbound_at       timestamptz,
  last_outbound_at      timestamptz,
  last_draft_id         text,
  last_draft_grade      text,
  summary               text,
  created_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source, source_thread_id)
);
CREATE INDEX IF NOT EXISTS sales_threads_lead_idx ON public.sales_threads (lead_id, last_message_at DESC);
CREATE INDEX IF NOT EXISTS sales_threads_project_idx ON public.sales_threads (project_id, last_message_at DESC);

CREATE TABLE IF NOT EXISTS public.lead_events (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id               uuid        REFERENCES public.leads(id) ON DELETE CASCADE,
  thread_id             uuid        REFERENCES public.sales_threads(id) ON DELETE SET NULL,
  event_type            text        NOT NULL
                        CHECK (event_type IN ('inbound','outbound','draft_created','draft_sent','stage_change','score_change','nudge_sent','nudge_skipped','meeting_detected','brief_sent')),
  event_data            jsonb,
  actor                 text        NOT NULL DEFAULT 'titan',
  created_at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS lead_events_lead_idx ON public.lead_events (lead_id, created_at DESC);
CREATE INDEX IF NOT EXISTS lead_events_type_idx ON public.lead_events (event_type, created_at DESC);

-- =========================================================================
-- THREAD 2 — Proposal Spec Generator (minimal; reuses existing tables)
-- =========================================================================

CREATE TABLE IF NOT EXISTS public.proposal_spec_runs (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id            text        NOT NULL DEFAULT 'EOM',
  lead_id               uuid        REFERENCES public.leads(id) ON DELETE SET NULL,
  source                text        CHECK (source IN ('call_notes','fireflies','manual')),
  source_ref            text,                                -- fireflies id, notes file path, etc.
  generated_spec_yaml   text,                                -- the output spec
  war_room_grade        text,
  war_room_exchange_id  uuid,                                -- FK to war_room_exchanges
  missing_fields        text[],
  status                text        NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','generating','war_room_grading','complete','failed','needs_solon_review')),
  docx_output_path      text,
  created_at            timestamptz NOT NULL DEFAULT now(),
  completed_at          timestamptz
);
CREATE INDEX IF NOT EXISTS proposal_spec_runs_status_idx ON public.proposal_spec_runs (status, created_at DESC);

-- =========================================================================
-- THREAD 3 — Recurring Marketing Engine
-- =========================================================================

CREATE TABLE IF NOT EXISTS public.marketing_content_queue (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  source                text        NOT NULL,               -- 'amg_blog','youtube','linkedin','fireflies','decisions','newsletter'
  source_url            text,
  title                 text        NOT NULL,
  summary               text,
  raw_excerpt           text,
  tags                  text[]      DEFAULT '{}',
  published_at          timestamptz,
  ingested_at           timestamptz NOT NULL DEFAULT now(),
  dedupe_hash           text        NOT NULL,
  used_in_package       boolean     NOT NULL DEFAULT false,
  used_in_package_id    uuid,
  UNIQUE (dedupe_hash)
);
CREATE INDEX IF NOT EXISTS marketing_queue_available_idx
  ON public.marketing_content_queue (ingested_at DESC) WHERE used_in_package = false;

CREATE TABLE IF NOT EXISTS public.marketing_packages (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id            text        NOT NULL DEFAULT 'EOM',
  week_iso              text        NOT NULL,                -- e.g. '2026-W15'
  primary_content_ids   uuid[],                              -- FK array into marketing_content_queue
  email_body            text,
  linkedin_body         text,
  x_body                text,
  video_brief           text,
  video_asset_url       text,
  video_asset_thumbnail text,
  status                text        NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','awaiting_approval','approved','regenerating','holding','scheduled','published','failed')),
  slack_approval_ts     text,
  approved_by           text,
  approved_at           timestamptz,
  scheduled_at          timestamptz,
  published_urls        jsonb,                               -- per surface: {email:.., linkedin:.., x:.., video:..}
  war_room_grades       jsonb,                               -- per surface grades
  regen_count           int         NOT NULL DEFAULT 0,
  created_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, week_iso)
);
CREATE INDEX IF NOT EXISTS marketing_packages_status_idx ON public.marketing_packages (status, created_at DESC);

-- =========================================================================
-- THREAD 4 — Back-Office Autopilot
-- =========================================================================

CREATE TABLE IF NOT EXISTS public.expected_payments (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id            text        NOT NULL DEFAULT 'EOM',
  customer_email        text        NOT NULL,
  customer_name         text,
  amount_usd            numeric(10,2) NOT NULL,
  due_date              date        NOT NULL,
  source                text        NOT NULL DEFAULT 'manual'
                        CHECK (source IN ('manual','build_proposal','subscription','invoice')),
  subscription_id       text,
  invoice_id            text,
  plan_id               text,
  valid_from            date        NOT NULL DEFAULT CURRENT_DATE,
  valid_until           date,
  status                text        NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','paid','late','missing','cancelled','closed','needs_review')),
  created_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (customer_email, due_date, amount_usd)
);
CREATE INDEX IF NOT EXISTS expected_payments_open_idx ON public.expected_payments (due_date) WHERE status = 'open';
CREATE INDEX IF NOT EXISTS expected_payments_customer_idx ON public.expected_payments (customer_email, due_date DESC);

CREATE TABLE IF NOT EXISTS public.received_payments (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id            text        NOT NULL DEFAULT 'EOM',
  paypal_txn_id         text        UNIQUE,
  processor             text        NOT NULL DEFAULT 'paypal'
                        CHECK (processor IN ('paypal','paymentcloud','dodo','durango','wise','zelle','wire','other')),
  customer_email        text,
  customer_name         text,
  gross_amount_usd      numeric(10,2) NOT NULL,
  fee_usd               numeric(10,2),
  net_amount_usd        numeric(10,2),
  txn_date              date        NOT NULL,
  subscription_id       text,
  invoice_id            text,
  memo                  text,
  raw_row               jsonb,
  imported_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS received_payments_customer_idx ON public.received_payments (customer_email, txn_date DESC);
CREATE INDEX IF NOT EXISTS received_payments_date_idx ON public.received_payments (txn_date DESC);

CREATE TABLE IF NOT EXISTS public.reconciliation_events (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id            text        NOT NULL DEFAULT 'EOM',
  expected_payment_id   uuid        REFERENCES public.expected_payments(id),
  received_payment_id   uuid        REFERENCES public.received_payments(id),
  classification        text        NOT NULL
                        CHECK (classification IN ('paid_on_time','paid_late','overpaid','underpaid','missing','pending','needs_solon_review')),
  variance_amount_usd   numeric(10,2),
  variance_days         int,
  notes                 text,
  created_at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS recon_events_classification_idx ON public.reconciliation_events (classification, created_at DESC);

-- =========================================================================
-- THREAD 5 — Client Reporting Autopilot
-- =========================================================================

CREATE TABLE IF NOT EXISTS public.clients (
  project_id            text        PRIMARY KEY,
  name                  text        NOT NULL,
  primary_domain        text,
  contact_name          text,
  contact_email         text,
  status                text        NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','paused','churned','prospect')),
  cadence_cron          text        DEFAULT '0 9 1 * *',    -- 1st of month 09:00
  auto_ship_enabled     boolean     NOT NULL DEFAULT false,
  auto_ship_approvals   int         NOT NULL DEFAULT 0,
  auto_ship_unlock_at   int         NOT NULL DEFAULT 4,     -- approvals needed to unlock
  red_status_rules      jsonb,
  onboarded_at          timestamptz NOT NULL DEFAULT now(),
  last_report_at        timestamptz
);

CREATE TABLE IF NOT EXISTS public.client_metric_profiles (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id            text        NOT NULL REFERENCES public.clients(project_id) ON DELETE CASCADE,
  ga4_property_id       text,
  gsc_site_url          text,
  posthog_project_id    text,
  umami_website_id      text,
  tracked_metrics       text[]      NOT NULL DEFAULT '{}',   -- 3-5 canonical metric names
  custom_kpi_sql        text,                                -- optional raw SQL for a custom KPI
  valid_from            timestamptz NOT NULL DEFAULT now(),
  valid_to              timestamptz,                         -- null = current version
  created_at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS client_metric_profiles_current_idx
  ON public.client_metric_profiles (project_id) WHERE valid_to IS NULL;

CREATE TABLE IF NOT EXISTS public.client_reports (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id            text        NOT NULL REFERENCES public.clients(project_id) ON DELETE CASCADE,
  month_iso             text        NOT NULL,                -- '2026-03'
  metrics_bundle        jsonb,
  narrative_text        text,
  report_markdown       text,
  status                text        NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','awaiting_review','approved','auto_shipping','sent','held','regenerating','failed')),
  red_status            boolean     NOT NULL DEFAULT false,
  war_room_grade        text,
  war_room_exchange_id  uuid,
  slack_approval_ts     text,
  delivery_sent_at      timestamptz,
  delivery_recipient    text,
  follow_up_tasks       uuid[],                              -- FK array into public.tasks
  created_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, month_iso)
);
CREATE INDEX IF NOT EXISTS client_reports_status_idx ON public.client_reports (status, created_at DESC);
CREATE INDEX IF NOT EXISTS client_reports_project_month_idx ON public.client_reports (project_id, month_iso DESC);

-- =========================================================================
-- RLS — enable on every new table + service-role full access + project tenant isolation
-- =========================================================================

DO $$
DECLARE
  t text;
BEGIN
  FOR t IN SELECT unnest(ARRAY[
    'leads','sales_threads','lead_events',
    'proposal_spec_runs',
    'marketing_content_queue','marketing_packages',
    'expected_payments','received_payments','reconciliation_events',
    'clients','client_metric_profiles','client_reports'
  ])
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS %I_service_role_full_access ON public.%I', t, t);
    EXECUTE format(
      'CREATE POLICY %I_service_role_full_access ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true)',
      t, t
    );
  END LOOP;
END $$;

-- Tenant isolation for tables that carry project_id
DO $$
DECLARE
  t text;
BEGIN
  FOR t IN SELECT unnest(ARRAY[
    'leads','sales_threads','proposal_spec_runs',
    'marketing_packages',
    'expected_payments','received_payments','reconciliation_events',
    'client_metric_profiles','client_reports'
  ])
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I_tenant_isolation ON public.%I', t, t);
    EXECUTE format($p$
      CREATE POLICY %I_tenant_isolation ON public.%I
        FOR ALL TO authenticated
        USING (project_id = COALESCE(current_setting('request.jwt.claim.project_id', true), project_id))
        WITH CHECK (project_id = COALESCE(current_setting('request.jwt.claim.project_id', true), project_id))
    $p$, t, t);
  END LOOP;
END $$;

-- =========================================================================
-- Comments
-- =========================================================================
COMMENT ON TABLE public.leads IS 'Thread 1 Sales Inbox: lightweight CRM / deal board. One row per unique contact in the sales pipeline.';
COMMENT ON TABLE public.sales_threads IS 'Thread 1 Sales Inbox: one row per email thread or Slack DM chain, linked to a lead.';
COMMENT ON TABLE public.lead_events IS 'Thread 1 Sales Inbox: audit trail of inbound/outbound/draft/stage events for a lead.';
COMMENT ON TABLE public.proposal_spec_runs IS 'Thread 2: proposal-spec-from-call-notes generator runs. Tracks the extractor + war-room + DOCX render flow.';
COMMENT ON TABLE public.marketing_content_queue IS 'Thread 3 Marketing: deduped feed of ingested content sources (blog, YouTube, Fireflies, decisions).';
COMMENT ON TABLE public.marketing_packages IS 'Thread 3 Marketing: weekly 4-surface publish packages (email + LinkedIn + X + video), approval + schedule state.';
COMMENT ON TABLE public.expected_payments IS 'Thread 4 Back-Office: what we expected to be paid (from subscription or invoice). Reconciled against received_payments.';
COMMENT ON TABLE public.received_payments IS 'Thread 4 Back-Office: normalized payment events imported from PayPal CSV / Paddle / Dodo / PaymentCloud etc.';
COMMENT ON TABLE public.reconciliation_events IS 'Thread 4 Back-Office: classification of expected vs received (paid_on_time, late, missing, etc.).';
COMMENT ON TABLE public.clients IS 'Thread 5 Client Reporting: active client roster with reporting cadence + auto-ship unlock state.';
COMMENT ON TABLE public.client_metric_profiles IS 'Thread 5: per-client metric source mapping (GA4 property, GSC site, tracked metric list).';
COMMENT ON TABLE public.client_reports IS 'Thread 5: monthly report artifacts with metrics bundle, narrative, delivery status, red-status flag.';
