-- ============================================================================
-- sql/008_amg_crm_contacts.sql
-- AMG CRM Phase 1 — Contacts + Pipeline + Activities + Persistent Memory
-- Doctrine: CT-0417-29 (Solon directive 2026-04-17)
-- Author: Titan · 2026-04-17
-- Apply via: Supabase SQL Editor (egoazyasyrhslluossli) — Solon manual paste
-- Idempotent: safe to re-run; all objects use IF NOT EXISTS / CREATE OR REPLACE
--
-- Companion: sql/007_amg_crm_phase1.sql (Solon Sub-Portal — solon_task_queue,
--             client_kpi_snapshots, semantic_embeddings, etc.)
-- This file (008) defines the CRM-Phase-1 surface area named in the CT-0417-29
-- brief: crm_contacts, crm_leads, crm_deals, crm_activities, crm_persistent_memory.
-- 008 is independent of 007 (no FK from 008 → 007), so 008 can apply before 007
-- if needed for the Mobile Command CRM ship.
--
-- Sequence note: at probe time (2026-04-17), the operator project had ZERO
-- of these CRM tables AND zero of sql/007's tables. Both 007 and 008 still
-- need Solon paste before T1 verification can pass.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 0. Prerequisites
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto;       -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pg_trgm;        -- trigram search on contact names
-- Vector extension is OPTIONAL for the persistent-memory layer; enabled by 007
-- if Solon also paste-applies sql/007. We do not require it here.

-- ----------------------------------------------------------------------------
-- 1. crm_contacts — primary contact-of-record per Chamber/client/individual
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.crm_contacts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            text UNIQUE NOT NULL,         -- e.g. 'jdj-levar', 'shop-unis', 'revere-chamber'
    display_name    text NOT NULL,                -- 'JDJ Investment Properties (Levar)'
    contact_name    text,                          -- 'Don Martelli'
    contact_email   text,
    contact_phone   text,
    company         text,
    address         text,
    city            text,
    state           text,
    zip             text,
    timezone        text DEFAULT 'America/New_York',
    tags            text[],
    notes           text,
    persistent_memory_ref  uuid,                  -- FK to crm_persistent_memory.namespace_id (added later via ALTER, after that table exists)
    source_channel  text,                          -- 'inbound-email' / 'referral' / 'event' / 'cold-outbound' / 'manual'
    source_ref      text,                          -- arbitrary external ref (Linear ticket, Slack thread, etc.)
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_crm_contacts_slug
    ON public.crm_contacts (slug);
CREATE INDEX IF NOT EXISTS idx_crm_contacts_email
    ON public.crm_contacts (contact_email);
CREATE INDEX IF NOT EXISTS idx_crm_contacts_name_trgm
    ON public.crm_contacts USING gin (display_name gin_trgm_ops);

-- ----------------------------------------------------------------------------
-- 2. crm_leads — top-of-funnel prospects (pre-deal)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.crm_leads (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id      uuid REFERENCES public.crm_contacts(id) ON DELETE SET NULL,
    lead_source     text,                          -- 'website' / 'referral' / 'gbp' / 'event' / 'outbound'
    stage           text NOT NULL CHECK (stage IN ('new','qualifying','qualified','disqualified')) DEFAULT 'new',
    intent_score    integer CHECK (intent_score BETWEEN 0 AND 100),
    first_contact_at timestamptz NOT NULL DEFAULT now(),
    qualified_at    timestamptz,
    notes           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_crm_leads_stage
    ON public.crm_leads (stage);
CREATE INDEX IF NOT EXISTS idx_crm_leads_contact
    ON public.crm_leads (contact_id);

-- ----------------------------------------------------------------------------
-- 3. crm_deals — qualified opportunities through close
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.crm_deals (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id      uuid NOT NULL REFERENCES public.crm_contacts(id) ON DELETE CASCADE,
    lead_id         uuid REFERENCES public.crm_leads(id) ON DELETE SET NULL,
    title           text NOT NULL,                -- 'Revere Chamber AI Advantage — Founding Partner'
    stage           text NOT NULL CHECK (stage IN
        ('discovery','proposal-sent','negotiation','closed-won','closed-lost','on-hold')) DEFAULT 'discovery',
    amount_cents    bigint,                        -- one-time setup OR ARR — capture both via metadata
    currency        text NOT NULL DEFAULT 'USD',
    metadata        jsonb DEFAULT '{}'::jsonb,    -- {setup_cents, monthly_cents, annual_cents, term_months, board_courtesy_pct}
    expected_close  date,
    closed_at       timestamptz,
    win_reason      text,                          -- when closed-won
    loss_reason     text,                          -- when closed-lost
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_crm_deals_stage
    ON public.crm_deals (stage);
CREATE INDEX IF NOT EXISTS idx_crm_deals_contact
    ON public.crm_deals (contact_id);
CREATE INDEX IF NOT EXISTS idx_crm_deals_close_date
    ON public.crm_deals (expected_close);

-- ----------------------------------------------------------------------------
-- 4. crm_activities — append-only activity feed per contact
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.crm_activities (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id      uuid NOT NULL REFERENCES public.crm_contacts(id) ON DELETE CASCADE,
    deal_id         uuid REFERENCES public.crm_deals(id) ON DELETE SET NULL,
    activity_type   text NOT NULL CHECK (activity_type IN
        ('call','email-sent','email-received','sms','meeting','note','stage-change','document-shared','demo')),
    direction       text CHECK (direction IN ('inbound','outbound','internal')),
    summary         text NOT NULL,
    body            text,
    actor           text NOT NULL,                 -- 'titan' / 'eom' / 'solon' / 'auto-mcp-sync' / external email addr
    actor_role      text,                          -- 'operator' / 'agent' / 'subscriber-side' / 'system'
    occurred_at     timestamptz NOT NULL DEFAULT now(),
    metadata        jsonb DEFAULT '{}'::jsonb,    -- {duration_min, attendees[], decision_id, source_thread_id}
    mcp_decision_id text,                          -- back-reference to MCP decision row
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_crm_activities_contact_time
    ON public.crm_activities (contact_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_crm_activities_deal
    ON public.crm_activities (deal_id);
CREATE INDEX IF NOT EXISTS idx_crm_activities_mcp
    ON public.crm_activities (mcp_decision_id);

-- ----------------------------------------------------------------------------
-- 5. crm_persistent_memory — per-contact persistent memory namespace
-- ----------------------------------------------------------------------------
-- Each contact gets a memory namespace. Every Titan/EOM interaction with that
-- contact's deal/relationship can write to + read from this namespace. The
-- get_unified_context() MCP tool surfaces these into Atlas's prompt as
-- per-contact ranked context. Designed for compact growth (<= 50KB / contact
-- in v1; pgvector embeddings come later when sql/007 lands).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.crm_persistent_memory (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id      uuid NOT NULL REFERENCES public.crm_contacts(id) ON DELETE CASCADE,
    namespace_id    uuid NOT NULL DEFAULT gen_random_uuid(),  -- one per contact; can be regenerated for full reset
    memory_type     text NOT NULL CHECK (memory_type IN
        ('fact','preference','rule','context','blocker','decision','timeline','contact-detail')),
    text_content    text NOT NULL,                 -- the memory text itself
    importance      smallint NOT NULL DEFAULT 5 CHECK (importance BETWEEN 1 AND 10),
    written_by      text NOT NULL,                 -- 'titan' / 'eom' / 'auto-from-mcp' / etc.
    source_decision_id text,                       -- if derived from an MCP decision row
    valid_from      timestamptz NOT NULL DEFAULT now(),
    valid_until     timestamptz,                   -- nullable = perpetual
    superseded_by   uuid REFERENCES public.crm_persistent_memory(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_crm_persistent_memory_contact
    ON public.crm_persistent_memory (contact_id);
CREATE INDEX IF NOT EXISTS idx_crm_persistent_memory_namespace
    ON public.crm_persistent_memory (namespace_id);
CREATE INDEX IF NOT EXISTS idx_crm_persistent_memory_type
    ON public.crm_persistent_memory (memory_type);
-- Trigram index lets the unified-context API do fast keyword-relevance ranking
-- without yet needing pgvector. Upgrade path to embeddings is additive.
CREATE INDEX IF NOT EXISTS idx_crm_persistent_memory_text_trgm
    ON public.crm_persistent_memory USING gin (text_content gin_trgm_ops);

-- crm_contacts.persistent_memory_ref intentionally does NOT have a FK
-- constraint to crm_persistent_memory.namespace_id — namespace_id is shared
-- across multiple memory rows belonging to the same contact, so it cannot
-- carry a UNIQUE constraint. The relationship is enforced at the application
-- layer: when a contact is created, atlas-api generates a UUID and stores it
-- both as crm_contacts.persistent_memory_ref AND as the namespace_id for
-- every subsequent memory row inserted for that contact. The contact-side
-- FK that DOES exist is crm_persistent_memory.contact_id → crm_contacts.id
-- (declared in the table definition above), which is sufficient for cascade
-- delete + integrity. The persistent_memory_ref column on crm_contacts is a
-- denormalized cache of "current active namespace" — convenient for the
-- get_unified_context() lookup hot-path.

-- ----------------------------------------------------------------------------
-- 6. updated_at trigger (applied to all mutable tables)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END$$;

DO $$
BEGIN
    -- Idempotent trigger creation
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_crm_contacts_updated_at') THEN
        CREATE TRIGGER trg_crm_contacts_updated_at
            BEFORE UPDATE ON public.crm_contacts
            FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_crm_leads_updated_at') THEN
        CREATE TRIGGER trg_crm_leads_updated_at
            BEFORE UPDATE ON public.crm_leads
            FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_crm_deals_updated_at') THEN
        CREATE TRIGGER trg_crm_deals_updated_at
            BEFORE UPDATE ON public.crm_deals
            FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    END IF;
END$$;

-- ----------------------------------------------------------------------------
-- 7. RLS — Solon-only access in v1; consumer/contact-side access via API later
-- ----------------------------------------------------------------------------
ALTER TABLE public.crm_contacts            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crm_leads               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crm_deals               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crm_activities          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crm_persistent_memory   ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS automatically; this policy gates the anon role
-- from reading/writing CRM data unless we explicitly grant per-contact access.
-- For v1: anon = no access. Service role = full access. UI uses service role
-- behind atlas-api which owns the auth gate.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'crm_contacts_service_only') THEN
        CREATE POLICY crm_contacts_service_only ON public.crm_contacts
            FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'crm_leads_service_only') THEN
        CREATE POLICY crm_leads_service_only ON public.crm_leads
            FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'crm_deals_service_only') THEN
        CREATE POLICY crm_deals_service_only ON public.crm_deals
            FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'crm_activities_service_only') THEN
        CREATE POLICY crm_activities_service_only ON public.crm_activities
            FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'crm_persistent_memory_service_only') THEN
        CREATE POLICY crm_persistent_memory_service_only ON public.crm_persistent_memory
            FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');
    END IF;
END$$;

-- ----------------------------------------------------------------------------
-- 8. Smoke tests (run AFTER applying — confirms tables + indexes + RLS exist)
-- ----------------------------------------------------------------------------
-- SELECT count(*) FROM public.crm_contacts;            -- 0 expected
-- SELECT count(*) FROM public.crm_leads;               -- 0 expected
-- SELECT count(*) FROM public.crm_deals;               -- 0 expected
-- SELECT count(*) FROM public.crm_activities;          -- 0 expected
-- SELECT count(*) FROM public.crm_persistent_memory;   -- 0 expected
-- SELECT tablename, rowsecurity FROM pg_tables WHERE tablename LIKE 'crm_%';
-- SELECT policyname FROM pg_policies WHERE tablename LIKE 'crm_%';

-- ============================================================================
-- END sql/008_amg_crm_contacts.sql
-- ============================================================================
