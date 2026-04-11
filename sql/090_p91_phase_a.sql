-- P9.1 Phase A — preparation SQL
-- Idempotent: safe to re-run.

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS cutover_lane text;
CREATE INDEX IF NOT EXISTS tasks_cutover_lane_idx ON tasks(cutover_lane) WHERE cutover_lane IS NOT NULL;

-- RPC claim_one: race-safe claim via SELECT FOR UPDATE SKIP LOCKED.
-- Returns the claimed row as JSON, or NULL if no matching task is available.
-- worker_filter values:
--   '__any__'   -> any pending task (unfiltered catch-all, used by blue systemd)
--   '__dark__'  -> match nothing (dark-mode workers emit heartbeats but claim nothing)
--   any other   -> LIKE '%<filter>%' match against task_type (simplified for P9.1)
CREATE OR REPLACE FUNCTION claim_one(
    p_instance_id text,
    p_worker_filter text DEFAULT '__any__'
)
RETURNS tasks
LANGUAGE plpgsql
AS $$
DECLARE
    claimed_row tasks;
BEGIN
    IF p_worker_filter = '__dark__' THEN
        RETURN NULL;
    END IF;

    SELECT * INTO claimed_row
    FROM tasks
    WHERE status = 'pending'
      AND claimed_by IS NULL
      AND (
          p_worker_filter = '__any__'
          OR task_type = ANY(string_to_array(p_worker_filter, ','))
      )
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;

    IF claimed_row.id IS NULL THEN
        RETURN NULL;
    END IF;

    UPDATE tasks
    SET status = 'in_progress',
        claimed_by = p_instance_id,
        cutover_lane = CASE
            WHEN p_instance_id LIKE 'titan-worker-%' THEN 'green'
            WHEN p_instance_id LIKE 'titan-py-%' THEN 'blue'
            ELSE cutover_lane
        END,
        updated_at = now()
    WHERE id = claimed_row.id
    RETURNING * INTO claimed_row;

    RETURN claimed_row;
END;
$$;

-- Grant execute to service_role (authenticated Supabase clients)
GRANT EXECUTE ON FUNCTION claim_one(text, text) TO service_role;
