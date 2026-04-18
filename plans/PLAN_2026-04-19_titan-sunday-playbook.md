# TITAN SUNDAY PLAYBOOK 2026-04-19

**Single pane of truth. Pairs with paste prompt. Reference this when re-waking mid-sprint instead of re-querying MCP.**

Anchors to MCP decisions logged 2026-04-18. If MCP and this doc ever disagree, MCP wins (it's canonical).

---

## THREE-PILLAR TRIPLE-DOWN (Solon directive 2026-04-18T20:15Z)

Three pillars MUST ship COMPLETE (not MVP) by Monday demo:

1. **CRM LOOP CLOSED COMPLETELY** (CT-0418-09 expanded)
2. **AI MEMORY GUARD COMPLETE** — polished + real (no mocking) (CT-0418-09 + CT-0418-11 merged)
3. **MOBILE CMD COMPLETE** (CT-0418-05 pulled-forward scope)

"COMPLETE" means: (a) Monday 10-beat demo flow 100% end-to-end without hitches, (b) Solon's daily ops 100% functional. Edge-case completeness beyond demo + daily use continues Tuesday/Wednesday.

Everything outside these three pillars is ICING (light touch) or DEFERRED.

---

## SUNDAY EXECUTION ORDER

Run continuously, no clock, elite quality to completion, next item on completion.

### Item 1 — SLACK COST CONTROL (pre-requisite, non-negotiable)

Per MCP 2026-04-18T19:20Z standing rule. Runs FIRST. Cost survival.

- Enumerate Slack webhook sources (VPS + Mac + n8n — grep SLACK_*_WEBHOOK env vars, slack_sdk usage, workflow webhook URLs)
- Severity-tier each: P0 (Slack+Ntfy), P1 (Slack rate-limited), P2 (Ntfy only), P3 (MCP log only)
- Downgrade current P2/P3 sources to Ntfy
- Webhook middleware chokepoint at n8n: de-dup (10-min window, message-hash fingerprint), hard caps (50 Slack/24hr global, 10/24hr per-source), maintenance-mode gate (check MCP `maintenance-mode-active` tag), cost kill-switch ($5/day or $100/month = auto-disable)
- E2E test: 15 synthetic rapid-fire alerts → only 1 lands Slack + counter increments. Force cost cap → kill-switch fires. Set maintenance-mode tag → suppression works.
- Ship tag: `slack-cost-control-live-armed-e2e-verified-2026-04-19`

### Item 2 — PILLAR 3: MOBILE CMD COMPLETE (CT-0418-05 pulled-forward)

#### 2a — Phase 2 walkthrough .docx

Titan produces exact-paste .docx with screenshots for Solon's Sunday PM batched session:

- sql/008 + sql/009 + sql/010 Supabase SQL Editor apply steps (line-by-line, screenshots of expected state)
- JWT RS256 keypair generation (openssl commands → /etc/amg/jwt-rs256.{priv,pub}.pem)
- VAPID keypair (optional, for push notifications)
- Gmail `gmail.send` scope upgrade (OAuth console steps)

Format for Solon mobile-friendly read. Clear success criteria per step. ~60-90 min Solon time.

#### 2b — Post-paste: Mobile Cmd full rollout

- Voice input working
- SSE streaming responses
- Auth endpoints live on newly-unlocked JWT
- All planned feature surfaces
- Tablet + phone both

#### 2c — Solon tests Sunday evening → bugs flagged → overnight fixes

Solon flags bugs via direct paste into Claude Code chat or EOM thread; EOM relays to Titan via `queue_operator_task`.

#### 2d — Monday AM: polished, battle-tested, ready

Ship tag: `mobile-cmd-complete-live-armed-e2e-verified-2026-04-19`

### Item 3 — PILLAR 1: CRM LOOP COMPLETE (CT-0418-09 expanded)

Tier A dual-engine architecture gate first (Perplexity Sonar Pro + Grok, both ≥9.3/dim, max 2 iterations). Then build:

- Per-tenant provisioning workflow: new client signup → tenants row + tenant_slug + tenant_uuid + JWT tenant_id claim + per-tenant Supabase schema isolation + agent roster activation + first-week deliverable auto-scheduled + portal access at `portal.aimarketinggenius.io/{tenant_slug}/`
- Lead intake auto-ingest from 5 sources: `inbound_form` (Lovable), `chatbot` (Alex orb), `voicebot` (Alex orb), `outbound_reply` (scaffold), `linkedin` (scaffold). Each writes CRM row with source attribution + tenant_id + Nadia entry point.
- CRM ↔ MCP bidirectional sync: CRM state changes → MCP decisions tagged `crm-memory-bridge` + `client-context:{tenant_slug}`. MCP decisions queryable back into CRM views.
- `agent_context_loader` extended: returns unified tenant context (CRM state + MCP decisions + memory_captures + project KB facts) for any agent on any tenant.
- RLS policies on all tenant-scoped tables. Synthetic tenant E2E test proves cross-tenant reads blocked.
- Revere Chamber demo tenant seeded for Monday pitch (tenant_slug: `revere-chamber-demo`).

Ship tag: `crm-loop-closure-complete-live-armed-e2e-verified-2026-04-19`

### Item 4 — PILLAR 2: AI MEMORY GUARD COMPLETE (CT-0418-09 + CT-0418-11 merged)

All real, no mocking.

#### 4a — Chrome extension polish

- UI rebranded AMG (navy + teal + green CTAs + white text), professional-grade not beta
- Smooth capture flow: select → click extension → classifier dropdown (research | prospect-context | decision-note | client-interaction | browsing-signal) → confirm save → animated confirmation → "saved to Atlas" toast
- Recent-captures sidebar (last 10 items: source URL, capture type, timestamp, tenant badge, verification status)
- Integration feedback: "X items captured, Y available to Atlas agents"
- Error handling: offline mode graceful fallback

#### 4b — Einstein Fact Checker (REAL)

- Claim extraction via Haiku 4.5 on captured content
- Source crosscheck via Perplexity Sonar API
- Items flagged verified/unverified based on actual check
- Unverified items still saved to vault but tagged
- Content scripts on Claude.ai + chat.openai.com + perplexity.ai + gemini.google.com detect AI outputs
- Overlay fires: "✓ Einstein verified N claims, saved to vault" (green) or "⚠ N claims need source" (yellow) or "✗ X unverified — not saved" (red)

#### 4c — Hallucinometer (REAL)

- Extension badge per supported LLM tab tracks message count (DOM-based)
- Color-code per Doc 10 thresholds: 🟢 FRESH 1-15 / 🟡 WARM 16-25 / 🟠 HOT 26-35 / 🔴 DANGER 36+
- Warning popup at 26: "⚠ Thread depth 26. Hallucination risk rising. Start new thread — AMG will carry context."
- Urgent red at 36: "🔴 Thread depth 36. Hallucinations likely. New thread NOW."

#### 4d — Vault Portal (REAL) at memoryvault.aimemoryguard.com

- Lovable or React build, AMG brand
- Auth via Supabase (reuse existing)
- Views: login → dashboard → memory feed → detail view
- Filter by LLM source (Claude, ChatGPT, Perplexity, Gemini, AMG Agents)
- Search + tenant filter + verification status filter
- Detail view shows full memory + provenance (source thread, captured_at, verified_by)
- Solon logs in end-to-end during Monday demo

#### 4e — Cross-LLM context injection (REAL)

- Content scripts on all 4 LLM platforms detect new-thread start
- Extension offers: "Inject relevant context from your vault?" with preview
- User confirms → context injected into LLM input field before user submits
- Works across all 4 platforms

#### 4f — Memory loop closed end-to-end

- AI Memory Guard captures → Einstein verifies → vault stores with verification flag → `agent_context_loader` pulls verified items first → agents respond with verified context
- E2E test: synthetic capture flow end-to-end, evidence captured

Ship tag: `ai-memory-guard-complete-live-armed-e2e-verified-2026-04-19`

### Item 5 — DON PREP BUNDLE (CT-0418-10)

#### 5a — Don Martelli 1-page prospect brief

- Pull LinkedIn + Revere Chamber context + board history + prior correspondence
- 5 lead-with talking points + 3 likely objections + Hammer Sheet counter-phrases
- Store: `/opt/amg-outbound/pitch-prep/DON_MARTELLI_BRIEF_2026-04-20.docx`
- Lumina v2 ≥9.0/dim Solon Voice Density + Vertical Specificity

#### 5b — Chamber Partnership Proposal .docx

Content-Sources-Mandate pre-draft: Hormozi Offer Engine + Solon OS + Hammer Sheet + Chamber AI Advantage Encyclopedia + case studies.

Structure: Cover → Partnership Vision → What AMG Provides (7-agent roster mapped to Chamber member needs) → Revenue Share Model → Member Benefits → Pilot Scope (90-day) → Success Metrics → Grand Slam Offer Summary → Signature.

**GUARANTEE PHRASING LOCKED** (exact): "If after 3 months you're not completely satisfied with the results we're getting for you, we'll work a full month FREE. No asterisks. No hedging."

Placement: Grand Slam Offer Summary + Partnership Terms + "Our Promise to Revere Chamber" on signature page.

Store: `/opt/amg-outbound/proposals/REVERE_CHAMBER_PARTNERSHIP_PROPOSAL_2026-04-20.docx`

Lumina v2 ≥9.0/dim on ALL dimensions.

#### 5c.0 — Demo dry-run

Solon dry-runs 10-beat demo flow Sunday evening post-Mobile-Cmd-test; broken beats patched overnight by Titan.

#### 5c — Demo backup redundancy

After demo flow complete + dry-run passes: record 5-min screen walkthrough + screenshot deck (PDF, ~15 slides).

Store: `/opt/amg-demo-backup/` + R2 mirror to `amg-storage/demo-backup-2026-04-20/`

Accessible offline from Mac + tablet + phone in case of Wi-Fi / orb failure mid-pitch.

### Item 6 — /chamber-partners PAGE FLASH (CT-0418-12 reduced icing)

Per Solon: main site + case studies already done. This is icing on the Chamber-specific page.

- Visual flash + nicer-looking fonts + Chamber-specific design language + polished visual hierarchy
- Brand-aligned (navy + teal + green CTAs + white) + elevated typography
- 2-3 compact case studies (Chamber-angled): pick strongest of Shop UNIS, Paradise Park, Revel & Roll, Levar/JDJ
- 7-agent visual section (card grid)
- Guarantee prominent
- CTA: book audit
- Lumina v2 ≥9.0/dim copy + visual quality gate

NOT IN SCOPE: main aimarketinggenius.io site-wide rewrite, main case studies page rewrite.

Ship tag: `chamber-partners-page-flash-live-armed-e2e-verified-2026-04-19`

### Item 7 — DAWN LUMINA RE-REVIEW

Before Solon wakes Monday AM, every Monday-bound deliverable gets re-scored by locked Lumina rubric v2:

- All 3 pillar ship tags verified
- /chamber-partners page
- Chamber Partnership Proposal
- Don prospect brief
- Demo flow dry-run evidence
- Vault Portal memories seeded
- Revere Chamber demo tenant + Alex pipeline verified

Any <9.0/dim iterated in-sprint or Tier A escalated. No deferred quality to Monday AM.

Log: `lumina-dawn-review-2026-04-20` with pass/fail per artifact.

---

## DEMO FLOW v3 (10 beats, ~20 min)

### Beat 1 — Opening frame (30s)

> "Every AI tool forgets, hallucinates, and drifts. We built the first one that remembers — verified, across every LLM you use, with real fact-checking and drift protection. Watch."

### Beat 2 — AI MEMORY GUARD EXPANDED SHOWCASE (6-7 min, hero)

- 2a: Live capture on Revere Chamber website — polished UI, 3 items captured (Don's board role, annual gala, member count)
- 2b: Einstein Fact Checker fires — "✓ Einstein verified 3 claims, saved to vault" badge visible
- 2c: Hallucinometer visible — "🟢 Thread depth 8/40 — fresh zone"
- 2d: ALEX BOT JAW-DROP — "Alex, what do you know about Revere Chamber?" Alex instantly recites captured items + Chamber Encyclopedia insights. Physical-reaction moment.
- 2e: Cross-LLM context tease — Solon switches to ChatGPT, AI Memory Guard offers context injection, or Solon narrates "Claude, ChatGPT, Perplexity, Gemini all pull from the same vault"
- 2f: Vault Portal glimpse — `memoryvault.aimemoryguard.com` polished dashboard shows all memories organized by source LLM + thread + verification

### Beat 3 — MOBILE CMD POCKET DEMO (1 min)

Phone voice command: "Atlas, draft a proposal for Revere Chamber." Mobile Cmd responds with preview. AI ops team in pocket.

### Beat 4 — BACKEND PORTAL GLIMPSE (30s)

Screen share Command Center + MCP decisions feed + task queue. Real production substrate. Screenshot deck fallback if live-share glitches.

### Beat 5 — CHAMBER AI ADVANTAGE VERBAL WALK (3-5 min)

Full 7-agent roster from Chamber AI Advantage Encyclopedia v1.4+: Maya (content), Nadia (nurture), Alex (voice + chat), Jordan (SEO), Sam (social), Riley (reputation), Lumina (visual). Partnership program. Revenue share. Member benefits.

Solon's home field — improv + Hammer Sheet + case studies + memorable expressions.

### Beat 6 — AMG WEBSITE TOUR (2-3 min)

Solon pulls up `aimarketinggenius.io`: hero → 7-agent section → CASE STUDIES PAGE live (Shop UNIS + Paradise Park + Revel & Roll + Levar/JDJ — real before/after, 30-day traction framing, not 90-180 day legacy).

Double-qualifier: Don realizes AMG is already doing this at higher level than competitors AND can build the Chamber's site too.

### Beat 7 — GUARANTEE DROP (1 min)

Lean-in moment. Exact phrasing:

> "If after 3 months you're not completely satisfied with the results we're getting for you, we'll work a full month FREE. No asterisks. No hedging."

Hormozi risk-reversal at sharpest. Pilot becomes zero-risk for Don.

### Beat 8 — CHAMBER PARTNERSHIP PROPOSAL HANDOFF (30s)

Printed .docx to Don: "I've drafted this for Revere specifically. The guarantee I just mentioned is in there, signed commitment. Review, tell me what you want refined."

### Beat 9 — NEXT STEP + CLOSE (1 min)

Propose pilot timeline (90 days, measurable, aligned with guarantee window). Ask for follow-up scheduling: "When can you meet again this week?"

### Beat 10 — OPTIONAL Q&A BUFFER

Anticipate 3-4 likely Don questions. Hammer Sheet counter-phrases pre-loaded in brief.

---

## ACCEPTANCE BARS (per task)

**Filter question**: "Does this serve the 10-beat demo flow or make the jaw-drop stronger?" If not → deferred.

**Automation Ship Criteria (5 conditions, per MCP 2026-04-18T18:50Z):**

1. Code committed (~20% of ship)
2. Services running (workflow activated, process listening, URL live)
3. E2E synthetic test passed (evidence captured: logs, MCP trail, Ntfy, file, state change)
4. Recovery test passed (for recovery-class automations)
5. MCP decision logged with `<name>-live-armed-e2e-verified-<date>` tag + all 5 condition tags

No automation counts as shipped without all 5. "Committed to git" is ~20%.

**Lumina Rubric v2 (locked in Sprint 4 Task 4.4):**

- Source Synthesis Depth ≥9.0/dim (evidence of ≥3 canonical sources blended)
- Solon Voice Density ≥9.0/dim (memorable expressions + rhetorical patterns + challenger posture + no generic AI cadence)
- Conversion Cadence (AIDA/PAS, hook, CTA)
- Vertical Specificity (Chamber context, not generic B2B)
- Plus format-specific dims per deliverable type (outbound email / voice pitch / landing page / proposal)

≥9.0/dim required for Monday-bound deliverables.

---

## CONTENT SOURCES MANDATE (any content piece)

Every content piece MUST synthesize ≥3 canonical sources BEFORE drafting:

1. **Solon OS** — voice + expressions + rhetorical patterns (via `search_memory`)
2. **Hormozi Offer Engine** — G Drive LeadGen KB folder `1CwZBrZR4g7E1rZSMQFNWUd-wOBe0sgUa` → `01-Hormozi-Offer-Engine.md`
3. **Hammer Sheet** — Chamber AI Advantage Encyclopedia v1.4+ + prior threads
4. **Chamber AI Advantage Encyclopedia v1.4+** — vertical positioning + 7-agent roster + partnership program + case studies
5. **Case Studies** — Shop UNIS, Paradise Park Novi, Revel & Roll West, Levar/JDJ
6. **G Drive LeadGen KB** — specific docs per content type (outbound email → 01+03, landing page → 12+13, etc.)
7. **Solon's memorable expressions** — via `search_memory` as needed

**FAIL STATES (automatic reject):**

- Generic AI cadence ("In today's fast-paced world," "Unlock the power of," "At [company] we believe")
- No Solon voice markers
- No Hormozi framework traceable
- Pure Chamber Encyclopedia regurgitation without Solon layer
- Reads like every other AI marketing agency

---

## DEFERRED TO TUESDAY+

- Sprint 2 scope (CT-0418-05 minus Phase 2 walkthrough + Mobile Cmd pulled forward) — prosecution auto-draft, daily summary backstop, Command Center 3-5/15
- Sprint 3 scope (CT-0418-06) — Mac Watchdog PREP, Storage Hygiene PREP, C1 v0.2
- Sprint 5 outbound entirely — Nadia 3-touch, Alex voice pitch outbound, LinkedIn DMs, reply handling
- Sprint 6 inbound nurture entirely — form auto-ingest (if not done in CRM), chatbot/voicebot pivots, Nadia 14-day drip
- Gemini MCP Auditor (CT-0418-07)
- Hammerspoon productivity suite (CT-0418-08)
- Non-Chamber demo archetype scripts (small biz + skeptic)
- Multi-tenant scale edge cases beyond Revere Chamber demo tenant
- Additional LLM platforms beyond Claude/ChatGPT/Perplexity/Gemini

---

## SHIP TAG CHECKLIST (Monday-AM must-have)

Before dawn Lumina review, these MCP tags must exist:

- [ ] `slack-cost-control-live-armed-e2e-verified-2026-04-19`
- [ ] `mobile-cmd-complete-live-armed-e2e-verified-2026-04-19`
- [ ] `crm-loop-closure-complete-live-armed-e2e-verified-2026-04-19`
- [ ] `ai-memory-guard-complete-live-armed-e2e-verified-2026-04-19`
- [ ] `chamber-partners-page-flash-live-armed-e2e-verified-2026-04-19`
- [ ] `lumina-dawn-review-2026-04-20`

Plus Don Prep deliverable paths verified:
- [ ] `/opt/amg-outbound/pitch-prep/DON_MARTELLI_BRIEF_2026-04-20.docx` exists
- [ ] `/opt/amg-outbound/proposals/REVERE_CHAMBER_PARTNERSHIP_PROPOSAL_2026-04-20.docx` exists
- [ ] `/opt/amg-demo-backup/` with R2 mirror exists

---

## TOKEN PRESSURE / RESTART HANDOFF

At 85%+ utilization: emit RESTART_HANDOFF per CLAUDE.md §13.1 Session Continuity. Path 4 armed — autonomous nudge will fire on next idle ≥10min with pending queue items + Claude Code app running.

Next session resume: §13.1b poll trigger (a) + read this playbook + continue at the next unchecked item.

---

## PATH 4 STATUS

LIVE ARMED per MCP `path-4-idle-nudge-live-armed-e2e-verified-2026-04-18`.

- VPS systemd `tla-idle-detector.timer` every 60s writes `tla-nudge-fire-pending` when Titan idle ≥10min + queue non-empty
- Mac Hammerspoon polls Supabase every 30s, injects nudge phrase if pending detected + not in dry-run
- Dedupe window 15 min, urgent-priority override, kill-switch via `tla-disabled` / `tla-nudge-disabled` MCP tags

---

## ACCEPTANCE FILTER (final)

Every task, every output, every iteration, ask:

**"Would Don Martelli walk away stunned?"**

If eye-roll risk anywhere → iterate, escalate Tier A, or defer. No shipping sub-elite.

Cook continuously.
