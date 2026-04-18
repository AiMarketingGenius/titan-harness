-- Rollback for sql/008_mobile_cmd_auth.sql
-- Run ONLY if the Mobile Command v2 auth stack is being reverted.
-- Drops all three tables + the helper function + policies (implicit via CASCADE).
-- Safe order: function first, then tables (FK cleanup handles refresh_tokens.replaced_by).

BEGIN;

DROP FUNCTION IF EXISTS public.revoke_refresh_family(UUID, TEXT);

DROP TABLE IF EXISTS public.push_subscriptions    CASCADE;
DROP TABLE IF EXISTS public.refresh_tokens        CASCADE;
DROP TABLE IF EXISTS public.webauthn_credentials  CASCADE;

COMMIT;

-- Post-rollback verification:
-- SELECT tablename FROM pg_tables WHERE tablename IN
--     ('webauthn_credentials','refresh_tokens','push_subscriptions');
--   -- expect 0 rows
-- SELECT proname FROM pg_proc WHERE proname = 'revoke_refresh_family';
--   -- expect 0 rows
