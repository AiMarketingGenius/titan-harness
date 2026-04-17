# AMG Brand Tokens v1 — Source of Truth

**Status:** LOCKED 2026-04-17 per CT-0417-24 Addendum #5 correction.
**Source:** extracted via Chrome MCP computed styles from live aimarketinggenius.io (2026-04-17T21:45Z).
**Authority:** supersedes every "navy + gold" reference in CT-0417-24 EOM docs for AMG surfaces. Navy + gold stays correct ONLY on Revere-specific materials (already shipped).
**Mirror:** this file is the SSOT; VPS counterpart at `/opt/amg-docs/brand/amg-brand-tokens-v1.md` (push when VPS access needed).

---

## 1. Canonical hex palette

```css
/* Core surfaces */
--amg-bg-primary:    #131825;  /* midnight navy base (body, primary sections) */
--amg-bg-section:    #0F172A;  /* slate-950 alternate section darker */
--amg-bg-section-2:  #0F1729;  /* secondary alt */
--amg-bg-card:       #1A2033;  /* slightly lifted card bg on dark sections */

/* Text */
--amg-text-primary:   #FFFFFF;  /* white — headings, primary copy on dark */
--amg-text-secondary: #C5CDD8;  /* soft gray — body copy */
--amg-text-muted:     #8796A8;  /* muted for meta */
--amg-border:         #465467;  /* divider / subtle rule */

/* Accents */
--amg-accent-cyan:     #00A6FF;  /* primary blue — nav active, links, chips */
--amg-accent-cyan-deep:#0080FF;  /* gradient end for blue CTAs */
--amg-accent-blue-alt: #2563EB;  /* alt tile/button blue */

/* CTAs */
--amg-cta-primary:     #10B77F;  /* BRIGHT GREEN — hero primary CTA (START FREE TRIAL) */
--amg-cta-primary-hover:#0EA572; /* hover darken */
--amg-cta-inverse:     #FFFFFF;  /* white btn on dark hero (with blue text) */
--amg-cta-ghost-bg:    rgba(255,255,255,0.1);  /* secondary/ghost overlay */
--amg-cta-blue-fill:   linear-gradient(to right, #00A6FF, #0080FF);
--amg-chip-bg:         rgba(0,166,255,0.10);  /* nav/badge backgrounds */

/* Utility */
--amg-radius:    10px;  /* buttons default */
--amg-radius-lg: 12px;  /* cards */
--amg-shadow:    0 8px 24px rgba(0,0,0,0.35);
```

## 2. Typography

```css
--amg-font:         "DM Sans", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
--amg-font-heading: "DM Sans", sans-serif;  /* same family, bolder weights */
```

- NOT Montserrat. EOM's "Montserrat" across every CT-0417-24 doc is wrong.
- H1: ~72px desktop / 40px mobile, weight 700
- H2: ~42px desktop / 28px mobile, weight 700
- H3: ~24px desktop / 20px mobile, weight 600
- Body: 16px, weight 400, line-height 1.6
- CTA button: 16-18px, weight 600, uppercase or title-case (varies by surface)

## 3. Color role assignments for new AMG surfaces

| Element | Token |
|---|---|
| Page background | `--amg-bg-primary` (#131825) |
| Hero background | `--amg-bg-primary` or `--amg-bg-section` |
| Alternating section | `--amg-bg-section` (#0F172A) |
| H1 / H2 headings | `--amg-text-primary` (white) |
| Sub-headlines, body | `--amg-text-secondary` (#C5CDD8) |
| Meta / helper | `--amg-text-muted` (#8796A8) |
| Eyebrow labels | `--amg-accent-cyan` (#00A6FF) |
| Primary CTA | `--amg-cta-primary` (#10B77F, green) |
| Secondary CTA | outlined white OR `--amg-cta-ghost-bg` overlay |
| Trust chips / badges | `--amg-chip-bg` background + cyan text |
| Stat callouts | `--amg-accent-cyan` or `--amg-accent-blue-alt` |
| Dividers | `--amg-border` (#465467) thin 1px |
| Card on dark | `--amg-bg-card` (#1A2033) with subtle border |

## 4. Existing routes on aimarketinggenius.io (discovered this turn)

- `/` (home — hero, services, agents, blog, pricing teasers, how it works)
- `/agents`
- `/pricing`
- `/cro-audit-services` ← this is the audit page (NOT `/audit`)
- `/for-fecs`
- `/vs-competitors`
- `/privacy-policy`
- `/terms-of-service`
- `/refund-policy`
- `/blog`

**Chamber-related routes that do NOT yet exist (all to create in this sprint):**
- `/chamber-ai-advantage`
- `/become-a-partner`
- `/case-studies` + 5 sub-pages
- `/tools/chamber-revenue-calculator` (Week 2 per synthesis)
- `/resources/chamber-ai-policy-template` (blog 4 lead magnet)
- 5 blog URLs per Execution Package Part E

## 5. Banned on AMG surfaces (Addendum #5)

- Gold fills / gold accents / gold text anywhere (reserved for Revere only)
- "Montserrat" font (use DM Sans)
- Navy #0a2d5e + Gold #d4a627 (Revere's — NOT AMG's)

## 6. Existing widget mismatch — flag

- `deploy/amg-chatbot-widget/widget.js` currently hardcodes #0B2572 navy + #d4a627 gold + Montserrat + #fbf9f3 cream message bg. These are Revere palette. Widget must be rebranded to AMG tokens above before flipping live on aimarketinggenius.io.

## 7. Verification rule

Every new AMG surface (Lovable page / PDF / email template / widget styling) MUST reference this file. Any CTA button that renders gold fill or Montserrat font fails verification automatically. Dual-engine Grok + Perplexity checks include the question "does this page match AMG live-site visual brand tokens v1?"

## 8. Changelog

- **2026-04-17** — initial extraction via Chrome MCP. Addendum #5 correction mechanism resolved.
