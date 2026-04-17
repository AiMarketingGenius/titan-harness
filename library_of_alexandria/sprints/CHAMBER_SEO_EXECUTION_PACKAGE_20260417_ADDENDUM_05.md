# CHAMBER SEO EXECUTION PACKAGE — ADDENDUM #5
**Date:** 2026-04-17 (END OF NIGHT — CRITICAL CORRECTION)
**Parent docs:** Synthesis + Execution Package + Addendum #1 + #2 + #3 + #4 + Titan Boot Prompt
**Scope:** Brand palette drift correction. EOM drifted "navy + gold" (which is Revere Chamber's palette) into all AMG site specs. AMG's actual palette = dark navy + blue/teal + bright green CTAs + white.

**SEVERITY:** 🔴 CRITICAL — supersedes every prior brand-palette reference across all 6 preceding docs. Fix required BEFORE any Lovable prompt executes on aimarketinggenius.io or any AMG-branded PDF renders.

---

## PART AH — THE DRIFT + THE TRUTH

### AH.1 — What went wrong

EOM repeatedly specified "navy + gold + white + Montserrat" as AMG's brand palette across:
- Execution Package Parts B, C, D
- Addendum #1 Part K (Case Studies page spec + 1-page PDF spec)
- Addendum #2 Part Q (3-persona CTA strip)
- Addendum #3 Part V (3 persona-specific PDFs)
- Addendum #4 Part AC (Case Studies summary 1-pager)
- Titan Boot Prompt "when uncertain on branding — navy + gold + white + Montserrat, always"

**Source of drift:** Chamber AI Advantage Encyclopedia v1.3 §1.4 calls out **"Revere example: Navy #0a2d5e + Gold #d4a627"** as the Revere-specific Chamber variant. EOM ingested that as AMG's general palette. Wrong.

### AH.2 — AMG's actual brand palette (from live site evidence)

From AMG_SITE_SCREENSHOTS_REFERENCE_20260329.pdf (project knowledge) + live site inspection:
- **Base:** dark navy background
- **Accent:** cyan / teal / bright blue (section callouts, sub-hero bands, some buttons)
- **Primary CTAs:** bright / vibrant green (NOT gold)
- **Text:** white primary + light gray secondary
- **Typography:** (Titan extracts from live site — may be DM Sans, Inter, or custom; the "Montserrat" specification I repeated was speculative)

**There is no gold anywhere in the current live AMG site.**

### AH.3 — Revere vs AMG — canonical mapping

| Surface | Palette | Source |
|---|---|---|
| aimarketinggenius.io (national AMG) | Dark navy + blue/teal + green CTAs + white | Live site |
| /chamber-ai-advantage (AMG national Chamber program page) | SAME AS AMG (dark navy + blue/teal + green) | This is an AMG site page; inherits AMG brand |
| /become-a-partner (AMG Chamber application) | SAME AS AMG | AMG site page |
| /case-studies + sub-pages | SAME AS AMG | AMG site pages |
| All 4 "How It Works" PDFs (sent via Alex lead capture) | SAME AS AMG | AMG-branded outbound collateral |
| Case Studies 1-pager PDF | SAME AS AMG | AMG-branded outbound collateral |
| Revere demo portal at portal.aimarketinggenius.io/revere-demo | Navy + gold (REVERE brand) | Revere-specific portal |
| Future Revere member-facing surfaces | Navy + gold (REVERE brand) | Revere-specific portal |
| Every OTHER Chamber's portal/member surfaces | That CHAMBER's colors | Per Encyclopedia §1.4 "uses Chamber's primary brand colors" |

**The Chamber AI Advantage Encyclopedia §1.4 states "Each Chamber gets a custom logo built by AMG as part of onboarding — uses Chamber's primary brand colors."** Revere's colors happen to be navy + gold. Other Chambers will have their own. The AMG national program page, PDFs, and national site never use any single Chamber's colors.

---

## PART AI — CORRECTION MECHANISM

### AI.1 — Authoritative source for AMG brand tokens

**Titan extracts brand tokens directly from the live aimarketinggenius.io site BEFORE writing any Lovable prompt or rendering any PDF.** Do NOT rely on my prior specification. Do NOT guess. Do NOT use navy + gold.

Extraction steps:

1. Stagehand-fetch or curl the live homepage CSS + computed styles on 2-3 representative pages (home, services, existing footer)
2. Extract:
   - Primary background hex (dark navy)
   - Primary accent hex (blue/teal)
   - CTA button fill hex (bright green)
   - CTA button text color
   - Heading color + body text color
   - Actual font-family + weights in use
   - Border-radius + spacing scale
3. Save to `/opt/amg-docs/brand/amg-brand-tokens-v1.md` with exact values
4. Pin this file as the single source of truth for all AMG-branded surfaces this weekend

### AI.2 — Global find-and-replace across all 6 prior docs

Mental swap during execution — when you read any of the prior docs, treat these strings as equivalent to "use AMG live-site brand tokens":

| Prior doc phrase | Actual instruction |
|---|---|
| "navy + gold" | "AMG live-site palette from amg-brand-tokens-v1.md" |
| "navy + gold + white + Montserrat" | "AMG live-site palette + AMG live-site typography" |
| "gold accent text" | "AMG live-site accent color (blue/teal or green per element role)" |
| "gold accent" / "gold CTA" | "AMG live-site CTA color (bright green)" |
| "navy background" | Accurate — dark navy IS the base. Keep as-is. |
| "white text" | Accurate — keep as-is. |
| Any hex value specified by EOM (#0a2540, #d4a627, etc.) | OVERRIDE with live-site-extracted hex |

### AI.3 — Color role mapping for new AMG surfaces

Use the extracted AMG tokens with these role assignments for new pages + PDFs:

| Element | AMG color role |
|---|---|
| Page background | Dark navy (live site base) |
| Hero background | Dark navy |
| Section headers (H1/H2) | White |
| Body text | White (primary) / light gray (secondary) |
| Accent eyebrow labels | Blue/teal accent |
| Primary CTAs | Bright green fill + dark text (matches live site button convention) |
| Secondary CTAs | Outlined blue/teal OR outlined green per live-site convention |
| Data callouts / stat tiles | Blue/teal accents on dark navy |
| Tables + dividers | Thin blue/teal rules |
| Card backgrounds (when used on dark sections) | Slightly lighter navy or charcoal |
| Card backgrounds (when used on alternating lighter sections) | Check live site — may be off-white or preserved dark-mode |

### AI.4 — Where navy + gold REMAINS correct

These surfaces keep navy + gold — do NOT change:
- Revere-specific proposal PDF (already generated)
- Revere hammer sheet PDF (already generated)
- Revere presentation PPTX (already generated)
- portal.aimarketinggenius.io/revere-demo (Revere portal — Revere-branded)
- Any Revere-branded documents sent to Don

Navy + gold is CORRECT for Revere. Incorrect for AMG national.

---

## PART AJ — UPDATED TITAN BOOT PROMPT OVERRIDE

Insert at the top of the Titan Boot Prompt execution order (BEFORE Step 1 Technical SEO):

```
STEP 0.5 — BRAND TOKEN EXTRACTION (MANDATORY FIRST ACTION)

Before any Lovable prompt or PDF render, extract AMG brand tokens from the live 
aimarketinggenius.io site. Save to /opt/amg-docs/brand/amg-brand-tokens-v1.md. 
This file is the single source of truth.

Mental override on all prior docs: wherever EOM wrote "navy + gold" for AMG 
surfaces, READ AS "AMG live-site palette from amg-brand-tokens-v1.md." EOM drifted 
the Revere Chamber palette (navy + gold) into AMG specs — Addendum #5 is the 
correction.

AMG actual palette from live-site evidence:
- Base: dark navy
- Accent: blue/teal  
- CTAs: bright green (NOT gold)
- Text: white primary + light gray secondary
- Typography: extract actual font-family from live site

Revere-specific navy + gold stays correct ONLY for Revere portal + Revere 
presentation materials already shipped. Every AMG national surface this weekend 
uses AMG live-site tokens.

If you find conflict between prior docs and this Addendum — Addendum #5 wins on 
brand/palette questions. All other doc content stands.
```

---

## PART AK — VERIFICATION GATE ADDITION

Add to all verification gates across prior addendums:

- [ ] **Brand tokens file exists** at `/opt/amg-docs/brand/amg-brand-tokens-v1.md` with real hex values from live site
- [ ] **Zero gold on AMG surfaces** — visual inspection of every new page + PDF confirms no gold fills, gold accents, or gold text
- [ ] **CTA buttons match live AMG green**, not Revere gold
- [ ] **New pages visually consistent with existing live site** — side-by-side screenshot comparison, no palette mismatch
- [ ] **PDFs match AMG brand** — preview renders show navy + blue/teal + green, not navy + gold
- [ ] **Revere-specific materials** (portal, already-shipped proposal/hammer/deck) still use navy + gold correctly

Dual-engine Grok + Perplexity reviews must include: "Does this page match the AMG live site's visual brand?" — if answer is no, score auto-drops below 9.3, fix required before ship.

---

## PART AL — EOM DRIFT BURN (standing rule update)

Per Solon standing rule "When corrected, burn it permanently":

**Burned: AMG national brand = dark navy + blue/teal + bright green CTAs + white. NOT navy + gold. Navy + gold is REVERE Chamber's palette only. Every new AMG surface pulls brand tokens from the live site, never from EOM guess-specification.**

Applies to: all future EOM outputs referencing AMG branding, color specs, or PDF design. Titan standing rules file should inherit this correction.

---

**End of Addendum #5. CRITICAL correction. Titan reads BEFORE Step 1 Technical SEO. Applies universally to all AMG surfaces in this sprint. Revere-specific materials unchanged.**

Weekend canon now: Synthesis + Execution Package + Addendum #1 + #2 + #3 + #4 + #5 + Titan Boot Prompt (7 reference docs + 1 kickoff prompt).
