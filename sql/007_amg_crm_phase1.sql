-- ============================================================================
-- sql/007_amg_crm_phase1.sql
-- AMG Internal CRM Phase 1 — Solon Sub-Portal backend
-- Doctrine: plans/DOCTRINE_AMG_INTERNAL_CRM_v1.0.md
-- Task: CT-0416-01 Track 3.1
-- Author: Titan · 2026-04-16
-- Apply via: Supabase SQL Editor (egoazyasyrhslluossli)
-- Idempotent: safe to re-run; all objects use IF NOT EXISTS / CREATE OR REPLACE
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 0. Prerequisites check
-- ----------------------------------------------------------------------------
-- Required extensions
CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector for semantic search
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- trigram text search fallback
CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- gen_random_uuid()

-- ----------------------------------------------------------------------------
-- 1. solon_task_queue — Solon-only tasks across all clients
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.solon_task_queue (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       uuid REFERENCES public.op_clients(id) ON DELETE SET NULL,
    title           text NOT NULL,
    description     text,
    due_at          timestamptz,
    priority        text CHECK (priority IN ('urgent','high','normal','low')) DEFAULT 'normal',
    status          text CHECK (status IN ('open','in_progress','blocked','done','cancelled')) DEFAULT 'open',
    source_channel  text,   -- 'portal-chat' / 'inbound-email' / 'inbound-sms' / 'manual'
    source_ref      text,   -- message_id or external ref
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    completed_at    timestamptz,
    tags            text[]
);
CREATE INDEX IF NOT EXISTS idx_solon_task_queue_status_due
    ON public.solon_task_queue(status, due_at NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_solon_task_queue_client
    ON public.solon_task_queue(client_id);

-- ----------------------------------------------------------------------------
-- 2. client_kpi_snapshots — hourly aggregate per client for the per-client dashboards
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.client_kpi_snapshots (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       uuid NOT NULL REFERENCES public.op_clients(id) ON DELETE CASCADE,
    captured_at     timestamptz NOT NULL DEFAULT now(),
    gbp_views       integer,
    gbp_calls       integer,
    gbp_directions  integer,
    gbp_messages    integer,
    conv_started    integer,
    conv_closed_won integer,
    conv_closed_lost integer,
    revenue_mtd_cents  bigint,
    revenue_ytd_cents  bigint,
    outstanding_invoice_cents bigint,
    content_shipped integer,
    tasks_open      integer,
    raw             jsonb
);
CREATE INDEX IF NOT EXISTS idx_client_kpi_client_time
    ON public.client_kpi_snapshots(client_id, captured_at DESC);

-- ----------------------------------------------------------------------------
-- 3. semantic_embeddings — pgvector table for cross-client search
-- ----------------------------------------------------------------------------
-- 1536-dim = OpenAI text-embedding-3-small (cost-optimal; 3-large is 3072-dim)
CREATE TABLE IF NOT EXISTS public.semantic_embeddings (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type     text NOT NULL,  -- 'message' / 'document' / 'agenda' / 'email' / 'sms' / 'carryover'
    source_id       uuid NOT NULL,
    client_id       uuid REFERENCES public.op_clients(id) ON DELETE CASCADE,
    content         text NOT NULL,          -- the embedded chunk
    content_tsv     tsvector,               -- full-text fallback
    embedding       vector(1536),           -- OpenAI 1536-dim
    meta            jsonb,                  -- e.g., { "speaker": "Levar", "channel": "sms", "thread_id": "..." }
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- HNSW index for fast ANN search (better than IVFFlat for < 1M rows)
CREATE INDEX IF NOT EXISTS idx_semantic_embeddings_hnsw
    ON public.semantic_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_semantic_embeddings_client
    ON public.semantic_embeddings(client_id);
CREATE INDEX IF NOT EXISTS idx_semantic_embeddings_source
    ON public.semantic_embeddings(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_semantic_embeddings_tsv
    ON public.semantic_embeddings USING gin (content_tsv);

-- Trigger to auto-populate tsvector
CREATE OR REPLACE FUNCTION public.semantic_embeddings_tsv_update()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.content_tsv := to_tsvector('english', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_semantic_embeddings_tsv ON public.semantic_embeddings;
CREATE TRIGGER trg_semantic_embeddings_tsv
    BEFORE INSERT OR UPDATE ON public.semantic_embeddings
    FOR EACH ROW EXECUTE FUNCTION public.semantic_embeddings_tsv_update();

-- ----------------------------------------------------------------------------
-- 4. solon_activity_feed — materialized cross-client activity stream
-- Pulls from messages + op_deals + op_invoices + chat_sessions into one ordered view
-- ----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS public.solon_activity_feed AS
SELECT
    'message'::text                AS kind,
    m.id                           AS row_id,
    m.client_id                    AS client_id,
    c.display_name                 AS client_name,
    m.created_at                   AS event_at,
    m.role                         AS actor,
    LEFT(m.content, 280)           AS summary,
    jsonb_build_object(
        'session_id', m.session_id,
        'channel', COALESCE(m.meta->>'channel', 'portal-chat')
    )                              AS meta
FROM public.messages m
LEFT JOIN public.op_clients c ON c.id = m.client_id
WHERE m.created_at > now() - interval '30 days'

UNION ALL

SELECT
    'deal'::text                    AS kind,
    d.id                            AS row_id,
    d.client_id                     AS client_id,
    c.display_name                  AS client_name,
    d.updated_at                    AS event_at,
    d.stage                         AS actor,
    COALESCE(d.title, 'Deal update') AS summary,
    jsonb_build_object(
        'stage', d.stage,
        'amount_cents', d.amount_cents,
        'probability', d.probability
    )                               AS meta
FROM public.op_deals d
LEFT JOIN public.op_clients c ON c.id = d.client_id
WHERE d.updated_at > now() - interval '30 days'

UNION ALL

SELECT
    'invoice'::text                 AS kind,
    i.id                            AS row_id,
    i.client_id                     AS client_id,
    c.display_name                  AS client_name,
    i.issued_at                     AS event_at,
    i.status                        AS actor,
    COALESCE(i.title, 'Invoice '||i.number) AS summary,
    jsonb_build_object(
        'status', i.status,
        'amount_cents', i.total_cents,
        'currency', i.currency,
        'due_at', i.due_at
    )                               AS meta
FROM public.op_invoices i
LEFT JOIN public.op_clients c ON c.id = i.client_id
WHERE i.issued_at > now() - interval '90 days'

ORDER BY event_at DESC;

CREATE INDEX IF NOT EXISTS idx_solon_activity_feed_event
    ON public.solon_activity_feed(event_at DESC);
CREATE INDEX IF NOT EXISTS idx_solon_activity_feed_client
    ON public.solon_activity_feed(client_id);
CREATE INDEX IF NOT EXISTS idx_solon_activity_feed_kind
    ON public.solon_activity_feed(kind);

-- Refresh function — call hourly or on-demand
CREATE OR REPLACE FUNCTION public.refresh_solon_activity_feed()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.solon_activity_feed;
EXCEPTION WHEN OTHERS THEN
    -- Fallback to non-concurrent if indexes not ready
    REFRESH MATERIALIZED VIEW public.solon_activity_feed;
END;
$$;

-- ----------------------------------------------------------------------------
-- 5. solon_pipeline — simple view over op_deals (live, not materialized)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.solon_pipeline AS
SELECT
    d.id,
    d.client_id,
    c.display_name                 AS client_name,
    d.stage,
    d.title,
    d.amount_cents,
    d.probability,
    (d.amount_cents * COALESCE(d.probability, 0.5) / 100)::bigint AS weighted_cents,
    d.expected_close_at,
    d.created_at,
    d.updated_at
FROM public.op_deals d
LEFT JOIN public.op_clients c ON c.id = d.client_id
WHERE d.stage NOT IN ('archived','duplicate');

-- ----------------------------------------------------------------------------
-- 6. solon_unified_inbox — view across chat + email + sms (via messages.meta.channel)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.solon_unified_inbox AS
SELECT
    m.id,
    m.client_id,
    c.display_name                 AS client_name,
    m.session_id,
    m.role,
    m.content,
    m.created_at,
    COALESCE(m.meta->>'channel', 'portal-chat') AS channel,
    m.meta->>'from_address'        AS from_address,
    m.meta->>'thread_id'           AS thread_id,
    COALESCE((m.meta->>'read')::boolean, false) AS read
FROM public.messages m
LEFT JOIN public.op_clients c ON c.id = m.client_id
WHERE m.created_at > now() - interval '60 days'
  AND m.role IN ('user','client','agent');   -- exclude system noise

-- ----------------------------------------------------------------------------
-- 7. solon_revenue_rollup — monthly / quarterly / YTD by client
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.solon_revenue_rollup AS
SELECT
    client_id,
    date_trunc('month', issued_at)       AS month,
    SUM(total_cents) FILTER (WHERE status = 'paid')      AS paid_cents,
    SUM(total_cents) FILTER (WHERE status = 'open')      AS open_cents,
    SUM(total_cents) FILTER (WHERE status = 'overdue')   AS overdue_cents,
    COUNT(*) FILTER (WHERE status = 'paid')              AS paid_count,
    COUNT(*) FILTER (WHERE status IN ('open','overdue')) AS outstanding_count
FROM public.op_invoices
WHERE issued_at > now() - interval '18 months'
GROUP BY client_id, date_trunc('month', issued_at);

-- ----------------------------------------------------------------------------
-- 8. semantic search RPC — match against semantic_embeddings, scoped by client
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.match_solon_memory (
    query_embedding   vector(1536),
    client_filter     uuid DEFAULT NULL,
    match_count       int  DEFAULT 20,
    similarity_floor  float DEFAULT 0.6
)
RETURNS TABLE (
    id          uuid,
    client_id   uuid,
    source_type text,
    source_id   uuid,
    content     text,
    similarity  float,
    meta        jsonb,
    created_at  timestamptz
)
LANGUAGE plpgsql STABLE AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.client_id,
        e.source_type,
        e.source_id,
        e.content,
        1 - (e.embedding <=> query_embedding) AS similarity,
        e.meta,
        e.created_at
    FROM public.semantic_embeddings e
    WHERE (client_filter IS NULL OR e.client_id = client_filter)
      AND (1 - (e.embedding <=> query_embedding)) >= similarity_floor
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ----------------------------------------------------------------------------
-- 9. Row Level Security
-- Policy: Solon (email matching solon@aimarketinggenius.io or solon@amg.solon OR role='solon_admin') can read all.
-- Everyone else: only their client_id row (via existing op_* RLS).
-- ----------------------------------------------------------------------------
ALTER TABLE public.solon_task_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.client_kpi_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.semantic_embeddings ENABLE ROW LEVEL SECURITY;

-- Drop prior policies (idempotent)
DROP POLICY IF EXISTS solon_full_access ON public.solon_task_queue;
DROP POLICY IF EXISTS solon_full_access ON public.client_kpi_snapshots;
DROP POLICY IF EXISTS solon_full_access ON public.semantic_embeddings;
DROP POLICY IF EXISTS client_tenant_access ON public.semantic_embeddings;

-- Solon can see everything
CREATE POLICY solon_full_access ON public.solon_task_queue
    FOR ALL TO authenticated
    USING (
        auth.jwt() ->> 'email' IN ('solon@aimarketinggenius.io','growmybusiness@aimarketinggenius.io','solon@amg.solon')
        OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'solon_admin'
    );

CREATE POLICY solon_full_access ON public.client_kpi_snapshots
    FOR ALL TO authenticated
    USING (
        auth.jwt() ->> 'email' IN ('solon@aimarketinggenius.io','growmybusiness@aimarketinggenius.io','solon@amg.solon')
        OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'solon_admin'
    );

CREATE POLICY solon_full_access ON public.semantic_embeddings
    FOR ALL TO authenticated
    USING (
        auth.jwt() ->> 'email' IN ('solon@aimarketinggenius.io','growmybusiness@aimarketinggenius.io','solon@amg.solon')
        OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'solon_admin'
    );

-- Clients see only their own embeddings (strict tenant partition)
CREATE POLICY client_tenant_access ON public.semantic_embeddings
    FOR SELECT TO authenticated
    USING (
        client_id = (auth.jwt() -> 'app_metadata' ->> 'client_id')::uuid
    );

-- ----------------------------------------------------------------------------
-- 10. Grants
-- ----------------------------------------------------------------------------
GRANT SELECT ON public.solon_activity_feed  TO authenticated;
GRANT SELECT ON public.solon_pipeline       TO authenticated;
GRANT SELECT ON public.solon_unified_inbox  TO authenticated;
GRANT SELECT ON public.solon_revenue_rollup TO authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.solon_task_queue       TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.client_kpi_snapshots   TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.semantic_embeddings    TO authenticated;

GRANT EXECUTE ON FUNCTION public.match_solon_memory(vector, uuid, int, float) TO authenticated;
GRANT EXECUTE ON FUNCTION public.refresh_solon_activity_feed()               TO authenticated;

-- ----------------------------------------------------------------------------
-- 11. Seed: spelling_rule_sungemmers (P10 rule from CT-0415-14-CORRECTION)
-- ----------------------------------------------------------------------------
INSERT INTO public.client_facts (client_id, fact_key, fact_value, is_required_in_deliverable, source)
SELECT
    c.id,
    'spelling_rule_sungemmers',
    'Canonical spelling: "Sungemmers" (plural, generic product line references) and "Sungemmer" (singular, specific SKU matching Shopify URL slug shsesg-emoji%e2%84%a2-sungemmer). Never "Sun Jammer" / "SunJammer" / "SunGemmer" / "Sun-Gemmer".',
    true,
    'CT-0416-01 Solon correction — supersedes prior CT-0415-14 lock'
FROM public.op_clients c
WHERE c.display_name ILIKE '%shop unis%'
  AND NOT EXISTS (
      SELECT 1 FROM public.client_facts cf
      WHERE cf.client_id = c.id AND cf.fact_key = 'spelling_rule_sungemmers'
  );

-- ----------------------------------------------------------------------------
-- 12. Smoke tests
-- ----------------------------------------------------------------------------
-- Confirm every expected object exists
DO $$
DECLARE
    missing text := '';
BEGIN
    FOR r IN
        SELECT unnest(ARRAY[
            'solon_task_queue','client_kpi_snapshots','semantic_embeddings'
        ]) AS t
    LOOP
        IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = r.t) THEN
            missing := missing || r.t || ', ';
        END IF;
    END LOOP;
    IF length(missing) > 0 THEN
        RAISE EXCEPTION 'Missing expected tables: %', missing;
    END IF;
    RAISE NOTICE '007: all tables present';
END$$;

-- End of sql/007_amg_crm_phase1.sql
