# Lumina — KB 12 Competitor Baseline (v2.0, added 2026-04-19 CT-0419-05)

## Purpose

Revenue-critical client-facing deliverables (Don-Demo sprints, founding-partner pitches, board demos) are evaluated not only against the Tier-A elite reference stack but also against the cohort of competitors the client is actively quoting. The bar isn't "good design" — it's "better than the other three quotes on the buyer's desk."

This file documents:

1. **Who Don is likely quoting** (as of CT-0419-05 2026-04-19) — a research-derived list of MA-local digital agencies, chamber-partnership agencies, enterprise marketing/SEO firms
2. **The 3-competitor blind-test rubric** used for the Don-Proof benchmark
3. **Patterns to draw from** (what competitors do well — study and exceed) and **anti-patterns** (what the cohort does badly — actively avoid)

## Don-Demo competitor cohort (initial research scope)

**Context:** Don Martelli is the Revere Chamber Board President. He has state grant money to spend on the Chamber's first significant AI/marketing engagement. He is actively collecting 3+ competitive quotes. AMG must show up visually stronger than the other 3 quotes to earn the founding-partner signature.

**Likely cohort (research sources: MA Chamber of Commerce partner-agency lists, state grant vendor pools, Chamber AI Advantage competitive landscape):**

### Local MA digital agencies (5+)

- **HawkPoint Marketing** (hawkpointmarketing.com) — Boston-area digital agency, strong Chamber-partnership history
- **NewBreed Marketing** (newbreedmarketing.com) — B2B lead-gen agency, local footprint
- **SilverCrest Digital** (silvercrestdigital.com) — local SEO + web dev, Chamber-member-facing
- **CTG Boston** (ctg-boston.com) — MA enterprise digital firm
- **Bluleadz** (bluleadz.com) — inbound marketing agency, HubSpot partner

### Chamber-partnership national agencies (3+)

- **360 Chamber Solutions** (360chambersolutions.com) — chamber membership + marketing services
- **ChamberMaster / GrowthZone** (growthzone.com) — chamber management + member-marketing
- **MemberClicks** (memberclicks.com) — association management platform with marketing modules

### Enterprise SEO/marketing firms (2+)

- **WebFX** (webfx.com) — enterprise SEO/marketing, national
- **Thrive Internet Marketing** (thriveagency.com) — enterprise digital marketing, national

## How to use this cohort in a review

For every revenue-critical client-facing deliverable, Lumina MUST:

1. **Pre-execution:** visit 3 randomly sampled cohort sites (rotate selection across deliverables). Note in the approval YAML's `competitor_baseline.corpus` which 3 were sampled.
2. **During execution:** identify 3 specific patterns to EXCEED (not match). Name them in comments in your executed code.
3. **Post-execution:** apply the 3-competitor blind-test rubric below. Target wins ≥2/3.

## 3-competitor blind-test rubric

### Setup

- Screenshot 3 competitor sites at 1440px desktop + 375px mobile (same viewports, same browser, same 10s settle for any animation)
- Screenshot our artifact at the same viewports
- Present 4 screenshots in a 2×2 grid with no labels (blind test)
- If time permits: recruit 3 third-party reviewers via Slack #amg-ops pulse, ask "which of these 4 looks like the most expensive design?"
- If no time: Lumina self-scores each pair honestly against these criteria

### Scoring dimensions (per blind pair, 1-5 scale)

1. **Immediate premium read (0.5s glance)** — does it signal "expensive" in the first half-second?
2. **Typography polish (5s read)** — does the font pairing, weight, and rhythm feel like a designer made it vs a template?
3. **Color depth (5s look)** — does the palette have purposeful contrast, deliberate gradients, or is it flat/default?
4. **Motion + micro-interaction (if live)** — is there any ambient motion? Hover feedback? Or is it static?
5. **Whitespace generosity** — does it breathe, or is it cramped?

Pair wins when AMG beats competitor on 3/5 dimensions minimum.

### Target outcome

- **2/3 cohort pair wins** → artifact passes the Don-Proof benchmark, cleared to ship
- **1/3 or 0/3** → artifact needs revision before ship, regardless of internal Lumina score
- **3/3** → exemplary, candidate for vertical template

## Patterns to EXCEED (what competitors do well)

1. **Trust-signal density** — most competitor sites front-load logos, metrics, testimonials. Match or exceed — but make ours REAL (actual client names, actual metrics, actual testimonials with signed release). Fake social proof = authenticity fail.
2. **Pricing transparency** — enterprise agencies hide pricing; local agencies show ranges. Ours shows specific tiers with clear delta between them (Atlas Lite $995 / Core $2500 / Metro $6500 / Enterprise $10K per 2026-04-19 Chamber AI Advantage locked doctrine).
3. **Case-study depth** — cohort cases are usually logo + 2-sentence summary. Ours should be logo + real metric + before/after + signed client quote.
4. **Lead-capture UX** — forms, CTAs, chatbot entry points. Match the density, exceed on speed (SSE streaming chatbot, <500ms voice first-audio).

## Anti-patterns (what the cohort does badly — actively avoid)

1. **Template-ish hero images** — every agency has a hero photo of a team meeting, a laptop-on-a-desk, or an abstract gradient with "WE DO MARKETING" in bold. Avoid. Use real product demo, live voice AI, or deliberate custom illustration.
2. **Stock testimonials / fake star ratings** — "5 stars" with no review source, or LinkedIn-photo faces that look AI-generated. Auto-fail authenticity. Ours are real, signed, linked.
3. **Bootstrap-4 card grids** — identical 3-up service cards with icon + h3 + paragraph + "Learn More" button. Dated visual grammar. Replace with differentiated cards per agent with unique iconography + per-agent mini-KPI + live-demo hover.
4. **Generic enterprise copy** — "empowering businesses to achieve more," "unlock the power of," "cutting-edge solutions." Replace with specific client language + verifiable claims.
5. **No mobile polish** — many competitor sites are laptop-optimized with compressed mobile. Ours is mobile-first.
6. **Zero motion** — cohort is mostly static pages. Deliberate motion is a trust signal that a designer/engineer cared.
7. **Default browser focus rings** — cohort tends to remove them entirely (accessibility fail) or leave browser default (craft fail). Ours are branded + visible + WCAG compliant.

## Research refresh cadence

This corpus ages. Refresh requires:

- Re-visit all 10+ sites quarterly or before any new revenue-critical pitch
- Capture updated screenshots + note pattern changes
- If any competitor does a significant redesign, flag it in MCP `lumina-competitor-update` tag
- Update this doc with findings

Next scheduled refresh: **2026-07-19** or on next revenue-critical pitch, whichever is sooner.

## Honesty clause

If an artifact fails the blind-test (wins 0/3 or 1/3), Lumina reports that honestly. The right move is iterate or flag blocker — not to fudge the scoring so the ship can go through. Solon would rather delay a pitch than lose it because a competitor's site looked better than ours.

"We lost to competitor portfolios" is the exact failure mode CT-0419-05 was created to prevent. The corpus exists to keep Lumina honest about whether we actually beat them.
