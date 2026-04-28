-- =============================================================================
-- DIR-2026-04-28-002a Step 2 — DDL Patches
-- =============================================================================
-- Per v3 §DIR-002a Step 2. Idempotent (IF NOT EXISTS / OR REPLACE).
--
-- Adapted from literal packet for two PostgreSQL-correctness reasons (logged
-- in MCP decision dir_002a_step2_ddl_applied):
--   (1) RLS policy on `class` (packet wrote `FOR UPDATE USING (class = OLD.class)`)
--       does NOT work in PostgreSQL because OLD/NEW are trigger-only, not
--       available in RLS context. Achieve the same immutability via a
--       BEFORE UPDATE trigger that raises an exception when class changes.
--   (2) `op_task_queue` requires priority + objective + acceptance_criteria +
--       queued_by as NOT NULL. Packet's enqueue trigger only supplied 8 cols.
--       Adapted: ALTER op_task_queue ADD class column; trigger supplies all
--       NOT NULL fields with sensible auto-derived values (priority=normal,
--       objective=first 200 chars of directive_md, acceptance_criteria=
--       embedded-in-instructions notice, queued_by='eom-finalize-trigger').
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. eom_judgments — add is_revision + rubric_injected_at_iteration (Grok #8)
--    + class column (P4 polish) with allowlist CHECK
-- ---------------------------------------------------------------------------
ALTER TABLE eom_judgments
  ADD COLUMN IF NOT EXISTS is_revision BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE eom_judgments
  ADD COLUMN IF NOT EXISTS rubric_injected_at_iteration INTEGER NOT NULL DEFAULT 1;

-- Add class column with allowlist + default. Backfill from directive_class
-- happens in next statement so historical rows reflect their original class.
ALTER TABLE eom_judgments
  ADD COLUMN IF NOT EXISTS class TEXT NOT NULL DEFAULT 'CLASS_A';

-- Idempotent CHECK constraint (drop-add pattern to avoid duplicate errors).
ALTER TABLE eom_judgments
  DROP CONSTRAINT IF EXISTS eom_judgments_class_check;
ALTER TABLE eom_judgments
  ADD CONSTRAINT eom_judgments_class_check
  CHECK (class IN ('CLASS_A', 'CLASS_B', 'CLASS_C'));

-- Backfill class from directive_class for any row where they diverge
-- (newly-added class column on existing rows defaults to CLASS_A regardless
-- of original directive_class).
UPDATE eom_judgments SET class = directive_class WHERE class IS DISTINCT FROM directive_class;

-- ---------------------------------------------------------------------------
-- 2. eom_judgments — BEFORE INSERT trigger: copy directive_class to class
--    so future submits don't have to know about the new column.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION eom_judgments_set_class_on_insert() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.class IS NULL OR NEW.class = 'CLASS_A' THEN
    NEW.class := NEW.directive_class;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_eom_judgments_set_class ON eom_judgments;
CREATE TRIGGER trg_eom_judgments_set_class
  BEFORE INSERT ON eom_judgments
  FOR EACH ROW EXECUTE FUNCTION eom_judgments_set_class_on_insert();

-- ---------------------------------------------------------------------------
-- 3. eom_judgments — BEFORE UPDATE trigger: enforce class immutability
--    (replaces packet's invalid RLS policy approach).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION eom_judgments_class_immutable() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.class IS DISTINCT FROM OLD.class THEN
    RAISE EXCEPTION 'eom_judgments.class is immutable post-insert (attempted change from % to %)',
      OLD.class, NEW.class
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_eom_judgments_class_immutable ON eom_judgments;
CREATE TRIGGER trg_eom_judgments_class_immutable
  BEFORE UPDATE ON eom_judgments
  FOR EACH ROW EXECUTE FUNCTION eom_judgments_class_immutable();

-- ---------------------------------------------------------------------------
-- 4. op_task_queue — add class column so trigger can propagate
-- ---------------------------------------------------------------------------
ALTER TABLE op_task_queue
  ADD COLUMN IF NOT EXISTS class TEXT;

-- Optional: also constrain class on op_task_queue to the same allowlist
-- (NULL allowed for legacy rows).
ALTER TABLE op_task_queue
  DROP CONSTRAINT IF EXISTS op_task_queue_class_check;
ALTER TABLE op_task_queue
  ADD CONSTRAINT op_task_queue_class_check
  CHECK (class IS NULL OR class IN ('CLASS_A', 'CLASS_B', 'CLASS_C'));

-- ---------------------------------------------------------------------------
-- 5. enqueue_task_on_finalize — server-side trigger
--    (Perplexity correction #5; adapted to supply all NOT NULL columns)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION enqueue_task_on_finalize() RETURNS TRIGGER AS $$
DECLARE
  derived_assignee TEXT;
  derived_objective TEXT;
BEGIN
  -- Only fire on transition into 'approved' status
  IF NEW.status = 'approved' AND OLD.status IS DISTINCT FROM 'approved' THEN
    derived_assignee := CASE
      WHEN NEW.directive_md ILIKE '%## TITAN_PORTION%' THEN 'titan'
      WHEN NEW.directive_md ILIKE '%## ACHILLES_PORTION%' THEN 'achilles'
      ELSE 'manual'
    END;

    -- Derive a non-empty objective from first 200 chars of directive_md (NOT NULL).
    derived_objective := COALESCE(
      NULLIF(TRIM(SUBSTRING(NEW.directive_md FROM 1 FOR 200)), ''),
      'Auto-enqueued from approved judgment ' || NEW.id::text
    );

    -- status='approved' (NOT 'pending'): op_task_queue.status CHECK allowlist
    -- does not permit 'pending'; existing pre_approved auto-enqueued tasks
    -- enter at status='approved' so executors can claim immediately.
    INSERT INTO op_task_queue (
      task_id,
      priority,
      objective,
      instructions,
      acceptance_criteria,
      assigned_to,
      status,
      approval,
      tags,
      class,
      queued_by,
      created_at
    ) VALUES (
      'CT-' || to_char(NOW(), 'MMDD') || '-' || substr(NEW.id::text, 1, 8),
      'normal',
      derived_objective,
      NEW.directive_md,
      'See full directive embedded in instructions; acceptance criteria are listed inline per v3 dispatch packet contract.',
      derived_assignee,
      'approved',
      'pre_approved',
      ARRAY['judgment_id:' || NEW.id::text, 'final_directive_sha:' || COALESCE(NEW.final_directive_sha, ''), 'auto_enqueued_finalize'],
      NEW.class,
      'eom-finalize-trigger',
      NOW()
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enqueue_on_finalize ON eom_judgments;
CREATE TRIGGER trg_enqueue_on_finalize
  AFTER UPDATE ON eom_judgments
  FOR EACH ROW EXECUTE FUNCTION enqueue_task_on_finalize();

-- ---------------------------------------------------------------------------
-- 6. tier2_cost_ledger — Grok correction #2
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tier2_cost_ledger (
  month                  TEXT PRIMARY KEY,
  deepseek_flash_calls   INTEGER NOT NULL DEFAULT 0,
  deepseek_flash_usd     NUMERIC(10,4) NOT NULL DEFAULT 0,
  deepseek_pro_calls     INTEGER NOT NULL DEFAULT 0,
  deepseek_pro_usd       NUMERIC(10,4) NOT NULL DEFAULT 0,
  qwen_local_calls       INTEGER NOT NULL DEFAULT 0,
  qwen_local_usd         NUMERIC(10,4) NOT NULL DEFAULT 0,
  total_usd              NUMERIC(10,4) GENERATED ALWAYS AS (deepseek_flash_usd + deepseek_pro_usd) STORED,
  last_updated           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMIT;

-- =============================================================================
-- Verification (run after the migration)
-- =============================================================================
-- \d eom_judgments  -- expect is_revision, rubric_injected_at_iteration, class
-- \d op_task_queue  -- expect class column
-- \d tier2_cost_ledger
-- SELECT trigger_name FROM information_schema.triggers
--   WHERE event_object_table IN ('eom_judgments', 'op_task_queue');
