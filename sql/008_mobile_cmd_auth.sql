-- Mobile Command v2 auth/security schema migration
-- Step 6.2 per plans/PLAN_MOBILE_COMMAND_V2_AUTH_ARCHITECTURE.md (commit 26044ac)
-- Read by:  lib/mobile_cmd_auth.py (Step 6.1 module, commit 75e9ac6)
-- Rollback: sql/008_mobile_cmd_auth_rollback.sql
--
-- Three tables:
--   1. webauthn_credentials — per-operator platform-authenticator public keys
--   2. refresh_tokens       — JWT refresh token pair rotation + reuse detection
--   3. push_subscriptions   — Web Push VAPID subscriptions + 410-expiry revocation
--
-- Assumes: public.operators table already exists (Solon = operator 1).
-- If not, create a minimal operators table first; this migration does NOT touch it.

BEGIN;

-- ─────────────────────────────────────────────────────────────────
-- Table 1: webauthn_credentials
-- One row per registered platform-authenticator (FaceID/TouchID credential).
-- An operator can have multiple credentials (e.g., iPhone + iPad home-screen
-- installs). Sign_count is rotated on every authentication per WebAuthn L3 spec.
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.webauthn_credentials (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id    UUID NOT NULL REFERENCES public.operators(id) ON DELETE CASCADE,
    credential_id  BYTEA NOT NULL UNIQUE,
    public_key     BYTEA NOT NULL,
    sign_count     BIGINT NOT NULL DEFAULT 0 CHECK (sign_count >= 0),
    transports     TEXT[] NOT NULL DEFAULT ARRAY['internal']::TEXT[],
    user_agent     TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at   TIMESTAMPTZ,
    revoked_at     TIMESTAMPTZ,
    revoked_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_webauthn_operator_active
    ON public.webauthn_credentials(operator_id)
    WHERE revoked_at IS NULL;

COMMENT ON TABLE public.webauthn_credentials IS
    'WebAuthn platform-authenticator credentials per operator. One row per registered device. sign_count rotated on every authenticate_verify.';

-- ─────────────────────────────────────────────────────────────────
-- Table 2: refresh_tokens
-- Family-scoped refresh token rotation. Each login creates a new family_id.
-- Each rotation creates a new row in the same family. If any row is presented
-- twice (used_at IS NOT NULL), the entire family is revoked (reuse detection).
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.refresh_tokens (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id  UUID NOT NULL REFERENCES public.operators(id) ON DELETE CASCADE,
    token_hash   BYTEA NOT NULL UNIQUE,
    family_id    UUID NOT NULL,
    issued_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL,
    used_at      TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ,
    revoke_reason TEXT,
    replaced_by  UUID REFERENCES public.refresh_tokens(id) ON DELETE SET NULL
);

-- Fast lookup for active tokens per operator (used on every /api/auth/refresh call).
CREATE INDEX IF NOT EXISTS idx_refresh_operator_active
    ON public.refresh_tokens(operator_id, family_id)
    WHERE revoked_at IS NULL AND used_at IS NULL;

-- Fast hash lookup for rotate path.
CREATE INDEX IF NOT EXISTS idx_refresh_token_hash
    ON public.refresh_tokens(token_hash);

-- Reuse-detection scan + family-revoke scan.
CREATE INDEX IF NOT EXISTS idx_refresh_family
    ON public.refresh_tokens(family_id);

COMMENT ON TABLE public.refresh_tokens IS
    'JWT refresh token rotation with family-scoped reuse detection. Presenting a used token revokes entire family + forces WebAuthn re-auth.';

-- ─────────────────────────────────────────────────────────────────
-- Table 3: push_subscriptions
-- Web Push VAPID subscriptions per operator. iOS 30-day expiry handled by
-- marking revoked_at + revocation_reason='expired_410' when the push service
-- returns 404/410. PWA must re-subscribe on next launch.
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.push_subscriptions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id       UUID NOT NULL REFERENCES public.operators(id) ON DELETE CASCADE,
    endpoint          TEXT NOT NULL UNIQUE,
    p256dh_key        TEXT NOT NULL,
    auth_key          TEXT NOT NULL,
    user_agent        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_success_at   TIMESTAMPTZ,
    last_failure_at   TIMESTAMPTZ,
    failure_count     INTEGER NOT NULL DEFAULT 0,
    revoked_at        TIMESTAMPTZ,
    revocation_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_push_operator_active
    ON public.push_subscriptions(operator_id)
    WHERE revoked_at IS NULL;

COMMENT ON TABLE public.push_subscriptions IS
    'Web Push VAPID subscriptions. One row per PWA install. Auto-revoked on iOS 30-day 410 expiry; PWA re-subscribes on next launch.';

-- ─────────────────────────────────────────────────────────────────
-- Row-Level Security policies
-- Single-operator scope for now. When multi-tenant generalization (Step 7)
-- lands, policies expand to match operator_id = current_setting('amg.operator_id')::uuid.
-- ─────────────────────────────────────────────────────────────────
ALTER TABLE public.webauthn_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.refresh_tokens      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.push_subscriptions  ENABLE ROW LEVEL SECURITY;

-- Service-role bypass (atlas_api runs as service role — full CRUD needed).
-- Postgres + Supabase automatically grant the service_role key full access;
-- we add explicit policies for clarity + audit-trail readability.

DROP POLICY IF EXISTS sr_webauthn_all ON public.webauthn_credentials;
CREATE POLICY sr_webauthn_all ON public.webauthn_credentials
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

DROP POLICY IF EXISTS sr_refresh_all ON public.refresh_tokens;
CREATE POLICY sr_refresh_all ON public.refresh_tokens
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

DROP POLICY IF EXISTS sr_push_all ON public.push_subscriptions;
CREATE POLICY sr_push_all ON public.push_subscriptions
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

-- Operator self-scoped policies (used when atlas_api eventually propagates a
-- JWT-derived operator_id into a session-GUC for read-only self-queries;
-- currently all atlas_api reads use service_role, so these are forward-compat).

DROP POLICY IF EXISTS op_webauthn_self_read ON public.webauthn_credentials;
CREATE POLICY op_webauthn_self_read ON public.webauthn_credentials
    FOR SELECT
    TO authenticated
    USING (operator_id::text = current_setting('amg.operator_id', TRUE));

DROP POLICY IF EXISTS op_refresh_self_read ON public.refresh_tokens;
CREATE POLICY op_refresh_self_read ON public.refresh_tokens
    FOR SELECT
    TO authenticated
    USING (operator_id::text = current_setting('amg.operator_id', TRUE));

DROP POLICY IF EXISTS op_push_self_read ON public.push_subscriptions;
CREATE POLICY op_push_self_read ON public.push_subscriptions
    FOR SELECT
    TO authenticated
    USING (operator_id::text = current_setting('amg.operator_id', TRUE));

-- ─────────────────────────────────────────────────────────────────
-- Helper function: cascade-revoke a refresh token family.
-- Called by lib/mobile_cmd_auth.py::rotate_refresh_token on reuse detection
-- OR by revoke_chain on operator-initiated logout. Atomic + returns count.
-- ─────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.revoke_refresh_family(
    p_family_id UUID,
    p_reason TEXT
) RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    affected INTEGER;
BEGIN
    UPDATE public.refresh_tokens
       SET revoked_at = now(),
           revoke_reason = p_reason
     WHERE family_id = p_family_id
       AND revoked_at IS NULL;
    GET DIAGNOSTICS affected = ROW_COUNT;
    RETURN affected;
END;
$$;

COMMENT ON FUNCTION public.revoke_refresh_family IS
    'Cascade-revoke all active refresh tokens in a family. Returns rows affected.';

COMMIT;

-- ─────────────────────────────────────────────────────────────────
-- Verification queries (run after apply to confirm clean migration):
-- ─────────────────────────────────────────────────────────────────
-- SELECT count(*) FROM public.webauthn_credentials;  -- expect 0
-- SELECT count(*) FROM public.refresh_tokens;        -- expect 0
-- SELECT count(*) FROM public.push_subscriptions;    -- expect 0
-- SELECT policy_name FROM pg_policies WHERE tablename IN
--     ('webauthn_credentials','refresh_tokens','push_subscriptions');
--   -- expect 6 rows (2 policies × 3 tables)
-- SELECT proname FROM pg_proc WHERE proname = 'revoke_refresh_family';
--   -- expect 1 row
