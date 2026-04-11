-- titan-harness/sql/003_war_room_exchanges.sql
-- Purpose: Phase G.3 War Room — log every round of the Titan ↔ Perplexity
-- auto-refinement loop. One row per round. Rounds of the same session share
-- an exchange_group_id so the full convergence trajectory can be replayed.
--
-- Separate from `tasks` because a single task may spawn multiple war-room
-- sessions (e.g. plan_finalization + architecture_decision) and we want
-- cost/grade trends over time, not just "was this task war-roomed".
--
-- Run once in Supabase SQL Editor. Safe to re-run (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS public.war_room_exchanges (
  id                        uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Grouping: one uuid per war-room invocation, linking all rounds.
  exchange_group_id         uuid        NOT NULL,
  round_number              int         NOT NULL CHECK (round_number >= 1),
  parent_exchange_id        uuid        REFERENCES public.war_room_exchanges(id) ON DELETE SET NULL,

  -- Titan's output under review (may be revised round-to-round).
  titan_output_text         text        NOT NULL,
  titan_output_hash         text        NOT NULL,  -- sha256 for dedup/replay detection

  -- Perplexity's structured response.
  perplexity_response_text  text,                  -- full raw response
  grade                     text        CHECK (grade IN ('A','B','C','D','F','ERROR')),
  issues                    jsonb       DEFAULT '[]'::jsonb,
  recommendations           jsonb       DEFAULT '[]'::jsonb,
  summary                   text,                  -- one-line Perplexity verdict

  -- Token accounting.
  model                     text        DEFAULT 'sonar-pro',
  input_tokens              int,
  output_tokens             int,
  cost_cents                numeric(10,4) DEFAULT 0,

  -- Context.
  project_id                text        DEFAULT 'EOM',
  phase                     text,                  -- e.g. 'G.3', 'MP-1', 'Shop-UNIS-extras'
  trigger_source            text        CHECK (trigger_source IN (
                                           'phase_completion',
                                           'plan_finalization',
                                           'architecture_decision',
                                           'manual'
                                         )),

  -- Loop-exit bookkeeping. Set on the LAST row of a group.
  converged                 boolean     DEFAULT false,
  terminal_reason           text        CHECK (terminal_reason IN (
                                           'passed',         -- grade >= min_acceptable_grade
                                           'max_rounds',     -- cap hit
                                           'cost_ceiling',   -- $ cap hit
                                           'error',          -- Perplexity error
                                           NULL
                                         )),

  instance_id               text,                  -- which titan-harness instance ran it
  created_at                timestamptz NOT NULL DEFAULT now()
);

-- Indexes for common queries.
CREATE INDEX IF NOT EXISTS war_room_group_idx
  ON public.war_room_exchanges (exchange_group_id, round_number);

CREATE INDEX IF NOT EXISTS war_room_project_phase_idx
  ON public.war_room_exchanges (project_id, phase, created_at DESC);

CREATE INDEX IF NOT EXISTS war_room_grade_idx
  ON public.war_room_exchanges (grade)
  WHERE grade IS NOT NULL;

CREATE INDEX IF NOT EXISTS war_room_created_at_idx
  ON public.war_room_exchanges (created_at DESC);

-- Comments for future archaeologists.
COMMENT ON TABLE  public.war_room_exchanges
  IS 'Phase G.3: Titan ↔ Perplexity auto-refinement loop log. One row per round. Groups share exchange_group_id.';
COMMENT ON COLUMN public.war_room_exchanges.exchange_group_id
  IS 'UUID linking all rounds of a single war-room session.';
COMMENT ON COLUMN public.war_room_exchanges.round_number
  IS '1-indexed round within the session. Max enforced by policy.war_room.max_refinement_rounds.';
COMMENT ON COLUMN public.war_room_exchanges.titan_output_hash
  IS 'sha256 of titan_output_text for replay/dedup detection.';
COMMENT ON COLUMN public.war_room_exchanges.terminal_reason
  IS 'Why this group ended. Only populated on the final row of the group.';
