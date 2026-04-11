# RADAR — Titan's Never-Lose-Anything Open Queue

**Owner:** Titan (COO). **Canonical state for what's open, blocked, parked, or in-flight.**
**Last refreshed:** 2026-04-11 13:24 UTC
**Refresh cadence:** every session boot; full regenerate daily via `scripts/radar_refresh.py`.

**Hard rule:** every important idea, DR, megaprompt, or half-finished project must (a) exist as a row in `tasks`/`mp_runs` or a `PLAN_*.md`/`MP_*.md` file, AND (b) have a line here under one of the sections below. No exceptions.

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
- **Voice AI Path B RunPod worker** — **deprioritized** per 2026-04-11 directive. Comes after MP-4 + CORDCUT 4+5.

### Shop UNIS extras (CT-0410-01)
- Internal linking sweep + product page optimization + AI Overview expansion. Pre-approved. Not started.

---

## Blocked on Solon (actionable items)

From `~/titan-session/NEXT_TASK.md`:

1. **Apply `sql/006_payment_link_tests.sql`** in Supabase SQL Editor (gates Gate 3)
2. **Gate 3 end-to-end verification** via `scripts/test_payment_url.py` (depends on #1)
3. **Batched 2FA/credential session** (~15-20 min): Claude.ai sessionKey + Perplexity cookie + Loom creds + Gmail OAuth
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

## Archive (completed >7 days, for reference only)

- Performance rollout P2-P13 — completed 2026-04-11 (commit `a87a0f0`)
- War-Room A-grade overhaul — completed 2026-04-10 (commit `84d4a1f`)
- Phase G.1-G.4 — completed 2026-04-10/11
- Gate 3 payment-link pipeline — completed 2026-04-11 (commit `f1ab8b0`)
- Slack-routed war-room dispatcher — completed 2026-04-11 (commit `f97a7c1`)
- Autopilot Suite scaffold (INVENTORY + 5 DRs + schema + stubs + policy) — completed 2026-04-11 (commit `bea1740`)
- CLAUDE.md + CORE_CONTRACT §0 + RADAR.md — completed 2026-04-11 (this commit)
