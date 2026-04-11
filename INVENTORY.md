# titan-harness Inventory (last 5 days: 2026-04-06 → 2026-04-11)

**Purpose:** ground-truth document for Perplexity (and Solon). Lists everything built in the titan-harness + amg-titan stack over the last 5 days. Organized by domain. Each item notes: what it is, where it lives, current state, and what it does NOT do (scope boundary).

**Why this exists:** Solon asked Perplexity for a 5-thread "autopilot suite" (sales inbox, proposal SOW, marketing engine, back-office, client reporting). Several components of that ask were already built during the performance rollout + Phase G + Gate 3 + MP-1 HARVEST work. This document is the disambiguator so Perplexity can focus its recommendations on the actual gaps rather than re-specifying things that already ship.

**HEAD as of writing:** `f97a7c1` on master, mirrored Mac ↔ VPS `/opt/titan-harness` ↔ VPS bare `/opt/titan-harness.git` ↔ GitHub `AiMarketingGenius/titan-harness`.

---

## 1. Harness substrate (performance rollout P2–P13)

Status: **SHIPPED + in production on VPS**. All 12 substrate layers are committed and soaked. See `baselines/post_rollout_2026-04-11_baseline.md` for the measured deltas from the pre-rollout state.

| Layer | Module | Lines | What it does | Notes |
|---|---|---:|---|---|
| P2 LiteLLM gateway | `/opt/titan-processor/litellm/` + env block in `/root/.titan-env` | — | Single LLM ingress on `http://127.0.0.1:4000`. Routes every LLM call in the harness. Virtual keys per caller (`war_room`, `mp_runner`, `queue_watcher`, `n8n`, `claude_code`). Master key in `LITELLM_MASTER_KEY`. | Healthchecks `{"models":[...]}` on `/v1/models`. Perplexity sonar-pro routing is 401'd right now due to quota exhaustion (see NEXT_TASK.md Solon action #4). Claude sonnet/opus/haiku routing works. |
| P3 model router | `lib/model_router.py` (163 lines) | 163 | Given a `task_type` resolves the right model via `policy.yaml model_router.tasks:` block. Task types: `plan`, `architecture`, `spec`, `synthesis`, `phase`, `transform`, `classify`, `research`, `review`, `war_room_grade`, `draft`, `code`. | Lets callers say "give me a model for a `classify` task" instead of hardcoding Haiku/Sonnet/sonar-pro. Fallback chain configured per task. |
| P4 context builder | `lib/context_builder.py` (305 lines) | 305 | `build_context(task, caller, max_tokens)` returns a budgeted context string assembled from: Supabase `plans/`, recent git log, memory files, the task's own spec. Used by every autonomous caller. | Prevents context bloat. Caps at configurable `max_tokens`. |
| P5 LLM batch | `lib/llm_batch.py` (293 lines) | 293 | `batch_score(items, task_type)` parallelizes many small LLM calls into one gateway batch. Bounded concurrency via `async_pool`. | Used by MP-1 Phase 7 MCP decisions scoring, and will be used by sales-inbox classifier. |
| P6 LLM client | `lib/llm_client.py` (323 lines) | 323 | `complete()` and `stream_to_supabase()` — the canonical LLM call wrapper. Handles gateway routing, token accounting, retries, Supabase logging to `llm_calls` table. | Every caller goes through this; nothing talks to LiteLLM directly anymore except war_room.py (direct-to-perplexity.ai path, which is quota-blocked). |
| P7 prompt pipeline | `lib/prompt_pipeline.py` (353 lines) | 353 | Run a DAG of sub-steps, each a prompt → LLM → parse → next. Used for multi-step transformations. | Underpins the DR generation phases in idea_to_dr.py. |
| P8 async pool | `lib/async_pool.py` (129 lines) | 129 | `asyncio.Semaphore`-wrapped task runner with capacity awareness. | Used by batch + idea_to_execution. |
| P12 capacity | `lib/capacity.py` (58 lines) + `bin/check-capacity.sh` (48 lines) + `bin/harness-preflight.sh` (50 lines) | 156 | 12-key capacity block: `POLICY_CAPACITY_MAX_LLM_CONCURRENT_BATCHES=8`, `POLICY_CAPACITY_CPU_HARD_LIMIT=90`, `POLICY_CAPACITY_RAM_HARD_LIMIT_GIB=56`, etc. Hard-blocks any LLM call or mp-run if a ceiling is exceeded. | NON-BYPASSABLE. Runs before every phase in mp-runner + idea-to-execution. Returns exit 2 on hard block. |
| P13 fast mode | `sql/100_fast_mode.sql` + policy block | — | `/fast` CLI toggle for Claude Code. User-only (Titan can't toggle it). | Docs in `RELAUNCH_CLAUDE_CODE.md`. |
| — | `lib/titan-env.sh` (8 lines) | 8 | Shared env loader sourced by every bin/ script. | — |
| — | `lib/policy-loader.sh` (430 lines) | 430 | Parses `policy.yaml` into `POLICY_*` env vars used by every bash/Python caller. | Non-bypassable: every script sources this before running. |

**What the substrate does NOT do:** it does not provide business-level automation (inbox handling, proposal drafting, marketing posting, client reporting). Those are application layers that sit on top of the substrate.

---

## 2. IdeaBuilder pipeline (Phase G — idea → DR → war-room → phased execution)

Status: **SHIPPED + running on cron every 2 minutes on VPS**. Currently in log-only soak for the first 48h, then flips to `--once` active mode.

| Component | File | Lines | What it does |
|---|---|---:|---|
| Contract doc | `IDEA_TO_EXECUTION_PIPELINE.md` | 206 | Canonical spec. Section 1 intake, Section 2 DR via Perplexity, Section 3 per-phase war-room, Section 4 phased execution, Section 5 orchestrator, Section 6 default-on rule, Section 7 capacity + A-grade inheritance. |
| Intake: lock-it hook | `hooks/user-prompt-idea.sh` (198 lines) | 198 | Watches Claude Code user prompts for the 🔒 "lock it" trigger. Captures the idea text to `~/titan-session/ideas-queue.jsonl`. |
| Intake: drain daemon | `bin/idea-drain.sh` (171 lines) + `services/titan-ideas-drain.timer` | 183 | Polls the jsonl queue every 60s, POSTs each idea to Supabase `public.ideas`, slack-pings once per successful insert. Idempotent (409 = already-inserted). |
| Intake: helpers | `bin/idea-list.sh`, `bin/idea-edit.sh`, `bin/idea-delete.sh`, `bin/idea-health.sh`, `bin/idea-promote.sh` (184 lines) | ~620 | CRUD on the `ideas` table + promotion to `tasks` as a CT-MMDD-NN task. |
| DR generator | `lib/idea_to_dr.py` (299 lines) | 299 | `run_dr(idea, project_id)` → calls Perplexity sonar-pro through LiteLLM with the DR prompt. Writes to `/opt/titan-harness/plans/PLAN_<date>_<slug>.md`. Inserts `idea_to_exec_runs` audit row. **Currently broken due to PPLX quota exhaustion.** |
| Orchestrator | `lib/idea_to_execution.py` (573 lines) | 573 | End-to-end poll cycle: checks preflight + capacity, scans `ideas` + `session_next_task` + `tasks` tables for pending work, routes to the right section handler (DR, prompt/spec grading, phase exec). Bounded concurrency via `asyncio.Semaphore(8)`. |
| Orchestrator runner | `bin/idea-to-execution.sh` (31 lines) | 31 | Thin wrapper — sources env + policy, runs `python3 -m idea_to_execution --once` or `--daemon`. |
| Schema | `sql/110_idea_pipeline.sql` (60 lines) | 60 | `ideas` table, `idea_to_exec_runs` audit table, `session_next_task` table, indexes. |
| Policy block | `policy.yaml idea_to_execution:` | — | Default-on flag, disabled-projects list, poll interval, cost caps. |

**Cron:** `*/2 * * * * bin/idea-to-execution.sh --once` on VPS, logging to `/var/log/titan-idea-exec.log`.

**What IdeaBuilder does NOT do yet:**
- Does not handle incoming Slack/Gmail as ideas (that's the sales inbox agent thread — new work)
- Does not auto-execute phases that require external state (e.g., "post to LinkedIn" — that's the marketing engine thread — new work)
- Does not grade via Slack-routed Perplexity (code shipped in `lib/war_room_slack.py` but `slack_grading_enabled=false` in policy.yaml)

---

## 3. War Room (A-grade grading loop)

Status: **SHIPPED + in production**. A-grade floor (9.4+/10) enforced on every deliverable. Two grading paths: direct API (default, currently blocked on quota) + Slack-routed (shipped tonight, disabled by default until Solon installs Perplexity Slack app).

| Component | File | Lines | What it does |
|---|---|---:|---|
| Core grader | `lib/war_room.py` | 1123 | `WarRoom.grade(titan_output, phase, trigger_source, context, project_id)` runs the full iteration loop: Perplexity sonar-pro grades on 10 dimensions, Sonnet reviser rewrites if below A, up to 5 rounds, cost-capped at 50¢/round. Logs every round to `war_room_exchanges` table. Slack pings on final grade. |
| Slack-routed grader (NEW 2026-04-11) | `lib/war_room_slack.py` | 480 | `SlackWarRoom.grade(...)` — mirror signature of WarRoom.grade(). Posts to `#titan-perplexity-warroom` with `@perplexity` mention, polls `conversations.replies`, parses bot reply back into `GradeResult`. Privacy scan blocks SSN/EIN/API-keys/sessionKeys from being posted. Disabled by default. |
| Dispatcher | `lib/war_room.py` WarRoom.grade() top | — | If `policy.slack_grading_enabled=true`, routes to SlackWarRoom; else direct API path. Falls through on import error. |
| CLI runners | `bin/war-room.sh` (92 lines), `bin/war-room-shim.sh` (157 lines) | 249 | Standalone CLI: grade a markdown file from the command line. Used by mp-runner for auto-grading phase outputs. |
| Schema | `sql/003_war_room_exchanges.sql` | — | `war_room_exchanges` table + RLS per project_id. |
| Policy block | `policy.yaml war_room:` | — | enabled, model (sonar-pro), min_acceptable_grade=A, max_refinement_rounds=5, cost_ceiling_cents_per_exchange=50, reviser_model=claude-sonnet-4-6, slack_grading_* block. |

**Grading rubric (10 dimensions, all scored /10):** correctness, completeness, honest scope, rollback availability, fit with harness patterns, actionability, risk coverage, evidence quality, internal consistency, ship-ready for production.

**What the War Room does NOT do:**
- Does not grade raw harvest outputs (only planning/synthesis docs)
- Does not auto-revise infinitely (hard ceiling at 5 rounds or $0.50/round)
- Does not currently route through Perplexity Slack (code shipped, awaiting Solon to install the app)

---

## 4. MP-1 HARVEST (solon corpus)

Status: **PARTIAL — 43% complete, 856 artifacts on disk**. Located at `/opt/amg-titan/solon-corpus/` on VPS (not in the titan-harness repo).

| Phase | Script | State | Artifacts |
|---|---|---|---:|
| 1. Claude threads | `harvest_claude_threads.py` | **Pre-built tonight 2026-04-11**. Needs CLAUDE_SESSION_KEY cookie from Solon. | 0 |
| 2. Perplexity threads | `harvest_perplexity.py` | **Pre-built tonight 2026-04-11**. Needs PERPLEXITY_COOKIE_HEADER from Solon. | 0 |
| 3. Fireflies | `harvest_fireflies.py` (exists pre-session) | Reconciled from disk on 2026-04-10. | 46 (5 high-quality) |
| 4. Loom | `harvest_loom.py` (exists pre-session) | Needs LOOM_API_KEY or cookie. | 0 |
| 5. Gmail | ❌ **NOT YET BUILT** (harvest_gmail.py missing) | Needs OAuth consent + Pub/Sub setup. | 0 |
| 6. Slack | internal script | Complete 2026-04-10. | 37 (7 high) |
| 7. MCP decisions | internal script | Complete 2026-04-10. | 773 (90 high) |
| 8. Manifest consolidator | `mp1_phase8_manifest.py` (487 lines) | Complete 2026-04-10. | manifest built |

**Total:** 856 artifacts, 2.68 MB on disk. Checkpoint at `/opt/amg-titan/solon-corpus/.checkpoint_mp1.json`.

**Hard blocker:** Phase 1/2/4/5 need Solon's 2FA/credential session (~15 min).

**MP-1 → MP-4 chain:** MP-2 SYNTHESIS, MP-3 ATLAS BLUEPRINT, MP-4 ATLAS BUILD are all queued but gated on MP-1 completion.

---

## 5. Proposal generator + Gate 3 payment verification

Status: **SHIPPED — Gates 1+2+3 all live on master f1ab8b0, merged tonight**. sql/006 pending Solon apply in Supabase SQL Editor (Solon action #1 in NEXT_TASK).

| Component | File | Lines | What it does |
|---|---|---:|---|
| Proposal builder | `scripts/build_proposal.py` | 608 | Reads a `spec.yaml` client spec, looks up each plan in `payment_links_paypal.json`, builds a DOCX from a template, runs THREE gates. Exits 2/3/5 for gate failures. |
| Template | `templates/proposals/jdj_proposal_v4_linksfix.docx` | — | Binary — the current JDJ proposal base template. `v3_original.docx` is the pre-fix backup. |
| DOCX patch helper | `scripts/patch_jdj_docx.py` | 130 | Post-build token substitution on the DOCX XML. Used when the python-docx renderer can't hit a layout-sensitive cell. |
| Gate 1 | inside `build_proposal.py resolve_subscribe_urls()` | — | Every plan in the spec must have a matching subscribe URL in the catalog. Exit 2 on miss. |
| Gate 2 | inside `build_proposal.py` post-build scan | — | Every subscribe URL must appear in the rendered DOCX plain text. Exit 3 on miss. |
| **Gate 3 (NEW 2026-04-11)** | inside `build_proposal.py verify_gate3_payment_link_tests()` | — | Every subscribe URL must have a `status='pass'` row in `public.payment_link_tests` within the last 24h. Exit 5 on miss. Born from the JDJ Lavar 2026-04-10 wrong-brand-name incident. |
| **Gate 3 browser tester (NEW 2026-04-11)** | `scripts/test_payment_url.py` | 462 | Playwright-based end-to-end test against a real PayPal checkout. CAPTCHA detection (AND-logic to avoid false positives), brand-name match extraction ("Let's check out with <BRAND>"), screenshot capture, Supabase log to `payment_link_tests`. Exit codes 0 (pass) / 1 (fail) / 2 (captcha_blocked) / 3 (error). |
| **Gate 3 schema (NEW 2026-04-11)** | `sql/006_payment_link_tests.sql` | 113 | `public.payment_link_tests` table, 4 indexes (url_recent, plan, status_failing, project_created), RLS with service-role full-access + tenant-isolation policies. **PENDING SOLON APPLY.** |
| CLI flags (NEW) | `--skip-gate3`, `--gate3-window-hours` | — | Dangerous flags for dry-run bypass, never to ship with. |
| Docs | `RELAUNCH_CLAUDE_CODE.md` | 68 | Relaunch mechanics + hard rules + post-merge state. |

**What the proposal generator does NOT do yet (gap for Thread 2):**
- Does not take **call notes** as input — only a pre-written `spec.yaml`. Converting call notes into a spec.yaml is the Thread 2 new work.
- Does not have per-client voice / tone templates beyond the JDJ template family.
- Does not generate SOWs (scope-of-work) separately from the proposal — only the combined proposal+SOW DOCX.

---

## 6. Merchant stack blueprint (Phase 1 DR + Phase 2 application package)

Status: **SHIPPED tonight (2026-04-11), war-room graded A 9.49/10**. Parked in `plans/` (gitignored; mirrored to VPS).

| File | Purpose |
|---|---|
| `plans/PLAN_2026-04-11_merchant-stack.md` | Full DR with Phases 1-5, ranked top-3 primary + top-3 MoR + top-3 backup, fee math at 4 MRR brackets, approval probability reasoning, war-room grade. Recommendation: **PaymentCloud + Dodo Payments + Durango** in parallel on day 1, with PayPal Business + Wise Business as backup rails. |
| `plans/merchant-stack-applications/00_SOLON_ACTION_CHECKLIST.md` | 13-item atomic Solon task list (EIN, articles, ID, bank statements, cover letter sigs, etc.) |
| `plans/merchant-stack-applications/01_PaymentCloud_cover_letter_DRAFT.md` | Pre-war-room draft cover letter with prior-shutdown disclosure |
| `plans/merchant-stack-applications/02_Dodo_Payments_cover_letter_DRAFT.md` | Same, Dodo-specific |
| `plans/merchant-stack-applications/03_Durango_cover_letter_DRAFT.md` | Same, Durango-specific |
| `plans/merchant-stack-applications/04_website_compliance_audit.md` | Partial audit — SPA blocker on Lovable-hosted site, Chrome MCP follow-on queued |

**Phase 3 integration spec, Phase 4 fallback plan, Phase 5 migration plan** — all architected in the main DR file but not yet expanded into separate implementation docs.

**Hard blocker on this thread:** Perplexity quota (for future DR runs) + Solon signatures/KYC docs.

---

## 7. Mirror + deployment infrastructure

Status: **SHIPPED**. 4-way mirror: Mac ↔ VPS working ↔ VPS bare ↔ GitHub.

| Component | Location | State |
|---|---|---|
| Mac repo | `/Users/solonzafiropoulos1/titan-harness` (symlinked from `~/bin/titan-harness`) | HEAD = `f97a7c1` |
| VPS working tree | `/opt/titan-harness/` | HEAD = `f97a7c1` |
| VPS bare repo | `/opt/titan-harness.git/` | HEAD = `f97a7c1` |
| GitHub mirror | `AiMarketingGenius/titan-harness` | HEAD = `f97a7c1` (auto-mirrored via post-receive hook on bare repo) |
| Post-receive hook | `/opt/titan-harness.git/hooks/post-receive` | `git push --mirror github` on every push, logged to `/var/log/titan-harness-mirror.log` |
| Titan-policy repo | `AiMarketingGenius/titan-policy` | Planned (Phase G.1.4 mid-flow), not yet created |
| Deploy key | VPS `/root/.ssh/titan_github_mirror` | Installed on titan-harness GitHub repo |
| Symlink | `~/bin/titan-harness` → `~/titan-harness` | Stable |
| Legacy backup | `~/bin/titan-harness.legacy.bak` | Pre-mirror Mac install, safe to delete |

**Safety guards:** never launch Claude Code from iCloud path (silent eviction risk). Relaunch mechanics in `RELAUNCH_CLAUDE_CODE.md`.

---

## 8. Policy / contracts

| File | Purpose |
|---|---|
| `CORE_CONTRACT.md` (187 lines) | Canonical harness contract. Section 1 capacity, 2 war-room, 3 substrate, 4 model routing, 5 context, 6 logging, 7 idea pipeline default-on. |
| `policy.yaml` (283 lines after tonight's war_room.slack_grading_* additions) | All runtime config: capacity block, war_room block (incl. slack_grading), mp_runs block, idea_to_execution block, model_router.tasks table, slack channels. |
| `lib/policy-loader.sh` (430 lines) | Parses policy.yaml → `POLICY_*` env vars that every bash/Python caller reads. |
| `SESSION_PROMPT.md` (70 lines) | Canonical session boot text pasted by Solon on fresh Claude Code sessions. |
| `.gitignore` | Excludes `__pycache__/`, `*.pyc`, `*.bak.*`, `plans/`, secrets. |

---

## 9. Sprint / decision / memory system

Status: **SHIPPED** — runs via the MCP server at `mcp__0f44c9ec-a530-47dc-a8b8-4db51c221197`.

- `get_bootstrap_context` — injects standing rules + sprint state + recent decisions into new sessions
- `get_sprint_state EOM` — current kill chain, blockers, completion %, infrastructure status, last decision
- `get_recent_decisions` — 20-decision rolling window
- `get_task_queue` — filtered by status/priority/project/assignee
- `queue_operator_task` / `claim_task` / `update_task` — operator task queue with approval workflow
- `log_decision` — semantic decision log with embeddings + conflict detection
- `flag_blocker` / `resolve_blocker` — blocker tracker
- `search_memory` — vector search across all operator memories
- `generate_carryover` — session handover doc generator
- `perplexity_review` — (currently 401'd) delegated review tool

**What this does NOT do:** it does not replace titan-harness's own `war_room_exchanges` + `mp_runs` + `idea_to_exec_runs` tables — it's a lighter operator-level layer sitting above.

---

## 10. Docs + baselines

| File | Purpose |
|---|---|
| `README.md` | Repo entry point |
| `CORE_CONTRACT.md` | Harness contract (see §8) |
| `IDEA_TO_EXECUTION_PIPELINE.md` | IdeaBuilder spec (see §2) |
| `RELAUNCH_CLAUDE_CODE.md` (NEW 2026-04-11) | How to relaunch a Titan session cleanly |
| `P9.1_CUTOVER_REPORT.md` | Phase 9.1 cutover notes |
| `SESSION_PROMPT.md` | Fresh-session boot text |
| `INVENTORY.md` (this file) | 5-day build inventory |
| `baselines/P0_baseline.md` | Pre-rollout baseline |
| `baselines/post_rollout_2026-04-11_baseline.md` | Post-rollout baseline (deltas from P0) |

---

## 11. Git log (last 5 days, HEAD-relative)

```
f97a7c1  War-room Slack dispatcher: Perplexity quota bypass path         (2026-04-11, tonight)
f1ab8b0  Gate 3 payment link tester + mirror relaunch docs                (2026-04-11, tonight)
28d3b70  Merge origin/master into vps-drift-2026-04-11                    (2026-04-11)
a87a0f0  Capture VPS working-tree drift: perf rollout + IdeaBuilder + war room + capacity + policy  (2026-04-11, 8906 insertions)
b446856  Option A+B: proposal generator with build-time payment-link gate (2026-04-10)
aa8dfe8  MP-1 Phase 8: manifest consolidator + mp-runner bug fixes         (2026-04-10)
84d4a1f  War Room A-grade overhaul: shippability rubric + parser hardening + RLS  (2026-04-10)
26dccae  Phase G.4: apply harness to MP-1/MP-2 execution (Option A wrapper) (2026-04-10)
b17df3c  Revert HOW_TO_USE.md: Solon explicitly does not want manuals      (2026-04-10)
8ba5731  Add HOW_TO_USE.md — plain-English walkthrough (reverted next)     (2026-04-10)
6a551a2  War Room: suppress Slack ping on A/B grades (noise filter)        (2026-04-10)
112295e  Phase G.3: War Room — Titan ↔ Perplexity auto-refinement loop    (2026-04-10)
3ba6c04  Phase G.2: policy-as-code loader + war_room config block          (2026-04-10)
5cf0a2c  Phase G.1 idea-finalization hook: lock-it trigger + queue drainer + helpers  (2026-04-10)
dc88369  titan-harness v1.0: cross-instance Claude Code hooks              (2026-04-09)
```

~9,500 lines of production code + configs + schema + docs shipped across 15 commits.

---

## 12. Gap map: Solon's 5-thread autopilot ask vs. what already exists

This is the mapping that matters for Perplexity's next recommendation pass. Perplexity suggested 5 automation threads. Here's what's already built and what's the actual delta.

### Thread 1 — Sales Inbox + CRM Agent

| Sub-item in Perplexity's ask | Already built? | Gap (what Titan needs to build) |
|---|---|---|
| Watch sales Gmail inbox | ❌ no | Entire Gmail Pub/Sub watcher + OAuth bootstrap + webhook handler |
| Watch Slack DMs | ❌ no | Slack Events API subscription for DMs to Solon's user |
| Auto-tag and prioritize leads | ❌ no | `lib/sales_inbox/classifier.py` + `sql/007_leads.sql` + lead scoring rules |
| Draft replies | ❌ no | `lib/sales_inbox/drafter.py` — but uses existing `WarRoom` + `lib/llm_client` substrate, so it's 1 module not a stack |
| Update CRM / deal board | ❌ no (no CRM exists) | `leads` table serves as lightweight deal board |
| Auto-followups | ❌ no | `lib/sales_inbox/cadence.py` + cron timer |
| "Prepare me for this call" briefs | ❌ no | `scripts/precall_brief.py` + Calendar poll |
| Use War Room A-grade floor | ✅ yes | Existing `WarRoom.grade()` is reused — zero new code here |
| Use LiteLLM routing for classification | ✅ yes | Existing `lib/llm_client.complete()` reused |
| Use Supabase for state | ✅ yes | Standard harness pattern |
| Use Slack for notifications | ✅ yes | `lib/war_room._post_slack()` helper reused |

**Net: ~80% new code, 20% reuse.** DR already drafted tonight at `plans/PLAN_2026-04-11_sales-inbox-crm-agent.md` (war-room A 9.46/10).

### Thread 2 — Proposal + SOW Auto-Drafting

| Sub-item in Perplexity's ask | Already built? | Gap |
|---|---|---|
| Generate A-grade proposal DOCX from a spec | ✅ **YES** | `scripts/build_proposal.py` ships this. 608 lines, Gates 1+2+3 already live. |
| Use existing templates | ✅ **YES** | `templates/proposals/jdj_proposal_v4_linksfix.docx` exists |
| Plug into Gate 3 "only payment-ready deals" | ✅ **YES** | Gate 3 shipped tonight (f1ab8b0). Exit code 5 on miss. |
| Build-time payment link verification | ✅ **YES** | Gate 1 + Gate 2 + Gate 3 |
| War-room grade the proposal | ⚠️ not currently | build_proposal doesn't call WarRoom. Could be added trivially (one module import + one method call at render-time) |
| **From a short description of prospect + call notes, auto-generate a spec.yaml** | ❌ **NO — this is the actual gap** | `lib/proposal_spec_generator.py` — takes `{prospect_description, call_notes_text}` → yields a valid `spec.yaml` that build_proposal.py can consume. Uses existing Fireflies transcripts as input when available. |
| SOW as separate deliverable | ❌ no | `templates/proposals/sow_*.docx` + `--output-sow` flag on build_proposal |

**Net: ~20% new code, 80% reuse.** The gap is a single new module (`proposal_spec_generator.py`) + a small wiring change in `build_proposal.py` to add a `--from-call-notes` intake path. NOT a full rewrite.

### Thread 3 — Recurring Marketing Engine

| Sub-item | Already built? | Gap |
|---|---|---|
| Ingest content/insights from AMG sources | ❌ no | `lib/content_sources/` — scraper for AMG blog + Solon's recent posts |
| Generate email copy, LinkedIn post, X post, short-form video | ❌ no | `lib/marketing/package_builder.py` — calls LLM per surface with surface-specific prompts |
| Short-form video generation | ❌ no | Opus Clip API integration (clip repurposing) + HeyGen API (avatar shorts) |
| n8n flow for multi-surface publish | ❌ no | New `n8n/flows/weekly_content_package.json` |
| Approval gate (Solon approves once, then schedules) | ❌ no | Slack approval dialog via `chat.postMessage` + polling for reaction |
| Schedule and publish | ❌ no | n8n native schedule trigger + per-surface nodes (LinkedIn Company, X v2, email provider, YouTube/Shorts) |
| War-room grade each surface's copy to A | ✅ reused | WarRoom substrate |
| LLM routing | ✅ reused | lib/llm_client |
| Supabase content state | ✅ reused | standard pattern, new tables |

**Net: ~90% new code, 10% reuse.** This is the biggest gap. Needs 4-5 new modules + an n8n flow + API keys.

### Thread 4 — Back-Office Autopilot

| Sub-item | Already built? | Gap |
|---|---|---|
| Reconcile paid invoices vs expected | ❌ no | `scripts/money_reconcile.py` — joins PayPal transaction export + Supabase `leads`/`sales_threads` + invoice table |
| Flag churn / late payers | ❌ no | `sql/008_subscription_state.sql` + `scripts/churn_scan.py` |
| Weekly money + risk report | ❌ no | `scripts/money_risk_report.py` — generates a 1-page markdown, posts to Solon's Slack DM |
| Slack delivery | ✅ reused | standard helper |
| LLM summarization | ✅ reused | lib/llm_client |

**Net: ~85% new code, 15% reuse.**

### Thread 5 — Client Reporting Autopilot

| Sub-item | Already built? | Gap |
|---|---|---|
| GA4 monthly metrics per client | ❌ no | `lib/metrics_sources/ga4.py` — google-analytics-data SDK |
| Search Console impressions/clicks per client | ❌ no | `lib/metrics_sources/gsc.py` |
| Lead count per client | ⚠️ partial | Will exist after Thread 1 `leads` table ships |
| "What we did, what's next" narrative | ❌ no | `lib/client_reporting/narrative.py` — pulls from `mp_runs`, `plans/`, git log for the client's project_id |
| Monthly report markdown or PDF | ❌ no | `scripts/client_monthly_report.py` |
| Red-status escalation | ❌ no | Simple threshold rules + Slack DM |
| Auto-send to client | ⚠️ gated | Requires sending permission (per CORE_CONTRACT) — stay in drafts-only mode first |

**Net: ~85% new code, 15% reuse.**

---

## 13. Non-reused items Solon should know about (other standing work)

### Still in flight (not part of the 5-thread ask)

- **Phase G.1.4:** Titan-policy repo creation + deploy key + post-receive hook. Half-done (titan-harness repo done, titan-policy not yet created on GitHub).
- **Phase G.2:** harness policy YAML. **Done** (committed in 3ba6c04).
- **Phase G.3:** iPhone edge function. Not started.
- **Phase G.4:** apply harness to MP-1/MP-2 execution. **Done** (committed in 26dccae).
- **Atlas Layer 2 portal build:** queued, Solon directive 2026-04-10, blocked on sweep SOP being absorbed.
- **Voice AI Path B (RunPod worker):** deprioritized per 2026-04-11 directive, sits after MP-4 + CORDCUT 4+5.
- **CORDCUT 4+5 (Portal Rebuild + Multi-Lane Mirror v1.1):** 5 prereqs blocking (no Caddy block, no source tree, missing spec, no CT-0408-24 artifacts, "Lovable edits complete" unconfirmed).
- **Shop UNIS extras (CT-0410-01):** internal linking sweep + product page optimization + AI Overview expansion. Pre-approved but not started.
- **Client Sweep SOP:** killed 2026-04-10, superseded by Atlas Layer 2 scope.

### Completed this week that isn't directly in §1-10

- **JDJ proposal rebuild** — new template + patch_jdj_docx.py to fix a layout bug that the Jinja token substitution couldn't reach
- **MP-runner bug fixes** — multiple (committed with aa8dfe8)
- **Policy-loader.sh** — 430-line parser that replaces ad-hoc env var exports
- **Services files** — systemd timer + macOS launchd plist for the ideas drainer
- **Baselines** — P0 pre-rollout snapshot + post-rollout comparison file in `baselines/`

---

## 14. Pending Solon action items (hard blockers across threads)

Copied from `~/titan-session/NEXT_TASK.md`:

1. **Apply `sql/006_payment_link_tests.sql`** in Supabase SQL Editor (blocks Gate 3 end-to-end)
2. **Gate 3 end-to-end verification** via `scripts/test_payment_url.py` on the VPS (after #1)
3. **Batched 2FA/credential session** for MP-1 Phase 1/2/4/5 (~15 min: claude.ai sessionKey + Perplexity cookie header + Loom creds + Gmail OAuth consent)
4. **🔴 Perplexity API quota exhausted** — top up at https://www.perplexity.ai/settings/api
5. **Slack bot token + Perplexity Slack app install** (optional quota-bypass path for war-room)

### New action items added by the autopilot-suite work (after tonight's run completes):

6. **Gmail OAuth + Google Cloud project + Pub/Sub topic** for Thread 1 sales inbox agent
7. **Slack Events API app + scopes** (`im:history`, `im:read`) for Thread 1 Slack DM watching
8. **Content source URLs** for Thread 3 marketing engine (AMG blog feed, Solon's LinkedIn activity, any newsletter archive)
9. **Opus Clip + HeyGen API keys** for Thread 3 short-form video
10. **LinkedIn Company + X API v2 Basic tier ($200/mo)** for Thread 3 publishing
11. **Email provider API** (Resend, Postmark, or continue existing Google Workspace SMTP) for Thread 3 email surface
12. **PayPal transactions export access or Invoicing API token** for Thread 4 reconciliation
13. **GA4 + GSC service-account credentials** for Thread 5 client metrics
14. **Client roster** (which active clients get Thread 5 monthly reports — list of names + project_ids)

---

## 15. What Perplexity should know when grading the autopilot-suite recommendation

1. **The harness substrate is already rich** — there is a war-room, an A-grade floor, a capacity gate, a model router, a context builder, an LLM client, a Supabase schema with RLS, an idea pipeline, cron-scheduled orchestrators, Slack integration, a 4-way mirror. None of this needs to be rebuilt.
2. **The proposal builder is already live with 3 gates** — don't suggest rebuilding `build_proposal.py`. The gap is the call-notes → spec.yaml front-door (~200 lines).
3. **Perplexity's own API is currently dead** due to quota. Any autopilot component that depends on live Perplexity grading should ship with the `lib/war_room_slack.py` path as an alternative, or fall back to Claude-Sonnet-as-grader with an explicit downgrade flag.
4. **Solon's action budget is scarce.** Prioritize automations where the Solon-required setup is under 30 minutes per thread. Avoid threads that need multi-day OAuth verification or enterprise account creation.
5. **Silent COO mode applies.** No chatter, no preamble, only Slack pings on DR complete / A-grade / needs-Solon-override.
6. **Sending messages on Solon's behalf is gated** — drafts-only until Solon explicitly approves a "ship it" action. This is a hard rule from CORE_CONTRACT and the Claude Code action_types contract.
7. **Everything lives in Supabase + titan-harness + VPS + GitHub.** No new SaaS platforms unless there's a concrete blocker that only a new SaaS solves.

---

## 16. Headcount-of-code summary

```
lib/ (13 files)        5,806 lines Python/shell
scripts/ (4 files)     1,687 lines Python
bin/ (20 files)        ~2,800 lines bash/Python
sql/ (16 files)        ~950 lines
docs (6 .md files)     ~900 lines markdown
policy.yaml            283 lines
templates/             2 DOCX files
─────────────────────────────────────────────
Total (committed):     ~12,500 lines shipped over 5 days
Pre-mirror VPS drift:  +8906 additional lines captured in a87a0f0
Tonight's additions:   +1,382 lines (Gate 3 + war-room slack dispatcher)
```

---

**End of inventory.** Updated 2026-04-11 by Titan during the overnight autopilot-suite DR run.
