-- titan-harness/sql/130_agent_voice_library.sql
-- CT-0415-17 — 7-agent voice library table.
-- Stores one row per (agent, message_type) pair. Portal reads this table
-- to render "Hear from Alex/Maya/Jordan/..." buttons on client pages.

CREATE TABLE IF NOT EXISTS public.agent_voice_library (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Agent identity
  agent_id          text NOT NULL CHECK (agent_id IN ('alex','maya','jordan','sam','riley','nadia','lumina')),
  agent_role        text NOT NULL,

  -- Voice model
  voice_profile     text NOT NULL,        -- e.g. 'bf_emma', 'am_michael', 'solon_clone'
  tts_engine        text NOT NULL CHECK (tts_engine IN ('kokoro','elevenlabs')),

  -- Message
  message_type      text NOT NULL CHECK (message_type IN ('intro','status_update','question','deliverable','escalation','closing')),
  transcript_text   text NOT NULL,
  client_name       text NOT NULL DEFAULT 'your business',  -- placeholder value used at gen time

  -- Audio artifact
  audio_url         text NOT NULL,        -- HTTPS URL — portal fetches this
  audio_bytes       integer,
  audio_duration_ms integer,

  -- Lifecycle
  status            text NOT NULL DEFAULT 'active' CHECK (status IN ('active','pending_regen','deprecated')),
  pending_reason    text,                  -- e.g. 'ElevenLabs Solon clone regen required'

  -- Provenance
  generated_at      timestamptz NOT NULL DEFAULT now(),
  generated_by      text NOT NULL DEFAULT 'ct0415_17_voice_library_gen.py',
  manifest_sha      text,

  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),

  UNIQUE (agent_id, message_type, client_name)
);

CREATE INDEX IF NOT EXISTS idx_avl_agent           ON public.agent_voice_library (agent_id);
CREATE INDEX IF NOT EXISTS idx_avl_agent_message   ON public.agent_voice_library (agent_id, message_type) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_avl_status          ON public.agent_voice_library (status);

-- RLS: read-only for anon (portal fetches), full access for service role
ALTER TABLE public.agent_voice_library ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "avl_anon_read" ON public.agent_voice_library;
CREATE POLICY "avl_anon_read"
  ON public.agent_voice_library
  FOR SELECT
  TO anon, authenticated
  USING (status = 'active');

DROP POLICY IF EXISTS "avl_service_all" ON public.agent_voice_library;
CREATE POLICY "avl_service_all"
  ON public.agent_voice_library
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Trigger: auto-update updated_at on row change
CREATE OR REPLACE FUNCTION public._avl_touch_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_avl_updated_at ON public.agent_voice_library;
CREATE TRIGGER trg_avl_updated_at
  BEFORE UPDATE ON public.agent_voice_library
  FOR EACH ROW EXECUTE FUNCTION public._avl_touch_updated_at();
