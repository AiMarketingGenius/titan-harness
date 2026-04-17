# CHAMBER SEO EXECUTION PACKAGE — ADDENDUM #6
**Date:** 2026-04-17 (END OF NIGHT — HONEST AUDIT + GOVERNANCE RESET)
**Parent docs:** Synthesis + Execution Package + Addendum #1-#5 + Titan Boot Prompt
**Scope:** Full audit of errors EOM introduced across prior 6 docs + role reset: EOM gives directives/keywords/outlines only. Writing goes to SEO | Social | Content specialist project. Titan builds.

**SEVERITY:** 🔴 CRITICAL — several errors below are pricing SOT violations or invented promises that could create legal/contractual exposure. Fix before Titan executes.

---

## PART AM — HONEST AUDIT OF EOM ERRORS

### 🔴 CRITICAL (must fix before Titan executes)

**AM.1 — Rev-share margin number is WRONG across all 6 docs**

- I wrote **"35% lifetime margin"** everywhere — `/chamber-ai-advantage`, `/become-a-partner`, homepage Chamber band, Partner Program PDF, Alex system prompt, blog #2, hammer weave inserts.
- **ACTUAL canonical number per MCP + user memories + Revere founding terms:** **18% Founding Partner rev-share / 15% standard**
- Source of EOM drift: Solon's Perplexity research brief PROMPT said "35%" as aspirational framing. MCP decisions + hammer sheet + Revere proposal all say **18% founding vs. 15% standard**.
- **PRICING SOT VIOLATION.** Hard rule #8 broken.

**Fix required:** Every "35%" instance across all 6 docs becomes "18% Founding Partner / 15% standard" OR "18% lifetime margin for Founding Partners." Page copy + PDFs + Alex system prompt + blog copy all get corrected before ship.

---

**AM.2 — Invented claims / unsourced promises**

I wrote statements as fact that have no source:

| Claim I wrote | Problem | Fix |
|---|---|---|
| "Chambers using the AI Advantage program see elevated member retention after 12 months of adoption" | No evidence — we have zero long-term Chamber data | Remove entirely, or caveat as "we expect" |
| "Typical Chamber launch timeline: Week 1-2 onboarding, Week 3-4 member config, Week 5-8 ramp" | Fabricated cadence | Remove or replace with "Chamber-specific timeline discussed during onboarding" |
| "Chambers that communicate the benefit meaningfully to members consistently exceed baseline adoption within 6 months" | No baseline, no data | Remove |
| "Chambers with 75+ member businesses typically see the strongest program economics" | Arbitrary threshold | Remove or replace with "We'll assess your Chamber's fit during the intro call" |
| "Typical member count at mature adoption: 40-60%" (Starter) / "25-35%" (Growth) / "10-20%" (Pro) in /become-a-partner tier table | Fabricated adoption curves | Remove the percentage bands; keep tier structure only |
| "12-month performance review clause" | Is this actually in the Chamber contract? Need legal verification | Either confirm with Solon + contract template OR remove |
| "Either party may restructure or exit the agreement without penalty" | Legal claim — verify against Encyclopedia §13 Legal Framework | Verify or remove |
| "No member is ever 'locked' to AMG" | Contract claim | Verify or soften |

**Fix required:** Titan strips or verifies every one of these before page ships. When in doubt, remove.

---

**AM.3 — "Free Website Audit" CTA is misleading**

Per Doc 26 Pricing Rate Card, website audits are a PAID product:
- Option B (fix prompts): $299
- Option C (design brief): +$500
- Option D (Figma mockup): $1,500-$3,500
- Option E (DFY implementation): $250-$500/page

I wrote "Get a Free Website Audit →" on the homepage 3-persona CTA strip. That's bait-and-switch territory.

**Fix required:** CTA wording options (pick one):
- "Get Your Website Score →" (lighter, not a promise)
- "See Your Conversion Report →" (describes what they get without free-claim)
- "Book a Website Strategy Call →" (pivots to a call, no "free audit" promise)
- "Get a 5-Minute Site Assessment →" (Lumina-delivered preview, genuine free tier)

Solon picks. Default if silent: "Get Your Website Score →"

---

**AM.4 — Brand palette drift (already corrected via Addendum #5)**

Navy + gold was Revere, not AMG. Addendum #5 handles. Listed here for completeness of audit.

---

### 🟡 IMPORTANT (should fix before ship)

**AM.5 — R2 bucket name wrong**

I specified `amg-lead-docs/` as the R2 bucket for PDF storage. Per user memories, the actual R2 bucket is `amg-storage`. Lead docs should live under a prefix: `amg-storage/lead-docs/` not a separate bucket.

**Fix:** Titan uses `amg-storage/lead-docs/{lead_id}/{filename}.pdf` instead of new bucket.

---

**AM.6 — Trade-secret scrub list missing vendor names**

My Addendum #3 Part T.2 + Addendum #4 scrub list missed: **AWS, GCP, Bedrock, Vertex, Cloudflare, R2, Hetzner, HostHatch.**

Per user memories: "All vendor names (AWS, GCP, Bedrock, Vertex) stay internal — 'Triple-Redundant AI Infrastructure' / 'Always-On Marketing' are the client-facing framings."

**Fix:** Extend scrub list to include AWS / GCP / Bedrock / Vertex / Cloudflare / R2 / Hetzner / HostHatch / Amazon / Google Cloud. Replace with "AMG's cloud infrastructure" or "Triple-Redundant AI Infrastructure."

---

**AM.7 — Hammer sheet source path unclear**

I referenced `/home/claude/CHAMBER_AI_ADVANTAGE_HAMMER_SHEET.pdf` as the KB source. That's an ephemeral Claude-session path from earlier today's build thread — not persistent on Solon's infrastructure.

**Fix:** Titan pulls the source .md version (not PDF) from `library_of_alexandria/chamber-ai-advantage/` OR from MCP-linked artifact. If source .md doesn't exist, Titan regenerates the hammer sheet content from the verbal-pitch briefing docs and the Encyclopedia before sanitization pass.

---

**AM.8 — Calendly link referenced but no URL given**

Email templates in Addendum #3 Part V + Addendum #4 Part AD say "Solon's Calendly link" / "[CALENDLY_LINK]" placeholder. No actual URL.

**Fix:** Solon provides his Calendly URL OR Titan creates a Cal.com-style calendar page at `aimarketinggenius.io/book-call` that routes bookings to Solon. Default if silent: Titan creates `/book-call` with a simple scheduler or email-to-book form.

---

**AM.9 — `/api/email/lead-followup` endpoint status unclear**

I specified this as "Titan builds" but didn't confirm it doesn't already exist. If an existing email-send endpoint serves the same purpose, reuse. Otherwise Titan builds.

**Fix:** Titan inventories existing email endpoints on VPS before building net-new. Reuse if possible.

---

### 🟢 OPTIMIZE (not pitch-blocking)

**AM.10 — "Montserrat" typography speculation**

Addendum #5 already flags — Titan extracts actual font from live site.

**AM.11 — Blog URL slugs**

I picked slugs like `/blog/chamber-declining-membership-ai-fix`. SEO | Social | Content project reviews for keyword alignment + slug length.

**AM.12 — Alex's "Solon will reach out within 4 hours to confirm"**

Promise of human response time. May not always hold. Softer: "Solon or a team member will reach out soon."

**AM.13 — ClawCADE spelling**

I used "ClawCADE." Solon wrote "CLawCade" once (likely typo). Source doc in Drive has "ClawCADE Case Study.pdf." Stick with "ClawCADE" — matches source.

**AM.14 — "Chamber AI Advantage is the first national program"**

Grok research confirmed no Tier-1 competitor. Safe claim, but phrase as "the first AI-marketing-specific Chamber channel partner program" rather than "first national program" for defensibility.

---

## PART AN — GOVERNANCE RESET (Solon's correct critique)

### AN.1 — EOM's actual role

EOM is an **Operations Manager**, not a writer.

**EOM produces:**
- Keywords + search intent
- Structural outlines (H1 / H2 / H3)
- AEO target queries + passage placement rules
- Schema specs
- Internal link targets
- CTA destinations + button text directives
- Word count targets
- Success metrics
- Trade-secret rules
- Brand-token references (via live-site extraction)
- Verification gates

**EOM does NOT produce:**
- Full prose copy
- Verbatim AEO passages
- Complete FAQ answers
- Email body copy
- Alex's conversational scripts
- Blog prose

### AN.2 — SEO | Social | Content specialist project produces

All prose copy that lives on AMG-branded surfaces:
- Page copy on `/chamber-ai-advantage`, `/become-a-partner`, `/case-studies`, homepage edits
- AEO passages (first 150 words of each page)
- FAQ answers
- Blog prose (all 5 pillars, full 1,500-2,800 words each)
- PDF copy (all 4 persona PDFs + Case Studies 1-pager)
- Email body templates
- Alex's conversational greetings + example responses
- Any meta descriptions, titles, alt text

SEO | Social | Content project is equipped with AMG brand voice, keyword strategy, and SEO best practices. That's its lane.

### AN.3 — Titan's role

- Extracts brand tokens from live site (per Addendum #5)
- Executes atomic Lovable prompts for page builds
- Commissions SEO | Social | Content project for each copy deliverable via `queue_operator_task`
- Swaps placeholder copy → SEO Content output in Lovable once approved
- Renders PDFs
- Wires CRM/email/Slack integrations
- Runs verification gates
- Reports to Solon

### AN.4 — What to do with the prose copy I already wrote

**Treat everything I wrote as DRAFT SUGGESTIONS, not final copy.**

Specifically:
- The AEO passages I wrote verbatim in the Execution Package Part C, D + blog briefs E → hand to SEO Content as *reference direction* + target keywords. SEO Content rewrites in AMG voice with proper keyword density.
- The FAQ answers I wrote → same. Reference direction, SEO Content rewrites.
- The Alex system prompt conversational scripts → same.
- The email body templates → same.
- The Two Boats framework + month-6 Board paragraph + new FAQs in Addendum #1 Part J → same.
- The PDF body copy in Addendum #3 Part V + Addendum #4 Part AC → same.

Everything structural — H1s, section orders, keyword assignments, schema specs, internal link maps, CTA destinations, form fields, verification gates — **stays valid**. That's EOM's lane.

---

## PART AO — CORRECTIONS TITAN MUST APPLY

Before executing any Lovable prompt or rendering any PDF, Titan applies these global corrections to prior doc content:

### AO.1 — Global find-and-replace

| Find | Replace | Scope |
|---|---|---|
| "35% lifetime margin" / "35% margin" / "35%" in Chamber context | "18% Founding Partner / 15% standard lifetime margin" | All 6 docs, every surface |
| "Navy + gold" / "navy + gold + white + Montserrat" (for AMG surfaces) | "AMG live-site brand tokens per Addendum #5" | All 6 docs (Addendum #5 handles) |
| "Get a Free Website Audit →" | "Get Your Website Score →" (or Solon's chosen alternative) | Homepage 3-persona CTA strip |
| "amg-lead-docs/" R2 bucket | "amg-storage/lead-docs/" prefix | Addendum #3 + #4 |
| "/home/claude/CHAMBER_AI_ADVANTAGE_HAMMER_SHEET.pdf" | Source .md from library_of_alexandria/chamber-ai-advantage/ OR regenerate | Addendum #3 + #4 Alex KB sources |

### AO.2 — Removals (stripped before any surface ships)

Strip these invented claims entirely:
- "elevated member retention after 12 months of adoption"
- "Chambers that communicate the benefit meaningfully... consistently exceed baseline adoption within 6 months"
- "Chambers with 75+ member businesses typically see the strongest program economics"
- Adoption percentage bands in /become-a-partner tier table (40-60% / 25-35% / 10-20%)
- "Typical Chamber launch timeline: Week 1-2... Week 3-4... Week 5-8" (OR verify with Solon's actual onboarding SOP)

### AO.3 — Verifications (ask Solon OR remove)

Before surfacing, Titan checks with Solon via `#solon-command`:
- "12-month performance review clause" — in our actual contract template?
- "Either party may restructure or exit the agreement without penalty" — confirmed?
- "No member is ever locked to AMG" — confirmed?
- "Dedicated Chamber success partner" — is this a defined role?

If Solon confirms → keep. If silent after 2 hours → remove/soften.

### AO.4 — Extended trade-secret scrub list

Addendum #3 Part T.2 scrub list EXTENDS to include:
- AWS / Amazon / Amazon Web Services
- GCP / Google Cloud / Google Cloud Platform
- Bedrock / Vertex / Vertex AI
- Cloudflare / R2 / Workers / Pages
- Hetzner / HostHatch
- Any raw cloud infrastructure vendor name

Replacement framings: "AMG's cloud infrastructure" / "Triple-Redundant AI Infrastructure" / "Always-On Marketing platform."

---

## PART AP — REVISED SEO | SOCIAL | CONTENT PROJECT DELIVERABLES

Titan queues these tasks to the SEO | Social | Content specialist project (one sub-task per deliverable, each tagged with `chamber-seo-sprint` + `weekend-2026-04-18`):

| # | Deliverable | Reference in prior docs | Word count |
|---|---|---|---|
| 1 | `/chamber-ai-advantage` full page copy | Execution Package Part C outline + Addendum #1 Part J inserts | 1,800-2,400 |
| 2 | `/become-a-partner` full page copy | Execution Package Part D outline | 1,200-1,600 |
| 3 | `/case-studies` index page copy | Addendum #1 Part K.4 outline | 600-900 |
| 4 | 5 individual `/case-studies/[slug]` pages copy | Addendum #1 Part K.5 template | 800-1,200 each |
| 5 | 5 pillar blog posts full prose | Execution Package Part E briefs | 1,500-2,800 each |
| 6 | Homepage copy edits (Chamber band + hero sentence + 3-persona cards + Client Results row) | Addendum #1 Part B + Addendum #2 Part Q + Addendum #1 Part K.6 | 200-400 total |
| 7 | 4 persona PDFs body copy (Partner Program + Services + Audit Worksheet + Case Studies 1-pager) | Addendum #3 Part V + Addendum #4 Part AC | 400-800 per PDF |
| 8 | Alex system prompt conversational scripts | Addendum #3 Part U structural outline | 600-900 system prompt |
| 9 | Lead capture email body templates (4 personas) | Addendum #3 Part V.4 + Addendum #4 Part AD.3 | 150-250 each |
| 10 | aimemoryguard.com restoration copy verification | Addendum #1 Part M | N/A (verify not rewrite) |

SEO | Social | Content project receives: EOM outlines + keywords + schema + CTA targets + trade-secret scrub list + AMG brand voice guide + corrected 18%/15% margin + extracted brand tokens. Returns: finished prose, dual-engine validated, Lumina-approved.

Titan ships via Lovable atomic prompts after SEO Content delivers each piece.

---

## PART AQ — UPDATED TITAN DISPATCH

Replaces the "When in doubt" closing section of the Titan Boot Prompt:

```
WHEN IN DOUBT:
- EOM gives outlines + keywords + structure. SEO | Social | Content project writes prose. 
  YOU build.
- If EOM doc contains prose copy — treat as reference direction only. Commission SEO 
  Content for final.
- Smaller is better — ship 10 perfect things over 20 half-done things
- Brevity mandatory per Solon standing rule
- Brand tokens from live site, NEVER guess (Addendum #5)
- Rev-share margin is 18% Founding / 15% standard, NEVER 35% (Addendum #6)
- Strip invented claims before ship (Addendum #6 Part AO.2)
- Verify with Solon on contract-language claims before publishing (Addendum #6 Part AO.3)
- Extended trade-secret scrub includes AWS/GCP/Bedrock/Vertex/Cloudflare/R2/Hetzner 
  (Addendum #6 Part AO.4)
```

Insert as Step 0.75 (between Step 0.5 brand token extraction and Step 1 Technical SEO):

```
STEP 0.75 — COPY SOURCE ROUTING (MANDATORY)

All prose copy for AMG-branded surfaces routes to the SEO | Social | Content 
specialist project via queue_operator_task. EOM-written copy in prior docs is 
reference direction, not final copy. Commission SEO Content project for:
- Page copy (all 3 Chamber pages + /case-studies + homepage edits)
- 5 pillar blog posts full prose
- 4 persona PDFs body copy
- Alex system prompt conversational scripts
- Lead capture email body templates

Each commission includes: EOM outline + keywords + AEO target queries + schema + 
CTA destinations + trade-secret scrub list + brand tokens + corrected rev-share 
(18%/15%) + Addendum #6 Part AO corrections.

Titan builds Lovable pages with placeholder copy first. Swaps in SEO Content 
output once delivered + Lumina ≥9.3 approved.
```

---

## PART AR — VERIFICATION GATE ADDITIONS

Add to all verification gates:

- [ ] **18% Founding Partner / 15% standard** appears everywhere — zero "35%" remaining
- [ ] **All invented claims stripped** (AM.2 list reviewed and removed/verified)
- [ ] **"Free Audit" CTA replaced** with approved alternative
- [ ] **R2 bucket path corrected** to `amg-storage/lead-docs/`
- [ ] **Extended trade-secret scrub verified** — no AWS/GCP/Bedrock/Vertex/Cloudflare/R2/Hetzner on surfaces
- [ ] **Prose copy came from SEO Content project**, not EOM — commission tickets logged in MCP
- [ ] **Contract-claim language verified** with Solon (performance review clause, exit without penalty, no lock-in)
- [ ] **Calendly link real** or `/book-call` page stub live

Dual-engine reviews add: "Does this page contain any invented statistics or unsourced promises?" — if yes, score drops below 9.3.

---

**End of Addendum #6. This one's a governance correction + honest audit. Weekend canon: 8 reference files + Titan Boot Prompt. Addendum #6 has supersession authority on pricing/claims/copy-governance questions. EOM reset to Ops Manager lane.**

Writing copy is not my job. Directing the writers is. Burned.
