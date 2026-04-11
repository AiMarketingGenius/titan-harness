-- titan-harness/sql/004_mp_runs.sql
-- Purpose: Phase G.4 — log every invocation of an MP (megaprompt) phase
-- across MP-1 (harvest) and MP-2 (synthesis), with war-room grade FK
-- and per-project tenancy so the same table can serve AMG and any
-- future Titan-as-COO client.
--
-- Design principles:
--   * Multi-tenant from day 1: project_id is NOT NULL and indexed.
--   * Replay-friendly: re-running the same phase creates a new row; the
--     previous row stays for audit. Idempotency is enforced at the script
--     layer, not via DB uniqueness.
--   * War-room linkage: war_room_group_id is a plain uuid (not a hard FK)
--     so war_room_exchanges can be truncated without breaking this table.
--   * Checkpoint snapshot: checkpoint_snapshot_jsonb captures the pre-run
--     state of the MP-1 checkpoint file so we can always answer "what did
--     the world look like when this run started?"
--
-- Run once in Supabase SQL Editor. Safe to re-run (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS public.mp_runs (
  id                       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Tenancy + phase identity
  project_id               text        NOT NULL DEFAULT 'EOM',
  megaprompt               text        NOT NULL CHECK (megaprompt IN ('mp1','mp2','mp1-5','mp2-x')),  -- room to grow
  phase_number             int         NOT NULL CHECK (phase_number >= 0),
  phase_name               text        NOT NULL,                -- e.g. 'fireflies_harvest', 'corpus_audit'

  -- Linkage to the broader operator task queue
  task_id                  text,                                -- CT-MMDD-NN if claimed from tasks queue
  parent_run_id            uuid        REFERENCES public.mp_runs(id) ON DELETE SET NULL,

  -- Execution state machine
  status                   text        NOT NULL DEFAULT 'pending'
                                       CHECK (status IN ('pending','running','complete','failed','blocked','skipped')),
  blocker_reason           text,                                -- populated when status='blocked'

  -- Timing
  started_at               timestamptz NOT NULL DEFAULT now(),
  completed_at             timestamptz,
  duration_ms              int,

  -- Runtime identity
  instance_id              text,                                -- hostname of the runner that executed this
  script_path              text,                                -- absolute path to the phase script that ran
  exit_code                int,

  -- Artifact accounting
  artifacts_count          int         DEFAULT 0,
  high_quality_count       int         DEFAULT 0,
  medium_quality_count     int         DEFAULT 0,
  low_quality_count        int         DEFAULT 0,
  bytes                    bigint      DEFAULT 0,
  words                    int         DEFAULT 0,
  output_paths             jsonb       DEFAULT '[]'::jsonb,     -- list of files/dirs created or updated

  -- Cost accounting
  api_spend_cents          numeric(12,4) DEFAULT 0,
  spend_budget_cents       numeric(12,4),                       -- hard cap at run start (from policy)

  -- War-room linkage (planning outputs only)
  war_room_triggered       boolean     DEFAULT false,
  war_room_group_id        uuid,                                -- links to public.war_room_exchanges.exchange_group_id
  war_room_grade           text        CHECK (war_room_grade IN ('A','B','C','D','F','ERROR') OR war_room_grade IS NULL),
  war_room_cost_cents      numeric(10,4) DEFAULT 0,

  -- Checkpoint + arbitrary metadata
  checkpoint_snapshot_jsonb jsonb,                              -- snapshot of .checkpoint_mp1.json or equivalent at run start
  stdout_tail              text,                                -- last 4kb of stdout for quick debugging
  stderr_tail              text,                                -- last 4kb of stderr
  notes                    text,

  -- Housekeeping
  created_at               timestamptz NOT NULL DEFAULT now(),
  updated_at               timestamptz NOT NULL DEFAULT now()
);

-- Indexes for common queries.
-- Project + mp + phase: "show me mp2 phase 1 runs for EOM"
CREATE INDEX IF NOT EXISTS mp_runs_project_mp_phase_idx
  ON public.mp_runs (project_id, megaprompt, phase_number, created_at DESC);

-- Status filter: "find running or blocked phases"
CREATE INDEX IF NOT EXISTS mp_runs_status_idx
  ON public.mp_runs (status)
  WHERE status IN ('running','pending','blocked','failed');

-- War-room FK lookups: "which runs produced war-roomed outputs"
CREATE INDEX IF NOT EXISTS mp_runs_war_room_group_idx
  ON public.mp_runs (war_room_group_id)
  WHERE war_room_group_id IS NOT NULL;

-- Time-series for dashboards
CREATE INDEX IF NOT EXISTS mp_runs_created_at_idx
  ON public.mp_runs (created_at DESC);

-- updated_at trigger
CREATE OR REPLACE FUNCTION public.mp_runs_set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS mp_runs_updated_at ON public.mp_runs;
CREATE TRIGGER mp_runs_updated_at
  BEFORE UPDATE ON public.mp_runs
  FOR EACH ROW EXECUTE FUNCTION public.mp_runs_set_updated_at();

-- Comments for future archaeologists (and future clients).
COMMENT ON TABLE  public.mp_runs
  IS 'Phase G.4: Per-project log of every MP (megaprompt) phase execution. Multi-tenant by project_id. Links planning outputs to war_room_exchanges via war_room_group_id.';
COMMENT ON COLUMN public.mp_runs.megaprompt
  IS 'Megaprompt family. Currently mp1 (harvest) and mp2 (synthesis). Future clients may add mp3+ pipelines — the CHECK constraint should be extended, not the column.';
COMMENT ON COLUMN public.mp_runs.checkpoint_snapshot_jsonb
  IS 'Point-in-time snapshot of the checkpoint file (.checkpoint_mp1.json or equivalent) at the moment this run started. Useful for replaying against the same world-state.';
COMMENT ON COLUMN public.mp_runs.war_room_group_id
  IS 'Links to public.war_room_exchanges.exchange_group_id when war_room_triggered=true. Not a hard FK so war_room_exchanges can be truncated without breaking mp_runs.';
