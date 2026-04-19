-- Commit #4 of Pillar 1 CRM Loop — lead intake (5 sources, Kleisthenes).
--
-- crm_lead_intake table captures raw lead rows from 5 canonical sources:
--   inbound_form | chatbot | voicebot | outbound_reply | linkedin
-- Tenant-scoped. Deduplicates by (tenant_id, source, contact_email).
-- Auto-schedules Nadia nurture entry on insert via trigger.
--
-- Named distinctly from legacy `public.crm_leads` (contact_id/stage/
-- intent_score model, 0 rows, predates Kleisthenes multi-tenant work).
-- The two can coexist — intake is the raw funnel, legacy crm_leads is
-- the relational CRM. Future commit may merge them; for now, separation
-- avoids data-loss risk on the un-used legacy table.

BEGIN;

CREATE TABLE IF NOT EXISTS public.crm_lead_intake (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                 UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    source                    TEXT NOT NULL,
    source_metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    contact_name              TEXT,
    contact_email             TEXT,
    contact_phone             TEXT,
    contact_company           TEXT,
    raw_payload               JSONB NOT NULL DEFAULT '{}'::jsonb,
    status                    TEXT NOT NULL DEFAULT 'new',
    assigned_agent            TEXT,
    nadia_entry_scheduled_at  TIMESTAMPTZ,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT crm_lead_intake_source_check CHECK (
        source IN ('inbound_form','chatbot','voicebot','outbound_reply','linkedin')
    ),
    CONSTRAINT crm_lead_intake_status_check CHECK (
        status IN ('new','qualified','disqualified','contacted','converted')
    ),
    CONSTRAINT crm_lead_intake_assigned_agent_check CHECK (
        assigned_agent IS NULL OR assigned_agent IN
            ('maya','nadia','alex','jordan','sam','riley','lumina')
    )
);

-- Dedup constraint: one lead per (tenant, source, email) when email is present.
-- NULL emails are allowed to multi-row (e.g., voicebot calls before email capture).
CREATE UNIQUE INDEX IF NOT EXISTS crm_lead_intake_tenant_source_email_uq
    ON public.crm_lead_intake(tenant_id, source, contact_email)
    WHERE contact_email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_crm_lead_intake_tenant_created
    ON public.crm_lead_intake(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_crm_lead_intake_tenant_status
    ON public.crm_lead_intake(tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_crm_lead_intake_tenant_source
    ON public.crm_lead_intake(tenant_id, source);

CREATE INDEX IF NOT EXISTS idx_crm_lead_intake_nadia_pending
    ON public.crm_lead_intake(tenant_id, nadia_entry_scheduled_at)
    WHERE nadia_entry_scheduled_at IS NOT NULL AND status = 'new';

COMMENT ON TABLE public.crm_lead_intake IS
    'Lead intake funnel. 5 canonical sources map to Nadia nurture entry on insert.';

-- Touch updated_at on mutation.
CREATE OR REPLACE FUNCTION public.crm_lead_intake_touch()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS crm_lead_intake_touch_tr ON public.crm_lead_intake;
CREATE TRIGGER crm_lead_intake_touch_tr
    BEFORE UPDATE ON public.crm_lead_intake
    FOR EACH ROW
    EXECUTE FUNCTION public.crm_lead_intake_touch();

-- Auto-schedule Nadia entry on insert (5 min from now) if not explicitly set.
-- lib/crm_lead_intake.py is the canonical insert path; trigger is defensive
-- belt-and-suspenders for direct SQL insertions.
CREATE OR REPLACE FUNCTION public.crm_lead_intake_auto_schedule_nadia()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.nadia_entry_scheduled_at IS NULL AND NEW.status = 'new' THEN
        NEW.nadia_entry_scheduled_at := now() + INTERVAL '5 minutes';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS crm_lead_intake_nadia_schedule_tr ON public.crm_lead_intake;
CREATE TRIGGER crm_lead_intake_nadia_schedule_tr
    BEFORE INSERT ON public.crm_lead_intake
    FOR EACH ROW
    EXECUTE FUNCTION public.crm_lead_intake_auto_schedule_nadia();

-- RLS — tenant-scoped reads/writes for authenticated; service_role bypass.
ALTER TABLE public.crm_lead_intake ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS sr_crm_lead_intake_all ON public.crm_lead_intake;
CREATE POLICY sr_crm_lead_intake_all ON public.crm_lead_intake
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

DROP POLICY IF EXISTS op_crm_lead_intake_tenant_read ON public.crm_lead_intake;
CREATE POLICY op_crm_lead_intake_tenant_read ON public.crm_lead_intake
    FOR SELECT
    TO authenticated
    USING (tenant_id::text = current_setting('amg.tenant_id', TRUE));

DROP POLICY IF EXISTS op_crm_lead_intake_tenant_insert ON public.crm_lead_intake;
CREATE POLICY op_crm_lead_intake_tenant_insert ON public.crm_lead_intake
    FOR INSERT
    TO authenticated
    WITH CHECK (tenant_id::text = current_setting('amg.tenant_id', TRUE));

DROP POLICY IF EXISTS op_crm_lead_intake_tenant_update ON public.crm_lead_intake;
CREATE POLICY op_crm_lead_intake_tenant_update ON public.crm_lead_intake
    FOR UPDATE
    TO authenticated
    USING (tenant_id::text = current_setting('amg.tenant_id', TRUE))
    WITH CHECK (tenant_id::text = current_setting('amg.tenant_id', TRUE));

COMMIT;

-- Post-apply verification:
--   SELECT COUNT(*) FROM public.crm_lead_intake;  -- expect 0 (no seed)
--   SELECT COUNT(*) FROM pg_policies WHERE tablename='crm_lead_intake';  -- expect 4
