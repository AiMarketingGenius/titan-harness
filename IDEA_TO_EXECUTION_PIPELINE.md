# IDEA → DR → PLAN → EXECUTE Pipeline

**Status:** ACTIVE and NON-BYPASSABLE for any new major project (AMG core or client "Titan-as-COO" deployments).
**Date:** 2026-04-11
**Owner:** Titan (autonomous).
**Contracts inherited:** Capacity CORE CONTRACT, Blaze-Mode Conversation Contract, A-grade war-room floor (9.4+/10).

---

## Purpose

Every idea that enters the harness — whether via Solon's "lock it" prompt, an operator-queued task, a Slack message, or a row inserted into `ideas` / `session_next_task` — flows through a single automated pipeline:

```
IDEA (raw capture)
   ↓
DESIGN REVIEW (Perplexity sonar-pro, saved as plans/PLAN_<date>_<slug>.md)
   ↓
PROMPT / SPEC WAR ROOM (per-phase prompts graded to A)
   ↓
PHASED EXECUTION (each phase under harness preflight + capacity gate)
   ↓
PER-PHASE QA (Perplexity grade, auto-advance on A, iterate until A or flag for Solon)
```

Solon does nothing manual. Titan does everything. Solon is only contacted when a phase is flagged `needs_solon_override` after max iterations, or on specific Slack events (DR complete · phase A-graded · phase flagged for override).

---

## Section 1 — Idea Intake

### Watched sources

1. **`ideas` table** rows with `status IN ('approved','promoted')`.
2. **`session_next_task` table** rows — each row's `body` field carries JSON with optional `task_type` (plan · blueprint · performance · infra · mp1 · mp2 · atlas). Any row not already linked to a `tasks` row is a candidate.
3. **`user-prompt-idea.sh` hook** (the existing "lock it" + 🔒 emoji trigger) continues to feed `ideas` as it does today. No change.

### Normalization

For each new idea/task:

1. Build `PLAN_REQUEST.md` artifact:
   ```
   # Plan Request: <title>
   Source: ideas / session_next_task / lock-it hook
   Project: <project_id>
   Raw text: <idea_text or body.summary>
   Requester: <instance_id>
   Captured at: <created_at>
   ```
2. Insert (or upsert on idempotency key) a row in `tasks`:
   ```
   task_type: 'dr_plan'
   status:    'pending'
   summary:   'DR plan for: <title>'
   handler_type: 'titan_auto'
   urgency:   'normal'
   routing:   'idea_to_execution'
   project_id: <project_id>
   ```
3. Idempotency key: `sha256(source_id + ':' + slug)` stored in `tasks.deliverable_url` (re-purposed audit field). Subsequent runs UPSERT instead of INSERT.

---

## Section 2 — Design Review with Perplexity

Implemented in `lib/idea_to_dr.py`.

### Inputs
- `PLAN_REQUEST.md` or the raw idea text
- Project context via `lib/context_builder.build_context()` (P4 substrate)

### DR prompt (sent to `perplexity_review`, `review_type='architecture'`)

> You are evaluating a raw idea for inclusion in an automated AI-agent harness. Produce a design review that includes: (1) scope & goals, (2) phases with dependencies (topo-sortable), (3) per-phase task type (plan/architecture/spec/synthesis/phase/transform/classify/research), (4) per-phase required inputs and outputs, (5) risks + mitigations, (6) acceptance criteria per phase, (7) rollback path, (8) honest scope cuts (what is deferred as follow-on). Target A-grade (9.4+/10) on your native scale. If the idea is underspecified, ask top 3 clarifying questions and grade as B.

### Output
- Saved to `plans/PLAN_<YYYY-MM-DD>_<slug>.md`
- Supabase `tasks` row updated: `status='completed'`, `deliverable='<path to plan>'`, `deliverable_content=<markdown>`, `war_room_grade='A'`
- On weak grade (<A): loops through `lib/war_room.py` up to 5 exchanges; on max-iter fail flags `needs_solon_override`

---

## Section 3 — Prompt / Spec War Room

### Per-phase extraction

Parses the DR plan for numbered phases. For each phase:
1. Generates `plans/prompts/PROMPT_<phase_N>_<slug>.md` (the operator instruction for that phase)
2. Generates `plans/prompts/SPEC_<phase_N>_<slug>.md` (the technical spec / acceptance criteria)

### Grading loop

For each prompt and spec:
1. Calls `WarRoom().grade(titan_output=<text>, phase=<phase_name>, trigger_source='plan_finalization', project_id=<project_id>)`
2. Uses existing `policy.yaml war_room:` config (min_grade=A, max_refinement_rounds, cost ceiling)
3. On A-grade: save final text to `plans/prompts/` and log `war_room_exchanges` row linked to the parent `dr_plan` task via `exchange_group_id`
4. On max-iter fail: mark parent task `needs_solon_override`

---

## Section 4 — Phased Execution

Each DR phase becomes a row in **`mp_runs`** (chosen over `tasks` because `mp_runs` already has `phase_number`, `phase_name`, `war_room_group_id`, `duration_ms`, `api_spend_cents` etc.).

Per-phase schema:
```
mp_runs:
  project_id: <from idea>
  megaprompt: 'idea_to_exec'       -- new megaprompt tag (added to constraint)
  phase_number: 1..N
  phase_name: <from DR plan>
  status: 'running' → 'complete' | 'failed' | 'blocked'
  parent_run_id: <first phase of the idea>
  war_room_group_id: <from P3 prompt/spec grading>
  notes: <links to prompt/spec files>
```

### Execution loop (per phase)

1. `bin/harness-preflight.sh` — non-bypassable (exit 10/11/12 on violation)
2. `bin/check-capacity.sh` — hard_block = defer and exit 2
3. Look up the phase's task_type → `lib/model_router.resolve_model()` (P3 substrate)
4. Assemble context via `lib/context_builder.build_context()` (P4 substrate)
5. Execute the phase — route via:
   - `bin/mp-runner.sh` if the phase has a registered script
   - `lib/prompt_pipeline.run_pipeline()` if the phase is a DAG of sub-steps (P7 substrate)
   - `lib/llm_client.complete()` or `.stream_to_supabase()` for single-LLM phases (P6 substrate)
   - `lib/llm_batch.batch_score()` if the phase is multi-item (P5 substrate)
6. Call Perplexity QA prompt:
   > Would you ship this phase output as production-ready? Grade 1-10, A-grade floor 9.4+. Top 5 blockers if below. Evaluation criteria: correctness, completeness, honest scope, rollback availability, fit with harness patterns (gateway, capacity, model router, context builder, prompt pipelines).
7. On A: `mp_runs.status='complete'`, `war_room_grade='A'`, advance to next phase
8. Below A after max iterations (5): `mp_runs.status='blocked'`, `notes='needs_solon_override'`, Slack alert, STOP auto-advance for this idea
9. Log every exchange to `war_room_exchanges` with a stable `exchange_group_id` tying all phases of one idea together

---

## Section 5 — End-to-End Orchestrator

### `lib/idea_to_execution.py` + `bin/idea-to-execution.sh`

Entry points:
- `idea-to-execution.sh --once` — single poll + process cycle (cron-friendly)
- `idea-to-execution.sh --daemon` — long-running poll loop (systemd-friendly)
- `idea-to-execution.sh --dry-run` — log-only mode (no LLM calls, no Supabase writes, no Slack)

### Poll cycle

1. `harness-preflight.sh` — bail on violation
2. `check-capacity.sh` — hard_block skips the tick entirely
3. Query Supabase for pending work:
   - `ideas` WHERE `status IN ('approved','promoted')` AND `promoted_to_task_id IS NULL`
   - `session_next_task` WHERE body has an unlinked task_type
   - `tasks` WHERE `task_type='dr_plan'` AND `status='pending'` (Section 2 work)
   - `tasks` WHERE `task_type='dr_plan'` AND `status='completed'` AND prompt/spec grading not yet done (Section 3 work)
   - `mp_runs` WHERE `megaprompt='idea_to_exec'` AND `status='running'` AND capacity/age triggers say time to advance (Section 4 work)
4. For each item, run the appropriate section handler with a single bounded time budget (`POLICY_CAPACITY_MAX_LLM_CONCURRENT_BATCHES=8` cap)
5. Slack notifications ONLY on:
   - DR complete (`plans/PLAN_<date>_<slug>.md` written)
   - Phase finished with A-grade
   - Phase flagged `needs_solon_override`
6. No chatter, no routine heartbeat, no progress spam — matches Silent COO + Blaze Mode

### Capacity integration
- Bounded concurrency: `asyncio.Semaphore(POLICY_CAPACITY_MAX_LLM_CONCURRENT_BATCHES)` wraps the section handlers so one idea with 10 phases doesn't starve others
- Per-phase capacity re-check before each LLM call via `lib/capacity.check_capacity()`

---

## Section 6 — Contract / Defaults

### Default ON
Any new major project (AMG or client Titan-as-COO) routes through this pipeline by default. No manual step.

### Opt-out
Explicit override required via either:
- `tasks.notes` containing `override:bypass_idea_pipeline`
- `policy.yaml` `idea_to_execution.disabled_project_ids` list
- Environment variable `IDEA_TO_EXEC_DISABLED_PROJECTS=<csv>`

### Enforcement
- `CORE_CONTRACT.md` Section 7 documents the default-on rule
- `bin/idea-to-execution.sh` always runs `harness-preflight.sh` before any work
- `policy.yaml` `idea_to_execution:` block carries the configuration surface
- Overrides are logged to `mp_runs.notes` with the exact override reason

---

## Section 7 — Capacity + A-Grade Inheritance

This pipeline inherits ALL prior contracts:
- 12-key capacity block (hard ceilings at 12/8/20/3/10/4/15/8 · 80/90% CPU · 50/56 GiB RAM)
- Fast Mode default ON / Blaze Mode conversational contract
- `harness-preflight.sh` + `check-capacity.sh` non-bypassable
- War-room A-grade floor (9.4+/10) on every deliverable
- `lib/context_builder.py` for context trimming (no re-pasted history)
- `lib/model_router.py` for task_type → model resolution
- Substrate-first discipline: ship substrate, soak, migrate callers

---

## Change Log

| Date | Change |
|---|---|
| 2026-04-11 | Contract created. Substrate shipped: `IDEA_TO_EXECUTION_PIPELINE.md`, `lib/idea_to_dr.py`, `lib/idea_to_execution.py`, `bin/idea-to-execution.sh`, `sql/110_idea_pipeline.sql`, `policy.yaml idea_to_execution:` block, CORE_CONTRACT.md Section 7, cron (`*/2 * * * *` log-only for first 48h, then `--once` active). |
