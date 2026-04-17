# Titan KB — 03 Quality Bar (exemplars + anti-examples)

## Premium reference bar (what "good" looks like)

These are the aesthetic + interaction benchmarks every client-facing AMG visual deliverable competes against. If Lumina would look at our work next to one of these and see ours fall short, it's not ready.

### Aesthetic references
- **Linear** — linear.app — typography rhythm, tight spacing scale, micro-interactions, dark mode craft
- **Stripe** — stripe.com — gradient depth, photography + illustration balance, precise copy hierarchy
- **Vercel** — vercel.com — grid + whitespace, geometric precision, restrained color, motion
- **Apple HIG** — apple.com — typography scale, status animations, single-click flows
- **Notion** — notion.so — information density done elegantly, hover states as primary UI vocabulary
- **Claude.ai** — claude.ai — chat UI hierarchy, streaming text rhythm, quiet-confidence tone
- **Rabbit R1** — the orb + device UI language — use ONLY as aesthetic reference for voice orbs, never as copy source

### Voice/orb references (for Mobile Command + voice widgets)
- **Rabbit R1** orb — 3D depth, audio-reactive motion
- **Humane Pin** — voice interface visual language
- **OpenAI voice mode** — amplitude-reactive pulses, thinking swirl
- **Siri** — listening/thinking/speaking state transitions

### Copy + tone references
- **37signals / Basecamp** — no-bullshit direct voice, "nobody's hands are bigger than yours" energy
- **Patagonia** — mission-driven, plain-English technical
- **Mailchimp** (historical) — warmth + humor without cringe

## Anti-examples (immediate auto-reject)

### Aesthetic failures
- **Bootstrap 2018 dashboard** — flat beige + navy, plain HTML tables, no depth, no hover states, no micro-interactions
- **Generic SaaS marketing template** — stock photo of diverse team laughing at laptop, gradient hero with vague "transform your business" tagline
- **Wix defaults** — that specific drop-shadow-on-everything vibe
- **Material Design applied without customization** — screams "we didn't bother"
- **Monotonous icon grids** — 7 identical squares for 7 different entities (the 2026-04-17 Revere portal v3 failure mode)

### Copy + tone failures
- **"Unlock the power of AI"** / **"Revolutionize your business"** — any phrase that could be on every competitor's homepage
- **"As an AI, I'd be happy to help..."** — corporate-AI-assistant register
- **Banned phrases (see 01_trade_secrets.md):** all Claude/OpenAI/Gemini/Grok/Perplexity mentions in client-facing
- **Lorem ipsum** anywhere visible
- **Stock testimonial** ("John D., verified customer") without actual client approval

### UX failures
- **Password on client side in JS** and calling it "secure" — that's a gate, not security; document it as demo-only
- **Popups without dismiss affordance** — modal that traps the user
- **Navigation that hides behind hamburger on desktop** — only mobile
- **Link-looking-buttons / button-looking-links** — visual affordance must match behavior
- **No focus states** — keyboard users are users
- **Animations that can't be paused** — prefers-reduced-motion must be honored

## Scoring rubric for Lumina reviews

Lumina scores visual deliverables on 5 dimensions, 0-10 each. Floor: 9.3 average, no dimension below 8.5.

1. **Authenticity** — does it use the client's real brand? Or is it invented/placeholder? (2026-04-17 failure mode.)
2. **Hierarchy** — where does the eye land first? Does attention flow match the page's intended action?
3. **Craft** — typography pairing, spacing scale, color depth, micro-interaction polish
4. **Responsiveness** — mobile (375px) + tablet + desktop + widescreen (2560px+) all polished, not just desktop
5. **Accessibility** — WCAG AA minimum, ARIA, keyboard nav, contrast, reduced-motion, screen-reader sanity

A deliverable can score 10/10 on craft + hierarchy and still fail at 5/10 on authenticity (using placeholder brand when the real one was scrape-able). Authenticity is the 2026-04-17 lesson. Never below 8.5 here.

## Specific exemplar: Revere portal v4 (what we shipped post-fix)

What worked (why it got 9.65 dual-grade):
- Real Revere Chamber logo (scraped + optimized)
- Actual Revere navy `#0B2572` + Montserrat font (their typeface)
- Per-agent letter + gradient tint differentiation (no more 7 identical squares)
- Zero trade-secret leaks
- ARIA accessibility lift
- Responsive from 375px to 2560px
- Clear hierarchy: kicker → h2 → body → card-grid → amg-banner

What's still gated for v5 (CT-0417-F4C full Lumina redesign):
- Sparkline / progress-ring visualization instead of naked numbers
- Color depth (gradients, shadows, layering — not just flat beige+navy)
- Agent card personality glyphs (not just letters) — e.g., SEO = compass, Content = pen, Social = network
- Micro-interactions: hover tilts, smooth transitions between views
- Loading states during view switches

## Specific exemplar: Friday demo runbook (shipped 9.66 dual-grade)

What worked:
- Clear URLs + passwords + fallbacks
- 12-min script with minute-by-minute flow
- 6-row objection prep covering expected Board President questions
- Technical pre-call check with exact curl commands Solon can run
- Post-call action matrix tied to every likely outcome

What's the bar for ALL runbooks: Solon can execute the demo cold without thinking. If the runbook requires judgment calls in the moment, it's not done.
