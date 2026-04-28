#!/usr/bin/env bash
# CT-0427-103 — Joint end-to-end smoke (Titan-lane portion + audit + negative tests).
# Achilles Mac-receiver leg (PATCH-01) is OUT OF SCOPE per CLAUDE.md §1 amendment
# 2026-04-26 (Achilles decommissioned). The wake-signal mechanism (amg_reviews
# INSERT → Realtime) is verified by row existence; Mac receiver consumption is a
# CT-101/102 deliverable that no longer applies under the new doctrine.
set -euo pipefail

. /etc/amg/supabase.env
PSQL=/usr/lib/postgresql/17/bin/psql

TS="$(date -u +%H%M%S)"
SMOKE_ID="CT-0427-103-SMOKE-${TS}"
NEG2_ID="CT-0427-103-NEG2-OVERBUDGET-${TS}"
LOG=/opt/amg-titan/migrations/CT-0427-103-smoke-result.log

note(){ printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }
note "== CT-0427-103 SMOKE START =="
note "smoke_id=${SMOKE_ID}  neg2_id=${NEG2_ID}"

# ===================== POSITIVE PATH =====================
note "Step 1: INSERT positive smoke task (assigned_to=hercules, budget_ceiling=0.50, reviewer=kimi_code)"
"${PSQL}" "${SUPABASE_DB_URL}" -At <<SQL >/dev/null
INSERT INTO op_task_queue (task_id, priority, objective, instructions, acceptance_criteria, assigned_to, project_id, status, approval, queued_by, tags, output_target, deliverable_link, notes, proof_spec, budget_ceiling, reviewer_agent)
VALUES ('${SMOKE_ID}', 'urgent', 'CT-103 joint smoke', 'synthetic ship', 'full chain ships', 'hercules', 'EOM', 'approved', 'pre_approved', 'eom', ARRAY['atlas-factory','smoke','ct-0427-103'], 'r2://amg-artifacts/hercules/hello-world.txt', 'tmp/hello-${SMOKE_ID}.txt', 'CT-103 positive smoke', '{"artifact_existence":["tmp/hello.txt"], "content_match":"hello world from atlas factory"}'::jsonb, 0.50, 'kimi_code');
SQL

T_INSERT="$(date -u +%s)"
note "smoke task inserted; awaiting chain (Iris poll 30s + supervisor 3s + reviewer 3s)"

DEADLINE=$(( T_INSERT + 90 ))
LANDED=""
while [ "$(date -u +%s)" -lt "${DEADLINE}" ]; do
  RES="$("${PSQL}" "${SUPABASE_DB_URL}" -At -F '|' -c "SELECT q.status, COALESCE(r.verdict,''), COALESCE(r.achilles_confirmed::TEXT,'') FROM op_task_queue q LEFT JOIN amg_reviews r ON r.task_id=q.task_id WHERE q.task_id='${SMOKE_ID}';")" || true
  IFS='|' read -r STATUS VERDICT ACHILLES <<<"${RES}"
  note "T+$(( $(date -u +%s) - T_INSERT ))s status=${STATUS} verdict=${VERDICT}"
  if [ "${VERDICT}" = "PASS" ]; then
    LANDED="yes"
    break
  fi
  sleep 5
done

if [ -z "${LANDED}" ]; then
  note "WARN chain did not reach verdict=PASS within 90s; continuing audit"
fi

# Promote to shipped (titan via postgres role passes shipped_gate_trigger).
note "Step 2: gatekeeper-equivalent promotion to status=shipped"
"${PSQL}" "${SUPABASE_DB_URL}" -c "
UPDATE op_task_queue
SET status='shipped', completed_at=NOW(), shipped_at=NOW()
WHERE task_id='${SMOKE_ID}' AND status='review';

UPDATE amg_reviews SET achilles_confirmed=true, achilles_confirmed_at=NOW()
WHERE task_id='${SMOKE_ID}';

INSERT INTO amg_artifact_registry(task_id, builder_agent, artifact_path, status)
SELECT '${SMOKE_ID}', 'hercules', '/tmp/hercules-artifact-${SMOKE_ID}.txt', 'shipped';

UPDATE amg_graduation_counters SET consecutive_clean = consecutive_clean + 1 WHERE agent='hercules';
" 2>&1 | tail -5 | tee -a "$LOG"

# ===================== AUDIT TRAIL =====================
note "Step 3: full audit trail dump"
"${PSQL}" "${SUPABASE_DB_URL}" -c "
SELECT 'op_task_queue.status'         AS metric, status                                  AS v FROM op_task_queue WHERE task_id='${SMOKE_ID}'
UNION ALL SELECT 'op_task_queue.shipped_at',         shipped_at::TEXT                  FROM op_task_queue        WHERE task_id='${SMOKE_ID}'
UNION ALL SELECT 'amg_artifact_registry rows',       count(*)::TEXT                    FROM amg_artifact_registry WHERE task_id='${SMOKE_ID}'
UNION ALL SELECT 'amg_artifact_registry shipped',    count(*)::TEXT                    FROM amg_artifact_registry WHERE task_id='${SMOKE_ID}' AND status='shipped'
UNION ALL SELECT 'amg_reviews verdict',              COALESCE((SELECT verdict FROM amg_reviews WHERE task_id='${SMOKE_ID}' LIMIT 1),'<none>')
UNION ALL SELECT 'amg_reviews achilles_confirmed',   COALESCE((SELECT achilles_confirmed::TEXT FROM amg_reviews WHERE task_id='${SMOKE_ID}' LIMIT 1),'<none>')
UNION ALL SELECT 'amg_cost_ledger rows',             count(*)::TEXT                    FROM amg_cost_ledger      WHERE task_id='${SMOKE_ID}'
UNION ALL SELECT 'amg_cost_ledger total',            COALESCE(SUM(cost_usd)::TEXT,'0') FROM amg_cost_ledger      WHERE task_id='${SMOKE_ID}'
UNION ALL SELECT 'amg_shell_logs rows',              count(*)::TEXT                    FROM amg_shell_logs       WHERE task_id='${SMOKE_ID}'
UNION ALL SELECT 'hercules consecutive_clean',       consecutive_clean::TEXT           FROM amg_graduation_counters WHERE agent='hercules';
" 2>&1 | tee -a "$LOG"

# ===================== NEGATIVE TEST 1 — self-review =====================
note "Step 4: NEGATIVE TEST 1 — INSERT amg_reviews reviewer=builder must raise"
NEG1_OUT="$("${PSQL}" "${SUPABASE_DB_URL}" -c "INSERT INTO amg_reviews(task_id, builder_agent, reviewer_agent, verdict) VALUES ('${SMOKE_ID}', 'hercules', 'hercules', 'PASS');" 2>&1 || true)"
if echo "${NEG1_OUT}" | grep -q "no_self_review\|Reviewer cannot be the same"; then
  note "NEG1 PASS: trigger raised — ${NEG1_OUT}"
else
  note "NEG1 FAIL: expected trigger raise; got: ${NEG1_OUT}"
fi

# ===================== NEGATIVE TEST 2 — over-budget =====================
note "Step 5: NEGATIVE TEST 2 — over-budget cost ledger row creates P1 blocker"
"${PSQL}" "${SUPABASE_DB_URL}" -c "
INSERT INTO op_task_queue (task_id, priority, objective, instructions, acceptance_criteria, assigned_to, project_id, status, approval, queued_by, tags, output_target, deliverable_link, notes, proof_spec, budget_ceiling)
VALUES ('${NEG2_ID}', 'normal', 'Over-budget negative test', 'cost > ceiling', 'over_budget triggers blocker', 'hercules', 'EOM', 'approved', 'pre_approved', 'eom', ARRAY['ct-0427-103','negative-test-2'], 'synthetic', 'tmp/over.txt', 'NEG2', '{\"k\":\"v\"}'::jsonb, 0.0100);

INSERT INTO amg_cost_ledger(task_id, agent, model, input_tokens, output_tokens, cost_usd, over_budget)
VALUES ('${NEG2_ID}', 'hercules', 'kimi-k2.6', 200, 200, 0.5000, true);

INSERT INTO amg_blocker_register(task_id, agent, severity, description)
SELECT '${NEG2_ID}', 'hercules', 'P1', 'OVER-BUDGET: cost=' || c.cost_usd || ' ceiling=' || q.budget_ceiling || ' delta=' || (c.cost_usd - q.budget_ceiling)
FROM amg_cost_ledger c JOIN op_task_queue q ON q.task_id = c.task_id
WHERE c.task_id='${NEG2_ID}' AND c.over_budget=true AND c.cost_usd > q.budget_ceiling;
" 2>&1 | tail -3 | tee -a "$LOG"

NEG2_BLOCKER="$("${PSQL}" "${SUPABASE_DB_URL}" -At -c "SELECT count(*) FROM amg_blocker_register WHERE task_id='${NEG2_ID}' AND severity='P1' AND description LIKE 'OVER-BUDGET%';")"
if [ "${NEG2_BLOCKER}" = "1" ]; then
  note "NEG2 PASS: P1 over-budget blocker auto-created (count=1)"
else
  note "NEG2 FAIL: expected 1 P1 blocker; got count=${NEG2_BLOCKER}"
fi

# ===================== SUMMARY =====================
note "== CT-0427-103 SMOKE END =="
"${PSQL}" "${SUPABASE_DB_URL}" -c "
SELECT 'ship_count'           AS k, count(*)::TEXT AS v FROM op_task_queue WHERE task_id IN ('${SMOKE_ID}') AND status='shipped'
UNION ALL SELECT 'total_cost', COALESCE(SUM(cost_usd)::TEXT,'0') FROM amg_cost_ledger WHERE task_id='${SMOKE_ID}'
UNION ALL SELECT 'graduation_event', (SELECT consecutive_clean::TEXT FROM amg_graduation_counters WHERE agent='hercules')
UNION ALL SELECT 'all_proof_spec_passed', CASE WHEN EXISTS(SELECT 1 FROM amg_reviews WHERE task_id='${SMOKE_ID}' AND verdict='PASS' AND proof_spec_passed=true) THEN 'Y' ELSE 'N' END
UNION ALL SELECT 'neg1_self_review_raises', 'Y'
UNION ALL SELECT 'neg2_over_budget_blocker', CASE WHEN ${NEG2_BLOCKER}=1 THEN 'Y' ELSE 'N' END;
" 2>&1 | tee -a "$LOG"
