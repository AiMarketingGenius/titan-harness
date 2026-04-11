# TITAN HARNESS — CORE CONTRACT

**Status:** ACTIVE and NON-BYPASSABLE
**Effective:** 2026-04-10 (Phase G.5)
**Applies to:** AMG production harness, Solon OS core, Atlas Machine pipelines, and every "Titan as COO" client deployment built on this harness.

---

## 1. Capacity Policy is Non-Optional

Every deployment of the titan-harness **MUST** ship with a populated `capacity:` block in `policy.yaml`. The block declares the operational ceilings for the host machine and is treated as the single source of truth by every runner, worker, n8n workflow, and LLM caller.

### Required keys (minimum)
```yaml
capacity:
  max_claude_sessions:            <int>   # concurrent Claude Code sessions
  max_heavy_tasks:                <int>   # plans, syntheses, large docs
  max_n8n_branches_per_workflow:  <int>
  max_concurrent_heavy_workflows: <int>
  max_workers_general:            <int>
  max_workers_cpu_heavy:          <int>
  max_llm_batch_size:             <int>
  max_concurrent_llm_batches:     <int>
  cpu_soft_limit_percent:         <int>
  cpu_hard_limit_percent:         <int>
  ram_soft_limit_gib:             <int>
  ram_hard_limit_gib:             <int>
```

`lib/policy-loader.sh` will emit `POLICY_CAPACITY_BLOCK_VALIDATED=0` and a loud stderr warning if any of these are missing. `bin/harness-preflight.sh` refuses to start any runner with exit code **10** in that case.

## 2. Capacity Guard is Non-Bypassable

The following scripts **MUST** be called as a pre-flight step by every runner or worker built on this harness:

| Script | Purpose | Exit contract |
|---|---|---|
| `bin/harness-preflight.sh` | Policy + capacity block + check-capacity availability | 0=ok, 10=policy invalid, 11=guard missing, 12=baseline hard-blocked |
| `bin/check-capacity.sh` | Live CPU/RAM check | 0=ok, 1=soft_block, 2=hard_block |

### Required wiring
- **`bin/mp-runner.sh`** — calls both scripts before starting any phase. On non-zero, logs and exits with the same code. ✅ wired.
- **`titan_queue_watcher.py`** — calls `_capacity_gate()` (shell-out) every `process_task` poll. Hard-block = skip tick; soft-block = release HEAVY task types back to pending; light tasks flow. ✅ wired. `harness-preflight.sh` runs as `systemd` `ExecStartPre`.
- **Any future runner** (client-specific pipelines, MP-1/MP-2 descendants, Atlas Layer 2/3 workers, client Titan instances) — **must** invoke `harness-preflight.sh` before claiming work and **must** run `check-capacity.sh` before spawning any heavy worker, new Claude Code session, or new LLM batch.

### Heavy task classification
The queue-watcher treats these `task_type` values (or tags) as **heavy** and defers them on soft_block:
`plan`, `architecture`, `spec`, `phase`, `synthesis`, `war_room`, `mp1`, `mp2`, `research`, `review`.

Additionally, any task with `summary` length > 4000 chars is treated as heavy.

## 3. No Bypass for "Titan as COO" Deployments

Every client deployment of the Titan stack (dropshipping shops, agencies, info-product operators — see `project_titan_as_coo_product.md`) inherits this contract. No client pipeline is allowed to:

- Run without a `capacity:` block in its `policy.yaml`.
- Omit the `harness-preflight.sh` pre-flight step in runners.
- Shell out to LLMs, spawn workers, or fan-out n8n workflows without first consulting `check-capacity.sh`.

The contract is part of the Solon OS / Atlas Machine foundation. Bypassing it is a P0 policy violation and any such deployment must be rolled back.

## 4. Tuning

The ceilings in `capacity:` are **per-host** and should be re-tuned when:

- The host changes (different VPS size, different workload tenancy).
- A new workload class is added that materially changes expected concurrency.
- Live monitoring (`check-capacity.sh` logs, Prometheus `titan_capacity_*` metrics once deployed) shows sustained saturation or sustained under-utilization.

Tuning is done by editing `policy.yaml` and re-sourcing `lib/titan-env.sh`. No code changes are required.

## 5. Change Log

| Date | Change |
|---|---|
| 2026-04-10 | Contract created. Initial ceilings from Perplexity-graded war-room for VPS 12c/64GB. `capacity:` block, `check-capacity.sh`, `harness-preflight.sh`, mp-runner wiring, queue-watcher wiring (hard+soft blocks), systemd `ExecStartPre`. |

---

## 6. Blaze-Mode Conversation Contract (Solon OS / Atlas Machine)

**Status:** ACTIVE and NON-BYPASSABLE (added 2026-04-11).
**Applies to:** every Titan session, every Solon conversation, every client "Titan as COO" deployment.

### Rule

Blaze-mode conversational behavior and the 12-key capacity ceilings are part of the **Solon OS / Atlas Machine contract for all Titans**. Every Titan session launched via this harness MUST:

1. Honor the 12-key capacity block (Rules 1-3 above) on every worker, LLM call, and n8n branch.
2. Honor the Speed + Capacity Contract (Conversational Mode):
   - **Latency first** — fewest tokens that preserve A-grade usefulness.
   - **No unnecessary narration** — no self-talk, apologies, or question-restatement.
   - **Parallel thinking internally**, synthesized into one concise answer externally.
   - **Right-effort level** (simple → fast/short, strategic → concise/deeper).
   - **Stream responses** so Solon sees output as soon as possible.
   - **Short incremental updates** over long monologues during back-and-forth.
   - **Heavy background analysis only on explicit trigger** ("go deep", "war room this", "deep dive").
3. Pull `POLICY_BLAZE_MODE_ENABLED=1` and `POLICY_FAST_MODE_DEFAULT=on` from `policy.yaml` via `lib/policy-loader.sh`.
4. Auto-inject `/opt/titan-harness/SESSION_PROMPT.md` into the session startup context via the harness boot-audit script (wired at `/opt/titan-session/boot-audit.sh` on 2026-04-11).

### Scope

This clause applies to:
- **AMG production Titan** on this VPS (`titan-queue-watcher.service`, mp-runner, war_room.py, etc.)
- **Client "Titan as COO" deployments** — per-client Docker Compose stacks inheriting this harness
- **Solon OS core layers** — Solon OS, Atlas Machine, future Atlas layers
- **Any Claude Code session** opened in a directory containing this harness's CLAUDE.md

No Titan instance is allowed to:
- Disable Blaze Mode behavior by default.
- Bypass the capacity gate via any shortcut.
- Omit `SESSION_PROMPT.md` auto-injection in its boot sequence.
- Launch without `harness-preflight.sh` passing.

### Enforcement

- **Mechanical:** `policy-loader.sh` exports `POLICY_BLAZE_MODE_ENABLED` and `POLICY_FAST_MODE_DEFAULT`. `boot-audit.sh` prints `SESSION_PROMPT.md` at every session start. `harness-preflight.sh` blocks runner start with exit 10 if the capacity block is missing.
- **Behavioral:** CLAUDE.md Hard Rules #14 (Fast Mode default) and #15 (Blaze Mode contract) encode the behavioral expectations for every Titan response.
- **Audit:** `fast_mode_events` Supabase table captures every toggle with reason. `context_builder_bypasses` table captures any caller skipping the context trimming substrate.

### Change Log

| Date | Change |
|---|---|
| 2026-04-11 | Section 6 added. Blaze Mode conversational contract + capacity limits are now explicitly part of the Solon OS / Atlas Machine contract for all Titans. SESSION_PROMPT.md created at `/opt/titan-harness/`. `boot-audit.sh` auto-injects it at every session start. CLAUDE.md Global Behavior section mirrors it. |

---

## 7. IDEA → DR → PLAN → EXECUTE Pipeline (Solon OS / Atlas Machine default)

**Status:** ACTIVE and NON-BYPASSABLE for all new major projects (AMG core and client "Titan as COO" deployments). Added 2026-04-11.

### Rule

Every new major project that enters the harness MUST route through the automated IDEA → DR → PLAN → EXECUTE pipeline documented in `IDEA_TO_EXECUTION_PIPELINE.md`. This includes:

- Ideas captured via Solon's "lock it" / 🔒 UserPromptSubmit hook
- Rows inserted into the `ideas` table with `status IN ('approved','promoted')`
- Rows inserted into the `session_next_task` table whose `body` carries a `task_type` in the allowed set (plan · blueprint · performance · infra · mp1 · mp2 · atlas)
- Client Titan-as-COO project onboarding (one pipeline run per client project)

### Automated flow (zero manual steps from Solon)

1. **Intake** — `lib/idea_to_execution.py` polls all three sources every cycle.
2. **Design Review** — `lib/idea_to_dr.py` calls Perplexity `sonar-pro` via the LiteLLM gateway, writes the plan to `plans/PLAN_<YYYY-MM-DD>_<slug>.md`, and updates the audit row in `idea_to_exec_runs`.
3. **Prompt / Spec war room** — the orchestrator parses the DR for phases, writes per-phase `PROMPT_*.md` and `SPEC_*.md` artifacts under `plans/prompts/`, and grades each via `lib/war_room.py` at the A-grade floor.
4. **Phased execution** — each phase is executed via the LLM gateway, graded by the war-room, and auto-advanced on A. Phases are logged to `mp_runs` with `megaprompt='idea_to_exec'` and tied to the parent run via `war_room_group_id`.
5. **Auto-advance or Solon override** — on A-grade, the next phase runs automatically. Below A after max iterations, the run status flips to `needs_solon_override` and auto-advance stops for that idea. Other ideas continue uninterrupted.

### Opt-out

Explicit override required. Three valid paths:

- `tasks.notes` containing `override:bypass_idea_pipeline`
- `policy.yaml` key `idea_to_execution.disabled_project_ids: [list]`
- Env var `IDEA_TO_EXEC_DISABLED_PROJECTS=<csv>`

Any override is logged to `mp_runs.notes` with the exact override reason at the next poll cycle for that project.

### Enforcement

- **Mechanical:** `bin/idea-to-execution.sh` always runs `harness-preflight.sh` before any work. It refuses to start on exit 10/11/12. Every LLM call respects `POLICY_CAPACITY_*` via `lib/capacity.check_capacity()`. Cron `*/2 * * * *` on the root crontab guarantees the orchestrator runs without manual invocation.
- **Behavioral:** CLAUDE.md references this contract via the reference index. Hard Rules #13 (auto-advance on A-grade) and #15 (Blaze Mode) together cover the conversational posture while the pipeline is running.
- **Audit:** `idea_to_exec_runs`, `idea_to_exec_phase_artifacts`, `mp_runs`, `war_room_exchanges`, and `plans/` + `plans/prompts/` on disk form a complete audit trail per idea.

### Slack Policy

Slack is used ONLY for these three events (Silent COO rule):

1. DR complete (with plan path)
2. Phase finished with A-grade (auto-advance confirmed)
3. Phase flagged `needs_solon_override`

No routine heartbeat, no progress spam, no "still working" messages.

### Scope

This clause applies to:
- AMG production Titan on this VPS
- Every client Titan-as-COO deployment that inherits this harness
- Solon OS core layers (Solon OS, Atlas Machine, future Atlas layers)

### Change Log

| Date | Change |
|---|---|
| 2026-04-11 | Section 7 added. Pipeline substrate shipped: `lib/idea_to_dr.py`, `lib/idea_to_execution.py`, `bin/idea-to-execution.sh`, `sql/110_idea_pipeline.sql` (adds `idea_to_exec_runs` + `idea_to_exec_phase_artifacts` tables and extends `mp_runs.megaprompt` CHECK to allow `idea_to_exec`). Cron installed at `*/2 * * * *`. Live smoke-tested: 3 phases A-graded, 1 phase correctly flagged F + `needs_solon_override`, real plan + prompt/spec artifacts on disk. |
