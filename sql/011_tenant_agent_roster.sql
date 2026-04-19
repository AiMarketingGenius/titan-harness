-- Commit #3 of Pillar 1 CRM Loop — per-tenant agent roster (Kleisthenes).
--
-- Each tenant gets an instance of the 7-agent AMG roster (Maya/Nadia/Alex/
-- Jordan/Sam/Riley/Lumina). Row per tenant × agent. Config JSONB per row
-- lets a tenant customize voice ID / persona / prompt overrides without
-- duplicating the agent definition itself.
--
-- RLS: service_role bypass + authenticated read scoped to amg.tenant_id GUC
-- (set by lib/tenant_context.py tenant_tx on every authenticated request).
--
-- Idempotency pattern: CREATE TABLE IF NOT EXISTS + DO $$ IF NOT EXISTS(...)
-- blocks on ADD CONSTRAINT per P10 lesson from ct-0419-sql-reapply — 009
-- lacked these guards and failed on second apply.

BEGIN;

-- ─────────────────────────────────────────────────────────────────
-- Table: tenant_agent_roster
-- ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.tenant_agent_roster (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    agent_key       TEXT NOT NULL,
    role_title      TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    config          JSONB NOT NULL DEFAULT '{}'::jsonb,
    activated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT tenant_agent_roster_agent_key_check CHECK (
        agent_key IN ('maya','nadia','alex','jordan','sam','riley','lumina')
    )
);

-- One row per (tenant, agent). Re-seeding is a no-op.
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'tenant_agent_roster_tenant_agent_uq'
    ) THEN
        ALTER TABLE public.tenant_agent_roster
            ADD CONSTRAINT tenant_agent_roster_tenant_agent_uq
            UNIQUE (tenant_id, agent_key);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_tenant_agent_roster_tenant
    ON public.tenant_agent_roster(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_agent_roster_enabled
    ON public.tenant_agent_roster(tenant_id, enabled) WHERE enabled = TRUE;

COMMENT ON TABLE public.tenant_agent_roster IS
    'Per-tenant 7-agent AMG roster (Kleisthenes civic-tenant model). Seeded on provision.';

-- ─────────────────────────────────────────────────────────────────
-- Seed the 7 default agents for amg-internal + revere-chamber-demo.
-- Idempotent: ON CONFLICT (tenant_id, agent_key) DO NOTHING.
-- ─────────────────────────────────────────────────────────────────

WITH seed_agents(agent_key, role_title) AS (
    VALUES
        ('maya',   'Content Strategist'),
        ('nadia',  'Nurture & Follow-up'),
        ('alex',   'Voice + Chat'),
        ('jordan', 'SEO & Rankings'),
        ('sam',    'Social Presence'),
        ('riley',  'Reputation & Reviews'),
        ('lumina', 'Visual & Brand')
),
target_tenants AS (
    SELECT id FROM public.tenants
    WHERE slug IN ('amg-internal', 'revere-chamber-demo')
)
INSERT INTO public.tenant_agent_roster (tenant_id, agent_key, role_title)
SELECT t.id, s.agent_key, s.role_title
  FROM target_tenants t
  CROSS JOIN seed_agents s
ON CONFLICT (tenant_id, agent_key) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────
-- RLS — service_role bypass + authenticated tenant-scoped read.
-- ─────────────────────────────────────────────────────────────────

ALTER TABLE public.tenant_agent_roster ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS sr_tenant_agent_roster_all ON public.tenant_agent_roster;
CREATE POLICY sr_tenant_agent_roster_all ON public.tenant_agent_roster
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

DROP POLICY IF EXISTS op_tenant_agent_roster_read ON public.tenant_agent_roster;
CREATE POLICY op_tenant_agent_roster_read ON public.tenant_agent_roster
    FOR SELECT
    TO authenticated
    USING (tenant_id::text = current_setting('amg.tenant_id', TRUE));

-- ─────────────────────────────────────────────────────────────────
-- Trigger: auto-update updated_at on row mutation.
-- ─────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.tenant_agent_roster_touch()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tenant_agent_roster_touch_tr ON public.tenant_agent_roster;
CREATE TRIGGER tenant_agent_roster_touch_tr
    BEFORE UPDATE ON public.tenant_agent_roster
    FOR EACH ROW
    EXECUTE FUNCTION public.tenant_agent_roster_touch();

COMMIT;

-- Post-apply verification:
--   SELECT tenant_id, COUNT(*) FROM public.tenant_agent_roster GROUP BY tenant_id;
--     -- expect 2 rows × 7 agents each (amg-internal + revere-chamber-demo)
--   SELECT COUNT(*) FROM pg_policies WHERE tablename = 'tenant_agent_roster';  -- expect 2
