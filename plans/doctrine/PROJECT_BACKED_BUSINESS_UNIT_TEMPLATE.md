# Project-Backed Business Unit Template — Atlas productization blueprint

**Status:** ARCHITECTURE LOCKED 2026-04-17 (Option C Hybrid, 18-project base)
**Canonical path:** `/opt/amg-docs/doctrine/PROJECT_BACKED_BUSINESS_UNIT_TEMPLATE.md` (mirrored from harness)
**Owner:** Solon (approval), Titan (execution)

---

## 1. WHY THIS EXISTS

AMG's real product isn't "another agency." It's **a cloneable agent-infrastructure template** per business vertical. Chambers, restaurants, med spas, law firms, HVAC chains — each vertical gets a tailored project set sized to their business units.

The 18-project base below is the **AMG-internal instantiation** of this template. Every future vertical-client deployment forks this repo of Claude Projects, swaps KB content for the new vertical, and ships.

Each Claude Project represents a specialized **business unit** with deep domain expertise:
- Layer 1 (Titan specialists, 10 projects) — internal execution engines
- Layer 2 (Subscriber agents, 7 projects) — client-facing interfaces
- Layer 3 (Business ops, 1+ projects) — internal operations + vertical-product template

## 2. LAYER MAP

### Layer 1 — Titan Specialists (internal execution — 10)

| # | Project | Scope | KB size target |
|---|---|---|---|
| 1 | Titan-Operator | Master orchestrator; dispatches to specialists; owns sprint state | 20K tokens |
| 2 | Titan-CRO | Conversion optimization, landing page audits, funnel diagnosis, A/B tests | 20K |
| 3 | Titan-SEO | Technical SEO, schema, local rankings, GBP, keyword research | 25K |
| 4 | Titan-Content | Blog, email, GBP posts, long-form writing, newsletter | 20K |
| 5 | Titan-Social | IG, FB, LinkedIn, X content calendars + platform playbooks | 20K |
| 6 | Titan-Paid-Ads | Meta, Google, LinkedIn ad campaign strategy + execution | 20K |
| 7 | Titan-Security | Pen testing, Infisical, SOC 2 prep, tenant isolation | 15K |
| 8 | Titan-Reputation | Review monitoring + response, crisis comms, Google/Yelp/Tripadvisor | 20K |
| 9 | Titan-Outbound | Cold email, LinkedIn outreach, prospecting, meeting booking | 20K |
| 10 | Titan-Proposal-Builder | Client proposals, contracts, SOWs, pricing | 20K |

### Layer 2 — Subscriber Agents (client-facing — 7)

| # | Project | Role | KB size target |
|---|---|---|---|
| 11 | Alex-AMG-Strategist | Business Coach — strategy, prioritization, routing | 20K |
| 12 | Maya-Content-Strategist | Brand voice, content frame (execution via Titan-Content) | 15K |
| 13 | Jordan-SEO-Specialist | Client-facing SEO diagnosis (execution via Titan-SEO) | 15K |
| 14 | Sam-Social-Media-Manager | Client-facing social strategy (execution via Titan-Social) | 15K |
| 15 | Riley-Reviews-Manager | Client-facing reputation (execution via Titan-Reputation) | 15K |
| 16 | Nadia-Outbound-Coordinator | Client-facing outbound (execution via Titan-Outbound) | 15K |
| 17 | Lumina-UX-CRO-Gatekeeper | Design system + CRO + Lumina gate for all visual deliverables | 25K |

### Layer 3 — Internal Business Ops (1+; template for vertical products)

| # | Project | Scope | Vertical pattern |
|---|---|---|---|
| 18 | Titan-Accounting | AMG bookkeeping, tax prep, financial reporting | Becomes template for selling AI Accounting as a vertical module |

Future verticals add their own Layer 3 projects: Titan-Inventory (restaurants/retail), Titan-HIPAA-Content (med spas), Titan-Matter-Management (law firms), Titan-Dispatch-Routing (HVAC/home services), etc.

## 3. OPERATING PATTERN

```
Subscriber (Joe's Pizza of Revere)
        │
        ▼
  Subscriber Agent (Alex-AMG-Strategist)          ← Layer 2 (client-facing surface)
        │
        │  "I'll hand this to Titan-Content for the draft"
        ▼
  Specialist Titan (Titan-Content)                ← Layer 1 (internal execution)
        │
        │  draft → Lumina-UX-CRO-Gatekeeper review
        ▼
  Lumina scores ≥ 9.3 → Gemini Flash + Grok Fast dual-validate ≥ 9.3 each → ship
```

- Subscribers never invoke Layer 1 directly. Subscriber-agent routing layer handles all delegation.
- Titan-Operator orchestrates multi-specialist workflows (e.g., SEO + Content + Social combined campaign).
- Lumina is BOTH a Layer 2 subscriber agent AND the visual/CRO gate on every client-facing deliverable. She is called twice: once as client-facing consult, once as internal gate.

## 4. KB + SI STRUCTURE (every project)

```
/opt/amg-docs/agents/{name}/
├── SYSTEM_INSTRUCTIONS.md          # the 'custom instructions' blob for the Claude Project
├── META.yaml                       # cache_key, token_count, last_reviewed, claude_project_id
└── kb/
    ├── 00_identity.md              # who this project is, scope, non-negotiables
    ├── 01_capabilities.md          # what it can + cannot do (hard lines)
    ├── 02_tone_voice.md            # voice markers, banned phrases
    ├── 03_domain_knowledge.md      # the meat — 60-70% of the KB is here
    ├── 04_routing_handoffs.md      # which other projects does this one hand off to + when
    ├── 05_reference_data.md        # Encyclopedia v1.3 section refs, pricing cheatsheet, data it cites
    ├── 06_trade_secrets.md         # never-mention list + preferred framing
    ├── 07_quality_bar.md           # what "good" output looks like (anti-examples + exemplars)
    └── 99_examples.md              # 10 gold-standard exchanges
```

## 5. EXECUTION SEQUENCE (Phase 1-5 per master batch directive)

### Phase 1 — KB + SI generation (3-4 h)

- Generate 18 KB packages: per the structure in §4, 15-25 files each, 15-25K tokens each
- Trade-secret compliant: Atlas/AMG brand names ALLOWED; underlying vendors (Claude/Anthropic/Gemini/Grok/OpenAI/ElevenLabs/Supabase/n8n/Stagehand) and infrastructure codenames (beast/HostHatch/140-lane) FORBIDDEN in any KB content that subscriber agents may quote
- 18 SYSTEM_INSTRUCTIONS.md files at `/opt/amg-docs/agents/{name}/SYSTEM_INSTRUCTIONS.md`
- Validator: `bin/kb-tokenize.sh --all` confirms each KB under the 30K cap

### Phase 2 — Stagehand project cloning (2-3 h)

- Authenticate claude.ai via persistent browser session (Stagehand pool on `browser.aimarketinggenius.io:3200`)
- Identify template project to clone (likely EOM — richest existing KB)
- Clone template 18 times via UI automation
- Rename each clone per §2 list
- For each clone:
  1. Wipe inherited KB from template
  2. Upload that agent's KB files via Stagehand file-upload automation
  3. Paste the agent's SI into custom instructions
  4. Enable memory features
  5. Capture project URL/ID from browser address bar
  6. Screenshot populated project for verification

### Phase 3 — Integration (1-2 h)

- Write `/opt/amg-docs/agents/project_ids.json` mapping project name → claude.ai project URL/ID
- Update `lib/mcp_agent_context_loader.js` to route calls through project-backed context per project_id (phase-2 handoff: calls claude.ai conversational API via project membership instead of KB-in-context)
- Titan-Operator's CLAUDE.md bootstraps from its own project
- Specialist Titans invoked via `agent_context_loader(agent_name, client_id, query)`
- Subscriber agents routed through WoZ pipeline with same loader

### Phase 4 — Smoke testing (1 h)

- Test each specialist Titan: e.g. "Titan-SEO, audit reverechamberofcommerce.org"
- Test each subscriber agent: e.g. "Alex, explain Chamber AI Advantage to a skeptical Board member"
- Test orchestration: Titan-Operator dispatches Titan-CRO to redesign Revere portal agent cards → output reviewed by Lumina → Gemini Flash + Grok Fast dual-validate ≥ 9.3 → ship
- Log all 18 pass/fail + sample outputs to MCP

### Phase 5 — Revere portal redesign (2-3 h)

- Titan-Operator dispatches Titan-CRO to redesign the agent cards for premium aesthetic
- Lumina reviews + scores ≥ 9.3
- Gemini Flash + Grok Fast dual-validate
- Ship to `checkout.aimarketinggenius.io/revere-demo/` (overrides prior v4)

**Total estimate:** 9-13 hours autonomous execution, spread across focused multi-hour sessions. **NOT one-turn work.**

## 6. STAGEHAND AUTH CASCADE PROTOCOL (per directive)

If claude.ai Stagehand auth fails:
1. Check persistent browser cookies at `browser.aimarketinggenius.io:3200` via the existing Stagehand pool client
2. Cascade-call Grok: `"claude.ai Stagehand session authentication 2026"` — ask for persistent-session tactics
3. Cascade-call Gemini Flash same query
4. Try session cookies from `/etc/amg/claude-session.json` if it exists
5. ONLY if 1-4 fail: flag to Solon with specific credential needed, AND propose alternative — temporarily generate agents via Anthropic API with full context manually injected until claude.ai session restored

## 7. VERTICAL REPLICATION PATTERN

For each new vertical (chambers, restaurants, med spas, etc.):

1. Fork the 18-project set
2. Rename Layer 2 and Layer 3 per vertical: e.g. for restaurants → `Titan-Menu-Strategy`, `Titan-Inventory`, `Titan-Staff-Scheduling`, `Chef-AMG-Strategist`, etc.
3. Rewrite KB `03_domain_knowledge.md` per vertical
4. Keep Layer 1 Titan specialists mostly intact (SEO/CRO/Content/Social/Paid-Ads/Security/Reputation/Outbound/Proposal are cross-vertical)
5. Swap `SYSTEM_INSTRUCTIONS.md` vocabulary per vertical
6. Ship

Chambers specifically: Chamber OS modules (Meeting Intelligence PRO, Mobile Command, CRM, Social Engine, Email, Lead Nurture, Outbound, Teleprompter, Ticketing, Voice Callback, Reputation, Analytics, Self-Healing) map 1:1 to Layer 3 projects.

## 8. COST + SCALE NOTES

- 18 × ~20K-token KB = ~360K tokens total. At Anthropic prompt caching rates ($0.30/MTok cache read), that's $0.11 cached.
- Per agent call with cached KB: ~$0.027 (per project-backed-agents design doc §4)
- 18 projects × 50 calls/day × $0.027 = ~$24/day at steady AMG-scale internal use
- Scales to any vertical with identical cost structure — each client's 18-project fork amortizes cache hits within that client's session window

## 9. GOVERNANCE

- Every new project added to the base set → log decision to MCP, update this file, bump version
- Every KB material update → grader validation (Gemini Flash + Grok Fast dual ≥ 9.3 per §2 of standing rules)
- Every claude.ai project config change → Stagehand screenshot captured, filed under `/opt/amg-docs/agents/{name}/verification/YYYY-MM-DD.png`
- Quarterly KB refresh: `scripts/kb_freshness_audit.py` (to be built) flags agent KBs that haven't been touched in 90 days

## 10. FIRST-WAVE EXECUTION STATUS

| Phase | Status | Artifact |
|---|---|---|
| Template doc | ✅ SHIPPED 2026-04-17 | this file |
| 18 KB dir scaffold | 🟡 IN PROGRESS | `plans/agents/kb/{18 dirs}` |
| Alex KB (Layer 2 first) | 🟡 PARTIAL (3 files, 3.7K tokens) | `plans/agents/kb/alex/00-01-06.md` |
| 17 other KBs | 🔴 PENDING (CT-0417-HYBRID-C18 Phase 1) | — |
| 18 SI files | 🔴 PENDING | — |
| Stagehand cloning | 🔴 PENDING (Phase 2) | — |
| MCP integration | 🔴 PENDING (Phase 3) | — |
| Smoke tests | 🔴 PENDING (Phase 4) | — |
| Revere Phase 5 redesign | 🔴 PENDING (Phase 5) | — |

Continue execution: claim next phase as `CT-0417-HYBRID-C18-PHASE-{1..5}` from MCP sprint state.
