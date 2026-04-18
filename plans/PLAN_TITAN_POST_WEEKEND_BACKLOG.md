# TITAN POST-WEEKEND BACKLOG — PRIORITIZED
**Date:** 2026-04-17 EOD
**Source:** MCP sprint state + recent decisions + user memories
**Order:** Demo-worthy / pitch-supporting first. Infrastructure after.

---

## TIER 1 — DEMO-WORTHY (next after AMG site + aimemoryguard ship)

### 1. MOBILE COMMAND v2 — AMG-branded, premium, actually-functional-looking

Solon directive: the current /titan mobile PWA looks sparse and unimpressive. Next project is to rebuild Mobile Command so it looks like a real, polished mobile app that Solon controls Titan (Claude Code) from his phone.

**Requirements:**
- Full AMG branding: dark navy + blue/teal accents + bright green CTAs + white text (live site tokens)
- Premium visual design — not placeholder chips + orb. Real app feel.
- **Actual iPhone screenshots or screen-frame mockup** embedded on the AMG site as a "See Mobile Command" demo surface (so prospects see the product in action)
- Functional surface: Solon actually executes commands from his phone — "run deploy," "check sprint state," "draft follow-up email," etc.
- Voice-orb integration (same pipeline as AMG Alex — shared backend)
- Command history + response feed visible
- Real command examples from Solon's daily workflow

**Why this matters for pitch:**
- Demonstrates AMG's AI platform isn't just blog posts and social — it's an operator-grade system
- Don sees "Solon literally runs his AI agency from his phone" → positions AMG as category leader
- Screenshots on the AMG site become lasting trust signals, not just live-demo moments

**Deliverables:**
- Redesigned Mobile Command PWA at `ops.aimarketinggenius.io/titan` (or current route)
- High-quality iPhone mockup screenshots embedded on AMG site
- Short demo video (30-60 sec, screen-recorded on actual iPhone)
- Lumina visual review ≥9.3

Titan already has the spec context from CT-0417-27 Mobile Command Infrastructure. This extends that — v2 is the visual + content polish layer.

---

### 2. AMG SITE ONGOING POLISH

Post-weekend feedback loop — things that will surface after Solon lives on the site for a day:
- Copy refinements from Solon's own read-through
- Additional case study detail when any existing client ships a new win
- Lumina re-audit in 2 weeks for drift correction
- A/B test the 3-persona CTA strip order
- Blog publishing cadence continues (post #6 and beyond via SEO | Social | Content project)

---

## TIER 2 — REVENUE UNBLOCKERS

### 3. PayPal plan creation — AIMG ($9.99 Pro + $19.99 Pro+)

Status: BLOCKED on PayPal slider CAPTCHA. Solon provides `PAYPAL_CLIENT_ID` + `PAYPAL_SECRET` in `#solon-command` OR logs into paypal.com once on persistent browser so Titan grabs session cookies.

Once creds drop: Titan fires `/home/titan/amg/paypal_add_aimg.py` → 2 products live for aimemoryguard.com consumer subscriptions.

### 4. Levar Week-1 fulfillment execution

GBP live as of 2026-04-17. Fulfillment handoff to WoZ agents (Alex/Maya/Jordan/Sam/Riley/Nadia) — not Titan's core ops. Titan confirms WoZ routing works + monitors first-week output quality.

### 5. Voice orb demo video

Already in sprint scope (Sunday PM) but formalized here: backup demo video for Monday pitch, then becomes permanent asset on AMG site showcasing the voice AI.

---

## TIER 3 — MULTI-TENANT + CRM INFRASTRUCTURE

### 6. CT-0417-35 Multi-tenant CRM generalization

CRM Phase 1 shipped at `ops.aimarketinggenius.io/crm` (CT-0417-29). Next phase: generalize to `portal.aimarketinggenius.io/{tenant_slug}/crm` with Supabase RLS on tenant_id. Each Chamber + each subscriber = their own CRM. Solon becomes tenant #1 with super-admin flags.

### 7. CT-0417-30 T2 + T8 completion (AIMG admin portal)

Stage 2 held items: `sql/aimg_001_admin_schema.sql` (subscribers + einstein_fact_checks + billing_events tables), admin actions (create/upgrade/downgrade/pause/suspend/refund), PayPal API wiring (unblocks on #3).

### 8. /titan desktop UX decision

Mobile Command v2 (#1 above) resolves this — desktop becomes the "see Mobile Command demo" surface for prospects; mobile is actual operator use. Blocker closes when Mobile Command v2 ships.

---

## TIER 4 — DOCTRINE + SECURITY + RELIABILITY

### 9. DR-AMG-ENFORCEMENT-01 v1.4 hard-gate implementation

Behavioral rules → hard technical gates. Includes cosign cryptographic signing, YubiKey-backed Tier-1 ceremonies, parallel dual-signal canary probes (HTTPS + SSH), pre-proposal-gate.sh, OPA policies, Slack auto-alerts. Titan executes under EOM line-by-line review. Propose-only mode stays until this ships.

### 10. DR-AMG-SECRETS-01 secrets rotation

Blocks lead-gen outbound activation per §15.2. Full rotation sweep: env files, API keys, webhook secrets, OAuth tokens. Titan inventories + rotates + verifies.

### 11. Hetzner secondary VPS (disaster recovery standby)

Per DR-AMG-RECOVERY-01 RED-status item. Secondary VPS provisioned, DNS cutover via Cloudflare pre-wired, quarterly restore drill scheduled.

### 12. Description Field bug sweep (10 Claude projects)

Across all AMG Claude projects — standing bug. Titan diagnoses + fixes.

### 13. Four Doctrines audit cadence

CT-0417-28 shipped. Next re-audit: 7 days from ship OR on-demand when a 🔴 item closes.

---

## TIER 5 — GROWTH INFRASTRUCTURE

### 14. Claude Partner Network application

30 min Tuesday morning task. `claude.com/partners`. AMG = Consulting Partner. Baseline: 3 production deployments + 1 CCA certified architect (Solon takes the cert, free for first 5,000 partner-org employees).

### 15. ZDR request via sales@anthropic.com

Tuesday morning. Triggers account team assignment + internal review. Applies to Enterprise API + Claude Code with Commercial org API key.

### 16. Console spend caps audit + workspace splits

Tuesday morning. Separate workspaces: Titan VPS / EOM / Consumer products. Workspace-level caps with org ceiling override.

### 17. Teleprompter build

Research prompt drafted, parked. Run Perplexity + Grok async, execute post-Monday.

### 18. AIMG Chrome extension v0.2 (Hallucinometer)

Post-patent-filing. Held until Solon files provisional A ($65) + B ($65).

---

## TIER 6 — IP + LEGAL

### 19. Provisional patent A ($65) — Memory Guard consumer 6-embodiment

Solon files via USPTO EFS-Web. EOM drafts ready-to-paste. ~20 min.

### 20. Provisional patent B ($65) — Atlas/AMG platform 11-embodiment

Same day as A. EOM drafts ready-to-paste. ~20 min.

### 21. Free trademark sweep (28 brand terms)

Titan runs in parallel with Solon's patent filings. Includes all agent names + product names + internal operator names + Einstein Fact Checker™.

### 22. © 2026 footer + Confidential watermark sweep

Across all AMG docs + AIMG docs + client deliverables. Titan automates via pre-commit hook.

---

## TIER 7 — SOLON OS (post-Monday strategic)

### 23. MP-1 / MP-2 Solon OS substrate resume

Mid-flow at Phase G.1.4. Triple-source extraction (EOM + Perplexity + Titan) → canonical behavioral profile → agents as Solon personality clones.

### 24. Chamber Marketing Podcast concept

Parked 2026-04-17 late-night. Strategy + production + guest outreach design in Tuesday planning.

---

## TIER 8 — SUPPORTING / DEFERRED

- Shop UNIS / Paradise Park / Revel & Roll West ongoing delivery (WoZ-handled, Titan monitors only)
- Contract template drafting (attorney-reviewable SOW + Exhibits A-G for Don signing)
- PaymentCloud application (Titan fills via Stagehand, Solon finishes on phone)
- Secondary processor resolution (Durango vs. FastSpring conflict)
- Mobile native iOS/Android Memory Guard companion (deferred multi-month project)

---

## RECOMMENDED TITAN SEQUENCE POST-WEEKEND

**Monday (after pitch):**
- Mobile Command v2 kickoff
- PayPal creds unblock (if Solon dropped them)
- Post-pitch AMG site polish based on Solon feedback

**Tuesday:**
- Mobile Command v2 first visual mockups
- Claude Partner Network application
- ZDR request
- Console spend caps audit
- Provisional patents ready for Solon filing

**Wednesday-Friday:**
- Mobile Command v2 ship
- CT-0417-35 multi-tenant CRM generalization
- DR-AMG-ENFORCEMENT-01 v1.4 hard-gate implementation
- Secrets rotation
- Hetzner secondary VPS

**Following week:**
- AIMG admin portal Stage 2
- Four Doctrines re-audit
- Chamber Marketing Podcast launch plan

---

**End of backlog. This is Titan's post-weekend queue — demo-worthy work up top, infrastructure + growth after.**
