-- sql/008_demo_client.sql
-- POST-R3 Phase 4 — Atlas Demo Client + 7-Lane Pipeline
--
-- Inserts "Atlas Demo Co" (HVAC vertical) with pipeline lanes and sample tasks.
-- Apply via Supabase SQL Editor on project egoazyasyrhslluossli.

-- 1. Demo client record
INSERT INTO public.clients (
  project_id,
  name,
  primary_domain,
  contact_name,
  contact_email,
  status,
  onboarded_at
) VALUES (
  'atlas-demo-co',
  'Atlas Demo Co',
  'atlasdemo.co',
  'Demo Contact',
  'demo@atlasdemo.co',
  'active',
  now()
) ON CONFLICT (project_id) DO NOTHING;

-- 2. Pipeline lanes table (idempotent)
CREATE TABLE IF NOT EXISTS public.client_pipeline_lanes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id text NOT NULL REFERENCES public.clients(project_id) ON DELETE CASCADE,
  lane_order int NOT NULL,
  lane_name text NOT NULL,
  lane_status text DEFAULT 'idle'
    CHECK (lane_status IN ('active','paused','running','queued','idle','complete')),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE (project_id, lane_order)
);

ALTER TABLE public.client_pipeline_lanes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_full_access" ON public.client_pipeline_lanes
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- 3. Pipeline tasks table (idempotent)
CREATE TABLE IF NOT EXISTS public.client_pipeline_tasks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id text NOT NULL REFERENCES public.clients(project_id) ON DELETE CASCADE,
  lane_order int NOT NULL,
  task_name text NOT NULL,
  task_status text DEFAULT 'pending'
    CHECK (task_status IN ('completed','in_progress','blocked','pending')),
  notes text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE public.client_pipeline_tasks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_full_access" ON public.client_pipeline_tasks
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- 3b. Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_pipeline_lanes_project
  ON public.client_pipeline_lanes (project_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_tasks_project_lane
  ON public.client_pipeline_tasks (project_id, lane_order);
CREATE INDEX IF NOT EXISTS idx_pipeline_tasks_status
  ON public.client_pipeline_tasks (task_status);

-- 4. Insert 7 lanes for Atlas Demo Co
INSERT INTO public.client_pipeline_lanes (project_id, lane_order, lane_name, lane_status) VALUES
  ('atlas-demo-co', 1, 'Prospect',     'complete'),
  ('atlas-demo-co', 2, 'Qualified',    'complete'),
  ('atlas-demo-co', 3, 'Proposal',     'active'),
  ('atlas-demo-co', 4, 'Negotiation',  'active'),
  ('atlas-demo-co', 5, 'Onboarding',   'running'),
  ('atlas-demo-co', 6, 'Active',       'queued'),
  ('atlas-demo-co', 7, 'Completed',    'idle')
ON CONFLICT (project_id, lane_order) DO UPDATE SET
  lane_name = EXCLUDED.lane_name,
  lane_status = EXCLUDED.lane_status,
  updated_at = now();

-- 5. Insert sample tasks across lanes
-- Lane 1 (Prospect) — completed
INSERT INTO public.client_pipeline_tasks (project_id, lane_order, task_name, task_status) VALUES
  ('atlas-demo-co', 1, 'Initial outreach email sent', 'completed'),
  ('atlas-demo-co', 1, 'Discovery call scheduled', 'completed');

-- Lane 2 (Qualified) — completed
INSERT INTO public.client_pipeline_tasks (project_id, lane_order, task_name, task_status) VALUES
  ('atlas-demo-co', 2, 'Budget confirmed ($3K/mo)', 'completed');

-- Lane 3 (Proposal) — in progress
INSERT INTO public.client_pipeline_tasks (project_id, lane_order, task_name, task_status) VALUES
  ('atlas-demo-co', 3, 'SOW draft v2 sent', 'completed'),
  ('atlas-demo-co', 3, 'Awaiting client signature', 'in_progress');

-- Lane 4 (Negotiation) — one blocked
INSERT INTO public.client_pipeline_tasks (project_id, lane_order, task_name, task_status, notes) VALUES
  ('atlas-demo-co', 4, 'Payment terms review', 'blocked', 'Client requested Net-45 — needs Solon approval');

-- Lane 5 (Onboarding) — in progress
INSERT INTO public.client_pipeline_tasks (project_id, lane_order, task_name, task_status) VALUES
  ('atlas-demo-co', 5, 'GBP access collected', 'completed'),
  ('atlas-demo-co', 5, 'NAP data audit', 'in_progress');

-- ============================================================
-- ROLLBACK (run manually if needed):
--   DELETE FROM public.client_pipeline_tasks WHERE project_id = 'atlas-demo-co';
--   DELETE FROM public.client_pipeline_lanes WHERE project_id = 'atlas-demo-co';
--   DELETE FROM public.clients WHERE project_id = 'atlas-demo-co';
--   DROP TABLE IF EXISTS public.client_pipeline_tasks CASCADE;
--   DROP TABLE IF EXISTS public.client_pipeline_lanes CASCADE;
-- ============================================================
