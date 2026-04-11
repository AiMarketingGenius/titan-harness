-- titan-harness/sql/005_enable_rls.sql
-- Purpose: Enable Row Level Security on all titan-harness tables and
-- install policies that allow the service role full access while laying
-- the groundwork for per-project JWT isolation (future multi-tenant
-- Titan-as-COO clients).
--
-- Background: G.1 (ideas), G.3 (war_room_exchanges), and G.4 (mp_runs)
-- all shipped with rowsecurity=false because PostgREST was hitting the
-- tables via the service role key, which bypasses RLS anyway. The A-grade
-- war-room review of the sprint kill-chain correctly flagged this as a
-- multi-tenant hardening gap: without RLS enabled, a future client
-- plugging a limited JWT into the API would inherit unrestricted access.
--
-- Design:
--   1. ENABLE RLS on all three tables
--   2. Install a "service_role full access" policy (tagged so it can be
--      replaced per-tenant later without dropping RLS)
--   3. Install a "project_id tenant isolation" policy that will activate
--      only when a request carries a JWT claim `project_id = <value>`
--      (no-op today; becomes load-bearing when we issue scoped JWTs)
--
-- Run once in Supabase SQL Editor. Safe to re-run (policies use DROP IF EXISTS).

-- ---------------------------------------------------------------------------
-- 1. public.ideas
-- ---------------------------------------------------------------------------
ALTER TABLE public.ideas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ideas_service_role_full_access ON public.ideas;
CREATE POLICY ideas_service_role_full_access
  ON public.ideas
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

DROP POLICY IF EXISTS ideas_project_tenant_isolation ON public.ideas;
CREATE POLICY ideas_project_tenant_isolation
  ON public.ideas
  FOR ALL
  TO authenticated
  USING (
    project_id = COALESCE(
      current_setting('request.jwt.claim.project_id', true),
      project_id   -- fall back to row's own value if no claim (no-op)
    )
  )
  WITH CHECK (
    project_id = COALESCE(
      current_setting('request.jwt.claim.project_id', true),
      project_id
    )
  );

-- ---------------------------------------------------------------------------
-- 2. public.war_room_exchanges
-- ---------------------------------------------------------------------------
ALTER TABLE public.war_room_exchanges ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS war_room_service_role_full_access ON public.war_room_exchanges;
CREATE POLICY war_room_service_role_full_access
  ON public.war_room_exchanges
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

DROP POLICY IF EXISTS war_room_project_tenant_isolation ON public.war_room_exchanges;
CREATE POLICY war_room_project_tenant_isolation
  ON public.war_room_exchanges
  FOR ALL
  TO authenticated
  USING (
    project_id = COALESCE(
      current_setting('request.jwt.claim.project_id', true),
      project_id
    )
  )
  WITH CHECK (
    project_id = COALESCE(
      current_setting('request.jwt.claim.project_id', true),
      project_id
    )
  );

-- ---------------------------------------------------------------------------
-- 3. public.mp_runs
-- ---------------------------------------------------------------------------
ALTER TABLE public.mp_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS mp_runs_service_role_full_access ON public.mp_runs;
CREATE POLICY mp_runs_service_role_full_access
  ON public.mp_runs
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

DROP POLICY IF EXISTS mp_runs_project_tenant_isolation ON public.mp_runs;
CREATE POLICY mp_runs_project_tenant_isolation
  ON public.mp_runs
  FOR ALL
  TO authenticated
  USING (
    project_id = COALESCE(
      current_setting('request.jwt.claim.project_id', true),
      project_id
    )
  )
  WITH CHECK (
    project_id = COALESCE(
      current_setting('request.jwt.claim.project_id', true),
      project_id
    )
  );

-- ---------------------------------------------------------------------------
-- Comments
-- ---------------------------------------------------------------------------
COMMENT ON POLICY ideas_project_tenant_isolation ON public.ideas IS
  'G.4 A-grade hardening: filter by JWT project_id claim when present. Service role bypasses via separate policy. No-op today (no scoped JWTs yet); becomes active for multi-tenant Titan-as-COO clients.';
COMMENT ON POLICY war_room_project_tenant_isolation ON public.war_room_exchanges IS
  'G.4 A-grade hardening: same pattern as ideas. Keeps war-room audit trail tenant-scoped.';
COMMENT ON POLICY mp_runs_project_tenant_isolation ON public.mp_runs IS
  'G.4 A-grade hardening: same pattern as ideas. Keeps MP phase logs tenant-scoped.';
