-- P-IDEAPIPE: schema + constraint extensions for the IDEA→DR→PLAN→EXECUTE primitive.
-- Safe to re-run (all DDL is IF NOT EXISTS or idempotent ALTER).

-- 1) Extend mp_runs.megaprompt allowed values to include 'idea_to_exec'
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'mp_runs_megaprompt_check') THEN
    ALTER TABLE mp_runs DROP CONSTRAINT mp_runs_megaprompt_check;
  END IF;
  ALTER TABLE mp_runs ADD CONSTRAINT mp_runs_megaprompt_check
    CHECK (megaprompt = ANY (ARRAY['mp1','mp2','mp1-5','mp2-x','mp_perf','idea_to_exec']));
END $$;

-- 2) Per-idea dedupe / idempotency: stable hash column on tasks used by the orchestrator
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS idempotency_key text;
CREATE UNIQUE INDEX IF NOT EXISTS tasks_idempotency_key_uidx
  ON tasks(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- 3) Orchestrator state: idea_to_exec_runs audit table (one row per end-to-end run)
CREATE TABLE IF NOT EXISTS idea_to_exec_runs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  idempotency_key text NOT NULL,
  idea_id         uuid,
  source          text NOT NULL,             -- ideas | session_next_task | lock_it | manual
  task_id         uuid,                      -- FK-like ref to tasks.id for the dr_plan row
  project_id      text,
  title           text,
  slug            text,
  plan_path       text,                      -- plans/PLAN_<date>_<slug>.md
  phase_count     int,
  phases_complete int DEFAULT 0,
  phases_failed   int DEFAULT 0,
  status          text NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','dr_running','dr_complete',
                                    'prompt_grading','executing','complete',
                                    'needs_solon_override','failed','deferred')),
  started_at      timestamptz DEFAULT now(),
  completed_at    timestamptz,
  notes           text,
  war_room_group_id uuid,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idea_to_exec_runs_key_uidx ON idea_to_exec_runs(idempotency_key);
CREATE INDEX IF NOT EXISTS idea_to_exec_runs_status_idx ON idea_to_exec_runs(status);
CREATE INDEX IF NOT EXISTS idea_to_exec_runs_started_idx ON idea_to_exec_runs(started_at DESC);

-- 4) Per-phase artifacts pointer (optional convenience for quick pulls)
CREATE TABLE IF NOT EXISTS idea_to_exec_phase_artifacts (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id       uuid REFERENCES idea_to_exec_runs(id) ON DELETE CASCADE,
  phase_number int NOT NULL,
  phase_name   text,
  prompt_path  text,
  spec_path    text,
  mp_runs_id   uuid,
  grade        text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (run_id, phase_number)
);
