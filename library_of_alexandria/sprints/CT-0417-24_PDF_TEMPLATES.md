# CT-0417-24 — Persona PDF HTML Templates

**Date:** 2026-04-17
**Scope:** 4 persona-specific PDF templates + 1 universal Case Studies 1-pager, rendered via weasyprint OR pptx-pdf skill, personalized per lead via `{{LEAD_NAME}}` + `{{CHAMBER_NAME}}` placeholders, stored at `amg-storage/lead-docs/{lead_id}/{filename}.pdf` with 48hr signed URLs.
**Brand:** AMG live-site tokens per `library_of_alexandria/brand/amg-brand-tokens-v1.md` — dark navy #131825 + cyan #00A6FF + green #10B77F + DM Sans. NO gold. NO Montserrat.
**Copy source:** body copy for each PDF will be replaced with finished prose from SEO|Social|Content project commission CT-0417-27 (email + Alex scripts extended to include persona PDF bodies). Placeholder copy below is structural only.

---

## Shared CSS (used by all PDFs)

```css
@page {
  size: Letter;
  margin: 0.5in 0.6in;
  @bottom-center {
    content: "AMG · aimarketinggenius.io · growmybusiness@aimarketinggenius.io · Prepared for {{LEAD_NAME}}";
    font-family: "DM Sans", sans-serif;
    font-size: 9pt;
    color: #8796A8;
  }
}
body {
  font-family: "DM Sans", sans-serif;
  color: #1a1f2e;
  line-height: 1.55;
  font-size: 11pt;
  margin: 0; padding: 0;
}
h1 { color: #131825; font-size: 28pt; font-weight: 700; margin: 0 0 8pt 0; line-height: 1.15; }
h2 { color: #131825; font-size: 18pt; font-weight: 700; margin: 24pt 0 8pt 0; line-height: 1.2; }
h3 { color: #131825; font-size: 14pt; font-weight: 600; margin: 16pt 0 6pt 0; }
.eyebrow { color: #00A6FF; font-size: 10pt; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8pt; }
.cover {
  background: linear-gradient(135deg, #131825 0%, #0F172A 100%);
  color: #FFFFFF;
  padding: 1.2in 0.8in 1in 0.8in;
  margin: -0.5in -0.6in 24pt -0.6in;
}
.cover h1 { color: #FFFFFF; font-size: 36pt; margin-bottom: 12pt; }
.cover .eyebrow { color: #00A6FF; }
.cover .subtitle { color: #C5CDD8; font-size: 14pt; font-weight: 500; }
.cta-band {
  background: #10B77F; color: #131825;
  padding: 18pt 24pt; margin: 24pt 0;
  border-radius: 6pt; text-align: center;
  font-weight: 600;
}
.cta-band a { color: #131825; text-decoration: underline; }
.stat-grid { display: flex; gap: 12pt; margin: 12pt 0; }
.stat-card {
  flex: 1; background: #F5F7FA;
  border-left: 3pt solid #00A6FF;
  padding: 12pt 14pt; border-radius: 4pt;
}
.stat-card .num { color: #00A6FF; font-size: 22pt; font-weight: 700; line-height: 1; }
.stat-card .label { color: #131825; font-size: 10pt; font-weight: 600; margin-top: 4pt; }
.stat-card .sub { color: #465467; font-size: 9pt; margin-top: 2pt; }
ul.bullets { padding-left: 18pt; }
ul.bullets li { margin-bottom: 6pt; }
.tile {
  background: #F5F7FA; padding: 12pt; border-radius: 4pt; border: 0.5pt solid #E2E8F0;
  margin-bottom: 10pt;
}
.quote {
  border-left: 3pt solid #00A6FF; padding: 8pt 12pt;
  font-style: italic; color: #2a3342; background: #F5F7FA;
  margin: 12pt 0;
}
footer-note { color: #8796A8; font-size: 8pt; }
.muted { color: #465467; }
```

---

## Template 1 — `partner-program.html` (Chamber persona, 2 pages)

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Chamber AI Advantage — Partner Program Overview</title>
<style>/* shared CSS inlined */</style>
</head>
<body>

<!-- COVER / HEADER -->
<div class="cover">
  <div class="eyebrow">CHAMBER AI ADVANTAGE</div>
  <h1>Partner Program Overview</h1>
  <div class="subtitle">Prepared for {{LEAD_NAME}}{{#CHAMBER_NAME}} · {{CHAMBER_NAME}}{{/CHAMBER_NAME}}</div>
</div>

<!-- PAGE 1 -->
<h2>The 3-Layer Chamber AI Advantage Model</h2>

<h3>Layer 1 — Chamber Website + AI Support</h3>
<p>Your Chamber's own website rebuilt on a modern stack, with an AI chatbot for visitor inquiries, ticketing, SEO foundation, Google Business Profile optimization, and security hardening. One-time build, delivered in 3–4 weeks.</p>

<h3>Layer 2 — White-Labeled Member Program</h3>
<p>Members subscribe to Chamber-branded AI marketing services at Chamber-member pricing (15% off public retail). The Chamber earns rev-share on every active subscription — <strong>18% for Founding Partners (first 10 Chambers globally), 15% standard</strong>. Zero platform cost to the Chamber for this layer.</p>

<h3>Layer 3 — Chamber OS (optional)</h3>
<p>Dedicated AI infrastructure running internal Chamber operations. Modular — Chambers activate only what they need. Scales from basic ops to full Chamber automation.</p>

<h2>Founding Partner Economics</h2>

<div class="stat-grid">
  <div class="stat-card"><div class="num">18%</div><div class="label">Founding rev-share</div><div class="sub">locked for life · 15% standard post-Founding</div></div>
  <div class="stat-card"><div class="num">$0</div><div class="label">Layer 2 cost to Chamber</div><div class="sub">member-benefit platform fully absorbed</div></div>
  <div class="stat-card"><div class="num">10</div><div class="label">Founding slots globally</div><div class="sub">regional exclusivity to first-qualified</div></div>
</div>

<h2>What Members Get</h2>
<ul class="bullets">
  <li>AI-powered SEO + content marketing</li>
  <li>Social media management + scheduling</li>
  <li>Reputation management + review response</li>
  <li>Paid ad strategy + creative</li>
  <li>Lead generation + outbound</li>
  <li>Performance reporting + analytics</li>
</ul>
<p>All delivered under the Chamber's brand. Members experience "my Chamber helped me grow" — not "a vendor my Chamber recommended."</p>

<!-- PAGE BREAK -->
<div style="page-break-before: always;"></div>

<!-- PAGE 2 -->

<h2>How Your Chamber Earns</h2>
<p>Chamber members pay 15% off public retail. Chamber earns rev-share on every active subscription, paid monthly, for life.</p>

<table style="width: 100%; border-collapse: collapse; font-size: 10pt;">
  <thead>
    <tr style="background: #F5F7FA;">
      <th style="padding: 8pt; text-align: left; border-bottom: 1pt solid #CBD5E0;">Plan</th>
      <th style="padding: 8pt; text-align: right; border-bottom: 1pt solid #CBD5E0;">Member rate</th>
      <th style="padding: 8pt; text-align: right; border-bottom: 1pt solid #CBD5E0;">Founding 18%</th>
      <th style="padding: 8pt; text-align: right; border-bottom: 1pt solid #CBD5E0;">Standard 15%</th>
    </tr>
  </thead>
  <tbody>
    <tr><td style="padding: 8pt;">Starter</td><td style="padding: 8pt; text-align: right;">$422/mo</td><td style="padding: 8pt; text-align: right;"><strong>$76/mo</strong></td><td style="padding: 8pt; text-align: right;">$63/mo</td></tr>
    <tr><td style="padding: 8pt;">Growth</td><td style="padding: 8pt; text-align: right;">$677/mo</td><td style="padding: 8pt; text-align: right;"><strong>$122/mo</strong></td><td style="padding: 8pt; text-align: right;">$102/mo</td></tr>
    <tr><td style="padding: 8pt;">Pro</td><td style="padding: 8pt; text-align: right;">$1,272/mo</td><td style="padding: 8pt; text-align: right;"><strong>$229/mo</strong></td><td style="padding: 8pt; text-align: right;">$191/mo</td></tr>
  </tbody>
</table>

<h2>Regional Exclusivity</h2>
<p>Default territory is a 20-mile non-exclusive radius from Chamber HQ. Chambers that want hard regional exclusivity can purchase Exclusive Territory with annual quotas — fully creditable against same-12-month rev-share earnings. Cross-state anti-poaching is contractual across all partners.</p>

<div class="cta-band">
  <strong>Next step:</strong> 30-minute intro call with Solon.<br>
  → <a href="{{BOOK_CALL_URL}}">{{BOOK_CALL_URL}}</a><br>
  <span style="font-size: 10pt;">Or reply to the email that delivered this — Alex will pick up where you left off.</span>
</div>

<p class="muted" style="font-size: 9pt;">Prepared for {{LEAD_NAME}}. All figures reference the Chamber AI Advantage Encyclopedia v1.4.1 (current), and are subject to the Master Services Agreement terms discussed during onboarding. See <a href="https://aimarketinggenius.io/case-studies">aimarketinggenius.io/case-studies</a> for client results across verticals.</p>

</body>
</html>
```

---

## Template 2 — `services-overview.html` (Local biz / ecom persona, 2 pages)

```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>AMG Services Overview</title><style>/* shared CSS */</style></head>
<body>

<div class="cover">
  <div class="eyebrow">AI MARKETING GENIUS</div>
  <h1>Services Overview</h1>
  <div class="subtitle">Prepared for {{LEAD_NAME}}</div>
</div>

<h2>Your Dedicated AI Marketing Team</h2>
<p>Every AMG subscriber gets a team of seven specialist AI agents, coordinated as a single unit, working 24/7.</p>

<div class="tile"><strong>Alex</strong> — Business coach. Strategy, positioning, prioritization.</div>
<div class="tile"><strong>Maya</strong> — Content strategy. Blog, email, social copy.</div>
<div class="tile"><strong>Jordan</strong> — SEO, Google Business Profile, local rankings.</div>
<div class="tile"><strong>Sam</strong> — Social scheduling + engagement.</div>
<div class="tile"><strong>Riley</strong> — Review monitoring + response.</div>
<div class="tile"><strong>Nadia</strong> — Outbound outreach, lead gen.</div>
<div class="tile"><strong>Lumina</strong> — Conversion optimization, landing pages, UX.</div>

<!-- PAGE BREAK -->
<div style="page-break-before: always;"></div>

<h2>Pricing Tiers</h2>

<div class="stat-grid">
  <div class="stat-card"><div class="num">$497/mo</div><div class="label">Starter</div><div class="sub">core AMG retainer</div></div>
  <div class="stat-card"><div class="num">$797/mo</div><div class="label">Growth</div><div class="sub">mid-tier retainer</div></div>
  <div class="stat-card"><div class="num">$1,497/mo</div><div class="label">Pro</div><div class="sub">full-service retainer</div></div>
</div>

<h3>Shield Add-On</h3>
<p>Reputation guardrail available as a standalone at $97/$197/$347 per month tiered by response volume.</p>

<h2>What You Get In Your First 48 Hours</h2>
<ul class="bullets">
  <li>Full business audit + benchmark</li>
  <li>Dedicated AI team provisioned + briefed</li>
  <li>First content + outbound + reputation runs executed</li>
  <li>14-day trial — no credit card required for trial window</li>
</ul>

<h2>Client Results Across Verticals</h2>
<p>See case studies from Shop UNIS (Shopify ecom), Paradise Park Novi (family entertainment), Mike Silverman (home services), Revel & Roll West (bowling), and ClawCADE (amusement) — same AI platform, results in each vertical.</p>

<div class="cta-band">
  <strong>Next step:</strong> 30-minute conversation with Solon or start your 14-day trial.<br>
  → <a href="{{BOOK_CALL_URL}}">Book a call</a> · <a href="https://aimarketinggenius.io/pricing">See pricing</a>
</div>

</body>
</html>
```

---

## Template 3 — `website-strategy-brief.html` (Website buyer persona, 3 pages — NOT "Free Audit Worksheet")

Previous EOM spec called this "Website Audit Worksheet (free)." Per Addendum #6 AM.3 correction (audits are $299-$3500 paid product), we call this the **Website Strategy Brief** and make it a value-forward overview of what AMG builds + CRO fundamentals, ending with CTA to paid CRO audit OR 14-day trial.

```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>AMG Website Strategy Brief</title><style>/* shared CSS */</style></head>
<body>

<div class="cover">
  <div class="eyebrow">AMG WEBSITE STRATEGY</div>
  <h1>Website Strategy Brief</h1>
  <div class="subtitle">Prepared for {{LEAD_NAME}}</div>
</div>

<!-- PAGE 1 -->
<h2>The CRO Fundamentals AMG Ships</h2>
<p>Every AMG-built website is designed to rank, convert, and compound. Our 12-point CRO framework covers:</p>

<ul class="bullets">
  <li>Core Web Vitals (LCP &lt; 2.5s · INP &lt; 200ms · CLS &lt; 0.1)</li>
  <li>Conversion friction audit (form drop-off, CTA clarity)</li>
  <li>Mobile UX + tap target sizing</li>
  <li>Trust signal placement (reviews, credentials, social proof)</li>
  <li>Schema markup + AEO passage optimization</li>
  <li>Heading hierarchy + semantic structure</li>
  <li>Image optimization + lazy loading</li>
  <li>Site architecture + internal linking</li>
  <li>Analytics + goal tracking wiring</li>
  <li>Accessibility AA contrast + keyboard nav</li>
  <li>Page weight budgets</li>
  <li>Conversion copy hierarchy</li>
</ul>

<div style="page-break-before: always;"></div>

<!-- PAGE 2 -->
<h2>How AMG Builds Websites</h2>
<p>Site builds run through the full 7-agent team: Lumina owns CRO + UX, Jordan handles SEO foundations, Maya writes conversion copy, and Alex coordinates positioning. Every site ships with:</p>

<ul class="bullets">
  <li>Mobile-first responsive build</li>
  <li>Schema + OG + canonical + sitemap</li>
  <li>GBP + analytics setup</li>
  <li>Trust + social proof placement</li>
  <li>Contact + lead capture wired to your CRM</li>
  <li>Post-launch 30-day CRO monitoring + iteration</li>
</ul>

<h2>Scoring Your Current Site</h2>
<p>Want a quick snapshot of where your current site stands? Run the AMG Website Score at <a href="https://aimarketinggenius.io/cro-audit-services">aimarketinggenius.io/cro-audit-services</a>.</p>

<p>If you want a deep tiered CRO audit (Option B $299 prompt-fix, Option C $500+ design brief, Option D $1,500–$3,500 Figma mockups, Option E $250–500/page DFY implementation), the full menu is available on that page.</p>

<div style="page-break-before: always;"></div>

<!-- PAGE 3 -->
<h2>What AMG Sites Look Like</h2>
<p>See live examples from AMG clients — [screenshots from case study Social Proof Collages, inserted by Titan from Viktor folder at render time, 3 images max at 300px wide].</p>

<div class="cta-band">
  <strong>Next step:</strong> book a 30-minute call to review your site + goals<br>
  → <a href="{{BOOK_CALL_URL}}">Book a call</a> · or see case studies at <a href="https://aimarketinggenius.io/case-studies">aimarketinggenius.io/case-studies</a>
</div>

</body>
</html>
```

---

## Template 4 — `capabilities-overview.html` (AI consulting / other persona, 2 pages)

Structure mirrors services-overview but reframes for consulting/agency/curious audience — emphasizes AMG's ability to build custom AI systems (Encyclopedia §19) for companies in addition to its channel model. 2 pages.

```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>AMG Capabilities Overview</title><style>/* shared CSS */</style></head>
<body>

<div class="cover">
  <div class="eyebrow">AMG · AI MARKETING GENIUS</div>
  <h1>Capabilities Overview</h1>
  <div class="subtitle">Prepared for {{LEAD_NAME}}</div>
</div>

<h2>What AMG Is</h2>
<p>AMG is a private AI platform for local-business marketing. We run a 7-agent subscription product for local businesses, a white-labeled Chamber of Commerce channel program, and custom AI systems buildouts for companies with specific needs.</p>

<h2>The 7-Agent AMG Stack</h2>
<p>Alex (strategy), Maya (content), Jordan (SEO), Sam (social), Riley (reputation), Nadia (outbound), Lumina (CRO). Backed by proprietary orchestration with 140 concurrent AI workflows across redundant infrastructure.</p>

<h2>Channel Programs</h2>
<p>Chamber AI Advantage is the flagship channel — Chambers of Commerce deliver AMG's services as a Chamber-branded member benefit and earn 18% Founding Partner rev-share (15% standard) on every subscription. See <a href="https://aimarketinggenius.io/chamber-ai-advantage">/chamber-ai-advantage</a>.</p>

<div style="page-break-before: always;"></div>

<h2>Custom AI Systems</h2>
<p>AMG builds custom AI systems for companies with specific needs — orchestration layers, custom agent rosters, integrations, internal tools. Engagements are scoped per project. Hourly customization rates range from $300/hr simple work to $500/hr complex engineering, tiered by complexity with Platinum partner discounts available (Encyclopedia §26).</p>

<h2>Infrastructure</h2>
<p>Production runs on AMG's cloud infrastructure — Triple-Redundant AI Infrastructure with always-on marketing delivery. Specific vendor details disclosed only under MNDA during partnership scoping.</p>

<div class="cta-band">
  <strong>Next step:</strong> 30-minute conversation with Solon to scope fit.<br>
  → <a href="{{BOOK_CALL_URL}}">Book a call</a>
</div>

</body>
</html>
```

---

## Template 5 — `case-studies-summary.html` (Universal 1-pager — ALL personas receive)

```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>AMG Case Studies Summary</title><style>/* shared CSS */</style></head>
<body>

<!-- HEADER (tighter, fits 1 page) -->
<div style="background: linear-gradient(135deg, #131825 0%, #0F172A 100%); color: #FFFFFF; padding: 0.6in 0.6in 0.4in 0.6in; margin: -0.5in -0.6in 16pt -0.6in;">
  <div class="eyebrow" style="color: #00A6FF;">PROOF ACROSS VERTICALS</div>
  <h1 style="color: #FFFFFF; font-size: 26pt; margin-bottom: 4pt;">Case Studies Summary</h1>
  <div style="color: #C5CDD8; font-size: 12pt; font-style: italic;">One AI platform. Real clients. Measurable outcomes. Prepared for {{LEAD_NAME}}.</div>
</div>

<!-- 2x3 grid of 6 tiles — 5 client tiles + CTA tile -->
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10pt; margin: 0;">

  <!-- TILE 1: SHOP UNIS -->
  <div class="tile" style="padding: 10pt;">
    <div style="color: #00A6FF; font-size: 9pt; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;">ECOMMERCE · SHOPIFY</div>
    <div style="color: #131825; font-size: 13pt; font-weight: 700; margin: 3pt 0;">Shop UNIS / Sun-Jammer</div>
    <ul class="bullets" style="padding-left: 14pt; margin: 6pt 0; font-size: 9.5pt;">
      <li>[TITAN pulls 2-3 strongest metrics from SHOP UNIS Case Study v5 in Viktor folder — if unverifiable, omit rather than fabricate]</li>
    </ul>
  </div>

  <!-- TILE 2: PARADISE PARK -->
  <div class="tile" style="padding: 10pt;">
    <div style="color: #00A6FF; font-size: 9pt; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;">FAMILY ENTERTAINMENT CENTER</div>
    <div style="color: #131825; font-size: 13pt; font-weight: 700; margin: 3pt 0;">Paradise Park Novi</div>
    <ul class="bullets" style="padding-left: 14pt; margin: 6pt 0; font-size: 9.5pt;">
      <li>[real metrics from Paradise Park Case Study, Jeff Wainwright CEO]</li>
    </ul>
  </div>

  <!-- TILE 3: MIKE SILVERMAN -->
  <div class="tile" style="padding: 10pt;">
    <div style="color: #00A6FF; font-size: 9pt; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;">HOME SERVICES · WATER DAMAGE</div>
    <div style="color: #131825; font-size: 13pt; font-weight: 700; margin: 3pt 0;">Mike Silverman — Texas</div>
    <ul class="bullets" style="padding-left: 14pt; margin: 6pt 0; font-size: 9.5pt;">
      <li>[real metrics from Mike Silverman Case Study]</li>
    </ul>
  </div>

  <!-- TILE 4: REVEL & ROLL -->
  <div class="tile" style="padding: 10pt;">
    <div style="color: #00A6FF; font-size: 9pt; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;">ENTERTAINMENT · BOWLING</div>
    <div style="color: #131825; font-size: 13pt; font-weight: 700; margin: 3pt 0;">Revel &amp; Roll West</div>
    <ul class="bullets" style="padding-left: 14pt; margin: 6pt 0; font-size: 9.5pt;">
      <li>[real metrics from Revel & Roll Case Study]</li>
    </ul>
  </div>

  <!-- TILE 5: CLAWCADE (buried mid-list per Solon) -->
  <div class="tile" style="padding: 10pt;">
    <div style="color: #00A6FF; font-size: 9pt; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;">AMUSEMENT · ARCADE OPS</div>
    <div style="color: #131825; font-size: 13pt; font-weight: 700; margin: 3pt 0;">ClawCADE</div>
    <ul class="bullets" style="padding-left: 14pt; margin: 6pt 0; font-size: 9.5pt;">
      <li>[real metrics from ClawCADE Case Study PDF]</li>
    </ul>
  </div>

  <!-- TILE 6: CTA -->
  <div class="tile" style="padding: 10pt; background: #10B77F; color: #131825; text-align: center; display: flex; flex-direction: column; justify-content: center;">
    <div style="font-size: 11pt; font-weight: 600; margin-bottom: 6pt;">See all case studies with full metrics + screenshots</div>
    <div style="font-size: 10pt;"><strong><a href="https://aimarketinggenius.io/case-studies" style="color: #131825;">aimarketinggenius.io/case-studies</a></strong></div>
  </div>

</div>

<p class="muted" style="font-size: 8pt; margin-top: 14pt; text-align: center;">All case study metrics reference source documents in AMG's client folder. Prepared for {{LEAD_NAME}}.</p>

</body>
</html>
```

---

## Render pipeline (Titan VPS deployment)

```python
# lib/render_persona_pdf.py — pseudo-code
import weasyprint, jinja2, os, boto3
from datetime import datetime, timedelta

TEMPLATES = {
  'partner_program': '/opt/amg-docs/templates/partner-program.html',
  'services_overview': '/opt/amg-docs/templates/services-overview.html',
  'website_strategy_brief': '/opt/amg-docs/templates/website-strategy-brief.html',
  'capabilities_overview': '/opt/amg-docs/templates/capabilities-overview.html',
  'case_studies_1pager': '/opt/amg-docs/templates/case-studies-summary.html',
}

def render_and_upload(template_key, variables, lead_id):
    tpl_path = TEMPLATES[template_key]
    html = jinja2.Template(open(tpl_path).read()).render(**variables)
    pdf_bytes = weasyprint.HTML(string=html).write_pdf()

    # Upload to R2 at amg-storage/lead-docs/{lead_id}/{template_key}.pdf (NOT amg-lead-docs/)
    s3 = boto3.client('s3', endpoint_url=os.environ['R2_ENDPOINT'], ...)
    key = f"lead-docs/{lead_id}/{template_key}.pdf"
    s3.put_object(Bucket='amg-storage', Key=key, Body=pdf_bytes, ContentType='application/pdf')

    # 48hr signed URL
    url = s3.generate_presigned_url('get_object',
        Params={'Bucket': 'amg-storage', 'Key': key},
        ExpiresIn=48 * 3600)
    return url
```

## Verification gate per PDF

- [ ] File size < 500KB
- [ ] DM Sans font rendered (not Montserrat/default sans)
- [ ] Rev-share is 18%/15% NEVER 35%
- [ ] No banned vendor names in rendered text (grep output)
- [ ] {{LEAD_NAME}} + {{CHAMBER_NAME}} substituted correctly
- [ ] Hero uses #131825 / #00A6FF / #10B77F (no gold)
- [ ] CTAs link to real URLs (not placeholder)
- [ ] For case-studies-summary: real metrics from Viktor folder, zero fabrication

---

**End of templates. SEO|Social|Content project CT-0417-27 commission delivers finished prose to replace placeholder body copy.**
