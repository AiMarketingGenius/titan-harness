# TITAN POST-WEEKEND FOCUS QUEUE — v2 (SOLON REORDERED)
**Date:** 2026-04-17 EOD
**Supersedes:** TITAN_POST_WEEKEND_BACKLOG.md (v1)
**Source of reorder:** Solon directive 2026-04-17 — focused build order, nothing else until these are perfected.

---

## CORE FOCUS — THE ONLY FIVE THINGS THAT MATTER NEXT

After AMG site + aimemoryguard restore ship Sunday 6pm ET, Titan's entire attention goes to these 5 — in this exact order. Everything else in the prior backlog waits until these are complete.

---

### 1. SOLON OS + ATLAS SYSTEM — finish both completely

**Status:** MP-1 / MP-2 mid-flow at Phase G.1.4 (triple-source extraction). Baby Atlas v1 architecture doctrine shipped (CT-0417-F6, dual-grader 9.65).

**What "complete" means:**
- Triple-source Solon OS extraction finished (Lane 1 EOM + Lane 2 Perplexity + Lane 3 Titan) → synthesized canonical behavioral profile
- Solon OS behavioral profile deployed into Atlas as the substrate for agent personality behavior
- Atlas Layer 2 portal build complete — multi-tenant ready, per CT-0417-F6 spec
- Parallel-lane fan-out (up to 5 concurrent lanes) functional with live testing
- Per-Chamber cost_kill_switch caps wired and tested
- Atlas sole-interface rule enforced (admin talks only to Atlas; 8 specialists silent backstage)
- Dual-grader rubric update deployed (any Baby Atlas artifact omitting sole-interface OR parallel-lanes auto-fails below 9.3)

**Why this comes first:** Solon OS is the substrate. Mobile Command needs Solon's voice personality — that voice lives in Solon OS. Building Mobile Command before Solon OS = building on incomplete foundation.

---

### 2. MOBILE COMMAND v2 — AMG-branded, Solon voice, premium app-grade, with Claude on/off/reset

**Only starts after #1 is complete.**

**Visual + UX requirements:**
- Full AMG brand (dark navy + blue/teal + bright green + white)
- Premium mobile app design — not placeholder chips + orb. Real iPhone app feel.
- Real iPhone screenshots for embedding on AMG site as trust signals
- Voice orb uses Solon's cloned voice (from ElevenLabs, post-Solon-OS-completion)

**Functional requirements:**
- Live command execution — Solon controls Claude Code / Titan from phone
- Command history + response feed
- **Claude on/off/reset controls** — Solon can from his phone:
  - Start Claude Code session
  - Stop Claude Code session
  - Reset Claude Code (kill + fresh boot)
  - View current session status (active / idle / processing)
- Push notifications when Titan completes a task or hits a blocker
- Voice input (talk to Titan) + voice output (hear responses in Solon's own cloned voice)

**Asset deliverables:**
- Working Mobile Command v2 PWA at `ops.aimarketinggenius.io/titan` (or current route)
- iPhone screenshots embedded on AMG site as demo surface
- 30-60 second screen-recording demo video (actual iPhone, not simulator)
- Lumina ≥9.3 visual review

---

### 3. CRM — complete the multi-tenant generalization

**Status:** Phase 1 shipped at `ops.aimarketinggenius.io/crm` (CT-0417-29, dual-grader 9.55). 5 clients backfilled. CRM↔MCP bidirectional sync live.

**What "complete" means (CT-0417-35):**
- Multi-tenant generalization to `portal.aimarketinggenius.io/{tenant_slug}/crm`
- Supabase RLS on tenant_id — each tenant's data fully isolated
- Solon becomes tenant #1 with super-admin flags (sees all tenants + cross-tenant analytics)
- Email Outbound module wired as CRM core feature (per P10 multi-tenant doctrine)
- Voice AI Outbound module wired as CRM core feature
- Every new tenant auto-provisioned on signup with scoped RLS
- Cross-tenant adversarial testing passed (no data leakage across tenants)
- Dual-engine ≥9.3 on the generalization

---

### 4. AIMG EXTENSION — PRE-GENERATION FACT-CHECKING (correct BEFORE output, not after)

**Status:** v0.1.0 deployed with post-generation Einstein Fact Checker (detects contradictions after AI responds). Solon's Perplexity research: the correct architecture is pre-generation interception — flag issues AS the AI produces output, not after.

**What "complete" means:**
- Extension updated to intercept AI-generated text during stream
- Real-time flagging while output is being produced
- Visual indicators appear inline as suspect content streams
- User can pause/review/correct mid-generation
- Works across all 5 supported platforms (ChatGPT / Claude / Perplexity / Gemini / Grok)
- Performance budget: < 100ms added latency to perceived output speed
- Hallucinometer severity scoring integrated (green / yellow / red zones per flagged span)
- Auto-Carryover still functional after upgrade
- Memory Capture still functional after upgrade
- Dual-grader ≥9.3 on the architecture shift

**Why this matters:** fact-checking AFTER output is too late — users have already read and internalized wrong info. Pre-generation flagging is the patent-differentiating mechanism and the real user-safety feature.

---

### 5. COMMAND CENTER PORTAL — unified visibility

**What "complete" means:**
- Single portal where Solon sees everything:
  - All memories across all Claude conversations (via consumer Supabase gaybcxzrzfgvcqpkbeiq)
  - Thread health + contradiction flags + Auto-Carryover events
  - Subscriber revenue + MRR rollup (AMG + AIMG + Memory Vault + Chamber rev-share)
  - Chamber partnership pipeline
  - Titan ops dashboard embedded
  - CRM cross-tenant view (from #3 above)
- Search across all memories with filter (by platform / by date / by severity flag / by topic)
- Correct / delete / export any memory
- Visual dashboard — not just raw data tables. AMG-branded, premium.
- Desktop-optimized (Solon's primary work surface)
- Dual-engine ≥9.3

**Location:** `portal.aimarketinggenius.io/{solon-slug}/` (Solon's super-tenant sub-portal per P10 GHL-style multi-tenant doctrine).

---

## EXECUTION RULES FOR TITAN

1. Sequential discipline — no parallel execution across these 5. #1 must ship before #2 starts. #2 must ship before #3 starts. And so on.
2. Each item has dual-engine ≥9.3 + Lumina ≥9.3 before "complete."
3. Any blocker → log to `#solon-command` with question + options + recommendation. Do not guess. Do not skip to next item.
4. Real-time MCP logging — `log_decision` on every decision, `update_sprint_state` on every sub-task ship.
5. Trade-secret scrub on every surface (extended list per Addendum #6).
6. AMG brand tokens from live site only (per Addendum #5).
7. No prose copy by Titan — commission SEO | Social | Content project for any visible copy. Lumina for any visual review.

## WHAT TITAN DOES NOT DO UNTIL ALL 5 ARE COMPLETE

These wait:
- DR-AMG-ENFORCEMENT-01 v1.4 hard-gate implementation
- DR-AMG-SECRETS-01 secrets rotation
- Hetzner secondary VPS
- AIMG admin portal Stage 2
- Claude Partner Network application
- ZDR request
- Console spend caps audit
- Teleprompter build
- Provisional patents (Solon files when ready, Titan supports)
- Chamber Marketing Podcast infrastructure
- Contract template drafting
- PaymentCloud application
- Description Field bug sweep across 10 Claude projects
- Four Doctrines re-audit

All of the above stay in Tier 2 backlog until the focus 5 ship.

---

**Titan's next 3 hours focus per Solon directive:** perfection on whichever of the 5 is in-flight. Solon checks back in 3 hours.

**End of focus queue v2.**
