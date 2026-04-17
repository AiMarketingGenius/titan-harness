# Lumina — KB 05 Reference Data

## Design system — AMG core tokens

These are the default AMG brand tokens. Overridden per-client via `tenant_config.theme` JSONB + `brand-audit.md` per client. Any deviation from a client's authentic brand palette requires explicit Lumina-proxy justification in the brand audit.

### Color
- **AMG primary navy:** `#0B2572` (matches Revere Chamber real brand)
- **AMG accent gold:** `#d4a627` (premium overlay, differentiator in member-facing surfaces)
- **Royal blue:** `#116DFF` (Revere CTAs)
- **Teal:** `#2DB4CA` (Revere logo accent)
- **Ink:** `#1c2433`
- **Muted:** `#6c7687`
- **Success:** `#1a7f4d`
- **Warn:** `#c17a00`
- **Danger:** `#a02020`
- **Ivory:** `#fbf9f3`
- **Paper:** `#ffffff`
- **Line:** `#e6e2d4`

### Typography scale
- **Default font family:** Montserrat (Google Fonts, weights 400/500/600/700) — matches Revere real brand
- **Fallback stack:** `'Montserrat', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`
- **Scale (majo-third, base 16px):**
  - h1: 32px / 40px line-height
  - h2: 26px / 34px
  - h3: 20px / 28px
  - body: 16px / 24px
  - small: 14px / 20px
  - micro: 12px / 16px

### Spacing scale
- Base: 4px
- Steps: 4, 8, 12, 16, 24, 32, 48, 64
- Card gutter: 18px default; 24px on widescreen
- Section spacing: 64px vertical
- Hero padding: 64px top / 32px sides (mobile 32/16)

### Shadow + depth
- Low: `0 2px 6px rgba(11,37,114,0.22)`
- Card: `0 4px 24px rgba(11,37,114,0.08)`
- Elevated: `0 12px 40px rgba(11,37,114,0.14)`

### Border radius
- Small: 6px
- Medium: 10px
- Card: 12px
- Large: 16px

### Easing + motion
- Default: `cubic-bezier(0.22, 1, 0.36, 1)` — smooth acceleration
- Fast (hover): 150ms
- Medium (view transitions): 300ms
- Slow (attention/storytelling): 600ms
- Prefers-reduced-motion: disable all non-essential motion, keep semantic state changes

### Breakpoints
- Mobile: 375px (tested), 414px (iPhone Pro Max)
- Tablet: 768px
- Small laptop: 1024px
- Desktop: 1440px
- Widescreen: 1920px
- Ultra-wide: 2560px

## Accessibility reference

### Contrast minimums (WCAG 2.1 AA)
- Body text: 4.5:1
- Large text (18pt+ or 14pt+ bold): 3.0:1
- Non-text UI (focus rings, borders, icons): 3.0:1

### ARIA patterns (common)
- `role="navigation"` + `aria-label` on nav elements
- `role="status"` + `aria-live="polite"` on dynamic status
- `aria-current="page"` on active nav item
- `aria-expanded` on collapsible panels
- `aria-hidden="true"` on decorative-only elements

### Keyboard
- All interactive elements tab-reachable
- Focus states visible (never `outline: none` without replacement)
- ESC closes modals
- Arrow keys for menu navigation where appropriate
- Tab order matches visual order

### Motion
- Honor `prefers-reduced-motion: reduce`
- Never auto-play video with sound
- Allow pausing any animation running >5s

## Reference library

Bookmarked exemplars for comparative critique:

- **Linear** — linear.app (spacing rhythm, dark mode craft, micro-interactions)
- **Stripe** — stripe.com (gradient depth, illustration balance, copy hierarchy)
- **Vercel** — vercel.com (grid + whitespace, geometric precision, motion)
- **Apple HIG** — developer.apple.com/design (typography scale, status animations, touch targets)
- **Notion** — notion.so (information density, hover-as-primary-UI)
- **Claude.ai** — claude.ai (chat UI hierarchy, streaming rhythm)
- **Rabbit R1 / Humane Pin / OpenAI voice mode** — orb visual language
- **37signals / Basecamp** — no-BS copy register for CTAs
- **Patagonia** — mission-driven specific imagery

## CRO benchmarks (local businesses, rough industry averages)

Never promise specific numbers — these are directional only:

- **Landing page conversion (local service):** 3-7%
- **Ecommerce cart abandonment:** 55-70%
- **Email nurture open rate:** 18-25% (CAN-SPAM compliant)
- **CTA click-through (above fold):** 4-8%
- **Mobile bounce rate (service sites):** 40-55%
- **Page load impact:** every 1s past 2s costs ~10% conversion

## Client-specific brand audits (indexed)

- **Revere Chamber:** `plans/deployments/REVERE_CHAMBER_BRAND_AUDIT.md`
- **Additional clients:** audit doc created per client at `/opt/amg-docs/clients/{slug}/brand-audit.md` on first visual engagement

## Anti-patterns (cataloged failures)

- **Bootstrap-2018 flat design** (see `03_quality_bar_examples.md` for full list)
- **Placeholder brand where real brand was scrape-able** (2026-04-17 Revere v3)
- **Identical icons across differentiated entities** (2026-04-17 "7 RC squares")
- **Stock photography in member references**
- **Auto-playing video with sound**
- **Motion that can't be paused**
- **Focus-state suppression without replacement**
