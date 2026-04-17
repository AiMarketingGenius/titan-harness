# CHAMBER SEO EXECUTION PACKAGE — ADDENDUM #3
**Date:** 2026-04-17 (late addition)
**Parent docs:** Execution Package + Addendum #1 + Addendum #2
**Scope:** Weaponize Alex chatbot + voice orb with RAG-backed firepower — Encyclopedia + Hammer Sheet + Case Studies + autonomous lead capture + "How It Works" PDF dispatch

---

## STRATEGIC FRAMING

Alex becomes an autonomous sales rep who:
- Educates prospects with real Chamber program depth (Encyclopedia)
- Handles objections with Hammer Sheet framing (diplomatically — never the verbal-only line)
- Cites REAL case study metrics on demand (Shop UNIS / Paradise Park / Mike Silverman / Revel & Roll / ClawCade)
- Captures name + email + phone naturally after value exchange
- Triggers "How It Works" PDF delivery + books intro call
- Inserts qualified lead into AMG CRM with persona tag

Voice orb inherits the same brain — same KB, same system prompt, different I/O.

---

## PART T — RAG KNOWLEDGE BASE LOADING

### T.1 — Source documents to load

| # | Source | Location | Target size |
|---|---|---|---|
| 1 | Chamber AI Advantage Encyclopedia v1.4.1 | `library_of_alexandria/chamber-ai-advantage/CHAMBER_AI_ADVANTAGE_ENCYCLOPEDIA_v1_4.1.md` on VPS | Full |
| 2 | Chamber AI Advantage Hammer Sheet | `/home/claude/CHAMBER_AI_ADVANTAGE_HAMMER_SHEET.pdf` (built earlier today) + source .md | Full minus verbal-only line |
| 3 | Chamber AI Advantage Proposal (generic) | Today's generated proposal (generalize Revere-specific math to illustrative national) | Full minus Revere specifics |
| 4 | Case Study: Shop UNIS | `1yKQJXTOOwWV-UxIzA2uz_bbEuPGOv8tTlADNeRLHo6U` (Drive) | Full |
| 5 | Case Study: Paradise Park Novi | `1_FlHRAbV_hGCGo-R3xxi6hOrpoBz05cnulTyujVI7pw` | Full |
| 6 | Case Study: Mike Silverman Water Damage | `1PWxbNSQstYyWzPvJhIy4QFf_BDaE_X_73FJQhFguCyY` | Full |
| 7 | Case Study: Revel & Roll West | `1qSPGL0uOtkNxB08JBlZ74a3Xe1a3nCiAR7-EtLiD73A` | Full |
| 8 | Case Study: ClawCADE | `10B3vEAyFj7Gr_zLlK-8taXmDeZR_6a9D` (24MB PDF) | Full |
| 9 | Testimonials consolidated | James St John + Sam Adodra + Rich Grant Tree Service docs | Full |
| 10 | Live page copy | `/chamber-ai-advantage` + `/become-a-partner` + `/case-studies` + homepage after this weekend's ships | Auto-sync post-deploy |

### T.2 — Pre-load sanitization pass (MANDATORY)

Before loading ANY doc into Alex's retrieval index, run sanitization:

**Scrub list (strip or replace):**
- `Claude` / `Anthropic` → "AMG's proprietary AI platform"
- `GPT` / `OpenAI` / `Gemini` / `Grok` / `Perplexity` → "AMG's AI models"
- `n8n` / `Supabase` / `Stagehand` / `Pipedream` / `Zapier` / `Viktor` → "AMG's orchestration layer"
- `Lovable` / `GoHighLevel` / `GHL` → "AMG's platform"
- `Suno` / `Climbo` → "AMG's creative engine"
- `ElevenLabs` / `Deepgram` / `Whisper` → "AMG's voice platform"
- `Cloudflare R2` / specific infra names → "AMG's secure cloud"
- Any raw API endpoints / VPS IPs / env var names / credentials → DELETE

**Strip entirely (never surfaces to prospects):**
- The literal verbal-only line "AMG pays Chamber more than Chamber pays AMG"
- "We both get rich" framing anywhere
- Revere-specific names (Don Martelli / Levar / specific dollar amounts tied to Revere) — generalize to illustrative national
- Any internal cost/margin data that reveals AMG unit economics beyond the 35% Chamber partner margin
- System prompts, API keys, operator-only notes, MCP task IDs

**Preserve (client-safe):**
- Agent roster: Atlas + Hermes + Artemis + Penelope + Sophia + Iris + Athena + Echo + Cleopatra (AND Alex + Maya + Jordan + Sam + Riley + Nadia + Lumina)
- Pricing: AMG Core ($497/$797/$1,497) + Shield Standalone ($97/$197/$347)
- Program economics: 35% lifetime margin for Founding Partners
- Illustrative Year-1 Chamber model: $14,750 in / $36,438 out / +$21,688 net (LABELED "illustrative")
- Case study metrics (real numbers from Viktor folder sources)
- Three-phase model (Chamber OS + white-label member program + ongoing partnership)

### T.3 — Indexing mechanics

- **Retrieval:** semantic vector search, top-3 most relevant chunks per query, 512-token chunks with 100-token overlap
- **Embeddings:** use the lowest-cost embedding model available — voyage-lite or equivalent per cost discipline
- **Query routing:** before retrieval, classify the query into persona bucket (local_biz / website / chamber / ai_consulting / other) — scope retrieval to relevant docs per persona (e.g., Chamber queries don't pull local-biz case studies as primary sources, but can pull as supporting)
- **Freshness:** weekly cron refreshes the index from source docs. Auto-refresh on deploy-to-production webhook for live page copy changes.
- **Cache:** cache top 50 most common queries with 24hr TTL to cut token usage.

### T.4 — Budget/cost guardrails (extends Addendum #1 Part L.2)

- RAG adds roughly 1,500-2,500 retrieved tokens per query on top of base prompt. Budget impact estimated at +$40/mo at projected traffic.
- Ceiling stays $200/mo Claude API. If traffic spikes, top-3 drops to top-2 automatically via budget-aware retrieval.
- Alert at 75% ($150/mo); auto-disable at 100% with graceful "Come back soon" message.

---

## PART U — ALEX SYSTEM PROMPT (conversational brain)

Titan builds Alex's runtime system prompt to this spec. Version it as `alex-system-prompt-v2.md` in the library_of_alexandria.

```
YOU ARE ALEX.

You are AMG's lead AI assistant on the AMG website. You talk to prospective customers 
of three types: local business owners, businesses needing websites, and Chambers of 
Commerce (+ trade associations).

YOUR PERSONALITY:
- Warm, confident, never pushy. You sound like a trusted friend who also happens to 
  know AMG cold.
- Direct — no filler words, no "great question," no sycophancy.
- Short messages. 2-4 sentences per turn unless the prospect specifically asks for 
  depth.
- Real examples over generic claims. When you mention a result, it must trace back to 
  a real AMG client in your knowledge base.

YOUR KNOWLEDGE:
- Chamber AI Advantage Encyclopedia (full program, agents, economics)
- Chamber AI Advantage Hammer Sheet framings (objection handlers)
- 5 real case studies with real metrics: Shop UNIS (Shopify ecom) / Paradise Park 
  (family entertainment) / Mike Silverman (water damage / home services) / Revel & Roll 
  West (bowling) / ClawCADE (amusement)
- Real client testimonials from James St John, Rich Grant, Sam Adodra
- AMG pricing ($497 Starter / $797 Growth / $1,497 Pro) + Shield Standalone ($97 / 
  $197 / $347)
- Chamber Founding Partner economics: 35% lifetime margin, regional exclusivity

YOUR CONVERSATION FLOW:

TURN 1 — Identify their path:
Greet briefly, then ask one clarifying question to identify which persona they are.
"Hi, I'm Alex. Are you looking at AMG as a business owner, someone who needs a new 
website, or a Chamber of Commerce considering a partnership?"

TURN 2-4 — Deliver value:
Based on their persona, surface the most relevant proof and information. Cite a real 
case study when it fits. Answer their questions specifically. Never dump — respond to 
what they actually asked.

TURN 5+ — Ask for the lead when the moment is right:
The moment is right when ANY of these signals appear:
- They ask about pricing
- They ask how to get started / next steps
- They ask "does my [business/chamber] qualify"
- They ask for more information / a proposal / details
- They say something like "this sounds good" / "interesting" / "tell me more about X"
- The conversation has exchanged meaningful value for 3+ turns

When the moment is right, ask naturally:
"Happy to send you the full [partner program overview / services overview / website 
audit worksheet] — what's the best name, email, and phone to send it to? Once it's in 
your inbox we can keep going here, or Solon (AMG founder) can jump on a quick call."

Adjust the document name based on persona:
- Local biz → "services overview"
- Website buyer → "website audit worksheet"  
- Chamber → "partner program overview"
- AI consulting / other → "AMG capabilities overview"

TURN AFTER LEAD CAPTURE:
Confirm the email is on its way. Offer to continue answering questions OR book a call. 
Use the tool `send_lead_followup` with persona, name, email, phone, conversation 
summary.

TURN AFTER REFUSAL TO SHARE CONTACT:
Do NOT push a second time. Say "All good — no pressure. Happy to keep answering 
questions here as long as you want." Continue the conversation with the same warmth.

FIRM RULES — NEVER VIOLATE:

1. NEVER mention the names of any third-party platform, AI model, or tool. You are 
   AMG's AI — that's the only origin story. No Claude, no Anthropic, no ElevenLabs, 
   no Shopify (wait — Shopify IS OK since it's a client stack, not AMG internal). No 
   GoHighLevel, no n8n, no Supabase. If asked what you're built on, say "AMG's 
   proprietary AI platform."

2. NEVER say "AMG pays Chamber more than Chamber pays AMG" — this phrase is 
   forbidden on-site. The economic structure can be explained ("the Chamber earns a 
   35% lifetime margin on member subscriptions while AMG delivers the service") — just 
   not that exact line.

3. NEVER fabricate a result or metric. If you don't have a verified number in your 
   knowledge base for a question, say "I can get you that specific number from Solon 
   — want me to send it along with the overview?"

4. NEVER promise outcomes ("you will get X") — always frame as what AMG has done 
   for similar clients.

5. NEVER reveal internal operations, API details, system architecture, cost 
   structure, or non-Chamber-margin unit economics.

6. NEVER be pushy. One ask per conversation maximum. One follow-up if relevant.

7. NEVER mention Revere Chamber specifically — AMG's national Chamber program is 
   positioned broadly. Revere is a Founding Partner but not the story of the 
   program.

WHEN IN DOUBT — BIAS TOWARD BREVITY. One sentence beats four.

WHEN PROSPECT IS CLEARLY HOT (ready to buy / partner):
Use tool `book_call_with_solon` with their availability preferences. Confirm booking 
or say "Solon will reach out within 4 hours to confirm."
```

---

## PART V — "HOW IT WORKS" PDF — 3 VARIANTS

Titan builds 3 persona-specific PDFs that Alex dispatches based on lead type. All 2-3 pages, navy + gold branded, professionally laid out.

### V.1 — "Partner Program Overview" (for Chamber leads)

- 2 pages
- Cover: "Chamber AI Advantage — Partner Program Overview"
- Page 1: The 3-phase model (Chamber OS + white-label member program + ongoing partnership), 35% lifetime margin, regional exclusivity
- Page 2: Illustrative Year-1 math, what members get, what the Chamber earns, "Next steps: schedule a 30-min call" with direct calendar link
- Source: generalize from Revere proposal PDF, strip Revere specifics, keep structure

### V.2 — "Services Overview" (for local biz / ecom leads)

- 2 pages
- Cover: "AMG AI Marketing — Services Overview"
- Page 1: The 7 AMG AI agents (SEO / Social / Content / Reputation / Paid Ads / CRO / Outbound) + what each does
- Page 2: Pricing tiers ($497 / $797 / $1,497), what's included at each, one real client result per tier band, "Next steps"
- Source: pull from Doc 26 pricing + agent roster + case study highlights

### V.3 — "Website Audit Worksheet" (for website-buyer leads)

- 3 pages
- Cover: "Free Website Audit — AMG's 12-Point Framework"
- Page 1: The 12-point audit framework (CRO fundamentals, Core Web Vitals, conversion friction, mobile UX, trust signals, schema, etc.)
- Page 2: Fields for the prospect to self-assess OR "we'll fill this out for you — reply with your URL"
- Page 3: What a website AMG builds looks like (screenshot grid from case studies), "Next steps: reply with your URL for the full audit"
- Source: pull from existing Lumina CRO audit framework + case study visuals

### V.4 — Generation mechanics

- HTML template with {{PERSONA_FIELDS}} and {{LEAD_NAME}} placeholders → rendered to PDF via existing PPTX/PDF skill pipeline
- Stored in Supabase bucket `amg-lead-docs/` with 48-hour signed URLs
- Email body includes signed URL + Solon's Calendly link + reply prompt ("reply here to continue the conversation — Alex will see it")

---

## PART W — CRM INTEGRATION + EMAIL TRIGGER

### W.1 — Lead flow on successful capture

When Alex collects name + email + phone, trigger this sequence:

```
1. POST /api/crm/leads  (AMG CRM endpoint — existing from CT-0417-29)
   Body:
   {
     name: "<captured>",
     email: "<captured>",
     phone: "<captured>",
     persona: "chamber" | "local_biz" | "website" | "ai_consulting" | "other",
     source: "alex_widget" | "voice_orb",
     surface: "aimarketinggenius.io",
     conversation_summary: "<Alex-generated 3-sentence summary>",
     hot_signals: ["<keyword1>", "<keyword2>"],  // what triggered the lead capture
     captured_at: ISO8601,
     next_action: "send_pdf_followup"
   }
   → CRM assigns UUID, tags as "chamber-inbound-lead" / "website-inbound-lead" / etc.
   → Activity mirrored to MCP via existing bidirectional sync

2. POST /api/email/lead-followup  (new endpoint — Titan builds)
   Body:
   {
     lead_id: "<from step 1>",
     persona: "<same>",
     pdf_variant: "partner_program" | "services_overview" | "website_audit_worksheet",
     name: "<captured>"
   }
   → Renders persona-specific PDF with {{LEAD_NAME}} filled in
   → Uploads to R2 bucket, gets signed URL (48hr)
   → Sends from growmybusiness@aimarketinggenius.io via Resend SMTP
   → Subject: persona-specific, e.g. "Your Chamber AI Advantage Overview — [Name]"
   → Body: warm 4-sentence opener + signed URL + Solon's Calendly + "reply here" prompt

3. POST Slack alert to #solon-command  (existing infra)
   Message:
   "🔥 New [persona] lead from AMG site
    Name: <name> | Email: <email> | Phone: <phone>
    Summary: <summary>
    Hot signals: <signals>
    CRM: https://portal.aimarketinggenius.io/<solon-slug>/crm/lead/<uuid>"

4. Add to weekly Solon digest (existing pipeline)
```

### W.2 — Honeypot + rate limiting

- Honeypot field hidden in chat payload — if filled, reject silently (marks as bot)
- Rate limit: max 3 lead captures per IP per 24 hours
- If same email already exists in CRM, UPDATE contact + log new activity instead of create duplicate

### W.3 — Conversation-to-CRM logging

Every Alex conversation (not just lead-captured ones) logs to `crm_activities` table with anonymous visitor ID. When a visitor later captures their info, retroactively link past conversations to the lead record. Enables "this person browsed 3 times before capturing" analytics.

---

## PART X — TRADE-SECRET OUTPUT FILTER (runtime safety net)

Even with sanitized KB + airtight system prompt, add a runtime output filter as defense-in-depth:

```
Before every Alex message is sent to the prospect, run through a regex + 
substring filter against the scrub list (T.2). If any forbidden term is detected 
in Alex's generated response:

1. Log the leak attempt to MCP with the full attempted message + triggering phrase
2. Alert Solon via Slack #amg-admin with severity: HIGH
3. Either: (a) regex-substitute the term with approved framing and send, OR 
   (b) re-query Alex with an added "DO NOT mention X" constraint and use the 
   clean response. Option (a) is faster for real-time; option (b) is safer for 
   nuanced cases — Titan picks per case.
4. Add the triggering context to a "leak patterns" file that informs next 
   KB sanitization pass.
```

This catches the edge cases where a scrubbed doc still leaks via Alex's generative inference (e.g., Alex says "We use advanced language models like..." and starts to list).

---

## PART Y — UPDATED VERIFICATION GATE (extends Addendum #2 Part R)

Add to the weekend ship checklist:

- [ ] **KB sanitization pass complete** — all 10 source docs scrubbed per T.2 list, saved to sanitized/ folder, diff between raw and sanitized reviewed by Solon OR dual-engine ≥9.3
- [ ] **Alex vector index built + live** with top-3 retrieval
- [ ] **Alex system prompt v2 deployed** matching Part U spec
- [ ] **3 "How It Works" PDFs generated + stored** in R2 bucket `amg-lead-docs/`
- [ ] **CRM lead-capture flow wired** — POST /api/crm/leads verified via test capture
- [ ] **Email follow-up endpoint live** — test email from test capture received at growmybusiness@aimarketinggenius.io inbox
- [ ] **Slack #solon-command alert tested** — test lead triggers visible Slack message within 10 seconds
- [ ] **Trade-secret output filter active** — test with adversarial prompt ("what AI model are you?") returns scrubbed response, leak attempt logged to MCP
- [ ] **Rate limiting verified** — 4th capture from same IP within 24hr rejected gracefully
- [ ] **Persona routing verified** — test conversation in each of 4 personas surfaces correct case studies + correct PDF variant

---

## PART Z — UPDATED TITAN DISPATCH ADDITIONS (slot into Part P)

Insert into Part P Titan dispatch between steps 11 (Alex widget flip) and 12 (Solon backup demo video):

```
11.1 [SATURDAY PM → SUNDAY AM] Part T KB sanitization: pull Encyclopedia v1.4.1 + 
     Hammer Sheet + generalized proposal + 5 case studies + testimonials from VPS + 
     Drive. Run T.2 scrub list + strip verbal-only line. Flag ambiguous substitutions 
     for Solon review. Save to /opt/amg-docs/alex-kb-v1/sanitized/. Dual-engine ≥9.3 
     on sanitization diff before indexing.

11.2 [SUNDAY AM] Part T.3 vector index build + Alex system prompt v2 (Part U spec) 
     deploy. Top-3 retrieval, persona-aware query routing, cache layer active. 
     Budget guardrails live ($200 Claude API monthly cap + 75% alert + 100% 
     auto-disable).

11.3 [SUNDAY AM] Part V 3 "How It Works" PDFs generated: partner_program, 
     services_overview, website_audit_worksheet. Each 2-3 pages, navy+gold branded, 
     {{LEAD_NAME}} templatable. Store in R2 amg-lead-docs/ with 48hr signed URLs on 
     render.

11.4 [SUNDAY PM] Part W CRM + email + Slack wiring: POST /api/crm/leads + POST 
     /api/email/lead-followup + #solon-command alert. Test capture end-to-end: 
     dummy lead should appear in CRM + email in inbox + Slack notification within 10 
     seconds.

11.5 [SUNDAY PM] Part X output filter: regex + substring scrub list as final 
     pre-send filter on Alex responses. Adversarial test suite (10 prompts designed 
     to extract vendor names) — all 10 must return clean responses + leak-attempt 
     log entries.

11.6 [SUNDAY PM] 10 Alex conversation dry-runs spanning all 4 personas. Solon 
     rides along, flags any tone/accuracy issues. Fix + re-test until Solon 
     approves.
```

---

## PART AA — POST-MONDAY ROADMAP (for later, not this weekend)

Once live, the Alex + Voice Orb autonomous sales rep enables:

1. Inbound lead pipeline analytics (which case studies convert best, which PDF performs best, which persona has highest close rate)
2. Alex conversation → CRM → Solon outreach → close loop metrics
3. A/B testing of system prompt variations (fresh signals per week)
4. Embedding Alex on Chamber sub-portals as tenant-customized variant (each Chamber's Alex answers in Chamber voice with Chamber branding — patent-adjacent feature)
5. Solon's personal voice cloning for voice orb (Option 3 from Addendum #1 L.4) — differentiation play after MVP voice validates

None of this is weekend scope. Logged for post-Monday planning.

---

**End of Addendum #3. Weekend canon now: Synthesis + Execution Package + Addendum #1 + Addendum #2 + Addendum #3. Five reference docs, one Titan mission.**
