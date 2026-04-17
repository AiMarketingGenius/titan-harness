# CT-0417-24 — Atomic Lovable Prompts (Paste-Ready)

**Date:** 2026-04-17
**Target:** aimarketinggenius.io (Lovable project `aimarketinggenius.lovable.app`)
**Order:** paste prompts in the order below, ONE AT A TIME. Wait for Lovable to ship each, run Lumina proxy ≥9.3 review between each, then paste the next.
**All corrections from `CT-0417-24_CORRECTIONS_LOG.md` are APPLIED in the prompts below.** No prompt writes 35%, Montserrat, gold, "Free Website Audit", `amg-lead-docs/` new bucket, or any invented claim.
**Brand tokens from:** `library_of_alexandria/brand/amg-brand-tokens-v1.md` (live-site extracted 2026-04-17T21:45Z).

---

## HOW TO USE THIS FILE

1. Open Lovable, open the AMG project (aimarketinggenius.lovable.app).
2. Copy the first prompt block (between the `===` delimiters), paste into Lovable.
3. Wait for Lovable to generate.
4. Review visually — does it match the spec, match live-site brand tokens?
5. Run Lumina proxy review (via `bin/review_gate.py --bundle <bundle> --step-id LOV-<N>` — Computer reviewer).
6. If ≥9.3 → ship. If <9.3 → fix per reviewer notes, re-paste adjusted prompt.
7. After all pages are live, run dual-engine Grok + Perplexity ≥9.3 gate before final pitch.

**NEVER batch these.** Each prompt is additive and assumes its predecessor shipped cleanly.

---

## PROMPT 0 — TECHNICAL SEO FOUNDATION (ships first, before any page)

If Lovable exposes direct file access to the deploy root, paste these as file creations. Otherwise, this is a direct-commit task that Solon or Titan runs against whatever asset system the Lovable project uses for static SEO files.

### 0.1 — `robots.txt` at site root

```
User-agent: Googlebot
Allow: /

User-agent: Bingbot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Claude-Web
Allow: /

User-agent: GPTBot
Allow: /

User-agent: Google-Extended
Allow: /

Sitemap: https://aimarketinggenius.io/sitemap.xml
```

### 0.2 — `sitemap.xml` at site root (starter — expand as pages ship)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://aimarketinggenius.io/</loc><lastmod>2026-04-17</lastmod><priority>1.0</priority></url>
  <url><loc>https://aimarketinggenius.io/agents</loc><priority>0.8</priority></url>
  <url><loc>https://aimarketinggenius.io/pricing</loc><priority>0.8</priority></url>
  <url><loc>https://aimarketinggenius.io/cro-audit-services</loc><priority>0.7</priority></url>
  <url><loc>https://aimarketinggenius.io/for-fecs</loc><priority>0.6</priority></url>
  <url><loc>https://aimarketinggenius.io/vs-competitors</loc><priority>0.6</priority></url>
  <url><loc>https://aimarketinggenius.io/chamber-ai-advantage</loc><lastmod>2026-04-17</lastmod><priority>0.9</priority></url>
  <url><loc>https://aimarketinggenius.io/become-a-partner</loc><lastmod>2026-04-17</lastmod><priority>0.9</priority></url>
  <url><loc>https://aimarketinggenius.io/case-studies</loc><lastmod>2026-04-17</lastmod><priority>0.8</priority></url>
  <url><loc>https://aimarketinggenius.io/case-studies/shop-unis</loc><priority>0.7</priority></url>
  <url><loc>https://aimarketinggenius.io/case-studies/paradise-park-novi</loc><priority>0.7</priority></url>
  <url><loc>https://aimarketinggenius.io/case-studies/mike-silverman-water-damage</loc><priority>0.7</priority></url>
  <url><loc>https://aimarketinggenius.io/case-studies/revel-roll-west</loc><priority>0.7</priority></url>
  <url><loc>https://aimarketinggenius.io/case-studies/clawcade</loc><priority>0.7</priority></url>
  <url><loc>https://aimarketinggenius.io/blog</loc><priority>0.6</priority></url>
</urlset>
```

### 0.3 — `llms.txt` at site root (future-proofing; low priority per synthesis §4)

```
# AI Marketing Genius (AMG)
# https://aimarketinggenius.io

## Core resources
- [Chamber AI Advantage program](https://aimarketinggenius.io/chamber-ai-advantage)
- [Become a Founding Partner](https://aimarketinggenius.io/become-a-partner)
- [Case studies](https://aimarketinggenius.io/case-studies)
- [Services pricing](https://aimarketinggenius.io/pricing)
- [CRO audit](https://aimarketinggenius.io/cro-audit-services)

## About
AMG runs the first AI marketing channel partner program for Chambers of Commerce and Trade Associations. Chambers earn lifetime rev-share on member AI marketing subscriptions; members receive enterprise-grade AI marketing at Chamber-member pricing.

## Crawling preferences
AI assistants may cite content from this site with attribution. Please include the specific page URL when quoting substantive content.
```

---

## PROMPT 1 — HOMEPAGE: CHAMBER BAND (Execution Package Part B.2, corrected)

```
Add a new full-width section to the homepage positioned IMMEDIATELY AFTER the current hero section and IMMEDIATELY BEFORE the existing services grid.

Section background: dark navy #131825 (matches site base) with a subtle inner gradient from #131825 to #0F172A.
Vertical padding: 80-100px desktop, 56-72px mobile. Centered max-width 1200px.

EYEBROW (small, uppercase, tracked, color #00A6FF):
"FOR CHAMBERS OF COMMERCE + TRADE ASSOCIATIONS"

H2 (white, weight 700, ~42px desktop / 28px mobile, DM Sans):
"The First AI Channel Partner Program Built for Chambers"

Sub-headline (#C5CDD8 light gray, ~18px desktop, line-height 1.55, max-width 720px centered):
"Generate non-dues revenue, reduce Board workload, and deliver a member benefit your members actually want — through a white-labeled AI marketing program your Chamber fully controls."

TWO CTAs side by side (mobile: stacked with 16px gap):
- Button 1 (primary, bright green #10B77F fill, white text, 10px border-radius, 16px-18px font-weight 600, padding 16px 32px):
  text: "See the Chamber AI Advantage Program →"
  link: /chamber-ai-advantage

- Button 2 (outlined, 1px border rgba(255,255,255,0.4), white text, same size/radius/padding):
  text: "Apply as a Founding Partner →"
  link: /become-a-partner

BELOW buttons, thin single-line trust row (small #C5CDD8 text, 14px, centered, 24px top margin):
"Founding Partner economics · Lifetime rev-share on member subscriptions · White-labeled delivery"

Responsive: stack CTAs vertically on mobile. Tap targets minimum 48px. WCAG AA text contrast.

Font family: DM Sans throughout.

Do NOT modify any other section. Additive only. Do NOT introduce gold, gold accents, or Montserrat anywhere.
```

---

## PROMPT 2 — HOMEPAGE: HERO SENTENCE WEAVE (Execution Package Part B.3)

```
In the existing hero section of the homepage, locate the sub-headline or supporting paragraph beneath the main H1 ("Your AI Marketing Employee — Working 24/7").

Append ONE sentence to the end of that supporting paragraph. Exact wording:

"Local businesses grow with us directly. Chambers of Commerce partner with us to deliver AI marketing as a Chamber member benefit."

Do NOT change the H1, the existing CTAs, or any other element. This is a one-sentence additive edit only.
```

---

## PROMPT 3 — HOMEPAGE: FOOTER "FOR CHAMBERS" COLUMN (Execution Package Part B.4)

```
In the existing site footer, add a new column titled "For Chambers" (or append to the nearest appropriate existing column if the grid is full).

Under "For Chambers" add these 3 links in order:
1. "Chamber AI Advantage Program" → /chamber-ai-advantage
2. "Become a Founding Partner" → /become-a-partner
3. "Case Studies" → /case-studies

Match existing footer styling (same font weight, same color, same hover states). Maintain existing footer mobile collapse behavior. Do NOT modify other columns.
```

---

## PROMPT 4 — HOMEPAGE: 3-PERSONA CTA STRIP (Addendum #2 Part Q, corrected)

```
Add a new full-width section to the homepage positioned IMMEDIATELY AFTER the hero section and IMMEDIATELY BEFORE the Chamber band added in Prompt 1 (section titled "The First AI Channel Partner Program Built for Chambers").

Section name for internal reference: "Where are you on your journey?"

Design: slightly lighter background #1A2033 for clean visual contrast against the darker hero above and the dark navy Chamber band below. Vertical padding 72-96px. Centered max-width 1200px.

H2 (centered, white, DM Sans, weight 700, ~36px desktop / 26px mobile):
"Start Where You Are"

Sub-headline (centered, #C5CDD8, DM Sans, 18px, one line):
"Three paths to working with AMG — pick yours."

Below the sub-headline, a 3-column card row (mobile: stacked vertically with 24px gap).

Each card:
- Background: #131825 with 1px border rgba(0,166,255,0.2)
- Padding 28px
- 12px border-radius
- Hover state: subtle translateY(-4px) + border color #00A6FF
- Focus state: visible 3px outline #00A6FF for keyboard nav
- Equal heights, primary CTAs aligned at bottom of card

═══ CARD 1 — LOCAL BUSINESS / ECOMMERCE ═══

Top icon: storefront or shopping-bag line icon, color #00A6FF, 32px
Eyebrow (small uppercase tracked, #00A6FF, 12px): "FOR BUSINESS OWNERS"
H3 (white, DM Sans, weight 600, 22px): "Grow Your Business with AI Marketing"
Body paragraph (#C5CDD8, 15px, line-height 1.55):
"Local service business, family entertainment center, Shopify store, or restaurant — AMG's AI marketing agents deliver real results across verticals. See the proof, then see the pricing."
Two inline small links (stacked, #00A6FF, 13px, underlined on hover):
→ "See case studies" → /case-studies
→ "See pricing" → /pricing
Primary CTA button (full-width of card, bright green #10B77F fill, white text, 10px radius, padding 12px 16px, weight 600):
"Get Started →" → /pricing

═══ CARD 2 — NEED A WEBSITE ═══

Top icon: globe or browser-window icon, #00A6FF, 32px
Eyebrow: "FOR BUSINESSES NEEDING A NEW SITE"
H3 (white): "Launch a Site That Actually Converts"
Body:
"AMG builds high-conversion websites powered by AI — Shopify stores, local-business sites, Chamber portals. We design to rank, convert, and compound."
Two inline small links:
→ "See sites we've built" → /case-studies
→ "How we build" → /#how-it-works
Primary CTA (full-width green fill):
"Get Your Website Score →" → /cro-audit-services

═══ CARD 3 — CHAMBER OF COMMERCE ═══

Top icon: building-columns or institution icon, #00A6FF, 32px
Eyebrow: "FOR CHAMBERS + TRADE ASSOCIATIONS"
H3 (white): "Turn AI Marketing Into Non-Dues Revenue"
Body:
"Chambers of Commerce partner with AMG to offer AI marketing as a Founding-Partner-branded member benefit. Your Chamber earns lifetime rev-share on every member subscription. First Chamber in each region locks regional exclusivity."
Two inline small links:
→ "See the program" → /chamber-ai-advantage
→ "Apply as Founding Partner" → /become-a-partner
Primary CTA (full-width green fill):
"Explore the Chamber Program →" → /chamber-ai-advantage

═══ END CARDS ═══

Mobile: stack cards vertically with 24px gap, each card full-width, min height 280px. Tap targets 48px+ on primary CTAs.

TECHNICAL:
- Add schema markup ItemList with 3 ListItem entries pointing to /case-studies, /cro-audit-services, /chamber-ai-advantage
- Lighthouse accessibility AA minimum
- WCAG: all text 4.5:1 contrast against card background

Do NOT modify any other section. Additive only. Font: DM Sans. No gold or Montserrat anywhere.
```

---

## PROMPT 5 — HOMEPAGE: CLIENT RESULTS ROW (Addendum #1 Part K.6, corrected)

```
In the homepage, between the existing services grid and the footer (or within the existing trust/social-proof area if that section already exists), add a new compact section.

Background: alternate section color #0F172A.
Vertical padding: 48-64px.

H2 (centered, white, DM Sans, weight 700, 28px desktop / 22px mobile):
"Real Results. Real Clients."

Sub-head (centered, #C5CDD8, 16px, max-width 640px):
"AMG delivers for Shopify ecommerce brands, family entertainment centers, home services companies, and retail — all on the same AI platform."

5 small logo/vertical tiles in a row (mobile: horizontal scroll with snap + subtle scrollbar). Each tile: 72-96px tall, centered logo or vertical-name text at 14-16px, subtle background #131825, 10px radius, 1px border rgba(255,255,255,0.08):
1. "SHOP UNIS · Shopify Ecom"
2. "PARADISE PARK NOVI · FEC"
3. "MIKE SILVERMAN · Water Damage"
4. "REVEL & ROLL WEST · Bowling"
5. "CLAWCADE · Amusement"

Below tiles, centered outlined CTA (20-24px top margin, 1px rgba(255,255,255,0.4) border, white text, 10px radius, padding 12px 24px, weight 600):
"See full case studies →" → /case-studies

Keep section tight — maximum 220px tall on desktop.

Font: DM Sans. No gold or Montserrat anywhere.
```

---

## PROMPT 6 — /chamber-ai-advantage PAGE (Execution Package Part C + Hammer Weave Part J, corrected)

```
Create a new page at route /chamber-ai-advantage.

Page title tag: "Chamber AI Advantage | AI Channel Partner Program for Chambers of Commerce"
Meta description: "The first AI marketing channel partner program built for Chambers of Commerce. Generate non-dues revenue, deliver a differentiated member benefit, and reduce Board workload. Founding Partner applications open."

Use existing site shell (header + footer). Global palette: dark navy #131825 base, #0F172A alternate, white + #C5CDD8 text, #00A6FF cyan-blue accents, #10B77F bright green primary CTAs. Font: DM Sans. 10-12px border radius on buttons + cards. No gold. No Montserrat.

PAGE STRUCTURE:

═══════════════════════════════════════
SECTION 1 — HERO (full-width, #131825 background)
═══════════════════════════════════════

EYEBROW (#00A6FF): "FOR CHAMBERS OF COMMERCE + TRADE ASSOCIATIONS"

H1 (white, DM Sans, weight 700, ~56-72px desktop / 36-44px mobile):
"How Chambers of Commerce Increase Revenue with AI-Powered Channel Partnerships"

Sub-headline (#C5CDD8, 18-20px, max-width 780px):
"The first AI marketing program designed for Chambers — generate non-dues revenue, deliver a member benefit competitors can't match, and reduce Board workload without adding staff."

Two CTAs:
- Primary (green #10B77F fill): "Apply as a Founding Partner →" → /become-a-partner
- Secondary (outlined white): "See real client results →" → /case-studies

═══════════════════════════════════════
SECTION 2 — AEO PASSAGE (#0F172A background, max-width 780px centered)
═══════════════════════════════════════

No H2. Callout block with thin left border 3px solid #00A6FF, padding 28px.

[TITAN NOTE: prose below is structural placeholder — SEO|Social|Content project replaces with finished AMG-voice copy before ship. Keep structure + AEO Q&A first-150-words pattern + internal links.]

PARAGRAPH 1 (white, 20px, weight 500):
"The fastest way for a chamber of commerce to grow revenue in 2026 is a white-labeled AI marketing program that generates non-dues revenue while reducing staff load. Chambers that adopt AI channel partnerships earn lifetime rev-share on every member subscription, cover their own operating costs, and deliver measurable member value — without the Chamber building, staffing, or maintaining the technology."

PARAGRAPH 2 (#C5CDD8, 16px):
"AMG's Chamber AI Advantage is the first national program to package this as a true channel partnership: the Chamber controls the relationship, AMG delivers the service, and both earn when members succeed."

═══════════════════════════════════════
SECTION 3 — "The Non-Dues Revenue Problem" (#131825 background)
═══════════════════════════════════════

H2 (white): "The Non-Dues Revenue Problem Every Chamber Faces"

3-column grid (mobile: stacked). Each column card-styled with 1px rgba(0,166,255,0.2) border, #0F172A bg, 12px radius, 28px padding:

COLUMN 1:
Icon (line style, #00A6FF, 32px): trending-down
Stat headline (white, 18px weight 600): "Declining dues income"
Body (#C5CDD8, 14px): "Membership numbers compress while operating costs rise. Dues alone no longer fund Chamber operations at the level members expect."

COLUMN 2:
Icon: users
Stat: "Commoditized member benefits"
Body: "Discount cards, networking events, and referral lists are now table-stakes. Members ask: what's different about THIS Chamber?"

COLUMN 3:
Icon: clock
Stat: "Volunteer Board burnout"
Body: "Marketing, events, outbound, reputation — workload grows while Board bandwidth stays flat."

Closing paragraph below grid (centered, white, 18px, max-width 680px):
"Chambers that solve all three simultaneously win the next decade."

═══════════════════════════════════════
SECTION 4 — "Why AI is the New Affinity Standard" (#0F172A background)
═══════════════════════════════════════

H2: "Why AI Marketing is the New Chamber Affinity Standard"

Intro paragraph (#C5CDD8, max-width 780px):
"Affinity programs work when the Chamber delivers real economic value members can't get elsewhere. In 2026 the answer is a proprietary AI marketing platform members couldn't afford individually — bundled as a Chamber member benefit."

4 feature tiles (2×2 grid desktop, stacked mobile). Each tile: #131825 bg, 12px radius, 24px padding, 1px subtle border.

TILE 1 — "Member economics":
"Members get enterprise-grade AI marketing at a Chamber-member discount off public retail. Typical member saves meaningfully vs. hiring a conventional agency."

TILE 2 — "Chamber economics":
"Chamber earns lifetime rev-share on every active member subscription — 18% for Founding Partners, 15% standard."

TILE 3 — "Board workload":
"AI handles the execution layer: social posts, reputation monitoring, outbound, event promotion, reporting. Board approves strategy; AI delivers the work."

TILE 4 — "Differentiation":
"No other Chamber in your region offers this. First-mover Chambers lock Founding Partner economics."

═══════════════════════════════════════
SECTION 4.5 — "Two Boats" (Hammer Weave) (#131825 background)
═══════════════════════════════════════

H2 (white): "Two Boats, One Choice"

Intro paragraph (#C5CDD8, max-width 780px):
"Every Chamber reaches the same fork. One boat is a traditional vendor relationship — the Chamber pays for a website, a software license, or a marketing service; the vendor delivers; the Chamber books the expense. Money flows one direction. The other boat is a channel partnership — the Chamber delivers a vetted service to members; the Chamber earns a margin on every member who subscribes; non-dues revenue grows while members grow their businesses. Money flows both directions."

2-column side-by-side table (mobile: stacked). Each column: 1px border rgba(255,255,255,0.1), 28px padding, 12px radius.

LEFT COLUMN header (muted white, 16px): "BOAT 1 — Traditional Vendor Relationship"
Bulleted list (#C5CDD8, 15px, line-height 1.7):
• Chamber pays vendor monthly / annually
• Chamber absorbs cost; Board sees expense line
• Member benefit is indirect (internal efficiency)
• Vendor owns the member relationship after introduction
• Relationship ends when contract ends

RIGHT COLUMN header (#00A6FF, 16px): "BOAT 2 — Channel Partnership (Chamber AI Advantage)"
Bulleted list (white, 15px, line-height 1.7):
• Chamber earns margin on every active member subscription
• Chamber adds non-dues revenue; Board sees income line
• Member benefit is direct (members receive AI marketing at Chamber-member pricing)
• Chamber owns the branded member relationship permanently
• Relationship compounds as member base grows

Closing line (bold, centered, 24px, white on #10B77F fill band, 16px padding, max-width 560px):
"Boat 1 is a budget line. Boat 2 is an engine."

═══════════════════════════════════════
SECTION 5 — "The Chamber AI Advantage Model" (#0F172A background)
═══════════════════════════════════════

H2: "How the Chamber AI Advantage Model Works"

3-phase horizontal timeline (mobile: stacked vertical). Each phase tile: #131825 bg, 12px radius, 28px padding, 1px subtle border:

PHASE 1 — "Chamber Website + AI Support (Layer 1)":
Sub: "Your Chamber's own website, rebuilt and AI-supported."
Body: "Full website migration to a modern stack, AI chatbot for visitor inquiries, ticketing, SEO foundation, Google Business Profile optimization, security hardening. One-time build, delivered in 3-4 weeks."

PHASE 2 — "White-Labeled Member Program (Layer 2)":
Sub: "AI marketing as a Chamber-branded member benefit."
Body: "Members subscribe to the Chamber's AI marketing service at Chamber-member pricing (15% off public retail). The Chamber earns Founding Partner rev-share on every subscription — 18% for Founding Chambers, 15% standard. Members get enterprise AI at a rate they couldn't access on their own. Zero platform cost to the Chamber for this layer."

PHASE 3 — "Chamber OS + ongoing partnership (Layer 3)":
Sub: "Optional internal Chamber automation."
Body: "Dedicated AI infrastructure running Chamber operations — harvested Chamber content, Board decision execution, modular capabilities from basic ops to full Chamber automation. Scales with the Chamber."

═══════════════════════════════════════
SECTION 6 — "Board Reporting + Governance" (#131825 background)
═══════════════════════════════════════

H2: "Board-Ready AI — Reporting, Governance, Peace of Mind"

Two-column layout (mobile stacked):

LEFT COLUMN — Board reporting:
H3 (white, 20px): "Monthly Board Reports"
Body (#C5CDD8): "Every month, your Board receives a plain-language report covering member outcomes, subscription growth, non-dues revenue earned, and key metrics. No dashboards to learn. No vendor reports to decode. Just the numbers the Board cares about, translated into decisions they need to make."

RIGHT COLUMN — AI governance:
H3: "AI Governance Templates"
Body: "AMG provides a Board-approved AI Policy Template, clear usage boundaries, data retention standards, and regular compliance updates. Your Chamber adopts AI with documented governance — not experimental risk."

SUB-BLOCK appended (full-width, max-width 780px, #0F172A bg, 28px padding, 12px radius, 36px top margin):
H3 (#00A6FF, 18px): "What the Board sees at the 6-month mark"
Body (white, 17px, line-height 1.6):
"Six months after launch, the Board reporting segment looks different. The Executive Director reports on member businesses that generated measurable growth through Chamber-delivered services. The Treasurer reports the non-dues revenue line — a recurring number, not an event spike. Board members hear stories from member businesses that start with 'my Chamber helped me grow.' The Chamber's narrative shifts from activities to outcomes."

Below sub-block, secondary outlined CTA:
"Download the Chamber AI Policy Template →" → /resources/chamber-ai-policy-template (stub)

═══════════════════════════════════════
SECTION 7 — FAQ (AEO-critical, FAQPage schema) (#0F172A background)
═══════════════════════════════════════

H2 (centered, white): "Frequently Asked Questions"

9 Q&A blocks. Each: expandable accordion OR always-open on desktop, always-open on mobile. Q in bold white 18px, A in #C5CDD8 15px line-height 1.6, 20px padding between each.

Q1: "How can a chamber of commerce use AI?"
A1: "Chambers use AI across four layers: internal operations (CRM, events, email, reporting), member benefit delivery (AI marketing at Chamber-member pricing), outbound and recruitment (AI prospect identification), and governance + reporting (Board-ready summaries and AI policy compliance). The Chamber AI Advantage program packages all four into a single channel partnership."

Q2: "What's the best way for a chamber of commerce to generate non-dues revenue?"
A2: "The fastest-growing non-dues revenue category in 2026 is channel partnerships — the Chamber delivers a vetted service to members and earns a margin on every sale. Traditional affinity programs (insurance, office supplies) are commoditized. AI marketing channel partnerships are uncommoditized, high-value, recurring, and aligned with what member businesses actually need."

Q3: "What does a chamber channel partner program look like?"
A3: "A Chamber channel partner program is a revenue-sharing agreement where the Chamber offers a service to members under Chamber branding and earns a percentage of every subscription. The Chamber AI Advantage program is structured as a Founding Partner agreement: 18% lifetime rev-share on member subscriptions for Founding Chambers (15% standard), white-labeled delivery, Chamber-controlled branding, and zero platform cost for the member-benefit layer."

Q4: "Should a chamber invest in AI tools?"
A4: "Yes — but with governance. Chambers that adopt AI without a Board-approved policy take on unnecessary risk. The Chamber AI Advantage program includes a Board-ready AI Policy Template, documented data handling, and regular compliance updates. Governance is how Chambers move faster without creating exposure."

Q5: "How is this different from ChamberMaster or GrowthZone?"
A5: "Traditional Chamber management software (ChamberMaster, GrowthZone, MemberClicks) is built for internal Chamber operations — roster management, event registration, billing. The Chamber AI Advantage program is built for MEMBER revenue — delivering AI marketing to member businesses as a Chamber-branded benefit, with the Chamber earning a margin. The two are complementary, not competitive."

Q6: "What does Founding Partner status mean?"
A6: "Founding Partners are the first 10 Chambers to adopt the program globally. Founding Partners receive enhanced economics (18% lifetime rev-share vs 15% standard), locked setup pricing, priority onboarding, reference-case positioning, and contractual first-mover protection in their service area. Only the first 10 Chambers qualify; after that, standard terms apply."

Q7: "What's the delivery timeline?"
A7: "Layer 1 (Chamber website rebuild + AI support) is delivered in 3-4 weeks from deposit. Layer 2 (member platform) launches immediately after Layer 1 ships, typically Week 5-6. Layer 3 (Chamber OS) is modular and can begin anytime — most Chambers start it in Month 3."

Q8: "What's the risk to our Chamber if member adoption is soft?"
A8: "Layer 2 (the member-benefit program) has zero platform cost to the Chamber. Layer 1 (website rebuild) is a one-time investment with value regardless of member adoption. The Chamber's launch webinar, co-op marketing match, and Board-ready member communications template are included to accelerate adoption. If a Chamber purchases Exclusive Territory, quota-miss rules with a 30-day cure period apply, and the Chamber retains all existing member relationships and rev-share on those."

Q9: "How is this different from the 20 vendors pitching my Chamber every quarter?"
A9: "Traditional Chamber vendors sell the Chamber a tool the Chamber pays for. The Chamber AI Advantage program inverts that — AMG pays the Chamber a share of every member subscription sold through the channel. The Chamber's budget isn't a cost center; it's a revenue line. Regional exclusivity also means the first Chamber in a market closes the door behind them."

═══════════════════════════════════════
SECTION 8 — CLOSING CTA BAND (Hammer Weave) (gradient #10B77F → #0EA572, dark text)
═══════════════════════════════════════

H2 (dark, centered, 40px desktop): "Founding Partner status is granted once per region. Which Chamber claims your market?"

Paragraph (dark, max-width 720px, 17px):
"The first Chamber in each region locks regional Founding Partner terms for the life of the agreement. Subsequent Chambers in that region are not eligible for Founding Partner economics. Apply today to secure first-mover status."

Two CTAs side by side:
- Primary (solid dark #131825 fill, white text, 12px radius): "Apply as a Founding Partner →" → /become-a-partner
- Secondary (outlined dark): "Book a 30-minute intro call →" → /book-call

═══════════════════════════════════════

TECHNICAL REQUIREMENTS:
1. Add JSON-LD schema: Article + FAQPage (all 9 Q&As) + Organization + BreadcrumbList. Include "Last updated: April 2026" in Article schema.
2. Page weight under 200KB if possible. Lazy-load any images below fold.
3. Semantic heading hierarchy (H1 → H2 → H3 — no skipping).
4. All links with descriptive anchor text.
5. Open Graph + Twitter Card meta tags with a hero image using the program name.
6. Canonical tag pointing to /chamber-ai-advantage.
7. Visible breadcrumb at top: Home > Chamber AI Advantage.
8. Mobile: 48px minimum tap targets, 16px minimum body text.
9. All text WCAG AA contrast against its background. Verify with automated check.

Do NOT modify any other page. Font: DM Sans. No gold. No Montserrat. No mention of any underlying vendor/platform/tool.
```

---

## PROMPT 7 — /become-a-partner PAGE (Execution Package Part D, corrected)

```
Create a new page at route /become-a-partner.

Page title tag: "Become a Chamber Founding Partner | AMG Chamber AI Advantage Program"
Meta description: "Apply to become a Chamber of Commerce Founding Partner in the AMG AI Advantage program. Earn lifetime rev-share on member subscriptions. Limited regional exclusivity — only 10 Founding slots globally."

Use existing site shell. Global palette: dark navy #131825 base, #0F172A alternate, white + #C5CDD8 text, #00A6FF accents, #10B77F primary CTAs. DM Sans font. 10-12px radius. No gold. No Montserrat.

PAGE STRUCTURE:

═══════════════════════════════════════
SECTION 1 — HERO (#131825 background)
═══════════════════════════════════════

EYEBROW (#00A6FF): "FOUNDING PARTNER APPLICATION"

H1 (white): "Chamber of Commerce AI Affinity Program — Founding Partner Application"

Sub-headline (#C5CDD8, max-width 780px):
"Earn 18% lifetime rev-share on every Chamber-member AI marketing subscription. Only 10 Founding Partner slots globally. Board-ready structure. Zero platform cost for the member-benefit layer."

Primary CTA (green #10B77F): "Apply Now →" (scrolls to form at bottom of page)

═══════════════════════════════════════
SECTION 2 — AEO PASSAGE (#0F172A background, max-width 780px)
═══════════════════════════════════════

No H2. Callout block with 3px left border #00A6FF, 28px padding.

PARAGRAPH 1 (white, 20px):
"A chamber of commerce channel partner program is a revenue-sharing agreement where the Chamber offers a vetted service to members under Chamber branding and earns a percentage of every subscription. AMG's Chamber AI Advantage is the first AI-marketing-specific channel partnership: 18% lifetime rev-share for Founding Partners (15% standard), zero platform cost for the member-benefit layer, white-labeled delivery, regional exclusivity for Founding Partners."

PARAGRAPH 2 (#C5CDD8, 16px):
"Unlike traditional affinity programs (insurance cards, office supply discounts), the member benefit here is an active marketing service that grows member businesses — which is the outcome every Chamber exists to support."

═══════════════════════════════════════
SECTION 3 — "Founding Partner Economics" (#131825 background)
═══════════════════════════════════════

H2: "Founding Partner Economics"

4-column stat grid (mobile: 2×2). Each stat card: #0F172A bg, 12px radius, 28px padding, 1px border rgba(0,166,255,0.15), centered content:

STAT 1:
Number (#00A6FF, 48px, weight 700): "18%"
Label (white, 15px weight 600): "Founding Partner rev-share"
Sub (#C5CDD8, 13px): "locked for life · 15% standard post-Founding"

STAT 2:
Number: "$0"
Label: "Platform cost for Layer 2"
Sub: "member-benefit platform has zero cost to Chamber"

STAT 3:
Number: "10"
Label: "Founding slots globally"
Sub: "regional exclusivity to first-qualified"

STAT 4:
Number: "Life"
Label: "Term on rev-share"
Sub: "for as long as subscriptions remain active"

═══════════════════════════════════════
SECTION 4 — "What Members Get" (#0F172A background)
═══════════════════════════════════════

H2: "What Your Members Get"

Intro (#C5CDD8, max-width 780px):
"Members subscribe to AMG AI marketing at Chamber-member pricing — 15% off public retail. Every member receives a dedicated AI marketing team delivering the full service bundle, Chamber-branded."

6-feature grid (3×2 desktop, stacked mobile). Each tile: #131825 bg, 12px radius, 24px padding, icon + label + one-line body:

F1 icon + label: "AI-powered SEO + content marketing"
F2: "Social media management + scheduling"
F3: "Reputation management + review response"
F4: "Paid ad strategy + creative"
F5: "Lead generation + outbound"
F6: "Performance reporting + analytics"

Closing line (white, centered, 20px, weight 600, max-width 680px):
"All delivered under the Chamber's brand. Members experience 'my Chamber helped me grow.'"

═══════════════════════════════════════
SECTION 5 — "How Your Chamber Earns" (#131825 background)
═══════════════════════════════════════

H2: "How Your Chamber Earns"

Intro (#C5CDD8, max-width 780px):
"The Chamber earns rev-share on every active member subscription — for the life of the subscription. Founding Partners lock 18% for life. Standard Chambers earn 15%."

3-tier table (mobile: stacked vertical). Each tier row: #0F172A bg, 12px radius, 24px padding:

| Plan | Public retail | Chamber member rate | Founding 18% | Standard 15% |
|---|---|---|---|---|
| Starter | $497/mo | $422/mo | $76/mo | $63/mo |
| Growth | $797/mo | $677/mo | $122/mo | $102/mo |
| Pro | $1,497/mo | $1,272/mo | $229/mo | $191/mo |

Note below table (#C5CDD8, 14px):
"Member rates reflect the standard 15% Chamber-member discount off public retail. All tiers carry the same rev-share to the Chamber."

═══════════════════════════════════════
SECTION 6 — "AI Member Benefits Chambers Can White-Label" (#0F172A background)
═══════════════════════════════════════

H2: "AI Member Benefits Your Chamber Can White-Label"

H3 (white, 22px): "White-Label AI Marketing for Chamber Members"
Paragraph (#C5CDD8):
"Every subscription is white-labeled under the Chamber's name. Members receive email from the Chamber, see Chamber branding in dashboards, and experience the service as a Chamber offering. AMG operates as an invisible delivery partner."

H3: "Rev-Share Structure"
Paragraph:
"Founding Chambers lock 18% rev-share for life. Standard Chambers earn 15%. Rev-share is a percentage of net collected subscription revenue from Chamber-referred members, paid monthly."

H3: "Regional Exclusivity"
Paragraph:
"Default territory is a 20-mile non-exclusive radius from Chamber HQ. Chambers that want hard regional exclusivity can purchase Exclusive Territory with annual quotas and a 30-day cure period on misses. Cross-state anti-poaching is contractual across all partners."

═══════════════════════════════════════
SECTION 7 — APPLICATION FORM (#131825 background)
═══════════════════════════════════════

H2: "Apply to Become a Founding Partner"

Paragraph (#C5CDD8, max-width 720px):
"Applications are reviewed weekly. Qualified Chambers receive a 30-minute intro call within 5 business days. Founding Partner slots are offered on a first-qualified basis by region."

FORM (centered, max-width 680px, 28px padding, #0F172A bg, 12px radius, 1px border rgba(255,255,255,0.1)):

1. Chamber Name * (text input, required)
2. Your Role * (dropdown: Executive Director / President / Board Member / Communications / Other, required)
3. Your Name * (text input, required)
4. Email * (email input, required)
5. Phone (text input, optional)
6. Chamber Member Count * (dropdown: Under 100 / 100-250 / 250-500 / 500-1,000 / 1,000+, required)
7. Chamber Website (text input, optional)
8. What interests your Chamber most about this program? (textarea, optional, 4 rows)

CONSENT checkbox: "I'm authorized to discuss partnerships on behalf of my Chamber."

Honeypot hidden field: name="website_url_hp", aria-hidden="true", not visible to users (bot capture).

SUBMIT BUTTON (large, green #10B77F fill, white text, 14px padding, 12px radius, weight 600, full-width of form):
"Submit Application →"

Small text below submit (#C5CDD8, 13px):
"We'll respond within 5 business days. Your information is used only to evaluate this partnership and is never shared."

FORM BEHAVIOR:
- Client-side validation: required fields, email format, honeypot empty
- POST to /api/chamber-partner-application (Titan will wire this endpoint on VPS)
- On success: show inline success state with heading "Application received" and body "We'll be in touch within 5 business days. Check your email for confirmation."
- On failure: inline error message, form state preserved

═══════════════════════════════════════
SECTION 8 — FAQ (FAQPage schema) (#0F172A background)
═══════════════════════════════════════

H2 (centered, white): "Frequently Asked Questions"

Q1: "How do Chambers create member benefit programs that actually drive retention?"
A1: "Retention-driving benefits share three traits: members can't easily replicate the value on their own, the benefit delivers measurable economic outcome, and members consume it regularly. AI marketing subscriptions satisfy all three — individual members can't access enterprise AI pricing on their own, the economic impact is measurable in member business growth, and members engage monthly."

Q2: "What happens if our Chamber signs and member adoption is soft?"
A2: "Layer 2 (the member-benefit platform) has zero platform cost to the Chamber. Layer 1 (website rebuild) is a one-time investment with value regardless of Layer 2 adoption. Chambers that purchase Exclusive Territory have an annual quota with a 30-day cure period — if missed, the Chamber retains all existing member relationships and rev-share on those, and the territory returns to non-exclusive status."

Q3: "Can the Chamber set its own member pricing?"
A3: "Member pricing is uniform across all Founding Partner Chambers — 15% off public retail. This protects member trust and prevents inter-Chamber pricing competition. Chambers may offer promotional first-month incentives from their own member budget if desired."

Q4: "Is there a minimum member count to qualify?"
A4: "Qualification isn't based on a hard minimum; we evaluate fit during the intro call. Chambers of any size can succeed in the program with the right communication strategy. Smaller Chambers are often strong candidates because the program economics can offset operating budget pressure quickly."

Q5: "What is the AMG commitment to the Chamber?"
A5: "AMG commits to: white-labeled delivery under Chamber branding, monthly Board-ready reporting, 18% lifetime rev-share for Founding Partners (15% standard), regional Founding Partner protection, launch webinar support, Board-ready AI Policy Template, and ongoing platform evolution at no additional cost to the Chamber for the member-benefit layer."

═══════════════════════════════════════

TECHNICAL REQUIREMENTS:
1. JSON-LD schema: Service + FAQPage + Organization + BreadcrumbList
2. Form POSTs to /api/chamber-partner-application (Titan wires on VPS). If endpoint not yet live, post to a placeholder that emails growmybusiness@aimarketinggenius.io via Resend SMTP with subject "Founding Partner application: {{chamber_name}}".
3. Client-side validation + honeypot + rate limit (3 submissions per IP per hour server-side)
4. Success page redirects to /become-a-partner?submitted=1 OR shows inline success state — either acceptable
5. Email notification on submit to growmybusiness@aimarketinggenius.io
6. Breadcrumb: Home > Chamber AI Advantage > Become a Partner
7. OG + Twitter Card + canonical tags
8. Mobile + accessibility AA

Do NOT modify any other page. Font: DM Sans. No gold. No Montserrat. No vendor/platform name leaks.
```

---

## PROMPT 8 — /case-studies INDEX PAGE (Addendum #1 Part K.4, corrected)

```
Create a new page at route /case-studies.

Page title: "Case Studies | AMG AI Marketing Results for Local + Ecommerce Businesses"
Meta description: "Real results from AMG's AI marketing platform. Case studies from Shopify ecommerce brands, family entertainment centers, home services companies, and retail — all on the same AI platform."

Use existing site shell, palette #131825 base + #0F172A alternate + white/#C5CDD8 text + #00A6FF accents + #10B77F CTAs. DM Sans. No gold. No Montserrat.

STRUCTURE:

═══════════════════════════════════════
SECTION 1 — HERO (#131825)
═══════════════════════════════════════

EYEBROW (#00A6FF): "PROOF"
H1 (white): "Real Results from AMG's AI Marketing Platform"
Sub (#C5CDD8, max-width 780px): "Across Shopify ecommerce, family entertainment centers, home services, and retail — our AI agents deliver measurable outcomes. Every case below is a real AMG client."

═══════════════════════════════════════
SECTION 2 — AEO PASSAGE (#0F172A, max-width 780px)
═══════════════════════════════════════

Callout block with 3px left border #00A6FF.

Body (white, 17px):
"AMG's AI marketing platform produces consistent results across verticals because the system is built on the same multi-agent architecture regardless of industry. Each client receives a dedicated AMG AI team — SEO, content, reputation, paid ads, CRO, outbound — operating as a coordinated unit. The case studies below show what this looks like in production across ecommerce, local service, and entertainment businesses."

═══════════════════════════════════════
SECTION 3 — FEATURED CASE STUDIES (#131825)
═══════════════════════════════════════

H2 (white): "Featured Case Studies"

2-column large-card grid (mobile: stacked). Each card: #0F172A bg, 12px radius, 1px border rgba(0,166,255,0.2), hover state lift + border #00A6FF.

CARD 1 — SHOP UNIS:
- Top image placeholder (industry-specific, lazy-loaded, 16:9 aspect)
- Vertical tag (small uppercase #00A6FF): "ECOMMERCE — SHOPIFY"
- H3 (white, 24px): "Shop UNIS / Sun-Jammer"
- 3 metric stat bullets (#C5CDD8, bold numbers white): [TITAN — replace with real metrics from Viktor AI > Case Studies Drive folder, SHOP UNIS Full Case Study v5. If metrics unverifiable, omit rather than fabricate.]
- Short quote (14px, italic, #C5CDD8, if available from source doc)
- Link (right-aligned, #00A6FF): "Read the full case study →" → /case-studies/shop-unis

CARD 2 — PARADISE PARK NOVI:
- Top image placeholder
- Vertical tag: "FAMILY ENTERTAINMENT CENTER"
- H3: "Paradise Park Novi"
- 3 metric bullets (from Paradise Park Full Case Study, Jeff Wainwright CEO)
- Link → /case-studies/paradise-park-novi

═══════════════════════════════════════
SECTION 4 — MORE CASE STUDIES (#0F172A)
═══════════════════════════════════════

H2: "More AMG Client Results"

3-column smaller card grid (mobile: stacked). Each card same styling as Section 3 but compact:

CARD 3 — MIKE SILVERMAN:
- Vertical tag: "HOME SERVICES — WATER DAMAGE"
- H3: "Mike Silverman — Texas Water Damage Repair"
- 3 metric bullets (from Mike Silverman Full Case Study)
- Link → /case-studies/mike-silverman-water-damage

CARD 4 — REVEL & ROLL WEST:
- Vertical tag: "ENTERTAINMENT — BOWLING"
- H3: "Revel & Roll West"
- 3 metric bullets
- Link → /case-studies/revel-roll-west

CARD 5 — CLAWCADE:
- Vertical tag: "AMUSEMENT — ARCADE OPERATIONS"
- H3: "ClawCADE"
- 3 metric bullets
- Link → /case-studies/clawcade

═══════════════════════════════════════
SECTION 5 — TESTIMONIALS (#131825)
═══════════════════════════════════════

H2: "What Clients Say"

3-column testimonial grid (mobile: stacked). Each tile: #0F172A bg, 12px radius, 24px padding:

T1 — James St John:
- Headshot circle 64px (from Drive if available)
- Quote (pull from Testimonial James St John doc, 1 sentence verbatim max 25 words)
- Name + Business (small #C5CDD8)

T2 — Rich Grant Tree Service (video):
- Thumbnail + play button (inline native HTML5 <video> with poster image, muted autoplay + unmute on tap)
- Quote overlay (pull from Rich Grant transcript, strongest 1-sentence)
- Vertical tag: "HOME SERVICES — TREE SERVICE"

T3 — Sam Adodra (video):
- Same video pattern
- Quote overlay
- Vertical tag: per transcript context

═══════════════════════════════════════
SECTION 6 — CLOSING CTA (gradient #10B77F → #0EA572, dark text)
═══════════════════════════════════════

H2 (dark, centered, 32px): "Ready to see what AMG can do for your business?"
Paragraph (dark, 16px, centered): "Same AI platform. Same results. Different vertical."

Two CTAs:
- Primary (dark #131825 fill, white text, 12px radius): "See our services →" → /
- Secondary (outlined dark): "For Chambers of Commerce →" → /chamber-ai-advantage

═══════════════════════════════════════

TECHNICAL:
1. Schema: CollectionPage + ItemList + individual CaseStudy items
2. LazyLoad all images below fold
3. Video embeds via HTML5 <video> with poster (avoid YouTube iframe weight). Host videos at R2 amg-storage with public read.
4. Breadcrumb: Home > Case Studies
5. Canonical, OG, Twitter Card tags
6. Schema validates via Google Rich Results Test

Font DM Sans. No gold. No Montserrat. No vendor leaks.

TITAN NOTE: all client metrics + quotes pulled from Viktor AI > Case Studies Drive folder (folder ID 1tBNVv96TtU_TCpyrmGRfygn5oX2HqAcg). If a specific number isn't in the source doc, OMIT that bullet. Never fabricate.
```

---

## PROMPT 9-13 — /case-studies/{slug} SUB-PAGES

Use this template for each of the 5 case study sub-pages. Replace `{slug}` + `{client_name}` + `{vertical_tag}` + source metric data with values from the corresponding Viktor AI Drive source doc.

Sub-pages:
- `/case-studies/shop-unis` (Shop UNIS / Sun-Jammer, Ecommerce Shopify)
- `/case-studies/paradise-park-novi` (Paradise Park Novi, Family Entertainment Center)
- `/case-studies/mike-silverman-water-damage` (Mike Silverman, Home Services)
- `/case-studies/revel-roll-west` (Revel & Roll West, Entertainment/Bowling)
- `/case-studies/clawcade` (ClawCADE, Amusement/Arcade)

Prompt template (paste verbatim per sub-page, swapping the 4 bracketed values):

```
Create a new page at route /case-studies/{slug}.

Page title: "{client_name} Case Study | AMG AI Marketing Results"
Meta description: "[TITAN pulls 1-2 sentence summary from the source doc]"

Use existing site shell, #131825/#0F172A palette, DM Sans, #10B77F CTAs, no gold, no Montserrat.

SECTIONS:

A — HERO: client name + vertical tag + hero image + one-sentence summary pulled from source
B — AEO PASSAGE (first 150 words): "who the client is + what they needed + what AMG delivered" in prose form, #0F172A callout block
C — THE CHALLENGE: 2-3 paragraphs, what the client faced before AMG (pulled from source)
D — THE AMG APPROACH: which AI agents were engaged + what they executed (trade-secret clean — "AMG SEO agent" / "AMG content agent", never underlying platforms)
E — THE RESULTS: 3-6 metric tiles (real numbers only; OMIT if not in source), optional before/after comparison
F — CLIENT VOICE: 1-2 verbatim quotes with attribution (lightly edit for flow only, never fabricate)
G — VISUALS: 3-6 screenshots from Social Proof Collage in source doc, compressed WebP <200KB each, alt text includes client + result
H — RELATED CASE STUDIES: 2 cards pointing to sibling case-study sub-pages
I — CLOSING CTA: "Explore AMG for [their vertical] →" → /
J — CHAMBER CTA BAND: secondary band with "Are you a Chamber? Offer results like this to your members →" → /chamber-ai-advantage

Schema: CaseStudy/Article + Organization + BreadcrumbList + ItemList for G.
Breadcrumb: Home > Case Studies > {client_name}

TITAN NOTES — STRICT:
- Read the actual Drive case study doc before writing copy. Don't synthesize from memory.
- Pull the strongest 3-6 metrics from the "Results" section of the source doc.
- Pull 1-2 verbatim client quotes (edit lightly for flow, never fabricate).
- Use Social Proof Collage images — compressed WebP, descriptive alt text.
- If source material is weak or results are soft → flag to Solon, do NOT publish weak case study.
- Trade-secret discipline: NEVER name Claude/Anthropic/n8n/Supabase/Lovable/GHL/Suno/Stagehand/Viktor/AWS/GCP/Cloudflare/Hetzner/HostHatch/ElevenLabs/Deepgram/Whisper. Use "AMG's AI agents" / "AMG's proprietary platform" / "AMG's cloud infrastructure."
- Client-specific platform names OK (Shopify, Square, GBP) since they're the client's own stack.

Font DM Sans. No gold. No Montserrat.
```

---

## PROMPT 14 — /book-call STUB (Addendum #6 AM.8 default)

```
Create a new page at route /book-call.

Page title: "Book a 30-Minute Intro Call with Solon | AI Marketing Genius"
Meta description: "Book a 30-minute conversation with Solon, AMG's founder. Discuss your Chamber, business, or website project."

Use existing site shell. #131825 bg, DM Sans, #10B77F CTA.

STRUCTURE:

═══════════════════════════════════════
SECTION 1 — HERO
═══════════════════════════════════════

EYEBROW (#00A6FF): "30-MINUTE INTRO CALL"
H1 (white): "Let's talk."
Sub (#C5CDD8, max-width 640px): "Chamber partnership, business services, or a website project. Whatever brought you here, book 30 minutes and we'll figure out the best path."

═══════════════════════════════════════
SECTION 2 — FORM (centered, max-width 560px, #0F172A bg, 12px radius, 28px padding)
═══════════════════════════════════════

If Solon provides a Calendly URL, replace this form with an embedded Calendly iframe + fallback link.

Otherwise:

FORM fields:
1. Your Name * (text)
2. Email * (email)
3. Phone (text, optional)
4. Business or Chamber Name * (text)
5. What's this about? * (dropdown: Chamber partnership / Business services / Website project / Other)
6. Anything specific you'd like to discuss? (textarea, optional)
7. Preferred day/time * (text: "e.g. Tuesday afternoon ET")

Honeypot hidden field + rate limit.

SUBMIT BUTTON (green #10B77F, full-width, 14px padding, 12px radius, 600 weight):
"Request a time →"

On success: show "Thanks — we'll confirm a time within 24 hours. Watch your inbox."

Email notification to growmybusiness@aimarketinggenius.io with subject "Intro call request: {{name}} — {{subject}}".

═══════════════════════════════════════

Do NOT modify any other page. Font DM Sans. No gold. No Montserrat.
```

---

## PROMPT 15 — /resources/chamber-ai-policy-template STUB (blog 4 lead magnet landing, optional — ship with blog 4)

```
Create a new page at route /resources/chamber-ai-policy-template.

Page title: "Free Chamber AI Policy Template (Board-Ready PDF) | AI Marketing Genius"
Meta description: "Download AMG's free Chamber AI Policy Template — a Board-ready PDF that any Chamber can adopt with minor modifications. Created and maintained by AMG."

Hero + email-capture form:

EYEBROW (#00A6FF): "FREE DOWNLOAD"
H1: "The Chamber AI Policy Template Every Board Should Adopt"
Sub (#C5CDD8): "A 5-element framework as a Board-ready PDF. Covers AI tools used, data handling, member/donor information protection, oversight cadence, and public disclosure. Drafted for Chamber use. Adopt with minor modifications."

Form:
1. First Name *
2. Chamber Name *
3. Role *
4. Email *

Consent checkbox: "I agree to receive Chamber-program communications from AMG."

Submit → POST /api/crm/leads with persona=chamber, tag=chamber-ai-policy-download, and trigger email with PDF signed URL from amg-storage/lead-docs/.

Success state: "Check your inbox for the PDF. It's also available as a backup link below."

Below form, CTA band:
"Want to go deeper? → See the Chamber AI Advantage program" → /chamber-ai-advantage

Font DM Sans. No gold. No Montserrat.
```

---

## EXECUTION ORDER SUMMARY

1. Prompt 0.1-0.3 (technical SEO files) — do first, before any page prompt
2. Prompt 1 (Chamber band) — wait for ship → Lumina ≥9.3
3. Prompt 2 (hero sentence weave)
4. Prompt 3 (footer column)
5. Prompt 4 (3-persona CTA strip) — depends on Prompts 1 + 2 shipping first
6. Prompt 5 (Client Results row)
7. Prompt 6 (/chamber-ai-advantage)
8. Prompt 7 (/become-a-partner) — depends on Prompt 6 being live for linking
9. Prompt 8 (/case-studies index)
10. Prompts 9-13 (case study sub-pages) — one at a time
11. Prompt 14 (/book-call stub)
12. Prompt 15 (/resources/chamber-ai-policy-template, ship with Blog 4)

After all prompts ship + Lumina ≥9.3 each: run dual-engine Grok + Perplexity ≥9.3 on /chamber-ai-advantage + /become-a-partner + /case-studies before final pitch.

---

**End of atomic Lovable prompts. Solon pastes one at a time; Lumina reviews between each; dual-engine at end.**
