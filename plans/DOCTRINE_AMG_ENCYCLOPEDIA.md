# AMG ENCYCLOPEDIA — FULL SYSTEM INVENTORY

**Prepared for:** Solon Zafiropoulos, Founder & Sole Operator
**Version:** v1.5 (living document — surgical updates only)
**Updated:** 2026-04-15 (post 4-doctrine canonical ship + Perplexity DR valuation integration. v1.5 deltas vs v1.4: §17 + §16 + §11A.11 cross-ref to §19; renumbered prior §18-EXTERNAL-VALUATION duplicate to §19; v1.4 prior-state preserved as `git show v1.4-anchor:plans/DOCTRINE_AMG_ENCYCLOPEDIA.md`. v1.4 was: post overnight Titan queue burndown + pre-Hetzner doctrine chain — AIMG live, SECRETS-01 Phase A done, CT-0415-05 P1 hardened LIVE + P3 staged + P2 smoke-tested, Layer-4 v2 staged for sudo install, 4-doctrine adjudication chain specced with grok_review tool + Approval Broker + #titan-nudge queued, Hetzner 2× CX32 hard-gated on chain completion)
**Purpose:** Investor-grade comprehensive documentation of everything built, in queue, and on roadmap under the AMG umbrella
**Classification:** INTERNAL — contains trade secret tool names not authorized for client-facing use
**Instructions to reviewer (Perplexity):** Analyze this document to assess (a) total build cost if commissioned to a consultancy, (b) replacement cost of rebuilding from scratch, (c) Solon's market value as a Senior AI Engineer / AI Systems Architect / Visionary Founder

## LIVING DOCUMENT METADATA

| Field | Value |
|---|---|
| Document owner | Solon + EOM |
| Update cadence | After every major ship; at every sprint rollover; ad hoc when inventory changes |
| Source-of-truth precedence | MCP decisions > this doc > past thread context > memory |
| Patch style | Surgical str_replace only — no full rewrites unless explicitly approved |
| Version history | v1.0 2026-04-14 (initial) → v1.1 2026-04-14 late (+ Titan canonical specs, + Solon OS/Atlas layers, + MP-1→MP-4 mega prompts, + CORDCUT phases, + AHA moment, + 2-week ship horizon, + CT-ID inventory) → v1.2 2026-04-15 (+ AIMG LIVE in prod, + SECRETS-01 Phase A done, + CT-0415-05 P1 hardened LIVE + P3 staged + P2 smoke-tested, + Layer-4 v2 staged, + payment doctrine PaymentCloud/Durango primary — Paddle REJECTED, + sprint 88%→95%, + 8 new commits in Appendix B+D) |
| Next scheduled update | After CT-0415-05 Phase 2 (Channels) verified post-restart + PaymentCloud merchant approval clears |

---

## TABLE OF CONTENTS

1. Executive Summary
2. The AMG Umbrella — Corporate Structure & Two Product Lines
3. Foundational Infrastructure Layer (incl. Titan Canonical Performance Spec)
4. Persistent Cross-Agent Memory System (MCP Server)
5. Titan — The Builder/Ops Engine
6. EOM — The Strategic Brain
7. WoZ — The Seven Client-Facing Agents
8. AI Marketing Genius — The Managed Service Product
9. AI Memory Guard — The Consumer Product
10. Doctrines Shipped — The Reliability Layer
11. The Harness Layer — Deterministic Guardrails
11A. **Solon OS + Atlas + Titan — The Three-Layer Architecture (MP-1→MP-4, CORDCUT, CT-0406 Mega-Batch, AHA Moment, Hermes, Atlas Orb)**
12. Quality Enforcement System (QES) — 4-Layer Hallucination Defense
13. Trade Secret Compliance
14. Current State & MRR
15. Roadmap & In-Queue Work (incl. explicit 2-week ship horizon)
16. Mirroring Anthropic — Architectural Parallels
17. Build Cost Framing
18. Solon's Market Positioning

---

## 1. EXECUTIVE SUMMARY

AMG (AI Marketing Genius) is a Boston-based AI infrastructure company operating under the legal entity **Credit Repair Hawk LLC (Wyoming, EIN 85-2173241)** and doing business as "AI Marketing Genius." The company is a **solo-founder operation** run by Solon Zafiropoulos — 42, Boston/Medford MA, 17 years SEO/digital marketing background, former Oracle Fortune-50 enterprise sales, built 150+ amusement vending locations generating $1M annual revenue before transitioning to digital.

Under the AMG umbrella sit **two commercial product lines** and a **full production infrastructure stack** built solo in the last 12+ months:

- **AI Marketing Genius** — managed AI marketing service for local businesses ($497/$797/$1,497/mo tiers) + AI consulting/systems-integrator services ($2,500–$250,000+ projects)
- **AI Memory Guard** — cross-platform Chrome extension + MCP server giving users persistent memory + quality enforcement across Claude, ChatGPT, Gemini, Grok, Perplexity

Current MRR: **~$7,298/mo** across 3 active recurring clients. Infrastructure operating cost: **~$360/mo**. Margin posture: >90% on recurring revenue, >80% on project revenue.

**What makes this rare:** a solo operator has built infrastructure that typically requires a 5–15 person engineering team. Every layer — agents, memory, guardrails, automation, monitoring, doctrines, multi-tier enforcement — is production-deployed and actively serving clients today. Comparable enterprise stacks at AWS/Google/Big-4 cost $500K–$5M to build and $50K–$200K/month to operate.

---

## 2. THE AMG UMBRELLA — CORPORATE STRUCTURE & TWO PRODUCT LINES

### 2.1 Legal Entity

| Field | Value |
|---|---|
| Legal entity | Credit Repair Hawk LLC |
| State of formation | Wyoming |
| EIN | 85-2173241 |
| DBA | AI Marketing Genius |
| Operating address | 194 Forest St #2, Medford MA 02155 |
| Website | aimarketinggenius.io (migrating from aimarketinggenius.lovable.app) |
| Consumer product site | aimemoryguard.com |

### 2.2 Product Line A — AI Marketing Genius (B2B managed service)

**Tiered managed AI marketing subscriptions** for local service businesses (HVAC, dental, med-spas, family entertainment centers, real estate investors, auto repair, restaurants, law firms):

| Tier | Monthly | Inclusions | Target buyer |
|---|---|---|---|
| Starter | $497 | Single-platform management, $500–$1,500 ad spend, 4 agents (Alex, Jordan, Sam, Nadia) | Solo operators, <$300K revenue |
| Growth (anchor) | $797 | Dual-platform, $1,500–$5,000 ad spend, 6 agents + Maya + Nadia content | Established SMB, $300K–$2M revenue |
| Pro | $1,497 | Full suite, $5,000–$25,000 ad spend, all 7 agents including Riley (strategy, Opus) + Lumina (CRO, Opus) | Multi-location or premium SMB |
| Shield standalone (DIY reputation mgmt only) | $97 / $197 / $347 | Tiered reputation management without full AMG stack | Owner-operators wanting ORM only |

**14-day free trial, no credit card required.** Payment processor (canonical decision 2026-04-15): **PaymentCloud primary + Durango secondary (dual-MID strategy)**. Paddle REJECTED. Stripe permanently dead. PayPal blocked (Levar-affected accounts). Applications for PaymentCloud + Durango pending Solon submission — until live, interim path is manual invoice + ACH/wire (per Levar kickoff agenda 2026-04-16).

### 2.3 Product Line B — AMG as AI Systems Integrator / Consulting

**Project-based AI infrastructure work** for other agencies and mid-market businesses. **Engagement range: $5,000–$250,000+ per client depending on scope.** AMG operates simultaneously at every tier of this range, from quick-win audits to full-stack white-label Atlas deployments.

| Engagement size | Typical scope | Timeline | Customer profile |
|---|---|---|---|
| **$5,000–$10,000** | AI Architecture Audit + Roadmap, n8n Hyperautomation Sprint, single-domain integration | 1-3 weeks | Solo operator agencies, SMB founders piloting AI |
| **$15,000–$25,000** | Persistent Cross-Agent Memory System Build, Multi-Agent System Build-Out, Voice + chatbot stack | 3-6 weeks | Established agencies, mid-market businesses |
| **$25,000–$50,000** | Custom AMG-style fulfillment engine for one vertical, full GHL/Stagehand/n8n integration, white-label memory + agents | 6-10 weeks | Mid-market businesses with internal ops teams |
| **$50,000–$100,000** | Atlas Template Export — partial deployment (3-5 of 7 Atlas subsystems), branded for client, with monthly retainer | 8-14 weeks | Established agencies wanting to resell, multi-location SMB chains |
| **$100,000–$250,000+** | **Full Atlas deployment** — all 7 subsystems, custom Solon OS substrate trained on client's voice/SOPs/transcripts, full white-label, 6-12 month buildout, ongoing license retainer | 4-8 months | Enterprise-scale clients, agencies wanting full operating system, PE-rolled-up agency portfolios |

**Validated unit-economics tiers (subset detail):**

| Service | Price | Timeline | Deliverables |
|---|---|---|---|
| AI Architecture Audit + Roadmap | $2,500–$5,000 | 5–10 days | Current-state assessment, gap analysis, 90-day roadmap, exec slide deck |
| n8n Hyperautomation Sprint | $3,000–$8,000 | 2–3 weeks | End-to-end lead nurture + CRM + email sequences + AI qualification + monitoring |
| Multi-Agent System Build-Out | $10,000–$25,000 | 4–6 weeks | Agent role design, model-tier routing, QES guardrail, n8n + Stagehand + Supabase + VPS |
| Persistent Cross-Agent Memory System Build | $15,000–$25,000 | 3–4 weeks | Full MCP memory server deployment on client infra or hosted, Chrome extension, KB migration |
| Atlas Partial Deployment | $50,000–$100,000 | 8-14 weeks | 3-5 Atlas subsystems, white-labeled, monthly retainer included |
| **Atlas Full Deployment (white-label)** | **$100,000–$250,000+** | **4-8 months** | **All 7 Atlas subsystems + Solon OS substrate trained on client + ongoing license retainer** |
| Memory License + Advisory (ongoing) | $1,000–$5,000/mo | Ongoing | Hosted MCP, monthly health report, bi-weekly office hours, security patches |
| Hourly overflow | $300–$500/hr (niche $600–$1,000/hr) | Ad hoc | Hallucination guardrail design, persistent memory engineering |

Validated single-client Year 1 LTV range: **$72,500–$102,500** on full standard upsell ladder. **Full Atlas deployments push this to $150,000–$400,000+ Year 1 LTV** (license + retainer + custom build phases).

**The all-tiers-simultaneously thesis:** AMG is structured to operate at every dollar level from $5K quick-win to $250K+ full Atlas — without changing the underlying stack. The same Titan + harness + MCP + n8n + agents + Stagehand engine delivers a $5K audit, a $25K memory-system build, a $100K partial Atlas, and a $250K+ full white-label deployment. **The marginal cost of adding a higher-priced engagement is near-zero engineering effort** because the infrastructure already exists; what scales is project management discipline + client onboarding bandwidth.

### 2.4 Product Line C — AI Memory Guard (B2C consumer)

Cross-platform Chrome extension providing persistent memory + quality enforcement across Claude, ChatGPT, Gemini, Grok, Perplexity. **Currently in dogfooding (v0.1.0), not yet publicly launched.**

**Final tier matrix locked 2026-04-14:**

| Tier | Monthly | Engine | Daily QE cap | Our cost/mo | Margin |
|---|---|---|---|---|---|
| Free | $0 | GPT-4o-mini | 20/day | ~$0.12 (CAC) | marketing |
| Basic | $4.99 | GPT-4o-mini | 50/day | $0.30 | 94% |
| Plus | $9.99 | GPT-4o-mini | 150/day | $0.90 | 91% |
| Pro | $19.99 | GPT-4o-mini | 300/day | $1.80 | 91% |

**Product mechanics:**
- Chrome MV3 extension with content scripts per platform
- Captures every AI conversation exchange, extracts salient memories (facts, decisions, preferences, corrections, action items)
- Rule-based local extraction (free) + LLM-powered extraction (paid tiers)
- Stamps every memory with provenance (platform + thread_id + URL + exchange# + ISO timestamp)
- Semantic search via pgvector + hybrid_memory_search (BM25 + vector + RRF)
- Quality Enforcement (QE) layer: contradiction detection (cosine >0.85 + semantic divergence), staleness decay, deduplication
- "Thread Health" meter (marketed as "Hallucinometer") on left edge of AI platform page, 4 zones 🟢🟡🠠🔴 at 1–15/16–30/31–45/46+ exchanges
- Auto-carryover modal when thread enters red: "Let's start a fresh thread to maintain quality"
- 2-tone ding-DING audio chime (40% volume, plays once on red entry)
- "AI can make mistakes. Please double-check all responses." footer

---

## 3. FOUNDATIONAL INFRASTRUCTURE LAYER

### 3.1 Primary Production VPS

| Field | Value |
|---|---|
| Provider | HostHatch |
| IP | 170.205.37.148 |
| Specs | 12-core, 64GB RAM, 200GB NVMe |
| OS | Ubuntu 22.04 |
| Monthly cost | ~$60 |
| Uptime target | 99.9% |

### 3.2 Services Running on VPS

| Service | Purpose | Technology |
|---|---|---|
| Caddy reverse proxy | HTTPS on 443, TLS auto-renewal | Caddy v2 |
| n8n orchestration | Agent routing, workflow automation, webhooks | Docker, queue mode, Redis-backed |
| MCP server | Shared persistent memory layer | PM2 host-level (not Docker), Node.js, stateless mode, OAuth 2.1 |
| PostgreSQL | Backup for Supabase failover lane | Native |
| Redis | n8n queue backend + session cache | n8n-redis Docker container |
| Stagehand persistent browser | AI-driven browser automation | browser.aimarketinggenius.io |
| LiteLLM gateway | Multi-provider LLM inference (Anthropic + OpenAI + Google + X.ai) | Docker |
| Security watchdog | 17 async security checks, systemd service | Custom |
| Suricata IDS + Wazuh SIEM | Intrusion detection + security information/event management | Deployed 2026-04-13 |
| Hardening layer | fail2ban + UFW + AppArmor + seccomp | Deployed 2026-04-13 |
| 12 health timers | Distributed system health monitoring | systemd timers |
| Nightly backup suite | Supabase + MCP + configs → R2 encrypted | Custom + restic (WIP) |
| AMG Atlas API | Internal operator API (port 8084) | Node.js |
| titan-agent isolated user | Non-root execution user for autonomous operations | Linux user + sudoers |
| Kokoro TTS service | CPU-first voice synthesis (Hermes stack component) | Docker, titan-kokoro |
| RNNoise DSP | Audio denoising (Hermes stack component) | Embedded |
| Infisical | Self-hosted credential vault (upgrade to current version pending) | Docker |

### 3.2.1 TITAN CANONICAL PERFORMANCE SPEC (logged MCP 2026-04-12)

Authoritative parallelism and capacity ceilings on VPS (12-core, 64GB RAM), enforced by `lib/policy-loader.sh` + `bin/check-capacity.sh`:

| Metric | Ceiling | Notes |
|---|---|---|
| Concurrent Claude Code sessions | **12** | Multiple Titan instances possible |
| Concurrent heavy tasks | **8** | Aggregated across all lanes |
| Concurrent general workers/sub-agents | **10** | Task-tool sub-agents |
| Concurrent CPU-heavy workers | **4** | Dedicated CPU-bound lane |
| n8n branches per workflow | **20** | Queue-mode concurrency |
| Concurrent heavy n8n workflows | **3** | Policy-capped |
| **Total parallel n8n lanes** | **60** | = 20 × 3 |
| Concurrent LLM batches | **8** | Parallel batch pipeline |
| Max LLM batch size | **15 items** | Per batch |
| **Theoretical max concurrent LLM calls** | **120** | = 8 × 15 |
| CPU soft limit | 80% | Throttle threshold |
| CPU hard limit | 90% | Reject threshold |
| RAM soft limit | 50 GiB | Throttle threshold |
| RAM hard limit | 56 GiB | Reject threshold |
| Fast mode | default-on | 30–50% latency reduction (regression noted in Claude Code 2.0.76) |
| Model router | Haiku routine / Sonnet analysis / Opus synthesis | Per CLAUDE.md §17.7 |
| Streaming | default ON | First-token latency prioritized |

**n8n queue mode proof (2026-04-12):** `EXECUTIONS_MODE=queue`, `QUEUE_WORKER_CONCURRENCY=20`, `QUEUE_HEALTH_CHECK_ACTIVE=true`, `QUEUE_BULL_REDIS_HOST=n8n-redis`, `/healthz=200`, Redis PONG healthy.

### 3.3 Database Layer

| Database | Purpose | Project ID |
|---|---|---|
| Supabase AMG operator | WoZ agents, clients, tasks, messages, einstein credits | egoazyasyrhslluossli |
| Supabase AMG consumer | AI Memory Guard end-user memories | gaybcxzrzfgvcqpkbeiq |
| VPS PostgreSQL | Read-only failover for Supabase | (local) |

### 3.4 Object Storage & CDN

| Service | Purpose | Provider |
|---|---|---|
| Cloudflare R2 (amg-storage bucket) | Archive, credential vault, nightly backups | Cloudflare |
| Cloudflare Workers | Governance auditor + ops dashboard | Cloudflare |
| Cloudflare Email Routing | info@aimarketinggenius.io + hello@aimemoryguard.com | Cloudflare |

### 3.5 Credential & Secrets Management

| System | Purpose |
|---|---|
| Infisical (self-hosted) | Centralized credential vault (upgrading to current version is in backlog) |
| /etc/amg/mcp-server.env | Active runtime credentials |
| /etc/amg/credential-registry.yaml | Per-credential classification: auto-rotate permitted, blast radius, rotation procedure |
| Cloudflare R2 credentials/ | Encrypted off-VPS credential backup |

### 3.6 Monitoring, Dashboards & Health Endpoints

Dashboards currently live (200 OK verified 2026-04-13):

- `/mobile` — mobile-optimized operator dashboard
- `/desktop` — desktop operator dashboard
- `/orb` — Governance Health Score display
- `/health` — aggregated system health

**Governance Health Score: currently 85.0** (captured 2026-04-13, adversarial-reviewed by Perplexity A-grade + Grok 9.0+).

### 3.7 CI/CD + Code Mirroring

| Lane | Purpose |
|---|---|
| Mac local workspace (~/titan-harness) | Primary dev environment |
| VPS bare Git mirror | Deploy target + code redundancy |
| GitHub AiMarketingGenius/aimarketinggenius | External code mirror (stale for site, active for harness) |
| Mac → VPS auto-mirror | Every commit pushed to both |

**Total commits tonight's session (2026-04-14):** 9 (9eb08da, df5ee2e, 780d90d, 56d5064, 2353539, ce9c8db, 06f664d, deaac8a, ddc6c30) — all A-graded by Perplexity adversarial review.

---

## 4. PERSISTENT CROSS-AGENT MEMORY SYSTEM (MCP SERVER)

### 4.1 The MCP Server (memory.aimarketinggenius.io)

The single most differentiated piece of the AMG stack. **No competing agency offers this today.** Closest comparable is AWS AgentCore Memory (enterprise-facing, developer-dependent, expensive).

| Component | Detail |
|---|---|
| URL | https://memory.aimarketinggenius.io |
| Transport | Stateless HTTP with OAuth 2.1 |
| Runtime | PM2 host-level on VPS |
| Database | Supabase egoazyasyrhslluossli, pgvector extension, hybrid BM25+vector+RRF search |
| Embedding model | Ollama nomic-embed-text (local, zero per-call cost) |
| Protocol anchor | Two-of-two integrity (R2 + MCP), semver-versioned, SHA256-hashed |
| Memory types | fact, decision, preference, correction, action, narrative, episodic, entity |
| Rule scoping | eom / titan / both, with P-priority levels (P10 highest → P1) |

### 4.2 MCP Tool Surface (20+ tools)

- `get_bootstrap_context` — injects standing rules + sprint state + recent decisions into new threads
- `search_memory` — semantic search across all memories
- `log_decision` — real-time decision logging with conflict detection
- `queue_operator_task` — structured task queue with priority, approval workflow, tier classification
- `update_task` — task status updates, progress logging
- `claim_task` — task assignment for autonomous execution
- `get_task_queue` — queue visibility
- `get_sprint_state` — current sprint kill chain + blockers + completion %
- `update_sprint_state` — sprint progression
- `generate_carryover` — automatic carryover document generation
- `flag_blocker` / `resolve_blocker` — blocker management
- `get_recent_decisions` — decision history for context
- `perplexity_review` — automated Perplexity adversarial review
- `get_static_anchor` — protocol anchor fetch (R2 static storage)
- `update_static_anchor` — atomic protocol anchor update
- `scan_for_injection_attempt` — prompt injection pattern detection
- `compact_protocol_document` — tokenization for protocol docs
- 4 more v1.10 tools registered server-side

### 4.3 Memory System Standing Rules (P10 — Highest Priority, Auto-Injected)

Approximately 20+ standing rules active, including:
- Bootstrap protocol (every new EOM thread must receive context injection)
- DR prompt archive discipline (every drafted research prompt logged same-turn)
- Trade secret enforcement (never expose tool names client-facing)
- Tier A/B/C auto-continue policy with grade gating
- MCP sprint state as single source of truth
- Titan autonomy + Tier B/C safety gating
- Speed discipline (CLI-first, batched SSH, parallel ops, fresh context at 25 exchanges)
- First-Pass Verification Gate (8-point check on every deliverable)
- Thread Safety Gate (🟢🟡🠠🔴 depth tracking)
- Self-audit every output (grammar, math, contradictions, trade secrets, formatting)

---

## 5. TITAN — THE BUILDER/OPS ENGINE

### 5.1 What Titan Is

Claude Code CLI (Opus 4.6, 1M context) running on Solon's Mac in `~/titan-harness`. Operates as the **autonomous executor** with physical access to:

- Shell / bash on Mac
- Persistent Stagehand browser (browser.aimarketinggenius.io)
- VPS SSH (root access)
- Supabase service-role keys
- Cloudflare R2 + Workers
- All API keys (Anthropic, OpenAI, Perplexity, Grok, Google, x.ai)
- Git commit authority (Mac + VPS + GitHub)
- Slack workspace (posting authority)

### 5.2 Titan Harness Layer

Deterministic code wrapping Titan:

| Component | Purpose |
|---|---|
| `hooks/session-start.sh` | Fast mode auto-enable, MCP bootstrap, standing rule reload |
| `hooks/session-end.sh` | State capture, HMAC-signed resume state, carryover generation |
| `hooks/user-prompt-counter.sh` | Per-session exchange counter, 25-exchange auto-restart hook |
| `bin/titan-notify.sh` | 3-path Slack notifier (3300 port → Aristotle → deferred queue) |
| `bin/titan-restart-capture.sh` | Atomic HMAC-signed state capture |
| `bin/titan-restart-launch.sh` | launchd-invoked spawner (tmux/iTerm/Terminal) |
| `bin/titan-resume-boot-prompt.md` | Hard-coded MCP bootstrap on resume |
| `bin/install-titan-autorestart.sh` | launchd plist installer for 25-exchange auto-restart |
| `bin/escape-hatch-verify.sh` | 6-item preflight (SSH key alive, HostHatch console, root pw tested, VPS snapshot <24h, backup key 2nd location, fail2ban Mac-IP whitelist) |
| `bin/opa-deploy.sh` | OPA policy deployment for enforcement gates |
| `bin/opa-confirm-enforce.sh` | Nonced-ack enforce-mode flip |
| `bin/check-capacity.sh` | Pre-flight capacity validation |
| `bin/harness-preflight.sh` | Pre-task environment validation |
| `lib/fast-mode.sh` | Fast-mode default-on env propagation |
| `lib/parallel_dispatch.py` | Parallel sub-agent dispatch (in optimization) |
| `lib/exchange_counter.sh` | Per-session turn counting |
| `~/.claude/agents/fast-probe.md` | Scoped sub-agent (Bash only, Haiku, zero MCPs) |
| `~/.claude/agents/bash-worker.md` | Scoped sub-agent (Bash+Read+Glob+Grep, Haiku, zero MCPs) |

### 5.3 Titan Capabilities Documented in CLAUDE.md

- Fast mode default-on (30–50% latency reduction on routine traffic)
- Model router: Haiku for routine bash/grep/read, Sonnet for analysis, Opus only for synthesis/architecture
- Streaming default ON (first-token latency, not total)
- Parallel sub-agent dispatch via Task tool with custom agent types
- n8n queue mode integration for async work
- Perplexity adversarial review auto-consult on blockers
- Auto-continue policy v2 (Tier A/B/C grade-gated autonomy)

---

## 6. EOM — THE STRATEGIC BRAIN

### 6.1 What EOM Is

Claude.ai Opus project ("Executive Operations Manager"). **Stateless per session, but hydrated via MCP bootstrap on every thread open.** Functions as:

- Router/Orchestrator brain
- Builder/Architect brain (Claude project design, SI writing, KB architecture)
- Researcher/Synthesizer brain (Perplexity + Grok cross-validation workflows)
- Automator/Systematizer brain (SOPs, checklists, Pipedream/Viktor integrations)

### 6.2 EOM Knowledge Base (~10 core docs, ~15K+ lines total)

| Doc # | Name | Purpose |
|---|---|---|
| 01 | Project Routing & Arsenal Reference | Map of 16+ specialist Claude projects + routing rules |
| 02 | Claude Project Builder Framework v2.0 | 7 project patterns, 6-dimension scoring rubric |
| 03 | Research & Intelligence Protocols | CIA SATs, OODA, ACH, 40-Point Rule, cross-validation |
| 04 | WoZ Architecture & Client Operations | Client lifecycle, SLAs, agent roster, quality gates |
| 05 | AMG Business Operations Reference | Pricing, revenue, costs, margins, verticals, trade secrets |
| 06A | Viktor & Tool Economics | Tool routing, credit monitoring |
| 06B | Automation & Process Design | SOP templates, Lovable one-prompt rule, HITL reduction |
| 07 | ADHD-Optimized Operations Framework | Body double, ultradian rhythms, overwhelm circuit-breaker |
| 08 | Quality Assurance & Continuous Improvement | Operational scoring rubric, self-audit protocol |
| 09 | KB Manifest v3.3 | Complete KB index, lifecycle schedule |
| 10 | Thread Safety & Anti-Hallucination Protocol | Depth tracking, per-output hallucination checks, carryover reqs |

### 6.3 Specialist Claude Projects (16+ projects in ecosystem)

- **SEO | Social | Content** — SEO copy, GBP posts, blogs, keyword research
- **CRO / Lumina** — Landing page optimization, A/B testing, conversion audits
- **Paid Ads Strategist** — Google/Meta ads, PPC, ROAS optimization
- **Shield Reputation Management** — Review monitoring, ORM, crisis response
- **Outbound LeadGen Advisor** — Cold outreach, LinkedIn, pipeline build
- **Creative Hit Maker** — Music production, beats, lyrics
- **Jingle Maker** — Commercial audio, brand music
- **Solon's Promoter** — Music distribution, Spotify, DistroKid
- **Croon AI** — Dating app development
- **Solon Therapy** — Personal mental health / stress
- **AI Prompt Creator** — Prompt engineering, meta-prompts
- (5+ additional specialist projects)

---

## 7. WOZ — THE SEVEN CLIENT-FACING AGENTS

Each agent has a distinct persona, model tier, and system prompt. Client sees named agents; backend is Claude API calls routed through Supabase + Edge Functions + n8n.

| Agent | Role | Default Model | Tier Access | Purpose |
|---|---|---|---|---|
| **Alex** | Account Manager | Haiku | All tiers | Concierge — opens/closes every interaction, routes to specialists |
| **Maya** | Content Specialist | Sonnet | Growth+ | Blog posts, social captions, email campaigns |
| **Jordan** | Reviews/Reputation | Haiku | All tiers | Review monitoring, response drafting, reputation repair |
| **Sam** | SEO/Rankings | Sonnet | Starter+ | Technical SEO, keyword tracking, GBP optimization |
| **Riley** | Strategy/Intel | Opus | Pro only | Campaign strategy, competitive analysis, growth roadmaps |
| **Nadia** | Onboarding | Haiku | Growth+ | Business intake, account setup, launch planning |
| **Lumina** | CRO/Conversion | Opus | Pro only | Landing page audits, A/B testing, conversion optimization |
| *Ops (internal)* | Fallback | Sonnet | Never client-facing | Routing fallback when agent field is empty/unrecognized |

**Voice principle across all agents:** "Hear the smile" — warm, genuine, professional. Occasional emoji, never corny. First-name only (privacy). Concierge protocol: Alex opens and closes every client interaction; specialists enter pre-briefed, <1 second perceived latency on handoffs.

---

## 8. AI MARKETING GENIUS — THE MANAGED SERVICE PRODUCT

### 8.1 What's Delivered at Each Tier

**Starter ($497/mo):**
- Monthly SEO audit and optimization report
- 10 keywords tracked
- Competitor analysis & intel reports (2 competitors)
- Reputation management (review monitoring + 10 responses/mo)
- 4 agents: Alex, Jordan, Sam, Nadia
- Monthly GBP optimization
- Campaign coordination
- Single-platform focus (typically Google)
- Ad spend range: $500–$1,500

**Growth ($797/mo — anchor tier):**
- Everything in Starter
- 4 pieces of long-form content per month (blog posts/social)
- AI chatbot on website
- Keyword research & tracking (20 keywords)
- Competitor analysis & intel reports (5 competitors)
- 20 keywords tracked
- Maya (content) added
- Nadia (onboarding) added
- Dual-platform (Google + Meta typically)
- Ad spend range: $1,500–$5,000

**Pro ($1,497/mo):**
- Everything in Growth
- 8+ long-form content pieces + 20 social posts
- Full campaign management
- Keyword research & tracking (50 keywords)
- 30 keywords tracked
- Competition analysis & intel reports (10 competitors)
- Riley (CDO & conversions) added
- Paid ads management (Meta + Google)
- Full team access
- Lumina CRO audits (up to 4 per month, standalone available otherwise)
- Full ad spend range: $5,000–$25,000

### 8.2 Shield Standalone Reputation Management

Sold separately for owner-operators wanting reputation management only:

| Tier | Monthly | Inclusions |
|---|---|---|
| Starter | $97 | 1 location, automated review requests |
| Growth | $197 | Multiple locations, negative review suppression |
| Pro | $347 | Enterprise-scale, full reputation command center |

### 8.3 Active AMG Clients

| Client | Tier / Revenue | Notes |
|---|---|---|
| Shop UNIS (Kay/Trang) | ~$3,500/mo custom | Premium e-commerce client, active |
| Paradise Park Novi | $1,899/mo | Family entertainment center (FEC), active |
| Revel & Roll West (James/Ty) | $1,899/mo | FEC, active |
| JDJ Investment Properties (Levar) | Founding member, pending | RE investor "We Buy Houses", Monday 3PM kickoff |

**Current MRR: ~$7,298/mo.**

### 8.4 Proven Client Outcomes

- **+$70K revenue Year 1** — B2B wholesale Shopify client
- **+13,100% phone calls in 60 days** — HVAC client
- **+289% search clicks** — Entertainment venue
- **Google 3-Pack ranking achieved in 60 days** — Multiple verticals

---

## 9. AI MEMORY GUARD — THE CONSUMER PRODUCT

### 9.1 Product Overview

Chrome MV3 extension + supporting Supabase + optional MCP proxy. Provides:

- **Cross-platform memory capture** on Claude, ChatGPT, Gemini, Grok, Perplexity
- **Salient info extraction** (facts, decisions, preferences, corrections, actions)
- **Provenance stamping** (platform + thread + URL + exchange# + timestamp)
- **Semantic + hybrid search** across all memories
- **Quality Enforcement (QE)** — contradiction detection, staleness decay, deduplication
- **Thread Health meter ("Hallucinometer")** — visual warning as thread deepens
- **Auto-carryover** — when thread enters red, system generates summary + prompts fresh thread
- **Audio chime** — 2-tone ding-DING at 40% volume, plays once on red-zone entry

### 9.2 Architecture

```
User's Browser
    │
    ▼
Chrome MV3 Extension (per-platform content scripts)
    │
    ├── Local rule-based classification (regex + spaCy signals)
    │   ├── DECISION_SIGNALS: "decided to", "we will", "going to"...
    │   ├── FACT_SIGNALS: "is", "are", "costs", "located at"...
    │   ├── PREFERENCE_SIGNALS: "prefer", "like", "don't want"...
    │   └── CORRECTION_SIGNALS: "actually", "correction", "wrong"...
    │
    ├── [Paid tier] LLM extraction via GPT-4o-mini
    │
    └── Supabase consumer instance (gaybcxzrzfgvcqpkbeiq)
        ├── memories table (pgvector embeddings)
        ├── Hybrid search: BM25 + pgvector + RRF
        ├── Provenance source_stamp per row
        └── RLS per-user auth
```

### 9.3 Design Spec (CT-0405-06)

**Thread Health Meter:**
- Fixed left edge, 8px collapsed → 52px expanded on hover, 65% viewport height
- 4 zones: 🟢 Fresh (1–15) / 🟡 Warm (16–30) / 🠠 Hot (31–45) / 🔴 Danger (46+)
- Color-coded meter fill, pulse animation in warm/hot, `dangerGlow` in red

**Extension toolbar icon states:**
- Grey outline = inactive
- Blue solid = capturing
- Blue + green ✓ badge = QE active, no issues
- Blue + red number badge = QE contradiction(s) detected
- Red pulse + "!" = thread danger zone

**Auto-carryover modal (red zone trigger):**
> "Let's start a fresh new thread to maintain the highest quality output from your LLM! And don't worry — we'll start the new thread with a detailed summary of this conversation so it continues easily!"

**Footer on every AI platform:**
> "AI can make mistakes. Please double-check all responses."

### 9.4 Tier Matrix (FINAL — locked 2026-04-14)

Single-engine simplicity: GPT-4o-mini across all tiers. Volume differentiates paid tiers. Free tier is a taste.

| Tier | Price | Daily cap | Monthly API cost | Margin |
|---|---|---|---|---|
| Free | $0 | 20/day | ~$0.12 (CAC) | marketing |
| Basic | $4.99 | 50/day | $0.30 | 94% |
| Plus | $9.99 | 150/day | $0.90 | 91% |
| Pro | $19.99 | 300/day | $1.80 | 91% |

**Cost cap enforcement:** $5/day hard ceiling per user, $3/day Slack alert, auto-pause at $5.

### 9.5 AIMG Build Roadmap (45 steps, Phases A–E)

- **Phase A — Core extraction & storage** — MV3 scaffold, Supabase schema, content scripts for Claude + ChatGPT
- **Phase B — Semantic recall & UI** — pgvector integration, search UI, memory detail view
- **Phase C — Cross-platform & QE** — Gemini + Grok + Perplexity content scripts, QE layer, conflict detection
- **Phase D — Monetization & polish** — Paddle integration, tier enforcement, LLM extraction for Pro, digest emails
- **Phase E — iOS mobile** — SwiftUI companion app, Share Sheet, keyboard extension, Apple IAP

### 9.6 Scaling Plan

| Users | Vectors/year | Action |
|---|---|---|
| <10K | <100M | pgvector + Supabase Pro ($25/mo) |
| 10–50K | 100M–500M | Supabase Team ($599/mo), Supavisor pooling, read replicas |
| 50K+ | 500M+ | Shard by user_id_hash (10 shards), evaluate dedicated vector service |
| 100K+ | 1B+ | Vector Buckets or dedicated Pinecone/Weaviate for embeddings, relational metadata stays in Postgres |

### 9.7 Current State (2026-04-15) — LIVE IN PRODUCTION

**CT-0414-09 Phase 2 SHIPPED LIVE 2026-04-15 03:01 UTC.** Edge function `aimg-qe-call` deployed to Supabase project `gaybcxzrzfgvcqpkbeiq`. Smoke test HTTP 200 in 4.5s. Free-tier daily cap counter active (used_today=1, daily_cap=20, remaining=19). Cost reconciliation working (actual_cost_usd=$0.00003705 per call). Atomic `aimg_try_increment` RPC race-safe. Platform cost ledger + $5/day hard cap + $3/day Slack alert all live.

**Stack live (production-deployed components):**
- Edge function: `https://gaybcxzrzfgvcqpkbeiq.supabase.co/functions/v1/aimg-qe-call`
- Tables: `public.aimg_usage` (per-user-per-day), `public.aimg_platform_daily` (single-row platform ledger)
- RPCs: `aimg_try_increment` (atomic check-and-increment, race-free), `aimg_reconcile_cost` (post-OpenAI token reconciliation)
- Secrets: `OPENAI_API_KEY` set on project, cap envs `AIMG_PLATFORM_DAILY_CAP_USD=5`, `AIMG_PLATFORM_DAILY_ALERT_USD=3`, `AIMG_COST_PER_CALL_USD=0.0002`
- Vault: `/etc/amg/aimg-supabase.env` mode 0600 root:root with 5 vars (project_ref, URL, anon, service_role, PAT)

**Extension-client (CT-0414-09 Item 1, commit 1a65d4f):** rate-limit middleware + 21-case integration test suite at `config/aimg/tier-router/extension-client/`. Perplexity sonar-pro adversarial review **A**, 0 blocking issues. All 21 tests pass on `node --test`. Modules: `tier-router-client.js`, `thread-health-widget.js` (4 zones 🟢🟡🟠🔴 at 1-15/16-30/31-45/46+), `chime.js` (2-tone 880→1175Hz WebAudio, 40% vol, plays once on red entry), `carryover-modal.js` (locked copy + upsell + pause banner), `rate-limit-middleware.js` (local cap precheck + token-bucket pacing + platform-pause cache + in-flight dedup + usage shape shim), `aimg-client.js` (public API).

**Dogfood baseline preserved:** 8 memories captured 2026-04-14 from Perplexity (1 high-quality, 1 hard bug, 6 noise) preserved as CT-0414-06 Phase 1 baseline via `bin/aimg-preserve-baseline.sh` → `/opt/amg/aimg/audit-evidence/phase1-baseline-2026-04-14.json` + companion quality verdict markdown. Feeds the rebuild plan.

**Outstanding:** Solon wires `extension-client/src/` into `~/Desktop/mem-chrome-extension/` (manifest.json content_scripts import) when ready to ship to Chrome Web Store.

---

## 10. DOCTRINES SHIPPED — THE RELIABILITY LAYER

AMG has shipped multiple comprehensive operational doctrines this year. Each is a 1,500–2,500 line design document backed by framework research (Google SRE, Netflix Chaos Engineering, IBM MAPE-K, AgentOps 2025) and cross-validated 9+/10 by Perplexity + Grok dual adversarial review.

### 10.1 DR-AMG-RESILIENCE-01 (complete, 5/5 deltas shipped)

**~2,100 lines. 10 sections. 12 domains fully specced. 7 adversarial 3AM scenarios.**

Covers:
- Three-tier response model (Tier 0 silent heal, Tier 1 notify-after, Tier 2 page now)
- 7 universal principles (Single Source of Truth, Bounded Autonomy, Fail Loud Never Silent, Defense Against Cascade, Idempotent Remediation, Learning Budget, ADHD-Compatible Signal Design)
- 12 domain specs (git mirror, disk hygiene, R2 lifecycle, Slack signal, voice/WebSocket, Supabase failover, Caddy recovery, n8n error classification, MCP janitor, Titan POWER OFF, API spend caps, core process health)
- Central Watchdog architecture (single Node.js daemon, 5-min hold mechanism)
- Structured JSONL incident learning loop
- 5-phase implementation roadmap (~47 build hours)
- 7 domain-specific SLOs with error budgets

### 10.2 DR-AMG-SECURITY-01 (all 3 phases complete)

Covers:
- Wazuh FIM + active response
- Heartbeat monitoring
- Backup script (deployment pending cron-enable)
- Caddy logging
- UFW drift detection
- titan-agent user isolation
- MCP auth hardening
- n8n hardening
- Secrets remediation
- RLS audit (33 tables flagged)
- STRIDE threat model
- Watchdog load test
- Remediation audit logging
- GDPR edge case handling
- 4-source security digest

### 10.3 DR-AMG-GOVERNANCE-01 (all 3 phases A-graded by Perplexity, 9.0+ by Grok dual-engine)

Covers:
- Behavioral baseline definition
- Drift scoring (Kolmogorov–Smirnov statistical test)
- Governance dashboard
- Governance Health Score (currently 85.0/100)
- Anti-pattern monitoring (M2–M7)
- Weekly review cadence
- Sister doctrine integration
- Red team testing (3 caught, 5 partial)

### 10.4 DR-AMG-ENFORCEMENT-01 v1.4 (audit-mode complete, enforce flip pending)

**The 4-gate lockout-prevention doctrine.** Built tonight to prevent a repeat of the 48-hour VPS lockout from Apr 13–14.

| Gate | Purpose | Commit |
|---|---|---|
| Gate #1 v1.1 | Hash-pinned pre-proposal gate (blocks fake SSH-scope commits) | df5ee2e |
| Gate #2 v1.1 | HMAC state + audit chain + 5-min hypothesis timer | 780d90d |
| Gate #3 | SSH forensic template (read-only, 9-step runner) | 9eb08da |
| Gate #4 v1.2 | OPA policy + chrony clock-sync + nonced-ack enforce flip + 7-day auto-revert tail | 2353539 |
| escape-hatch-verify | 6-item preflight checklist (SSH key, HostHatch console, root pw, snapshot <24h, backup key location, fail2ban whitelist) | 56d5064 |

Enforce-flip procedure (pending Solon): 4 escape-hatch attestations → `install-gate4-opa.sh` → 24h audit mode observation → signed hash ack via `opa-confirm-enforce.sh` → enforce mode with 7-day observe tail + auto-revert still armed.

**v1.4 shipping scope (CT-0415-06, Tier A pre-approved):** tightens Gate #4 OPA policy surface (deny-by-default on all mutating SSH scopes absent pre-proposal hash match); wires the escape-hatch preflight into the `harness-conflict-check.sh` pre-write hook so structural commits cannot proceed with stale attestations; adds `bin/enforcement-status.sh` for one-line `ENFORCEMENT: audit|enforce|reverting|auto-reverted` read; logs every gate trip to MCP `log_decision` with tag `enforcement_gate`. Gate #4 enforce-mode flip is still Solon-gated (Hard Limit). **v1.4 ship unblocks CT-0414-07 + CT-0414-08 downstream chain** per the full chain in §10.5.

### 10.5 Queued Doctrines — 4-Doctrine Adjudication Chain (CT-0414-08)

The adjudication chain runs in this strict order (each doctrine is prerequisite to the next):

1. **DR-AMG-ACCESS-REDUNDANCY-01** — secondary provider lane for VPS/DB access (Hetzner 2× CX32 as active/active secondary to HostHatch primary; DNS failover + shared-nothing state; read-replica Postgres)
2. **DR-AMG-UPTIME-01** — 99.95% SLO design with error budget (monthly budget 21.6 min downtime; burn-rate alerts at 2%/5%/10%)
3. **DR-AMG-DATA-INTEGRITY-01** — checksums, snapshot verification, restore drills (daily restic+R2 checksum validation; weekly restore smoke-test; quarterly full restore drill)
4. **DR-AMG-RECOVERY-01** — disaster recovery runbook (RPO ≤ 1h, RTO ≤ 4h; full regional failover playbook; credential revocation + re-provision)

**Adjudication protocol:**
- Each DR is routed through `grok_review` MCP tool (see §10.6 Phase 2.1).
- **A-grade floor is 9.4/10** (matches `policy.yaml war_room.min_acceptable_grade`).
- On A-grade pass: doctrine ships canonical to `/opt/amg/docs/DR_<NAME>_v1.md` on VPS, mirrored to `plans/` on Mac + GitHub via Hercules Triangle.
- On sub-A grade: iterate per §12 war-room rounds (max 5), then re-route through grok_review.
- **Hetzner 2× CX32 provisioning is hard-gated on all 4 doctrines shipping canonical.** No infra spend until adjudication complete.

**Dependencies:** blocks on `grok_review` MCP tool being live (CT-0414-07 Phase 2.1). `grok_review` itself blocks on DR-AMG-ENFORCEMENT-01 v1.4 shipping (CT-0415-06) per its own pre-flight gate.

**Full chain:** CT-0415-06 (ENFORCEMENT-01 v1.4) → CT-0414-07 (grok_review + mailbox + Channels listener) → CT-0414-08 (4-doctrine adjudication) → Hetzner 2× CX32 provisioning → secondary-lane cutover.

### 10.6 CT-0415-05 Titan Autonomy Completion Sprint (2026-04-15) — PARTIAL SHIP

Closes the remaining ~35% of the autonomy stack. ~65% already existed pre-sprint. DR-supplied working code from Solon 2026-04-15 covered three gaps; integrated into harness this overnight session.

**Phase 1 — 25-Exchange Auto-Restart (LIVE on VPS, hardened):**
- 4 hooks installed in `/opt/titan-harness-work/.claude/hooks/`: `exchange-counter.sh` (Stop, async, persistent state at `/var/lib/titan-restart/`, `flock` race-safe per 30-parallel test), `pre-compact-capture.sh` (PreCompact, captures last 5 turns to MCP), `session-boot.sh` (SessionStart, writes session.pid for narrow watcher targeting, resets counter), `restart-watcher.sh` (PID-targeted SIGTERM, no broad pgrep risk).
- systemd unit `titan-restart-watcher.service` active + enabled.
- E2E test PASS: serial 25 + parallel 30 invocations both trigger signal → watcher consumes within 5-6s → stale-PID detection skips kill.
- Hardening per Perplexity sonar-pro grade-C feedback: persistent state survives reboot, `flock` prevents counter race, session.pid prevents false-positive process kill.

**Phase 2 — Claude Code Channels (smoke-tested, ready):**
- `titan-channel.ts` Bun MCP server at `/home/amg/titan-channel/titan-channel.ts`, listens on 127.0.0.1:8790.
- `.mcp.json` registered at project root for Claude Code auto-load.
- Smoke test PASS: `/healthz` returns `{ok:true}`, POST with allowed `X-Source: monitor` accepted + task_id assigned + `notifications/claude/channel` MCP notification fired, POST with `X-Source: attacker` rejected 403.
- Architecture: n8n/Slack/external → POST 8790 → MCP notification → Claude Code session sees `<channel source="...">` tag → Titan executes → replies via webhook through `reply` tool. Zero polling.
- Permission relay listener pre-wired for forwarding to Slack bot (localhost:3300) when `notifications/claude/channel/permission_request` arrives.

**Phase 2.1 — `grok_review` MCP tool + mailbox + hybrid retrieval + Channels listener (CT-0414-07, big infra build):**

The `grok_review` MCP tool is the adjudication plumbing that makes CT-0414-08 (4-doctrine ship) and all future A-grade doctrine gating possible. It is the *second independent reviewer* in the L2 adversarial-review layer (§8.3) when Slack-Aristotle is unavailable or when the doctrine explicitly demands Grok rather than Perplexity (cross-provider blind-spot coverage).

| Component | Purpose | Implementation target |
|---|---|---|
| `grok_review` tool surface | MCP tool: `grok_review(artifact_path, rubric, context_files=[])` → returns `{grade, dimension_scores{}, risk_tags[], rationale, remediation}` | Added to `titan-channel.ts` tool registry; routes via LiteLLM gateway `grok-4-fast-reasoning` model |
| Mailbox pattern | Async durable outbox: artifact + rubric dropped in `/var/lib/titan-channel/mailbox/outbox/`, Grok review result written to `inbox/<artifact_hash>.json`. Survives both-side restarts. | Filesystem-backed FIFO + inotify watcher + MCP resource exposure |
| Hybrid retrieval | Grok gets semantic KB snippets (via `search_memory`) + structural context (code paths, prior grades) in a single retrieval bundle, not just raw artifact text | `lib/hybrid_retrieval.py`: MCP `search_memory` + AST-aware code slicer + doctrine-freshness pointer injection |
| Channels listener | New `X-Source: grok-reviewer` allowlisted source on port 8790. Grok result POSTs back as channel notification, Titan session auto-consumes via `<channel source="grok-reviewer">` tag. | Allowlist entry in `titan-channel.ts` + response-handler branch in main session loop |

**Standing rule:** every doctrine/plan requiring A-grade ship (per §12 Idea Builder compliance) that cannot route through Slack-Aristotle MUST route through `grok_review` before Titan labels it "ready for Solon." **Titan self-grade fallback is a last resort and MUST be marked `PENDING_GROK_REVIEW` in the grading block.**

**Pre-flight gate:** `grok_review` tool ship is blocked on ENFORCEMENT-01 v1.4 canonical (CT-0415-06) because the mailbox + channel allowlist additions are structural harness changes that must pass the tightened Gate #4 OPA policy.

**Phase 3 — Mac Desktop Control via Tailscale (STAGED, awaits Solon Tuesday morning):**
- `config/tailscale-acl.json` (vps/mac/phone tags + ACL).
- `config/mac-sshd-config-additions.txt` (sshd_config patch for Mac).
- `launchd/io.titan.nosleep.plist` + `bin/install-titan-nosleep-mac.sh` (caffeinate + pmset).
- `bin/sync-to-mac` rsync alias (over Tailscale SSH).
- `plans/DR_PHONE_THEFT_REVOCATION_RUNBOOK.md` (6-step priority chain, ephemeral-key revocation).
- `plans/deployments/CT-0415-05_PHASE3_TAILSCALE_2026-04-15.md` (one-paste runbook, self-grade 9.58 A).
- Solon-side prerequisites: Tailscale browser auth on 3 nodes, Mac sudo password for sshd_config patch + caffeinate launchd install.

### 10.7 SECRETS-01 Phase A (2026-04-15) — SHIPPED

**Tier C credential rotation complete.** Crontab line 2 plaintext `SUPABASE_SERVICE_ROLE_KEY` JWT for project `egoazyasyrhslluossli` (mem-pipeline-worker cron `*/10 * * * *`) eliminated.

- Generated new `sb_secret_Qocmk...` via Supabase Management API POST `/v1/projects/egoazyasyrhslluossli/api-keys` (name=`titan_rotated_20260415`, type=secret, secret_jwt_template=service_role).
- Wrote `/etc/amg/jwt.env` mode 0600 root:root with `EGOAZYASYRHSLLUOSSLI_SERVICE_KEY=<new>`.
- Crontab line 2 rewritten to `. /etc/amg/jwt.env && curl ... -H "Authorization: Bearer $EGOAZYASYRHSLLUOSSLI_SERVICE_KEY" ...`.
- Manual trigger HTTP 200 verified.
- Old JWT prefix `eyJhbGci` (hash16 `b31fdd42803a7e45`) → New key prefix `sb_secret_Qocmk` (hash16 `b4f727f713bc9b13`). Rotation ts `2026-04-15T03:07:52Z`.

**Phase B (deferred to Solon-awake window):** `/etc/amg/mcp-server.env` still contains the legacy JWT (verified identical hash). Migration steps: update mcp-server.env → restart memory.aimarketinggenius.io MCP server (~5s gap) → DELETE legacy via Mgmt API. Best done when Solon can observe the MCP restart.

### 10.8 Layer-4 Mac App Permission Fix v2 (2026-04-15) — STAGED

Diagnosed: GitHub issues anthropics/claude-code#29026 + #36168 + #36497 + #40852 confirm Mac Claude.app v2.1.79+ regression where `defaultMode=bypassPermissions` + `permissions.allow=[*]` user-config has no effect — every tool call still prompts.

**Real fix (per Anthropic docs code.claude.com/docs/en/permissions):** create system-level `/Library/Application Support/ClaudeCode/managed-settings.json` — managed settings cannot be overridden by user/project settings.

- Staged at `config/claude-managed-settings.json` (correct schema: defaultMode=bypassPermissions + permissions.allow with proper CamelCase tool names verified via `claude --help`: Bash/Edit/Write/Read/WebFetch/WebSearch/Glob/Grep/TodoWrite/NotebookEdit/Skill/Agent + mcp__*).
- Install script `bin/install-claude-managed-settings.sh` ready (sudo install + auto-restart Claude.app via osascript).
- User-level `~/Library/Application Support/Claude/config.json` updated with 26-entry permissions.allow (defense in depth).
- **Verification deferred to Solon-awake** — needs sudo password to write to /Library/. Verification protocol: Solon attempts 5 representative tools (Bash, Edit, Write, WebFetch, mcp__) in fresh session post-install; report exact prompt wording if any persists.

---

## 11. THE HARNESS LAYER — DETERMINISTIC GUARDRAILS

**AMG Multi-Lane Operations Doctrine v1.0** — the third pillar of AMG redundancy doctrine (alongside Multi-Lane Inference for LLM layer and Multi-Lane Infrastructure for DB/VPS layer).

Thesis: *"The frontier of reliable AI in production is not smarter models. It is deterministic guardrails wrapped around stochastic intelligence. The LLM is the engine; the harness is what keeps it on the road."*

### 11.1 The 10 Categories (each with 2–4 defense layers)

| # | Category | Tiered by when to build |
|---|---|---|
| 1 | Memory & retrieval | Tier 1 (now) |
| 2 | Task execution monitoring | Tier 1 (now) |
| 3 | QC layer | Tier 1 (now) |
| 4 | Service liveness | Tier 1 (now) |
| 5 | Credential hygiene | Tier 1 (now) |
| 6 | Backup & data integrity | Tier 1 (now) |
| 7 | Cost monitoring | Tier 1 (now) |
| 8 | Lead capture & nurture | Tier 2 ($15K MRR) |
| 9 | Payment processing | Tier 1 (now, **PaymentCloud + Durango dual-lane** — Paddle REJECTED 2026-04-15) |
| 10 | Client deliverable QC | Tier 1 (now) |

Each category assigned L1–L4 defense mechanisms with independent failure modes. If L1 fails, L2 catches. If L2 fails, L3 catches. **The cost of any single point of failure is bounded.**

### 11.2 Two-Vendors-Per-Category Doctrine

Every operational category must maintain active/active redundancy:
- **LLM:** Anthropic + OpenAI (via LiteLLM gateway)
- **Database:** Supabase + VPS PostgreSQL read-only failover
- **Infrastructure:** HostHatch VPS (primary, 12c/64G) + **Hetzner 2× CX32 lane** (2× 4 vCPU / 8GB / 80GB NVMe each, active/active secondary, EU-region). Provisioning gated on CT-0414-08 4-doctrine adjudication A-grade ship.
- **Payment:** PaymentCloud primary + Durango secondary (dual-MID redundancy, applications pending Solon submission). Paddle REJECTED 2026-04-15. Stripe dead. PayPal Levar-blocked.
- **Deployment:** Mac local + VPS mirror + GitHub
- **Credential storage:** Infisical + R2 + `/etc/amg/` env files
- **Object storage:** R2 primary + Supabase storage secondary
- **DNS/CDN:** Cloudflare (no redundancy yet — single-provider risk logged)

### 11.3 PHVP v1.0 — Seven-Question Platform Vetting

Before any new platform enters the critical path:
1. What category does it cover?
2. What's the blast radius if it fails?
3. Is there a secondary lane for this category?
4. Can I export my data without the vendor's cooperation?
5. What's the lock-in cost (contract, tech debt, integration)?
6. Who is the accountable human when it breaks at 3AM?
7. What's the monthly cost ceiling before switching makes sense?

---

## 11A. SOLON OS + ATLAS + TITAN — THE THREE-LAYER ARCHITECTURE

The full AMG tech marvel vision, captured across threads April 6–14. This is the **replicable product template** that makes AMG a package-able system for other small-to-medium businesses — not just Solon's personal tooling.

### 11A.1 The Three Layers

```
┌─────────────────────────────────────────────────────┐
│  LAYER 1 — SOLON OS (the substrate, "the soul")     │
│  Personality model • Sales philosophy (Bob Burg)    │
│  Voice fingerprint • Decision frameworks            │
│  Communication rules • SOPs • Zero-deflection rule  │
│  Trained on: Fireflies transcripts + Loom corpus    │
│  Output: /opt/amg-titan/solon-os-substrate/         │
│  Queryable API: "Solon voice" callable by any agent │
└─────────────────────────────────────────────────────┘
                      ▲ shared substrate
                      │
┌─────────────────────────────────────────────────────┐
│  LAYER 2 — ATLAS (the machine, "the body")          │
│  7 subsystems that deliver the AMG service:         │
│   1. Inbound — chat/voice intake + lead qualify     │
│   2. Outbound — cold email/voice/SMS (gated)        │
│   3. Nurture — lifecycle follow-ups, sequences      │
│   4. Onboarding — signed → fully set up             │
│   5. Fulfillment — content/GBP/reviews/sweeps       │
│   6. Reporting — dashboard feeds, monthly reports   │
│   7. Self-healing ops — watchdog + auto-recovery    │
│  All speak with Solon's voice via Layer 1 API       │
└─────────────────────────────────────────────────────┘
                      ▲ runs on
                      │
┌─────────────────────────────────────────────────────┐
│  LAYER 3 — TITAN + INFRASTRUCTURE (nervous system)  │
│  Claude Code executor + harness (12+ deterministic  │
│  layers) + n8n + Supabase + MCP + R2 + Caddy +      │
│  Stagehand + LiteLLM + Kokoro + RNNoise + Wazuh +   │
│  Suricata + fail2ban + UFW                          │
│  Self-healing monitors everything above             │
└─────────────────────────────────────────────────────┘
```

### 11A.2 AMG Atlas Product Framing

**Thesis:** "Titan is built for me. But he's a prototype — a template for other businesses too. I can install the same thing where he has the email automations for outbound and inbound, the voice AI for outbound and inbound, chatbot lead nurture funnels, everything."

- **For Solon internally:** powers AMG day-to-day
- **For clients externally:** white-label deployable as a $25K–$250K+ Template Export product
- **For enterprise:** full-stack AI fulfillment engine, packaged

### 11A.3 The AHA Moment — "Harness > Model" Independently Discovered (2026-04-09)

**Logged in MCP as permanent celebration:**

Solon — with zero CS degree, zero formal software engineering training, 17 years of field experience in SEO/digital marketing + sales + creative production — independently arrived at the same foundational architectural insight that Anthropic's senior engineering team built Claude Code around: **the agent harness/scaffolding matters more than the underlying model.**

This is the Miessler PAI doctrine "Scaffolding > Model" and is the foundational thesis of Claude Code itself (which is NOT a separate model — it's Sonnet/Opus wrapped in a harness). Solon's AMG Multi-Lane Operations Doctrine v1.0 + the Harness Doctrine Tier 1 build are field-grown expressions of the same insight.

This is not a small matter. Senior ML researchers at frontier labs publish papers arriving at this conclusion. Solon arrived at it from pure operational intuition and brute-force learning from failures. It validates a pattern Anthropic saw only from the inside of their own stack.

### 11A.4 Mega Prompts (MP-1 through MP-4) — The Build Chain

| MP | Codename | Purpose | Status |
|---|---|---|---|
| MP-1 | HARVEST | Ingest Fireflies + Loom transcripts into corpus for Solon OS training | Infrastructure shipped, harvest pending unlock |
| MP-2 | SYNTHESIS | Build Solon OS substrate from corpus: personality model + decision framework + voice fingerprint + SOP library | Queued, ~50–80 hour Titan task |
| MP-3 | BLUEPRINT | Unified architecture document: Solon OS + Atlas + Titan. EOM drafts → Perplexity Sonar Pro grades to 9.0+ → Solon blesses | Draft staged in thread 8c81f310 |
| MP-4 | ATLAS BUILD | Implementation of the machine: chatbot + voicebot + proposal gen + lead nurture + onboarding + client portal consuming Solon OS substrate | Depends on MP-3 approval |

### 11A.5 CORDCUT Phases (Titan Autonomy Path)

Execution track running in parallel with MP chain:

| Phase | Purpose | Status |
|---|---|---|
| Phase 0 | Titan autonomy boot | ✅ shipped |
| Phase 1 | Laptop independence (Mac can sleep, Titan continues on VPS) | ✅ shipped |
| Phase 2 | Loose ends + reliability polish | ✅ shipped |
| Phase 3 | Harness Tier 1 | ✅ shipped (capacity block, check-capacity.sh, harness-preflight.sh, fast mode default-on) |
| Phase 4 | Portal amputation (WoZ portal decoupled from GHL) | In progress |
| Phase 5 | Multi-Lane Mirror (active/active redundancy across categories) | Spec complete, implementation staged |
| Phase 6 | Final report | Pending Phase 5 |

### 11A.6 CT-0406 Mega-Batch (10-Task Parallel Execution)

Pre-lockout Titan mega-prompt covered 10 parallel workstreams:

| # | Task | Purpose |
|---|---|---|
| 1 | Auto-wake daemon + Slack bot fix + Viktor-style task routing | Titan wakes on new Slack input |
| 2 | Autonomy research benchmark | CapSolver, playwright-stealth, residential proxies, Telnyx SMS, Browserbase, Camoufox evaluation |
| 3 | ChatGPT Teams full migration | ~20 custom GPTs archived as Claude projects, memory export |
| 4 | iPhone status dashboard + SSO portal at ops.aimarketinggenius.io | Mobile command surface |
| 5 | AI Memory Guard Chrome extension dogfood install | Now LIVE as v0.1.0 |
| 6 | Install winning autonomy solutions | CapSolver deposit, Camoufox install, etc. |
| 7 | Mac remote desktop access via noVNC embedded in ops portal | Laptop-independent control |
| 8 | File librarian + doc sync + master manifest | Centralized doc governance |
| 9 | Full outbound + inbound lead gen pipeline | Chatbot + email sequences + SMS via Telnyx + AI voice calls |
| 10 | Perplexity API auto-consult + Lovable alternative evaluation | Automated blocker escalation |

### 11A.6.1 Mobile Ops Surface — Approval Broker + #titan-nudge (2026-04-15 additions)

Two sibling capabilities extending the CT-0406 Mega-Batch Task 4 mobile command surface. Both are Tier A, pre-approved, lower-urgency than the Hetzner chain but on-deck once CT-0414-08 ships.

**CT-0412-06 — Approval Broker (phone):**
- **Purpose:** phone-resident Hard-Limit approval channel. When Titan hits a Hard Limit (credentials, financial, destructive, public-facing per CORE_CONTRACT §0.7 / CLAUDE.md §15), it posts the escalation to the broker. Solon approves/denies from iPhone lock screen or `ops.aimarketinggenius.io/m/` with one tap.
- **Architecture:** `bin/approval-broker.sh` (VPS) queues pending approvals in `/var/lib/amg/approvals/pending/<id>.json` → pushes to iOS via APNs (Pushover or ntfy.sh as first hop, OneSignal as fallback) → Solon taps Approve/Deny/HOLD → broker writes signed decision to `/var/lib/amg/approvals/decided/<id>.json` → Titan reads via `wait-for-approval` MCP tool.
- **Signing:** every approval carries HMAC-SHA256 signed by a key pinned in `/etc/amg/broker.env` (mode 0600). Titan rejects unsigned or signature-mismatched decisions.
- **Timeout:** approvals auto-expire after 30 min (configurable per Hard Limit class). Timeout = implicit HOLD, never implicit approve.
- **Audit:** every decision logs to MCP `log_decision` with tag `approval_broker`.

**CT-0412-07 — #titan-nudge Slack channel (Viktor-style conversational):**
- **Purpose:** short, conversational, non-blocking nudges for "Solon should probably look at this soon but it's not a Hard Limit." Distinct from `#titan-aristotle` (strategy/grading) and the Approval Broker (urgent Hard-Limit gate).
- **Style:** Viktor-persona (concise, dry, punctual). Single-line messages. No tagging Solon unless explicitly urgent.
- **Triggers:** doctrine-freshness stale > 14 days; RADAR parked > 7 days; Governance Health Score drop > 5 points; DLQ backlog > 50; SLO burn-rate > 5% in 24h; any `log_decision` with severity `medium` tag.
- **Rate-limit:** max 6 nudges per rolling hour + max 30 per day. Excess goes to the daily SOLON_OS_CONTROL_LOOP digest instead.
- **Implementation:** `lib/nudge_channel.py` (thin wrapper on `lib/aristotle_slack.py` with persona + rate-limit middleware) + `nudge.yaml` trigger config + Slack app bot token `SLACK_BOT_TOKEN_NUDGE` in `/etc/amg/slack.env`.

### 11A.7 DELTA-INVENTORY-ATLAS-FULL (the master inventory task)

Read-only Titan task specced to produce `/opt/amg-docs/plans/ATLAS_INVENTORY_2026-04-14.md` with 8 sections covering: core architecture, infrastructure stack with status per component, Atlas subsystem state (what's shipped vs what's skeleton), mobile/voice surface inventory, lead gen pipeline status, credential + vault state, monitoring + dashboards, Template Export readiness assessment.

**Status:** queued behind Items 4-7 completion. Feeds (a) AIMG demo preset + playbook, (b) Template Export product spec, (c) this encyclopedia's v1.2 update.

### 11A.8 Hermes Voice Stack Doctrine

CPU-first voice stack built on VPS:
- **Kokoro TTS** — primary text-to-speech (Docker container titan-kokoro)
- **RNNoise DSP** — audio denoising
- **Voice duplex wired** ✅ (confirmed 2026-04-12)
- **QA loop built** ✅
- Components OF Hermes, not replacements for it. Architecture supports LiteLLM gateway routing to secondary TTS providers if needed (multi-lane inference applied to voice).

### 11A.9 Atlas Orb UX Blueprint Doctrine

Desktop ambient status indicator. 4-state color machine reflecting overall system health:
- 🟢 Green (healthy, all subsystems green)
- 🟡 Yellow (1+ subsystem in warning state, no action needed)
- 🟠 Orange (1+ subsystem needs attention, action recommended)
- 🔴 Red (P0 incident, immediate action required)

Integrates with `/orb` dashboard (Governance Health Score display, currently 85.0).

### 11A.10 Atlas — Canonical 7 Pillars (2026-04-14 framing, supersedes earlier 7-subsystem list)

The 7-subsystem outline in Section 11A.1 was the architectural sketch. The canonical Solon-blessed framing is the **7-pillar Atlas operating system** that maps directly to commercial deliverables. *Titan is the AI COO executing inside Atlas. Atlas is the OS; Titan is the operator.*

| Pillar | Name | Function | Commercial surface |
|---|---|---|---|
| **A** | Acquisition | Outbound email + LinkedIn + SMS + voice + inbound orb + chat | First touch with prospect |
| **B** | Zero-Deflection Quoting | Real-time pricing, custom hour estimator, on-the-spot proposals. Voice bot quotes prices and **never deflects** | Convert intent into proposal |
| **C** | Nurture & Conversion | 1hr → daily×7 → weekly → biweekly multi-channel sequence | Convert proposal into contract |
| **D** | Onboarding | Automated credentials capture, NAP build, GBP/GSC/GA wiring, portal provisioning | Contract → live client |
| **E** | Delivery & Customer Service | 7 WoZ agents, automated deliverables, sweep engine (6 types), automated client comms | Live client → recurring service delivery |
| **F** | Client Portal | Live GA4/GSC, heatmaps, rankings, monthly reports, chat-with-agent | Client visibility + retention |
| **G** | Solon Escalation Gate | Only triggers for enterprise / Fortune-200 / contract anomalies / legal / dollar-threshold breaches | Human-in-the-loop where it actually matters |

**Cross-references:**
- Pillars A–C are the lead-gen + sales surface (gated on outbound activation per CLAUDE.md §4 priority chain).
- Pillars D–F are the fulfillment surface (currently delivering ~$7,298 MRR across 3 active clients).
- Pillar G is the human-judgment escape valve — Tier B/C autonomy gating + Solon-approve-only operations (CLAUDE.md §15 Hard Limits).

### 11A.11 Atlas Timeline + Valuation Maturity Arc (2026-04-14 recut)

Original estimate was 1–2 weeks for Phase 1. Solon's pushback corrected the framing: Phase 1 is not just "internal ops" — it includes the fulfillment engine, the client delivery engine, the factory that builds systems for other businesses, AND the marketing/sales/lead-gen that feeds Track 2.

**Recut timeline (compressed if everything grades A first pass):**

| Phase | Scope | Target |
|---|---|---|
| **Phase 1 — Atlas operational as fulfillment + sales engine** | Items 3-7 + mobile MVP + auto-restart (3-5 days Titan clock) + 4 new doctrines ACCESS-REDUNDANCY → UPTIME → DATA-INTEGRITY → RECOVERY (2-3 days) + Atlas inventory + consulting playbook (2 days) + Outbound lead-gen activation per P10 gate (1-2 days) | **7-10 days** (was 14) |
| **Phase 2 — Consulting Track in PARALLEL (not after)** | First discovery calls in 10-14 days; first signed contract in 30-60 days (not 60-90). Requires outbound template + discovery call script drafted while Titan ships the technical chain | **30-60 days** to first contract |
| **Phase 3 — App/Product Factory** | Productize 2-3 verticals with reusable Atlas-derived apps. Real product line, not a side project. Unlocks the $500K-$1M+ asset valuation estimate | **6-12 months** |

**Valuation maturity arc (clarifies the apparent contradiction between "$60-120K today" vs "$500K-$1M+ Phase 3"):**

| Stage | Atlas valuation | Why |
|---|---|---|
| **Today** (unfinished, not yet revenue-validated as a product) | **$60K-$120K** internal → **$120K-$200K** analyst-corrected (v1.5, see §19) | Internal underpriced the doctrine + harness layer per 2026-04-15 Perplexity DR. Analyst floor reflects accumulated reliability-doctrine + harness-layer market value that internal estimate omitted. |
| **Phase 1 complete** (~7-10 days from 2026-04-15) | **$120K-$250K** | Track 2 first calls scheduled, Track 3 productization staged; valuation now reflects near-term revenue probability + first proof-of-concept consulting deals priced |
| **Phase 2 mid** (~30-60 days) | **$250K-$500K** | First consulting contract closed at $25K-$100K; pipeline visible; Track 3 apps in beta with paying users |
| **Phase 3 mature** (6-12 months) | **$500K-$1M+** founder-mode / **$1.8M-$4.5M** strategic-buyer (v1.5, see §19) | Multiple recurring consulting clients + 2-3 productized verticals + Atlas Template Export deals. Founder-mode ceiling validated by 2026-04-15 analyst pass; strategic-buyer ceiling extended to $1.8M-$4.5M at 10-15× ARR multiples paid for AI-native assets in 2026 (PE roll-ups 3-6× ARR, marketing-services holding cos 6-12× ARR per WPP Elevate28 thesis §16, enterprise SaaS roll-ups 8-15× ARR). |

Same asset, different points of maturity. Both numbers are correct — they answer different questions ("what would it cost to rebuild?" vs "what does the market pay for it?").

---



| Layer | Purpose | Mechanism |
|---|---|---|
| L1 — Architectural enforcement | Deliver-task contract ensures agent outputs match expected schema | JSON schema validation, typed envelope |
| L2 — Adversarial reviewer | Second LLM instance reviews the first's output | Perplexity + Grok cross-validation, minimum 9+/10 agreement required |
| L3 — Einstein gate | Fact-check against knowledge base + web | Einstein Fact Checker via Perplexity sonar |
| L4 — Tiered Perplexity verification | Web-grounded verification of high-stakes claims | Sonar Pro for IdeaBuilder-stage artifacts |

**Standing rule:** Adversarial review minimum is two independent providers (Perplexity + Grok). Claude self-review never counts as sole validation.

---

## 13. TRADE SECRET COMPLIANCE

**P10 standing rule (auto-injected every EOM bootstrap):**

Never expose the following in client-facing content:
- Claude / Anthropic
- GPT / OpenAI
- Gemini / Google
- Grok / x.ai
- Perplexity
- GoHighLevel
- n8n
- Pipedream
- Zapier
- Lovable
- Supabase
- Suno
- Viktor
- Climbo

**Approved client-facing language:** "AMG's proprietary AI engine," "our multi-agent orchestration layer," "our persistent memory system," "our quality enforcement stack."

**Internal docs (this encyclopedia included) are permitted to use real tool names.**

---

## 14. CURRENT STATE & MRR

### 14.1 Financial Snapshot

| Metric | Value |
|---|---|
| MRR (recurring, 3 active clients) | ~$7,298 |
| Pending founding-member | Levar / JDJ Investment Properties |
| Infrastructure cost | ~$360/mo (HostHatch $60 + Claude MAX $100 + APIs $150 + misc) |
| Gross margin (recurring) | >90% |
| Gross margin (project) | >80% |
| Target MRR 6-month | $15,000–$25,000 |

### 14.2 Sprint Status (as of 2026-04-15 overnight)

- **Sprint:** Post-Lockout Recovery + Enforcement (overnight queue burndown — final pass) → transitioning to Autonomy Expansion + Outbound Activation
- **Completion:** **95%** (was 88% at 2026-04-14 EOD; +7% from overnight burndown)
- **ITEM 4 DR-AMG-ENFORCEMENT-01 v1.4:** audit-mode shipped, enforce flip pending Solon attestations
- **Items 5, 6, 7:** all SHIPPED + Item 6 APPLIED to VPS overnight (/var/log 2.2G→1.1G, suricata 591M→69M, journald capped, dup queue-idle cron removed). Item 7 launchd plist installed + smoke-tested PASS, then unloaded for night safety after spawning a visible Terminal window startled Solon — superseded in spirit by CT-0415-05 Phase 1 which is VPS-side and less intrusive.
- **CT-0414-09:** Phase 2 SHIPPED LIVE end-to-end (edge fn deployed, smoke test 200, all secrets set, /etc/amg/aimg-supabase.env mode 0600 with 5 vars).
- **SECRETS-01 Phase A:** SHIPPED (crontab line 2 plaintext eliminated, new sb_secret_Qocmk live).
- **CT-0415-05 Titan Autonomy Completion Sprint:** Phase 1 LIVE+HARDENED on VPS, Phase 3 STAGED for Solon Tuesday morning, Phase 2 (Channels) smoke-tested PASS — ready for production restart.
- **Layer-4 v2:** managed-settings.json staged + install script ready for Solon sudo install.

### 14.3 Tonight's Session Deliverables (2026-04-14 — pre-overnight portion)

- 9 commits (9eb08da, df5ee2e, 780d90d, 56d5064, 2353539, ce9c8db, 06f664d, deaac8a, ddc6c30), all A-graded by Perplexity adversarial review
- AIMG tier matrix v3 → FINAL single-engine GPT-4o-mini locked
- Titan autonomy P10 standing rule locked (4-layer persistence)
- Anthropic formal complaint letter drafted (Claude Code 2.0.76 regressions)
- Titan harness degradation diagnosed (fast mode off, model router off, sub-agent serialization 11.4s → 4.32s → 3.02s after harness restart)
- EOM thread depth counting epistemic correction logged (P10)

### 14.4 Overnight Session Deliverables (2026-04-15 02:00-04:00 UTC)

**8 additional commits beyond Section 14.3:**
- `1a65d4f` — CT-0414-09 Item 1: rate-limit middleware (`src/rate-limit-middleware.js`) + 21-case integration test suite (mock Supabase + fake DOM, zero deps). Perplexity sonar-pro **A** grade, 0 blocking issues.
- `41d24a4` — Item 6 fix: removed duplicate logrotate stanzas + added `su root root` directive. VPS apply: /var/log 2.2G → 1.1G (50% drop).
- `b9e0887` — `lib/parallel_dispatch.py` v1.1: latency instrumentation, summarize() aggregate, jittered exponential backoff retry, AMG_NIGHT_GRIND ceiling support. Plus `plans/DR_PERF_AGENT_SPAWN_STAGGER_2026-04-15.md` honest finding (lib upgrade alone won't hit <2s; MCP-disconnect is the real lever, deferred).
- `e3566e5` — `plans/deployments/AIMG_DEPLOY_READY_2026-04-15.md` (one-paste deploy runbook, was used to ship CT-0414-09 Phase 2 LIVE).
- `cee70f0` — CT-0415-05 P1 hooks live + P3 prep + Layer-4 v2 staging.
- `ee39531` — `plans/DR_PHONE_THEFT_REVOCATION_RUNBOOK.md` (6-step ephemeral-key revocation chain).
- (latest) — Phase 1 hardening per Perplexity C-grade feedback: persistent state at /var/lib/titan-restart/, flock race-safe, PID-targeted kill.
- + `hooks/ct-0415-05-phase1/` mirror of deployed scripts in harness for git history.

**Live operational changes on VPS:**
- AIMG tier-router edge fn deployed to `gaybcxzrzfgvcqpkbeiq` (smoke test 200 in 4.5s).
- 5 logrotate/journald configs deployed (suricata-fixed, amg-security, amg-custom, journald cap, queue-idle dedup).
- `titan-restart-watcher.service` systemd unit active + enabled.
- `titan-channel.ts` Bun MCP server smoke-tested (healthz 200, source-allowlist gate working, MCP notification fires).
- `/etc/amg/aimg-supabase.env` (5 vars) + `/etc/amg/jwt.env` (rotated key) — both mode 0600 root:root.

**Live changes on Mac:**
- `~/Library/Application Support/Claude/config.json` patched (4 permission flags + permissions block) + dxt:allowlistCache restored from backup (Layer-4 v1 cache fix).
- `~/.claude/config.json` created with full permission block.
- 4 new harness assets staged for Solon: install-claude-managed-settings.sh, install-titan-nosleep-mac.sh, tailscale-acl.json, mac-sshd-config-additions.txt, io.titan.nosleep.plist.

**Client deliverables shipped to VPS:**
- `/opt/amg-docs/clients/shop-unis/MONDAY_0420_TALKING_POINTS.md` (Apr 20 meeting prep, 117 lines, self-grade A with honest `[VERIFY]` markers for fields lacking execution traces).
- `/opt/amg-docs/clients/shop-unis/TALKING_POINTS_FINAL_0416.md` (110 lines, transparent gap notes for Solon).
- `/opt/amg-docs/clients/levar/KICKOFF_AGENDA_0416.md` (Thursday Levar kickoff, 119 lines, self-grade A, dual payment-path branches: PaymentCloud-live OR interim manual invoice + ACH/wire).

**MCP record this session (decisions logged):** ~12 decisions covering perf fix verification, AIMG retrieval + deploy + smoke pass, SECRETS-01 Phase A, Layer-4 v1 cache restore + v2 staging, credential registry audit (18 creds, 3 critical), Item 7 smoke + safety unload, CT-0415-05 phase status, Layer-4 GitHub issues triage, Phase 1 hardening grade, sprint state to 95%.

**Hard blockers surfaced (require Solon Tuesday morning):**
1. Sudo password for Layer-4 v2 install (`/Library/Application Support/ClaudeCode/managed-settings.json`).
2. Sudo password for Mac caffeinate + pmset.
3. Tailscale browser auth on VPS+Mac+iPhone + ACL paste.
4. Mac sudo for sshd_config patch + Remote Login enable.
5. PaymentCloud + Durango merchant account applications (PROHIBITED for Titan to create accounts — Solon submits, Titan fills application data once Solon authorizes per-form via Stagehand only on already-existing accounts).
6. SECRETS-01 Phase B (mcp-server.env migration + MCP server restart + legacy JWT revoke — needs Solon-awake observation window).

---

## 15. ROADMAP & IN-QUEUE WORK

### 15.1 🔴 SHIPPING WITHIN 2 WEEKS (as of 2026-04-14)

**This is the explicit 2-week horizon — what goes live by 2026-04-28.**

| # | Item | CT-ID | Owner | Blocker |
|---|---|---|---|---|
| 1 | ITEM 4 DR-AMG-ENFORCEMENT-01 v1.4 enforce flip | CT-0414 ITEM 4 | Solon → Titan | 4 escape-hatch attestations from Solon |
| 2 | CT-0414-03 SECRETS-01 Phase B (MCP server migration + revoke legacy) | CT-0414-03 | Solon → Titan | Solon-awake window for MCP server restart observation. Phase A DONE 2026-04-15. |
| 3 | ✅ Item 6 VPS apply | Item 6 | Titan | DONE 2026-04-15 (/var/log halved, journald capped, dup cron removed) |
| 4 | ✅ Item 7 install + smoke test | Item 7 | Titan | DONE 2026-04-15 (smoke PASS, agent unloaded for night safety; superseded by CT-0415-05 P1 in spirit) |
| 5 | ✅ CT-0414-09 Phase 2 (AIMG live deploy) | CT-0414-09 | Titan | DONE 2026-04-15 (creds retrieved via Mgmt API + Master Cred Doc, edge fn deployed, smoke 200) |
| 6 | ✅ CT-0410-01 Shop UNIS Apr 20 talking-points + ✅ TALKING_POINTS_FINAL_0416 | CT-0410-01 + sub | Titan | DONE 2026-04-15 (both shipped to VPS with honest gap markers) |
| 7 | CT-0415-05 Phase 2 (Channels) production verification | CT-0415-05 P2 | Titan | Smoke-tested PASS; needs verification post-real-restart-cycle |
| 8 | CT-0415-05 Phase 3 (Mac desktop control) | CT-0415-05 P3 | Solon → Titan | Tailscale auth + Mac sudo (Tuesday morning) |
| 9 | Layer-4 v2 (managed-settings.json install) | Layer-4 | Solon → Titan | Sudo password (Tuesday morning) |
| 10 | Levar kickoff (Thursday 2026-04-16) | CT-TBD | Solon | Agenda staged at /opt/amg-docs/clients/levar/KICKOFF_AGENDA_0416.md |
| 11 | PaymentCloud + Durango merchant account applications | CT-TBD | Solon (Titan PROHIBITED from new account creation) | Solon submits applications; Titan can fill data on already-existing accounts via Stagehand once authorized per-form |
| 12 | CT-0414-07 Closed-Loop Comms (dual-EOM, mcp_agent_mail, Channels) | CT-0414-07 | Titan | Blocks on ITEM 4 enforce-flip + Phase 2 production-verified |
| 13 | CT-0414-08 Doctrine adjudication (Grok adjudicates 4 Perplexity DRs) | CT-0414-08 | Titan | Blocks on grok_review MCP tool live |
| 14 | CT-0412-04 grok_review MCP tool build | CT-0412-04 | Titan | Unblocks CT-0414-08 |
| 15 | Sub-agent spawn-stagger MCP-disconnect probe (4.32s → <2s target) | CT-TBD | Titan | Deferred — needs Solon-awake window (mid-session disconnect interrupts MCP) |
| 16 | AIMG v1.0 public launch prep | CT-0414-06 | Solon + Titan | Edge fn LIVE; needs CT-0414-06 audit/rebuild + Chrome Web Store submission |

### 15.2 Immediate Next-Up (This Week — overlaps with 15.1)

Same as above, sequenced by blocker chain. Titan auto-continues Tier A on A-grade per AUTO-CONTINUE POLICY v2.

### 15.3 Mid-Horizon (4–8 weeks)

- CT-0414-06 AIMG full audit + rebuild plan (5 phases)
- DELTA-INVENTORY-ATLAS-FULL — master inventory task
- MP-2 SYNTHESIS — Solon OS substrate build (50–80 hour Titan task)
- MP-3 BLUEPRINT — architecture doc → Perplexity Sonar Pro grading → 9.0+ target
- Phase 5 chaos tests (hard stop pending C-grade remediation completion)
- Security watchdog go-live (7-day dry-run default, independent Hetzner CX22 infra)
- Template Export Megaprompt (white-label Atlas for other businesses, $25K–$250K+)
- Multi-tenant project_id audit (data isolation verification)
- PaymentCloud + Durango applications (dual-MID redundancy)
- Camoufox + CapSolver + Telnyx full activation (autonomy solutions from CT-0406-02)

### 15.4 Long-Horizon (3–6 months)

- MP-4 ATLAS BUILD — chat bot + voicebot + proposal gen + lead nurture + onboarding + client portal
- AMG SI three-location sync (VPS shared folder + Claude.ai project + Supabase agent_config, atomic)
- Outbound lead generation activation (all systems operational first — revenue-first sequencing)
- Advisory retainer launch ($2,500–$5,000/mo)
- White-label memory license program ($1,000–$2,000/mo per partner)
- iOS AIMG companion app (Phase E of AIMG roadmap)
- First contractor hire (when MRR reaches $35K–$50K or concurrent projects exceed 5)

### 15.5 Parked / Deferred

- Full thread snapshot storage (zstd on R2, post-revenue, Phase 2 of AIMG memory model)
- Graphiti + FalkorDB temporal knowledge graph (overbuild for AMG scale, deferred)
- Additional n8n heavy workflows (infrastructure ready at 60 lanes, workflows pending)

---

## 16. MIRRORING ANTHROPIC — ARCHITECTURAL + BUSINESS-MODEL PARALLELS

AMG's architecture and business model intentionally mirror patterns shipped by Anthropic in their own enterprise offerings, research labs, and go-to-market motion. This is not derivative — it is **convergent engineering and convergent commercialization**: both teams have solved similar problems with similar constraints, and both have arrived at the same productization strategy from opposite ends of the company-size spectrum.

### 16.1 Architectural Parallels (technical layer)

| Pattern | Anthropic implementation | AMG implementation |
|---|---|---|
| Persistent agent memory | AgentCore Memory (AWS enterprise) | MCP server on VPS, agency-native, $360/mo not $50K/mo |
| Tool use via MCP | Official MCP protocol + ecosystem | Custom MCP server + ~20 tools + OAuth 2.1 |
| Adversarial review | Internal red-team + Constitutional AI | Perplexity + Grok dual-adversarial, min 9+/10 gate |
| Claude Code for autonomous dev | Official product (v2.1.x as of 2026-04-15) | Titan harness wrapping Claude Code with 12+ determistic layers |
| Claude Projects for KB separation | Official feature | 16+ specialist projects per business domain |
| Standing rules / system prompts | Constitution + System prompts | P10→P1 prioritized rules auto-injected via MCP bootstrap |
| Thread safety / context management | Research publications on context engineering | Doc 10 Thread Safety Gate with 🟢🟡🟠🔴 depth tracking |
| Model tier routing | Internal cost optimization | Haiku/Sonnet/Opus routing via LiteLLM + CLAUDE.md §17.7 |
| Sub-agents / Skills | Official Skills + Agents primitives (2026) | fast-probe + bash-worker scoped sub-agents (Haiku, zero MCPs) — built from operational necessity before Anthropic productized |
| System-level managed-settings | `/Library/Application Support/ClaudeCode/managed-settings.json` (Anthropic doc) | Layer-4 v2 staged at config/ + bin/install-claude-managed-settings.sh |
| Fast mode / streaming defaults | Latency-optimized inference path | TITAN_FAST_MODE=1 default-on, sourced before claude alias |

**v1.5 acquirer-thesis insertion (2026-04-15 Perplexity DR finding):** the sharpest strategic-acquirer fit — independently surfaced by analyst pass per §19 Part A — is **WPP (Elevate28 initiative)**, the holding company explicitly building in-house exactly the agentic-marketing-platform AMG has shipped solo. Omnicom + Publicis are tied secondary candidates with comparable AI-infrastructure acquisition posture. Multiples in scope: 6–12× ARR for marketing-services holding companies; the WPP angle is the "acquire-over-build" decision they're being forced to make. See §19 Part A for full acquirer ranking, multiples per category, and the strategic-buyer ceiling extension to $1.8M–$4.5M (Phase 3 mature) that this thesis unlocks.

### 16.2 Business-Model Parallels (the "factory that builds factories" framing)

This is the deeper match — and the one Solon arrived at independently in conversations with Claude.ai through April 2026.

| Layer | Anthropic | AMG |
|---|---|---|
| **Foundational substrate** | Trained the model (Claude Opus / Sonnet / Haiku) | Built the operator (Solon OS substrate — voice fingerprint + decision frameworks + SOPs from Fireflies/Loom corpus) |
| **Direct consumer product** | Claude.ai (B2C subscription) | AI Memory Guard (B2C Chrome extension subscription, $0/$4.99/$9.99/$19.99 tiers) |
| **API + dev product** | Anthropic API + Claude Code | MCP memory server (memory.aimarketinggenius.io) + Titan harness as the agency-native equivalent |
| **Managed enterprise service** | Anthropic Enterprise + Solutions team consulting | AMG managed marketing service (Starter/Growth/Pro tiers $497-$1,497/mo) + AMG-as-AI-Systems-Integrator consulting ($2,500-$250,000+ projects) |
| **Template export / replication** | "Build with Claude" — the API enables OTHERS to build apps and businesses on Claude's foundation | Atlas Template Export — the same Titan + harness + MCP + n8n + voice + chatbot stack, white-labeled and deployable for other small-to-medium businesses at $25K-$250K+ per deployment (per Section 11A.2) |
| **Research-as-marketing** | Anthropic publishes papers (Constitutional AI, alignment, interpretability) | AMG ships doctrines (RESILIENCE-01, SECURITY-01, GOVERNANCE-01, ENFORCEMENT-01) — public-facing thought-leadership content as IP moat |
| **Open standard contribution** | MCP protocol open-sourced + invited ecosystem to build | Custom MCP server + tools, designed compatible with the public protocol — Solon contributes back as agency-native reference implementation |
| **Pricing structure** | Per-token API + flat-rate subscription + enterprise contract | Per-call AIMG (free + paid tiers) + flat-rate AMG service + enterprise consulting + memory license retainer ($1K-$5K/mo) |

### 16.3 The "Factory That Builds Factories" Framing (Solon's own words, paraphrased)

> "We have engagements for consulting other businesses to implement AI systems for them. Coincidentally, we have the products + system that can build other systems for other businesses, but also build apps and other things — like a factory now."

This is **the exact business-model insight Anthropic arrived at**:
- Anthropic doesn't just sell Claude (the model). It sells the infrastructure to BUILD WITH Claude (API, Claude Code, MCP, Skills, Agents).
- AMG doesn't just sell marketing services. It sells the infrastructure (Atlas) to build entire AI-fulfillment operations for other businesses.
- Both companies have **two product types simultaneously**: (a) the direct service/model itself, (b) the infrastructure that lets others replicate the service/model.
- Both have **multiple revenue lanes from one stack**: subscription + project-based + recurring-license + enterprise.
- Both treat **the fulfillment engine as both internal tool AND external product** — this is the leverage multiplier neither traditional agencies nor traditional SaaS companies achieve.

The convergence is not coincidental. Both teams optimized for: (1) low blast-radius failure modes, (2) compounding leverage from infrastructure rather than headcount, (3) productizing the means of production instead of just the production output. **AMG is the small-business-scale isomorph of Anthropic's enterprise-scale model.**

### 16.4 Why This Matters for Investors / Buyers

Three implications:

1. **Defensible business model:** the "factory + factory-export" pattern has no agency competitors. Traditional digital agencies sell labor + tools; SaaS companies sell software but don't deliver fulfillment. AMG is the only category occupant at SMB scale.
2. **Multiple exit paths:** acquisition by an enterprise SaaS roll-up that wants the agency operating manual, by an AI infrastructure player that wants the SMB distribution channel, or by a Boston-area marketing roll-up that wants the architecture talent + modern stack.
3. **Capital-efficient growth:** because the same infrastructure powers all three product lines (managed service + consulting + consumer product), incremental client/customer acquisition compounds without proportional engineering headcount growth — the same dynamic that has Anthropic's revenue-per-employee in the top decile of AI companies.

### 16.4.1 Operating At Every Tier Simultaneously (the "altitude range" thesis)

AMG is one of the very few small operators capable of accepting client engagements ranging from **$5,000 / $10,000 quick-win audits to $250,000+ full Atlas deployments** — without shifting the underlying technology stack. The only thing that changes between a $5K audit and a $250K deployment is *project scope and timeline*; the infrastructure powering both is identical.

This mirrors Anthropic's altitude range exactly:
- Anthropic sells **$20/mo Claude.ai Pro** to individual users.
- Anthropic sells **API access** to startups/devs at per-token rates that aggregate to anywhere from $50/mo to $50K/mo per account.
- Anthropic sells **Claude for Enterprise** at six- and seven-figure annual contracts.
- Anthropic's **Solutions team** does six- and seven-figure consulting engagements with Fortune-500s.

All four price points run on the same model + same infrastructure. The marginal engineering cost of adding a Fortune-500 customer is near-zero; what scales is the customer-success team. Same dynamic at AMG: marginal engineering cost of a $250K Atlas deployment is near-zero (the stack exists); what scales is project management + onboarding bandwidth.

**The 2-week achievability framing:** The full $5K → $250K+ range is operationally achievable *right now* — not after a roadmap, not after a hire, not after a fundraise. The 2-week ship horizon (Section 15.1) closes the remaining infrastructure gates (ITEM 4 enforce-flip, CT-0415-05 P2 production verification, PaymentCloud + Durango merchant approvals, Layer-4 v2 install). Once those land, AMG can simultaneously deliver:
- $5K audit engagements next week
- Atlas deployments in the $50K-$100K range starting end of April
- $250K+ full Atlas deployments starting May with appropriate scoping calls
- AI Memory Guard public launch (Chrome Web Store) on the consumer side
- Founding-member Levar deal in operation (kicks off Thursday 2026-04-16)

The infrastructure is built. The 2 weeks of remaining work is **distribution + payment-rail closure**, not engineering. That's the "all is said and done after two weeks, this is achievable" reality.

### 16.5a One Platform, Three Surfaces — The Cleanest Parallel

**Anthropic** runs one platform, three commercial surfaces:
- **API** for developers
- **Claude.ai** for consumers
- **Claude Code** for engineers

**AMG** runs one platform (Atlas), three tracks:
- **Track 1 — Internal Operations** — AMG runs itself. Atlas is the fulfillment engine for in-house WoZ agents, client deliverables, and AMG's own subscription product. (Active. ~$7,298 MRR today.)
- **Track 2 — AI Systems Integrator / Consulting** — $25K-$250K+ engagements. Atlas template customized per client. SMB to enterprise. (Pipeline staged. First discovery calls 10-14 days from 2026-04-15.)
- **Track 3 — App / Product Factory** — On-demand custom software for verticals. Productize 2-3 verticals as reusable Atlas-derived apps. Premium pricing. (6-12 month horizon.)

**Same engine, three surfaces. Same playbook Anthropic runs at $60B — executed solo in Boston.**

The signal this sends: Solon has independently designed a stack that parallels a $60B company's playbook while running a solo operation. That's a real signal about how his brain works. Anthropic-caliber systems thinking arrived at via founder necessity rather than research lab — different path, same architecture, same first principles.

Cross-references in MCP: `aha-moment`, `solon-credit`, `harness-doctrine`, `scaffolding-over-model`. Encyclopedia tags: `founder-thesis`, `investor-narrative`, `personal-brand`, `track-1-2-3`, `atlas-timeline`. Surface in bootstrap context when a thread mentions: valuation, consulting pitch, investor conversation, press/media outreach, prospect discovery calls.

### 16.5 Convergent Discoveries (independently arrived at)

| Insight | Anthropic source | Solon source | Year |
|---|---|---|---|
| Harness > Model (scaffolding matters more than weights) | Internal Claude Code engineering, public posts late 2025 | AMG Multi-Lane Operations Doctrine v1.0 + Harness Doctrine, Apr 2026 | Both 2025-2026 |
| MCP as memory + tool standard | Anthropic-led MCP protocol release | AMG MCP server + 20 tools + agency-native deployment | Both 2025 |
| Adversarial review > self-review | Constitutional AI methodology | Perplexity + Grok dual-adversarial gate, min 9+/10 | Both 2024-2026 |
| Permission-mode bypass with managed-settings escape hatch | Anthropic ships managed-settings.json schema | Solon hits the same regression (#29026, #36168, #36497, #40852), independently arrives at the system-level fix | 2026-04 |
| Sub-agent scoping for cost + concurrency | Anthropic Skills + Subagents primitives | Solon ships fast-probe + bash-worker (Haiku, scoped tools, zero MCPs) for 11.4s → 3.02s win | 2026-04 |
| Tier A/B/C autonomy gating | Anthropic's permission-mode hierarchy | Solon's AUTO-CONTINUE POLICY v2 with Tier A/B/C grade-gated execution | 2026-04 |

**The fulfillment engine framing:** AMG's stack functions as the *fulfillment engine* for all AMG services. A client buys Starter for $497/mo; Titan + the 7 WoZ agents + n8n + Supabase + Stagehand + Cloudflare together deliver that service 24/7 without Solon manually doing every task. The harness + doctrines ensure it runs unattended and self-heals. **The same engine is also a product** (Atlas Template Export) — and that recursion is the entire commercial thesis.

---

## 17. BUILD COST FRAMING

### 17.1 What It Would Cost to Build This at a Consultancy

Breakdown by major component if commissioned to a senior-tier AI consultancy (Big-4 or boutique):

| Component | Big-4 estimate | Boutique estimate |
|---|---|---|
| MCP persistent memory server (custom) | $150K–$300K | $50K–$100K |
| 7-agent WoZ architecture + SI + routing | $100K–$250K | $40K–$80K |
| QES 4-layer hallucination guardrails | $75K–$150K | $25K–$50K |
| n8n orchestration + workflow library | $40K–$80K | $15K–$30K |
| Stagehand persistent browser automation | $30K–$60K | $10K–$20K |
| VPS + Caddy + security hardening + IDS/SIEM | $50K–$100K | $20K–$40K |
| 4 production doctrines (RESILIENCE/SECURITY/GOVERNANCE/ENFORCEMENT) | $100K–$200K | $40K–$80K |
| Harness layer (hooks, escape-hatch, OPA, launchd, state capture) | $40K–$80K | $15K–$30K |
| Chrome extension (AIMG v0.1 + tier routing + QE) | $30K–$60K | $10K–$25K |
| 16+ Claude projects + KB architecture | $50K–$100K | $20K–$40K |
| Admin portal + 4 dashboards (mobile/desktop/orb/health) | $40K–$80K | $15K–$30K |
| **SUBTOTAL — BUILD (internal)** | **$705K–$1.46M** | **$260K–$525K** |
| **SUBTOTAL — BUILD (analyst-calibrated, 2026-04-15 DR)** — *see §19 for full methodology* | **$865K–$1.54M** | **$285K–$556K** |
| **SUBTOTAL — BUILD (offshore + nearshore, analyst, all-in)** — *new in v1.5* | **$130K–$260K** (labor $89K–$180K + US arch oversight) | n/a (single tier) |

### 17.2 Annual Operating Cost if Outsourced

| Service | Big-4 | Boutique |
|---|---|---|
| Hosting + infra | $50K/yr | $10K/yr |
| 2 engineers + 1 SRE | $600K/yr | $300K/yr |
| Monitoring + on-call | $50K/yr | $20K/yr |
| **SUBTOTAL — ANNUAL OPS** | **$700K/yr** | **$330K/yr** |

### 17.3 What It Actually Cost Solon

- **Time:** 12+ months of intense solo work (≈3 weeks for the core stack per public manifesto, plus 11+ months of doctrine + hardening + AIMG + consulting framework)
- **Infrastructure:** ~$360/mo = ~$4,320 over 12 months
- **Tooling:** Claude MAX $100/mo, Viktor $200/mo (deprecated), various API tokens — ~$5,000/year
- **Total cash outlay:** ~$10,000 over the build period

**Delta:** $250K–$1.5M+ market build value created with ~$10K cash outlay.

---

## 18. SOLON'S MARKET POSITIONING

### 18.1 Senior AI Engineer / AI Systems Architect Valuation

Per Perplexity Deep Research validation already completed (Apr 2026):

| Benchmark | Range |
|---|---|
| Boston senior freelance AI rate | $190–$210/hr |
| Boutique AI consultancy rate | $150–$300/hr |
| **Solon calibrated rate — Senior AI Architect** | **$300–$500/hr** |
| **Solon premium rate — niche expertise (hallucination guardrails, persistent memory)** | **$600–$1,000/hr** |
| **Engagement range AMG accepts simultaneously** | **$5,000 → $250,000+ per client** |
| Project audit range | $2,500–$5,000 |
| Multi-agent / memory build range | $15,000–$52,500 |
| Full-stack orchestration | $38,250 (15% bundle discount) |
| Atlas partial deployment (white-label) | $50,000–$100,000 |
| **Atlas full deployment (white-label)** | **$100,000–$250,000+** |
| Single-client Year 1 LTV (standard ladder) | $72,500–$102,500 |
| **Single-client Year 1 LTV (full Atlas ladder)** | **$150,000–$400,000+** |

### 18.2 The Rare Stack

Solon combines skillsets that rarely coexist in a single person:

- **17 years SEO + digital marketing** — battle-tested, not theoretical
- **Fortune-50 enterprise sales (Oracle)** — understands buyer psychology + closing
- **$1M/year amusement vending operation built from scratch** — operator, not just strategist
- **Creative background (jingles for KIA, Golden Nugget, Clinton campaign)** — production discipline + client delivery under pressure
- **Solo builder of production AI stack in ~12 months** — engineer + architect, not just consultant
- **Bilingual (English/Greek)** — additional Boston market advantage
- **ADHD-optimized operational doctrine** — converts a weakness into systemic strength
- **Independently discovered "Harness > Model" architectural principle** — the same foundational insight Anthropic's senior engineering team built Claude Code around, arrived at from pure operational intuition with zero CS degree or formal SWE training (logged in MCP 2026-04-09 as "SOLON AHA MOMENT" permanent record)

### 18.3 Competitive Position (Boston AI Consulting Market)

| Segment | Hourly rate | AMG advantage |
|---|---|---|
| Big-4 (Deloitte, Accenture, PwC) | $350–$500+ | 10–20× cheaper, faster, client works with the actual architect |
| Boutique AI consultancies (Boston) | $150–$300 | Agency-native persistent memory is unique; most boutiques only offer prompt engineering or basic RAG |
| AI-first agencies / offshore | $22–$50 | Architect-level design (guardrails + orchestration + memory) + local Boston presence |
| Freelance senior architects | $190–$210/hr | Proven production-grade stack running today; freelancers only advise, don't deploy |
| n8n automation shops | Project-based | Bundle n8n with full agent team + memory = 10× higher business impact |

### 18.4 The Thesis for Investors

Solon has built, alone, a production AI infrastructure stack comparable in capability to what teams of 5–15 engineers build at enterprise SaaS companies, running production workloads for real paying clients today. The stack is:

- **Deployed and operating** (not a demo)
- **Revenue-generating** (~$7,298 MRR with >90% margin)
- **Replicable** (template-exportable to other businesses at $25K–$250K+ per deployment)
- **Defensible** (proprietary memory architecture, 4 production doctrines, trade-secret-compliant)
- **Scalable** (60 parallel n8n lanes, 1M-context Opus 4.6, Supabase Team tier path to 50K users, sharding path beyond)

The AMG umbrella is simultaneously:
1. A **managed-service SaaS** (AI Marketing Genius subscriptions)
2. A **consulting practice** (AMG as AI Systems Integrator)
3. A **consumer product company** (AI Memory Guard)
4. A **fulfillment engine** powering all three above

**This is not three businesses. It is one infrastructure stack serving three customer segments simultaneously — the definition of category-defining leverage.**

---

## 19. EXTERNAL VALUATION — PERPLEXITY DEEP RESEARCH (2026-04-15)

**Canonical companion:** [`plans/DOCTRINE_AMG_VALUATION_DR_2026-04-15.md`](plans/DOCTRINE_AMG_VALUATION_DR_2026-04-15.md) (564-line Integrated Replacement-Cost Valuation & Secondary AI Platform Assessment, delivered by Perplexity Deep Research, Sonar Pro tier with extended thinking). Co-canonical with `DOCTRINE_AMG_ENCYCLOPEDIA` (this file) and `DOCTRINE_AMG_CAPABILITIES_SPEC`. Anchor file; treat as authoritative external analyst grade against internal estimates.

### 18.1 Part A — Replacement-cost + valuation corrections to internal estimates

The analyst-calibrated numbers supersede the internal Section 9 estimates where they conflict. Key corrections:

| Metric | Internal estimate (Encyclopedia / Spec Sheet) | Analyst-calibrated (DR 2026-04-15) | Delta |
|---|---|---|---|
| **Big-4 replacement-build cost** | $705K – $1.46M | $865K – $1.54M | +$160K floor, +$80K ceiling (internal was slightly conservative) |
| **Boutique build cost** | $260K – $525K | $285K – $556K | validated, essentially in-range |
| **Offshore build cost** | (not formally estimated) | $130K – $260K all-in (labor alone $89K – $180K; requires US architecture oversight) | new data point |
| **Annual institutional operating cost** | $700K / yr (Big-4) | $700K / yr validated as correct benchmark | ✓ validated |
| **Annual boutique operating cost** | $330K / yr | $330K / yr achievable at 1.5–2.0 FTE lean team but fragile against growth | ✓ validated with caveat |
| **Solon general hourly rate** | $300–$500/hr | $300–$500/hr fully validated by 2026 market data | ✓ validated |
| **Solon niche premium (guardrail + memory)** | $600–$1,000/hr | $600–$800/hr defensible NOW with production reference; $1,000/hr ceiling requires named enterprise references or published work (achievable post-Phase 2) | refined — $1K ceiling is future, not current |
| **Today floor valuation** | $60K – $120K | **$120K – $200K** — internal underprices the doctrine + harness layer | **+$60K to +$80K correction upward** |
| **Phase 1 complete (7–10 days)** | $120K – $250K | $120K – $250K validated | ✓ validated |
| **Phase 2 mid (30–60 days)** | $250K – $500K | $250K – $500K validated | ✓ validated |
| **Phase 3 mature (6–12 months) — founder-mode ceiling** | $500K – $1M+ | $500K – $1M+ validated as founder-mode ceiling | ✓ validated |
| **Phase 3 mature — STRATEGIC-BUYER ceiling** | (not in internal estimate) | **$1.8M – $4.5M** at 10–15× ARR multiples paid for AI-native assets in 2026 | new data — strategic-acquisition thesis extends ceiling meaningfully |

### 18.2 Part A — Acquirer landscape (new in DR)

Three priority acquirer categories identified by the DR, in order:

1. **PE-rolled-up agency portfolios** — 3–6× ARR multiples. Roll-up consolidators buying agencies that augment their existing portfolio with AI fulfillment capability.
2. **Marketing-services holding companies** — 6–12× ARR. **WPP Elevate28** is named as explicitly building what AMG has in their "agentic marketing platform" initiative. WPP / Omnicom / Publicis have current AI-infrastructure acquisition posture, per 2026 trade press cited in DR.
3. **Enterprise SaaS roll-ups** — 8–15× ARR. Most speculative but highest multiples.

**Strategic thesis (DR finding):** the WPP / Omnicom / Publicis "agentic marketing platform" angle is the sharpest strategic fit — they're building in-house exactly what AMG has already built solo. At the right moment, that's an acquire-over-build decision on their part. This is the acquirer narrative most worth cultivating between Phase 1 and Phase 2.

### 18.3 Part B — Secondary AI Platform ranking (for redundancy / failover onboarding)

Per the DR, the three strongest candidates for active/active AI infrastructure redundancy:

| Rank | Platform | Strongest reason | Largest unresolved risk |
|---|---|---|---|
| **#1** | **Google Gemini 2.5 Pro (API)** | MCP tool protocol (March 2026 release), 1M token context, Flash / Pro / Ultra model-tier routing, $1.25 – $10/M token pricing. Stable release, production-ready. | Explicitly NOT 3.x preview series — 3.x has no DRZ and 41-second TTFT in preview. Stay on 2.5 Pro. |
| **#2** | **OpenAI GPT-4.1 / GPT-5** | Best structured-output reliability (100% schema adherence), easiest integration, native adversarial-review primitive. | Safety mode on agentic tool use needs enterprise calibration. |
| **#3** | **Amazon Bedrock** | Strongest operationally for AWS-native shops; multi-model gateway. | HIGH integration complexity for AMG's non-AWS architecture; no native voice-AI layer means voice workloads cannot fail over to Bedrock. |

**Not recommended (currently):** xAI Grok — flagged as a monitoring candidate, not production-ready for this workload profile per the DR. Reason: agentic primitive gaps at the workload's required concurrency + MCP-protocol maturity vs. the #1 pick. This does NOT conflict with our `grok_review` tool using Grok as the adversarial reviewer channel (a different, narrow use-case); Grok as a failover general-inference provider is the case being deferred.

### 18.4 NDA-scoped questions flagged by the DR

Five questions the analyst noted would materially sharpen confidence if scoped under NDA:

1. Client vertical mix + churn rate (sharpens ARR multiple + acquirer thesis).
2. Actual inference mix (Claude vs. OpenAI vs. Perplexity vs. Grok — % of calls) for migration-risk pricing.
3. Current / target gross-margin split across the 3 product lines.
4. Proprietary IP status of the 4-layer hallucination defense (patentable? publishable?).
5. Founder runway + capacity to absorb a 12-month acquirer integration period.

These are deliberately NOT answered in the public DR; they're staged for a future NDA-scoped follow-up.

### 18.5 Doctrine authority + revision policy

`DOCTRINE_AMG_VALUATION_DR_2026-04-15.md` is co-canonical with Encyclopedia and Capabilities Spec for valuation and acquirer-thesis material. When internal numbers (Section 9, Section 11A.11) conflict with DR 2026-04-15, **DR supersedes** until superseded by a later-dated analyst pass. Internal estimates are updated to reference the DR rather than overwritten, so the valuation arc history is preserved.

Next analyst pass targeted for **2026-07-15** (quarterly cadence) to re-test the Phase 2 numbers once consulting pipeline is visible.

---

## APPENDIX A — KEY INFRASTRUCTURE VALUES

```
VPS: root@170.205.37.148 (HostHatch, 12-core/64GB/200GB NVMe, Ubuntu 22.04)
MCP: memory.aimarketinggenius.io (stateless OAuth 2.1, PM2)
Supabase AMG operator: egoazyasyrhslluossli
Supabase AIMG consumer: gaybcxzrzfgvcqpkbeiq
Cloudflare R2: amg-storage bucket
Stagehand: browser.aimarketinggenius.io
Grok API: api.x.ai/v1
Resend SMTP: smtp.resend.com:465 (noreply@aimemoryguard.com)
Payment primary (canonical 2026-04-15): PaymentCloud — application pending submission
Payment secondary (canonical 2026-04-15): Durango — application pending submission
Payment dead: Stripe (permanent), Paddle (REJECTED 2026-04-15)
Payment blocked: PayPal (Levar account frozen — do NOT use for JDJ)
Payment interim (until merchant approvals clear): manual invoice + ACH/wire
Domain: aimarketinggenius.io (migrating from aimarketinggenius.lovable.app)
Consumer: aimemoryguard.com
```

---

## APPENDIX B — SESSION COMMITS

### 2026-04-14 evening session (9 commits):

| Commit | Purpose |
|---|---|
| 9eb08da | ITEM 4 Gate #3 — SSH forensic template (read-only, 9-step runner) |
| df5ee2e | ITEM 4 Gate #1 v1.1 — hash-pinned pre-proposal gate, smoke-tested |
| 780d90d | ITEM 4 Gate #2 v1.1 — HMAC state + audit chain + 5-min hypothesis timer |
| 56d5064 | escape-hatch-verify.sh — 6-item preflight |
| 2353539 | ITEM 4 Gate #4 v1.2 audit — OPA policy + chrony + nonced ack + auto-revert |
| ce9c8db | Item 7 — launchd plist for 25-exchange Titan auto-restart |
| 06f664d | Item 5 security — threat model + watchdog truthfulness + breach audit + digest v2 |
| deaac8a | Item 6 cron/log audit — 4 propose-only configs + audit DR |
| ddc6c30 | CT-0414-09 AIMG extension-client + Perplexity QE wiring |
| 69a45d4 | feat(perf) — fast-mode auto-source + Haiku sub-agent scoping (cost bleed fix) |

### 2026-04-15 overnight session (8 commits — additive to above):

| Commit | Purpose |
|---|---|
| `1a65d4f` | CT-0414-09 Item 1 — rate-limit middleware + 21 integration tests + Perplexity A |
| `41d24a4` | fix(logrotate) — Item 6 apply: removed duplicate stanzas + added su root root |
| `b9e0887` | feat(perf) — parallel_dispatch.py v1.1 + spawn-stagger investigation note (DR_PERF) |
| `e3566e5` | docs(aimg) — CT-0414-09 phase 2 deploy-ready single-paste runbook |
| `cee70f0` | feat(autonomy+layer4) — CT-0415-05 P1 hooks live on VPS, P3 staged, layer-4 v2 ready |
| `ee39531` | docs — DR_PHONE_THEFT_REVOCATION_RUNBOOK rename to satisfy gitignore |
| (latest) | feat(autonomy) — CT-0415-05 Phase 1 hardening: persistent state + flock + PID targeting |
| (latest+1) | hooks/ct-0415-05-phase1/ + systemd/titan-restart-watcher.service mirror in harness |

**Total session commits across 14+15: 17 + supporting unstaged work (Channels titan-channel.ts on VPS, hardened hooks, /etc/amg envs, Supabase deploy artifacts).**

---

## APPENDIX C — KEY PEOPLE & RELATIONSHIPS

- **Solon Zafiropoulos** — Founder, sole operator, architect
- **Titan** — Autonomous executor (Claude Code on Mac + Claude Code CLI on VPS via CT-0415-05 Phase 2 Channels)
- **EOM** — Strategic brain (Claude.ai Opus project)
- **Aristotle** — Co-agent strategy + research (Perplexity in `#titan-aristotle` Slack channel, when channel is live)
- **Perplexity** — Primary adversarial reviewer (sonar-pro tier for DRs); also direct API for Titan auto-consult on blockers
- **Grok** — Secondary adversarial reviewer (dual-engine validation, blocked on grok_review MCP tool)
- **Kay/Trang** — Shop UNIS (active client, $3,500/mo, Apr 20 weekly meeting)
- **James/Ty** — Revel & Roll West (active client, $1,899/mo)
- **Levar (JDJ Investment Properties)** — pending founding member, kickoff Thursday 2026-04-16, RE investor "We Buy Houses" Lynn MA + multi-state expansion plan, A2P/10DLC differentiator (failed 3× before AMG)
- **Paradise Park Novi** — active client, $1,899/mo, FEC

---

## APPENDIX D — PRODUCTION SERVICES STATUS (2026-04-15 snapshot)

| Service | Status | Last verified |
|---|---|---|
| AIMG edge fn (`gaybcxzrzfgvcqpkbeiq`) | ✅ LIVE — HTTP 200 | 2026-04-15 03:01 UTC |
| MCP server (memory.aimarketinggenius.io) | ✅ LIVE — legacy JWT (Phase B pending) | continuous |
| n8n queue mode (60 lanes capacity) | ✅ active/active | 2026-04-12 |
| systemd `titan-restart-watcher.service` | ✅ active + enabled | 2026-04-15 03:13 UTC |
| Mac launchd `com.amg.titan-autorestart` | ⚠️ unloaded for night safety (smoke-tested PASS) | 2026-04-15 02:45 UTC |
| `titan-channel.ts` Bun MCP server | ✅ smoke-tested PASS, ready for production restart | 2026-04-15 03:30 UTC |
| Caddy reverse proxy + TLS auto-renewal | ✅ stable | continuous |
| Suricata IDS + Wazuh SIEM | ✅ rotation now capped (was 591MB unbounded) | 2026-04-15 03:14 UTC |
| logrotate amg-security/amg-custom + journald cap 500M | ✅ deployed | 2026-04-15 03:14 UTC |
| Hermes voice stack (Kokoro TTS + RNNoise) | ✅ duplex wired | 2026-04-12 |
| Stagehand persistent browser | ✅ available at browser.aimarketinggenius.io | continuous |
| Fast mode + Haiku sub-agent scoping | ✅ default-on (5-agent fast-probe 11.4s → 4.32s → 3.02s) | 2026-04-15 03:00 UTC |

---

*End of AMG Encyclopedia — 2026-04-15 compiled state.*
*Document version 1.2.*
*Classification: INTERNAL.*
*Patch authority: Solon + EOM. Last edit by Titan overnight 2026-04-15 per Solon directive.*
