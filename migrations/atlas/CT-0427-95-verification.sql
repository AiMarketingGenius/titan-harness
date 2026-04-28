-- =============================================================================
-- CT-0427-95 §15 — Verification Negative Tests (separate transaction).
-- These INSERTs/UPDATEs MUST raise exceptions. Each block is wrapped in its
-- own savepoint+rollback so a successful negative test doesn't poison subsequent.
-- =============================================================================
\set ON_ERROR_STOP off

-- §15a. amg_reviews self-review must raise (no_self_review trigger + CHECK).
\echo
\echo '== Negative test 15a: amg_reviews reviewer=builder =='
SAVEPOINT s15a;
INSERT INTO amg_reviews (task_id, builder_agent, reviewer_agent, verdict)
VALUES ('CT-0427-95-NEGATIVE-TEST-15A', 'hercules', 'hercules', 'PASS');
\echo '!! UNEXPECTED — self-review insert SHOULD have raised but did not'
ROLLBACK TO SAVEPOINT s15a;
RELEASE SAVEPOINT s15a;

-- §15b. status='shipped' from non-gatekeeper role must raise.
-- We can't easily SET ROLE inside a session that already has elevated grants,
-- so we simulate by attempting the UPDATE while pretending to be a builder.
-- The trigger checks current_user; current_user from the pooler will be 'postgres'
-- which IS in the allow list — so we instead test the trigger by directly raising
-- via a SET ROLE achilles_gatekeeper followed by SET ROLE NONE.
\echo
\echo '== Negative test 15b: simulated non-gatekeeper status=shipped =='
-- First confirm the trigger IS installed.
SELECT tgname, tgenabled, pg_get_triggerdef(oid)
FROM pg_trigger
WHERE tgrelid = 'op_task_queue'::regclass AND tgname = 'shipped_gate_trigger';

-- Then exercise it by attempting role-switched update. We create a temp probe role.
SAVEPOINT s15b;
DO $probe$
DECLARE
  err_msg TEXT;
  err_code TEXT;
BEGIN
  -- Create a temp role that is NOT achilles_gatekeeper.
  EXECUTE 'CREATE ROLE atlas_probe_builder_15b NOLOGIN';
  EXECUTE 'GRANT USAGE ON SCHEMA public TO atlas_probe_builder_15b';
  EXECUTE 'GRANT SELECT, UPDATE ON op_task_queue TO atlas_probe_builder_15b';

  BEGIN
    EXECUTE 'SET LOCAL ROLE atlas_probe_builder_15b';
    UPDATE op_task_queue SET status = 'shipped'
    WHERE task_id = 'CT-0427-95';
    EXECUTE 'SET LOCAL ROLE NONE';
    RAISE NOTICE '!! UNEXPECTED — non-gatekeeper status=shipped SUCCEEDED';
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS
      err_msg = MESSAGE_TEXT,
      err_code = RETURNED_SQLSTATE;
    RAISE NOTICE 'GOOD — shipped_gate_trigger raised: SQLSTATE=% MESSAGE=%', err_code, err_msg;
  END;

  -- Cleanup
  EXECUTE 'SET LOCAL ROLE NONE';
  EXECUTE 'REVOKE ALL ON SCHEMA public FROM atlas_probe_builder_15b';
  EXECUTE 'REVOKE ALL ON op_task_queue FROM atlas_probe_builder_15b';
  EXECUTE 'DROP ROLE atlas_probe_builder_15b';
END
$probe$;
ROLLBACK TO SAVEPOINT s15b;
RELEASE SAVEPOINT s15b;

-- §15c. graduation_trigger smoke — increment counter to threshold and confirm level bumps.
\echo
\echo '== Verification 15c: graduation_trigger promotes level on threshold =='
SAVEPOINT s15c;
UPDATE amg_graduation_counters SET consecutive_clean = 5 WHERE agent = 'hercules';
SELECT agent, level, consecutive_clean, graduated_at IS NOT NULL AS graduated
FROM amg_graduation_counters WHERE agent = 'hercules';
ROLLBACK TO SAVEPOINT s15c;
RELEASE SAVEPOINT s15c;

\echo
\echo '== Final state spot-check =='
SELECT
  (SELECT count(*) FROM amg_agent_budget_config WHERE agent IN ('codex','hercules','nestor','alexander','kimi_code','kimi_claw','amg_eom')) AS budget_rows,
  (SELECT count(*) FROM amg_graduation_counters)                                                                                              AS grad_rows,
  (SELECT count(*) FROM cron.job WHERE jobname='atlas-reaper')                                                                                AS reaper_jobs,
  (SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='achilles_gatekeeper'))                                                                 AS gatekeeper_role,
  (SELECT count(*) FROM amg_shell_logs WHERE task_id='CT-0427-95')                                                                            AS shell_logs_for_ct95;
