-- P10 n8n Queue Mode + Parallel Branches — schema migration
-- Supports orchestrator→subworkflow fan-out with DLQ + advisory lock + observability.

CREATE TABLE IF NOT EXISTS n8n_running_heavy (
  workflow_class text PRIMARY KEY,
  run_id         text NOT NULL,
  started_at     timestamptz NOT NULL DEFAULT now(),
  heartbeat      timestamptz NOT NULL DEFAULT now()
);
-- UNIQUE on workflow_class enforces max 1 run per class; multiple classes
-- in flight still bounded by POLICY_CAPACITY_MAX_HEAVY_WORKFLOWS=3 at the
-- orchestrator claim layer.

CREATE TABLE IF NOT EXISTS n8n_runs (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workflow_class   text NOT NULL,
  workflow_run_id  text,
  fan_out_size     int DEFAULT 0,
  successes        int DEFAULT 0,
  failures         int DEFAULT 0,
  deferred         int DEFAULT 0,
  cache_hits       int DEFAULT 0,
  duration_ms      int,
  status           text CHECK (status IN ('running','success','partial','failed','deferred')),
  started_at       timestamptz NOT NULL DEFAULT now(),
  ended_at         timestamptz,
  notes            text
);
CREATE INDEX IF NOT EXISTS n8n_runs_class_idx ON n8n_runs(workflow_class);
CREATE INDEX IF NOT EXISTS n8n_runs_started_idx ON n8n_runs(started_at DESC);

CREATE TABLE IF NOT EXISTS n8n_dlq (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workflow_class   text,
  workflow_run_id  text,
  item_id          text NOT NULL,
  item_payload     jsonb,
  error_text       text,
  retry_count      int DEFAULT 0,
  created_at       timestamptz NOT NULL DEFAULT now(),
  resolved_at      timestamptz
);
CREATE INDEX IF NOT EXISTS n8n_dlq_unresolved_idx ON n8n_dlq(created_at DESC) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS n8n_dlq_class_idx ON n8n_dlq(workflow_class);

-- Subworkflow idempotency: (workflow_run_id, item_id) composite key
CREATE TABLE IF NOT EXISTS n8n_subworkflow_outputs (
  workflow_run_id text NOT NULL,
  item_id         text NOT NULL,
  output          jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (workflow_run_id, item_id)
);
