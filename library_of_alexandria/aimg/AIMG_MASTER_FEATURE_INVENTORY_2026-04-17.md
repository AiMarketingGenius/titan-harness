# AI MEMORY GUARD — MASTER FEATURE INVENTORY
**Generated:** 2026-04-17 | **Scope:** All EOM threads since product inception (2026-04-05)
**Source method:** conversation_search + search_memory iterative scour | ~30 prior threads synthesized

---

## 1. PRODUCT IDENTITY — LOCKED

| Attribute | Value | Status |
|---|---|---|
| Product name | **AI Memory Guard** | 🏆 LOCKED 2026-04-06 |
| Chrome Web Store title | AI Memory Guard — Cross-Platform Memory + Fact Checking for AI Chats | ✅ LOCKED |
| Tagline (hero) | "AI can make mistakes. We help you catch them." | ✅ LOCKED |
| Marketing brand for Thread Health meter | Hallucinometer™ | ✅ LOCKED (trademark ITU target) |
| In-product label for meter | Thread Health | ✅ LOCKED (per P validation — avoids scaring consumers with "hallucination") |
| Parent brand tie-in | **KILLED** — no "from the makers of AI Marketing Genius" footer per CT-0416-07 trade secret rule | 🔴 REMOVED |
| Domain | aimemoryguard.com | ✅ LIVE (Cloudflare zone `023d9d0c5624005c1a484b4b746b0b06`) |
| Primary email | hello@aimemoryguard.com | ✅ LIVE |
| Sender email | noreply@aimemoryguard.com (Resend verified) | ✅ LIVE |

---

## 2. PRICING & TIERS — LOCKED

| Tier | Price | Memory | Fact Checker (Haiku QE) | Einstein Deep Check | Auto-Carryover | Hallucinometer |
|---|---|---|---|---|---|---|
| **Free** | $0 | 50 memories/week | 10/day | 0/day | 3/week | ✅ All tiers |
| **Pro** | $9.99/mo | Unlimited | 100/day | 10/day | Unlimited | ✅ All tiers |
| **Pro+** | $19.99/mo | Unlimited | 500/day | 5–50/day | Unlimited | ✅ All tiers |

**Payment:** Paddle (5% + $0.50/txn). Product IDs: not yet created per last MCP state.
**Key rule:** QE (Haiku Fact Checker) is on **every tier** — differentiator is volume, not feature access.
**Revenue math:** At 1,000 Pro subs = $9,990/mo · 500 Pro+ = $9,995/mo → $20K/mo MRR @ ~1,500 total subs.

---

## 3. CORE FEATURES — 4 PILLARS (The Moat)

### 3.1 Cross-Platform Memory Capture
- **Platforms supported:** Claude.ai · ChatGPT · Gemini · Grok · Perplexity (5)
- **Storage:** Consumer Supabase `gaybcxzrzfgvcqpkbeiq` → `consumer_memories` table
- **Provenance stamps (mandatory on every memory):** platform · thread_id · thread_url · exchange_number · source_timestamp · project_id
- **Extraction:** Rule-based (free tier) + embeddings-based (paid)
- **Embedding model:** OpenAI text-embedding-3-small (1536 dims, $0.02/MTok)
- **Injection:** Context injected to any AI chat before user message sends
- **Status:** 🟡 SHIPPED BUT BROKEN in v0.1.0 — counter=0 bug (memories not persisting). CT-0416-07 rebuild in progress.

### 3.2 Hallucinometer™ (Thread Health)
- **Purpose:** Real-time thread depth gauge — users SEE degradation before it happens
- **Tier model (matches EOM Doc 10):** 🟢 Fresh 1–15 · 🟡 Warm 16–30 · 🟠 Hot 31–45 · 🔴 Danger 46+
- **Visual:** 8px vertical bar on left edge (collapsed), 52px expanded on hover, glassmorphism backdrop
- **Audio:** Single professional 2-tone chime at red-zone entry (NOT siren). 40% system volume. Plays once, never repeats.
- **Pulse animations:** Escalate by tier — silent green → 400ms yellow pulse → faster orange → dangerGlow red
- **Status:** 🔴 NOT IMPLEMENTED in current extension build. CT-0416-07 includes rebuild gate.

### 3.3 Auto-Carryover
- **Purpose:** One-click clean thread handoff before hallucination hits
- **Triggers (three escalation points):**
  - Exchange 35 → non-blocking card slides bottom-right ("Start fresh thread?")
  - Exchange 46 → blocking modal ("Let's start a fresh new thread... full context carries over")
  - Exchange 55 → persistent top banner (last resort)
- **Mechanism:** Haiku summarizes current thread → carryover doc generated → copied to clipboard → opens new tab on same platform
- **Dismiss copy:** "Continue This Thread" (neutral, not guilt-trip)
- **Status:** 🔴 NOT IMPLEMENTED. CT-0416-07 rebuild gate.

### 3.4 Einstein Fact Checker + Fact Checker (Haiku QE)
- **Two-tier QE:**
  - **Fact Checker (Free on all tiers):** Haiku-powered contradiction detection — compares new AI output against user's stored memories, flags inconsistencies in ≤30s
  - **Einstein Fact Checker (premium depth):** Deeper verification — fact-checks against web + memory + Anthropic-signed reasoning chain
- **UX:** Inline warning icon ⚠️ next to flagged response + bottom-right notification card with two buttons ("Fact Check" free / "Einstein" premium)
- **Einstein result:** Blurred until user spends a daily credit (10 for Pro, 5–50 for Pro+)
- **Edge Function:** `einstein-fact-check` deployed to Supabase `gaybcxzrzfgvcqpkbeiq` ✅
- **Status:** 🟡 BACKEND DEPLOYED, UI INTEGRATION UNVERIFIED. CT-0416-07 rebuild gate for end-to-end test.

---

## 4. INFRASTRUCTURE — CURRENT STATE

| Component | Status | Detail |
|---|---|---|
| Chrome extension v0.1.0 | 🟡 REBUILD IN PROGRESS | CT-0416-07 clean install path 2026-04-16 14:00Z |
| Consumer Supabase | ✅ LIVE | Project `gaybcxzrzfgvcqpkbeiq`, separate from operator |
| Einstein Edge Function | ✅ DEPLOYED | `einstein-fact-check` at `gaybcxzrzfgvcqpkbeiq.supabase.co/functions/v1/einstein-fact-check`, fail-closed on auth (401 expected unauthenticated) |
| Resend SMTP | ✅ LIVE | smtp.resend.com:465, DKIM/SPF/DMARC verified, zero drseo.io leak. Keys: `re_LMTWxcLU_4B1CEbmqTzxNoGAHVFfab4HG` (send), `re_SMkFKAAX_DWJWciRPLk2gVWLKaaacsJ5E` (full) |
| Cloudflare zone | ✅ LIVE | `aimemoryguard.com` zone ID `023d9d0c5624005c1a484b4b746b0b06` |
| Google Workspace (parent) | ✅ LIVE | `growmybusiness@aimarketinggenius.io` on Business Plus trial, downgrade to Starter pending |
| Landing page (aimemoryguard.com) | 🟡 REBUILD QUEUED | CT-0416-07 gate — had regression with trade-secret leak footer + broken $ sign pricing |
| Cloudflare Pages deploy | 🔴 BLOCKED | Token scope mismatch: master doc token is `ads@drseo.io` account, aimemoryguard Pages under different CF account. Need `CLOUDFLARE_API_TOKEN_AIMG` added |
| SQL migration `sql/002_einstein_fact_checks.sql` | 🔴 BLOCKED | Solon manual paste into Supabase SQL Editor required |
| Admin command portal (subscriber management) | 🔴 NOT BUILT | Gap — no visible way for Solon to view/pause/upgrade/suspend subs |
| Chrome Web Store listing | 🔴 NOT PUBLISHED | Developer account ($5) not yet signed up |
| Paddle product IDs (Pro/Pro+) | 🔴 NOT CREATED | Billing not yet wired |

---

## 5. FEATURE STATUS MATRIX — Everything Ever Discussed

### 🏆 SHIPPED & WORKING
- Product naming locked (AI Memory Guard)
- Domain + email + SMTP (Resend verified)
- Consumer Supabase isolation from operator
- Einstein Fact Checker Edge Function deployed
- Google Workspace parent account

### 🟡 SHIPPED BUT BROKEN / UNVERIFIED
- Extension v0.1.0 (counter=0 persistence lie — CT-0416-07 rebuild)
- Landing page aimemoryguard.com (regression — trade-secret leak, broken $ signs, fake testimonials)
- Einstein Edge Function end-to-end UI integration (deployed but never observed working in extension)

### 🔴 SPEC'D & APPROVED, NOT BUILT
- Hallucinometer UI (tier colors, pulse, audio chime, left-edge bar)
- Auto-Carryover triggers (card @ 35, modal @ 46, banner @ 55) + Haiku summarization
- Admin command portal (subscriber management — create/pause/upgrade/downgrade/suspend accounts visible to Solon)
- Paddle product IDs + billing wiring
- Chrome Web Store developer account + listing submission
- Apple App Store iOS companion (deferred multi-month per standing decision)

### 💤 DISCUSSED, DEFERRED
- Mobile native iOS/Android Memory Guard companion — post-desktop-stabilization
- HIPAA-compliant enterprise tier (Phase 2 priority after consumer launch)
- White-label for agencies (B2B Context Guard variant discussed, not prioritized)
- Cross-thread memory bridge between AI platforms (advanced — architectural)
- "Thread Guard" / "Context Guard" B2B variants (naming explored, parked)

### ⚰️ KILLED
- "AMG Memory" / "Memory Genius" / "Recall Genius" — all naming alternatives killed when "AI Memory Guard" locked
- Gmail SMTP approach (cross-domain block — Resend replaced)
- Gmail alias workaround (Workspace blocks)
- Google Workspace secondary domain ($7.20/mo extra rejected)
- "From the makers of AI Marketing Genius" footer (trade-secret leak — killed per CT-0416-07)
- Stripe (permanently dead for all AMG products)
- Old extension "Universal Memory Capture" (replaced by AI Memory Guard)

---

## 6. UI/UX CANONICAL DECISIONS

1. **Hallucinometer label split** — "Hallucinometer™" on landing page/marketing, "Thread Health" in-product UI
2. **Sound = single professional chime, NOT siren** — plays once on red-zone entry, user-toggleable
3. **Dismiss copy = "Continue This Thread"** — neutral, not guilt-trip
4. **Internal operator memory = infrastructure only** — no visual hallucinometer metaphors (separation of concerns)
5. **Dark theme** matches extension aesthetic
6. **WCAG 2.1 AA contrast** — no ghost buttons, 52px button height, 16px minimum body text
7. **Mobile-responsive** landing page
8. **NO trade-secret leaks** — never name Claude/Anthropic/GPT/OpenAI in client-facing surfaces
9. **NO fake testimonials** — all fabricated social proof killed
10. **Professional, trust-forward** — "Guard" angle signals protection, not cleverness

---

## 7. CRITICAL GAPS (What Breaks Launch If Not Fixed)

| # | Gap | Severity | Blocker? |
|---|---|---|---|
| 1 | Counter=0 persistence bug — memories don't actually save | 🔴 CRITICAL | Kills dogfooding + product trust |
| 2 | Hallucinometer not implemented | 🔴 CRITICAL | Core advertised feature missing |
| 3 | Auto-Carryover not implemented | 🔴 CRITICAL | Core advertised feature missing |
| 4 | Einstein UI integration unverified | 🔴 CRITICAL | Edge Function wasted if UI can't hit it |
| 5 | Admin portal not built | 🟡 IMPORTANT | Can't manage subs at launch |
| 6 | Landing page regression | 🟡 IMPORTANT | Trade-secret leak risk + broken pricing |
| 7 | Cloudflare Pages deploy token scope | 🟡 IMPORTANT | Blocks aimemoryguard.com push |
| 8 | Chrome Web Store listing not submitted | 🟡 IMPORTANT | Distribution blocked |
| 9 | Paddle product IDs not created | 🟡 IMPORTANT | Can't bill subs |
| 10 | Provisional patent filings — status unclear | 🔴 CRITICAL | IP moat at risk; competitors could file first |
| 11 | Trademark ITU filing — status unclear | 🟡 IMPORTANT | Name lockdown exposure |

---

## 8. WHAT'S VERIFIED vs. WHAT'S ASSUMED

**VERIFIED (logged in MCP with evidence):**
- Extension v0.1.0 zipped + installed (CT-0406-17)
- Resend SMTP end-to-end tested (FROM header correct, zero leak)
- Google Workspace parent account created
- Einstein Edge Function deployed (curl confirmed 401 unauth = fail-closed correctly)
- Supabase consumer project separated from operator

**ASSUMED BUT NOT PROVEN (need evidence gates):**
- Memory persistence actually works in rebuilt extension (three-number alignment test pending)
- Hallucinometer renders and fires correctly at tier boundaries
- Auto-carryover produces usable carryover docs that restore context in new threads
- Einstein Fact Checker actually detects planted contradictions within 30s + enforces daily caps
- Landing page mobile-responsive + no trade-secret leaks
- Admin portal exists (per memory notes: "aimemoryguard.com admin dashboard visibility unclear" — meaning most likely NOT built)

---

## 9. COST ECONOMICS (Per-User Monthly)

**Per paid subscriber blended cost:**
- Haiku Fact Checker at 100 calls/day × $0.25/MTok ~= $0.05/user/mo
- Einstein deep checks at 10/day ~= $0.40/user/mo
- Supabase storage/compute ~= $0.10/user/mo
- Embedding calls ~= $0.05/user/mo
- **Blended: ~$0.60/user/mo cost at Pro tier** → $9.99 price = **94% gross margin**

At 1,000 Pro subs: $9,990 revenue, $600 cost = **$9,390/mo net contribution** to MRR.

---

## 10. REVENUE PROJECTIONS (Conservative → Aggressive)

| Scenario | Subs | MRR | Timeline |
|---|---|---|---|
| Dogfood launch | 1 (Solon) | $0 | ✅ In progress |
| Soft launch | 50 mix Free/Pro | ~$300 | 30 days post-launch |
| Organic growth | 500 paid (350 Pro + 150 Pro+) | ~$6,500 | 90 days |
| Hockey stick | 2,500 paid | ~$30,000 | 6 months |
| **Moat: QE on every tier + 2 provisional patents** | | | |

---

## 11. COMPETITIVE LANDSCAPE (From Memory)

| Competitor | Price | What They Do | What They DON'T Do |
|---|---|---|---|
| Mem0/OpenMemory | FREE (open source) | Memory only, 5 platforms | No QE · No Hallucinometer · No Auto-Carryover |
| MemoryPlugin | $10/mo | Memory, 12+ platforms | No QE · No Hallucinometer |
| Supermemory | $19–249/mo | Memory + RAG (enterprise-ish) | No QE · No consumer Hallucinometer |
| myNeutron | Varies | Semantic AI memory | No QE |
| AI Context Flow | Freemium | Context injection | No QE |

**Market gap confirmed:** Consumer prosumer-grade QE + cross-platform memory does NOT exist elsewhere. **That gap is the moat.**

---

## 12. STANDING RULES ABOUT MEMORY GUARD (BURNED)

1. 🔴 **No false completion.** Three-number alignment (popup counter = Supabase row count = fresh timestamps) required for every persistence test.
2. 🔴 **No trade-secret leaks** in client-facing surfaces. Never reference Claude/Anthropic/OpenAI/Supabase/Paddle/Resend by name on aimemoryguard.com.
3. 🔴 **QE on all tiers.** Haiku Fact Checker is NOT premium-only. Free gets 10/day, Pro 100/day, Pro+ 500/day. Volume differentiation, not feature gating.
4. 🔴 **Dogfooding before external launch.** Extension must prove persistence + Hallucinometer + Auto-Carryover + Einstein in production-like use before Chrome Web Store submission.
5. 🟡 **Diagnose before rebuild.** Counter=0 bug: find the specific pipeline break (embedding failure / RLS / auth refresh / storage API) before patching anything.
6. 🟡 **Elite Output Standard P10.** Functional-but-ugly is a FAIL. Professional polish is launch gate.
7. 🟡 **Desktop-first, mobile-later.** iOS/Android companion deferred multi-month until desktop stable with paying users.

---

## 13. OPEN QUESTIONS FOR SOLON

1. **Patent filings — actually filed or still planned?** userMemories says "two provisional patents + trademark ITU" but no decision log confirms USPTO receipt numbers. Need status.
2. **Chrome Web Store developer account** — signed up ($5)? If no, blocks public distribution.
3. **Paddle product IDs for $9.99 Pro + $19.99 Pro+** — created? If no, can't bill.
4. **Admin command portal scope** — do you want this on aimemoryguard.com/admin or as part of ops.aimarketinggenius.io? Current memory unclear.
5. **First public launch target date** — vague "after desktop stabilizes." Need a ship-by date to backward-plan.

---

*End of Master Feature Inventory — AI Memory Guard 2026-04-17*
*Source: conversation_search across ~30 prior EOM threads + search_memory across MCP decision log + userMemories cross-check.*
*Companion documents: AIMG_PATENT_SCOPE_ADDENDUM_2026-04-17.md · TITAN_PROMPT_CT-0417-29_30_31_memoryguard-reclamation.md*
