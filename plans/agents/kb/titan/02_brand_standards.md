# Titan KB — 02 Brand Standards (authentic client branding, never invented)

## Rule zero

When we build for a client, we use **their actual brand**. Not a placeholder palette. Not an invented monogram. Not a "close enough" color from our imagination.

When Solon caught the Revere portal v3 demo with a made-up "RC" monogram and invented navy+gold palette on 2026-04-17, the issue wasn't that the demo looked bad — it's that the demo looked **invented**. Clients see that instantly and lose confidence.

## Required process for every new client-facing visual deliverable

1. **Scrape their actual site via Chrome MCP** before you touch a single CSS variable.
2. **Document at `/opt/amg-docs/clients/{client-slug}/brand-audit.md`** with:
   - Logo source URL + local copy + optimized-size copy
   - Exact hex codes extracted from their computed CSS (document which element you sampled)
   - Typography family + weights (hit Google Fonts / Adobe Fonts + load via CDN, don't eyeball a sans-serif)
   - Screenshots of 3+ surfaces (homepage, 2 inner pages, mobile view)
3. **Use their colors as PRIMARY.** Any AMG-layer accent (e.g., premium gold overlay) is explicitly rationalized in the brand audit as a complementary treatment, not a replacement.
4. **Lumina reviews** the visual before it ships. She scores ≥ 9.3 vs the design system AND vs the client's actual brand. Both must pass.
5. **Dual-validator** (Gemini Flash + Grok Fast) on the final bundle ≥ 9.3 each.

## Revere Chamber specifically (audited 2026-04-17)

- **Logo:** `https://static.wixstatic.com/media/5b253f_684e79dee1274048ae8a7b1491e99ee2~mv2.png` — teal C-shape, REVERE wordmark, CHAMBER OF COMMERCE below. Local copy: `deploy/revere-demo/brand-assets/revere-chamber-logo.png` (74KB optimized from 683KB source).
- **Primary navy:** `#0B2572` (from Log In link `rgb(11,37,114)`)
- **Royal blue accent:** `#116DFF` (from "Skip to Main Content" focus state `rgb(17,109,255)`)
- **Teal (logo-only):** ~`#2DB4CA` → `#4ED0DB` gradient
- **Font:** Montserrat 400/500/600/700 via Google Fonts
- **No gold in their native palette.** Demo uses gold `#d4a627` as deliberate AMG-overlay accent with Lumina-justified rationale (private member surface differentiates from public Chamber site).
- Full audit: `plans/deployments/REVERE_CHAMBER_BRAND_AUDIT.md`

## Logos — always optimize before ship

Raw logo downloads from Wix / Squarespace / WordPress are typically 500KB-2MB PNGs. These tank portal load times.

- Target: ≤100 KB per logo, ≤300px wide for header use
- Tool: `sips -Z 320 --setProperty formatOptions 82` on macOS
- Keep the original in `brand-assets/{slug}-original.png` as a source-of-truth archive
- Ship `brand-assets/{slug}.png` (or `.webp` once we land the WebP conversion pipeline)

## Color palettes — DO NOT invent without explicit Lumina sign-off

Not every client brand is beautiful. When a client's real brand is:
- **Tasteful:** use it verbatim. Our job is to frame their brand well, not upgrade it.
- **Dated / weak:** Lumina designs a complementary treatment that pairs *with* their real brand (e.g., their navy + our gold accent). Never replace their identity.
- **Genuinely unusable** (rare — think mid-2000s clip-art logo in neon): escalate to Solon. He may approve a full brand refresh as a separate engagement. Never silently "fix" the brand without approval.

## Typography — always load, never eyeball

- Google Fonts: `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" />`
- Apply via CSS var: `--brand-font: 'Montserrat', -apple-system, BlinkMacSystemFont, ...`
- Fallback stack must exist — Google Fonts can fail on slow networks and we don't want generic serif default
- For client-specific typography, check if Adobe Fonts / Monotype paid licenses apply — Solon approves budget before we use one

## Photography + imagery

- **Never use stock photography** for client-facing member references. If the demo references "Joe's Pizza of Revere" — use a real Revere business name Solon recognizes, or better: hand it to Solon for naming before ship.
- **Never generate AI imagery** for client brands (logos, hero photos, member-business photography) without Solon sign-off.
- **Screenshots from their real site** are the preferred placeholder when actual brand assets are missing.

## Agent card / persona differentiation

Avoid visual monotony: 7 identical squares with the same initials is a Lumina fail. Each agent card gets:
- Distinct letter (A/M/J/S/R/N/L) or agent-specific glyph
- Subtle color tint variation anchored on client navy — cool-to-warm gradient across the 7 personas
- Consistent icon size + shadow depth so the set reads as one family despite the variation

## Accessibility (AA minimum, always)

- Color contrast ≥ 4.5:1 for body text, ≥ 3:1 for large
- ARIA labels on navigation, status indicators, interactive elements
- `aria-live` on dynamic status
- `aria-hidden` on decorative-only elements (status dots, icon-backgrounds)
- Keyboard nav works: every interactive element tab-reachable
- Focus states visible, not suppressed via `outline: none` without a replacement
- Screen reader tested via VoiceOver + NVDA at minimum once per ship

## Anti-patterns (auto-Lumina-reject)

- Identical icons across differentiated entities (the 7-RC-squares failure mode)
- Placeholder colors where real client colors should be
- Trade-secret leaks in UI copy (see `01_trade_secrets.md`)
- Bootstrap-2018 aesthetic — flat solid colors, plain tables, no depth, no motion
- Apple HIG / Linear / Stripe / Vercel / Notion are the reference bar for premium
- Stock-photography member portraits
- "Lorem ipsum" anywhere — every visible string is real or purposeful
