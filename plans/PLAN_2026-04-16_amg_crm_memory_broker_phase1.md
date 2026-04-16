# PLAN — AMG CRM + Persistent Memory Broker · Phase 1

**Task:** design and ship the brokered multi-tenant CRM + memory layer on the AMG operator Supabase project.
**Author:** Titan (architect role) · **Reviewer gate:** Sonar A- minimum before any SQL applies to prod.
**Date:** 2026-04-16
**Status:** DRAFT · PENDING_ARISTOTLE (grading block at bottom marked pending; §12 Idea Builder compliance applies; per §12.5 this plan cannot be marked "ready for Solon" until Aristotle/Sonar returns A-grade or operator explicitly overrides)
**Proposed Greek codename:** `Themis` — goddess of divine order, law, custom. Fits the doctrine-enforcement + tenant-isolation role. `Themis CRM Broker` renders cleanly on a landing page. Awaiting Solon approval per §14 Greek codename rule.

---

## Solon's four design decisions (locked 2026-04-16)

| # | Decision | Choice | Implication |
|---|---|---|---|
| Q1 | `tenant_id` shape | **UUID PK + slug UNIQUE secondary index** | Safer external exposure; slug for logs/human lookup; every tenant-scoped query joins on UUID |
| Q2 | Memory promotion authority | **Operator-only for all memory types (Phase 1)** | Zero accidental canonization. Agents propose; Solon (or Titan acting as operator) approves. Trade: operator inbox grows until volume proves the flow. Relaxable in Phase 2. |
| Q3 | Consumer→operator bridge | **No bridge in Phase 1** | AIMG consumer project (`gaybcxzrzfgvcqpkbeiq`) stays fully isolated. Zero cross-pollination risk. Bridge deferred to Phase 2. |
| Q4 | Broker runtime | **Bun/TypeScript, separate service** (NOT extending amg-mcp-server) | Fresh Bun service at `/opt/amg-crm-broker/` following the `titan-channel.ts` pattern. Keeps core MCP server's blast radius small. |

---

## 1. Executive summary

Phase 1 establishes a brokered multi-tenant CRM + persistent memory layer on the AMG operator Supabase project (`egoazyasyrhslluossli`). **Schema + broker + auditability only. No UI.**

Six architectural layers — every table sits in exactly one:

```
┌─ LAYER 1 ─ TENANT REGISTRY ──────────────────────────────────────┐
│  tenants · operators · operator_tenants                          │
│  Who exists + who can see what                                   │
├─ LAYER 2 ─ RAW EVENTS (IMMUTABLE) ────────────────────────────────┤
│  operator_events                                                 │
│  Append-only signal log. Never mutated. Never deleted.           │
├─ LAYER 3 ─ MEMORY (PROPOSED → CANONICAL) ─────────────────────────┤
│  memory_items · memory_promotions                                │
│  Distilled from events. Status lifecycle: proposed → canonical.  │
│  Operator-only promotion per Q2.                                 │
├─ LAYER 4 ─ CANONICAL CRM (PROMOTED TRUTH) ────────────────────────┤
│  customers · contacts · engagements · activities                 │
│  Only promoted content lands here. Extension/plugin writes       │
│  are IMPOSSIBLE at this layer (RLS enforces).                    │
├─ LAYER 5 ─ OPERATIONAL SURFACES ──────────────────────────────────┤
│  agent_runs · qc_reviews · dual_ai_runs                          │
│  Per-run audit. Dual-AI phase worker writes here on every        │
│  implementation-phase task completion.                           │
├─ LAYER 6 ─ CONTEXT PACKETS ───────────────────────────────────────┤
│  context_packets                                                 │
│  Pre-assembled Customer 360 bundles. Cache layer. Rebuilt        │
│  on canonical change via broker.                                 │
└──────────────────────────────────────────────────────────────────┘
```

**Hard rules enforced at DB level (not just code-level):**
1. No `INSERT`/`UPDATE`/`DELETE` on Layer 4 (canonical CRM) from `authenticated` role — only `service_role` (broker) can write. Plugin/extension sessions never promote to service_role.
2. No direct writes on `memory_items.status='canonical'` — must transit through `memory_promotions` audit trail.
3. `operator_events` is append-only — `UPDATE`/`DELETE` policy denies everything except service_role.
4. Tenant isolation is RLS-enforced on every tenant-scoped table. `service_role` sees all; authenticated operators see only their assigned tenants; master operator (Solon) sees all tenants.

**Phase 1 explicitly does NOT include:**
- Any UI (CLI broker only).
- Consumer→operator bridge (Q3).
- Automated promotion (Q2).
- Retroactive backfill of existing client data (seeds only the 4 current active tenants as shells).
- Production cutover — everything ships to staging/beast-canary first, 24-hour observation, then prod switch.

---

## 2. Output 1 — SQL migration plan

Nine migrations, numbered starting at 160 to avoid collision with the existing sql/140 (implementation_qc_gate) and sql/141 (dual_ai_exchanges) from the foreman plan. Each is `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` + `ALTER TABLE ENABLE ROW LEVEL SECURITY` style — idempotent + re-runnable + rollback-safe.

### Ordered apply sequence

| # | File | What it creates | Apply target |
|---|---|---|---|
| 160 | `sql/160_crm_tenants.sql` | `tenants` registry table | operator project `egoazyasyrhslluossli` |
| 161 | `sql/161_crm_operators.sql` | `operators` + `operator_tenants` ACL tables | operator project |
| 162 | `sql/162_crm_events.sql` | `operator_events` immutable event log | operator project |
| 163 | `sql/163_crm_memory.sql` | `memory_items` + `memory_promotions` + pgvector extension | operator project |
| 164 | `sql/164_crm_canonical.sql` | `customers` + `contacts` + `engagements` + `activities` | operator project |
| 165 | `sql/165_crm_operational.sql` | `agent_runs` + `qc_reviews` + `dual_ai_runs` | operator project |
| 166 | `sql/166_crm_context.sql` | `context_packets` cache + TTL trigger | operator project |
| 167 | `sql/167_crm_rls.sql` | All RLS policies across all 11 tables, atomic | operator project |
| 168 | `sql/168_crm_seed.sql` | 5 tenant rows (shop-unis, paradise-park-novi, revel-roll-west, jdj-levar, amg-internal) + Solon master operator row | operator project |

**Apply order enforcement:** `167_crm_rls.sql` MUST run AFTER 160–166 (policies reference table names). `168_crm_seed.sql` MUST run AFTER 167 (inserts trigger RLS checks). Broker boot refuses to start if any of 160–168 shows absent in `information_schema`.

### Canonical DDL — Layer 1 (tenant registry)

```sql
-- sql/160_crm_tenants.sql
CREATE TABLE IF NOT EXISTS public.tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT NOT NULL,
  display_name TEXT NOT NULL,
  tier TEXT NOT NULL DEFAULT 'standard'
    CHECK (tier IN ('amg_internal','starter','growth','pro','founding_member','consulting','template_export')),
  account_manager_id UUID,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','paused','offboarded','archived')),
  billing_ref TEXT,
  project_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS tenants_slug_uq ON public.tenants (slug);
CREATE INDEX IF NOT EXISTS tenants_status_idx ON public.tenants (status);
ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
```

```sql
-- sql/161_crm_operators.sql
CREATE TABLE IF NOT EXISTS public.operators (
  id UUID PRIMARY KEY,  -- must equal auth.uid() when authenticated
  email TEXT UNIQUE NOT NULL,
  display_name TEXT,
  role TEXT NOT NULL DEFAULT 'agent'
    CHECK (role IN ('master','manager','agent','client_user','readonly')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.operator_tenants (
  operator_id UUID NOT NULL REFERENCES public.operators(id) ON DELETE CASCADE,
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'viewer'
    CHECK (role IN ('owner','editor','viewer')),
  granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  granted_by UUID REFERENCES public.operators(id),
  PRIMARY KEY (operator_id, tenant_id)
);
CREATE INDEX IF NOT EXISTS operator_tenants_tenant_idx ON public.operator_tenants (tenant_id);

ALTER TABLE public.operators ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_tenants ENABLE ROW LEVEL SECURITY;

-- Cache current operator's tenant list into a stable SECURITY DEFINER function
CREATE OR REPLACE FUNCTION public.current_operator_tenants()
RETURNS SETOF UUID
LANGUAGE sql
SECURITY DEFINER
STABLE
AS $$
  SELECT tenant_id FROM public.operator_tenants WHERE operator_id = auth.uid();
$$;

CREATE OR REPLACE FUNCTION public.current_operator_role()
RETURNS TEXT
LANGUAGE sql
SECURITY DEFINER
STABLE
AS $$
  SELECT role FROM public.operators WHERE id = auth.uid();
$$;
```

### Canonical DDL — Layer 2 (immutable events)

```sql
-- sql/162_crm_events.sql
CREATE TABLE IF NOT EXISTS public.operator_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES public.tenants(id) ON DELETE RESTRICT,  -- NULL = amg-internal global
  event_kind TEXT NOT NULL
    CHECK (event_kind IN (
      'message_inbound','message_outbound','call_completed','call_missed',
      'form_submission','email_sent','email_received','meeting_held','meeting_noshow',
      'file_delivered','task_started','task_completed','task_failed',
      'qc_review_completed','dual_ai_completed',
      'payment_received','payment_failed','subscription_changed',
      'agent_handoff','escalation_raised','escalation_resolved',
      'external_signal','other'
    )),
  event_source TEXT NOT NULL,  -- e.g. 'slack','gmail','n8n','stagehand','voice_agent','manual'
  actor_role TEXT NOT NULL     -- 'solon','titan','agent:alex','system','external:<ref>'
    CHECK (actor_role ~ '^(solon|titan|agent:[a-z]+|system|external:.+)$'),
  actor_id TEXT,
  subject_ref TEXT,            -- e.g. customer_id, task_id, contact_id
  subject_type TEXT
    CHECK (subject_type IN ('customer','contact','task','engagement','activity','system','other')),
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_hash TEXT,            -- for dedup if upstream emits at-least-once
  occurred_at TIMESTAMPTZ NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (event_source, source_hash)
);

CREATE INDEX IF NOT EXISTS operator_events_tenant_occurred_idx
  ON public.operator_events (tenant_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS operator_events_subject_idx
  ON public.operator_events (subject_type, subject_ref);
CREATE INDEX IF NOT EXISTS operator_events_kind_idx
  ON public.operator_events (event_kind, occurred_at DESC);

ALTER TABLE public.operator_events ENABLE ROW LEVEL SECURITY;

-- Enforce immutability at the database level (policy below, but also via trigger defensive layer)
CREATE OR REPLACE FUNCTION public._operator_events_immutable_guard()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'operator_events is append-only (attempted %)', TG_OP;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER operator_events_no_update
  BEFORE UPDATE ON public.operator_events
  FOR EACH ROW EXECUTE FUNCTION public._operator_events_immutable_guard();

CREATE TRIGGER operator_events_no_delete
  BEFORE DELETE ON public.operator_events
  FOR EACH ROW EXECUTE FUNCTION public._operator_events_immutable_guard();
```

### Canonical DDL — Layer 3 (memory items + promotion audit)

```sql
-- sql/163_crm_memory.sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.memory_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES public.tenants(id) ON DELETE RESTRICT,  -- NULL = cross-tenant system fact
  subject_ref TEXT NOT NULL,            -- who/what this memory is about (customer_id, contact_id, etc.)
  subject_type TEXT NOT NULL
    CHECK (subject_type IN ('customer','contact','engagement','tenant','agent','system','other')),
  item_type TEXT NOT NULL
    CHECK (item_type IN ('fact','decision','preference','correction','action','narrative','episodic','entity')),
  content TEXT NOT NULL,
  content_embedding VECTOR(1536),       -- populated async by broker
  confidence NUMERIC(3,2) NOT NULL DEFAULT 0.50
    CHECK (confidence >= 0 AND confidence <= 1),
  source_event_ids UUID[] NOT NULL DEFAULT ARRAY[]::UUID[],
  status TEXT NOT NULL DEFAULT 'proposed'
    CHECK (status IN ('proposed','canonical','superseded','rejected')),
  proposed_by_agent TEXT NOT NULL,      -- e.g. 'agent:maya', 'titan', 'n8n:content-extract'
  proposed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  promoted_by_operator UUID REFERENCES public.operators(id),
  promoted_at TIMESTAMPTZ,
  superseded_by UUID REFERENCES public.memory_items(id),
  reject_reason TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_items_tenant_subject_idx
  ON public.memory_items (tenant_id, subject_type, subject_ref) WHERE status = 'canonical';
CREATE INDEX IF NOT EXISTS memory_items_status_idx
  ON public.memory_items (status, proposed_at DESC);
CREATE INDEX IF NOT EXISTS memory_items_embedding_idx
  ON public.memory_items USING ivfflat (content_embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE IF NOT EXISTS public.memory_promotions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  memory_item_id UUID NOT NULL REFERENCES public.memory_items(id) ON DELETE CASCADE,
  from_status TEXT NOT NULL,
  to_status TEXT NOT NULL,
  decided_by UUID NOT NULL REFERENCES public.operators(id),
  decision_rationale TEXT,
  sonar_grade TEXT,                     -- if the promotion was routed through Sonar (future)
  dual_ai_run_id UUID,                  -- if dual-AI worker gated this promotion
  decided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_promotions_item_idx
  ON public.memory_promotions (memory_item_id, decided_at DESC);

ALTER TABLE public.memory_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_promotions ENABLE ROW LEVEL SECURITY;
```

### Canonical DDL — Layer 4 (CRM: customers / contacts / engagements / activities)

```sql
-- sql/164_crm_canonical.sql

CREATE TABLE IF NOT EXISTS public.customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
  external_id TEXT,                     -- e.g. GBP place_id, Shopify customer_id
  name TEXT NOT NULL,
  industry TEXT,
  vertical TEXT,
  website TEXT,
  primary_phone TEXT,
  primary_email TEXT,
  address JSONB,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('prospect','active','churned','archived')),
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_activity_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, external_id)
);
CREATE INDEX IF NOT EXISTS customers_tenant_status_idx ON public.customers (tenant_id, status);
CREATE INDEX IF NOT EXISTS customers_last_activity_idx ON public.customers (tenant_id, last_activity_at DESC);

CREATE TABLE IF NOT EXISTS public.contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
  customer_id UUID REFERENCES public.customers(id) ON DELETE SET NULL,
  first_name TEXT,
  last_name TEXT,
  email TEXT,
  phone TEXT,
  role TEXT,
  is_primary BOOLEAN NOT NULL DEFAULT false,
  consent_flags JSONB NOT NULL DEFAULT '{}'::jsonb,  -- email_opt_in, sms_opt_in, tcpa_consent_at, etc.
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS contacts_tenant_customer_idx ON public.contacts (tenant_id, customer_id);
CREATE UNIQUE INDEX IF NOT EXISTS contacts_tenant_email_uq
  ON public.contacts (tenant_id, lower(email)) WHERE email IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.engagements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
  customer_id UUID NOT NULL REFERENCES public.customers(id) ON DELETE CASCADE,
  engagement_type TEXT NOT NULL
    CHECK (engagement_type IN ('deal','subscription','project','retainer','one_off')),
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','won','lost','paused','completed','archived')),
  start_date DATE,
  end_date DATE,
  mrr_cents INTEGER,
  ltv_cents INTEGER,
  contract_value_cents INTEGER,
  notes TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS engagements_tenant_customer_idx ON public.engagements (tenant_id, customer_id);
CREATE INDEX IF NOT EXISTS engagements_status_idx ON public.engagements (status);

CREATE TABLE IF NOT EXISTS public.activities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
  customer_id UUID REFERENCES public.customers(id) ON DELETE SET NULL,
  contact_id UUID REFERENCES public.contacts(id) ON DELETE SET NULL,
  engagement_id UUID REFERENCES public.engagements(id) ON DELETE SET NULL,
  activity_type TEXT NOT NULL
    CHECK (activity_type IN ('call','email','sms','meeting','note','task','delivery','review','payment','other')),
  channel TEXT,
  direction TEXT CHECK (direction IN ('inbound','outbound','internal')),
  summary TEXT NOT NULL,
  details JSONB,
  source_event_id UUID REFERENCES public.operator_events(id),
  occurred_at TIMESTAMPTZ NOT NULL,
  logged_by_agent TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS activities_tenant_customer_occurred_idx
  ON public.activities (tenant_id, customer_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS activities_tenant_occurred_idx
  ON public.activities (tenant_id, occurred_at DESC);

ALTER TABLE public.customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.engagements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.activities ENABLE ROW LEVEL SECURITY;
```

### Canonical DDL — Layer 5 (agent_runs, qc_reviews, dual_ai_runs)

```sql
-- sql/165_crm_operational.sql

CREATE TABLE IF NOT EXISTS public.agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES public.tenants(id) ON DELETE RESTRICT,
  task_id TEXT,                         -- op_task_queue.task_id (soft ref, not FK — task_queue lives elsewhere)
  agent_id TEXT NOT NULL,               -- 'agent:alex', 'titan', 'dual_ai_worker', etc.
  model_used TEXT NOT NULL,             -- 'claude-opus-4-6', 'claude-haiku-4-5', 'sonar-pro', etc.
  input_tokens INTEGER,
  output_tokens INTEGER,
  cost_cents INTEGER,
  latency_ms INTEGER,
  status TEXT NOT NULL DEFAULT 'success'
    CHECK (status IN ('success','partial','failed','timeout','rate_limited')),
  output_ref TEXT,                      -- pointer to output artifact (R2 key, file path, etc.)
  output_hash TEXT,
  error_text TEXT,
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS agent_runs_task_idx ON public.agent_runs (task_id);
CREATE INDEX IF NOT EXISTS agent_runs_tenant_started_idx
  ON public.agent_runs (tenant_id, started_at DESC);

CREATE TABLE IF NOT EXISTS public.qc_reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES public.tenants(id) ON DELETE RESTRICT,
  task_id TEXT,
  agent_run_id UUID REFERENCES public.agent_runs(id) ON DELETE SET NULL,
  layer TEXT NOT NULL
    CHECK (layer IN ('a_hash','b_adversarial','c_deterministic','d_perplexity','dual_ai_sonar')),
  grade TEXT
    CHECK (grade IS NULL OR grade IN ('A+','A','A-','B+','B','B-','C+','C','C-','D','F','pending')),
  issues JSONB NOT NULL DEFAULT '[]'::jsonb,
  recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
  dimension_scores JSONB,               -- {correctness: 9.5, completeness: 9.2, ...}
  reviewer_model TEXT,
  cost_cents INTEGER NOT NULL DEFAULT 0,
  artifact_hash TEXT,
  reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS qc_reviews_task_layer_idx ON public.qc_reviews (task_id, layer);
CREATE INDEX IF NOT EXISTS qc_reviews_grade_idx ON public.qc_reviews (grade);

CREATE TABLE IF NOT EXISTS public.dual_ai_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES public.tenants(id) ON DELETE RESTRICT,
  task_id TEXT NOT NULL,                -- op_task_queue.task_id
  phase_label TEXT NOT NULL,            -- 'design','spec','implementation','verification','doctrine'
  -- Solution A lane
  solution_a_model TEXT NOT NULL,
  solution_a_text TEXT NOT NULL,
  solution_a_hash TEXT NOT NULL,
  solution_a_tokens_in INTEGER,
  solution_a_tokens_out INTEGER,
  solution_a_cost_cents INTEGER,
  solution_a_latency_ms INTEGER,
  -- Solution B lane
  solution_b_model TEXT NOT NULL,
  solution_b_text TEXT NOT NULL,
  solution_b_hash TEXT NOT NULL,
  solution_b_tokens_in INTEGER,
  solution_b_tokens_out INTEGER,
  solution_b_cost_cents INTEGER,
  solution_b_latency_ms INTEGER,
  -- Sonar adjudication
  sonar_model TEXT NOT NULL,            -- 'sonar-pro' or 'sonar'
  sonar_verdict JSONB NOT NULL,         -- full grader JSON (winner, dimension_scores, risk_tags, rationale, remediation)
  sonar_grade TEXT NOT NULL
    CHECK (sonar_grade IN ('A+','A','A-','B+','B','B-','C+','C','C-','D','F')),
  sonar_cost_cents INTEGER NOT NULL DEFAULT 0,
  -- Decision
  winner TEXT NOT NULL CHECK (winner IN ('a','b','merge','reject')),
  merged_output TEXT,
  merged_output_hash TEXT,
  selected_artifact_hash TEXT NOT NULL, -- = solution_a_hash OR solution_b_hash OR merged_output_hash
  completion_status TEXT NOT NULL
    CHECK (completion_status IN ('completed','revision_needed','escalated','rejected','budget_exhausted')),
  total_cost_cents INTEGER NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS dual_ai_runs_task_idx ON public.dual_ai_runs (task_id, completed_at DESC);
CREATE INDEX IF NOT EXISTS dual_ai_runs_completion_idx ON public.dual_ai_runs (completion_status);

ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qc_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dual_ai_runs ENABLE ROW LEVEL SECURITY;
```

### Canonical DDL — Layer 6 (context packets cache)

```sql
-- sql/166_crm_context.sql
CREATE TABLE IF NOT EXISTS public.context_packets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
  subject_ref TEXT NOT NULL,
  subject_type TEXT NOT NULL,
  purpose TEXT NOT NULL
    CHECK (purpose IN ('customer_360','onboarding','escalation','proposal','agent_handoff','qa_grounding')),
  included_items JSONB NOT NULL,        -- {memory_item_ids: [...], activity_ids: [...], customer_snapshot: {...}}
  rendered_body TEXT,                   -- cached stringification for direct injection
  token_count INTEGER,
  built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  built_for_agent TEXT,
  expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '6 hours'),
  hit_count INTEGER NOT NULL DEFAULT 0,
  last_hit_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS context_packets_tenant_subject_purpose_idx
  ON public.context_packets (tenant_id, subject_type, subject_ref, purpose);
CREATE INDEX IF NOT EXISTS context_packets_expires_idx ON public.context_packets (expires_at);

ALTER TABLE public.context_packets ENABLE ROW LEVEL SECURITY;
```

### Canonical DDL — RLS policies (all tables, atomic)

```sql
-- sql/167_crm_rls.sql — single transaction; DROP/CREATE pattern so re-runnable

BEGIN;

-- === tenants ===
DROP POLICY IF EXISTS tenants_svc_all ON public.tenants;
CREATE POLICY tenants_svc_all ON public.tenants FOR ALL TO service_role
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS tenants_master_read ON public.tenants;
CREATE POLICY tenants_master_read ON public.tenants FOR SELECT TO authenticated
  USING (public.current_operator_role() = 'master');

DROP POLICY IF EXISTS tenants_assigned_read ON public.tenants;
CREATE POLICY tenants_assigned_read ON public.tenants FOR SELECT TO authenticated
  USING (id IN (SELECT public.current_operator_tenants()));

-- === operators ===
DROP POLICY IF EXISTS operators_svc_all ON public.operators;
CREATE POLICY operators_svc_all ON public.operators FOR ALL TO service_role
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS operators_self_read ON public.operators;
CREATE POLICY operators_self_read ON public.operators FOR SELECT TO authenticated
  USING (id = auth.uid() OR public.current_operator_role() = 'master');

-- === operator_tenants ===
DROP POLICY IF EXISTS operator_tenants_svc_all ON public.operator_tenants;
CREATE POLICY operator_tenants_svc_all ON public.operator_tenants FOR ALL TO service_role
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS operator_tenants_self_read ON public.operator_tenants;
CREATE POLICY operator_tenants_self_read ON public.operator_tenants FOR SELECT TO authenticated
  USING (operator_id = auth.uid() OR public.current_operator_role() = 'master');

-- === operator_events ===  (append-only; immutability enforced via trigger)
DROP POLICY IF EXISTS operator_events_svc_all ON public.operator_events;
CREATE POLICY operator_events_svc_all ON public.operator_events FOR ALL TO service_role
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS operator_events_tenant_read ON public.operator_events;
CREATE POLICY operator_events_tenant_read ON public.operator_events FOR SELECT TO authenticated
  USING (
    public.current_operator_role() = 'master'
    OR tenant_id IN (SELECT public.current_operator_tenants())
  );

-- === memory_items ===
DROP POLICY IF EXISTS memory_items_svc_all ON public.memory_items;
CREATE POLICY memory_items_svc_all ON public.memory_items FOR ALL TO service_role
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS memory_items_tenant_read ON public.memory_items;
CREATE POLICY memory_items_tenant_read ON public.memory_items FOR SELECT TO authenticated
  USING (
    public.current_operator_role() = 'master'
    OR tenant_id IN (SELECT public.current_operator_tenants())
  );

-- NO authenticated INSERT/UPDATE/DELETE — broker (service_role) is the only write path.

-- === memory_promotions ===  (audit trail; append-only via app logic; service_role writes)
DROP POLICY IF EXISTS memory_promotions_svc_all ON public.memory_promotions;
CREATE POLICY memory_promotions_svc_all ON public.memory_promotions FOR ALL TO service_role
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS memory_promotions_tenant_read ON public.memory_promotions;
CREATE POLICY memory_promotions_tenant_read ON public.memory_promotions FOR SELECT TO authenticated
  USING (
    public.current_operator_role() = 'master'
    OR memory_item_id IN (
      SELECT id FROM public.memory_items
      WHERE tenant_id IN (SELECT public.current_operator_tenants())
    )
  );

-- === customers / contacts / engagements / activities ===  (Layer 4)
-- Pattern repeats; showing customers only. contacts/engagements/activities identical.
DROP POLICY IF EXISTS customers_svc_all ON public.customers;
CREATE POLICY customers_svc_all ON public.customers FOR ALL TO service_role
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS customers_tenant_read ON public.customers;
CREATE POLICY customers_tenant_read ON public.customers FOR SELECT TO authenticated
  USING (
    public.current_operator_role() = 'master'
    OR tenant_id IN (SELECT public.current_operator_tenants())
  );
-- Explicitly: NO authenticated INSERT/UPDATE/DELETE. Broker only.

-- (Repeat for contacts, engagements, activities.)

-- === agent_runs / qc_reviews / dual_ai_runs ===  (Layer 5)
-- Same pattern: svc_all + tenant_read only. All writes through broker.

-- === context_packets ===
DROP POLICY IF EXISTS context_packets_svc_all ON public.context_packets;
CREATE POLICY context_packets_svc_all ON public.context_packets FOR ALL TO service_role
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS context_packets_tenant_read ON public.context_packets;
CREATE POLICY context_packets_tenant_read ON public.context_packets FOR SELECT TO authenticated
  USING (
    public.current_operator_role() = 'master'
    OR tenant_id IN (SELECT public.current_operator_tenants())
  );

COMMIT;
```

### Canonical DDL — seeds

```sql
-- sql/168_crm_seed.sql (idempotent via ON CONFLICT)

-- 1. Solon master operator
INSERT INTO public.operators (id, email, display_name, role)
VALUES (
  'a0000000-0000-0000-0000-000000000001',   -- placeholder; replace with Solon's real auth.uid() at apply time
  'solon@aimarketinggenius.io',
  'Solon Zafiropoulos',
  'master'
)
ON CONFLICT (id) DO UPDATE SET role='master', updated_at=now();

-- 2. Titan service operator row (service_role bypasses RLS but we still want an operator row for audit)
INSERT INTO public.operators (id, email, display_name, role)
VALUES (
  'a0000000-0000-0000-0000-000000000002',
  'titan@aimarketinggenius.io',
  'Titan (autonomous executor)',
  'master'
)
ON CONFLICT (id) DO NOTHING;

-- 3. Tenants (shells only — full customer/contact data via broker later)
INSERT INTO public.tenants (slug, display_name, tier, status) VALUES
  ('amg-internal', 'AMG Internal Ops', 'amg_internal', 'active'),
  ('shop-unis', 'Shop UNIS (Kay/Trang)', 'pro', 'active'),
  ('paradise-park-novi', 'Paradise Park Novi', 'growth', 'active'),
  ('revel-roll-west', 'Revel & Roll West (James/Ty)', 'growth', 'active'),
  ('jdj-levar', 'JDJ Investment Properties (Levar)', 'founding_member', 'active')
ON CONFLICT (slug) DO UPDATE SET updated_at=now();

-- 4. Give Solon master access to all tenants explicitly (redundant with master role but clean audit)
INSERT INTO public.operator_tenants (operator_id, tenant_id, role, granted_by)
SELECT 'a0000000-0000-0000-0000-000000000001', id, 'owner', 'a0000000-0000-0000-0000-000000000001'
FROM public.tenants
ON CONFLICT (operator_id, tenant_id) DO NOTHING;
```

---

## 3. Output 2 — Table-by-table rationale

| Layer | Table | Why it exists | Why it's separate from X |
|---|---|---|---|
| 1 | `tenants` | Single source of truth for who can exist in the system. UUID PK + slug index per Q1. | Can't be an enum — tenants come and go. Can't merge with `customers` — tenants are WHO we serve; customers are WHO they serve. |
| 1 | `operators` | Distinct from `tenants`. Operators are humans/agents who do work; tenants are organizations we serve. | Separate from Supabase `auth.users` because we add role + display_name + role state that belongs in app schema, not auth schema. |
| 1 | `operator_tenants` | Many-to-many bridge. An operator can see multiple tenants; a tenant can have multiple operators. | Can't fold into `operators` (N:N). Must be a separate table for RLS scoping to work. |
| 2 | `operator_events` | The one table that's append-only. Every signal that arrived from anywhere. Immutability enforced by trigger + RLS policy. | Not merged with `activities` because activities are CANONICAL (one-row-per-touchpoint in CRM), events are RAW (possibly duplicate, possibly noisy, possibly deferred-to-discard). Events ARE promoted into activities through a defined pipeline. |
| 3 | `memory_items` | Distilled facts/prefs/decisions extracted from events. Explicit status lifecycle. | Separate from `operator_events` because events are the SOURCE, memory is the EXTRACTION. A single event can produce zero or many memory items. Separate from `activities` because activities are point-in-time touchpoints; memory is time-invariant facts. |
| 3 | `memory_promotions` | Audit trail for every promotion decision. Who approved what, when, with what rationale. | Separate from `memory_items` so we preserve the full state-transition history even after `memory_items` is updated. Enables rollback + governance audit. |
| 4 | `customers` | The thing each tenant serves. A tenant's customer base. | Separate from `tenants` because customers are scoped BY tenant. Separate from `contacts` because one customer has many contacts. |
| 4 | `contacts` | Humans at the customer orgs. Consent flags, direct outreach handles. | Separate from `customers` (N:1). Separate from `operators` (contacts are external, operators are internal). |
| 4 | `engagements` | The commercial relationship: deal / subscription / project / retainer. | Separate from `customers` because customers can have multiple overlapping engagements (subscription + ad-hoc project). Separate from `activities` because an engagement is a CONTAINER of activities, not an activity itself. |
| 4 | `activities` | Promoted touchpoints. Canonical "this happened." | Separate from `operator_events` because activities are CURATED (de-duped, contextualized, attributed). An activity ALWAYS has a single authoritative `source_event_id`. |
| 5 | `agent_runs` | Per-invocation trace for every AI agent call. Cost + latency + status. | Separate from `op_task_queue` (which is the task inbox) because one task can spawn multiple agent runs (e.g. 4 sub-agents in parallel, or retries after failure). |
| 5 | `qc_reviews` | Per-layer (A/B/C/D + dual_ai_sonar) QC output. | Separate from `op_task_queue.qc_layer_*` columns because those are flat enum slots; this table captures full dimension scores + issues + recommendations per layer per run. |
| 5 | `dual_ai_runs` | The single audit row that captures EVERYTHING the dual-AI phase worker does per implementation-phase task. Required per Solon directive. | Separate from `qc_reviews` because dual_ai_runs records BOTH generator solutions (A + B), not just a grade. Essential for forensic traceability + client demonstrations of "two AIs wrote this, a third graded it." |
| 6 | `context_packets` | Cache layer for assembled Customer 360 bundles. TTL-bound. | Separate from everything else because it's a MATERIALIZED VIEW in spirit — rebuilt from underlying canonical tables. Must be a table (not a view) because the broker needs to render + cache body text for direct injection into agent prompts. |

**Why no single monolithic `crm` table:** every layer has different mutability semantics (immutable vs. proposed→canonical vs. canonical+updatable vs. cache). Collapsing layers violates the modeling rule ("Raw events immutable. Memory distilled from events. Canonical CRM truth updated only by promotion rules.").

---

## 4. Output 3 — RLS policy map

Full policy set is in `sql/167_crm_rls.sql` (above). Compressed matrix:

| Table | service_role | authenticated (tenant-scoped) | authenticated (master) | anon |
|---|---|---|---|---|
| `tenants` | ALL | SELECT where id ∈ operator_tenants | SELECT all | denied |
| `operators` | ALL | SELECT self only | SELECT all | denied |
| `operator_tenants` | ALL | SELECT self-rows | SELECT all | denied |
| `operator_events` | ALL (append-only by trigger) | SELECT where tenant_id ∈ ops | SELECT all | denied |
| `memory_items` | ALL | SELECT where tenant_id ∈ ops | SELECT all | denied |
| `memory_promotions` | ALL | SELECT via memory_items join | SELECT all | denied |
| `customers` | ALL | SELECT where tenant_id ∈ ops | SELECT all | denied |
| `contacts` | ALL | SELECT where tenant_id ∈ ops | SELECT all | denied |
| `engagements` | ALL | SELECT where tenant_id ∈ ops | SELECT all | denied |
| `activities` | ALL | SELECT where tenant_id ∈ ops | SELECT all | denied |
| `agent_runs` | ALL | SELECT where tenant_id ∈ ops | SELECT all | denied |
| `qc_reviews` | ALL | SELECT via agent_run tenant | SELECT all | denied |
| `dual_ai_runs` | ALL | SELECT where tenant_id ∈ ops | SELECT all | denied |
| `context_packets` | ALL | SELECT where tenant_id ∈ ops | SELECT all | denied |

**Key invariant:** no table grants `INSERT`/`UPDATE`/`DELETE` to `authenticated`. **All writes flow through the broker (service_role).** This is the mechanism that enforces "extension/plugin data never writes directly to canonical CRM tables."

**Master operator (Solon):** `current_operator_role() = 'master'` function call in every policy. Set by the `operators.role='master'` row. Bypasses tenant scoping but still goes through RLS (audited via `operator_events`).

**Anon role:** fully denied on every CRM table. The broker's public-facing endpoints (if any in Phase 2) must use service_role + their own auth layer, never grant anon CRM read.

**Defensive triggers (belt and suspenders):**
- `operator_events` has `BEFORE UPDATE` and `BEFORE DELETE` triggers that `RAISE EXCEPTION`. Even a compromised service_role cannot modify history.
- `memory_items.status` transition to `canonical` requires a matching `memory_promotions` row (enforced in application layer by broker; Phase 2 adds DB-level check via trigger).
- `dual_ai_runs.completion_status='completed'` with `sonar_grade NOT IN ('A+','A','A-')` should raise (this is the §12.5 gate at the dual-AI table level; Phase 1 enforces it in broker logic + Phase 2 adds DB trigger).

---

## 5. Output 4 — MCP contract spec (Themis broker)

**Transport:** MCP over HTTP/SSE at `https://broker.aimarketinggenius.io/mcp` (Caddy → localhost:8791). Bearer-token authenticated. Each request MUST include `Authorization: Bearer <token>` where token maps to an `operators.id`.

**Runtime:** Bun + `@modelcontextprotocol/sdk` + `@supabase/supabase-js` + `zod`. Single binary service under systemd.

**Tool surface:**

### `get_customer_360(tenant_slug, customer_ref)`

Returns the full context packet for a customer: canonical CRM fields + recent activities (last 30d) + canonical memory items + pending memory proposals (count only, not content).

**Input:**
```typescript
{
  tenant_slug: string,               // 'shop-unis' etc.
  customer_ref: string,              // either customers.id (UUID) or customers.external_id
  include_activities?: boolean,      // default true
  activities_since_days?: number,    // default 30
  max_memory_items?: number          // default 50
}
```

**Output:**
```typescript
{
  customer: Customer,                // full row
  primary_contact: Contact | null,
  active_engagements: Engagement[],
  recent_activities: Activity[],
  canonical_memory: MemoryItem[],    // status='canonical', ordered by confidence desc
  pending_memory_count: number,      // status='proposed' awaiting promotion
  packet_id?: string,                // if cached in context_packets
  assembled_at: string
}
```

**Enforcement:** tenant_slug resolved to tenant_id, then all SELECT queries scoped. Unknown slug → `TENANT_NOT_FOUND`. No result cross-contamination possible (service_role respects the broker's own tenant scoping logic, which is defense-in-depth over RLS).

### `search_tenant_memory(tenant_slug, query, filters, top_k)`

Vector + lexical search over `memory_items` where `tenant_id = resolve(tenant_slug)` AND `status='canonical'`.

**Input:**
```typescript
{
  tenant_slug: string,
  query: string,
  filters?: {
    item_type?: 'fact'|'decision'|'preference'|'correction'|'action'|'narrative'|'episodic'|'entity',
    subject_type?: 'customer'|'contact'|'engagement'|'tenant'|'agent'|'system'|'other',
    subject_ref?: string,
    min_confidence?: number
  },
  top_k?: number                     // default 10, max 50
}
```

**Output:**
```typescript
{
  results: Array<{
    memory_item: MemoryItem,
    score: number,                   // cosine similarity 0-1
    match_type: 'vector'|'lexical'|'hybrid'
  }>
}
```

### `log_activity_event(tenant_slug, activity)`

**Dual-write:** inserts one row in `operator_events` (raw) AND — if the activity is canonicalizable immediately (direct 1-to-1, like "outbound email sent") — one row in `activities`. `activities.source_event_id` set to the event row.

**Input:**
```typescript
{
  tenant_slug: string,
  activity: {
    customer_ref?: string,
    contact_ref?: string,
    engagement_ref?: string,
    activity_type: 'call'|'email'|'sms'|'meeting'|'note'|'task'|'delivery'|'review'|'payment'|'other',
    channel?: string,
    direction?: 'inbound'|'outbound'|'internal',
    summary: string,
    details?: Record<string, unknown>,
    occurred_at: string,             // ISO-8601
    logged_by_agent: string          // 'agent:alex', 'n8n:inbox-watcher', etc.
  },
  source_signal?: {
    event_kind: string,
    event_source: string,
    payload?: Record<string, unknown>,
    source_hash?: string
  }
}
```

**Output:**
```typescript
{
  event_id: string,                  // operator_events.id
  activity_id?: string,              // activities.id (if canonicalized immediately)
  canonical: boolean                 // true = activity row created, false = event only, promotion pending
}
```

### `propose_memory_items(tenant_slug, subject_ref, subject_type, items[])`

Bulk insert into `memory_items` with `status='proposed'`. Returns proposal IDs.

**Input:**
```typescript
{
  tenant_slug: string,
  subject_ref: string,
  subject_type: string,
  items: Array<{
    item_type: string,
    content: string,
    confidence: number,              // 0-1
    source_event_ids: string[],      // must be non-empty
    proposed_by_agent: string,
    metadata?: Record<string, unknown>
  }>
}
```

**Output:**
```typescript
{
  proposals: Array<{
    id: string,
    tenant_id: string,
    status: 'proposed',
    proposed_at: string
  }>
}
```

### `promote_memory_fact(proposal_id, operator_decision, rationale, context?)`

**Operator-only per Q2.** Transitions `memory_items.status`. Writes `memory_promotions` audit row. Updates canonical CRM if the promotion implies it (e.g., promoting a `fact` about a customer's phone number updates `customers.primary_phone`).

**Input:**
```typescript
{
  proposal_id: string,
  operator_decision: 'promote'|'reject'|'supersede',
  rationale?: string,
  superseded_by?: string,            // memory_items.id if decision='supersede'
  sonar_grade?: string,              // if routed through Sonar (Phase 2)
  dual_ai_run_id?: string,           // if dual-AI gated (Phase 2)
  auto_canonicalize_crm?: boolean    // default true; when true, applies the memory to customers/contacts/engagements rows where appropriate
}
```

**Output:**
```typescript
{
  memory_item_id: string,
  new_status: 'canonical'|'rejected'|'superseded',
  canonical_crm_updated: boolean,
  canonical_crm_updates: Array<{
    table: string,
    id: string,
    fields: string[]
  }>,
  promotion_id: string               // memory_promotions.id
}
```

**Auth:** caller's bearer token MUST resolve to `operators.role IN ('master','manager')`. `agent` role cannot promote. Rejected with `PROMOTION_UNAUTHORIZED`.

### `build_context_packet(tenant_slug, subject_ref, subject_type, purpose, max_tokens)`

Assembles a Customer 360 (or other-purpose) bundle from canonical CRM + canonical memory_items + recent activities. Caches in `context_packets` with TTL. Returns rendered body.

**Input:**
```typescript
{
  tenant_slug: string,
  subject_ref: string,
  subject_type: string,
  purpose: 'customer_360'|'onboarding'|'escalation'|'proposal'|'agent_handoff'|'qa_grounding',
  max_tokens?: number,               // default 4000
  built_for_agent?: string,
  force_rebuild?: boolean            // skip cache
}
```

**Output:**
```typescript
{
  packet_id: string,
  rendered_body: string,
  token_count: number,
  included: {
    customer?: string,
    contacts: string[],
    engagements: string[],
    activities: string[],
    memory_items: string[]
  },
  expires_at: string,
  from_cache: boolean
}
```

### `log_agent_run(run)`

Writes `agent_runs` row. Called by every agent wrapper after execution.

**Input:**
```typescript
{
  tenant_slug?: string,
  task_id?: string,
  agent_id: string,
  model_used: string,
  input_tokens?: number,
  output_tokens?: number,
  cost_cents?: number,
  latency_ms?: number,
  status: 'success'|'partial'|'failed'|'timeout'|'rate_limited',
  output_ref?: string,
  output_hash?: string,
  error_text?: string,
  started_at: string,
  completed_at?: string,
  metadata?: Record<string, unknown>
}
```

**Output:** `{ run_id: string }`

### `log_qc_review(review)`

Writes `qc_reviews` row. Called by Layer A/B/C/D + dual-AI Sonar lane.

**Input:**
```typescript
{
  tenant_slug?: string,
  task_id?: string,
  agent_run_id?: string,
  layer: 'a_hash'|'b_adversarial'|'c_deterministic'|'d_perplexity'|'dual_ai_sonar',
  grade?: 'A+'|'A'|'A-'|'B+'|'B'|'B-'|'C+'|'C'|'C-'|'D'|'F'|'pending',
  issues?: Array<{severity: string, text: string}>,
  recommendations?: Array<{priority: string, text: string}>,
  dimension_scores?: Record<string, number>,
  reviewer_model?: string,
  cost_cents?: number,
  artifact_hash?: string,
  metadata?: Record<string, unknown>
}
```

**Output:** `{ review_id: string }`

### `log_dual_ai_run(run)` — **required audit surface for implementation-phase tasks**

Writes the full A-vs-B record. Called by `dual_ai_phase_worker.py` (when it goes live) once per implementation-phase task completion.

**Input:**
```typescript
{
  tenant_slug?: string,
  task_id: string,                   // required
  phase_label: 'design'|'spec'|'implementation'|'verification'|'doctrine',
  solution_a: { model: string, text: string, hash: string, tokens_in?: number, tokens_out?: number, cost_cents?: number, latency_ms?: number },
  solution_b: { model: string, text: string, hash: string, tokens_in?: number, tokens_out?: number, cost_cents?: number, latency_ms?: number },
  sonar: { model: string, verdict: object, grade: string, cost_cents?: number },
  winner: 'a'|'b'|'merge'|'reject',
  merged_output?: string,
  merged_output_hash?: string,
  selected_artifact_hash: string,    // MUST match solution_a.hash OR solution_b.hash OR merged_output_hash
  completion_status: 'completed'|'revision_needed'|'escalated'|'rejected'|'budget_exhausted',
  total_cost_cents: number,
  started_at: string,
  completed_at: string,
  metadata?: Record<string, unknown>
}
```

**Output:** `{ run_id: string }`

**Broker-side enforcement of §12.5 A- floor:**
- If `completion_status='completed'` AND `sonar.grade NOT IN ('A+','A','A-')` → reject with `IMPL_QC_GATE_VIOLATION`.
- If `selected_artifact_hash` does not match any of the three hashes → reject with `ARTIFACT_HASH_MISMATCH`.
- On valid write, broker optionally calls `op_task_queue.update_task(task_id, status='completed')` via the existing MCP tool chain (bypass via direct Supabase write is also blocked by `sql/140_implementation_qc_gate.sql` DB trigger in the foreman plan).

---

## 6. Output 5 — Server change plan (beast primary + HostHatch staging/failover)

### Beast VPS (primary production) — rollout

**Prerequisites:**
- Beast VPS specs confirmed + SSH access verified.
- `/etc/amg/crm-broker.env` deployed by Solon (or via Stagehand with Solon-in-loop) containing `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (for `egoazyasyrhslluossli`), `BROKER_BEARER_SECRET`, `BROKER_PORT=8791`.
- Bun installed on beast (`curl -fsSL https://bun.sh/install | bash`).

**Steps (file-by-file):**

1. Create `/opt/amg-crm-broker/` directory. Clone scaffold from `~/titan-harness/services/amg-crm-broker/` (new tree in repo).
2. `cd /opt/amg-crm-broker && bun install`.
3. Scaffold files to ship (all under `services/amg-crm-broker/` in harness repo):
   ```
   services/amg-crm-broker/
   ├── package.json
   ├── tsconfig.json
   ├── src/
   │   ├── index.ts              # MCP server entry + Bun HTTP listener
   │   ├── db.ts                 # Supabase client (service_role) + query helpers
   │   ├── auth.ts               # bearer-token → operator lookup
   │   ├── types.ts              # zod schemas for all 9 tools
   │   ├── tools/
   │   │   ├── get_customer_360.ts
   │   │   ├── search_tenant_memory.ts
   │   │   ├── log_activity_event.ts
   │   │   ├── propose_memory_items.ts
   │   │   ├── promote_memory_fact.ts
   │   │   ├── build_context_packet.ts
   │   │   ├── log_agent_run.ts
   │   │   ├── log_qc_review.ts
   │   │   └── log_dual_ai_run.ts
   │   └── audit/
   │       └── operator_events_logger.ts   # every tool call logs its own audit event
   ├── tests/
   │   ├── rls_isolation.test.ts
   │   ├── promotion_gate.test.ts
   │   ├── impl_phase_gate.test.ts
   │   └── dual_ai_audit.test.ts
   └── README.md
   ```
4. systemd unit at `/etc/systemd/system/amg-crm-broker.service`:
   ```
   [Unit]
   Description=AMG CRM + Memory Broker (Themis)
   After=network.target
   [Service]
   EnvironmentFile=/etc/amg/crm-broker.env
   ExecStart=/usr/local/bin/bun run /opt/amg-crm-broker/src/index.ts
   Restart=always
   RestartSec=3
   User=amg-broker
   [Install]
   WantedBy=multi-user.target
   ```
5. Caddy route on `broker.aimarketinggenius.io` → `reverse_proxy localhost:8791`. TLS auto via Let's Encrypt. Bearer-token check is in the broker itself, not Caddy (so bad-token attempts still log to `operator_events`).
6. Register the broker in Titan's MCP config (`~/.config/claude/claude_desktop_config.json` on Mac + equivalent on VPS) so Titan sessions can call these 9 tools directly.

**Apply order on beast:**
```
1. Apply sql/160..168 via Supabase Mgmt API + PAT (same path we used for sql/002).
2. Verify all 11 tables + all policies present via information_schema + pg_policies.
3. Deploy broker code to /opt/amg-crm-broker/.
4. systemctl daemon-reload && systemctl enable --now amg-crm-broker.
5. Smoke test:
   - curl GET /healthz → 200 {"ok":true}
   - curl GET /tools (MCP list) → 9 tools enumerated
   - POST /mcp {call: get_customer_360, tenant_slug: 'amg-internal', customer_ref: <bogus>} → expect 404 TENANT_CUSTOMER_NOT_FOUND (proves tenant resolution + RLS work)
   - POST /mcp {call: propose_memory_items, ...} with agent-role token → expect 403 on promote_memory_fact (proves role enforcement)
6. Register broker.aimarketinggenius.io in Caddy + reload Caddy.
7. Register broker in Titan MCP config.
8. 24-hour observation period: operator_events grows, zero RLS violations in Postgres log, zero broker crashes.
```

### HostHatch VPS (staging + DR failover) — mirror rollout

Same scaffold, mirror-deployed via the existing post-receive hook (already updated to update both `/opt/titan-harness` and `/opt/titan-harness-work` per the 2026-04-16 fix). Add a sibling rule to the hook for `/opt/amg-crm-broker/` sync.

**Cold-standby mode:**
- systemd unit installed + `enabled` but `stopped` by default.
- Env points at a SEPARATE Supabase project (if we create a staging project) OR at the same production project but with a READ-ONLY service key (no writes allowed to production from HostHatch in failover-test mode).
- Caddy route on `broker-staging.aimarketinggenius.io` (different subdomain) so we don't collide DNS.

**DR cutover runbook (future):**
- DNS failover: `broker.aimarketinggenius.io` CNAME from beast → HostHatch.
- `systemctl start amg-crm-broker` on HostHatch.
- Swap env to production SUPABASE_SERVICE_ROLE_KEY.
- Cutover verified by the 24-hour soak test on beast for the reverse.

### Apply ordering — beast first, HostHatch second

**Rationale:** beast is the new primary. Staging follows primary. Cutover path stays clean.

1. Day 0: SQL migrations to operator project (egoazyasyrhslluossli) — SAFE, no code depends on them yet.
2. Day 0+6h: broker ships to beast, smoke tests.
3. Day 0+24h: broker soak confirms no errors.
4. Day 1: broker ships to HostHatch as cold standby.
5. Day 1+24h: full topology confirmed; seed data backfill can begin (done via the broker, not raw SQL — this proves the broker is the canonical write path).

---

## 7. Output 6 — Rollback plan

Every layer is additive + reversible. Order of rollback is the reverse of deploy:

### Code rollback (broker)
```bash
# On beast
systemctl stop amg-crm-broker
systemctl disable amg-crm-broker
# All existing services unaffected.
```
Titan MCP config can also remove the broker from its tool list — Titan falls back to direct Supabase REST where needed.

### DNS/routing rollback
```bash
# Caddy
# Remove broker.aimarketinggenius.io block from Caddyfile
# systemctl reload caddy
```

### Schema rollback (operator Supabase project)

```sql
-- rollback script (sql/169_crm_rollback.sql, NOT committed until Solon explicitly authorizes use)
BEGIN;

-- Drop policies first (order matters because of dependencies)
DROP POLICY IF EXISTS ... ON public.tenants;
-- ... (all policies)

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS public.context_packets CASCADE;
DROP TABLE IF EXISTS public.dual_ai_runs CASCADE;
DROP TABLE IF EXISTS public.qc_reviews CASCADE;
DROP TABLE IF EXISTS public.agent_runs CASCADE;
DROP TABLE IF EXISTS public.activities CASCADE;
DROP TABLE IF EXISTS public.engagements CASCADE;
DROP TABLE IF EXISTS public.contacts CASCADE;
DROP TABLE IF EXISTS public.customers CASCADE;
DROP TABLE IF EXISTS public.memory_promotions CASCADE;
DROP TABLE IF EXISTS public.memory_items CASCADE;
DROP TABLE IF EXISTS public.operator_events CASCADE;
DROP TABLE IF EXISTS public.operator_tenants CASCADE;
DROP TABLE IF EXISTS public.operators CASCADE;
DROP TABLE IF EXISTS public.tenants CASCADE;

-- Drop helper functions
DROP FUNCTION IF EXISTS public.current_operator_tenants();
DROP FUNCTION IF EXISTS public.current_operator_role();
DROP FUNCTION IF EXISTS public._operator_events_immutable_guard();

-- pgvector extension: leave in place (may be used by other products)

COMMIT;
```

**Data loss on rollback:** full. This is acceptable in Phase 1 because the broker has been writing for at most ~24h of soak when rollback might fire, and no client-facing system yet depends on CRM data living in these tables. The existing `op_task_queue`, `agent_config`, `client_facts`, and AIMG consumer project are all untouched by this migration — they're in different tables / different projects.

**Partial rollback:** any single `sql/16N_*.sql` file is independently droppable. The dependency chain means you drop in reverse: 168 (seed data) → 167 (policies) → 166→165→164→163→162→161→160 (tables). Helper functions drop last.

**Non-destructive rollback (preferred):**
```sql
-- Disable RLS to keep the tables accessible to anyone with service_role, but
-- freeze the broker. Use when you want to stop writes without losing data.
ALTER TABLE public.operator_events DISABLE ROW LEVEL SECURITY;
-- (etc.)
systemctl stop amg-crm-broker
```
Then debug, resolve, re-enable RLS, restart broker. Zero data loss.

**Auditability of rollback:** the rollback itself is logged as a manual `log_decision` MCP call with tag `phase-1-rollback-executed` + rationale + timestamp. Matches the §17 Ironclad Auto-Harness pattern for destructive ops.

---

## 8. Dual-AI audit wiring — explicit confirmation

Per Solon's directive: *"Dual-AI audit tables wired so every implementation-phase task stores both model outputs, Sonar review, selected artifact hash, and completion status."*

**The single audit surface:** `public.dual_ai_runs` (Layer 5, DDL above).

**The single write path:** broker tool `log_dual_ai_run(run)` (MCP contract spec §5 above).

**The single enforcement path:** broker rejects `completion_status='completed'` with `sonar.grade NOT IN ('A+','A','A-')`. Returns `IMPL_QC_GATE_VIOLATION` error. The task in `op_task_queue` remains in `active` state, worker must either re-grade or escalate.

**Required fields always present:**
- `solution_a_text` + `solution_a_hash` + `solution_a_model`
- `solution_b_text` + `solution_b_hash` + `solution_b_model`
- `sonar_verdict` (full JSON) + `sonar_grade`
- `selected_artifact_hash` (must match one of solution_a/b/merged hashes)
- `completion_status` (enum, enforced by CHECK constraint)

**Cross-reference:** this audit wiring complements but does NOT replace the existing foreman plan:
- `sql/140_implementation_qc_gate.sql` (BEFORE UPDATE trigger on `op_task_queue`) = last-line DB guard at the task-queue level.
- `sql/141_dual_ai_exchanges.sql` = per-exchange audit for the `dual_ai_phase_worker.py` Python worker.
- `sql/165_crm_operational.sql` → `dual_ai_runs` table defined in this plan = the CRM-integrated audit, tenant-scoped + accessible via MCP.

All three tables can coexist. The foreman plan's `dual_ai_exchanges` is a **worker-local log** (every model call per phase per worker run). This plan's `dual_ai_runs` is the **tenant-integrated audit** (one row per task completion, referenced in Customer 360 packets). Recommend renaming foreman-plan's `dual_ai_exchanges` → `dual_ai_worker_exchanges` to avoid confusion; flagged as open question below.

---

## 9. Phase 1 acceptance criteria

1. All 9 SQL migrations (160–168) apply cleanly to operator Supabase project without errors.
2. All 11 tables exist + all policies show in `pg_policies`.
3. `operator_events` trigger rejects UPDATE + DELETE attempts (even from service_role).
4. Broker boots cleanly on beast. `/healthz` returns 200.
5. All 9 MCP tools enumerated in `/tools` response.
6. Smoke test for each tool against seed data:
   - `get_customer_360('amg-internal', …)` → returns empty packet with zero results (seed has no customers yet).
   - `propose_memory_items(...)` → creates `memory_items` row with status='proposed'.
   - `promote_memory_fact(...)` with agent token → rejected with `PROMOTION_UNAUTHORIZED`.
   - `promote_memory_fact(...)` with Solon's master token → transitions to canonical, creates `memory_promotions` row.
   - `log_dual_ai_run(...)` with `sonar.grade='B+'` + `completion_status='completed'` → rejected with `IMPL_QC_GATE_VIOLATION`.
   - `log_dual_ai_run(...)` with `sonar.grade='A-'` + matching hashes → succeeds, row inserted.
7. RLS isolation test: two operator tokens (one scoped to `shop-unis`, one scoped to `paradise-park-novi`) see ONLY their own tenant's data on every read.
8. Master operator token sees all tenants on every read.
9. Mirror legs: broker code present at `/opt/amg-crm-broker/` on both beast AND HostHatch (HostHatch cold-standby).
10. 24-hour soak on beast with zero broker crashes + zero RLS violations in Postgres log.
11. This plan file, `plans/PLAN_2026-04-16_amg_crm_memory_broker_phase1.md`, has Sonar grade ≥ A- in its grading block BEFORE any SQL applies to production.

---

## 10. Open questions (Solon needs to decide before Phase 1 applies)

1. **Solon's real `auth.uid()` UUID** for seed data. Currently placeholder `a0000000-...-01`. Needs swap at apply time. Easiest path: Solon signs in to Supabase Studio for the operator project once, I capture the UUID, swap it into `sql/168_crm_seed.sql` before apply.
2. **Greek codename approval.** Proposing `Themis` (divine order + tenant isolation + promotion rules). Alternative: `Hestia` (hearth/home = canonical source of truth). Or Solon-picked. Name locks once approved.
3. **Staging Supabase project decision.** Do we want a separate Supabase project for HostHatch staging (~$25/mo extra), or have HostHatch point at production with READ-ONLY key? Recommend separate for true isolation; defer to Solon.
4. **Name collision:** foreman plan proposed `dual_ai_exchanges`. This plan has `dual_ai_runs`. Recommend renaming foreman's to `dual_ai_worker_exchanges` to differentiate the worker-local log from the tenant-integrated audit. Solon confirmation needed.
5. **Grading path for this plan.** Per §12 + §12.5, this plan needs Sonar A- before any prod apply. Three paths: (a) Aristotle/Slack if channel live, (b) direct sonar-pro via `lib/war_room.py`, (c) Titan self-grade marked `PENDING_ARISTOTLE` if both unavailable. Prefer (a) or (b).

---

## 11. Explicitly NOT in Phase 1

- Any UI (no web app, no Titan desktop pane, no agent command center).
- Consumer → operator bridge (Q3 answer = no bridge in Phase 1).
- Automated promotion (Q2 answer = operator-only for all memory types).
- Backfill of existing client data from Fireflies / Loom / Slack / Gmail into `operator_events`. That's Phase 2 — Themis ingestion pipelines.
- Retention policies (TTL on events, soft-delete on customers). Phase 1 keeps everything forever; retention is Phase 2 governance doctrine work.
- Integration with the existing `op_task_queue` task lifecycle (broker can READ it; doesn't WRITE to it except via the existing MCP tools).
- Cost-tracking dashboards on `agent_runs.cost_cents`. The data is captured; visualization is Phase 2.
- AIMG-style dogfooding on Solon's own CRM (i.e., using Themis to track Solon's own life — feasible but out of scope).

---

## 12. Grading block

**Per §12 Idea Builder compliance, this plan is NOT ready for Solon to execute until it clears A-grade.**

| Dimension | Score | Notes |
|---|---|---|
| 1. Correctness | — | PENDING_ARISTOTLE — Sonar needs to verify SQL/RLS patterns + MCP contract soundness |
| 2. Completeness | — | PENDING_ARISTOTLE — does the 6-layer model cover everything Solon asked for? |
| 3. Honest scope | — | PENDING_ARISTOTLE |
| 4. Rollback availability | — | PENDING_ARISTOTLE — rollback script exists but unreviewed |
| 5. Fit with harness patterns | — | PENDING_ARISTOTLE — follows Ironclad §17 + Hercules Triangle + §12.5 A- floor |
| 6. Actionability | — | PENDING_ARISTOTLE |
| 7. Risk coverage | — | PENDING_ARISTOTLE — especially: tenant-bypass attack surfaces, broker auth bypass, RLS policy gaps |
| 8. Evidence quality | — | PENDING_ARISTOTLE — citations for pgvector + RLS best-practices? |
| 9. Internal consistency | — | PENDING_ARISTOTLE |
| 10. Ship-ready for production | — | PENDING_ARISTOTLE |
| **Overall** | **PENDING_ARISTOTLE** | |

**Method used:** drafted by Titan; awaiting external adjudication.
**Why this method:** Aristotle Slack channel unavailable at time of drafting; foreman-plan dual-AI worker not yet shipped. Path (c) self-grade would be premature given the complexity of this plan's RLS + broker contract surface.
**Pending:** re-grade via Perplexity sonar-pro as soon as Solon is at a terminal to kick off the war-room loop, OR via Aristotle-in-Slack once `policy.yaml aristotle_enabled: true` is live.
**Revision rounds:** 0. This is round 1.
**Decision:** HOLD — do not apply sql/160–168 to production until grading clears A-.

---

**Next step:** Solon decides on open questions §10 + picks grading path + authorizes or vetoes Phase 1 apply. Code + migrations are drafted only; nothing is touching Supabase until green-light.
