# Revere Chamber of Commerce — Brand Audit (2026-04-17)

**Source:** `https://reverechamberofcommerce.org/` (Wix site, platform detected: Wix Thunderbolt v1.17152)
**Scraped:** 2026-04-17 via Chrome MCP
**Purpose:** supersede placeholder navy+gold brand in demo portal with authentic Revere Chamber assets.

---

## 1. LOGO (authoritative)

- **Original:** `https://static.wixstatic.com/media/5b253f_684e79dee1274048ae8a7b1491e99ee2~mv2.png` — 1563×1563 PNG, ~683KB
- **Description:** "REVERE" wordmark set inside a teal-to-navy C-shape with two seagulls flying through the upper curve. "CHAMBER OF COMMERCE" in navy below the wordmark. Coastal-town imagery.
- **Local copy:** `deploy/revere-demo/brand-assets/revere-chamber-logo-original.png`
- **Replaces:** the placeholder "RC" monogram SVG I designed (`logo.svg`).

## 2. COLORS (extracted from live site)

| Role | Hex | Source element | Notes |
|---|---|---|---|
| Primary navy text | `#0B2572` | Log In link `rgb(11,37,114)` | Headlines, body ink |
| Royal blue (accent / CTAs) | `#116DFF` | "Skip to Main Content" focus color `rgb(17,109,255)` | Primary action color |
| Teal / cyan (logo-only) | sampled from logo gradient (approx `#2DB4CA` → `#4ED0DB`) | Logo C-shape | Reserved for logo + minimal accents |
| Background white | `#FFFFFF` | body | — |

**Important:** Revere's public-site palette is **blue + teal**. There is **no gold in their actual brand**. My prior demo used navy + gold as a placeholder.

**Lumina decision (proxy-graded — see §5):** keep a gold (`#d4a627`) accent in the MEMBER PORTAL surface as a deliberate premium treatment that differentiates the private member experience from the public Chamber homepage. Rationale: the member portal sits inside AMG's white-label platform, so a complementary warm accent signals "this is the premium private surface, not the public site." Revere's logo remains unchanged; their navy becomes the primary brand anchor; gold is the AMG-layer secondary. This matches Solon's stated approach: "Option B fallback — use Revere's brand as design inspiration, have Lumina design complementary treatment."

If Solon rejects the gold accent → swap to royal blue (`#116DFF`) as secondary and retire gold. One-line CSS var change.

## 3. TYPOGRAPHY

- **Primary font:** `Montserrat` (sans-serif, 400/500/600/700)
- **Fallback:** `sans-serif`
- **Observation:** clean, modern, Google-Fonts stock. Portal should match.

Previous demo used `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial` — fine but not on-brand. Swapping to `Montserrat` from Google Fonts.

## 4. LAYOUT + TONE OBSERVATIONS

- The live site uses a blue top banner + white content area.
- Primary nav is pill-style buttons (HOME, ABOUT, BECOME A MEMBER, EVENTS, MEET OUR BOARD, GET INVOLVED, Member Directory, Chamber Merchandise).
- Background imagery suggests Revere Beach / local streetscape.
- A chat widget is visible on the live site (bottom-right) via aminos.ai — they already have some automation.

## 5. LUMINA-PROXY REVIEW (pre-redesign baseline)

Running the demo portal CSS through a design-system review prompt gave:

- **Authenticity:** current demo uses placeholder "RC" monogram + invented gold palette. **Post-audit required change:** swap to real logo + real navy. Keep gold as an AMG-overlay accent with clear justification. Otherwise the demo looks invented.
- **Typography:** current demo uses system fonts. **Required change:** Montserrat via Google Fonts.
- **Hierarchy:** solid already (kicker → h2 → body → card-grid). No change.
- **Agent cards:** all 7 agents use identical "RC" square icon (monotonous). **Required change:** per-agent initial (A/M/J/S/R/N/L) + subtle color tint variation (7 shades spanning cool-to-warm across navy/teal/royal + gold highlight on active).
- **Micro-interactions:** hover states present but minimal. **Acceptable for Friday;** full Lumina redesign queued as CT-0417-F4C.

**Baseline Lumina-proxy score (pre-fix):** 7.0 — "authentic-branding fail disqualifies; fix logo + colors + agent cards before shipping."

**Target Lumina-proxy score (post-fix):** ≥ 9.3 — authentic Revere logo + accurate navy + Montserrat + agent card differentiation.

## 6. NEXT STEPS (this session)

1. Download real logo (done — `brand-assets/revere-chamber-logo-original.png`)
2. Swap `<img src="logo.svg">` → `<img src="brand-assets/revere-chamber-logo-original.png">` in index.html
3. Adjust CSS `--navy` from `#0a2d5e` → `#0B2572` (Revere's actual navy)
4. Add Google Fonts Montserrat import in style.css, update font-family stack
5. Differentiate 7 agent icons (initial per agent, subtle color variation)
6. Redeploy + Lumina-proxy grade + Gemini Flash + Grok Fast dual-validate (9.3 floor)
7. Queue CT-0417-F4C (full Lumina redesign per Solon's premium-polish directive) — this audit-driven patch is a baseline fix, not the final redesign

## 7. NEXT SPRINT (CT-0417-F4C)

Full Lumina redesign per Solon's "Bootstrap-2018 aesthetic" feedback:

- Visual hierarchy (sparklines + progress rings, not naked numbers)
- Color depth (gradients, shadows, layering)
- Typography premium pairing (Montserrat + complementary display font for headlines)
- Agent card personality (each card gets subtle persona glyph, not just letter)
- Micro-interactions on hover/tap
- Mobile polish down to 375px
- Desktop widescreen polish up to 2560px
- Lumina scores ≥ 9.3 BEFORE Gemini Flash + Grok Fast dual-validate
