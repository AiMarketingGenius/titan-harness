# CHAMBER SEO EXECUTION PACKAGE — ADDENDUM #2
**Date:** 2026-04-17 (late addition)
**Parent docs:** CHAMBER_SEO_EXECUTION_PACKAGE_20260417.md + ADDENDUM_01.md
**Scope:** Homepage 3-persona CTA strip — serves website buyers + AI expertise prospects + Chamber partners in one visual row

---

## STRATEGIC FRAMING

AMG site sells THREE things simultaneously:

1. **Websites** — local businesses + ecom brands needing new sites or redesigns (case studies prove quality)
2. **AI marketing expertise** — local businesses + agencies needing AI-driven marketing (services grid + voice orb + blogs)
3. **Chamber partnerships** — Chambers of Commerce wanting to offer AI marketing as a member benefit (dedicated pages)

A gorgeous site with zero audience-entry clarity sends qualified visitors to the wrong page. The 3-persona CTA strip fixes this — every visitor self-sorts in 5 seconds and lands on the page that closes them.

---

## PART Q — HOMEPAGE 3-PERSONA CTA STRIP

### Q.1 — Placement

Directly BELOW the current hero section, ABOVE the Chamber band added in Part B.

Order of appearance on homepage after this addendum:
1. Hero (existing — 1-sentence weave from Part B.3 is the only edit)
2. **3-Persona CTA Strip (NEW — this addendum)**
3. Chamber band (from Part B.2)
4. Existing services grid
5. Existing case studies row / Client Results (from Part K.6)
6. Existing trust/social-proof sections
7. Footer (with "For Chambers" column from Part B.4)

### Q.2 — Lovable prompt (atomic)

```
Add a new full-width section to the homepage, positioned IMMEDIATELY AFTER the hero section and IMMEDIATELY BEFORE the "For Chambers of Commerce + Trade Associations" navy band.

Section name: "Where are you on your journey?"

Design: light/white background for clean contrast against the navy hero above and the navy Chamber band below. 60-80px vertical padding. Centered layout, max-width 1200px.

H2 (centered, navy, bold):
"Start Where You Are"

Sub-headline (centered, medium gray, 1 line):
"Three paths to working with AMG — pick yours."

Below the sub-headline, a 3-column card row (mobile: stacked vertically with generous spacing).

═══ CARD 1 — LOCAL BUSINESS / ECOMMERCE ═══

Top icon: storefront or shopping-bag style icon, gold accent
Eyebrow (small, gold, uppercase): "FOR BUSINESS OWNERS"
H3 (bold, navy): "Grow Your Business with AI Marketing"
Body (1 short paragraph):
"Whether you run a local service company, a family entertainment center, a Shopify store, or a restaurant — AMG's AI marketing agents deliver real results. See the proof, then see the pricing."
Two inline links (stacked, small):
→ "See case studies" → /case-studies
→ "See pricing" → /#pricing (anchor to existing pricing section)
Primary CTA button (gold, full-width of card): "Get Started →" → /#pricing (or existing signup CTA)

═══ CARD 2 — NEED A WEBSITE ═══

Top icon: globe or browser-window icon, gold accent
Eyebrow (small, gold, uppercase): "FOR BUSINESSES NEEDING A NEW SITE"
H3 (bold, navy): "Launch a Site That Actually Converts"
Body (1 short paragraph):
"AMG builds high-conversion websites powered by AI — from Shopify stores to local-business sites to Chamber portals. Our sites are designed to rank, convert, and compound."
Two inline links (stacked, small):
→ "See sites we've built" → /case-studies
→ "How we build" → /#how-it-works (anchor to existing how-it-works section, or /services if dedicated)
Primary CTA button (gold, full-width of card): "Get a Free Website Audit →" → /audit (or /contact if audit page not yet built — Solon confirms)

═══ CARD 3 — CHAMBER OF COMMERCE ═══

Top icon: building-columns or institution icon, gold accent
Eyebrow (small, gold, uppercase): "FOR CHAMBERS + TRADE ASSOCIATIONS"
H3 (bold, navy): "Turn AI Marketing Into Non-Dues Revenue"
Body (1 short paragraph):
"Chambers of Commerce partner with AMG to offer AI marketing as a Founding-Partner-branded member benefit. Your Chamber earns lifetime margin on every member subscription. First Chamber in each region locks regional exclusivity."
Two inline links (stacked, small):
→ "See the program" → /chamber-ai-advantage
→ "Apply as Founding Partner" → /become-a-partner
Primary CTA button (gold, full-width of card): "Explore the Chamber Program →" → /chamber-ai-advantage

═══ END CARDS ═══

Card hover state: subtle lift (translateY(-4px)) + gold border highlight.
Card focus state: visible outline for keyboard nav.
All cards equal height. All primary CTAs aligned at bottom of card.

Mobile: cards stack vertically with 24px gap. Each card full-width, min 300px tall. Tap targets 48px+ on primary CTA.

TECHNICAL:
- Maintain overall brand navy + gold + white palette, Montserrat typography.
- Do NOT modify any other section. Additive only.
- Ensure schema markup on page is updated: add ItemList with 3 ListItem entries pointing to /case-studies, /audit (or /contact), /chamber-ai-advantage.
- Lighthouse accessibility audit should pass AA.
- WCAG: all text 4.5:1 contrast minimum.
```

### Q.3 — Two small dependencies for Titan to resolve

1. **`/audit` page route** — if a "free website audit" landing page doesn't already exist, Titan either creates a stub (short form: URL + email → triggers internal audit workflow) OR points the CTA to `/contact` as a fallback. Solon confirms which by Saturday AM. Default to stub if silent — simple page, atomic Lovable prompt, Titan drafts. Spec: hero + 1-paragraph value prop + form (URL + email + 1-line problem statement) + submit notifies growmybusiness@aimarketinggenius.io.

2. **Homepage existing anchors** — Titan verifies that `/#pricing` and `/#how-it-works` anchor IDs exist on current homepage. If missing, Titan adds them (surgical) so CTAs resolve correctly.

---

## PART R — UPDATED VERIFICATION GATE (extends Part O)

Add to the weekend ship checklist:

- [ ] **3-Persona CTA strip live** below hero, above Chamber band
- [ ] **All 3 card primary CTAs resolve** (no 404s — `/case-studies`, `/audit` or `/contact`, `/chamber-ai-advantage`)
- [ ] **Card hover + focus states** implemented + visible
- [ ] **Mobile stacking** tested on 375px viewport
- [ ] **Schema ItemList** added to homepage with 3 ListItem entries

---

## PART S — UPDATED TITAN DISPATCH LINE (slot into Part P of Addendum #1)

Insert into Part P Titan dispatch between steps 3 and 4:

```
3.5 [SATURDAY AM] Part Q homepage 3-Persona CTA Strip: one atomic Lovable prompt, 
    positioned between hero and Chamber band. Includes dependency check on /#pricing 
    and /#how-it-works anchors + /audit stub creation if needed.
```

---

**End of Addendum #2. Total documents for weekend sprint: Synthesis + Execution Package + Addendum #1 + Addendum #2.**
