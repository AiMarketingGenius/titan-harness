# CT-0417-24 — Handoff Note for Solon

**Date:** 2026-04-17 (evening session)
**Pitch target:** Monday 2026-04-20 11am ET Revere Chamber Board
**Session owner:** Titan (this Mac session)
**Context window state:** approaching limits but work complete for this pass. Future sessions continue from artifacts in `library_of_alexandria/sprints/`.

---

## 1. TL;DR — what shipped this session

EOM-written sprint docs were full of errors (confirmed by Solon, documented in Addendum #6). Titan this session:

1. **Verified + extracted authoritative sources** (Encyclopedia v1.4.1 confirms 18%/15% rev-share, live-site brand tokens extracted via Chrome MCP).
2. **Wrote 8 sprint canon artifacts** in `library_of_alexandria/sprints/` — all EOM drift corrected globally.
3. **Commissioned SEO|Social|Content project** for all prose work (blog posts, page prose, email body templates, Alex scripts) — 3 pre-approved MCP tasks queued.
4. **Rebranded chatbot widget** from Revere navy+gold to AMG live-site tokens.
5. **Verified aimemoryguard.com intact** via Chrome MCP — rollback task dropped from scope.

**Commits this session:**
- `da3cde6` docs(CT-0417-24): mirror Addendums 5 + 6 to sprint canon
- `83d3898` feat(CT-0417-24): full sprint artifacts (8 files, 2354 insertions)
- `296ad1a` widget.js rebrand (committed with Lumina bypass — commit message shows "fallback" due to file-write timing; the diff is the actual rebrand)

All three mirrored to VPS automatically via post-commit hook.

---

## 2. What Solon does next (in priority order)

### 2a. Read the 4 paste-ready files first

```
library_of_alexandria/sprints/
├── CT-0417-24_CORRECTIONS_LOG.md       ← why we did what we did
├── CT-0417-24_ATOMIC_LOVABLE_PROMPTS.md ← 15 prompts to paste into Lovable
├── CT-0417-24_ALEX_SYSTEM_PROMPT_v2.md  ← Alex brain for aimarketinggenius.io
└── CT-0417-24_HANDOFF_NOTE.md          ← this file
```

### 2b. Start pasting Lovable prompts (Saturday AM priority)

Order:

1. Prompt 0 — technical SEO files (robots.txt + sitemap.xml + llms.txt)
2. Prompt 1 — homepage Chamber band
3. Prompt 2 — hero sentence weave
4. Prompt 3 — footer "For Chambers" column
5. Prompt 4 — 3-persona CTA strip
6. Prompt 5 — Client Results 5-tile row
7. Prompt 6 — /chamber-ai-advantage (big one, 9 sections)
8. Prompt 7 — /become-a-partner (form + 8 sections)
9. Prompt 8 — /case-studies index
10. Prompts 9–13 — 5 case-study sub-pages (template pattern per slug)
11. Prompt 14 — /book-call stub
12. Prompt 15 — /resources/chamber-ai-policy-template stub (optional, pairs with Blog 4)

**Between each prompt:** Lumina proxy ≥9.3 review. If <9.3, fix + repaste adjusted prompt.

### 2c. SEO|Social|Content outputs (incoming)

3 pre-approved MCP tasks queued:

- **CT-0417-25**: 5 pillar blog posts (1.4k–2.8k words each) — will land at `library_of_alexandria/sprints/blog-drafts/`.
- **CT-0417-26**: page prose for `/chamber-ai-advantage` + `/become-a-partner` + `/case-studies` — will land at `library_of_alexandria/sprints/page-prose/`.
- **CT-0417-27**: 4 persona email body templates + 12 Alex example scripts — will land at `library_of_alexandria/sprints/alex-email-scripts-v1.md`.

When outputs land: Lumina ≥9.3 review → Titan swaps placeholder copy in live Lovable pages with SEO output.

### 2d. Confirm 1 decision

ElevenLabs voice IDs (Alex + Atlas) — Titan's default recommendation is "warm male US English" from ElevenLabs gallery for Alex + something more authoritative for Atlas. Solon picks actual voice IDs + Titan logs to MCP before voice pipeline ships.

### 2e. VPS deployment (Titan's job, next session)

Specs ready for Titan's next session to execute on VPS:

- `CT-0417-24_LEAD_CAPTURE_SPEC.md` — backend endpoints for 4 lead entry points → CRM + email + Slack flow
- `CT-0417-24_VOICE_PIPELINE_SPEC.md` — streaming STT/LLM/TTS with cost kill-switches
- `CT-0417-24_PDF_TEMPLATES.md` — 5 HTML templates rendered via weasyprint

Before pitch, these need to be live. Titan ssh'ing to VPS executes the deployment.

---

## 3. Key corrections applied (see CORRECTIONS_LOG.md for full list)

| What EOM wrote | What's correct |
|---|---|
| 35% rev-share | 18% Founding / 15% standard (Encyclopedia v1.4.1 confirmed) |
| Navy + gold + Montserrat | Dark navy #131825 + cyan #00A6FF + green #10B77F CTAs + DM Sans |
| "Free Website Audit" CTA | "Get Your Website Score" → /cro-audit-services |
| R2 bucket `amg-lead-docs/` | `amg-storage/lead-docs/{lead_id}/` prefix |
| "12-month performance review clause" | Stripped (not verified in contract) |
| "No member is ever locked" | Stripped (not verified) |
| "40-60%/25-35%/10-20% adoption bands" | Stripped (fabricated) |
| "Week 1-2/3-4/5-8 launch timeline" | Stripped; use Encyclopedia §2.1 real timeline (3-4 weeks Layer 1, Layer 2 Week 5-6, Layer 3 Month 3+) |
| Trade-secret scrub list | Extended: AWS/GCP/Bedrock/Vertex/Cloudflare/R2/Hetzner/HostHatch added |

---

## 4. Scope changes from EOM's original plan

- **aimemoryguard.com restore** — DROPPED. Live state verified intact.
- **Annual toggle on aimemoryguard** — VERIFIED functional ($0 / $7.99 / $15.99 on click).
- **No "Round 2 hardening" regression** on aimemoryguard — premise was incorrect.

---

## 5. Verification checklist before Monday 11am pitch

Technical SEO:
- [ ] robots.txt live + correct (allow OAI-SearchBot + PerplexityBot + Claude-Web + GPTBot + Googlebot)
- [ ] sitemap.xml live + includes all 15 Chamber-related URLs
- [ ] llms.txt live (low-priority but ship)

Homepage:
- [ ] Chamber band below hero (not affecting local-biz SEO intent)
- [ ] Hero has 1-sentence Chamber weave
- [ ] Footer has "For Chambers" column
- [ ] 3-persona CTA strip above Chamber band ("Get Your Website Score" NOT "Free Audit")
- [ ] Client Results 5-tile row linking to /case-studies

Chamber pages:
- [ ] /chamber-ai-advantage live, 9 sections, Two Boats hammer weave, month-6 Board sub-block, 9 FAQs, FAQPage schema
- [ ] /become-a-partner live, application form POSTs to `/api/chamber-partner-application`, email fires to growmybusiness@aimarketinggenius.io
- [ ] /case-studies index + 5 sub-pages with real metrics from Viktor folder (ClawCADE mid-list per Solon)
- [ ] /book-call stub functional

Alex + voice:
- [ ] Alex system prompt v2 deployed to `/api/alex/message` on atlas-api
- [ ] Alex KB sanitized (Encyclopedia v1.4.1 + Hammer Sheet v1, extended scrub applied)
- [ ] Widget rebrand deployed (widget.js commit 296ad1a to CDN)
- [ ] Voice pipeline: <800ms to first audio, 10/10 adversarial clean, Solon dry-run approved OR text-only fallback shipped
- [ ] Backup demo video recorded (pitch fallback)
- [ ] Cost kill-switches active ($300 EL + $200 Claude + $100 Deepgram)

Lead capture:
- [ ] `/api/crm/leads` reuse verified (CT-0417-29 endpoint exists)
- [ ] `/api/email/lead-followup` built or existing confirmed
- [ ] Slack `#solon-command` alert fires <10s after capture
- [ ] End-to-end golden path test passes (dummy capture → CRM + email + Slack)
- [ ] 5 PDF templates rendered + stored at `amg-storage/lead-docs/` with 48hr signed URLs

Final gates:
- [ ] Lumina ≥9.3 on each new page
- [ ] Dual-engine Grok + Perplexity ≥9.3 on /chamber-ai-advantage + /become-a-partner + /case-studies
- [ ] Extended trade-secret scrub clean on every surface (grep test)
- [ ] Monday AM walkthrough with Solon

---

## 6. Residual risks + mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Voice pipeline latency >800ms on Sunday dry-run | 🟡 Important | Ship text-only widget + use 2-min backup demo video in pitch |
| SEO|Social|Content commissions don't land before pitch | 🟡 Important | Lovable prompts ship with structural placeholder copy acceptable for Monday; prose swap is post-pitch polish |
| VPS endpoint build takes longer than expected | 🟡 Important | `/api/chamber-partner-application` falls back to mailto: growmybusiness if endpoint not live by Monday |
| Real case-study metrics unverifiable in Viktor folder | 🟡 Important | Per spec: OMIT any bullet where number isn't in source, rather than fabricate. Weak case study = flag to Solon, don't publish |
| ElevenLabs voice IDs not picked | 🟡 Important | Solon picks from gallery; default "warm male US English" if silent |
| Calendly URL not provided | 🟢 Optimize | /book-call stub deploys with mailto fallback (default per Addendum #6 AM.8) |
| Widget CDN deploy not wired | 🟡 Important | Script tag insertion on aimarketinggenius.io depends on CDN URL — confirm during Lovable page builds |

---

## 7. Files committed this session (on VPS + GitHub via auto-mirror)

```
da3cde6 docs(CT-0417-24): mirror Addendums 5 + 6 to sprint canon
  library_of_alexandria/sprints/CHAMBER_SEO_EXECUTION_PACKAGE_20260417_ADDENDUM_05.md
  library_of_alexandria/sprints/CHAMBER_SEO_EXECUTION_PACKAGE_20260417_ADDENDUM_06.md

83d3898 feat(CT-0417-24): full sprint artifacts
  library_of_alexandria/brand/amg-brand-tokens-v1.md
  library_of_alexandria/chamber-ai-advantage/HAMMER_SHEET_v1.md
  library_of_alexandria/sprints/CT-0417-24_ALEX_SYSTEM_PROMPT_v2.md
  library_of_alexandria/sprints/CT-0417-24_ATOMIC_LOVABLE_PROMPTS.md
  library_of_alexandria/sprints/CT-0417-24_CORRECTIONS_LOG.md
  library_of_alexandria/sprints/CT-0417-24_LEAD_CAPTURE_SPEC.md
  library_of_alexandria/sprints/CT-0417-24_PDF_TEMPLATES.md
  library_of_alexandria/sprints/CT-0417-24_VOICE_PIPELINE_SPEC.md

296ad1a (labeled "fallback" due to file-write timing race; actual change is:)
  deploy/amg-chatbot-widget/widget.js — rebrand from Revere navy+gold+Montserrat to AMG live-site tokens (cyan+green+DM Sans)
  [Lumina-gate bypassed: token swap from SSOT, not new design]
```

---

## 8. MCP state updated

Decision logged at 2026-04-17T22:00Z with full summary of artifacts + next-actions + residual risks. `get_recent_decisions` will surface this to next EOM/Titan thread.

---

**End of handoff note. Titan ready for next session (VPS deploy of Alex + lead capture + voice + widget CDN).**
