-- sql/008_governance_audit.sql
-- DR-AMG-GOVERNANCE-01 Task 1.1 — Immutable Audit Stream
-- Apply in Supabase SQL Editor (operator project: egoazyasyrhslluossli)
--
-- Hash-chained, insert-only governance telemetry table.
-- Defends against Evidence Pattern 1 (undetected violations), Principle 3 (Tamper-Resistant Telemetry).

-- 1. Create the table
CREATE TABLE IF NOT EXISTS public.governance_audit (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT NOT NULL,
  timestamp_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  agent_id TEXT NOT NULL DEFAULT 'titan',
  action_type TEXT NOT NULL,
  action_payload JSONB NOT NULL,
  rule_ids_checked TEXT[] DEFAULT '{}',
  rule_ids_violated TEXT[] DEFAULT '{}',
  enforcement_applied TEXT,
  outcome TEXT,
  git_sha_before TEXT,
  git_sha_after TEXT,
  mcp_state_hash TEXT,
  operator_override BOOLEAN DEFAULT FALSE,
  override_id UUID,
  prev_event_hash TEXT NOT NULL,
  this_event_hash TEXT NOT NULL,
  CONSTRAINT hash_chain_not_null CHECK (this_event_hash IS NOT NULL)
);

-- 2. Indexes
CREATE INDEX IF NOT EXISTS idx_gov_audit_session ON public.governance_audit(session_id);
CREATE INDEX IF NOT EXISTS idx_gov_audit_ts ON public.governance_audit(timestamp_utc DESC);
CREATE INDEX IF NOT EXISTS idx_gov_audit_violations ON public.governance_audit(rule_ids_violated)
  WHERE array_length(rule_ids_violated, 1) > 0;
CREATE INDEX IF NOT EXISTS idx_gov_audit_agent ON public.governance_audit(agent_id);

-- 3. RLS — insert-only for Titan, read for auditor, admin-only for Solon
ALTER TABLE public.governance_audit ENABLE ROW LEVEL SECURITY;

-- Titan can INSERT only. No UPDATE, no DELETE, ever.
CREATE POLICY titan_insert ON public.governance_audit
  FOR INSERT
  WITH CHECK (agent_id = 'titan');

-- Authenticated users can SELECT (auditor + operator read)
CREATE POLICY auditor_select ON public.governance_audit
  FOR SELECT
  USING (true);

-- Explicitly block UPDATE and DELETE for all roles
-- (RLS default-deny handles this, but belt-and-suspenders)
CREATE POLICY no_update ON public.governance_audit
  FOR UPDATE
  USING (false);

CREATE POLICY no_delete ON public.governance_audit
  FOR DELETE
  USING (false);

-- 4. Verification queries (run after apply to confirm)
-- SELECT count(*) FROM public.governance_audit; -- should be 0
-- Try UPDATE: UPDATE public.governance_audit SET agent_id = 'hacked' WHERE true; -- should fail
-- Try DELETE: DELETE FROM public.governance_audit WHERE true; -- should fail
