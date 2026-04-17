# Riley — KB 05 Reference Data

## Encyclopedia v1.3

Reputation bundled in Chamber OS module catalog (v1.3 §10). Solicitation sequences + dispute filings covered in Starter / Growth / Pro tiers.

## client_facts (via op_get_client_facts)

Per-subscriber reputation context:
- `review_platforms` — list of active platforms + URLs
- `review_voice_samples` — subscriber-owned response examples (for Riley to match)
- `review_comp_policy` — what comp/offer is subscriber-approved by review tier
- `review_banned_topics` — topics to avoid in responses
- `review_owner_escalation_threshold` — when to pull subscriber personally into the loop (e.g., 2-star or below automatic)
- `review_solicitation_opt_in` — customer data source subscriber has opt-in for solicitation

## Review platforms (active in AMG)

**Tier 1 (universal coverage):**
- Google Business Profile (reviews + Q&A)
- Yelp
- Facebook Recommendations
- BBB

**Tier 2 (category-specific):**
- Tripadvisor (hospitality / restaurants / attractions)
- OpenTable (restaurants)
- Healthgrades / Vitals / RateMDs (medical)
- Avvo / Martindale / Justia (legal)
- Angi / HomeAdvisor / Thumbtack (home services)
- Capterra / G2 (SaaS / software)
- Glassdoor (employer reviews)
- Nextdoor Neighborhood (community-local)

## Response voice baselines (before subscriber-specific voice samples)

### 5-star positive
- Warm, specific to review content, ≤3 sentences
- Template: "Thanks, [First Name] — glad the [specific detail] worked out. Come back anytime."

### 4-star mostly-positive
- Thank + acknowledge specific gap + specific action
- Template: "Thanks for the honest feedback, [First Name]. We hear you on [specific gap]. Come by and ask for [owner] if you want to talk through it."

### 3-star mixed
- Thank + directly address issue + brief action
- Template: "[First Name] — we want to make this right. Stop in this week, ask for [owner]. [Coffee/first drink/slice] is on us while we figure it out."

### 2-star negative
- Warm acknowledgment + specific action + direct-contact offer
- Template: "[First Name] — this isn't how we want you remembering us. [Owner] will call you personally at [day/time]. We want to fix this."
- **Hold for owner approval before publishing.**

### 1-star severe
- Cooling-off 30 min first
- Template: "[First Name] — we're sorry. [Owner] is calling you today. We're going to make this right."
- **Hold for owner approval + direct-owner phone follow-up.**

## Response timing targets

- 5-star: <14 min
- 4-star: <1 hour
- 3-star: <2 hours
- 2-star: <4 hours (cooling-off buffer; then subscriber approval; then publish)
- 1-star: <8 hours (same as 2-star but longer cooling-off + subscriber phone involvement)
- Spam / obvious fake: file TOS dispute first, no response needed until platform rules

## Comp / offer matrix (starting guidance; subscriber overrides)

- 5-star: no comp needed
- 4-star: no comp unless review mentions specific fixable gap
- 3-star: small comp ($10-25 value) if gap was service-quality
- 2-star: meaningful comp ($25-75 value) + personal follow-up
- 1-star: situational — sometimes no comp (if issue was unfair/fabricated); sometimes major gesture
- **Subscriber-specific:** client_facts.review_comp_policy overrides defaults

## Solicitation-sequence best practices (CAN-SPAM + TCPA + platform-TOS compliant)

### Email solicitation
- Opt-in only (CAN-SPAM)
- Branded honest sender identity (subscriber business name + valid reply-to)
- Ask for review ONLY; never route positive-only vs negative-only to different platforms (Google TOS violation — "review-gating")
- Opt-out link on every email
- Timing: post-transaction +3 to +14 days (category-dependent)
- Frequency cap: 1 review request per transaction, max 2 reminders

### SMS solicitation (requires TCPA opt-in)
- Opt-in documented per TCPA
- "Reply STOP" on every message
- Timing: post-transaction +1 to +7 days
- Frequency cap: 1 request + 1 reminder

### In-person ask
- Natural, not scripted
- Best timing: at moment of positive interaction (end of meal, after repair, during final walk-through)
- Follow up with QR code card or email reminder

## Platform TOS quick-reference (compliance)

- **Google Review Policy (current):** No review-gating, no solicitation gifts for reviews, no responding with discriminatory language, no fake reviews (first-party or reviewer-side)
- **Yelp:** Active anti-solicitation enforcement; don't ask family/friends/employees for reviews; Yelp actively removes reviews from customers recently asked
- **Tripadvisor:** Allows solicitation but flags suspicious patterns; natural post-stay timing best
- **BBB:** Complaint-resolution oriented; response to formal complaint is separate track from reviews

## Reputation dashboard composite score formula (AMG default)

- 40% — Star rating average (weighted across platforms per subscriber category)
- 25% — Review velocity (new reviews past 30d / last 90d avg)
- 20% — Response rate (% of reviews responded to within Riley target-time)
- 15% — Sentiment trend (keyword-theme positive vs negative over 90d)

Score 0-100; <70 red-flag; 70-85 stable; 85-95 strong; 95+ exceptional.

## Anti-patterns catalog

- **Review-gating** (routing happy customers to public review platforms, unhappy to private channels) — Google TOS violation
- **Paid reviews** — fraudulent + TOS violation
- **Family/employee reviews** — platform-detectable + erodes trust
- **Templated responses** — readers can tell; erodes authentic-voice signal
- **Publicly arguing with reviewers** — never wins; always shift to direct channel
- **Ignoring 5-star reviews** — silent positives feel cold; respond to all stars
- **Auto-published responses with AI-signal wording** — "Thank you for your valuable feedback, we appreciate your business" — auto-flag by reviewers as inauthentic
