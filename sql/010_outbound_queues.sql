-- Step 7.4 — Outbound Email + Voice AI queue tables.
-- Enqueued from atlas_api POST /api/outbound/{email,voice}; processed by
-- separate worker daemons (to ship in follow-up session). Per-tenant scoped
-- via tenant_id FK so multi-tenant isolation from sql/009 extends here.
--
-- Rollback: sql/010_outbound_queues_rollback.sql

BEGIN;

-- ─── Email outbound queue ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.outbound_email_queue (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    operator_id     UUID NOT NULL REFERENCES public.operators(id) ON DELETE SET NULL,
    from_alias      TEXT NOT NULL,
    to_recipients   TEXT[] NOT NULL,
    cc_recipients   TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    bcc_recipients  TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    subject         TEXT NOT NULL,
    body_plaintext  TEXT NOT NULL,
    body_html       TEXT,
    status          TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued', 'sending', 'sent', 'failed', 'canceled')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    enqueued_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    scheduled_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at         TIMESTAMPTZ,
    provider_message_id TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_outbound_email_queue_status
    ON public.outbound_email_queue(status, scheduled_at)
    WHERE status IN ('queued', 'sending');

CREATE INDEX IF NOT EXISTS idx_outbound_email_tenant
    ON public.outbound_email_queue(tenant_id, enqueued_at DESC);

COMMENT ON TABLE public.outbound_email_queue IS
    'Email outbound queue. Worker polls status=queued rows ordered by scheduled_at, transitions to sending/sent/failed. Provider integration (SMTP app-password or Gmail API) lives in the worker, not here.';

-- ─── Voice AI outbound queue ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.outbound_voice_queue (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    operator_id     UUID NOT NULL REFERENCES public.operators(id) ON DELETE SET NULL,
    to_phone        TEXT NOT NULL,  -- E.164 format
    from_phone      TEXT,            -- E.164; tenant-configured outbound caller ID
    voice           TEXT NOT NULL DEFAULT 'alex',
    script_template TEXT NOT NULL,
    script_vars     JSONB NOT NULL DEFAULT '{}'::jsonb,  -- merged into template at dial time
    max_duration_s  INTEGER NOT NULL DEFAULT 300,
    status          TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued', 'dialing', 'in_call', 'completed', 'failed', 'canceled', 'no_answer')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    enqueued_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    scheduled_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    dialed_at       TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    provider_call_id TEXT,  -- Telnyx / whichever provider returns
    transcript      TEXT,   -- post-call STT
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_outbound_voice_queue_status
    ON public.outbound_voice_queue(status, scheduled_at)
    WHERE status IN ('queued', 'dialing', 'in_call');

CREATE INDEX IF NOT EXISTS idx_outbound_voice_tenant
    ON public.outbound_voice_queue(tenant_id, enqueued_at DESC);

COMMENT ON TABLE public.outbound_voice_queue IS
    'Voice AI outbound queue. Worker polls queued rows, dials via Telnyx (or whichever provider), runs script through LLM chat loop + ElevenLabs TTS + Deepgram/Whisper STT, transitions through dialing -> in_call -> completed/failed/no_answer.';

-- ─── RLS (tenant-scoped per sql/009 pattern) ─────────────────────
ALTER TABLE public.outbound_email_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.outbound_voice_queue ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS sr_outbound_email_all ON public.outbound_email_queue;
CREATE POLICY sr_outbound_email_all ON public.outbound_email_queue
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

DROP POLICY IF EXISTS sr_outbound_voice_all ON public.outbound_voice_queue;
CREATE POLICY sr_outbound_voice_all ON public.outbound_voice_queue
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

DROP POLICY IF EXISTS op_outbound_email_tenant_read ON public.outbound_email_queue;
CREATE POLICY op_outbound_email_tenant_read ON public.outbound_email_queue
    FOR SELECT TO authenticated
    USING (tenant_id::text = current_setting('amg.tenant_id', TRUE));

DROP POLICY IF EXISTS op_outbound_voice_tenant_read ON public.outbound_voice_queue;
CREATE POLICY op_outbound_voice_tenant_read ON public.outbound_voice_queue
    FOR SELECT TO authenticated
    USING (tenant_id::text = current_setting('amg.tenant_id', TRUE));

COMMIT;

-- Verify:
-- SELECT COUNT(*) FROM public.outbound_email_queue;  -- expect 0 initially
-- SELECT COUNT(*) FROM public.outbound_voice_queue;  -- expect 0 initially
-- SELECT policyname FROM pg_policies WHERE tablename IN ('outbound_email_queue','outbound_voice_queue');
--   -- expect 4 rows (2 policies × 2 tables)
