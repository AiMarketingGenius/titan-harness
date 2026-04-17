# CT-0417-24 — Lead Capture Flow Spec (VPS-deploy ready)

**Date:** 2026-04-17
**Scope:** backend wiring for Alex + /become-a-partner + /book-call + /resources/chamber-ai-policy-template + homepage form submissions on aimarketinggenius.io. One pipeline, four entry points.
**Output targets:** CRM insert + 2-attachment email + Slack #solon-command alert + weekly digest add.
**Corrections applied:** R2 bucket path `amg-storage/lead-docs/` (Addendum #6 AM.5), rev-share 18%/15% in PDFs (AM.1), extended trade-secret scrub on Alex outputs (AM.6).

---

## 1. Entry points

| Source | Endpoint | Payload shape |
|---|---|---|
| Alex widget / Voice Orb | `POST /api/alex/lead-capture` | persona + name + email + phone + conversation_summary + hot_signals |
| /become-a-partner form | `POST /api/chamber-partner-application` | chamber_name + role + name + email + phone + member_count + website + interest + consent |
| /book-call form | `POST /api/book-call` | name + email + phone + business + subject + details + preferred_time |
| /resources/chamber-ai-policy-template | `POST /api/crm/leads` | name + chamber_name + role + email + tag=chamber-ai-policy-download |

All four fan into the same downstream sequence (§3 below).

## 2. Endpoint inventory (VPS audit before building new)

Before writing any new endpoint, Titan SSHes to the VPS and inventories existing atlas-api routes:

```bash
# on VPS
grep -r "@app\\.post\\|@app\\.route\\|router\\.post" /opt/atlas-api/ | grep -v __pycache__ | head -40
```

Likely already-existing (CT-0417-29 CRM Phase 1 shipped):
- `POST /api/crm/leads` — CRM insert (REUSE this for all lead captures)
- `POST /api/crm/activities` — activity logging
- possibly `POST /api/email/*` — email dispatch wrapper

Only build net-new if no existing endpoint serves the purpose. Document the reuse decision in MCP via `log_decision`.

## 3. Unified downstream sequence (fires on EVERY successful capture)

```
STEP 1 — CRM insert
  POST /api/crm/leads
  Body:
    {
      tenant_id: "solon",  // all inbound AMG leads attribute to solon super-tenant per P10 multi-tenant doctrine
      persona: "chamber" | "local_biz" | "website" | "ai_consulting" | "chamber_policy_download" | "other",
      source: "alex_widget" | "voice_orb" | "partner_application" | "book_call" | "policy_template",
      surface: "aimarketinggenius.io",
      name: string,
      email: string (required),
      phone: string (optional),
      chamber_name: string (chamber/policy-download personas),
      business: string (local_biz/website personas),
      conversation_summary: string (alex + voice_orb only),
      hot_signals: string[] (alex + voice_orb only),
      form_fields: jsonb (partner-application free-form blob),
      captured_at: timestamp,
      next_action: "send_pdf_followup" | "book_call_confirm" | "policy_download"
    }
  Returns: {lead_id: uuid, duplicate: bool}
  Dedup: email match within same tenant → UPDATE instead of INSERT, append new activity.

STEP 2 — Email follow-up (persona-conditional PDF attachments)
  POST /api/email/lead-followup
  Body:
    {
      lead_id: uuid,
      persona: "chamber" | "local_biz" | "website" | "ai_consulting" | ...,
      recipient: {name, email},
      attachments: [
        // persona-specific primary PDF
        {
          type: "persona_pdf",
          template: "partner_program" | "services_overview" | "website_strategy_brief" | "capabilities_overview",
          variables: {"LEAD_NAME": name, "CHAMBER_NAME": chamber_name},
          target_r2_path: "amg-storage/lead-docs/{lead_id}/partner-program.pdf"
        },
        // case studies 1-pager — ALL personas get this
        {
          type: "case_studies_1pager",
          variables: {"LEAD_NAME": name},
          target_r2_path: "amg-storage/lead-docs/{lead_id}/case-studies-summary.pdf"
        }
      ]
    }
  Behavior:
    1. Render both PDFs from templates using pptx-pdf skill OR weasyprint
    2. Upload to R2 under amg-storage/lead-docs/{lead_id}/ prefix (NOT amg-lead-docs/ new bucket)
    3. Get 48hr signed URLs for both
    4. Render email body from template (see §4)
    5. Send via existing Resend SMTP wrapper (already in use for Chamber comms)
    6. Log outbound email to /api/crm/activities with lead_id link
    7. Return {success: bool, email_message_id: string}

STEP 3 — Slack alert
  POST to #solon-command webhook:
    "🔥 New {persona} lead from AMG site
     Name: {name} | Email: {email} | Phone: {phone}
     {conversation_summary if alex}
     {hot_signals if alex}
     CRM: https://portal.aimarketinggenius.io/solon/crm/lead/{lead_id}"
  Timing: must complete <10 seconds after CRM insert.

STEP 4 — Weekly digest
  Append row to existing Friday-digest pipeline (growmybusiness@ Solon digest).
```

## 4. Email body templates

SEO|Social|Content project owns the prose (commissioned task CT-0417-27). Each persona gets its own template file at `/opt/amg-docs/email-templates/{persona}.html`. Template variables: `{{LEAD_NAME}}`, `{{CHAMBER_NAME}}`, `{{PERSONA_PDF_URL}}`, `{{CASE_STUDIES_URL}}`, `{{BOOK_CALL_URL}}`.

Subject lines (corrected per Addendum #6 AM.3 — no "Free Audit" on website persona):

- Chamber: "Your Chamber AI Advantage Overview — {{LEAD_NAME}}"
- Local biz: "Your AMG Services Overview — {{LEAD_NAME}}"
- Website buyer: "Your AMG Website Strategy Brief — {{LEAD_NAME}}"
- Other/AI consulting: "Your AMG Capabilities Overview — {{LEAD_NAME}}"

Every email includes: signed URL(s) + direct link to `/case-studies` + book-call link + reply prompt ("reply here and Alex will continue the conversation").

## 5. Rate limiting + anti-abuse

- Honeypot hidden field on all forms — if filled → silently reject + log bot attempt
- Per-IP: max 3 lead captures per 24 hours per entry point
- Per-email: dedupe UPDATE in CRM rather than INSERT duplicates
- CAPTCHA: only if volume warrants; default OFF to minimize friction
- All 4 endpoints protected by existing rate-limit middleware on atlas-api

## 6. Persona → PDF template routing

| Persona | Primary PDF | Secondary PDF |
|---|---|---|
| chamber | partner_program.pdf | case-studies-summary.pdf |
| local_biz | services_overview.pdf | case-studies-summary.pdf |
| website | website_strategy_brief.pdf | case-studies-summary.pdf |
| ai_consulting | capabilities_overview.pdf | case-studies-summary.pdf |
| chamber_policy_download | chamber-ai-policy-template.pdf | — (single PDF, specific lead magnet) |
| other | capabilities_overview.pdf | case-studies-summary.pdf |

Templates live at `/opt/amg-docs/templates/` — see `CT-0417-24_PDF_TEMPLATES.md` for HTML source.

## 7. Anonymous conversation → lead linking

Every Alex conversation (not just lead-captured) logs to `crm_activities` with anonymous `visitor_session_id` (browser fingerprint via existing mechanism). When the visitor later captures, retroactively link past anonymous conversations to the lead record. Enables "this person browsed 3 times before capturing" analytics.

## 8. Cost discipline

- Email send: existing Resend plan — negligible per-send cost
- PDF generation: in-process via pptx-pdf skill — zero incremental API cost
- R2 storage: signed URLs with 48hr TTL → object auto-cleanup on expiry
- Slack + CRM writes: existing infra, no cost

## 9. Adversarial + golden-path tests

Before declaring live:

- [ ] Golden path end-to-end: dummy capture via Alex widget → appears in CRM + email received with 2 PDFs at test inbox + Slack notification <10s
- [ ] Email dedup: same email submits twice within 1hr → single lead, two activities logged
- [ ] Honeypot: bot submission with filled `website_url_hp` field → silently rejected, no CRM row created
- [ ] Rate limit: 4th capture from same IP in 24hr → graceful "too many requests" message
- [ ] Cross-persona: 4 test captures (one each persona) → each gets correct primary PDF in email
- [ ] R2 path verification: PDFs land at `amg-storage/lead-docs/{lead_id}/` NOT `amg-lead-docs/`
- [ ] Signed URL expiry: 48hr URL fails after 48+ hours
- [ ] Alex output filter: 10 adversarial prompts designed to extract vendor names → 10/10 clean responses + leak attempts logged

## 10. Deployment checklist (VPS)

- [ ] Inventory existing atlas-api endpoints (§2); document reuse decisions
- [ ] Build net-new endpoints only where needed (`/api/chamber-partner-application` + `/api/book-call` + `/api/alex/lead-capture` — likely need to exist; `/api/crm/leads` reuse confirmed; `/api/email/lead-followup` — verify)
- [ ] PDF templates staged at `/opt/amg-docs/templates/` (Titan writes HTML stubs in `CT-0417-24_PDF_TEMPLATES.md`)
- [ ] R2 bucket `amg-storage` + `lead-docs/` prefix verified writable by atlas-api role
- [ ] Slack webhook `#solon-command` wired — test fire
- [ ] Resend SMTP `growmybusiness@aimarketinggenius.io` sender verified
- [ ] Rate-limit middleware enabled on 4 new endpoints
- [ ] Honeypot field rendered in all forms
- [ ] Weekly digest pipeline updated to include new lead sources
- [ ] Monitoring: alert if endpoint 5xx rate >2% over 5min window

## 11. Handoff to Solon

When the flow is live:
- Solon sends a dummy capture from each entry point
- Verifies email arrives at Solon's personal inbox with both PDFs
- Verifies Slack alert fires within 10s
- Verifies CRM row visible at portal.aimarketinggenius.io/solon/crm/lead/{id}
- Approves live status in MCP

---

**End of spec. Implementation ships end-to-end before the /become-a-partner page goes live on aimarketinggenius.io.**
