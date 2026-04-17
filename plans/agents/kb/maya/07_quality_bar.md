# Maya — KB 07 Quality Bar

## What 9.3+ Maya work looks like

A Maya-approved piece clears on:

1. **Voice authenticity** — reads like subscriber's real voice, not generic; passes the "would they actually say this out loud?" test
2. **Specificity density** — names/places/dates/numbers in 60%+ of sentences where they could appear
3. **Zero filler** — no boilerplate openers, no hedge-chains, no redundancies
4. **Clear next step** — reader knows what to do (buy / read / reply / book)
5. **Trade-secret clean** — no Claude/GPT/Gemini/etc. in content
6. **Length appropriate** — matched to surface (email <200 words, blog 800-1500, caption tuned to platform)

## 5-dimension rubric

| Dim | Weight | What 10/10 looks like |
|---|---|---|
| Voice | 25% | Subscriber's voice-samples adopted; reads aloud like them |
| Specificity | 20% | Named people/places/dates/numbers; zero abstractions where specifics fit |
| Hierarchy | 20% | Hook → thesis → proof → payoff; reader's eye moves predictably |
| Craft | 20% | Sentence rhythm varied; verbs > adjectives; active voice default |
| Compliance | 15% | Trade-secret clean; pricing accurate (v1.3); no fabricated data |

Weighted avg ≥ 9.3 → submit to Lumina (if visual) or subscriber. Floor on any single dim: 8.5.

## Exemplars

### Exemplar 1 — cold outbound

**Brief:** Nadia asks for a cold email to Revere-adjacent auto-body shops, subscriber is Joe's Pizza of Revere pitching referral-partnership.

**Draft (9.5/10):**
> Subject: Joe's Pizza — referral idea
>
> Hi Tom,
>
> Joe Pioli over at Joe's Pizza of Revere. You handle body work for half the Pacini family, so I figure you know the neighborhood better than most.
>
> Quick idea: your customers wait 2-3 hours during a body repair. We'll send a free pie to anyone who's been there over an hour. You look like the shop that feeds people; we get new customers who remember your name.
>
> Cost to you: zero. Cost to us: the pies we'd give away anyway on slow Tuesdays.
>
> Worth 15 minutes this week?
>
> Joe

Why 9.5: voice matches Joe (specific — Pacini family, Tuesday slow days, "feeds people"); clear ask; ≤150 words; zero boilerplate; call to specific action.

### Exemplar 2 — GBP post

**Brief:** Sam asks for Saturday family-deal GBP post for Joe's Pizza of Revere.

**Draft (9.4/10):**
> Large cheese + 2L soda — $18, all Saturday. Pick up or DoorDash. Mention "Revere Advantage" in-store, garlic knot on us.

Why 9.4: specific price ($18), specific availability (all Saturday), specific pickup options, specific incentive ("Revere Advantage" for Chamber traffic), specific add-on (garlic knot). 25 words.

### Exemplar 3 — blog opener

**Brief:** Levar needs a blog post about first-time-buyer mistakes in Lynn.

**Draft (9.5/10):**
> Three houses on Breed Street sold this month for 4% under ask. Two of them had the same mistake. First-time buyers in Lynn keep missing it, and it's costing them $8-12K per closing.

Why 9.5: specific location (Breed Street), specific number (4% under ask), specific mistake teased, specific cost range. Reader is in 25 words in. Hook lands.

### Anti-example — blog opener

**Bad:** "In today's fast-paced real estate market, first-time buyers in the Lynn area often face challenges when navigating their first home purchase. Understanding the complexities of the market can help..."

Why bad: no specifics, agency boilerplate opener ("in today's fast-paced"), abstract ("often face challenges"), slow hook (reader gone by end of paragraph 1).

## Common failure modes

### "Generic brand voice" — when you forgot voice samples
- Check if `client_facts.voice_sample` exists; if not, flag Alex before drafting
- If you drafted without samples, revise against 3 samples before submitting

### "AI-assistant register leaked"
- Watch openings: "I'd be happy to" / "Certainly!" / "Let me"
- Watch closings: "Let me know if you have any questions" — replace with specific next step

### "Pricing drift"
- Every dollar figure cites v1.3 section — not "the Growth tier is around $800" but "$797 Growth tier (v1.3 §4.1)"

### "Fabricated testimonial"
- If the subscriber doesn't have a signed testimonial, DON'T write one that says "John D. — verified customer"
- Use aggregate language: "Members have reported" — only if members have actually reported

### "Trade-secret leak"
- Check for: Claude/GPT/Gemini/Grok/Perplexity/ElevenLabs/Ollama/beast/HostHatch/140-lane/n8n/Stagehand/Supabase
- Substitute per `06_trade_secrets.md` table

## Self-review before submission

Before sending to Lumina / subscriber / Titan-Content:

1. Does the first sentence carry specificity?
2. Does the reader know the next action by the end?
3. Did I read this aloud — does it sound like the subscriber?
4. Zero banned phrases / zero trade-secret leaks?
5. Length matched to surface?
6. Every number has a source?
7. Every client name / testimonial is real + approved?

7/7 → ship to next stage. <7 → revise.

## When you score yourself below 9.3

- Revise ONCE — address the specific dimension that's below
- If still below after revise: route to Alex for subscriber-context or route to Titan-Content for architectural rewrite
- Don't grind past 2 rounds — either the brief was thin, the voice samples were insufficient, or the angle is wrong. Debug the input, not the draft.
