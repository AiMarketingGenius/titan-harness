-- P5 Batch LLM Helper — schema migration
CREATE TABLE IF NOT EXISTS llm_batch_runs (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id       uuid NOT NULL,
  caller         text NOT NULL,
  model_group    text NOT NULL,
  items_in       int NOT NULL,
  items_out      int NOT NULL,
  tokens_in      int DEFAULT 0,
  tokens_out     int DEFAULT 0,
  cost_cents     numeric DEFAULT 0,
  latency_ms     int DEFAULT 0,
  cache_hit_ratio numeric DEFAULT 0,
  status         text CHECK (status IN ('success','partial','failed','deferred')),
  error_text     text,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS llm_batch_runs_batch_idx ON llm_batch_runs(batch_id);
CREATE INDEX IF NOT EXISTS llm_batch_runs_caller_idx ON llm_batch_runs(caller);
CREATE INDEX IF NOT EXISTS llm_batch_runs_created_idx ON llm_batch_runs(created_at DESC);

CREATE TABLE IF NOT EXISTS llm_batch_dlq (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id      uuid,
  item_id       text NOT NULL,
  prompt_hash   text,
  item_payload  jsonb,
  error_text    text,
  retry_count   int DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now(),
  resolved_at   timestamptz
);
CREATE INDEX IF NOT EXISTS llm_batch_dlq_batch_idx ON llm_batch_dlq(batch_id);
CREATE INDEX IF NOT EXISTS llm_batch_dlq_unresolved_idx ON llm_batch_dlq(created_at DESC) WHERE resolved_at IS NULL;
