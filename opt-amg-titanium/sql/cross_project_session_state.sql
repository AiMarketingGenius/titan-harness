-- TITANIUM DOCTRINE v1.0 Gap 7: cross-project session-state bridge.
-- Single-row-per-user pointer table. Every thread close writes here;
-- every new thread bootstrap reads here FIRST to resolve bare "continue".
--
-- Apply via: psql "$SUPABASE_DB_URL" -f cross_project_session_state.sql
-- or Supabase SQL editor.

CREATE TABLE IF NOT EXISTS public.cross_project_session_state (
    user_id                 text PRIMARY KEY,
    last_thread_project_id  text NOT NULL,
    last_thread_id          text NOT NULL,
    last_thread_summary     text NOT NULL CHECK (char_length(last_thread_summary) <= 500),
    last_thread_ended_at    timestamptz NOT NULL DEFAULT now(),
    resume_prompt           text NOT NULL CHECK (char_length(resume_prompt) <= 1024),
    in_flight_task_ids      text[] NOT NULL DEFAULT '{}',
    last_major_decisions_3  jsonb NOT NULL DEFAULT '[]'::jsonb,
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- Auto-update updated_at on row change
CREATE OR REPLACE FUNCTION public._cross_project_touch_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS cross_project_touch_updated_at ON public.cross_project_session_state;
CREATE TRIGGER cross_project_touch_updated_at
BEFORE UPDATE ON public.cross_project_session_state
FOR EACH ROW
EXECUTE FUNCTION public._cross_project_touch_updated_at();

-- RLS: service role can read/write any row; end-users (anon/authenticated)
-- have no access. This is an internal operator-state table.
ALTER TABLE public.cross_project_session_state ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS service_role_all ON public.cross_project_session_state;
CREATE POLICY service_role_all
    ON public.cross_project_session_state
    AS PERMISSIVE
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- No policies for anon/authenticated — they get zero access.

-- Useful index for staleness queries
CREATE INDEX IF NOT EXISTS cross_project_session_state_ended_at_idx
    ON public.cross_project_session_state (last_thread_ended_at DESC);

-- Comment for discoverability
COMMENT ON TABLE public.cross_project_session_state IS
'Titanium Doctrine v1.0 Gap 7: zero-qualifier cross-project thread continuation pointer. One row per operator user. Every thread close writes; every new thread bootstrap reads first to resolve bare "continue". 48hr staleness guard in bootstrap handler.';

COMMENT ON COLUMN public.cross_project_session_state.resume_prompt IS
'≤1KB prompt text to paste back into new Claude.ai thread to resume work exactly where the prior thread left off. Must be project-agnostic enough to work regardless of which project the new thread is opened in.';
