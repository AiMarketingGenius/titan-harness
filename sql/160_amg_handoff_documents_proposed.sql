-- CT-0428-09 proposed DDL only.
-- Do not apply to production without explicit schema approval.
-- Purpose: persist Option B shift-rotation handoffs as a strict seven-field
-- JSON document plus searchable metadata.

CREATE OR REPLACE FUNCTION public.amg_jsonb_exact_keys(
    doc jsonb,
    required_keys text[]
)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
STRICT
AS $$
    SELECT
        jsonb_typeof(doc) = 'object'
        AND NOT EXISTS (
            SELECT 1
            FROM unnest(required_keys) AS key_name
            WHERE NOT (doc ? key_name)
        )
        AND NOT EXISTS (
            SELECT 1
            FROM jsonb_object_keys(doc) AS key_name
            WHERE NOT (key_name = ANY(required_keys))
        );
$$;

CREATE TABLE IF NOT EXISTS public.amg_handoff_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id text NOT NULL,
    outgoing_agent text NOT NULL,
    incoming_agent text,
    rotation_reason text NOT NULL CHECK (
        rotation_reason IN (
            'context-fill-60%',
            'wall-clock-45min',
            'quality-decline'
        )
    ),
    context_usage jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (
        jsonb_typeof(context_usage) = 'object'
    ),
    handoff_document jsonb NOT NULL CHECK (
        public.amg_jsonb_exact_keys(
            handoff_document,
            ARRAY[
                'task_goal',
                'completed_phases',
                'in_progress_phase',
                'key_decisions_made',
                'open_questions_blockers',
                'artifact_pointers',
                'do_not'
            ]
        )
        AND jsonb_typeof(handoff_document->'task_goal') = 'string'
        AND jsonb_typeof(handoff_document->'completed_phases') = 'array'
        AND jsonb_typeof(handoff_document->'in_progress_phase') = 'object'
        AND jsonb_typeof(handoff_document->'key_decisions_made') = 'array'
        AND jsonb_typeof(handoff_document->'open_questions_blockers') = 'array'
        AND jsonb_typeof(handoff_document->'artifact_pointers') = 'array'
        AND jsonb_typeof(handoff_document->'do_not') = 'array'
    ),
    source_decision_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    read_at timestamptz,
    read_by_agent text,
    superseded_at timestamptz
);

CREATE INDEX IF NOT EXISTS amg_handoff_documents_task_id_idx
    ON public.amg_handoff_documents (task_id);

CREATE INDEX IF NOT EXISTS amg_handoff_documents_active_idx
    ON public.amg_handoff_documents (created_at DESC)
    WHERE superseded_at IS NULL;

COMMENT ON TABLE public.amg_handoff_documents IS
    'Proposed CT-0428-09 table for Option B shift-rotation handoff documents.';

COMMENT ON COLUMN public.amg_handoff_documents.handoff_document IS
    'Strict seven-field JSON: task_goal, completed_phases, in_progress_phase, key_decisions_made, open_questions_blockers, artifact_pointers, do_not.';
