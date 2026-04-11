-- P6 Streaming Client — schema migration
CREATE TABLE IF NOT EXISTS task_streams (
  id          bigserial PRIMARY KEY,
  task_id     text NOT NULL,
  session_id  text,
  chunk_idx   int NOT NULL,
  chunk_text  text NOT NULL,
  is_final    boolean DEFAULT false,
  caller      text,
  model       text,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS task_streams_task_idx ON task_streams(task_id, chunk_idx);
CREATE INDEX IF NOT EXISTS task_streams_session_idx ON task_streams(session_id);

CREATE TABLE IF NOT EXISTS stream_fallbacks (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id     text,
  caller      text,
  reason      text,
  fallback_to text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stream_backpressure (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id     text,
  caller      text,
  dropped_chunks int DEFAULT 0,
  queue_depth int,
  reason      text,
  created_at  timestamptz NOT NULL DEFAULT now()
);
