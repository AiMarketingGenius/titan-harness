# AMG Pricing Guardrail — Provisional Doctrine

**Status:** LOCKED as doctrine 2026-04-12 per Solon directive. Supersedes every other pricing number in any Atlas plan, doctrine, script, or example transcript until a dedicated full AMG Pricing Doctrine file is created, graded A by the Reviewer Loop, and explicitly approved by Solon.

**Scope:** Every price number Atlas renders — in live voice, in text, in example transcripts, in prompts, in QA scenarios, in demo copy, anywhere — MUST originate from the canonical anchors in §1 below or be a range explicitly derived from them per §2.

---

## 1. Canonical AMG Tier Anchors (only legal source of price numbers)

| Tier | Monthly price (USD) | Notes |
|---|---|---|
| **Starter** | **$497 / month** | Entry-level AMG retainer. |
| **Growth** | **$797 / month** | Mid-tier AMG retainer. |
| **Pro** | **$1,497 / month** | Full-service AMG retainer. |
| **Shield (tier 1)** | **$97 / month** | Shield add-on / reputation guardrail. |
| **Shield (tier 2)** | **$197 / month** | Shield upgrade. |
| **Shield (tier 3)** | **$347 / month** | Shield top tier. |

These are the **only** numbers Atlas may quote directly. No other monthly retainers, no other Shield tiers, no other fixed dollar amounts in any Atlas surface until Solon approves a separate pricing doctrine.

## 2. Derived-pricing rules

When Atlas needs a range in demo copy (e.g. "what do most clients invest?"), it MUST derive from the anchors above:

- **Low end = Starter** ($497/mo)
- **High end = Pro** ($1,497/mo)
- Legal phrasings:
  - "Most clients invest between $497 and $1,497 per month."
  - "Entry point is $497/month; full-service is $1,497/month."
  - "We have a Starter at around $500, a Growth tier near $800, and Pro at roughly $1,500."
- Qualitative phrasings (preferred for public site demos):
  - "Entry level"
  - "Most clients invest between our Starter and Pro tiers"
  - "Our mid-tier Growth retainer"

## 3. One-time audits

One-time audits are **allowed as a concept** but must be priced **explicitly as fractions of the anchor tiers** and must be flagged as *provisional* in any user-facing copy until a dedicated pricing doctrine is approved. Example legal phrasings:

- "An audit is usually priced somewhere around half of a Starter month" (≈ $249)
- "One-time audit, priced at roughly a Starter month" (≈ $497)
- "Deep dive audit, roughly the price of a Growth month" (≈ $797)

## 4. Banned behaviors (HARD RULES)

Atlas MUST NOT:

1. **Invent new tiers** that are not in §1.
2. **Invent new numbers** outside of §1 or §3 derivations.
3. **Quote fabricated ranges** like "$1,500–$15,000/month" or "$4,000–$8,000 a month" or any number pulled from superseded plan files.
4. **Quote specific audit prices** other than the fractions enumerated in §3.
5. **Quote Shield tiers other than** $97 / $197 / $347.
6. **Stack tiers** ("Starter plus Growth equals $1,294") without the user explicitly asking for a multi-tier quote.

Any violation is a HARD FAIL for the Reviewer Loop and the utterance must be rewritten.

## 5. Shipping guardrail (production / demo context gate)

Atlas MUST NOT expose **dynamic, user-facing pricing** to real visitors on the **production site** until ALL of the following are true:

1. A dedicated AMG Pricing Doctrine file is created in `plans/DOCTRINE_AMG_PRICING_*.md`.
2. That doctrine passes the Reviewer Loop with grade A or A- and zero risk tags.
3. Solon explicitly approves it.

Until then, pricing-delivery flows must run in one of these modes:

- **Demo-staging context** — URL path explicitly marked as staging (e.g. `os.aimarketinggenius.io/atlas-staging`, `staging.atlas.*`, localhost, desktop app only).
- **Demo-loop gated** — only shown inside Flow C (founder "wow" demo) or the Loom recording flow, never the default public orb.
- **Qualitative-only** — when Atlas's response reaches the general public through the production orb, use only the qualitative phrasings in §2 ("entry level", "most clients invest between our Starter and Pro tiers").

## 6. Superseded numbers from prior docs (NOT VALID)

The following dollar amounts that appear in `plans/DOCTRINE_ATLAS_ORB_UX_BLUEPRINT.md` and elsewhere are explicitly NOT authoritative and Atlas must not quote them:

- "$1,500–$3,000/mo SEO Foundation"
- "$500 audit" (unless re-stated as "about a Starter month")
- "$4,000–$15,000/mo range" (fabricated full-retainer ranges)
- "$4,000 and $8,000 a month" (Flow C founder-demo transcript)
- Any Part 3.2 "AMG Service Pricing Tiers" table numbers
- Any BANT-branch pricing ranges that reference the invented numbers

These are retained in the original doctrine text for historical fidelity but are **overridden by this guardrail doctrine**. The blueprint's flows, orb visuals, conversation structure, guardrails, and escalation behavior remain canonical — only the pricing numbers are invalidated.

## 7. Implementation rules for Titan

1. The Atlas LLM system prompt MUST embed §1 as a literal dollar table and §4 as hard constraints.
2. Every Atlas response generation must run a regex post-filter that matches `\\$\\d[\\d,]*` and rejects any match not in the whitelist `{$97, $197, $347, $497, $797, $1,497}` (plus the derived audit values `$249, $497, $797`). Rejection triggers a Claude-side retry with a banned-number reminder.
3. The QA scenario bank must not contain any invented dollar amounts.
4. The pricing delivery flow (Flow A step 9, Flow C step 3) must use the Anchor → Range → Value → CTA pattern from the orb doctrine but substitute the canonical numbers above.
5. The BANT budget question may still be asked (Flow A Q3 "pilot budget / under five figures / ready to go bigger"), but Atlas MUST NOT propose any custom dollar figure back to the user — only map the answer to Starter / Growth / Pro.

## 8. Review cadence

This doctrine is **provisional**. It holds the line until Solon approves a full AMG Pricing Doctrine. Titan must not edit this file without an explicit Solon directive — it counts as a doctrine edit (Hard Limit).
