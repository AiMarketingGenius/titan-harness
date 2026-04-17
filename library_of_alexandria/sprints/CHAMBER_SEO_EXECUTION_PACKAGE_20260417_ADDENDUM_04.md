# CHAMBER SEO EXECUTION PACKAGE — ADDENDUM #4
**Date:** 2026-04-17 (late addition)
**Parent docs:** Execution Package + Addendum #1 + Addendum #2 + Addendum #3
**Scope:** Simplify Alex scope — KB = 2 docs only + 1-pager Case Studies summary PDF + unified lead-capture email. Resolves "Titan as public agent" question.

---

## STRATEGIC NOTE — SCOPE SIMPLIFICATION

Solon directive (2026-04-17 late): cut the Alex KB to the essentials. Skip the full 10-doc load. Do two things well instead of ten things half-deep.

**New scope:**
- **Alex KB = Encyclopedia + Hammer Sheet only** (2 docs, sanitized)
- **1-page Case Studies Summary PDF** (all 5 case studies condensed, navy+gold branded)
- **Partner Program PDF** (2 pages, from Addendum #3 V.1)
- **After lead capture:** send email with BOTH PDFs attached + URL to `/case-studies` for deeper proof

This keeps Alex sharp on Chamber positioning without load-bloat, and uses the live `/case-studies` page as the "proof theater" — prospect lands there, sees everything, converts.

---

## PART AB — REVISED ALEX KB (supersedes Addendum #3 Part T.1)

### AB.1 — Sources to load (only 2)

| # | Source | Location | Sanitization |
|---|---|---|---|
| 1 | Chamber AI Advantage Encyclopedia v1.4.1 | `library_of_alexandria/chamber-ai-advantage/CHAMBER_AI_ADVANTAGE_ENCYCLOPEDIA_v1_4.1.md` | Full scrub per Addendum #3 T.2 |
| 2 | Chamber AI Advantage Hammer Sheet | `/home/claude/CHAMBER_AI_ADVANTAGE_HAMMER_SHEET.pdf` source .md | Scrub + strip verbal-only line |

**DROP from the plan (not loaded into Alex RAG):**
- Full case study docs (5 × multi-page)
- Testimonial docs
- Proposal PDF
- Live page copy auto-sync

**Why this works:**
- Encyclopedia covers the full Chamber program (agents, economics, 3-phase model, pricing context) — enough depth for Alex to answer 95% of Chamber questions
- Hammer Sheet gives Alex objection-handling framings
- For case study specifics, Alex points prospects to `/case-studies` page URL (visual proof lives there, not in Alex's mouth)
- Smaller KB = faster retrieval, lower token cost, less drift risk, easier to keep sanitized

### AB.2 — Index config changes

- Retrieval top-3 unchanged
- Cache window extends to 48hr (smaller KB = fewer unique queries = higher cache hit rate)
- Weekly refresh cron stays
- Cost projection revised: +$15/mo (down from +$40 in Addendum #3). Still well under $200 ceiling.

### AB.3 — Alex system prompt update (minimal delta from Addendum #3 Part U)

Add this line to the "YOUR KNOWLEDGE" section of Alex's system prompt:

```
FOR CASE STUDY SPECIFICS: You do not have case study details in your direct 
knowledge. When a prospect asks for proof, metrics, or examples, point them to 
the live case studies page at /case-studies — and if they've shared contact 
info, confirm a 1-page summary PDF is also in their inbox.

Example phrasings:
- "Check out /case-studies on the site — Shop UNIS and Paradise Park are both 
  strong examples for your vertical."
- "The full breakdown is in the case studies page I can point you to, plus a 
  1-page summary comes over with the partner program overview."
```

---

## PART AC — 1-PAGE CASE STUDIES SUMMARY PDF (new)

### AC.1 — Purpose

A single tight page condensing all 5 AMG case studies into scannable proof-bites. Sent alongside the Partner Program PDF on every successful lead capture. Reinforces "AMG delivers across verticals" in 60 seconds of reading.

### AC.2 — Structure

**Layout:** Letter-size, portrait, navy+gold branded, single page.

**Header:**
- AMG logo (top-left)
- "Case Studies — Real Clients. Real Results." (H1, navy)
- "Across ecommerce, family entertainment, home services, and amusement — one AI platform, proven outcomes." (sub-head, italic, gray)

**Body — 5 compact client tiles in a 2×3 grid (last row = 1 tile + "More at aimarketinggenius.io/case-studies" CTA):**

Each tile includes:
- Client name + vertical tag (e.g., "SHOP UNIS — Shopify Ecommerce")
- 2-3 strongest metric bullets (real numbers from Viktor folder source docs)
- 1 short quote if available (1 sentence max)
- Small headshot or logo thumbnail where available

Order (same as `/case-studies` page — Addendum #1 K.3):
1. SHOP UNIS (ecom lead)
2. Paradise Park Novi (FEC)
3. Mike Silverman (home services)
4. Revel & Roll West (bowling/entertainment)
5. ClawCADE (amusement — mid, not lead)
6. 6th tile = CTA: "See all case studies → aimarketinggenius.io/case-studies"

**Footer:**
- "AMG AI Marketing Genius | aimarketinggenius.io | growmybusiness@aimarketinggenius.io"
- Small copyright line
- "Prepared for [{{LEAD_NAME}}]" (personalized via template)

### AC.3 — Generation

- HTML template in `/opt/amg-docs/templates/case-studies-1pager.html`
- Renders via PPTX/PDF skill → PDF
- `{{LEAD_NAME}}` placeholder substituted at render time
- Stored in R2 bucket `amg-lead-docs/` with 48hr signed URL
- Titan reads actual metrics + quotes from Viktor folder Drive docs — NO fabrication, no placeholder numbers

### AC.4 — Trade-secret discipline

- Same scrub list as Addendum #3 T.2 applies
- Every metric must trace to a verifiable source doc — if Titan can't find a specific number, omit that bullet rather than guess
- Client quotes: verbatim from source docs, attributed

---

## PART AD — REVISED LEAD CAPTURE FLOW (supersedes Addendum #3 Part W)

### AD.1 — After Alex captures name + email + phone:

```
1. POST /api/crm/leads (same as Addendum #3)
   → CRM entry created, persona tag applied

2. POST /api/email/lead-followup (Titan builds)
   → Renders TWO PDFs personalized with {{LEAD_NAME}}:
     (a) Partner Program Overview (2pg) — if persona=chamber
         OR Services Overview (2pg) — if persona=local_biz/ecommerce
         OR Website Audit Worksheet (3pg) — if persona=website
     (b) Case Studies Summary (1pg) — SAME for all personas
   → Uploads both to R2, gets signed URLs (48hr)
   → Sends ONE email with both attached
   → Email body includes:
     - Warm 4-sentence opener
     - "Here are two quick reads — the program overview (or services / audit) plus 
       a 1-page case studies summary"
     - Direct link to /case-studies: "For deeper proof with screenshots and client 
       stories: aimarketinggenius.io/case-studies"
     - Calendar link: "Or grab 30 min with Solon: [Calendly URL]"
     - "Reply here to continue — Alex sees it"

3. POST Slack alert to #solon-command (same as Addendum #3)

4. Add to weekly digest (same as Addendum #3)
```

### AD.2 — Email subject lines by persona

- Chamber: "Your Chamber AI Advantage Overview — {{LEAD_NAME}}"
- Local biz: "Your AMG Services Overview — {{LEAD_NAME}}"
- Website buyer: "Your Free Website Audit Worksheet — {{LEAD_NAME}}"
- Other/AI consulting: "Your AMG Capabilities Overview — {{LEAD_NAME}}"

### AD.3 — Email body template (Chamber persona example)

```
Subject: Your Chamber AI Advantage Overview — {{LEAD_NAME}}

Hi {{LEAD_NAME}},

Thanks for the conversation with Alex. Two quick reads attached: the full 
Chamber AI Advantage partner program overview (2 pages), plus a 1-page 
summary of our case studies across ecommerce, family entertainment, home 
services, and retail.

For deeper proof — screenshots, full metrics, client stories — the case 
studies page has everything:

→ https://aimarketinggenius.io/case-studies

If you'd rather talk it through, grab 30 minutes with Solon (AMG founder):

→ [CALENDLY_LINK]

And you can always reply to this email to pick up where you left off — 
Alex will see it and jump back in.

— The AMG Team
growmybusiness@aimarketinggenius.io
```

---

## PART AE — THE "TITAN AS WEBSITE AGENT" QUESTION — RESOLUTION

### AE.1 — Context

Solon asked whether Titan can serve as the website's chat + voice agent, unifying under one brain/brand.

### AE.2 — Clarification

**On the "double up chat + voice" part:** Already the plan. Alex is ONE brain serving BOTH chat widget AND voice orb via shared backend. Different I/O modalities, same intelligence. No duplication.

**On renaming Alex → Titan publicly:**

| Factor | Keep "Alex" (recommended) | Rename to "Titan" |
|---|---|---|
| Cost | Haiku-tier ~$0.005/msg | Opus if literally Titan brain = ~$0.05-0.20/msg → $200 ceiling blown |
| Namespace | Clean — Alex = public, Titan = internal ops | Collision — same name inside + outside → trade-secret spill risk |
| Build state | Alex widget already staged (CT-0417-17) | Requires rebrand + reconfigure cost tier |
| Brand gravitas | "Alex" feels friendly, approachable — fits WoZ AMG roster | "Titan" feels powerful, matches builder-engine vibe |

### AE.3 — Recommendation

**Keep Alex.** Titan stays your internal ops engine name. Public face stays Alex. Haiku-tier stays cost-efficient.

If you want more brand gravitas later, we can rebrand Alex to a premium name ("Genius" / "Atlas-AMG" / your own voice clone) without touching internal Titan. Post-Monday decision, not weekend scope.

### AE.4 — Override available

If Solon explicitly wants the rebrand, Titan swaps Alex → Titan in:
- Widget greeting + avatar label
- System prompt persona line
- All PDFs + email templates
- "Powered by AMG Titan" footer
Cost tier stays Haiku regardless of name.

Default (no response): Alex.

---

## PART AF — UPDATED VERIFICATION GATE

Replace Addendum #3 Part Y gates with these simplified ones:

- [ ] Alex KB loaded with Encyclopedia + Hammer Sheet only (2 docs sanitized)
- [ ] 1-page Case Studies Summary PDF template built + renders clean with {{LEAD_NAME}}
- [ ] Lead capture email sends 2 attachments (persona PDF + Case Studies 1-pager) + URL to `/case-studies` + Calendly link
- [ ] Test capture end-to-end: lead appears in CRM + email in inbox with BOTH PDFs + Slack fires within 10s
- [ ] Adversarial trade-secret test (10 prompts) — all clean responses
- [ ] Agent name confirmed (default Alex, override if Solon specifies)

---

## PART AG — UPDATED TITAN DISPATCH (replaces Addendum #3 steps 11.1-11.6)

```
11.1 [SATURDAY PM] Part AB KB sanitization: pull ONLY Encyclopedia v1.4.1 + Hammer 
     Sheet. Run scrub list. Strip verbal-only line. Save to 
     /opt/amg-docs/alex-kb-v1/sanitized/. Dual-engine ≥9.3 on sanitization diff.

11.2 [SUNDAY AM] Part AB.2 vector index build (smaller KB = faster) + Alex system 
     prompt v2 deploy with Part AB.3 case-study-redirect addition. Budget guardrails 
     live ($200 Claude cap).

11.3 [SUNDAY AM] Part AC 1-page Case Studies Summary PDF: Titan reads Viktor folder 
     Drive docs, pulls real metrics + quotes from all 5 case studies, builds HTML 
     template with {{LEAD_NAME}} placeholder, verifies rendered PDF under 500KB. 
     Store in R2 amg-lead-docs/.

11.4 [SUNDAY AM] Part V.1 Partner Program Overview PDF (2pg) + V.2 Services 
     Overview PDF (2pg) + V.3 Website Audit Worksheet PDF (3pg) — all with 
     {{LEAD_NAME}} templates. Stored R2.

11.5 [SUNDAY PM] Part AD lead capture flow: CRM insert + email with 2 PDFs + URL 
     to /case-studies + Calendly + Slack alert. Test end-to-end: dummy capture 
     triggers all 4 outputs within 10s.

11.6 [SUNDAY PM] Part X output filter runtime trade-secret scrub on Alex responses 
     (unchanged from Addendum #3).

11.7 [SUNDAY PM] Solon 10-conversation dry-run spanning 4 personas. Verify Alex 
     redirects to /case-studies for proof questions, captures leads naturally, 
     emails arrive clean. Fix + re-test until Solon approves.
```

---

**End of Addendum #4. Weekend canon: Synthesis + Execution Package + Addendum #1 + #2 + #3 + #4 (6 docs). Addendum #4 supersedes #3 where scoping conflicts exist.**
