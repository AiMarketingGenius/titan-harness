# CT-0417-24 — EOM Drift Corrections Log

**Date:** 2026-04-17
**Scope:** Every confirmed EOM drift in the 8 reference docs (Synthesis + Execution Package + Addendums 1–6) that Titan corrects BEFORE executing any Lovable prompt, PDF render, Alex KB load, or email template.
**Authority:** Encyclopedia v1.4.1 + `plans/DOCTRINE_AMG_PRICING_GUARDRAIL.md` + live aimarketinggenius.io (Chrome-extracted tokens at `library_of_alexandria/brand/amg-brand-tokens-v1.md`).
**Status:** all listed corrections APPLIED globally by Titan below. Any EOM doc phrasing on these topics is reference direction only — the values below win.

---

## 1. Rev-share margin (PRICING SOT VIOLATION in EOM docs)

| EOM wrote | Actual (Encyclopedia v1.4.1) |
|---|---|
| "35% lifetime margin" | **15% standard rev-share** / **18% Founding Partner rev-share (first 10 Chambers, locked for life)** |
| "35% on every subscription" | **% of NET COLLECTED subscription revenue** from Chamber-referred members |
| "zero platform cost to Chamber" | **Layer 2 member platform = $0 to Chamber** (correct). Layer 1 website rebuild + Layer 3 Chamber OS are paid — see §2 below. |

**Revere = Founding Partner #1, locked at 18% for life.**

### 1.1 Actual member-rate economics (use these on pages)

Chamber members get 15% off public retail ($497 / $797 / $1,497 per pricing SOT):

| Plan | Public retail | Chamber member rate | Standard rev-share 15% | **Founding rev-share 18%** |
|---|---|---|---|---|
| Starter | $497/mo | $422/mo | $63/mo | **$76/mo** |
| Growth | $797/mo | $677/mo | $102/mo | **$122/mo** |
| Pro | $1,497/mo | $1,272/mo | $191/mo | **$229/mo** |

Global find-replace: `35%` → `18% Founding Partner / 15% standard` (with context). Every page, PDF, Alex prompt, blog.

## 2. Setup fees + three-layer structure

EOM pages largely ignored Layer 1 + Layer 3. Correction:

- **Layer 1 (Chamber website rebuild + AI support):** one-time, 3–4 weeks. Paid by Chamber. Pricing tiered by Chamber size — discussed during onboarding. Includes full platform migration, SEO foundation, AI chatbot on Chamber website, ticketing, staff training, security hardening.
- **Layer 2 (Chamber member subscription):** white-labeled, Chamber earns rev-share per table above. **$0 cost to Chamber.**
- **Layer 3 (Chamber OS / Baby Atlas):** subscription for internal Chamber ops. Modular.

**Founding-10 setup fee on full bundle:** $19,997. Post-founding setup: $29,997.

Any page saying "zero platform cost to the Chamber" without qualifying "Layer 2 is zero-cost; Layers 1 and 3 are Chamber-funded investments" is misleading. Correct copy: "Chambers earn lifetime rev-share on member subscriptions with zero platform cost for the member-benefit layer. The Chamber's own website rebuild + optional Chamber OS are priced separately."

## 3. Brand palette drift (Addendum #5)

EOM wrote "navy + gold + white + Montserrat" across every AMG surface spec. Reality via live-site extraction:

- Base: **#131825** dark navy/midnight
- Accents: **#00A6FF** cyan-blue + **#0080FF** deep blue (gradient) + **#2563EB** alt tile blue
- Primary CTAs: **#10B77F bright green** (NOT gold)
- Text: **#FFFFFF** primary + **#C5CDD8** secondary + **#8796A8** muted
- Font: **DM Sans** (NOT Montserrat)

Full SSOT: `library_of_alexandria/brand/amg-brand-tokens-v1.md`.

Navy + gold remains correct only on Revere-specific materials (already shipped).

## 4. Invented claims stripped (Addendum #6 AM.2)

Removed globally — do NOT place on any AMG-branded surface until Solon or Encyclopedia supports them:

- ❌ "Chambers see elevated member retention after 12 months of adoption"
- ❌ "Chambers that communicate the benefit meaningfully consistently exceed baseline adoption within 6 months"
- ❌ "Chambers with 75+ member businesses typically see the strongest program economics"
- ❌ Adoption percentage bands (40-60% / 25-35% / 10-20% across Starter/Growth/Pro)
- ❌ "Typical Chamber launch timeline: Week 1-2 / 3-4 / 5-8"
- ❌ "12-month performance review clause"
- ❌ "Either party may restructure or exit the agreement without penalty"
- ❌ "No member is ever locked to AMG"
- ❌ "Dedicated Chamber success partner" (verify)

**Replacement pattern** when covering exit/retention: Encyclopedia §13 Legal Framework + §6 Exclusive Territory quota rules govern actual exit language — cite those or omit.

### 4.1 Verified claims Titan DOES write (from Encyclopedia)

- Delivery timeline: Layer 1 = **3–4 weeks** from deposit (§2.1, §9)
- Layer 2 launch: Week 5–6 after Layer 1 delivery
- Founding Partner slots: **10 Chambers globally**, locked 18% rev-share for life
- Setup: $19,997 Founding / $29,997 post-founding
- Chamber courtesy (Revere specific): 50% off everything as Founding Partner + Board-member relationship (Section 15)
- Exit rules: per §13 Legal Framework (Master Services Agreement template — 12-month cure on quota miss in Exclusive Territory specifically, cross-state anti-poaching clause)

## 5. Audit CTA wording

EOM wrote "Get a Free Website Audit →" on 3-persona CTA strip. Doc 26 confirms audits are paid ($299-$3500). Per Solon directive 2026-04-17:

- **Replace with:** "Get Your Website Score →"
- **Link to:** `/cro-audit-services` (existing page, not `/audit`)
- All three personas' website-bound CTAs use this wording.

## 6. R2 bucket path (Addendum #6 AM.5)

- EOM wrote: `amg-lead-docs/` (new bucket)
- Correct: `amg-storage/lead-docs/{lead_id}/{filename}.pdf` (prefix in existing bucket)

All PDF storage + signed URL generation uses the corrected path.

## 7. Trade-secret scrub list (extended per Addendum #6 AM.6)

Full banned list (surfaces everywhere — widget, KB, site copy, emails, PDFs, blogs):

**Tier 1 — AI vendors:**
Claude, Anthropic, GPT, OpenAI, ChatGPT, Gemini, Google AI, Grok, xAI, Perplexity, Mistral, Sonar.

**Tier 2 — Infra / orchestration:**
n8n, Supabase, Stagehand, Pipedream, Zapier, Lovable, GoHighLevel, GHL, Viktor, Cloudflare, R2, Workers, Pages, AWS, Amazon, GCP, Google Cloud, Bedrock, Vertex, Hetzner, HostHatch.

**Tier 3 — Creative / voice:**
Suno, Climbo, ElevenLabs, Deepgram, Whisper, Kokoro, Ollama.

**Replacement framings:**
- AI platform → "AMG's proprietary AI platform"
- Orchestration → "AMG's orchestration layer"
- Cloud → "AMG's cloud infrastructure" / "Triple-Redundant AI Infrastructure"
- Creative → "AMG's creative engine"
- Voice → "AMG's voice platform"

## 8. Verbal-only phrases (never on site)

- ❌ "AMG pays Chamber more than Chamber pays AMG"
- ❌ "We both get rich"
- ❌ Revere-specific dollar amounts on national AMG pages
- ❌ Direct attack lines on named competitors

On-site translation uses Two Boats framework (verbal vendor vs. channel partner logic, diplomatic).

## 9. Hammer Sheet source

- EOM referenced `/home/claude/CHAMBER_AI_ADVANTAGE_HAMMER_SHEET.pdf` (ephemeral Claude-session path, not on our infra).
- Titan regenerates as `library_of_alexandria/chamber-ai-advantage/HAMMER_SHEET_v1.md` from Encyclopedia v1.4.1 content (Two Boats section = §3 channel logic + §6.5 competition policy + §10 ops model + §17 sales pitches) — NO fabrication.

## 10. Calendly link

- EOM placeholder `[CALENDLY_LINK]` had no URL.
- Default decision: Titan creates `/book-call` stub with simple scheduler/mailto form if Solon doesn't provide Calendly URL by first send.

## 11. `/api/email/lead-followup` status

- Titan inventories existing email endpoints on VPS before building net-new. Reuse existing if possible (Resend SMTP wrapper may already exist).

## 12. Typography

- Montserrat → **DM Sans** everywhere (brand tokens §2).
- Widget + PDFs + Lovable prompts all updated.

## 13. aimemoryguard.com restore (Addendum #1 Part M)

**Scope change: NOT NEEDED.** Live state verified via Chrome MCP 2026-04-17T21:45Z — hero intact, annual toggle functional ($0 / $7.99 / $15.99 on click), "Save 20%" badge present, 5 platform logos present, no trade-secret leaks, no fake testimonials. Commit 56dc2a7 Lumina 9.49 state holds in production. Addendum #1 Part M premise of post-hardening regression does NOT match observed state. Surgical fix also not needed.

## 14. EOM prose copy across 8 docs

All prose EOM wrote (verbatim AEO passages, FAQ answers, body paragraphs, email templates, Alex scripts, blog copy) = **reference direction only**. Titan commissions SEO|Social|Content specialist project for final prose, using the outlines + structure + keywords + schema + CTA mapping from the EOM docs (which remain valid) + the corrections in this log.

Verification gate on any EOM-authored prose before ship: if it was quoted verbatim by EOM in a sprint doc, it is NOT ship-ready — route through SEO Content project.

---

**End of log. Every correction above is applied globally. Downstream deliverables (Lovable prompts, PDFs, Alex KB, email templates, blog briefs) reference this file.**
