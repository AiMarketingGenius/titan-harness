-- sql/150_client_facts.sql
-- CT-0417-F1: client-specific context for project-backed agents.
-- Read by agent_context_loader MCP tool; joined per-client at agent-call time.
--
-- Idempotent. Run against the operator Supabase (egoazyasyrhslluossli.supabase.co).
-- Reads from: log_decision (via project_source), WoZ agent transcripts.
-- Writes from: WoZ intake form, manual curation, fact-harvesting pipeline.

BEGIN;

CREATE TABLE IF NOT EXISTS public.client_facts (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id          text NOT NULL,                      -- slug: levar, shop-unis, revere-chamber, etc.
  fact_type          text NOT NULL
                     CHECK (fact_type IN (
                       'brand',              -- brand attributes, voice, values
                       'audience',           -- target segments, personas
                       'voice_sample',       -- direct quote from client / voice marker
                       'active_campaign',    -- what's currently running
                       'recent_decision',    -- decisions the client has made (from convo log)
                       'do_not_mention',     -- topics / competitors / sensitivities
                       'hot_button',         -- things the client cares deeply about
                       'pricing',            -- client-specific pricing/tier
                       'contact',            -- primary contacts, decision makers
                       'inventory',          -- products, services, SKUs
                       'kpi',                -- current performance metrics
                       'constraint'          -- legal, technical, budget constraints
                     )),
  content            text NOT NULL,                      -- the fact itself (plain text, ≤ ~500 chars ideal)
  confidence         real DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),
  source             text,                               -- 'solon_loom_mp1', 'woz_transcript', 'intake_form',
                                                          -- 'manual_curation', 'automated_extraction'
  source_ref         text,                               -- URL or file path to origin evidence
  created_at         timestamptz NOT NULL DEFAULT now(),
  last_verified_at   timestamptz,
  superseded         boolean NOT NULL DEFAULT false,
  superseded_at      timestamptz,
  superseded_by      uuid REFERENCES public.client_facts(id),
  tags               text[] DEFAULT '{}',
  embedding          vector(768),                        -- optional: populated for semantic recall within client facts
  operator_id        text DEFAULT 'OPERATOR_AMG'
);

-- Primary read path: fetch active facts for a client, highest confidence first
CREATE INDEX IF NOT EXISTS idx_client_facts_client_active
  ON public.client_facts (client_id, confidence DESC, created_at DESC)
  WHERE superseded = false;

-- Filter by fact_type when agent_context_loader wants only 'active_campaign' etc
CREATE INDEX IF NOT EXISTS idx_client_facts_client_type
  ON public.client_facts (client_id, fact_type)
  WHERE superseded = false;

-- Semantic search within a client's facts (optional — populated lazily)
CREATE INDEX IF NOT EXISTS idx_client_facts_embedding
  ON public.client_facts
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);

-- RLS: tenants see only their own rows. Service role bypasses.
ALTER TABLE public.client_facts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS client_facts_tenant_read ON public.client_facts;
CREATE POLICY client_facts_tenant_read ON public.client_facts
  FOR SELECT
  USING (client_id = current_setting('app.current_client_id', true));

DROP POLICY IF EXISTS client_facts_service_role_all ON public.client_facts;
CREATE POLICY client_facts_service_role_all ON public.client_facts
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- RPC: fetch top-N active facts for a client, formatted for agent context injection
CREATE OR REPLACE FUNCTION public.op_get_client_facts(
  p_client_id text,
  p_max_facts int DEFAULT 40,
  p_fact_types text[] DEFAULT NULL
) RETURNS TABLE (
  id uuid,
  fact_type text,
  content text,
  confidence real,
  created_at timestamptz,
  tags text[]
) LANGUAGE sql STABLE AS $$
  SELECT id, fact_type, content, confidence, created_at, tags
  FROM public.client_facts
  WHERE client_id = p_client_id
    AND superseded = false
    AND (p_fact_types IS NULL OR fact_type = ANY(p_fact_types))
  ORDER BY confidence DESC, created_at DESC
  LIMIT p_max_facts;
$$;

GRANT EXECUTE ON FUNCTION public.op_get_client_facts(text, int, text[]) TO service_role;

COMMIT;

-- Seed examples (safe to re-run; uses ON CONFLICT implicit via uuid pk).
-- Minimal seed so agent_context_loader returns non-empty results in dev.

INSERT INTO public.client_facts (client_id, fact_type, content, confidence, source) VALUES
  ('levar', 'brand', 'JDJ Investment Properties — Lynn MA real-estate operator. Signature voice: confident, direct, community-first.', 1.0, 'manual_curation'),
  ('levar', 'audience', 'Primary: Boston North Shore first-time home buyers + investors 35-55. Secondary: Lynn/Revere/Saugus local businesses for commercial leases.', 1.0, 'manual_curation'),
  ('levar', 'pricing', 'AMG subscriber since April 2026. Tier: Full Ops bundle. Paying $1,297 m1-3 → $797 m4-12. Year-1 value $11,064.', 1.0, 'mcp_decision_recall'),
  ('shop-unis', 'brand', 'SUNGEMMERS (plural product line) / SUNGEMMER (singular). Locked canonical spelling 2026-04-15. Never SunGemmer.', 1.0, 'mcp_decision_recall'),
  ('revere-chamber', 'brand', 'Revere Chamber of Commerce, Revere MA. Navy #0a2d5e + gold #d4a627. Board President: Don. Founding Partner status pending signature.', 1.0, 'manual_curation')
ON CONFLICT DO NOTHING;
