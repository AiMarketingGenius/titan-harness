-- titan-harness/sql/001_ideas_table.sql
-- Purpose: idea capture table for the UserPromptSubmit "lock it" hook.
-- Separate from strict `tasks` table so ideas can be captured raw and
-- promoted later. Includes idea_hash column + unique index for DB-layer
-- deduplication (belt + suspenders against hook-layer dedup bugs).
--
-- Run once in Supabase SQL Editor. Safe to re-run (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS public.ideas (
  id                   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_text            text        NOT NULL,                       -- full idea content
  idea_title           text,                                       -- first 80 chars, or explicit label
  idea_hash            text        NOT NULL,                       -- sha256 of normalized idea_text
  trigger_used         text,                                       -- which phrase fired ('lock it', '🔒', etc.)
  source               text        CHECK (source IN ('prompt-explicit','transcript-context')) DEFAULT 'prompt-explicit',
  instance_id          text        NOT NULL,                       -- mac-solon, vps-titan, etc.
  session_id           text,                                       -- Claude Code session id, if captured
  project_id           text        DEFAULT 'EOM',
  status               text        DEFAULT 'captured' CHECK (status IN ('captured','reviewing','promoted','dead')),
  promoted_to_task_id  text,                                       -- CT-MMDD-NN if promoted
  slack_ts             text,                                       -- Slack message ts for reply-threading
  notes                text,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);

-- Dedup at DB layer: same hash + same calendar day = duplicate.
-- If hook dedup misses, Postgres rejects with unique violation which drainer treats as success.
-- NOTE: created_at::date on a timestamptz is NOT IMMUTABLE (depends on session TZ).
-- AT TIME ZONE 'UTC' returns a plain timestamp, which IS IMMUTABLE when cast to date.
CREATE UNIQUE INDEX IF NOT EXISTS ideas_hash_day_uniq
  ON public.ideas (idea_hash, ((created_at AT TIME ZONE 'UTC')::date));

CREATE INDEX IF NOT EXISTS ideas_created_at_idx ON public.ideas (created_at DESC);
CREATE INDEX IF NOT EXISTS ideas_status_idx     ON public.ideas (status) WHERE status <> 'dead';
CREATE INDEX IF NOT EXISTS ideas_instance_idx   ON public.ideas (instance_id);

-- updated_at trigger
CREATE OR REPLACE FUNCTION public.ideas_set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ideas_updated_at ON public.ideas;
CREATE TRIGGER ideas_updated_at
  BEFORE UPDATE ON public.ideas
  FOR EACH ROW EXECUTE FUNCTION public.ideas_set_updated_at();

-- Comment for future archaeologists
COMMENT ON TABLE  public.ideas IS 'Raw idea capture from titan-harness UserPromptSubmit hook. Promotable to tasks.';
COMMENT ON COLUMN public.ideas.idea_hash IS 'sha256(lower(trim(strip_punct(idea_text)))) — used for dedup.';
COMMENT ON COLUMN public.ideas.status IS 'captured → reviewing → promoted → dead (soft delete).';
