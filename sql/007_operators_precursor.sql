-- Operators table precursor — required by sql/008_mobile_cmd_auth.sql.
-- Minimal schema: one row per operator, keyed on auth.users(id).
-- Seeds the earliest-created auth.users row as operator 1 (Solon).
-- Idempotent. Rollback: DROP TABLE public.operators CASCADE;

BEGIN;

CREATE TABLE IF NOT EXISTS public.operators (
    id             UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email          TEXT,
    display_name   TEXT,
    role           TEXT NOT NULL DEFAULT 'operator' CHECK (role IN ('admin', 'operator', 'viewer')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_operators_email ON public.operators(email);

COMMENT ON TABLE public.operators IS
    'Operator roster for AMG / Solon OS internal ops. Keyed on auth.users(id). sql/008+ mobile command auth tables FK to this.';

ALTER TABLE public.operators ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS sr_operators_all ON public.operators;
CREATE POLICY sr_operators_all ON public.operators
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

DROP POLICY IF EXISTS op_operators_self_read ON public.operators;
CREATE POLICY op_operators_self_read ON public.operators
    FOR SELECT TO authenticated
    USING (id = auth.uid());

-- Seed Solon as operator 1 — earliest-created auth.users row gets admin role.
INSERT INTO public.operators (id, email, display_name, role)
SELECT id, email, COALESCE(raw_user_meta_data->>'display_name', email), 'admin'
FROM auth.users
ORDER BY created_at ASC
LIMIT 1
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- Verify:
-- SELECT count(*) FROM public.operators;                 -- expect >= 1
-- SELECT id, email, role FROM public.operators LIMIT 5;  -- expect Solon as admin
