-- P7 Prompt Pipelines — schema migration
CREATE TABLE IF NOT EXISTS pipeline_runs (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_name  text NOT NULL,
  caller         text,
  input_hash     text,
  started_at     timestamptz NOT NULL DEFAULT now(),
  ended_at       timestamptz,
  status         text CHECK (status IN ('running','success','failed','deferred','partial')),
  failed_step    text,
  total_cost_cents numeric DEFAULT 0,
  notes          text
);
CREATE INDEX IF NOT EXISTS pipeline_runs_name_idx ON pipeline_runs(pipeline_name);
CREATE INDEX IF NOT EXISTS pipeline_runs_started_idx ON pipeline_runs(started_at DESC);

CREATE TABLE IF NOT EXISTS pipeline_steps (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id         uuid REFERENCES pipeline_runs(id) ON DELETE CASCADE,
  step_name      text NOT NULL,
  model_group    text,
  model_resolved text,
  started_at     timestamptz NOT NULL DEFAULT now(),
  ended_at       timestamptz,
  duration_ms    int,
  tokens_in      int DEFAULT 0,
  tokens_out     int DEFAULT 0,
  cost_cents     numeric DEFAULT 0,
  cache_hit      boolean DEFAULT false,
  status         text CHECK (status IN ('pending','running','success','failed','skipped')),
  error_text     text
);
CREATE INDEX IF NOT EXISTS pipeline_steps_run_idx ON pipeline_steps(run_id);

CREATE TABLE IF NOT EXISTS pipeline_step_outputs (
  run_id       uuid REFERENCES pipeline_runs(id) ON DELETE CASCADE,
  step_name    text NOT NULL,
  content_hash text NOT NULL,
  output       jsonb,
  created_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (run_id, step_name)
);

CREATE TABLE IF NOT EXISTS pipeline_failures (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id      uuid,
  step_name   text,
  error_text  text,
  retry_count int DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now()
);
