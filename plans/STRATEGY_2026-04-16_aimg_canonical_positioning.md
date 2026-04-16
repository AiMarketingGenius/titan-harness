# STRATEGY — AI Memory Guard Canonical Positioning, Market Gap, Brand, Copy

**Purpose:** final pre-restart strategy pass. Source of truth for AIMG positioning + branded feature architecture + public-facing copy + claim safety.
**Status:** DRAFT · PENDING_SONAR_A_MINUS (to be graded via direct Perplexity sonar-pro per Solon 2026-04-16 directive)
**Scope:** strategy, copy, gap analysis ONLY. No code. No UI redesign. No ship.
**Date:** 2026-04-16
**Paired with:** `plans/PLAN_2026-04-16_aimg_continuity_hardening.md` (engineering)
**Non-negotiables:** browser-first product truth · no vendor reveal · Einstein Fact Checker preserved · pricing locked at Free $0 / Basic $4.99 / Plus $9.99 / Pro $19.99

---

## 1. Executive recommendation — Canonical positioning

### Category

**Cross-platform AI continuity.**

A new category. Not "AI memory" (commoditized by ChatGPT Memory + Claude Projects). Not "prompt engineering" (commoditized). Continuity is infrastructure — it implies *your context travels with you*, not *your chat is saved*.

### One-sentence category definition

> **AI Memory Guard is cross-platform AI continuity for people who live inside AI chat.**

### Product positioning paragraph

> Every AI conversation dies the moment you close the tab. Context vanishes. Decisions evaporate. Contradictions go unnoticed. AI Memory Guard is the continuity layer that travels with you — capturing the decisions and facts that matter across every major AI assistant, warning you before your thread starts to degrade, and handing you a verified carryover so you pick up exactly where you left off. No silent injection. No vendor lock-in. You see everything we save.

### Why this matters now

> Knowledge workers spend hours a day inside AI chat. Most of that value dies with the tab. The winners of this era aren't the people with the best single AI — they're the people whose context, decisions, and corrections travel with them everywhere. AI Memory Guard is that layer. It's the difference between using AI like a tool and using it like a partner that remembers you.

### Positioning guardrails (how to talk about it + how not to)

| Talk like this | Not like this |
|---|---|
| "Continuity across every AI you use" | "Chat history manager" |
| "Captures the decisions, facts, and corrections that matter" | "Saves your conversations" |
| "Warns you before threads degrade" | "Tracks how long your chat is" |
| "A verified carryover you paste into a fresh thread" | "Auto-forwards your context" |
| "You see everything we save" | "Smart background sync" |
| "Proprietary verification layer" | "Runs another AI to check the first AI" |

**Voice:** confident, category-owning, plain-English. Engineer precision with founder conviction. Never apologetic. Never template-SaaS.

---

## 2. Market gap analysis

### 2.1 Demand that clearly exists

Knowledge workers are actively paying for symptoms of this problem today:
- **Re-explanation tax.** Users repeat themselves every thread. High-frequency pain.
- **Decision erosion.** "What did I decide on X last Thursday with Claude?" is unanswerable.
- **Platform fragmentation.** Most power users run Claude + ChatGPT + Perplexity weekly. Context is trapped per-tool.
- **Trust anxiety.** Users increasingly distrust AI output but have no tool to help them verify.
- **Thread fatigue.** Everyone has 20+ stale threads across 5 platforms. Finding the live one is a job.

Revealed demand signals: ChatGPT Memory rolled out as a flagship feature. Claude launched Projects. Rewind.ai raised $130M. Mem.ai, Sana, Otter — all memory-adjacent consumer plays at ~$10-20/mo. The market is there; none of them solve cross-platform continuity.

### 2.2 What competitors do badly

| Competitor pattern | What goes wrong |
|---|---|
| **Silent capture** (native model memory, Rewind.ai) | User doesn't know what's saved. Trust breaks the moment they realize. |
| **Single-platform lock-in** (ChatGPT Memory, Claude Projects) | Your memory is stuck inside the AI that owns you. Defeats the point. |
| **Save-but-don't-continue** (SaveGPT, ChatGPT Exporter) | You have a text archive. You still re-explain yourself. |
| **Storage without quality** (Mem.ai, Obsidian+AI) | Every memory is treated as equal. No contradiction layer. No confidence. |
| **Developer-only APIs** (Pinecone, Weaviate wrappers) | Inaccessible to the knowledge worker who actually has the problem. |
| **No thread health warning** (everyone) | Conversation degradation is invisible until it's bad. |
| **Generic "summary" feature** (every AI) | The summary isn't structured for pasting into a fresh thread. Useless for continuity. |
| **No cross-model verification** (everyone) | You have one AI's word for it. No second opinion. Ever. |

### 2.3 Under-served gaps AIMG should own

1. **Explicit carryover packaged for paste.** Every competitor "saves chats." No one hands you a structured summary designed for a fresh thread. This is AIMG's flagship.
2. **Thread health as an ambient signal.** No one does this. It's a daily-use trust surface.
3. **Cross-model contradiction detection.** Einstein Fact Checker is the category name we get to own.
4. **Provenance-stamped memory.** Every competitor treats all memory as equal. AIMG can show platform + thread + exchange + confidence.
5. **Browser-first, privacy-obvious.** "You see everything we save" is the trust posture nobody else is running.

### 2.4 Features to add next (ranked)

Ranking criteria: market impact × wow × doctrine fit ÷ implementation difficulty. Every suggestion extends AIMG's identity — no random feature creep.

| # | Feature | Market impact | Wow | Difficulty | Fit | Why it extends the moat |
|---|---|---|---|---|---|---|
| **A** | **Ask Your Memory** — conversational search over all your captured memories in a popup chat ("what did I decide about pricing last week?") | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Medium | High | Turns memory from a passive store into a daily-use surface. Stickiness jumps 10×. Uses the same semantic search already in doctrine. |
| **B** | **Thread Registry** — "Your 23 active Claude threads · 8 Perplexity threads" with last-updated + topic + health score per thread | ⭐⭐⭐⭐ | ⭐⭐⭐ | Low-Med | High | Solves the #1 organizational pain ("which thread had the good info?"). Users discover threads they forgot existed. Foundation for Thread Timeline. |
| **C** | **Weekly AI Digest** — email "This week you had 17 AI conversations covering 5 topics. You made these 12 decisions. Here are the 3 threads to revisit" | ⭐⭐⭐ | ⭐⭐⭐ | Low-Med | High | Retention lever + passive value prop. Paying users stay paying. Also a virality hook (forwards to colleagues = "how does he have this?"). |
| **D** | **Cross-Model Truth Check** — on any AI response, one-click "verify this" sends the claim to a second independent model and shows the comparison | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | High | High | The *real* Einstein moat. "AI that watches AI" moves from tagline to mechanic. Premium Pro/Pro+ feature. Differentiates from every memory tool in the market. |
| **E** | **Cross-Platform Bridge** — explicit "take my Claude context to Perplexity" button that opens the target platform + pre-formats your carryover | ⭐⭐⭐ | ⭐⭐⭐⭐ | Low | High | Makes the cross-platform promise visceral. Feels like switching with a briefcase, not starting over. |
| **F** | **"My AI thinks" card** — one-page summary of what your AI believes about YOU based on all memories, with a "correct this" button per line | ⭐⭐⭐ | ⭐⭐⭐⭐ | Medium | High | Identity mirror. Unexpectedly viral — users screenshot and share ("mine says I'm a chaotic genius"). Also the best onboarding surface. |

**Top 5 picks for next 90 days (by combined score): A, B, D, E, F.**

### 2.5 Ideas Solon may not have been asked for — explicitly flagged

These four are the "things I may not already know to ask for" the directive explicitly requested:

1. **"Ask Your Memory" conversational search.** The memory is already there; the chat surface turns it from filing cabinet into daily tool. This is the single highest-leverage addition.
2. **Thread Registry.** Users have a thread-management problem they haven't articulated. Showing them "your 23 active threads, 12 of which you haven't touched in 30 days" is unreasonably sticky.
3. **Weekly AI Digest (email).** Retention tool disguised as a product feature. Also a referral vector.
4. **"My AI thinks" identity card.** Unexpected viral surface + the best first-use moment for new users.

---

## 3. Brand architecture

### 3.1 Product

- **Name:** AI Memory Guard
- **Shorthand (OK to use):** AIMG
- **Master promise:** *Memory. Trust. Continuity. Across every AI you use.*
- **Alt taglines:**
  - *Never explain yourself to AI twice.*
  - *Continuity for the AI age.*
  - *Your context, everywhere you think.*

### 3.2 Branded feature trio — locked

These three are canonical, capitalized, and treated as product features in all public surfaces.

#### Memory Guard™ (core pillar)

- **What it means publicly:** "We capture the facts, decisions, and corrections that matter from your AI conversations — so you don't re-explain yourself every time you open a new chat."
- **Real mechanics backing it:** rule-based extraction across 8 memory types (fact/decision/preference/correction/action/narrative/episodic/entity); provenance stamping (platform + thread + exchange + timestamp); semantic + lexical search; confidence scoring; per-memory status lifecycle.
- **Safe to claim publicly:** cross-platform capture · memory by type · searchable · provenance-stamped · user-visible · deletable.
- **Don't claim:** "understands you" / "reads between the lines" / "infers your goals" / anything implying AI-grade comprehension beyond rule-based extraction.

#### Thread Health™ (second pillar)

- **What it means publicly:** "A live gauge on every AI conversation so you know before your thread starts degrading."
- **Real mechanics backing it:** exchange counter per thread; 4-zone color model (🟢 Fresh 1-15 / 🟡 Warm 16-30 / 🟠 Hot 31-45 / 🔴 Danger 46+); ambient left-edge meter; in-page warning escalation at exchange 35/46/55; audio chime in red.
- **Safe to claim publicly:** real-time thread depth tracking · visual warning before degradation · suggests fresh thread with context when conversations go long.
- **Don't claim:** "measures AI quality scientifically" / "detects hallucination" / any claim that the health score maps 1:1 to model performance.

#### Einstein Fact Checker™ (third pillar — proprietary AMG capability)

- **What it means publicly:** "A proprietary verification layer that catches contradictions across your AI conversations — when a response disagrees with something you established before, Einstein flags it."
- **Real mechanics backing it:** proprietary confidence scoring · token-overlap contradiction detection against prior canonical memories · contradiction groups · confidence adjustment on supersession · per-tier daily verification cap (10/50/150/300 across Free/Basic/Plus/Pro) · risk tags on flagged memories.
- **Safe to claim publicly:** contradiction flagging · cross-response truth consistency · verification layer · confidence-ranked memory.
- **Don't claim:** "always right" / "AI truth detector" / "prevents hallucinations" / anything implying omniscience. Einstein flags *potential contradictions* — user reviews.
- **Keep the name.** It's memorable, premium-feeling, differentiated, and maps to a real mechanic. Any argument to drop it would have to be overwhelming — and it isn't. Verdict: **lock.**

### 3.3 Secondary branded features (additive, don't overdo)

Only introduce a 4th branded name if the thing genuinely rises to pillar status. Current recommendation: **don't add more branded names in v0.2.0.** Carryover, search, settings are features under the three pillars, not new brands.

**Reserve for later (if built):**
- **Ask Your Memory™** — if we ship the conversational search surface (Section 2.4 feature A), this earns a name.
- **Memory Timeline™** — if we ship replay/scrubber (long-term).
- **Memory Bridge™** — if we ship the explicit cross-platform bridge button.

### 3.4 Visual / verbal identity notes

- **Primary metaphor:** the guard. A calm, attentive presence watching over your conversations. Not a surveillance tool. Not a cop. A librarian with a good memory.
- **Color system (already in code):** dark theme default · accent gradients · 4-zone status colors (green/yellow/orange/red) are load-bearing and must stay.
- **Typography:** sharp, readable, slightly technical. Not whimsical.
- **Iconography:** brain + shield + eye are all available motifs; current icon is a brain. Keep brain-centric visual identity through v1.0.

---

## 4. Canonical landing page copy deck

### A. Hero

**Eyebrow:** For everyone who lives inside AI chat.

**Headline:** **Never explain yourself to AI twice.**

**Subheadline:** AI Memory Guard is the continuity layer that travels with you across Claude, ChatGPT, Gemini, Grok, and Perplexity — capturing what matters, warning you before threads degrade, and handing you a verified carryover so you pick up exactly where you left off.

**Primary CTA:** Install Free

**Secondary CTA:** See how it works

**Trust / support line:** No silent capture. No black-box injection. You see everything we save.

*Alternate headline options, in case of A/B test:*
- *Continuity for the AI age.*
- *Your AI forgets. You shouldn't.*
- *Memory. Trust. Continuity. Across every AI you use.*

### B. Feature section — six blocks

**1. Memory Guard**
*Your AI conversations, finally remembered.*
We capture the facts, decisions, and corrections that matter — stamped with provenance so you always know where they came from. Across every AI you use.

**2. Thread Health**
*Know before your thread goes stale.*
A live gauge on every conversation. When your thread starts getting long, we tell you — and we show you exactly how to start fresh without losing a thing.

**3. Einstein Fact Checker**
*AI that watches AI.*
Our proprietary verification layer flags contradictions across your conversations — when a response disagrees with what you established before, Einstein catches it. Before it costs you.

**4. One-Click Carryover**
*Start a fresh thread. Not from zero.*
When your conversation gets too long, AI Memory Guard generates a structured carryover packet — your goals, decisions, corrections, and open items — ready to paste into a new thread. You approve every word.

**5. One layer. Every AI.**
*Claude. ChatGPT. Gemini. Grok. Perplexity.*
One continuity layer across all of them. Your memory travels with you — no lock-in, no walled garden, no re-explaining yourself every time you switch tools.

**6. Explicit, not silent.**
*You see everything we save.*
Every memory is inspectable. Every capture is visible. Every carryover is reviewed before it's pasted. No background injection. No invisible sync. Privacy is the default, not the upgrade.

### C. How it works — four steps

1. **Install in 10 seconds.** Free. No credit card. Pin it to your browser.
2. **Chat normally.** On Claude, ChatGPT, Gemini, Grok, or Perplexity — keep working the way you already work.
3. **We capture what matters.** Facts, decisions, corrections, action items — stamped with platform + thread + timestamp. Always visible in your popup.
4. **Continue anywhere.** When a thread gets long, one click hands you a verified carryover. Paste it into a fresh thread — same AI or a different one — and pick up exactly where you left off.

### D. Pricing — tiers locked per doctrine

| Tier | Monthly | One-liner | Emphasis | CTA |
|---|---|---|---|---|
| **Free** | **$0** | See how it works. Full continuity, capped verification. | Memory Guard · Thread Health · Einstein (10 checks/day) · basic carryover | **Install Free** |
| **Basic** | **$4.99** | For regular users who want the full memory surface. | Everything in Free · Einstein 50/day · full memory history · extended thread health | **Go Basic** |
| **Plus** | **$9.99** | For power users. Structured carryover. More verification. | Everything in Basic · Einstein 150/day · structured carryover · priority captures | **Go Plus** |
| **Pro** | **$19.99** | For professionals who live inside AI. | Everything in Plus · Einstein 300/day · deduplicated carryover · advanced memory review · priority support | **Go Pro** |

Pricing framing line (under the table): *Start free. Upgrade when your daily Einstein checks run out — not before. You won't.*

### E. Final CTA section

**Closing block:**

> **Your AI conversations are worth more than the tab they live in.**
>
> Every thread has decisions. Corrections. Commitments. Facts you wish you could search tomorrow. AI Memory Guard is the layer that holds onto them — across every AI you use, for as long as you want it to.
>
> No silent capture. No lock-in. No vendor you never heard of owning your context.
>
> **Install free. Never explain yourself to AI twice.**
>
> **[Install AI Memory Guard — Free]**
>
> *Works with Claude, ChatGPT, Gemini, Grok, and Perplexity. Chrome-first. Takes 10 seconds.*

---

## 5. Product-truth / claim safety table

| Claim | Safe publicly? | Why | Recommended phrasing |
|---|---|---|---|
| "Captures memories across 5 AI platforms" | ✅ Yes | True — manifest covers Claude, ChatGPT, Gemini, Grok, Perplexity | "Works across Claude, ChatGPT, Gemini, Grok, and Perplexity." |
| "Powered by Perplexity" / "Uses OpenAI" / "Anthropic-verified" | ❌ No | Vendor reveal — violates trade-secret rule | Use: "proprietary verification layer," "AMG verification stack" |
| "Einstein Fact Checker catches AI hallucinations" | 🟡 Soften | "Hallucinations" is overclaim; Einstein detects *contradictions against prior memories*, not ground-truth falsehood | "Flags contradictions across your conversations" |
| "Your memories are private" | ✅ Yes, with context | RLS-enforced user isolation is real | "Your memories stay yours. Row-level security ensures only you can see them." |
| "Prevents AI hallucinations" | ❌ No | Overclaim — we flag, we don't prevent | "Helps you catch AI mistakes before they cost you" |
| "Reduces AI hallucinations" | 🟡 Soften | Still strong; soften to behavioral reality | "Surfaces contradictions so you can correct them in real time" |
| "Cross-platform continuity" | ✅ Yes | Core product truth | "One continuity layer across every AI you use" |
| "Proprietary verification layer" | ✅ Yes | Doctrine-approved trade-secret framing | Use liberally — this is the preferred wording |
| "Semantic memory search" | ✅ Yes | pgvector + hybrid BM25+RRF is real | "Search by meaning, not just keyword" |
| "Thread health monitoring" | ✅ Yes | Real mechanic (exchange counter + 4-zone model) | "Live gauge on every conversation" |
| "One-click carryover" | ✅ Yes | Real feature | "A verified carryover you paste into a fresh thread" |
| "You see everything we save" | ✅ Yes | Provenance surface is real (popup shows every row) | Preserve this exact phrasing — it's a trust signature |
| "Works offline" | 🟡 Soften | Local extraction works; sync needs connection | "Captures locally; syncs when you're online" |
| "Military-grade encryption" | ❌ No | Cliché + unverifiable + misleading | Don't use. Say: "TLS in transit · encrypted at rest." |
| "Enterprise-ready" | 🟡 Soften | Not yet — no SSO, no audit controls, no SOC2 | Don't claim this until it's true. Safe alternative: "For professionals who live inside AI." |
| "Used by Fortune 500" | ❌ No | False | Don't claim. Say: "Built for power users." |
| "AI that watches AI" | ✅ Yes | Conceptual framing — honest about what Einstein does | Use freely |
| "Zero vendor lock-in" | 🟡 Soften | True for the memory layer, not necessarily for the extension | "Your memory isn't trapped in any single AI" |
| "Never sells your data" | ✅ Yes | Policy commitment — easy to keep | "We don't sell your data. Ever." |
| "No silent injection" | ✅ Yes | True and differentiating | Preserve — this is a trust signature |
| "Captures from your AI agents automatically" | ❌ No | Implies Titan/Claude Code capture, which is false for browser product | Don't use |
| "Your context travels with you" | ✅ Yes | Core promise, backed by real carryover | Preserve |
| "Remembers everything" | 🟡 Soften | We remember what you capture; we don't read minds | "Remembers what matters" |
| "Smarter than AI memory features" | 🟡 Soften | True in cross-platform sense, not in all dimensions | "Works across every AI — not locked to one" |
| "Free forever" | ✅ Yes | Free tier is real and durable | "Free tier stays free." |
| "Privacy by default" | ✅ Yes | User-scoped, visible, deletable | Preserve — trust signature |
| "Built solo in Boston" | ✅ Yes, optional | Founder signal, doesn't leak vendors | Use in About page, not front page |
| "Self-hosted option" | ❌ No | Not true for consumer product | Don't claim |

**Meta-rule:** every public claim must trace to a real product mechanic in the current codebase OR a clearly-flagged near-term buildable feature. Marketing rides ahead of engineering by weeks, not quarters.

---

## 6. Recommended next build priorities — top 3 (post-hardening)

After `plans/PLAN_2026-04-16_aimg_continuity_hardening.md` Phases 1-5 ship v0.2.0 to the store:

### #1 — Ask Your Memory

Conversational search as a popup surface. User types a question ("what did I decide about pricing last week?") and Ask Your Memory returns the relevant canonical memories + a short synthesized answer with citations. Uses the semantic search + hybrid retrieval already in doctrine.

**Why #1:** turns AIMG from a passive store into a daily-use tool. Stickiness multiplier is ~10×. It's the single highest-leverage feature addition in the roadmap. Also the most demo-able.

**Risk:** must not hallucinate. Every citation surfaces the source memory row. No free-form generation without attribution.

### #2 — Thread Registry

"Your active AI threads" surface in the popup: list of all threads across all 5 platforms, each with last-updated, platform, topic summary, exchange count, thread-health badge. Click any row → opens that thread in its platform.

**Why #2:** users discover threads they forgot existed. Solves the #1 organizational pain. Foundation for future Thread Timeline / Replay work. Low-medium implementation lift.

### #3 — Cross-Model Truth Check (Einstein Pro)

One-click "verify this" button on any captured AI response. Sends the claim to a *second independent model* (the provider abstracted away from public copy) and shows a side-by-side comparison: "Model A said X. Model B said Y. Here's where they diverge." Premium feature — gated to Plus / Pro / Pro+.

**Why #3:** this is the real Einstein moat. "AI that watches AI" moves from tagline to load-bearing mechanic. Differentiates from every memory tool in the market. The justification for Pro tier pricing.

**Risk:** cost control. Cross-model calls burn money. Daily caps per tier (same structure as current Einstein caps: 10/50/150/300) + per-claim throttling.

---

## Grading block

Per §12 + §12.5 of CLAUDE.md doctrine: this document is **NOT ready** until graded A- or better.

**Method:** direct Perplexity sonar-pro via `lib/war_room.py` per Solon 2026-04-16 instruction. Aristotle-in-Slack is fallback.

**Minimum passing grade:** A- (≥ 9.0 / 10).

**Dimensions pending:**

| Dimension | Score | Notes |
|---|---|---|
| 1. Category-defining positioning strength | — | PENDING |
| 2. Market gap realism (backed by market signals) | — | PENDING |
| 3. Brand architecture coherence | — | PENDING |
| 4. Copy voice — premium vs template SaaS | — | PENDING |
| 5. Claim safety — trade-secret compliance | — | PENDING |
| 6. Pricing alignment with doctrine | — | PENDING |
| 7. Feature recommendations — fit + impact | — | PENDING |
| 8. Internal consistency (positioning ↔ copy ↔ claims) | — | PENDING |
| 9. Differentiation from competitors | — | PENDING |
| 10. Ready-to-deploy quality | — | PENDING |

**Overall:** PENDING_SONAR_A_MINUS
**Revision rounds:** 0

**Decision:** HOLD — do not deploy to landing page or store listing until graded A- and Solon signs off.

---

*End of strategy pass. Canonical until superseded by a later-dated strategy doc. Survives restart.*
