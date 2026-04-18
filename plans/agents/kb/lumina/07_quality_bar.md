# Lumina — KB 07 Quality Bar

## What a 9.3+ Lumina approval looks like

All 5 dimensions at or above 9.0, overall ≥9.3, no critical_failures.

### Authenticity (9.3+)
- Real client logo (scraped + optimized, matches brand-audit doc)
- Real client color palette (extracted from live site, CSS vars match exactly)
- Real client typography (Google Fonts / Adobe Fonts loaded, fallback stack present)
- Real content references (actual business names, actual testimonials with signed approval, actual metrics with sources)
- Zero invented palette, zero placeholder monogram, zero stock-photo member references

### Hierarchy (9.3+)
- Eye-path follows intended conversion: hero → value-prop → social-proof → primary CTA
- H1 → H2 → H3 scale consistent, not compressed
- One primary CTA per view; secondary CTAs clearly subordinate
- Mobile + desktop both follow same hierarchy (not mobile-compressed or desktop-spread)
- F-pattern scan-tested for key pages

### Craft (9.3+)
- Typography: consistent scale, line-heights locked to baseline grid, letter-spacing optical
- Spacing: unified scale (4/8/12/16/24/32/48/64), no one-off pixel values
- Color: saturated with purpose, muted with purpose, contrast ratios verified
- Gradients: deliberate, not default
- Shadows: layered to suggest depth, not boxed around everything
- Micro-interactions: hover/focus/loading/success all present + smooth
- Animation timing: easing curves appropriate to content type

### Responsiveness (9.3+)
- 375px mobile: one-handed-reachable CTAs, tap targets 44pt+, no horizontal scroll, text readable at default zoom
- 768px tablet: layouts re-flow sensibly, not just stretched mobile
- 1024px small laptop: visual hierarchy maintained
- 1440-1920px desktop: content breathes, not tiny in middle of wide canvas
- 2560px+ widescreen: max-width set sensibly, white space deliberate
- ALL breakpoints tested (not just "it works on my 15-inch laptop")

### Accessibility (9.3+)
- Color contrast: 4.5:1 body, 3.0:1 large, 3.0:1 non-text
- ARIA: navigation labeled, status live regions, decorative-hidden, forms associated
- Keyboard: tab order matches visual order, focus states visible, ESC closes modals
- Screen reader tested: VoiceOver + NVDA at minimum (manual test once per ship)
- Reduced motion honored
- No auto-play sound
- Pause/stop available on any animation >5s

## Exemplars (what 9.5+ looks like)

### Exemplar 1 — Revere portal v4 (shipped 9.65)
- Authenticity 10.0: real Revere Chamber logo scraped, real navy #0B2572, real Montserrat
- Hierarchy 9.5: clear kicker → h2 → body → card-grid → banner flow
- Craft 9.5: per-agent icon differentiation, unified spacing scale, ARIA labels
- Responsiveness 9.5: tested 375px → 2560px
- Accessibility 9.5: aria-current, aria-live, aria-hidden decorative elements

### Exemplar 2 — runbook dual-graded 9.66
- Requirements fit 10.0: addresses all demo contingencies
- Clarity 9.5: 12-minute script, objection prep, technical pre-check
- Operability 9.7: Solon can run demo cold without thinking

## Anti-examples (auto-reject at review layer)

### Placeholder brand (2026-04-17 Revere v3)
- Invented "RC" monogram when real logo was scrape-able
- Invented navy+gold when real palette is navy+royal+teal
- **Auto-block. No revision round. Route back for brand-audit first.**

### Identical icons (2026-04-17 Revere v3)
- 7 agent cards with identical "RC" squares
- Differentiated entities MUST visually differentiate
- **Auto-block. Revise with per-entity variation.**

### Bootstrap-2018 aesthetic
- Flat solid colors, no depth
- Plain HTML tables
- No micro-interactions
- No hover states
- Sans-serif stack without loaded face
- **Auto-block. Design-level rethink required.**

### Stock photography in member references
- "Joe's Pizza of Revere" using stock pizza photo
- **Auto-block. Use real business Solon recognizes or flag TBD.**

### Trade-secret leaks
- "Powered by Atlas" acceptable ("Atlas" is AMG brand)
- "Live on beast + HostHatch" — ❌ internal codenames
- "Every agent runs on Claude" — ❌ underlying vendor
- **Auto-block. Route to trade-secret scan fix.**

## Scoring rubric (explicit)

### Per-dimension 0-10 scale

- **10.0** — Exemplary, sets the bar. Other artifacts should match this.
- **9.5** — Production-grade, minor polish opportunities noted.
- **9.3** — Floor for approval. Meets all requirements with nothing distracting.
- **9.0** — Almost there; specific fix needed.
- **8.5** — Below floor; revise required.
- **8.0** — Multiple fixes needed; possibly architectural.
- **7.0** — Architecture-level rethink recommended.
- **6.0** — Fundamental problem in approach.
- **<6.0** — Auto-block, route back for discovery before design.

### Dimension weights
- Authenticity: 25% (primary, 2026-04-17 lesson)
- Hierarchy: 20%
- Craft: 25%
- Responsiveness: 15%
- Accessibility: 15%

Weighted average ≥9.3 → approve. But ANY single dimension below 8.5 → revise regardless of average.

## Special-case floors

- **Board-pitch / investor-deck deliverables:** floor raised to 9.5 overall, no dimension below 9.0
- **First-of-vertical (first Chamber, first restaurant, first med-spa template):** floor 9.5, sets pattern for vertical
- **Crisis / hotfix / rollback:** floor stays 9.3 — no emergency exception; ship below floor only with Solon-explicit override + logged as post-mortem action

## Self-check before logging approval

1. Did I score all 5 dimensions?
2. Did I reference the library?
3. Did my critique have specific fixes (hex/pixel/selector)?
4. Did I catch authenticity first (before craft)?
5. Is the approval YAML complete with all subscores?
6. Is the sha256 of the artifact recorded?
7. **Did I measure typography against the reference site (AI Memory Guard for AMG surfaces) per `08_typography_reference.md`?** Specifically: eyebrow letter-spacing ≥15% of font-size? H2 weight ≥800 with optical tightening? Button weight ≥700?

7/7 → log approval. <7 → revise critique before finalizing.

## The 2026-04-17 Chamber-band typography miss (do not repeat)

Lumina scored the AMG Chamber CTA band's typography as "spec compliant" because the prompt spec (which Titan also wrote) used 12px eyebrow at 0.96px letter-spacing, 42px H2 at weight 700, 16px button at weight 600. All matched the prompt spec. None matched AI Memory Guard's typographic grammar. Solon's eyes caught the amateur feel; Lumina didn't. The permanent fix is in `08_typography_reference.md` — measure against the reference site, not the prompt spec.
