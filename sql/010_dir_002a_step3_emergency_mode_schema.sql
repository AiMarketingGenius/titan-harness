-- =============================================================================
-- DIR-2026-04-28-002a Step 3.1 + 3.2 — Emergency Mode schema + TTL cleanup
-- =============================================================================
-- Per v3 §DIR-002a Step 3.1 (op_emergency_signals + agent_config fast_poll
-- columns) and Step 3.2 (pg_cron daily TTL cleanup, 7-day retention).
-- Idempotent (IF NOT EXISTS / OR REPLACE / DO blocks).
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. op_emergency_signals — main signal queue
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS op_emergency_signals (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_type     TEXT NOT NULL CHECK (signal_type IN ('KILL', 'EDIT', 'PAUSE', 'RESUME')),
  target_agent    TEXT NOT NULL CHECK (target_agent IN ('titan', 'achilles', 'all')),
  target_task_id  TEXT,
  reason          TEXT NOT NULL,
  invoked_by      TEXT NOT NULL DEFAULT 'eom' CHECK (invoked_by IN ('eom', 'solon')),
  acknowledged_by TEXT[] NOT NULL DEFAULT '{}',
  status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'acknowledged', 'expired', 'cancelled')),
  expires_at      TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '10 minutes'),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  acknowledged_at TIMESTAMPTZ
);

-- Index for fast harness top-of-loop scan (created_at ASC ordering, see §3.6
-- concurrent-signal race handling).
CREATE INDEX IF NOT EXISTS idx_emergency_signals_active
  ON op_emergency_signals (status, target_agent, created_at)
  WHERE status = 'pending';

-- ---------------------------------------------------------------------------
-- 2. agent_config — fast_poll + fast_poll_until columns (Hercules correction #2
--    fallback path 2; emergency-signal heartbeat acceleration tertiary).
-- ---------------------------------------------------------------------------
ALTER TABLE agent_config
  ADD COLUMN IF NOT EXISTS fast_poll BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE agent_config
  ADD COLUMN IF NOT EXISTS fast_poll_until TIMESTAMPTZ;

-- ---------------------------------------------------------------------------
-- 3. TTL cleanup — pg_cron daily 04:00 UTC, 7-day retention on
--    expired/cancelled signals (Perplexity blocker #8 + v3 §3.2).
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM cron.job WHERE jobname = 'emergency_signals_cleanup'
  ) THEN
    PERFORM cron.unschedule('emergency_signals_cleanup');
  END IF;
END $$;

SELECT cron.schedule(
  'emergency_signals_cleanup',
  '0 4 * * *',
  $$
    DELETE FROM op_emergency_signals
    WHERE status IN ('expired', 'cancelled')
      AND COALESCE(acknowledged_at, expires_at) < NOW() - INTERVAL '7 days';
  $$
);

-- ---------------------------------------------------------------------------
-- 4. Auto-expire pending signals past expires_at on next scan (helper view +
--    background sweep, fired by the same daily cron for housekeeping).
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM cron.job WHERE jobname = 'emergency_signals_auto_expire'
  ) THEN
    PERFORM cron.unschedule('emergency_signals_auto_expire');
  END IF;
END $$;

SELECT cron.schedule(
  'emergency_signals_auto_expire',
  '*/5 * * * *',
  $$
    UPDATE op_emergency_signals
    SET status = 'expired'
    WHERE status = 'pending' AND expires_at < NOW();
  $$
);

-- ---------------------------------------------------------------------------
-- 5. HMAC secret bootstrap — emergency_signal_hmac_key in Supabase vault.
--    Per v3 P9 polish: 3 MCP tools require HMAC-SHA256 over the request body
--    using this shared secret, validated server-side before INSERT.
--
--    NOTE: secret is created with a random 64-byte hex value via gen_random_bytes
--    if not already present. Rotation handled separately (out of scope for 002a).
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  existing_secret TEXT;
BEGIN
  SELECT name INTO existing_secret FROM vault.secrets WHERE name = 'emergency_signal_hmac_key';
  IF existing_secret IS NULL THEN
    PERFORM vault.create_secret(
      encode(gen_random_bytes(32), 'hex'),
      'emergency_signal_hmac_key',
      'HMAC-SHA256 shared secret for op_emergency_signals MCP tools (DIR-002a §3.3 P9 polish)'
    );
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 6. SECURITY DEFINER RPC for retrieving the HMAC secret from vault.
--    The supabase JS client cannot directly query vault.decrypted_secrets via
--    .schema('vault').from('decrypted_secrets'). Standard Supabase pattern is
--    a SECURITY DEFINER function exposed via /rest/v1/rpc/<name>, restricted
--    to service_role.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_emergency_hmac_secret()
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = vault, public
AS $$
DECLARE
  secret TEXT;
BEGIN
  SELECT decrypted_secret INTO secret
  FROM vault.decrypted_secrets
  WHERE name = 'emergency_signal_hmac_key';
  RETURN secret;
END;
$$;

REVOKE EXECUTE ON FUNCTION public.get_emergency_hmac_secret() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.get_emergency_hmac_secret() FROM authenticated;
REVOKE EXECUTE ON FUNCTION public.get_emergency_hmac_secret() FROM anon;
GRANT EXECUTE ON FUNCTION public.get_emergency_hmac_secret() TO service_role;

COMMIT;

-- =============================================================================
-- Verification (run after migration)
-- =============================================================================
-- \d op_emergency_signals
-- \d agent_config  -- expect fast_poll + fast_poll_until
-- SELECT jobname, schedule, command FROM cron.job WHERE jobname LIKE 'emergency%';
-- SELECT name, description FROM vault.secrets WHERE name = 'emergency_signal_hmac_key';
