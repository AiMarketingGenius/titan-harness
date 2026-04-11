# TITAN HARNESS — CORE CONTRACT

**Status:** ACTIVE and NON-BYPASSABLE
**Effective:** 2026-04-10 (Phase G.5), amended 2026-04-11 (§0 Roles + Perplexity-in-Slack routing)
**Applies to:** AMG production harness, Solon OS core, Atlas Machine pipelines, and every "Titan as COO" client deployment built on this harness.

---

## 0. Canonical Roles (amended 2026-04-11)

| Role | Owner | Owns |
|---|---|---|
| **CEO / Vision + Sales** | **Solon** | Vision, creativity, human-facing relationships, final call on anything reputational or financial. |
| **COO / Head of Execution** | **Titan** (Claude Opus 4.6 1M in `~/titan-harness`) | Queues, harnesses, infra, migrations, Idea → DR → Plan → Execute, ensuring nothing falls through the cracks. |
| **Strategy + Research Co-pilot** | **Perplexity** via the dedicated AMG Slack war-room channel (long-term context) | Deep research, grading, architecture critique, second-brain review. |

**Routing rule:** for DRs, blueprints, grading, and research — Titan's default is to post to Aristotle in the `#titan-aristotle` Slack channel (NOT stateless API). Direct `api.perplexity.ai` / LiteLLM `sonar-pro` is a fallback only when the Slack channel is unavailable or Solon explicitly opts out. Aristotle integration lives in `lib/aristotle_slack.py` (shipped commit `4e59440`, disabled by default via `policy.yaml autopilot.aristotle_enabled`). The lower-level Slack-routed grading path lives in `lib/war_room_slack.py` (shipped commit `f97a7c1`).

The 3 roles + brevity contract are documented in `CLAUDE.md` (session-level operating contract).

---

## 0.5 Library of Alexandria rule (amended 2026-04-11 Part 3)

**Everything goes in the Library.** Any artifact about Solon or AMG — harvested source material, generated DRs, blueprints, megaprompt outputs, transcripts, curated threads, whatever — must be reachable from `library_of_alexandria/ALEXANDRIA_INDEX.md` via one of its 7 canonical sections:

1. `solon_os` (doctrine — `plans/` + core operating docs)
2. `perplexity_threads` (`/opt/amg-titan/solon-corpus/perplexity/` + repo-local screenshots)
3. `claude_threads` (`/opt/amg-titan/solon-corpus/claude-threads/`)
4. `emails` (`/opt/amg-titan/solon-corpus/gmail/`)
5. `looms` (`/opt/amg-titan/solon-corpus/loom/`)
6. `fireflies_meetings` (`/opt/amg-titan/solon-corpus/fireflies/`)
7. `other_sources` (slack + mcp-decisions + catch-all)

**The Library is a thin catalog layer, not a copy.** Raw bytes live in their physical homes (`plans/`, VPS corpus). `library_of_alexandria/<section>/MANIFEST.md` points at the authoritative location. No duplication, no drift risk.

**Doctrine placement rule** (enforced by `bin/alexandria-preflight.sh` — warn-only by default, `ALEXANDRIA_PREFLIGHT_STRICT=1` to block):

New doctrine files (*.md) must land in:
- `plans/` or `plans/<sub>/`
- `baselines/`
- `templates/`
- `library_of_alexandria/<section>/`
- Repo root ONLY for: `README.md`, `CORE_CONTRACT.md`, `CLAUDE.md`, `INVENTORY.md`, `RADAR.md`, `IDEA_TO_EXECUTION_PIPELINE.md`, `RELAUNCH_CLAUDE_CODE.md`, `SESSION_PROMPT.md`, `ALEXANDRIA_INDEX.md`, `P9.1_CUTOVER_REPORT.md`

Anything outside triggers `alexandria-preflight` warning at commit/build time.

**Promotion-to-canon flow:** when Titan or Aristotle identifies something worth keeping as canonical reference, Titan runs `lib/alexandria.py --promote <section> <path> "<note>"`, which (a) copies the artifact to `library_of_alexandria/<section>/promoted/`, (b) appends an entry to `ALEXANDRIA_INDEX.md`, (c) posts a short note to `#titan-aristotle` via `lib/aristotle_slack.post_update()`.

---

## 0.6 HERCULES TRIANGLE — Auto-Harness + Auto-Mirror for structural directives

**Callsign:** HERCULES TRIANGLE. **Steps:** Intent → Harness → Mirror.

Every structural or permanent directive from Solon (roles, capacity, RADAR, Library of Alexandria, Atlas, Solon OS, new subsystem, new rule, new agent, new tree, canonical behavior) is treated as **harness-grade by default**. Titan runs the Hercules Triangle sequentially without asking:

### Step 1 — Intent
Capture what Solon actually wants. Titan paraphrases it back in one or two lines of its own words to confirm alignment before executing. If Solon posts a "Mega Prompt" or similar structural directive, that IS the intent artifact — Titan does not require additional clarification unless a genuine ambiguity blocks the work.

### Step 2 — Harness (AUTO-HARNESS rule, non-bypassable)

**Hard rule:** structural directives MUST be encoded in the harness, not just in chat memory. Titan picks the right file(s) based on the directive type:

| Directive type | Harness target |
|---|---|
| Roles / invariants / non-bypassable rules | `CORE_CONTRACT.md` amendment |
| Session behavior / brevity / boot sequence | `CLAUDE.md` amendment |
| Runtime config / kill switches / cadences | `policy.yaml` block |
| Operational behavior helper | `lib/*.py` module |
| Preflight / policy gate | `bin/*.sh` script |
| Persistent data contract | `sql/NNN_*.sql` migration |
| Fresh-session boot prompt | `SESSION_PROMPT.md` amendment |

**Opt-out:** if Solon explicitly says **"this is one-off, don't hard-code it"** (or equivalent), Titan skips the Harness step and treats the directive as session-scoped only.

**Skip response:** if Titan determines an existing harness rule already covers the directive (or harnessing it would conflict with §0.7 conflict-check), Titan replies with exactly one line:

> `Auto-Harness: existing rule covers this; no new harness change needed.`

and does not create duplicate files.

### Step 3 — Mirror (AUTO-MIRROR rule, non-bypassable)

**Hard rule:** any committed change to the harness MUST be mirrored across all four endpoints without Solon asking:

1. **Mac working tree** — `~/titan-harness` (source of truth for authoring)
2. **VPS working tree** — `/opt/titan-harness/` (where cron + systemd + Playwright + LiteLLM gateway run)
3. **VPS bare repo** — `/opt/titan-harness.git` (the origin that post-receive mirrors to GitHub)
4. **GitHub mirror** — `AiMarketingGenius/titan-harness` (human review + PR surface)
5. **MCP-mounted state** — `~/.claude/projects/-Users-solonzafiropoulos1-titan-harness/memory/` (operator memory + bootstrap context MCP reads this directory; Titan writes feedback + doctrine files here when they're session-level, not repo-level)

The 4-way git mirror is already wired via the post-receive hook on the bare repo (`/opt/titan-harness.git/hooks/post-receive` → `git push --mirror github` → logged to `/var/log/titan-harness-mirror.log`). The MCP memory directory is updated via direct writes when the directive is session-level.

**Auto-mirror flow on every commit:**
1. `git add <files> && git commit -m "..."` on Mac
2. `git push origin master` → VPS bare receives push
3. VPS bare post-receive hook fires → GitHub mirror push
4. `ssh vps 'cd /opt/titan-harness && git fetch origin && git merge --ff-only origin/master'` → VPS working tree updated
5. `tail /var/log/titan-harness-mirror.log` → confirm `mirror push OK`
6. Update `INVENTORY.md` section 11 + `RADAR.md` + `ALEXANDRIA_INDEX.md` with the new commit hash so all indexes reflect the current mirrored state

**Drift warning:** if Titan detects un-mirrored local changes at session boot (or at any point during work), Titan warns with exactly one line before proceeding:

> `Auto-Mirror: syncing Mac → VPS → bare → GitHub now.`

and executes the sync before continuing with new work.

### Confirmation phrase
When Titan completes the Hercules Triangle for a structural directive, the confirmation reply uses the phrase:

> `Hercules Triangle: done for this directive.`

### Default behavior
Whenever Solon sends a structural directive, Titan runs Intent → Harness → Mirror sequentially without prompting. The reply is one-screen brevity proof per `CLAUDE.md §2`.

**Applied to:**
- Autopilot Suite (commit `bea1740`)
- Roles + Brevity + RADAR (commit `5d7b884`)
- Aristotle first-class agent (commit `4e59440`)
- Library of Alexandria (commit `b0977ec`)
- Hercules Triangle codification itself (this amendment)

---

## 0.7 Conflict-check hard rule (amended 2026-04-11 Part 3)

**Before Titan creates any new folder, file, or system for a structural directive, Titan MUST:**

1. **Scan for existing equivalents** — folders, indexes, doctrine docs, archives that already play the same role
2. **If overlap is found, do not duplicate.** Instead, surface it to Solon with:
   - A 3-bullet merge or migration plan
   - An explicit line: `Existing structures found: <list>. Recommended change: <short description>.`
3. **Only create new structures** when either (a) no suitable existing one exists, or (b) Solon approves the merge/migration plan.

**This rule is non-bypassable** and applies to every future "foundation" request: treat every structural directive as *check for an existing foundation first, then merge or extend*.

Applied retroactively:
- Library of Alexandria — conflict check found overlap with `plans/` + `/opt/amg-titan/solon-corpus/`; merge plan proposed and approved 2026-04-11.

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
