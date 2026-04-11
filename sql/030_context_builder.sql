-- P4 Context Builder — schema migration
-- Adds pgvector embedding column + supporting tables for trimmed-context retrieval.

CREATE EXTENSION IF NOT EXISTS vector;

-- mem_ground_truth_facts already exists (69 rows per MEMORY.md).
-- Add embedding column if missing.
ALTER TABLE mem_ground_truth_facts
  ADD COLUMN IF NOT EXISTS embedding vector(768);

CREATE INDEX IF NOT EXISTS mem_ground_truth_facts_embedding_idx
  ON mem_ground_truth_facts USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 10);

-- Observability: every build_context call is logged
CREATE TABLE IF NOT EXISTS context_builds (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  caller          text NOT NULL,
  task_id         text,
  task_type       text,
  max_tokens      int,
  final_tokens    int,
  sources_used    jsonb,
  relevance_scores jsonb,
  build_duration_ms int,
  cache_hit       boolean DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS context_builds_caller_idx ON context_builds(caller);
CREATE INDEX IF NOT EXISTS context_builds_created_idx ON context_builds(created_at DESC);

-- Per-chunk summaries cache (keyed by source_id + content hash)
CREATE TABLE IF NOT EXISTS context_summaries (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id      text NOT NULL,
  content_hash   text NOT NULL,
  summary_text   text NOT NULL,
  token_count    int,
  model          text,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS context_summaries_hash_unique
  ON context_summaries(source_id, content_hash);

-- Bypass violations (for surfacing callers that skip the builder)
CREATE TABLE IF NOT EXISTS context_builder_bypasses (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  caller      text NOT NULL,
  task_id     text,
  reason      text,
  detected_at timestamptz NOT NULL DEFAULT now()
);
