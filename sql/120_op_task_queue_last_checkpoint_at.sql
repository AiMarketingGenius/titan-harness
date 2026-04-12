-- sql/120_op_task_queue_last_checkpoint_at.sql
-- TITAN — BINDING DOCTRINE v2.0 Part 4.1
-- Adds the last_checkpoint_at column used by CT-0406-03 auto-wake watchdog.
--
-- Rules (doctrine Part 4.1):
--   - Every update_task call MUST set last_checkpoint_at = NOW()
--   - Every CHECKPOINT REPORT MUST include this update
--   - If last_checkpoint_at is NULL and created_at < NOW() - INTERVAL '15 minutes'
--     the watchdog treats the row as stalled.
--
-- Safe to re-run: uses IF NOT EXISTS.

ALTER TABLE op_task_queue
  ADD COLUMN IF NOT EXISTS last_checkpoint_at TIMESTAMPTZ;

COMMENT ON COLUMN op_task_queue.last_checkpoint_at IS
  'Updated by every checkpoint report. Null = never checkpointed. '
  'CT-0406-03 treats null + created_at > 15min as stalled.';

-- Helper RPC used by scripts/ct_0406_03_watchdog.py to fetch stalled rows in one
-- call. Uses security invoker; caller supplies the service-role key.
CREATE OR REPLACE FUNCTION public.get_stalled_tasks(cutoff TIMESTAMPTZ)
RETURNS TABLE (
  id UUID,
  task_id TEXT,
  status TEXT,
  assigned_to TEXT,
  objective TEXT,
  created_at TIMESTAMPTZ,
  last_checkpoint_at TIMESTAMPTZ
)
LANGUAGE SQL
SECURITY INVOKER
STABLE
AS $$
  SELECT
    t.id,
    t.task_id,
    t.status,
    t.assigned_to,
    t.objective,
    t.created_at,
    t.last_checkpoint_at
  FROM op_task_queue t
  WHERE t.status = 'in_progress'
    AND COALESCE(t.last_checkpoint_at, t.created_at) < cutoff
  ORDER BY COALESCE(t.last_checkpoint_at, t.created_at) ASC;
$$;

COMMENT ON FUNCTION public.get_stalled_tasks(TIMESTAMPTZ) IS
  'CT-0406-03 watchdog helper. Returns in-progress tasks whose last checkpoint '
  '(or created_at if never checkpointed) is older than the supplied cutoff.';
