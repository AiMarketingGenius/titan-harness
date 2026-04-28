-- =============================================================================
-- CT-0428-08 — Iris v0.2 + Queue Health Infra DDL
-- Adds: amg_daemon_heartbeats, amg_queue_health, amg_alerts
-- + pg_cron monitor: every 5 min INSERT queue health snapshot + raise alert
--   on tasks queued >10min unclaimed.
-- =============================================================================
\set ON_ERROR_STOP on
BEGIN;

-- amg_daemon_heartbeats — Iris (and other daemons) write a row each poll.
CREATE TABLE IF NOT EXISTS amg_daemon_heartbeats (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  daemon      TEXT NOT NULL,
  host        TEXT,
  pid         INTEGER,
  poll_count  BIGINT DEFAULT 0,
  status      TEXT NOT NULL DEFAULT 'ok',
  meta        JSONB,
  ts          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dh_daemon_ts ON amg_daemon_heartbeats(daemon, ts DESC);
ALTER TABLE amg_daemon_heartbeats ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS amg_daemon_heartbeats_service_all ON amg_daemon_heartbeats;
CREATE POLICY amg_daemon_heartbeats_service_all ON amg_daemon_heartbeats
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- amg_queue_health — pg_cron writes a snapshot every 5 min.
CREATE TABLE IF NOT EXISTS amg_queue_health (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ts                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  queued_pre_approved      INTEGER NOT NULL,
  queued_oldest_age_s      INTEGER,
  active                   INTEGER NOT NULL,
  active_oldest_age_s      INTEGER,
  in_review                INTEGER NOT NULL,
  shipped_today            INTEGER NOT NULL,
  iris_last_heartbeat_age_s INTEGER,
  alert_raised             BOOLEAN NOT NULL DEFAULT false,
  alert_reason             TEXT
);
CREATE INDEX IF NOT EXISTS idx_qh_ts ON amg_queue_health(ts DESC);
ALTER TABLE amg_queue_health ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS amg_queue_health_service_all ON amg_queue_health;
CREATE POLICY amg_queue_health_service_all ON amg_queue_health
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- amg_alerts — generic alert ledger (queue-stale, iris-stale, etc).
CREATE TABLE IF NOT EXISTS amg_alerts (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  alert_type   TEXT NOT NULL,
  severity     TEXT NOT NULL CHECK (severity IN ('P0','P1','P2','INFO')),
  message      TEXT NOT NULL,
  meta         JSONB,
  resolved_at  TIMESTAMPTZ,
  ts           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_alerts_unresolved ON amg_alerts(alert_type, ts DESC) WHERE resolved_at IS NULL;
ALTER TABLE amg_alerts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS amg_alerts_service_all ON amg_alerts;
CREATE POLICY amg_alerts_service_all ON amg_alerts
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Snapshot function — called by pg_cron.
CREATE OR REPLACE FUNCTION atlas_queue_health_snapshot() RETURNS VOID AS $fn$
DECLARE
  q_count INT; q_age INT;
  a_count INT; a_age INT;
  r_count INT; s_count INT;
  iris_age INT;
  raise_alert BOOLEAN := false;
  reason TEXT := NULL;
BEGIN
  SELECT count(*), COALESCE(EXTRACT(EPOCH FROM (NOW() - MIN(created_at)))::INT, 0)
    INTO q_count, q_age
    FROM op_task_queue
    WHERE status IN ('queued','approved') AND approval='pre_approved';

  SELECT count(*), COALESCE(EXTRACT(EPOCH FROM (NOW() - MIN(claimed_at)))::INT, 0)
    INTO a_count, a_age
    FROM op_task_queue
    WHERE status IN ('locked','active');

  SELECT count(*) INTO r_count FROM op_task_queue WHERE status='review';
  SELECT count(*) INTO s_count FROM op_task_queue WHERE status='shipped' AND completed_at::date = CURRENT_DATE;

  SELECT COALESCE(EXTRACT(EPOCH FROM (NOW() - MAX(ts)))::INT, NULL)
    INTO iris_age
    FROM amg_daemon_heartbeats WHERE daemon='iris';

  IF q_age > 600 AND q_count > 0 THEN
    raise_alert := true;
    reason := 'tasks queued >10min unclaimed: count=' || q_count || ' oldest_age=' || q_age || 's';
  ELSIF iris_age IS NOT NULL AND iris_age > 300 THEN
    raise_alert := true;
    reason := 'iris heartbeat stale: age=' || iris_age || 's';
  END IF;

  INSERT INTO amg_queue_health(queued_pre_approved, queued_oldest_age_s, active, active_oldest_age_s, in_review, shipped_today, iris_last_heartbeat_age_s, alert_raised, alert_reason)
  VALUES (q_count, NULLIF(q_age,0), a_count, NULLIF(a_age,0), r_count, s_count, iris_age, raise_alert, reason);

  IF raise_alert THEN
    INSERT INTO amg_alerts(alert_type, severity, message, meta)
    VALUES (
      CASE WHEN reason LIKE 'iris%%' THEN 'iris_stale' ELSE 'queue_stale' END,
      'P1',
      reason,
      jsonb_build_object('q_count', q_count, 'q_age', q_age, 'iris_age', iris_age)
    );
  END IF;
END
$fn$ LANGUAGE plpgsql;

-- pg_cron registration (idempotent).
SELECT cron.unschedule(jobid) FROM cron.job WHERE jobname = 'atlas-queue-health';
SELECT cron.schedule('atlas-queue-health', '*/5 * * * *', $cron$SELECT atlas_queue_health_snapshot();$cron$);

COMMIT;

\echo '== confirmation =='
SELECT
  (SELECT count(*) FROM information_schema.tables WHERE table_name IN ('amg_daemon_heartbeats','amg_queue_health','amg_alerts')) AS new_tables_present,
  (SELECT count(*) FROM cron.job WHERE jobname='atlas-queue-health') AS health_cron;

-- Run snapshot once for an immediate baseline row.
SELECT atlas_queue_health_snapshot();

SELECT ts, queued_pre_approved, queued_oldest_age_s, active, in_review, shipped_today, iris_last_heartbeat_age_s, alert_raised, alert_reason
FROM amg_queue_health ORDER BY ts DESC LIMIT 1;
