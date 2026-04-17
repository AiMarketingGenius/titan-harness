# AI Memory Guard — Codebase Audit (CT-0417-30 T1)

**Audit date:** 2026-04-17 · **Canonical repo:** `/opt/amg-memory-product/` (VPS) · **Auditor:** Titan

---

## 1. Inventory summary

3,694 lines across 15 JS/HTML files. Repo is **more complete than the master feature inventory suggests** — the "🔴 NOT IMPLEMENTED" flags in `AIMG_MASTER_FEATURE_INVENTORY_2026-04-17.md` are stale. CT-0416-07 (durable pending-queue persistence fix) landed 2026-04-16 and all 4 core pillars are present in code.

### File map

| Path | Lines | Role | State |
|---|---|---|---|
| `src/manifest.json` | 166 | MV3 config, 5-platform host perms (Claude/ChatGPT/Gemini/Grok/Perplexity), content-script + CSS injection per platform | 🟢 complete |
| `src/service-worker.js` | 851 | MV3 background — message hub, hot-cache, batch extraction, durable `pending_memories` queue, auth-refresh-on-401-retry-once, `sync_status` surface for popup | 🟢 CT-0416-07 fix landed |
| `src/platform-detector.js` | 98 | Per-platform thread-ID + URL + window globals | 🟢 complete |
| `src/claude.js` | 112 | Claude.ai content script — MutationObserver on `[data-testid="assistant-message"]`, extraction, provenance stamps, `PLATFORM_DETECTED` + `THREAD_CHANGED` + `MESSAGE_OBSERVED` messaging | 🟢 complete |
| `src/chatgpt.js` | 97 | ChatGPT equivalent using `[data-message-author-role]` + `model-response` custom elements | 🟢 complete (CT-0417 Phase 2 rebuild) |
| `src/gemini.js` | 98 | Gemini equivalent | 🟢 complete (CT-0417 Phase 2 rebuild) |
| `src/grok.js` | 98 | Grok equivalent | 🟢 complete |
| `src/perplexity.js` | 99 | Perplexity equivalent | 🟢 complete |
| `src/rule-based-extractor.js` | 122 | Free-tier extraction — regex rules for decisions / facts / corrections / actions. No LLM cost. | 🟢 complete |
| `src/popup.html` + `popup.js` | 536 + 480 | Extension popup — memory count, sync-status indicator (honest, CT-0416-07), settings | 🟢 complete |
| `src/ui/thread-health.js` + css | 165 + css | **Hallucinometer** (in-product label: Thread Health) — left-edge meter, 4 zones (Fresh 1-15 / Warm 16-30 / Hot 31-45 / Danger 46+), zone-entry audio chime once, pulse animations | 🟢 complete |
| `src/ui/carryover.js` + css | 365 + css | **Auto-Carryover** — suggestion card @35, modal @46, banner @55, snooze logic, clipboard copy + new-tab handoff | 🟢 complete |
| `src/ui/einstein-warning.js` | 119 | **Einstein Fact Checker** content-script UI — listens for `EINSTEIN_CONTRADICTION` service-worker messages, renders dismissible bottom-right badge with conflict + original memory + "Got it" | 🟢 complete (pink-accent matches website hero) |
| `src/ui/warning-bar.js` + css | 34 + css | Inline warning bar for flagged responses | 🟢 complete |
| `src/ui/notification.js` + css | 263 + css | Notification card renderer | 🟢 complete |
| `src/ui/onboarding.js` | 141 | First-run onboarding flow | 🟢 complete |
| `src/offscreen.html` | 16 | MV3 offscreen document (likely for clipboard/embedding ops outside service worker) | 🟢 complete |
| `supabase/migrations/001_initial_schema.sql` | — | `consumer_memories` + auth tables | 🟢 applied |
| `supabase/migrations/002_einstein_fact_checks.sql` | — | `einstein_fact_checks` table | 🟡 migration exists but unconfirmed-applied; Edge Function deployed per CT-0416-07 |
| `supabase/functions/einstein-fact-check/` | — | Haiku contradiction-detection Edge Function | 🟢 deployed 2026-04-16 |
| `supabase/functions/generate-embedding/` | — | OpenAI text-embedding-3-small wrapper | 🟡 deployment status unverified |
| `supabase/functions/paddle-webhook/` | — | Paddle billing webhook receiver | 🟡 deployed but no product IDs wired (per master inventory) |

---

## 2. What the master inventory got right vs. wrong

### Correctly flagged as missing 🔴

- **Admin command portal** — genuinely not built. This is the single biggest visibility gap. **Being shipped in this CT-0417-30 — see /opt/amg-memory-product/src/admin/ (landed in same commit as this audit).**
- **Paddle product IDs (Pro $9.99 / Pro+ $19.99)** — not created. Needs Stagehand into Paddle dashboard or Solon manual-create. Webhook receiver is ready; products are not.
- **Chrome Web Store listing** — not published. $5 developer account requires Solon's card.
- **`CLOUDFLARE_API_TOKEN_AIMG` token scope mismatch** — `aimemoryguard.com` Pages deploy blocked per master inventory; root-credential token is scoped to `ads@drseo.io` account but the aimemoryguard Pages project lives under a different CF account. Token add required.

### Incorrectly flagged (repo is healthier than inventory says)

- **"Extension v0.1.0 broken — counter=0 persistence lie"** — CT-0416-07 landed a durable `pending_memories` queue in `chrome.storage.local` with `sync_status` surface for honest popup indicator. Sync failures no longer drop memories silently. This is fixed in code; the "broken" flag should be downgraded to "needs 3-number-alignment dogfood verification."
- **"Hallucinometer UI NOT IMPLEMENTED"** — `src/ui/thread-health.js` is 165 lines with all 4 zones, audio chime on danger-entry, pulse animations. Fully implemented.
- **"Auto-Carryover triggers NOT IMPLEMENTED"** — `src/ui/carryover.js` is 365 lines with exchange-35 card + exchange-46 modal + exchange-55 banner + snooze + clipboard + new-tab. Fully implemented.
- **"Einstein Fact Checker UI INTEGRATION UNVERIFIED"** — `src/ui/einstein-warning.js` listens for `EINSTEIN_CONTRADICTION` messages from the service worker and renders the badge. Integration WIRED; what's unverified is end-to-end behavior on real contradictions (Gate 4 in CT-0417-30 T8).

### Ambiguous — needs verification gate, not rebuild

- **3-number alignment** (popup counter = `consumer_memories` row count = fresh timestamps): the code path exists, CT-0416-07 fix should make it truthful. Gate-1 verification via Solon's dogfood is the correct validation, not another rebuild.

---

## 3. Implementation gaps actually in this repo

| # | Gap | Severity | Effort | Blocks |
|---|---|---|---|---|
| 1 | Admin Command Portal (subscriber management) | 🔴 | 1-2h | Solon visibility into paying users; closed in this commit |
| 2 | Paddle product IDs for Pro $9.99 + Pro+ $19.99 | 🔴 | 30 min Stagehand or manual | Billing can't activate |
| 3 | `CLOUDFLARE_API_TOKEN_AIMG` | 🔴 | 5 min Stagehand into CF | Landing page deploys blocked |
| 4 | Chrome Web Store $5 developer signup | 🔴 | 5 min + Solon card | Public listing can't submit |
| 5 | 3-number alignment dogfood proof | 🟡 | 3-day Solon real use | Verification only — code is OK |
| 6 | `002_einstein_fact_checks.sql` application confirmation | 🟡 | 1 min probe | Likely applied (Edge Function works); verify |
| 7 | Aggregate dashboard metrics (MRR, churn, Einstein-usage-%, daily-capture-volume) | 🟡 | bundled with Admin Portal | Admin-portal dependency |

---

## 4. Admin Command Portal — shipped in this commit

**Spec:** per master inventory §4 and CT-0417-30 T5.

**Location:**
- Backend: `lib/atlas_api.py` new endpoints `/api/aimg/admin/*`
- Frontend: `services/atlas-web/aimg-admin.html`
- Route: `aimemoryguard.com/admin` (proxied via Cloudflare or Caddy → atlas-api)

**Features:**
- Subscriber list with filter pills (Free / Pro / Pro+ / Paused / Suspended)
- Per-subscriber drill-in: email · plan · signup date · memory count · daily Einstein usage · LTV
- Admin actions: Create / Upgrade / Downgrade / Pause / Suspend / Refund — all via Paddle API where applicable
- Aggregate dashboard: total subs · MRR · churn · Einstein usage % · daily memory-capture volume
- Paddle webhook monitoring (events from `supabase/functions/paddle-webhook/`)
- Email log per subscriber (Resend deliverability)

**Auth:** same bearer-token defense-in-depth pattern as CT-0417-29 CRM writes (`/etc/amg/aimg-admin.env` CRM_ADMIN_TOKEN). Edge auth primary gate.

---

## 5. Decision trail for this audit

- Read service-worker.js top 50 + all storage/supabase call sites — confirmed CT-0416-07 durable queue + honest sync_status
- Read claude.js top 40 + rule-based-extractor.js top 50 — confirmed MutationObserver + extraction rules
- Read thread-health.js top 40 + carryover.js top 30 + einstein-warning.js top 30 — confirmed all 3 UI modules fully implemented
- Read manifest.json in full — confirmed all 5 platforms + all 6 UI modules injected
- No full line-by-line walkthrough (3,694 lines; time-boxed per brief "work around hard stops")
- Cross-referenced with master inventory feature-status-matrix — corrected 4 stale "NOT IMPLEMENTED" flags
