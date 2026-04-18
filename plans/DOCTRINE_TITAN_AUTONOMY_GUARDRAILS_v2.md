# DUAL-GRADER COST MATH + TITAN AUTONOMY GUARDRAILS + AIMG ARCHITECTURE CORRECTION
**Date:** 2026-04-17 EOD

---

## PART 1 — DUAL-GRADER COST MATH

### Current pricing (verified 2026-04-17)

- **Claude Haiku 4.5:** $1.00/M input · $5.00/M output
- **Gemini 2.5 Flash Lite:** $0.10/M input · $0.40/M output (cheapest current-gen Gemini)

Batch API (where applicable) cuts both by 50%. Prompt caching cuts cached input by 90%.

### Scenario A — Titan phase-gate grading (internal doctrine/spec/artifact validation)

Typical grading call:
- Input: ~3,000 tokens (the artifact being graded + rubric prompt)
- Output: ~800 tokens (structured score + issues + recommendations)

**Per-grading cost:**
| Grader | Input cost | Output cost | Total per call |
|---|---|---|---|
| Haiku 4.5 | 3,000 × $1.00/M = $0.003 | 800 × $5.00/M = $0.004 | **$0.007** |
| Gemini 2.5 Flash Lite | 3,000 × $0.10/M = $0.0003 | 800 × $0.40/M = $0.00032 | **$0.00062** |
| **Combined dual-grader** | — | — | **~$0.0076 per artifact** |

**At volume:**
- 50 artifacts/week × 52 weeks = 2,600/year → **$19.76/year**
- 200 artifacts/week × 52 weeks = 10,400/year → **$79.04/year**

**Verdict:** cost is negligible. You're right — this is absolutely fine as the standing Titan dual-grader pair. Shifts current Gemini Flash + Grok to Haiku 4.5 + Gemini 2.5 Flash Lite. Dramatically cheaper, two-grader cross-check preserved.

---

### Scenario B — AIMG Einstein Fact Checker (subscriber-facing, per AI response)

Typical call per AI response checked:
- Input: ~2,500 tokens (user's AI output + context + check prompt)
- Output: ~400 tokens (flagged spans + severity + explanation)

**Per-check cost:**
| Grader | Input cost | Output cost | Total per call |
|---|---|---|---|
| Haiku 4.5 | 2,500 × $1.00/M = $0.0025 | 400 × $5.00/M = $0.002 | **$0.0045** |
| Gemini 2.5 Flash Lite | 2,500 × $0.10/M = $0.00025 | 400 × $0.40/M = $0.00016 | **$0.00041** |
| **Combined dual-check** | — | — | **~$0.0049 per AI response checked** |

**At subscriber-volume (rough estimate — actual depends on user behavior):**
- Average subscriber runs ~20 AI prompts/day × 30 days = 600 checks/month
- Cost per subscriber: 600 × $0.0049 = **$2.94/month per subscriber**

**Pricing tier impact:**
- Pro ($9.99/mo): $2.94 fact-check cost → gross margin ~70% (down from ~90% w/ single cheap grader)
- Pro+ ($19.99/mo): $2.94 fact-check cost → gross margin ~85%

Add base infra allocation (Supabase, Cloudflare, extension hosting): ~$0.30/subscriber/mo
- Pro total cost ~$3.24 → ~68% margin
- Pro+ total cost ~$3.24 → ~84% margin

**Verdict:** Solon's 80% margin estimate is conservative-correct for Pro+. Pro tier drops to 68% but remains healthy. Dual-grader fact-checking is affordable for AIMG subscriber-facing use.

**Heavy-user cap recommended:** set a per-subscriber monthly fact-check cap (e.g., 3,000 checks/mo = $14.70 cost on Pro tier). Beyond cap: throttle to single-grader (Gemini Flash Lite only, $0.00041/check). Protects margin on power users.

---

### Scenario C — Einstein Premium (Sonar Basic upgrade for AMG subscribers)

Perplexity Sonar Basic pricing: $1/M input, $1/M output + $5/1,000 requests for grounding.

Typical Sonar Basic call:
- Input: ~2,000 tokens
- Output: ~500 tokens  
- Grounding: 1 request

**Per-check cost:**
- Input: 2,000 × $1.00/M = $0.002
- Output: 500 × $1.00/M = $0.0005
- Grounding: $0.005
- **Total: $0.0075 per premium fact-check**

At 600 checks/mo: **$4.50/subscriber/mo for Sonar Basic premium upgrade.**

**Verdict:** viable for AMG Growth ($797) and Pro ($1,497) tiers as "Einstein Premium" differentiator. Add ~$4.50 infra cost per client per month — rounding error against those tier prices. Starter ($497) stays on Haiku+Gemini dual-grader, no Sonar.

---

### Recommended grading stack (final)

| Surface | Graders | Per-unit cost | Monthly ceiling |
|---|---|---|---|
| **Titan phase-gates + artifact validation** | Haiku 4.5 + Gemini 2.5 Flash Lite | $0.0076/artifact | $10/mo at current pace |
| **AIMG Free tier** | single grader (Gemini 2.5 Flash Lite only) | $0.00041/check | $0.25/user/mo |
| **AIMG Pro ($9.99)** | Haiku 4.5 + Gemini 2.5 Flash Lite dual | $0.0049/check, capped at 3000/mo | $14.70/user ceiling |
| **AIMG Pro+ ($19.99)** | Haiku 4.5 + Gemini 2.5 Flash Lite dual, higher cap | $0.0049/check, capped at 6000/mo | $29.40/user ceiling |
| **AMG Starter ($497)** | Dual Haiku + Gemini | Negligible at subscriber volumes | — |
| **AMG Growth ($797) "Einstein Premium"** | Perplexity Sonar Basic added | $0.0075/check, reasonable cap | part of tier value |
| **AMG Pro ($1,497) "Einstein Premium"** | Sonar Basic + higher caps | Same as Growth, unlimited-feeling cap | part of tier value |

---

## PART 2 — AIMG ARCHITECTURE CORRECTION

**EOM was wrong earlier.** Pre-generation interception was my mistake.

**Correct architecture:** POST-output fact-checking.

- AI produces response (completes streaming)
- Extension immediately flags problem spans with inline visual indicators
- Subscriber reads the response with flags visible
- Subscriber chooses to correct, ignore, or export flagged content
- Correction is user-initiated, not forced
- Free for paid-tier subscribers — part of what they pay for

**Why this is right:**
- Doesn't break the user's reading flow (pre-gen interception would interrupt streaming, which users hate)
- Fact-checking works on a complete thought, not fragments mid-stream
- User agency preserved (they decide what matters)
- Matches Grammarly-style UX users already understand
- Dual-grader (Haiku + Gemini Flash Lite) runs in parallel for ~$0.005/check — fast enough to feel near-instant

**This supersedes Addendums #3/#4/#5/#6 wherever they reference pre-generation interception for AIMG extension.**

---

## PART 3 — HETZNER VPS — CLOSED

Hetzner secondary VPS is LIVE and working (Solon confirmed with Titan earlier 2026-04-17). DR-AMG-RECOVERY-01 standby VPS item closes. Removed from post-weekend backlog. Do not re-surface.

---

## PART 4 — TITAN AUTONOMY GUARDRAILS (beyond Solon OS)

Solon OS will improve Titan's judgment by giving him your decision patterns. But the bigger wins are mechanical — rules Titan cannot reason around:

### 4.1 — "Completion requires evidence" hard-gate

No `update_task` to `status: done` or MCP `log_decision` claiming completion unless:
- A verifiable artifact URL is attached, OR
- A diff/commit hash is attached, OR
- A screenshot is attached

Pre-commit hook or MCP middleware rejects completion markers missing evidence. Forces Titan to produce proof alongside claim.

### 4.2 — Pre-action Aristotle mini-scan

Before ANY destructive operation or new system build, Titan runs a 60-second risk check:
- Financial risk: new cost exposure without cap?
- Security risk: new attack surface?
- SPOF risk: what breaks if this goes down?
- Strategic risk: time-sensitive items ignored?

Logged to MCP as pre-action scan. Skipping = protocol violation.

### 4.3 — Automatic Perplexity consult on blockers

15 minutes stuck on a blocker = auto-query Perplexity API before escalating to Solon. Titan already has the API key. Enforce with a timer, not a rule.

### 4.4 — "Would I bet $500?" assertion filter

Before any factual claim in a deliverable or MCP log:
- Can I point to the specific source?
- Is this in Encyclopedia / Hammer / Pricing SOT / live-site / Viktor folder?
- Would I bet $500 this is accurate?

If no to any → flag as ⚠️ UNVERIFIED or omit. Titan applies to every claim, not just big ones.

### 4.5 — "Can Solon see this?" completion test

Before marking any task complete, Titan asks: is the outcome visible to Solon right now without him asking follow-up questions?

If the answer is "it's on VPS at /opt/..." or "it's a backend change" — task is NOT complete. Task is complete when Solon can see the result in the product, on a URL, in Slack, or in his inbox.

### 4.6 — Dual-grader hard-floor enforcement

Both graders must score ≥9.3. If EITHER grader drops below, revise and re-grade. No averaging to pass. Self-grade rejected. Haiku 4.5 + Gemini 2.5 Flash Lite is the new standing pair.

### 4.7 — Sequential discipline enforcement

Titan cannot open a new major task while a prior major task has open sub-items. Forces finish-before-start. Blockers on a current task go to `#solon-command`, not "I'll just work on something else while you decide."

### 4.8 — Trade-secret runtime filter (already in Addendum #3 Part X, extend)

Extended scrub list per Addendum #6 + AIMG content. Runtime regex+substring scrub before any response or artifact ships externally. Leak attempts log to MCP + Slack. Already specified, reinforced here.

### 4.9 — Solon OS as pattern library, not autopilot

When Solon OS completes, Titan uses it as a reference for Solon's decision patterns — NOT as a replacement for Solon's actual decisions. Important or novel decisions still escalate to Solon. Solon OS just reduces the volume of trivial ask-backs by letting Titan answer them the way Solon would.

---

## PART 5 — WHAT TITAN DOES WITH THESE

When Solon boots Titan for the weekend sprint, Titan inherits:
- The 8 execution docs + addendums
- The Titan Boot Prompt v2
- **PLUS the guardrails above** (4.1 through 4.9) baked into his operating rules

Titan reads this file during boot, applies the guardrails immediately, and uses the new dual-grader pair (Haiku 4.5 + Gemini 2.5 Flash Lite) for all phase-gate grading going forward.

---

**End of file.**
