-- titan-harness/sql/140_white_label_tenant_config.sql
-- LG7 — White-label tenant + per-tenant config tables.
-- Per Solon directive 2026-04-16 (mobile-command-tiered + white-label code pattern).
--
-- Two-table design:
--   `tenants` — one row per AMG client (Levar, future Chamber partners, etc.)
--               + tier (starter|growth|pro) + mobile_app_enabled (Pro-only) + branding JSONB
--   `tenant_config` — extracted hardcoded strings + per-route overrides
--                     (brand_name, logo_url, CSS vars, agent_aliases)
--
-- Designed so portal code reads tenant_id from cookie/JWT → joins to tenants +
-- tenant_config → applies branding without code changes per client.
--
-- Run order: AFTER sql/130_agent_voice_library.sql (no dependency, just numbering).
-- Idempotent — uses IF NOT EXISTS throughout.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. tenants table (one row per AMG client)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.tenants (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Identity
  slug                  text NOT NULL UNIQUE,        -- e.g. 'levar', 'revere-chamber', 'amg-internal'
  display_name          text NOT NULL,               -- 'Levar Real Estate', 'Revere Chamber of Commerce'
  legal_name            text,                        -- optional formal name for invoices

  -- Tier (gates feature access)
  tier                  text NOT NULL DEFAULT 'starter'
                        CHECK (tier IN ('starter', 'growth', 'pro', 'enterprise', 'amg_internal')),

  -- Pricing snapshot (informational, not enforced — billing system is source of truth)
  monthly_price_usd     numeric(10,2),

  -- Pro-tier feature gates
  mobile_app_enabled    boolean NOT NULL DEFAULT false,  -- true ONLY when tier='pro' or 'enterprise'
  mobile_app_branding   jsonb,                            -- logo_url, primary/accent colors, agent_aliases

  -- White-label flag — when true, portal renders this tenant's branding instead of AMG's
  white_label           boolean NOT NULL DEFAULT false,

  -- Lifecycle
  status                text NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'paused', 'churned', 'pending_onboard')),
  onboarded_at          timestamptz,
  churned_at            timestamptz,

  -- Audit
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),
  notes                 text                          -- internal notes (not exposed to client)
);

-- Trigger: auto-update updated_at
CREATE OR REPLACE FUNCTION public.tenants_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tenants_updated_at_trg ON public.tenants;
CREATE TRIGGER tenants_updated_at_trg
  BEFORE UPDATE ON public.tenants
  FOR EACH ROW
  EXECUTE FUNCTION public.tenants_set_updated_at();

-- Constraint: mobile_app_enabled only allowed for pro / enterprise / amg_internal
ALTER TABLE public.tenants DROP CONSTRAINT IF EXISTS tenants_mobile_app_pro_only;
ALTER TABLE public.tenants ADD CONSTRAINT tenants_mobile_app_pro_only
  CHECK (
    (mobile_app_enabled = false)
    OR (tier IN ('pro', 'enterprise', 'amg_internal'))
  );

CREATE INDEX IF NOT EXISTS idx_tenants_tier         ON public.tenants (tier);
CREATE INDEX IF NOT EXISTS idx_tenants_status       ON public.tenants (status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_tenants_white_label  ON public.tenants (white_label) WHERE white_label = true;


-- ---------------------------------------------------------------------------
-- 2. tenant_config table (per-tenant overrides for hardcoded strings)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.tenant_config (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,

  -- Brand identity (overrides AMG defaults when white_label=true on the tenants row)
  brand_name      text,                            -- 'Revere Chamber Marketing', not 'AMG'
  brand_tagline   text,
  logo_url        text,                            -- absolute URL or /assets/... relative path
  favicon_url     text,

  -- Theme (CSS vars portal can inject into :root)
  theme           jsonb DEFAULT jsonb_build_object(
                     'primary',   '#1e40af',       -- AMG default navy
                     'accent',    '#fbbf24',       -- AMG default gold
                     'bg',        '#0f172a',       -- dark slate
                     'text',      '#f1f5f9',       -- near-white
                     'font_body', 'Inter, sans-serif',
                     'font_head', 'Inter, sans-serif'
                  ),

  -- Per-tenant agent aliases (Revere Chamber wants "Revere Business Coach" not "Alex")
  agent_aliases   jsonb DEFAULT jsonb_build_object(
                     'alex',   'Account Manager',
                     'maya',   'Content Lead',
                     'jordan', 'Reputation Manager',
                     'sam',    'SEO Lead',
                     'riley',  'Strategy Lead',
                     'nadia',  'Onboarding Specialist',
                     'lumina', 'CRO Expert'
                  ),

  -- Optional per-tenant override of which agents are enabled (Pro tier may unlock all 7,
  -- Starter may only show 3). NULL = all 7 active.
  enabled_agents  text[] DEFAULT NULL
                  CHECK (
                    enabled_agents IS NULL
                    OR enabled_agents <@ ARRAY['alex','maya','jordan','sam','riley','nadia','lumina']
                  ),

  -- Per-tenant CTA + signup URLs (white-label may point to client's own landing)
  signup_url      text,
  contact_url     text,

  -- Free-form per-tenant overrides (catch-all for stuff not yet promoted to typed columns)
  extras          jsonb DEFAULT '{}'::jsonb,

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  UNIQUE (tenant_id)  -- one config row per tenant
);

DROP TRIGGER IF EXISTS tenant_config_updated_at_trg ON public.tenant_config;
CREATE TRIGGER tenant_config_updated_at_trg
  BEFORE UPDATE ON public.tenant_config
  FOR EACH ROW
  EXECUTE FUNCTION public.tenants_set_updated_at();

CREATE INDEX IF NOT EXISTS idx_tenant_config_tenant ON public.tenant_config (tenant_id);


-- ---------------------------------------------------------------------------
-- 3. Row-Level Security (service-role write, tenant-scoped read)
-- ---------------------------------------------------------------------------

ALTER TABLE public.tenants        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_config  ENABLE ROW LEVEL SECURITY;

-- Service role can do anything (Titan / harness writes via service key)
DROP POLICY IF EXISTS tenants_service_role_all ON public.tenants;
CREATE POLICY tenants_service_role_all ON public.tenants
  FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS tenant_config_service_role_all ON public.tenant_config;
CREATE POLICY tenant_config_service_role_all ON public.tenant_config
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Authenticated users (portal users) can read their own tenant's row only.
-- Note: assumes JWT has 'tenant_id' claim — adjust if your auth scheme differs.
DROP POLICY IF EXISTS tenants_self_read ON public.tenants;
CREATE POLICY tenants_self_read ON public.tenants
  FOR SELECT TO authenticated
  USING (id = ((current_setting('request.jwt.claims', true))::jsonb ->> 'tenant_id')::uuid);

DROP POLICY IF EXISTS tenant_config_self_read ON public.tenant_config;
CREATE POLICY tenant_config_self_read ON public.tenant_config
  FOR SELECT TO authenticated
  USING (tenant_id = ((current_setting('request.jwt.claims', true))::jsonb ->> 'tenant_id')::uuid);


-- ---------------------------------------------------------------------------
-- 4. Seed rows (idempotent — use UPSERT)
-- ---------------------------------------------------------------------------

-- AMG internal tenant (Solon's own org, full feature access)
INSERT INTO public.tenants (slug, display_name, legal_name, tier, mobile_app_enabled, white_label, status, notes)
VALUES (
  'amg-internal',
  'AI Marketing Genius',
  'AI Marketing Genius LLC',
  'amg_internal',
  true,
  false,
  'active',
  'Solon owner-tenant. Full feature access. Bypasses all paywall checks.'
)
ON CONFLICT (slug) DO UPDATE SET
  display_name        = EXCLUDED.display_name,
  tier                = EXCLUDED.tier,
  mobile_app_enabled  = EXCLUDED.mobile_app_enabled,
  status              = EXCLUDED.status;

-- Levar (founding paying client, Pro tier so mobile app unlocks)
INSERT INTO public.tenants (slug, display_name, tier, monthly_price_usd, mobile_app_enabled, white_label, status, notes)
VALUES (
  'levar',
  'Levar Real Estate',
  'pro',
  1497.00,
  true,
  false,
  'active',
  'Founding member. Pro tier. Demo asset for Friday Revere pitch.'
)
ON CONFLICT (slug) DO UPDATE SET
  display_name        = EXCLUDED.display_name,
  tier                = EXCLUDED.tier,
  monthly_price_usd   = EXCLUDED.monthly_price_usd,
  mobile_app_enabled  = EXCLUDED.mobile_app_enabled,
  status              = EXCLUDED.status;

-- Revere Chamber (white-label channel partner — placeholder until contract signs)
INSERT INTO public.tenants (slug, display_name, tier, monthly_price_usd, mobile_app_enabled, white_label, status, notes)
VALUES (
  'revere-chamber',
  'Revere Chamber of Commerce',
  'pro',
  1497.00,
  true,
  true,
  'pending_onboard',
  'White-label channel partner. Branding overrides in tenant_config row. Demo Friday 2026-04-18.'
)
ON CONFLICT (slug) DO UPDATE SET
  display_name        = EXCLUDED.display_name,
  tier                = EXCLUDED.tier,
  white_label         = EXCLUDED.white_label,
  status              = EXCLUDED.status;

-- Seed tenant_config rows (default brand + agent aliases — only override if needed)
INSERT INTO public.tenant_config (tenant_id, brand_name, brand_tagline)
SELECT id, 'AMG', 'AI Marketing Genius — Done-with-you marketing systems.'
FROM public.tenants WHERE slug = 'amg-internal'
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO public.tenant_config (tenant_id, brand_name, brand_tagline)
SELECT id, 'Levar Marketing', 'Sold-by-data luxury real estate marketing.'
FROM public.tenants WHERE slug = 'levar'
ON CONFLICT (tenant_id) DO NOTHING;

-- Revere Chamber: white-label branding overrides (placeholder colors until Solon picks)
INSERT INTO public.tenant_config (tenant_id, brand_name, brand_tagline, theme, agent_aliases)
SELECT
  id,
  'Revere Chamber Marketing',
  'AI marketing built for Revere businesses.',
  jsonb_build_object(
    'primary',   '#0a2d5e',  -- Revere navy (placeholder)
    'accent',    '#d4a627',  -- Revere gold (placeholder)
    'bg',        '#ffffff',  -- light theme for chamber
    'text',      '#0a2d5e',
    'font_body', 'Inter, sans-serif',
    'font_head', 'Inter, sans-serif'
  ),
  jsonb_build_object(
    'alex',   'Revere Account Manager',
    'maya',   'Revere Content Strategist',
    'jordan', 'Revere Reputation Coach',
    'sam',    'Revere SEO Specialist',
    'riley',  'Revere Strategic Advisor',
    'nadia',  'Revere Onboarding Lead',
    'lumina', 'Revere Conversion Expert'
  )
FROM public.tenants WHERE slug = 'revere-chamber'
ON CONFLICT (tenant_id) DO UPDATE SET
  brand_name      = EXCLUDED.brand_name,
  brand_tagline   = EXCLUDED.brand_tagline,
  theme           = EXCLUDED.theme,
  agent_aliases   = EXCLUDED.agent_aliases;


COMMIT;

-- ---------------------------------------------------------------------------
-- POST-APPLY VERIFICATION (run separately after COMMIT to confirm)
-- ---------------------------------------------------------------------------
-- SELECT slug, display_name, tier, mobile_app_enabled, white_label, status FROM public.tenants;
-- SELECT t.slug, c.brand_name, c.theme->>'primary' AS primary_color, c.agent_aliases->>'alex' AS alex_alias
--   FROM public.tenant_config c JOIN public.tenants t ON t.id = c.tenant_id;
