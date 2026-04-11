-- P8 Parallel sub-agents — worker heartbeat + error tables
CREATE TABLE IF NOT EXISTS titan_workers (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  instance_id     text NOT NULL,
  worker_idx      int NOT NULL,
  host            text,
  pid             int,
  current_task_id text,
  active          boolean NOT NULL DEFAULT true,
  last_heartbeat  timestamptz NOT NULL DEFAULT now(),
  started_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (instance_id, worker_idx)
);
CREATE INDEX IF NOT EXISTS titan_workers_heartbeat_idx ON titan_workers(last_heartbeat DESC);
CREATE INDEX IF NOT EXISTS titan_workers_active_idx ON titan_workers(active) WHERE active = true;

CREATE TABLE IF NOT EXISTS worker_errors (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  instance_id    text,
  worker_idx     int,
  task_id        text,
  error_text     text,
  stacktrace     text,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS worker_errors_created_idx ON worker_errors(created_at DESC);
