-- Multi-tenant generalization — Step 7.1 per CT-0417-35 + MCP sprint state.
-- Extends the single-operator Mobile Command v2 auth stack (sql/008) into a
-- per-tenant surface. Each tenant (Chamber / agency client) gets its own
-- operator roster, Postgres-RLS-isolated data, and per-tenant branding.
--
-- Pattern — Sonar Pro audit 2026-04-18 §3a recommends:
--   SET LOCAL amg.tenant_id = <uuid>::text
-- at the start of every transaction, with RLS policies keyed off
--   current_setting('amg.tenant_id', TRUE)
-- atlas_api middleware will set this from the JWT's tenant_id claim on every
-- request before hitting any tenant-scoped table.
--
-- Rollback: sql/009_multi_tenant_rollback.sql

BEGIN;

-- ─────────────────────────────────────────────────────────────────
-- Table 1: tenants
-- One row per Chamber / agency client. Solon's own AMG ops gets a
-- self-referential "amg-internal" tenant for back-compat with Step 6.x
-- single-operator code paths.
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    subdomain       TEXT UNIQUE,  -- e.g. "revere-chamber" for revere-chamber.aimarketinggenius.io
    brand_config    JSONB NOT NULL DEFAULT '{}'::jsonb,  -- logo, palette, typography tokens
    webauthn_rp_id  TEXT,         -- per-tenant WebAuthn RP ID (subdomain match)
    webauthn_rp_name TEXT,
    vapid_public_key TEXT,        -- per-tenant VAPID (optional; shared fallback from env)
    vapid_subject    TEXT,
    plan_tier        TEXT NOT NULL DEFAULT 'chamber-standard',
    status           TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'churned')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    paused_at        TIMESTAMPTZ,
    churned_at       TIMESTAMPTZ
);

-- Fast lookup by slug + subdomain (hot path on every request — middleware sets
-- amg.tenant_id from one of these).
CREATE INDEX IF NOT EXISTS idx_tenants_slug       ON public.tenants(slug);
CREATE INDEX IF NOT EXISTS idx_tenants_subdomain  ON public.tenants(subdomain) WHERE subdomain IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tenants_status     ON public.tenants(status);

COMMENT ON TABLE public.tenants IS
    'Multi-tenant root. Each Chamber / agency client gets one row. Solon amg-internal tenant is seeded for back-compat with Step 6.x single-operator paths.';

-- Seed the amg-internal tenant so existing sql/008 data (operators, credentials,
-- refresh_tokens, push_subscriptions) can be back-filled with a known tenant_id
-- without invalidating Solon's active sessions.
INSERT INTO public.tenants (id, slug, name, subdomain, webauthn_rp_id, webauthn_rp_name, plan_tier)
VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    'amg-internal',
    'AI Marketing Genius (Internal)',
    'operator',  -- operator.aimarketinggenius.io
    'operator.aimarketinggenius.io',
    'AMG Mobile Command',
    'internal-solo'
) ON CONFLICT (id) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────
-- Add tenant_id to existing Step 6.2 tables.
-- Default to amg-internal so existing rows don't become orphaned.
-- ─────────────────────────────────────────────────────────────────

-- operators: assumed to exist pre-sql/008. Add tenant_id if missing.
ALTER TABLE public.operators
    ADD COLUMN IF NOT EXISTS tenant_id UUID NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001'::uuid
        REFERENCES public.tenants(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_operators_tenant ON public.operators(tenant_id);

-- webauthn_credentials: add tenant_id, back-filling from operator lookup.
ALTER TABLE public.webauthn_credentials
    ADD COLUMN IF NOT EXISTS tenant_id UUID;

UPDATE public.webauthn_credentials wc
   SET tenant_id = o.tenant_id
  FROM public.operators o
 WHERE wc.operator_id = o.id
   AND wc.tenant_id IS NULL;

ALTER TABLE public.webauthn_credentials
    ALTER COLUMN tenant_id SET NOT NULL,
    ADD CONSTRAINT webauthn_tenant_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_webauthn_tenant ON public.webauthn_credentials(tenant_id);

-- refresh_tokens: add tenant_id + composite UNIQUE(family_id, tenant_id)
-- per Sonar Pro §3c (prevents cross-tenant family_id replay).
ALTER TABLE public.refresh_tokens
    ADD COLUMN IF NOT EXISTS tenant_id UUID;

UPDATE public.refresh_tokens rt
   SET tenant_id = o.tenant_id
  FROM public.operators o
 WHERE rt.operator_id = o.id
   AND rt.tenant_id IS NULL;

ALTER TABLE public.refresh_tokens
    ALTER COLUMN tenant_id SET NOT NULL,
    ADD CONSTRAINT refresh_tenant_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_refresh_tenant ON public.refresh_tokens(tenant_id);

-- Note on UNIQUE(family_id, tenant_id): the sql/008 schema does NOT put UNIQUE
-- on family_id alone (multiple rows per family across rotations), so the
-- composite unique is not strictly required to prevent collisions. But adding
-- a covering index on (tenant_id, family_id) speeds per-tenant family scans
-- during revoke_family() calls.
CREATE INDEX IF NOT EXISTS idx_refresh_tenant_family
    ON public.refresh_tokens(tenant_id, family_id);

-- push_subscriptions: same pattern.
ALTER TABLE public.push_subscriptions
    ADD COLUMN IF NOT EXISTS tenant_id UUID;

UPDATE public.push_subscriptions ps
   SET tenant_id = o.tenant_id
  FROM public.operators o
 WHERE ps.operator_id = o.id
   AND ps.tenant_id IS NULL;

ALTER TABLE public.push_subscriptions
    ALTER COLUMN tenant_id SET NOT NULL,
    ADD CONSTRAINT push_tenant_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_push_tenant ON public.push_subscriptions(tenant_id);

-- ─────────────────────────────────────────────────────────────────
-- RLS policies — tenant isolation via current_setting('amg.tenant_id', TRUE).
-- atlas_api middleware sets this from JWT tenant_id claim on every request.
-- service_role bypass retained from sql/008 for backend admin paths.
-- ─────────────────────────────────────────────────────────────────

ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS sr_tenants_all ON public.tenants;
CREATE POLICY sr_tenants_all ON public.tenants
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

-- Authenticated users can only see their own tenant row (derived from JWT
-- tenant_id claim propagated to session GUC).
DROP POLICY IF EXISTS op_tenants_self_read ON public.tenants;
CREATE POLICY op_tenants_self_read ON public.tenants
    FOR SELECT
    TO authenticated
    USING (id::text = current_setting('amg.tenant_id', TRUE));

-- Tighten the existing Step 6.2 policies on webauthn / refresh / push to scope
-- by tenant_id in addition to operator_id. service_role policies from sql/008
-- remain permissive for admin paths; we add tenant-scoped policies for
-- authenticated reads.
DROP POLICY IF EXISTS op_webauthn_tenant_read ON public.webauthn_credentials;
CREATE POLICY op_webauthn_tenant_read ON public.webauthn_credentials
    FOR SELECT
    TO authenticated
    USING (
        tenant_id::text = current_setting('amg.tenant_id', TRUE)
        AND operator_id::text = current_setting('amg.operator_id', TRUE)
    );

DROP POLICY IF EXISTS op_refresh_tenant_read ON public.refresh_tokens;
CREATE POLICY op_refresh_tenant_read ON public.refresh_tokens
    FOR SELECT
    TO authenticated
    USING (
        tenant_id::text = current_setting('amg.tenant_id', TRUE)
        AND operator_id::text = current_setting('amg.operator_id', TRUE)
    );

DROP POLICY IF EXISTS op_push_tenant_read ON public.push_subscriptions;
CREATE POLICY op_push_tenant_read ON public.push_subscriptions
    FOR SELECT
    TO authenticated
    USING (
        tenant_id::text = current_setting('amg.tenant_id', TRUE)
        AND operator_id::text = current_setting('amg.operator_id', TRUE)
    );

-- ─────────────────────────────────────────────────────────────────
-- Helper: get_tenant_by_identifier(slug_or_subdomain TEXT) -> tenants row.
-- Middleware uses this to resolve the tenant from request context (slug on
-- path param or subdomain on Host header) and set amg.tenant_id before
-- issuing any scoped query.
-- ─────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.tenant_by_identifier(identifier TEXT)
RETURNS SETOF public.tenants
LANGUAGE sql
SECURITY DEFINER
AS $$
    SELECT * FROM public.tenants
     WHERE status = 'active'
       AND (slug = identifier OR subdomain = identifier)
     LIMIT 1;
$$;

COMMENT ON FUNCTION public.tenant_by_identifier IS
    'Resolve tenant by slug or subdomain. SECURITY DEFINER to allow middleware context-setting before RLS gates query access.';

COMMIT;

-- ─────────────────────────────────────────────────────────────────
-- Verification queries (run after apply):
-- ─────────────────────────────────────────────────────────────────
-- SELECT id, slug, subdomain, status FROM public.tenants;
--   -- expect at least amg-internal seed row
-- SELECT COUNT(*) FROM public.operators WHERE tenant_id IS NULL;  -- expect 0
-- SELECT COUNT(*) FROM public.refresh_tokens WHERE tenant_id IS NULL;  -- expect 0
-- SELECT COUNT(*) FROM public.webauthn_credentials WHERE tenant_id IS NULL;  -- expect 0
-- SELECT COUNT(*) FROM public.push_subscriptions WHERE tenant_id IS NULL;  -- expect 0
-- SELECT proname FROM pg_proc WHERE proname = 'tenant_by_identifier';  -- expect 1 row
-- SELECT policyname FROM pg_policies WHERE tablename = 'tenants';  -- expect 2 (sr + op_self)
