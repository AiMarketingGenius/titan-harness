# Maya — KB 05 Reference Data

## Source of truth

- **Encyclopedia v1.3** for Chamber program + AMG pricing + contract terms
- **client_facts** (via `op_get_client_facts` RPC) for subscriber-specific voice samples, brand attributes, banned topics, hot buttons
- **MCP search_memory** for prior subscriber decisions + voice evolution
- **Alex's 05_reference_data.md** for Chamber / AMG / subscriber quick-ref
- **Lumina's 05_reference_data.md** for design-system tokens if copy must match visual

## Voice-sample discipline

For every subscriber, 3+ voice samples minimum before drafting. Sources:
- Their recent blog posts / newsletters (if they write)
- Their Instagram/LinkedIn captions
- Their transcribed speech (Loom videos, podcasts, sales calls)
- Direct emails they've sent to customers
- Their About page + homepage

Voice samples live at `client_facts` with `fact_category='voice_sample'`. If none exist, ask Alex to collect before drafting.

## Subscriber reference quick-ref (expands via live `client_facts` lookup)

### Levar (JDJ Investment Properties, Lynn MA)
- Real-estate operator voice: direct, confident, community-first
- Common themes: Lynn / Winthrop / Revere / North Shore MA local
- Banned topics: (query live `client_facts`)
- Current campaigns: query live

### Shop UNIS (Sungemmers product line)
- **Canonical spelling:** query `client_facts.fact_key='spelling_rule_sun_jammer'` — current source says "Sun Jammer (two words, Title Case)" per April 2026 audit. Any older "SUNGEMMERS" references are superseded. **Always pull live before drafting.**
- Product: consumer product line
- Voice: playful, product-first, photo-supporting

### Revere Chamber of Commerce
- Institutional voice (Chamber admin / Board-facing)
- Member-facing voice (shifts warmer + local)
- Brand palette: navy #0B2572 + royal blue #116DFF + teal #2DB4CA (NOT gold — gold is AMG overlay)
- Font: Montserrat

### Paradise Park Novi / Revel & Roll West
- Client-specific voice pulled via `client_facts` live

## Content benchmarks (industry-directional, never promise specific numbers)

- **Email open rates (B2C consumer-service):** 22-28% on opt-in lists
- **Email click-through:** 2-4%
- **Blog engagement (local business readers):** 60-90s time on page at 1500 words
- **Social engagement rate (IG):** 1-3% for local business under 10K followers; 4-7% possible with strong community
- **LinkedIn article engagement:** 0.5-2% typical; 3-5% strong
- **Cold outbound reply rate (ICP-matched):** 3-8% is industry average; above 10% means either great copy or great targeting
- **GBP post engagement:** highly variable; consistency matters more than any single post

Use these for directional guidance; never commit specific numbers to subscribers.

## Copy-framework library

### Hero formula (landing page)
- **Headline:** outcome-driven, 6-10 words, specifics if possible
- **Subhead:** mechanism, 10-20 words
- **Proof:** trust signal (testimonial, logos, stat — real only)
- **CTA:** single, specific action-verb

### Email nurture arc (5-email sequence)
1. **Welcome + expectation-setting** (who you are, what to expect, one small value)
2. **Problem-naming** (articulate the problem better than the reader can)
3. **Solution-framing** (introduce the approach, not yet the product)
4. **Proof + case study** (real client win if approved; otherwise directional)
5. **Offer + next step** (specific, time-boxed, easy yes/no)

### Blog post structure
1. **Hook** (story/stat/question, <50 words)
2. **Thesis** (what this post will tell you)
3. **3-5 sections** with H2, each one specific takeaway
4. **Summary + next action**
5. **Meta description** (155 chars, keyword, hook)

### Social platform quick-ref
- **IG caption:** 80-150 char first line (the hook — what's shown in feed before "more"), full caption can run 500-1000 chars, hashtags in first comment or end
- **LinkedIn post:** 500-1200 chars optimal; first 2 lines are the hook; single CTA at end
- **X (Twitter):** thread > single tweet; each tweet ≤ 280 chars; hook in tweet 1
- **GBP post:** 1500 char max; local-keyword in first sentence; CTA button text specific
- **TikTok caption:** 80-150 char; native discoverability > hashtag-stuffing

## Banned phrases catalog (expanding)

### Agency boilerplate
- leveraging, unlocking, empowering, transforming, revolutionizing
- seamless, turnkey, robust, synergistic, scalable-as-adjective
- world-class, industry-leading, cutting-edge, best-in-class
- next-generation, paradigm-shift, game-changing, disrupt-as-verb
- "today's fast-paced world" / "in an era of" / "now more than ever"

### AI-assistant register
- "I'd be happy to help..."
- "Certainly!" / "Absolutely!" / "Great question!"
- "Let me explain..." / "Here's a breakdown..."
- "I understand you're looking for..."
- "As an AI..." / "as a language model..."

### Trade-secret (full list in 06)
- Claude, Anthropic, ChatGPT, GPT-*, OpenAI, Gemini, Grok, Perplexity
- ElevenLabs, Ollama, nomic-embed-text, Kokoro
- beast, HostHatch, 140-lane, n8n, Stagehand, Supabase
- Specific VPS IPs

## Exemplar library (reference specific posts when calibrating voice)

- **Basecamp "It Doesn't Have to Be Crazy at Work"** — operator-direct, no-BS register
- **Patagonia "Don't Buy This Jacket" ad** — mission-driven specificity
- **Stripe's Docs** — technical-precise, warmth without saccharine
- **Historical Mailchimp voice** — warmth without cringe (mid-2010s era)
- **Notion's release notes** — content-craft applied to dry subject matter

Bookmark + study when calibrating new subscriber voice.
