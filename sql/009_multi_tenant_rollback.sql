-- Rollback for sql/009_multi_tenant.sql. Applied only if we need to revert
-- multi-tenant generalization. Does NOT drop the tenants table if it already
-- contains real client data — abort manually if production tenants exist.

BEGIN;

-- Drop policies first (they reference columns we're about to drop).
DROP POLICY IF EXISTS op_push_tenant_read ON public.push_subscriptions;
DROP POLICY IF EXISTS op_refresh_tenant_read ON public.refresh_tokens;
DROP POLICY IF EXISTS op_webauthn_tenant_read ON public.webauthn_credentials;
DROP POLICY IF EXISTS op_tenants_self_read ON public.tenants;
DROP POLICY IF EXISTS sr_tenants_all ON public.tenants;

-- Drop indexes added in sql/009.
DROP INDEX IF EXISTS idx_push_tenant;
DROP INDEX IF EXISTS idx_refresh_tenant;
DROP INDEX IF EXISTS idx_refresh_tenant_family;
DROP INDEX IF EXISTS idx_webauthn_tenant;
DROP INDEX IF EXISTS idx_operators_tenant;
DROP INDEX IF EXISTS idx_tenants_slug;
DROP INDEX IF EXISTS idx_tenants_subdomain;
DROP INDEX IF EXISTS idx_tenants_status;

-- Drop FK constraints before the column drops.
ALTER TABLE public.push_subscriptions DROP CONSTRAINT IF EXISTS push_tenant_fk;
ALTER TABLE public.refresh_tokens     DROP CONSTRAINT IF EXISTS refresh_tenant_fk;
ALTER TABLE public.webauthn_credentials DROP CONSTRAINT IF EXISTS webauthn_tenant_fk;

-- Drop tenant_id columns from scoped tables.
ALTER TABLE public.push_subscriptions    DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE public.refresh_tokens        DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE public.webauthn_credentials  DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE public.operators             DROP COLUMN IF EXISTS tenant_id;

-- Drop helper function.
DROP FUNCTION IF EXISTS public.tenant_by_identifier(TEXT);

-- Drop the tenants table LAST. ABORT if it has >1 row (indicates real data).
DO $$
DECLARE
    tenant_count INT;
BEGIN
    SELECT COUNT(*) INTO tenant_count FROM public.tenants;
    IF tenant_count > 1 THEN
        RAISE EXCEPTION 'Aborting rollback: public.tenants has % rows (real client data). Drop manually if intentional.', tenant_count;
    END IF;
END $$;

DROP TABLE IF EXISTS public.tenants CASCADE;

COMMIT;
