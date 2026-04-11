-- P3 Model Router — schema migration
CREATE TABLE IF NOT EXISTS model_router_choices (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id         text,
  task_type       text,
  chosen_model    text NOT NULL,
  fallback_from   text,
  cost_cents      numeric DEFAULT 0,
  latency_ms      int DEFAULT 0,
  chosen_at       timestamptz NOT NULL DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS model_router_choices_chosen_at_idx ON model_router_choices(chosen_at DESC);
CREATE INDEX IF NOT EXISTS model_router_choices_task_type_idx ON model_router_choices(task_type);

CREATE TABLE IF NOT EXISTS model_router_misses (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_type    text NOT NULL,
  task_id      text,
  fallback_to  text NOT NULL,
  observed_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS model_router_misses_task_type_idx ON model_router_misses(task_type);
CREATE INDEX IF NOT EXISTS model_router_misses_observed_at_idx ON model_router_misses(observed_at DESC);
