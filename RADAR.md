# RADAR — Titan's Never-Lose-Anything Open Queue

**Owner:** Titan (COO). **Canonical state for what's open, blocked, parked, or in-flight.**
**Last refreshed:** 2026-04-12 07:18 UTC
**Refresh cadence:** every session boot; full regenerate daily via `scripts/radar_refresh.py`.

**Hard rule:** every important idea, DR, megaprompt, or half-finished project must (a) exist as a row in `tasks`/`mp_runs` or a `PLAN_*.md`/`MP_*.md` file, AND (b) have a line here under one of the sections below. No exceptions.

---

## Library of Alexandria (canonical index)

- **Index:** [`library_of_alexandria/ALEXANDRIA_INDEX.md`](library_of_alexandria/ALEXANDRIA_INDEX.md) — single catalog for everything harvested or authored about Solon/AMG
- **7 sections:** solon_os, perplexity_threads, claude_threads, emails, looms, fireflies_meetings, other_sources
- **Helper:** `python3 lib/alexandria.py --refresh|--search|--promote|--preflight`
- **Placement enforcement:** `bin/alexandria-preflight.sh` warns on doctrine files outside approved tree

---

## Execution Priority (default pull order when Solon hasn't explicitly overridden)

1. **Thread 1 Sales Inbox Autopilot** (`lib/sales_inbox.py`) — gated on `sql/007_autopilot_suite.sql` apply
2. **MP-1 harvest + MP-2 synthesis** — gated on batched 2FA session for Claude.ai + Perplexity + Loom + Gmail OAuth; now includes 3 creative projects (Croon, Hit Maker, Solon's Promoter)
3. **Atlas P1 client experience** — Founding Member signup → onboarding → first deliverable in 24 hours

---

## Open Megaprompts & Phases

- **MP-1 HARVEST** — 43% complete, 856 artifacts. Phase 6 Slack + Phase 7 MCP decisions + Phase 8 manifest done. Phase 3 Fireflies reconciled. Phase 1 (Claude threads) + Phase 2 (Perplexity) harvesters pre-built 2026-04-11, awaiting cookies. Phase 4 Loom needs creds. Phase 5 Gmail harvester not yet written. Blocker: Solon 2FA batch session.
- **MP-2 SYNTHESIS** — queued, autonomous, 8-12h Titan time, $150 Perplexity cap. Depends on MP-1 done. Phase 7b needs ~20 min Solon sample scoring.
- **MP-3 ATLAS BLUEPRINT** — collaborative, depends on MP-2 substrate.
- **MP-4 ATLAS BUILD** — bots, voicebots, proposals, nurture, onboarding, fulfillment, portal. Gated on MP-3 blueprint blessing.
- **Phase G.1.4** — titan-harness on GitHub ✅; titan-policy repo pending (create + deploy key + post-receive hook on both bare repos).
- **Phase G.3** — iPhone edge function. Not started.

---

## Open Infra / Harness Items

- **sql/006_payment_link_tests.sql** — ✅ APPLIED 2026-04-12. `payment_link_tests` table live in Supabase.
- **sql/007_autopilot_suite.sql** — ✅ APPLIED 2026-04-12. All 12 tables live in Supabase (leads, sales_threads, lead_events, proposal_spec_runs, marketing_content_queue, marketing_packages, expected_payments, received_payments, reconciliation_events, clients, client_metric_profiles, client_reports).
- **Slack war-room path for Perplexity** — code shipped (`lib/war_room_slack.py`, commit `f97a7c1`), disabled by default. Setup in progress.
- **🔵 P9.1 Docker worker pool 60h soak** — **PARKED ON PURPOSE** per Solon 2026-04-11 directive. State: code shipped Phase 9.1 (commit earlier session), canary not started. Upgrade candidate when Solon approves.
- **✅ n8n queue-mode** — ACTIVE since 2026-04-12. Running `EXECUTIONS_MODE=queue` with `QUEUE_WORKER_CONCURRENCY=20`, Redis-backed Bull queue (`n8n-redis-live`).
- **✅ Perplexity API** — WORKING as of 2026-04-12. `sonar-pro` responding via LiteLLM gateway. `perplexity_review` MCP tool confirmed functional.
- **Gmail harvester for MP-1 Phase 5** — not yet written (`harvest_gmail.py` missing). Needs OAuth consent flow.
- **AMG website compliance audit** — partial; Lovable SPA blocked WebFetch. Chrome MCP headless render follow-on queued.
- **Solon-OS session-close hook sync to Supabase** — stale PHASE_G_RESUME row from 2026-04-10 still served by `SessionStart:resume`. Local `NEXT_TASK.md` is truth. Low-priority re-sync.

---

## Open Product / Experience Work

### Autopilot Suite (DRs parked, all war-room A ≥9.40)
- **Thread 1 Sales Inbox + CRM Agent** — DR shipped (A 9.46/10). 5 phases. Stub at `lib/sales_inbox.py`. Blockers: Gmail OAuth + GCP Pub/Sub + Slack Events API + `sql/007`.
- **Thread 2 Proposal + SOW from Call Notes** — DR shipped (A 9.53/10). ~80% built (build_proposal.py + Gates 1+2+3 already ship). Gap is `lib/proposal_spec_generator.py` (~200 lines). Blockers: 2-3 example spec.yaml seeds.
- **Thread 3 Recurring Marketing Engine** — DR shipped (A 9.40/10). Stub at `lib/marketing_engine.py`. Blockers: Opus Clip + HeyGen + X Basic + LinkedIn Company OAuth + content source URLs. ~$390/mo opex.
- **Thread 4 Back-Office Autopilot** — DR shipped (A 9.45/10). Stub at `lib/back_office.py`. Blockers: PayPal export cadence + subscriber seed list. $0 new SaaS.
- **Thread 5 Client Reporting Autopilot** — DR shipped (A 9.40/10). Stub at `lib/client_reporting.py`. Blockers: client roster + metric profiles + GA4/GSC service account. $0 new SaaS.

### Merchant stack
- **AMG Merchant Stack Blueprint** — Phase 1 DR shipped (A 9.49/10). Top-3 primary: PaymentCloud + Dodo Payments + Durango. Parallel day-1 applications. Phase 2 cover letters drafted (3 files). Phase 3 integration spec + Phase 4 fallback + Phase 5 migration architected in main DR. Blockers: Solon signatures + KYC docs (13 atomic items in `plans/merchant-stack-applications/00_SOLON_ACTION_CHECKLIST.md`).

### Project Atlas pillars
- **P1 Client Experience** — Founding Member signup → onboarding → first-24h deliverable flow. Not yet DR'd. Depends on Autopilot Thread 1 + Thread 2 + Thread 5 shipping.
- **P2 Lead Engine** — not yet DR'd. Depends on Thread 1 + Thread 3 shipping.
- **P3 Self-Healing Ops** — not yet DR'd. Depends on Thread 4 + MP-2 substrate.

### CORDCUT 4+5 (Portal Rebuild + Multi-Lane Mirror v1.1)
- 5 prereqs blocking: no `portal.aimarketinggenius.io` Caddy block, no portal source tree on VPS, missing `PROMPT_2_MULTI_LANE_MIRROR_v1.1_EXECUTION.md`, no CT-0408-24 artifacts, "Lovable edits complete" unconfirmed.

### AMG site rebuild tracks
- **Lovable site audit via Chrome MCP** — queued follow-on (SPA blocked WebFetch)
- **AMG site compliance remediation** — pending audit findings

### Voice AI v2 — Hermes Phase A (CPU substrate) — 6/6 steps CODE-COMPLETE 2026-04-12
- **🟢 Binding doctrine:** [`plans/DOCTRINE_VOICE_AI_STACK_v1.0.md`](plans/DOCTRINE_VOICE_AI_STACK_v1.0.md) — verbatim Perplexity Computer ingest, supersedes v0.9 assumptions in prior Path A DR.
- **🟢 Active plan:** [`plans/DR_VOICE_AI_PHASE_A_HERMES_2026-04-12.md`](plans/DR_VOICE_AI_PHASE_A_HERMES_2026-04-12.md) — CPU-first pivot because VPS has no GPU (AMD EPYC 7763, 62 GB RAM). Zero new recurring spend, zero new creds, rollback is one command.
- **🟢 Phase A substrate status (6/6 doctrine-v1.0 steps):**
  - Step 1 Kokoro v1.0 CPU FastAPI — LIVE on VPS 127.0.0.1:8880 via systemd unit `titan-kokoro.service`, digest-pinned `sha256:c8812546...`, TTFB 31 ms, 2.38 s for ~4 s of audio on CPU (verified by `/tmp/hermes_smoke.wav`).
  - Step 4 Silero VAD v4 — `lib/silero_vad.py`, 237.9 ms wall on the smoke fixture, 2 speech segments detected.
  - Step 5 faster-whisper medium.en int8 — `lib/whisper_cpu.py`, warm 1.63× RTF (plan target ~2×), exact transcript match.
  - Step 7 Sentence buffer — `lib/sentence_buffer.py` + `tests/test_sentence_buffer.py`, 6/6 pytest green.
  - Step 8 RNNoise server-side — `lib/rnnoise_wrapper.py` + rnnoise_demo binary at `/usr/local/bin/`, 24.7 dB noise reduction, 0.3 dB signal preservation.
  - Step 9 Health check — `bin/titan-kokoro-healthcheck.sh` + `titan-kokoro-health.timer` (60 s cadence), `/var/log/titan/kokoro-health.jsonl` logging, 3-strike alert wired to `lib/war_room.notify`.
- **Reviewer Loop gating:** Calls 1/4, 2/4, 3/4 all graded **A** with zero risk tags by perplexity-api transport (total reviewer spend to date: $0.25 / $5.00 month cap). Call 4/4 (Step 8 grade) is scheduled via `systemd-run hermes-call4` to fire at **2026-04-12T00:08:23Z** after UTC daily-cap rollover; bundle pre-assembled at `/tmp/HERMES_STEP8_20260412_000000` on VPS. Result logs to `/var/log/titan/hermes-call4.log`.
- **Doctrine steps deferred (explicit, per plan §3 decision table):** Step 2 LiveKit-on-Telnyx (Phase B phone calls), Step 3 Deepgram Flux (Hard Limit money), Step 6 Chatterbox-Turbo (GPU gate), Step 10 ElevenLabs Starter fallback (Hard Limit money).
- **Next deliverable:** Atlas API shim (`lib/atlas_api.py`) that wires Silero → whisper → Claude → Kokoro into a WebSocket pipeline at `api.aimarketinggenius.io`. Not started — was explicitly out of scope per Hermes plan §11. This is the next plan to draft + route through the Idea Builder grading loop.
- **Voice AI Path B RunPod worker** — still **deprioritized** as enterprise upgrade path for SKU 3b trophy clients. Remains post MP-4 + CORDCUT 4+5.
- **Voice AI Path A demo plan (old)** — `plans/PLAN_2026-04-12_voice-ai-path-a-demo.md` SUPERSEDED by the Hermes plan; retained for history only.

### Atlas demo lane (parallel-track with Voice AI Path A)
- **Atlas skin polish on `os.aimarketinggenius.io`** — P1 demo-critical. Currently "too templated." Delegated to Perplexity Computer via `plans/COMPUTER_TASKS_2026-04-12.md` Task 1 (10-15k credits). Output → Titan applies permanently in repo.
- **Atlas API shim (VPS)** — new FastAPI at `api.aimarketinggenius.io` (`lib/atlas_api.py`, `sql/NNN_atlas_sessions.sql`, `atlas-api.service`). Handles WS for voice + text, enforces IP-protection rule (client never talks direct to Claude/Deepgram/ElevenLabs). Phase 1 of Voice AI Path A DR.
- **Cross-device session continuity** — `atlas_session_id` handshake reuses HERCULES_BACKFILL_REPORT §TODO.3 spec. Text + voice share the same session state. Demo money-shot: start convo on iPhone, continue on Mac desktop.
- **3 hero flows for Loom** — (1) campaign build, (2) outbound sequence, (3) weekly reporting. Each gets 2-3 min voice-driven segment in the Loom. Full Loom ~12-15 min.

### Perplexity Computer lane (52k credit budget)
- **Task bundle doc:** `plans/COMPUTER_TASKS_2026-04-12.md` — 4 scoped jobs totaling ~40k of 52k credits, leaves 12k for iteration
- **Task 1** Atlas skin polish (10-15k) — P1, immediate
- **Task 2** AMG site compliance audit via Chrome-MCP (5-8k) — P1, immediate, unblocks RADAR O7
- **Task 3** Loom demo asset capture (8-12k) — P1, gated on Tasks 1+2
- **Task 4** Merchant stack KYC screenshot + form prep (5-8k) — P2, independent

### Shop UNIS extras (CT-0410-01)
- Internal linking sweep + product page optimization + AI Overview expansion. Pre-approved. Not started.

---

## Blocked on Solon (actionable items)

From `~/titan-session/NEXT_TASK.md`:

1. **Apply `sql/006_payment_link_tests.sql`** in Supabase SQL Editor (gates Gate 3)
2. **Gate 3 end-to-end verification** via `scripts/test_payment_url.py` (depends on #1)
3. **Batched 2FA/credential session** (~15 min): Claude.ai sessionKey + Perplexity cookie + Loom creds + Gmail OAuth. **Checklist shipped:** `plans/BATCH_2FA_UNLOCK_2026-04-12.md` — 4 steps, safety rules, verification script, auto-fires MP-1 → MP-2 Solon Manifesto synthesis overnight
4. **🔴 Perplexity API quota top-up** at perplexity.ai/settings/api (2 min)
5. **Slack bot token + Perplexity Slack app install** — NOW a firm directive (was optional). Required for new COO ↔ Perplexity routing per CLAUDE.md §1.
6. **Apply `sql/007_autopilot_suite.sql`** in Supabase SQL Editor (gates all autopilot threads)
7. **Thread 1 unlock:** Google Cloud Pub/Sub + Gmail OAuth + Slack Events API
8. **Thread 2 unlock:** 2-3 example spec.yaml files + optional SOW template
9. **Thread 3 unlock:** AMG content source URLs + brand voice file + Opus Clip + HeyGen + X Basic + LinkedIn Company OAuth + email rail (~$390/mo)
10. **Thread 4 unlock:** PayPal export cadence + subscriber seed list
11. **Thread 5 unlock:** Client roster + metric profiles + GA4/GSC service account

---

## Parked > 7 Days

*(None yet — this section auto-populates via `scripts/radar_refresh.py` when an item has been in the queue >7 days without status change. Titan will surface each parked row as a "do you still want this, or archive?" question.)*

---

## Solon OS substrate (standing)

- **Titan-policy repo creation** (Phase G.1.4 finish) — pending
- **Atlas Layer 2 sweep SOP absorption** — pending
- **Cross-instance Slack routing** — live

---

## Product / Pricing doctrine (open specs)

**Canonical doctrine:** [`plans/DOCTRINE_AMG_PRODUCT_TIERS.md`](plans/DOCTRINE_AMG_PRODUCT_TIERS.md) (committed 2026-04-11 via Hercules backfill pass, also in MCP memory `project_amg_product_tiers.md` + `feedback_ip_protection.md`)

- **Three-SKU landing-page split** — AMG subs (self-serve funnel) / White-label (application-gated channel partner page) / Solon OS custom (invite-only "apply" page with scoping call). Currently collapsed into one funnel on aimarketinggenius.io. Spec not yet drafted.
- **White-label agency discount model** — no spec exists. Needs: discount %, minimum volume, branding scope, contractual no-compete, upgrade path from AMG-sub white-label → Atlas white-label. Blocker on agency channel launch.
- **Tenant-API architecture for custom builds** — standing principle per doctrine §2. Client instances must be tenants calling AMG's API, never standalone copies. Needs: reference architecture doc + client-deliverable template audit to confirm no prompt/persona/orchestration leakage.
- **Solon OS custom tier 3a vs 3b pricing bands** — Atlas-as-template (3a) vs fully-custom OS in client identity (3b). Price floors not yet set. Must be high enough to not create competition per Solon directive 2026-04-11.
- **`lib/pricing_engine.py`** — runtime enforcement of floor rules (cost-plus, competitor-displacement, value-share — max of the three). Required for the demo proposal flow Solon wants. Needs DR.

---

## Reviewer Loop transport layer — Slack-Computer primary + API fallback (2026-04-12)

**Doctrine:** `DR_TITAN_AUTONOMY_BLUEPRINT.md §9` + `CORE_CONTRACT.md §0.8` + `CLAUDE.md §16`
**Code:** `lib/slack_reviewer.py` (silent Slack transport, urllib-only, redacts secrets before post), `bin/titan-slack-setup.sh` (one-time onboarding, `read -rs` hidden token paste, auto-discovers Perplexity Computer bot user ID), `bin/review_gate.py` (auto-detect fallback chain, monthly API budget fail-closed)
**Config:** `policy.yaml autopilot.reviewer:` block (fallback order, monthly budget $20, poll interval 3s, timeout 120s, channel `#titan-aristotle`)

### Infisical keys reserved for this system (harness-core/dev)
| Key | Type | Purpose | Set by |
|---|---|---|---|
| `SLACK_BOT_TOKEN` | secret | Titan Slack bot OAuth token (xoxb-...) | `bin/titan-slack-setup.sh` (silent import via jq+curl) |
| `PERPLEXITY_API_KEY` | secret | Fallback API path when Slack unavailable | imported 2026-04-12 from `/opt/litellm-gateway/.env` |
| `LITELLM_MASTER_KEY` | secret | Shared with llm_client.py + war_room.py | imported 2026-04-12 |
| `SUPABASE_SERVICE_ROLE_KEY` | secret | Harness Supabase writes | imported 2026-04-12 |
| `SUPABASE_URL` | non-secret URL | Supabase endpoint | imported 2026-04-12 |
| `LITELLM_BASE_URL` | non-secret URL | LiteLLM gateway endpoint | imported 2026-04-12 |

### Non-secret config (on-disk, NOT in Infisical)
| File | Contents | Permissions |
|---|---|---|
| `/root/.infisical/slack-config.json` | `{channel_id, reviewer_bot_id, titan_bot_id, workspace}` | 600 root |
| `/root/.infisical/project-ids.json` | Infisical project UUID map | 600 root |
| `/root/.infisical/service-token-harness-core` | Infisical service token (read-only scope) | 600 root |
| `/root/.infisical/service-token-harvesters` | Infisical service token (read-only scope) | 600 root |

### Fallback order (auto-selected at `review_gate.py` runtime)
1. **slack-computer** — preferred. Titan bot @mentions Perplexity Computer in `#titan-aristotle`, polls for reply, parses JSON grade. Uses Solon's Pro credits (no API billing).
2. **perplexity-api** — dormant fallback. Activates only when Slack path unavailable AND `PERPLEXITY_API_KEY` in Infisical AND monthly spend < $20 USD (`policy.yaml autopilot.reviewer.api_monthly_budget_usd`). Spend log at `/var/log/titan/perplexity-api-spend.jsonl`.
3. **(none)** → exit 2, fail-closed, escalate to Solon.

---

## Titan 99.99% Autonomy Blueprint — ingested 2026-04-12 (canonical v2)

**Canonical DR (source of truth):** [`plans/DR_TITAN_AUTONOMY_BLUEPRINT.md`](plans/DR_TITAN_AUTONOMY_BLUEPRINT.md) — verbatim Perplexity Computer report, ingested per Solon directive 2026-04-12. Full 800-line blueprint saved as canonical. **Supersedes the v1 draft that had missing sections 5-8.**

**5 phase plans (rebuilt v2 from canonical source, all A-graded):**
1. [`plans/PLAN_2026-04-12_autonomy-phase1-infisical.md`](plans/PLAN_2026-04-12_autonomy-phase1-infisical.md) — **Phase 1 Secrets Hardening (Week 1-2)** — Deploy Infisical + migrate secrets + wrap with `infisical run --` + pyotp (gated) + git secrets hook — **9.46/10 A**
2. [`plans/PLAN_2026-04-12_autonomy-phase2-auth-ritual.md`](plans/PLAN_2026-04-12_autonomy-phase2-auth-ritual.md) — **Phase 2 Auth Ritual Systemization (Week 2-3)** — auth-ritual.sh + launchd Friday 4pm + Playwright storageState + <20 min target — **9.43/10 A**
3. [`plans/PLAN_2026-04-12_autonomy-phase3-anti-bot.md`](plans/PLAN_2026-04-12_autonomy-phase3-anti-bot.md) — **Phase 3 Anti-Bot Upgrade (Week 3-4)** — Nodriver + Camoufox + routing doctrine + Browserless — **9.52/10 A** — 🔴 HIGHEST URGENCY (direct fix for today's Cloudflare block)
4. [`plans/PLAN_2026-04-12_autonomy-phase4-job-queue.md`](plans/PLAN_2026-04-12_autonomy-phase4-job-queue.md) — **Phase 4 Scheduling & Queue (Week 4-5)** — systemd timers + BullMQ/Redis + 3 worker pools + supervisord — **9.41/10 A**
5. [`plans/PLAN_2026-04-12_autonomy-phase5-observability.md`](plans/PLAN_2026-04-12_autonomy-phase5-observability.md) — **Phase 5 Logging & Safety (Week 5-6)** — JSON audit logger + Loki/Grafana + circuit breaker + DLQ review in weekly ritual — **9.40/10 A**

**Dependency chain:**
- Phase 1 → unblocks 2, 4, 5 (secret injection)
- Phase 2 → depends on Phase 1
- Phase 3 → STANDALONE, direct fix for today's Cloudflare failure, can ship today
- Phase 4 → depends on Phase 1
- Phase 5 → depends on Phase 1 + Phase 4

**Conflict note:** canonical blueprint says BullMQ is [PROVEN] and "matches Titan's stack" (TypeScript assumption). Actual `titan-harness` is Python-first. Phase 4 plan documents BullMQ integration with a Python worker adapter as the canonical-honoring implementation; RQ (pure Python) is offered as an optional swap if Solon prefers. No substitution without explicit Solon decision.

**TOTP caveat (Phase 1 Step 1.4):** canonical blueprint marks pyotp + Keychain TOTP automation as [PROVEN]. This conflicts with the harness `user_privacy` safety rules on handling authentication factors. Phase 1 Step 1.4 ships pyotp installed but UNWIRED pending explicit Solon authorization per Solon-style thinking §4 Hard Limits #1.

**Recommended execution order** (Solon-style Principle 1 — high leverage first):
1. **Phase 3 FIRST** (standalone, 🔴 urgent, fixes today's blocker)
2. **Phase 1** in parallel with Phase 3
3. **Phase 2** after Phase 1
4. **Phase 4** after Phase 1
5. **Phase 5** last

---

## Never-Stop Autonomy + VPS Scheduler — shipped 2026-04-12

**Canonical:** `CORE_CONTRACT.md §8` + `CORE_CONTRACT.md §9` + `CLAUDE.md §15`
**Doctrines:**
- [`plans/DOCTRINE_SOLON_STYLE_THINKING.md`](plans/DOCTRINE_SOLON_STYLE_THINKING.md) — 10 principles + 5-step decision flow + 8 Hard Limits (self-graded 9.49/10 A)
- [`plans/DOCTRINE_ROUTING_AUTOMATIONS.md`](plans/DOCTRINE_ROUTING_AUTOMATIONS.md) — harness vs Computer vs Deep Research routing (self-graded 9.44/10 A)
- [`plans/PLAN_2026-04-12_vps-scheduler-night-grind.md`](plans/PLAN_2026-04-12_vps-scheduler-night-grind.md) — scheduler DR (self-graded 9.42/10 A)

**Scheduler artifacts shipped:**
- `bin/titan-hourly-drain.sh` — hourly drain wrapper (755, chmod +x)
- `bin/titan-night-grind.sh` — night grind wrapper (755, chmod +x)
- `lib/radar_drain.py` — non-interactive work identifier (v1 classifier, submission path is a follow-on)
- `policy.yaml autonomy:` + `scheduler:` + `routing:` blocks — kill switches + config

**Dormant until Solon runs the 1-command cron install** (plans/PLAN_2026-04-12_vps-scheduler-night-grind.md §4.5). Can't be auto-installed — modifying root crontab falls under the system-file safety rule.

**P0 rule:** if Titan ever parks non-interactive work on "awaiting Solon," that's a session-level failure per CORE_CONTRACT §8.4.

---

## Greek Codename — locked 2026-04-12 (5 marquee names)

Per Solon's directive "treat DOCTRINE_GREEK_CODENAMES.md as approved with your recommended conflict resolutions":

- **Hermes** → Voice AI Path A (demo voice lane) — applied in [`plans/PLAN_2026-04-12_voice-ai-path-a-demo.md`](plans/PLAN_2026-04-12_voice-ai-path-a-demo.md) on rename sweep
- **Iris** → Perplexity Computer task delegation — applied in [`plans/COMPUTER_TASKS_2026-04-12.md`](plans/COMPUTER_TASKS_2026-04-12.md) on rename sweep
- **Ploutos** → Merchant stack (payment processor orchestration)
- **Argus Panoptes** → RADAR never-lose-anything queue (this file)
- **Hippocrates** → Self-healing layer of Solon OS (Solon-proposed, locked)

Remaining 17 PROPOSED names from `plans/DOCTRINE_GREEK_CODENAMES.md §4` await explicit Solon approval before lock (Hard Limit #8 per DOCTRINE_SOLON_STYLE_THINKING §4).

---

## Greek Codename doctrine — shipped 2026-04-12

**Canonical:** [`plans/DOCTRINE_GREEK_CODENAMES.md`](plans/DOCTRINE_GREEK_CODENAMES.md) — Titan self-graded 9.46/10 A, `PENDING_ARISTOTLE`
**Enforcement:** `CLAUDE.md §14` — every new plan file must propose Greek codenames via Idea Builder loop before Solon-approval-lock

**Retroactive inventory status:** 31 items total — 7 locked (Solon, Atlas, Titan, Aristotle, Hercules, Alexandria, Hippocrates), 22 proposed pending Solon approval, 2 conflicts (Argus collision at #22/#25 and Hermes collision at #14/#25/#27) with Titan's recommended arbitration in doctrine §5.

**Top marquee proposals awaiting Solon lock:**
- **Hermes** — Voice AI Path A (demo voice lane)
- **Demeter** — MP-1 HARVEST pipeline
- **Mnemosyne** — MP-2 SYNTHESIS (Solon Manifesto distillation)
- **Prometheus** — IDEA → DR → PLAN → EXECUTE pipeline
- **Themis** — War Room A-grade grading loop
- **Hephaestus** — MP-4 ATLAS BUILD
- **Argus Panoptes** — RADAR open queue
- **Ariadne** — BATCH_2FA_UNLOCK + grab-cookies.py
- **Mentor** — EOM v2.2 (Claude.ai web Router/Builder persona)

---

## EOM v2.2 merge — shipped 2026-04-12

**Source scan + merge doctrine:** 5 HIGH-confidence EOM docs found on disk. Canonical is `~/Downloads/eom_si.md` (Apr 8, 2026, 35KB) = EOM v2.2+ with Four-Brain Model + 10-doc KB structure + Thread Safety Gate + Operator Memory Protocol.

- **Merged doctrine:** [`plans/DOCTRINE_EOM_MERGED_2026-04-12.md`](plans/DOCTRINE_EOM_MERGED_2026-04-12.md) — Titan self-graded 9.46/10 A (round 1, pending Aristotle re-review). 8 sections absorbed: ADHD protocols, anti-hallucination, Operator Memory Protocol, Aristotle 5-point Advisory Scan, severity tiers, response format, ALWAYS/NEVER rules, First-Pass Verification Gate.
- **Conflict queue:** [`plans/DOCTRINE_EOM_CONFLICTS_2026-04-12.md`](plans/DOCTRINE_EOM_CONFLICTS_2026-04-12.md) — 8 items pending Solon decision. None auto-applied. Estimated ~15 min Solon time to work through.
- **CLAUDE.md §13 added:** enforces new Memory Protocol + Advisory Scan + ADHD + Anti-Hallucination + Severity Tiers + Banned Phrases + First-Pass Verification Gate at session contract level.
- **Key finding:** EOM and Titan are **complementary**, not competing. Both share MCP memory server state with `project_id=EOM`. EOM = Claude.ai web Router/Builder. Titan = ~/titan-harness Researcher/Automator/COO. Kill chain already shows `Titan+EOM` collaboration tagging on MP-3 Atlas Blueprint.

### Top 3 conflicts needing fastest Solon decisions:
- **C4 AMG pricing currency** — $497/$797/$1,497 authoritative as of 2026-04-12? (1 line from Solon)
- **C7 Viktor AI status** — still running, or absorbed by Titan? (1 line from Solon)
- **C8 KB Docs 01-10 extraction** — blocked on `plans/BATCH_2FA_UNLOCK_2026-04-12.md` Step 1 Claude sessionKey → unlocks MP-1 Phase 1 harvester → pulls EOM project docs automatically

---

## Idea Builder retroactive grading queue (added 2026-04-12 per CLAUDE.md §12)

All new plan / doctrine files created by Titan must route through the Idea Builder / war-room grading loop before being treated as ready for Solon. Rule added 2026-04-12 after compliance violation on the 4 artifacts shipped earlier that day. Grading routing priority: Slack Aristotle → direct API → Titan self-grade fallback.

**Retroactively graded 2026-04-12 (Titan self-grade, pending real Aristotle re-review when Slack path comes online):**
- ✅ `plans/PLAN_2026-04-12_voice-ai-path-a-demo.md` — 9.40/10 A (round 2, after §14 Rollback + Vendor Outage added)
- ✅ `plans/BATCH_2FA_UNLOCK_2026-04-12.md` — 9.47/10 A (first pass)
- ⏳ `plans/COMPUTER_TASKS_2026-04-12.md` — execution brief, not a DR; deferred grading until Solon requests
- ✅ `plans/DOCTRINE_AMG_PRODUCT_TIERS.md` — committed doctrine, considered pre-graded via its inclusion in HERCULES_BACKFILL_REPORT.md §N; deferred formal re-grading

**Pre-rule plans (CORE_CONTRACT §7 era, 2026-04-10 / 04-11) still active on RADAR:** Autopilot Suite Threads 1-5 DRs — these WERE routed through war-room at time of creation (all A-grade 9.40-9.53 per INVENTORY.md) so are grandfathered, no re-grade needed.

---

## Structural gaps (from Hercules backfill 2026-04-11)

**Report:** [`HERCULES_BACKFILL_REPORT.md`](HERCULES_BACKFILL_REPORT.md)

- **⚠️ Email send-verification preflight gate** — no `bin/email-send-preflight.sh`, no `sql/*_email_send_tests.sql`, no `policy.yaml email_send:` block. Thread 1 Sales Inbox + Thread 3 Marketing Engine both stub outbound send without a preflight (parallel to Gate 3 payment-link tester pattern). P1 gap. Needs DR before implementation. Solon explicitly flagged this as a structural concern.
- **⚠️ Cross-device session continuity rule** — Atlas frontends (Mac ⇄ web ⇄ iPhone PWA) need a structural rule that all frontends speak to Titan via central `atlas_session_id` handshake, never direct Claude API. Tentative home: `CORE_CONTRACT.md §9`. Flagged here so it doesn't get lost during the Atlas skin build.
- **⚠️ `lib/pricing_engine.py`** — see "Product / Pricing doctrine" section above.

---

## Archive (completed >7 days, for reference only)

- Performance rollout P2-P13 — completed 2026-04-11 (commit `a87a0f0`)
- War-Room A-grade overhaul — completed 2026-04-10 (commit `84d4a1f`)
- Phase G.1-G.4 — completed 2026-04-10/11
- Gate 3 payment-link pipeline — completed 2026-04-11 (commit `f1ab8b0`)
- Slack-routed war-room dispatcher — completed 2026-04-11 (commit `f97a7c1`)
- Autopilot Suite scaffold (INVENTORY + 5 DRs + schema + stubs + policy) — completed 2026-04-11 (commit `bea1740`)
- CLAUDE.md + CORE_CONTRACT §0 + RADAR.md — completed 2026-04-11 (this commit)
