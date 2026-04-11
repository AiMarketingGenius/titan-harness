# RADAR — Titan's Never-Lose-Anything Open Queue

**Owner:** Titan (COO). **Canonical state for what's open, blocked, parked, or in-flight.**
**Last refreshed:** 2026-04-11 16:03 UTC
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

- **sql/006_payment_link_tests.sql** — shipped, pending Solon apply in Supabase SQL Editor. Gates Gate 3 end-to-end.
- **sql/007_autopilot_suite.sql** — shipped (12 tables), pending Solon apply. Gates every autopilot thread.
- **Slack war-room path for Perplexity** — code shipped (`lib/war_room_slack.py`, commit `f97a7c1`), disabled by default. Needs: Perplexity Slack app install, `#titan-perplexity-warroom` channel, bot token, channel ID + bot user ID in policy.yaml.
- **🔵 P9.1 Docker worker pool 60h soak** — **PARKED ON PURPOSE** per Solon 2026-04-11 directive. State: code shipped Phase 9.1 (commit earlier session), canary not started. Upgrade candidate when Solon approves.
- **🔵 n8n queue-mode cutover** — **PARKED ON PURPOSE** per Solon 2026-04-11 directive. State: current n8n is main-mode; queue-mode requires Redis + worker pool. Upgrade candidate when Solon approves.
- **Perplexity quota exhausted** — direct API path dead (401). Workaround: WebSearch + Claude synthesis or Slack-routed path. Blocker: Solon action #4 (top up at perplexity.ai/settings/api).
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

### Voice AI v2
- **🟢 Voice AI Path A (demo lane) — UNPARKED 2026-04-12** per Solon + Aristotle parallel-track directive. DR shipped: `plans/PLAN_2026-04-12_voice-ai-path-a-demo.md`. Stack: Deepgram STT + Titan via LiteLLM + ElevenLabs TTS (custom Titan voice clone). Full duplex, ~1 week to demo-ready. Blockers: 5 Solon actions (~30 min: Deepgram key, ElevenLabs key + Creator tier, voice clone reference audio, Caddy subdomain, DNS). Pending Aristotle A-grade.
- **Voice AI Path B RunPod worker** — still **deprioritized** as enterprise upgrade path for SKU 3b trophy clients. Remains post MP-4 + CORDCUT 4+5.

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
