# HERCULES BACKFILL REPORT

**Date:** 2026-04-11
**Operator:** Titan (Claude Opus 4.6 1M)
**Scope:** one-time backfill pass over the recent build era (last ~2-3 weeks, roughly commits `dc88369` → `a8ef728`) to confirm every structural or permanent directive from Solon is encoded in the harness (`CORE_CONTRACT.md`, `CLAUDE.md`, `SESSION_PROMPT.md`, `policy.yaml`, `lib/*.py`, `bin/*.sh`, `sql/NNN_*.sql`), respecting the conflict-check rule (`CORE_CONTRACT §0.7`).
**Method:** read the current harness files, scanned `git log --since="3 weeks ago"`, cross-referenced against `INVENTORY.md` + `RADAR.md`, and for each identified directive checked harness coverage. Any item already covered is reported as `Auto-Harness: existing rule covers this`. Any gap is either harnessed now (and the file committed + mirrored) or flagged as a `TODO`.

---

## Status legend

- ✅ **Already covered** — existing harness rule satisfies this directive; no new change needed (conflict-check §0.7 path)
- 🆕 **Harnessed now** — newly encoded in this backfill pass
- ⚠️ **TODO** — structural gap, needs a dedicated DR or follow-on harness change

---

## A. Roles + governance

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| A1 | Solon = CEO / Vision + Sales | 2026-04-11 Mega Directive | ✅ | `CORE_CONTRACT.md §0`, `CLAUDE.md §1` |
| A2 | Titan = COO / Head of Execution in `~/titan-harness` | 2026-04-11 Mega Directive | ✅ | `CORE_CONTRACT.md §0`, `CLAUDE.md §1` |
| A3 | Aristotle = Strategy + Research co-agent via `#titan-aristotle` Slack | 2026-04-11 Part 2 | ✅ | `CORE_CONTRACT.md §0` routing rule + `policy.yaml autopilot.aristotle_*` + `lib/aristotle_slack.py` (commit `4e59440`) |
| A4 | Aristotle is first-class (not stateless API); direct `api.perplexity.ai` is fallback only | 2026-04-11 Part 2 | ✅ | `CORE_CONTRACT.md §0` + `CLAUDE.md §1` routing rule |
| A5 | Auto-post triggers (inventory/RADAR/DR/control-loop/major commit) | 2026-04-11 Part 2 | ✅ | `policy.yaml autopilot.aristotle_auto_post_on:` |

---

## B. Brevity + conversational contract

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| B1 | Max 3 bullets, under 200 tokens, no self-narration | 2026-04-11 Mega Directive | ✅ | `CLAUDE.md §2`, `SESSION_PROMPT.md` Speed+Capacity block |
| B2 | Status format: `Now: ... Next: ... Blocked on: ...` | 2026-04-11 | ✅ | `CLAUDE.md §2` |
| B3 | Blaze Mode + Fast Mode default ON | Phase P11 (blaze directive) | ✅ | `CORE_CONTRACT.md §6`, `policy.yaml blaze_mode:`, `policy.yaml fast_mode:`, `SESSION_PROMPT.md` |
| B4 | Fast Mode exceptions: plan / architecture / war_room_revise / deep_debug | Phase P11 | ✅ | `policy.yaml fast_mode.exception_task_types` |
| B5 | Heavy analysis only on explicit trigger ("go deep", "war room this", "deep dive") | 2026-04-11 | ✅ | `policy.yaml blaze_mode.trigger_phrases_for_deep_mode` |

---

## C. RADAR + execution priority

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| C1 | `RADAR.md` is canonical "what's open" — every idea/DR/MP must exist there | 2026-04-11 Mega Directive | ✅ | `CLAUDE.md §3`, `RADAR.md` |
| C2 | Execution priority: Sales Inbox → MP-1/MP-2 → Atlas P1 | 2026-04-11 | ✅ | `CLAUDE.md §4`, `policy.yaml autopilot.execution_priority` |
| C3 | Parked > 7 days triggers a Solon check-in question | 2026-04-11 | ✅ | `CLAUDE.md §3`, `policy.yaml autopilot.radar_parked_days_threshold: 7` |
| C4 | Auto-refresh RADAR every 30 min + on boot | 2026-04-11 | ✅ | `policy.yaml autopilot.radar_refresh_cron: "*/30 * * * *"`, `scripts/radar_refresh.py`, `bin/titan-boot-audit.sh` |
| C5 | Daily `RADAR_SUMMARY.md` + Slack-pasteable status | 2026-04-11 | ✅ | `policy.yaml autopilot.radar_summary_path` |
| C6 | Parked-on-purpose P9.1 Docker worker pool soak | 2026-04-11 directive | ✅ | `policy.yaml autopilot.p91_docker_worker_pool_soak_enabled: false`, RADAR "Open Infra / Harness Items" |
| C7 | Parked-on-purpose n8n queue-mode cutover | 2026-04-11 directive | ✅ | `policy.yaml autopilot.n8n_queue_mode_cutover_enabled: false`, RADAR |

---

## D. Library of Alexandria (doctrine index)

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| D1 | Single catalog layer, 7 canonical sections | 2026-04-11 Part 3 | ✅ | `CORE_CONTRACT.md §0.5`, `library_of_alexandria/ALEXANDRIA_INDEX.md` (commit `b0977ec`) |
| D2 | Thin catalog, NOT a copy — raw bytes stay in physical homes | 2026-04-11 | ✅ | `CORE_CONTRACT.md §0.5`, section manifests |
| D3 | Doctrine placement rule (repo root allowlist + `plans/`, `baselines/`, `templates/`, `library_of_alexandria/<section>/`) | 2026-04-11 | ✅ | `CORE_CONTRACT.md §0.5`, `bin/alexandria-preflight.sh` |
| D4 | Promotion-to-canon flow via `lib/alexandria.py --promote` + Slack ping | 2026-04-11 | ✅ | `lib/alexandria.py`, `lib/aristotle_slack.post_update` |

---

## E. Hercules Triangle (Auto-Harness + Auto-Mirror)

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| E1 | Callsign HERCULES TRIANGLE: Intent → Harness → Mirror, non-bypassable | 2026-04-11 | ✅ | `CORE_CONTRACT.md §0.6`, `CLAUDE.md §10`, `SESSION_PROMPT.md` (commit `c55b941`) |
| E2 | Auto-Harness: directive-type → harness target table | 2026-04-11 | ✅ | `CORE_CONTRACT.md §0.6 Step 2` |
| E3 | Auto-Mirror: 5 endpoints (Mac / VPS working / VPS bare / GitHub / MCP memory) | 2026-04-11 | ✅ | `CORE_CONTRACT.md §0.6 Step 3`, VPS post-receive hook, `/var/log/titan-harness-mirror.log` |
| E4 | Drift warning + confirmation phrase | 2026-04-11 | ✅ | `CORE_CONTRACT.md §0.6`, `CLAUDE.md §10` |
| E5 | Conflict-check hard rule precedes Harness step | 2026-04-11 Part 3 | ✅ | `CORE_CONTRACT.md §0.7`, `CLAUDE.md §10` |

---

## F. Solon OS Cold Boot + Power Off

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| F1 | Every new Claude Code session on `~/titan-harness` is a Solon OS cold boot — auto-run audit, no wake word, one-line greeting | 2026-04-11 | ✅ | `CLAUDE.md §7`, `SESSION_PROMPT.md`, `bin/titan-boot-audit.sh`, SessionStart hook (commits `0421881` + `a8ef728`) |
| F2 | Power off trigger phrases + clean shutdown sequence + verbatim confirmation line | 2026-04-11 | ✅ | `CLAUDE.md §11`, `SESSION_PROMPT.md`, `bin/titan-poweroff.sh` (commit `54b4c97`) |
| F3 | Standing rules patched silently if missing from system prompt | 2026-04-11 | ✅ | `CLAUDE.md §7` + top of file self-patching clause |

---

## G. Capacity CORE CONTRACT

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| G1 | 12-key capacity block required in every deployment | Phase G.5 (2026-04-10) | ✅ | `CORE_CONTRACT.md §1-2`, `policy.yaml capacity:` |
| G2 | `harness-preflight.sh` + `check-capacity.sh` mandatory pre-flight for every runner | Phase G.5 | ✅ | `CORE_CONTRACT.md §2`, `bin/harness-preflight.sh`, `bin/check-capacity.sh`, `lib/capacity.py` |
| G3 | Heavy-task classification + soft/hard block behavior | Phase G.5 | ✅ | `CORE_CONTRACT.md §2`, `titan_queue_watcher.py` wiring |
| G4 | No client "Titan as COO" deployment bypass | Phase G.5 | ✅ | `CORE_CONTRACT.md §3` |

---

## H. IDEA → DR → PLAN → EXECUTE pipeline

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| H1 | Automated pipeline for every new major project | 2026-04-11 | ✅ | `CORE_CONTRACT.md §7`, `IDEA_TO_EXECUTION_PIPELINE.md` |
| H2 | Idea intake: lock-it hook + 🔒 emoji + `ideas` table | Phase G.1 (2026-04-10) | ✅ | `hooks/user-prompt-idea.sh`, `policy.yaml idea_capture:`, `sql/001_ideas_table.sql` (commit `5cf0a2c`) |
| H3 | Secret sanitization on idea capture | Phase G.1 | ✅ | `policy.yaml idea_capture.redact_patterns` |
| H4 | DR generator via Perplexity sonar-pro through LiteLLM | 2026-04-11 | ✅ | `lib/idea_to_dr.py`, `sql/110_idea_pipeline.sql` |
| H5 | Per-phase war-room grading + A-grade auto-advance | 2026-04-11 | ✅ | `CORE_CONTRACT.md §7`, `lib/idea_to_execution.py` |
| H6 | Cron `*/2 * * * *` orchestrator | 2026-04-11 | ✅ | `bin/idea-to-execution.sh`, crontab on VPS |
| H7 | Slack policy: DR complete / phase A-graded / needs_solon_override only | 2026-04-11 | ✅ | `CORE_CONTRACT.md §7`, `policy.yaml idea_to_execution.slack_events` |

---

## I. War Room (A-grade floor)

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| I1 | 9.4/10 minimum quality floor on every deliverable | 2026-04-10 directive | ✅ | `policy.yaml war_room.min_acceptable_grade: A`, `lib/war_room.py` (commit `84d4a1f`) |
| I2 | 10-dim rubric + max 5 refinement rounds + $0.50/round cost cap | Phase G.3 | ✅ | `policy.yaml war_room:`, `lib/war_room.py` |
| I3 | Sonnet reviser (not Haiku) for A-grade revisions | 2026-04-10 | ✅ | `policy.yaml war_room.reviser_model: claude-sonnet-4-6` |
| I4 | Slack-routed grading path for Perplexity quota bypass | 2026-04-11 | ✅ | `lib/war_room_slack.py` (commit `f97a7c1`), `policy.yaml war_room.slack_grading_*` |
| I5 | Suppress Slack ping on A/B grades (noise filter) | 2026-04-10 | ✅ | `lib/war_room.py` (commit `6a551a2`) |

---

## J. MP-1 HARVEST / MP-2 SYNTHESIS under harness

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| J1 | MP runs tracked in `mp_runs` table, scoped by project_id | Phase G.4 (2026-04-10) | ✅ | `policy.yaml mp_runs:`, `sql/005_mp_runs.sql`, `bin/mp-runner.sh` (commit `26dccae`) |
| J2 | Per-MP spend cap ($150 for MP-2) | Phase G.4 | ✅ | `policy.yaml mp_runs.spend_hard_cap_usd: 150` |
| J3 | Auto war-room on planning/synthesis phases only | Phase G.4 | ✅ | `policy.yaml mp_runs.war_room_phases` |
| J4 | MP-1 Phase 8 manifest consolidator | 2026-04-10 | ✅ | `bin/mp-runner.sh` + manifest logic (commit `aa8dfe8`) |

---

## K. Autopilot Suite (5 threads)

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| K1 | Thread 1 Sales Inbox + CRM Agent DR (A 9.46) | 2026-04-11 | ✅ | `plans/PLAN_2026-04-11_sales-inbox-crm-agent.md`, `lib/sales_inbox.py`, `policy.yaml autopilot.sales_inbox_*` (commit `bea1740`) |
| K2 | Thread 2 Proposal from Call Notes DR (A 9.53) | 2026-04-11 | ✅ | `plans/PLAN_2026-04-11_proposal-from-call-notes.md`, `lib/proposal_spec_generator.py` stub, `policy.yaml autopilot.proposal_from_notes_*` |
| K3 | Thread 3 Recurring Marketing Engine DR (A 9.40) | 2026-04-11 | ✅ | `plans/PLAN_2026-04-11_recurring-marketing-engine.md`, `lib/marketing_engine.py`, `policy.yaml autopilot.marketing_engine_*` |
| K4 | Thread 4 Back-Office Autopilot DR (A 9.45) | 2026-04-11 | ✅ | `plans/PLAN_2026-04-11_back-office-autopilot.md`, `lib/back_office.py`, `policy.yaml autopilot.back_office_*` |
| K5 | Thread 5 Client Reporting Autopilot DR (A 9.40) | 2026-04-11 | ✅ | `plans/PLAN_2026-04-11_client-reporting-autopilot.md`, `lib/client_reporting.py`, `policy.yaml autopilot.client_reporting_*` |
| K6 | All threads default DISABLED, kill-switches per thread | 2026-04-11 | ✅ | `policy.yaml autopilot.*_enabled: false` |
| K7 | Schema for all 5 threads | 2026-04-11 | ✅ | `sql/007_autopilot_suite.sql` (pending Solon apply — RADAR blocker) |

---

## L. Gate 3 payment-link pipeline + merchant stack

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| L1 | Gate 3 pre-build payment-link verification | 2026-04-11 | ✅ | `scripts/test_payment_url.py`, `sql/006_payment_link_tests.sql` (pending Solon apply) (commits `b446856`, `f1ab8b0`) |
| L2 | Proposal generator with build-time payment-link gate | 2026-04-10 | ✅ | `lib/build_proposal.py` |
| L3 | Merchant Stack Phase 1 DR (A 9.49) — PaymentCloud / Dodo / Durango | 2026-04-11 | ✅ | `plans/PLAN_2026-04-11_merchant-stack.md`, `plans/merchant-stack-applications/` |

---

## M. Performance rollout substrate (P2-P13)

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| M1 | LiteLLM gateway as single LLM ingress | P2 | ✅ | `/opt/titan-processor/litellm/`, `INVENTORY.md §1` |
| M2 | Model router (task_type → model) | P3 | ✅ | `lib/model_router.py`, `policy.yaml models:` |
| M3 | Context builder + memory-not-re-paste | P4 | ✅ | `lib/context_builder.py`, `CONTEXT_BUILDER_BYPASS` audit |
| M4 | LLM batch + async pool | P5 / P8 | ✅ | `lib/llm_batch.py`, `lib/async_pool.py` |
| M5 | LLM client with Supabase logging | P6 | ✅ | `lib/llm_client.py`, `llm_calls` table |
| M6 | Prompt pipeline DAG | P7 | ✅ | `lib/prompt_pipeline.py` |
| M7 | Capacity substrate (P12) | P12 | ✅ | `lib/capacity.py`, `bin/check-capacity.sh`, `bin/harness-preflight.sh` |
| M8 | Fast Mode toggle + audit | P13 | ✅ | `sql/100_fast_mode.sql`, `fast_mode_events` table |

---

## N. Product doctrine (this session, 2026-04-11 Part 4)

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| N1 | Three-SKU product ladder (AMG subs / white-label / Solon OS custom 3a+3b) | 2026-04-11 Part 4 | 🆕 | `plans/DOCTRINE_AMG_PRODUCT_TIERS.md` (this commit) + MCP memory `project_amg_product_tiers.md` |
| N2 | IP protection: tenant-API architecture, no-resale clauses, scrub trade secrets from templates | 2026-04-11 Part 4 | 🆕 | `plans/DOCTRINE_AMG_PRODUCT_TIERS.md` §2 (this commit) + MCP memory `feedback_ip_protection.md` |
| N3 | Never underprice custom builds — create-competition risk | 2026-04-11 Part 4 | 🆕 | `plans/DOCTRINE_AMG_PRODUCT_TIERS.md` §3 |
| N4 | Three SKUs need three separate landing pages / funnels | 2026-04-11 Part 4 | ⚠️ TODO | Requires RADAR item + landing-page DR (see §TODO.1) |
| N5 | White-label agency discount model | 2026-04-11 Part 4 | ⚠️ TODO | RADAR "Product / Pricing doctrine" → needs dedicated DR |

---

## O. Other recent era items

| # | Directive | Date / thread | Status | Harness location |
|---|---|---|---|---|
| O1 | Shop UNIS extras CT-0410-01 (internal linking sweep + product page opt) | 2026-04-10 | ✅ | `RADAR.md §Shop UNIS extras` — task row exists, pre-approved |
| O2 | Voice AI Path B RunPod worker deprioritized | 2026-04-11 | ✅ | `RADAR.md §Voice AI v2` — deprioritized note |
| O3 | Phase G.1.4 titan-harness GitHub mirror | 2026-04-11 | ✅ | Repo live at `AiMarketingGenius/titan-harness` |
| O4 | Phase G.1.4 titan-policy repo (pending) | 2026-04-11 | ✅ (tracked) | `RADAR.md §Solon OS substrate` — pending Solon |
| O5 | Atlas Layer 2 sweep SOP absorption | 2026-04-11 | ✅ (tracked) | `RADAR.md §Solon OS substrate` — pending |
| O6 | Cross-instance Slack routing live | 2026-04-11 | ✅ | `RADAR.md §Solon OS substrate` |
| O7 | AMG site compliance audit (partial, SPA blocked WebFetch) | 2026-04-11 | ✅ (tracked) | `RADAR.md §AMG site rebuild tracks` — Chrome MCP follow-on queued |
| O8 | CORDCUT 4+5 Portal Rebuild + Multi-Lane Mirror v1.1 | 2026-04-08 | ✅ (tracked) | `RADAR.md §CORDCUT 4+5` — 5 prereqs listed |
| O9 | Perplexity quota top-up action #4 | 2026-04-11 | ✅ (tracked) | `RADAR.md §Blocked on Solon #4` |
| O10 | Operational defaults (launch path, fast mode, parallelism, VPS-first) | 2026-04-11 | ✅ | MCP memory `feedback_operational_defaults.md` |

---

## TODO: structural gaps worth a stronger rule

### TODO.1 — Email send-verification preflight gate

**Gap:** Solon explicitly flagged email send-verification as a structural concern (same pattern as Gate 3 payment-link tester). Currently `lib/sales_inbox.py` has a stub, and Thread 3 `lib/marketing_engine.py` has a stub — neither has a pre-send verification gate. No `bin/email-send-preflight.sh` exists. No `sql/` migration defines an `email_send_tests` table.

**What's needed:**
- `sql/NNN_email_send_tests.sql` — table recording pre-send checks (SPF/DKIM/DMARC, unsubscribe link present, domain reputation, rate-limit bucket, content sanitization, placeholder substitution verified)
- `bin/email-send-preflight.sh` — preflight script callable from `lib/sales_inbox.py` and `lib/marketing_engine.py` before any outbound send
- `policy.yaml email_send:` block with hard/soft fail thresholds + kill switch
- `CORE_CONTRACT.md §8` (new section) enshrining "no outbound email without send-verification" as non-bypassable, parallel to §1 capacity and §7 IDEA pipeline

**Why not harnessed in this pass:** this is a new subsystem that deserves its own DR (design review) before code, not a rushed backfill. Added to RADAR under "Open Infra / Harness Items" as a P1 gap.

### TODO.2 — Three-SKU landing page doctrine → runtime pricing calculator

**Gap:** Product tier doctrine is now written (`plans/DOCTRINE_AMG_PRODUCT_TIERS.md`) but there is no runtime pricing calculator that enforces the tier boundaries (3a vs 3b price floors, white-label discount model). The Loom demo vision Solon described depends on a live proposal flow that quotes on the spot; that flow needs a harnessed pricing engine, not a spreadsheet.

**What's needed:**
- `lib/pricing_engine.py` — takes discovery answers (team size, stack size, pain points, urgency) and returns a scoped proposal number per SKU
- `policy.yaml pricing:` block with tier floors + discount matrix
- DR reviewed + graded A by Aristotle before build

**Why not harnessed in this pass:** depends on N4/N5 landing-page decisions + a dedicated pricing DR. Added to RADAR "Product / Pricing doctrine" section.

### TODO.3 — Cross-device session continuity (Mac ⇄ web ⇄ iPhone)

**Gap:** Solon wants "same conversation continues from Mac → iPhone → os.aimarketinggenius.io" as part of the demo experience. This is an implementation task, not a pure harness rule — but it needs a structural rule that says "all Atlas-facing frontends speak to Titan through a central session_id handshake, never direct Claude API." Without that rule, a lazy implementation could leak prompt-library / orchestration to the client side.

**What's needed:**
- Architectural rule in `CORE_CONTRACT.md` (tentative §9) — "Atlas frontends are thin; all reasoning routes through Titan on VPS; session state in Supabase keyed by `atlas_session_id`"
- Reference implementation note pointing to the existing `context_builder` + `llm_client` substrate
- Explicit link to the IP-protection doctrine (Section N)

**Why not harnessed in this pass:** Solon's vision is still forming; the rule should land after the first Atlas frontend DR is scoped. Flagged here so it doesn't get lost.

---

## Mirror verification

- **Mac working tree:** this commit
- **VPS working tree** `/opt/titan-harness/`: will be synced via `git fetch && merge --ff-only` post-push
- **VPS bare** `/opt/titan-harness.git`: receives via `git push origin master`, post-receive hook fires
- **GitHub mirror** `AiMarketingGenius/titan-harness`: auto-pushed by post-receive hook
- **MCP memory** `~/.claude/projects/.../memory/`: already updated earlier in this session (`project_amg_product_tiers.md`, `feedback_ip_protection.md`)

Mirror log tail expected: `mirror push OK` on `/var/log/titan-harness-mirror.log` after the push.

---

## Conclusion

The recent build era (commits `dc88369` → `a8ef728`, roughly 2026-03-27 → 2026-04-11) is **almost fully harnessed**. Every structural directive from the Mega Directive (roles + brevity + RADAR), Part 2 (Aristotle first-class), Part 3 (Library of Alexandria + Hercules Triangle + conflict-check), the Blaze Mode directive, the Capacity CORE CONTRACT, the IDEA pipeline, the Autopilot Suite, the War Room A-grade floor, and the Solon OS cold boot / power off sequence is encoded in at least one harness file (`CORE_CONTRACT.md`, `CLAUDE.md`, `SESSION_PROMPT.md`, `policy.yaml`, `lib/*.py`, `bin/*.sh`, `sql/NNN_*.sql`, or an MCP memory file).

**This pass harnessed three new items** (N1-N3: product tier doctrine + IP lockdown rule + pricing posture) into `plans/DOCTRINE_AMG_PRODUCT_TIERS.md` so they are repo-visible and not memory-only.

**Three structural TODOs were flagged** (email send-verification gate, pricing engine, Atlas frontend session continuity) — all added to RADAR, none urgent enough to block Thread 1 Sales Inbox or MP-1 harvest resume, but each worth a dedicated DR before implementation.

**Back to normal execution** with Auto-Harness + Auto-Mirror as the default per `CORE_CONTRACT.md §0.6`.

— Titan
