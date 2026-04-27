-- Migration: op_search_memory KB content boost + topic_tag filter
-- 2026-04-27 — Phase 2.5 Phase B (Solon directive same day)
--
-- Problem: pinned canonical_queue_task chunks dominated semantic search
-- results because pin_boost was 2.0× — KB content (sim 0.6+) lost to
-- pinned tasks (sim 0.4) on every query. Atlas / Encyclopedia / Architecture
-- chunks were invisible to search_memory.
--
-- Fix:
--   1. Pin boost reduced 2.0 -> 1.2 (still ranked higher, just not 2x)
--   2. KB chunk_type added to type_boost case at 1.3 (parity with narrative/reasoning)
--   3. New filter_topic_tags text[] parameter — array overlap filter for
--      namespace-scoped queries (used by search_kb)
--   4. New prefer_chunk_types text[] parameter — soft 1.4× boost on matching
--      types when caller specifies; default null = no preference
--
-- Drops all prior overloaded versions to clear PostgREST RPC routing conflict.

DROP FUNCTION IF EXISTS public.op_search_memory(vector, integer, text, text[], boolean) CASCADE;
DROP FUNCTION IF EXISTS public.op_search_memory(vector, integer, text, text[], boolean, text[]) CASCADE;
DROP FUNCTION IF EXISTS public.op_search_memory(vector, integer, text, text[], boolean, text[], text[]) CASCADE;

CREATE OR REPLACE FUNCTION public.op_search_memory(
  query_embedding vector,
  match_count integer DEFAULT 10,
  filter_project text DEFAULT NULL::text,
  filter_chunk_types text[] DEFAULT NULL::text[],
  include_archived boolean DEFAULT false,
  filter_topic_tags text[] DEFAULT NULL::text[],
  prefer_chunk_types text[] DEFAULT NULL::text[]
)
RETURNS TABLE(
  id uuid, content text, summary text, project_tag text, chunk_type text,
  similarity double precision, final_score double precision,
  pinned boolean, created_at timestamp with time zone,
  topic_tags text[]
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  WITH ranked AS (
    SELECT
      m.id, m.content, m.summary, m.project_tag, m.chunk_type,
      1 - (m.embedding <=> query_embedding) AS raw_similarity,
      m.pinned, m.created_at, m.topic_tags,
      CASE m.chunk_type
        WHEN 'narrative' THEN 1.3
        WHEN 'reasoning' THEN 1.3
        WHEN 'kb'        THEN 1.3
        WHEN 'decision'  THEN 1.1
        ELSE 1.0
      END AS type_boost,
      1.0 + 0.2 * EXP(-EXTRACT(EPOCH FROM (NOW() - m.created_at)) / 86400.0 / 30.0) AS recency_boost,
      CASE WHEN m.pinned THEN 1.2 ELSE 1.0 END AS pin_boost,
      CASE
        WHEN prefer_chunk_types IS NOT NULL AND m.chunk_type = ANY(prefer_chunk_types) THEN 1.4
        ELSE 1.0
      END AS prefer_boost
    FROM op_memory_vectors m
    WHERE m.operator_id = 'OPERATOR_AMG'
      AND m.superseded = false
      AND m.muted = false
      AND m.embedding IS NOT NULL
      AND (include_archived OR m.status = 'active')
      AND (filter_project IS NULL OR m.project_tag = filter_project)
      AND (filter_chunk_types IS NULL OR m.chunk_type = ANY(filter_chunk_types))
      AND (filter_topic_tags IS NULL OR m.topic_tags && filter_topic_tags)
  )
  SELECT r.id, r.content, r.summary, r.project_tag, r.chunk_type,
    r.raw_similarity::FLOAT,
    (r.raw_similarity * r.type_boost * r.recency_boost * r.pin_boost * r.prefer_boost)::FLOAT,
    r.pinned, r.created_at, r.topic_tags
  FROM ranked r
  ORDER BY (r.raw_similarity * r.type_boost * r.recency_boost * r.pin_boost * r.prefer_boost) DESC
  LIMIT match_count;
END;
$$;
