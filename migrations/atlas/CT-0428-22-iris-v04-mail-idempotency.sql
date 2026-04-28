-- =============================================================================
-- CT-0428-22 — Iris v0.4 mail idempotency + install-packet routing tracker
--
-- Adds: iris_mail_log
-- Purpose: kill the iris-mail redelivery loop (active P10 blocker
--          iris_mail_loop_ct-0428-12) by tracking which tasks Iris has
--          already mailed. Subsequent polls SELECT-exclude rows that
--          already appear in iris_mail_log so each operator-class task is
--          delivered exactly ONCE per its lifetime in op_task_queue.
--
-- Also tracks install-packet auto-routing: when Iris detects an objective
-- that wires/installs files into a recipient harness, it queues a sub-
-- task with the verify+test+commit protocol and records the linkage here.
-- =============================================================================
\set ON_ERROR_STOP on
BEGIN;

CREATE TABLE IF NOT EXISTS iris_mail_log (
  task_id                          TEXT PRIMARY KEY,
  recipient                        TEXT NOT NULL,
  mailed_at                        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  install_packet_routed            BOOLEAN NOT NULL DEFAULT false,
  install_packet_followup_task_id  TEXT,
  meta                             JSONB
);

CREATE INDEX IF NOT EXISTS idx_iris_mail_log_recipient_ts
  ON iris_mail_log(recipient, mailed_at DESC);
CREATE INDEX IF NOT EXISTS idx_iris_mail_log_install_packet
  ON iris_mail_log(install_packet_routed, mailed_at DESC)
  WHERE install_packet_routed = true;

ALTER TABLE iris_mail_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS iris_mail_log_service_all ON iris_mail_log;
CREATE POLICY iris_mail_log_service_all ON iris_mail_log
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Backfill: insert one row per task that has a `mail_delivered` decision
-- in op_decisions but no iris_mail_log entry yet. This excludes the 5+
-- currently-looping tasks from the next iris poll cycle.
--
-- Match heuristic: op_decisions rows tagged 'iris-mail' + 'mail_delivered'
-- with a tag of the form 'CT-MMDD-NN' (the task_id) or 'recipient:<name>'.
-- We pull the task_id from the tag and the recipient too.
INSERT INTO iris_mail_log (task_id, recipient, mailed_at, meta)
SELECT
  ct_tag.tag                         AS task_id,
  COALESCE(rcpt_tag.recipient, '?')  AS recipient,
  d.created_at                       AS mailed_at,
  jsonb_build_object('source', 'backfill', 'decision_id', d.id::text)
FROM op_decisions d
CROSS JOIN LATERAL (
  SELECT t AS tag
  FROM unnest(d.tags) AS t
  WHERE t ~ '^CT-[0-9]{4}-[0-9]+'
  LIMIT 1
) ct_tag
LEFT JOIN LATERAL (
  SELECT split_part(t, ':', 2) AS recipient
  FROM unnest(d.tags) AS t
  WHERE t LIKE 'recipient:%'
  LIMIT 1
) rcpt_tag ON true
WHERE d.tags && ARRAY['iris-mail','mail_delivered']
  AND ct_tag.tag IS NOT NULL
ON CONFLICT (task_id) DO NOTHING;

COMMIT;

\echo '== confirmation =='
SELECT count(*) AS iris_mail_log_rows FROM iris_mail_log;
SELECT recipient, count(*) AS mailed_count
FROM iris_mail_log
GROUP BY recipient
ORDER BY mailed_count DESC
LIMIT 10;
