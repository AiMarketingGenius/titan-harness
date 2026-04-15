# AMG CAPABILITIES SPEC SHEET — REDUNDANCY + VALUATION VERSION

**Prepared for:** External adversarial-review (build-cost estimation) + secondary AI platform onboarding (failover-readiness brief)
**Version:** v1.0 (2026-04-15) — derived from internal AMG Encyclopedia v1.2
**Classification:** SHAREABLE — trade-secret-scrubbed, no proprietary tool names, no internal codenames, no infrastructure identifiers
**Status:** Production-deployed, revenue-generating, ~12 months old

---

## PURPOSE OF THIS DOCUMENT

This spec sheet exists for two parallel use cases:

1. **External replacement-cost estimation.** Independent valuation by a senior AI consultancy or research partner to assess what it would cost to commission an equivalent stack from scratch.
2. **Secondary AI platform onboarding (redundancy / failover plan).** Brief for a second AI platform to mirror current production workloads in case of primary-platform outage. The intent is for AMG to maintain active/active capability across two AI infrastructure providers so that any single-vendor failure cannot interrupt client-facing operations.

To serve both, this document describes **what the system does** (capabilities, scale, output, SLAs) without revealing **how it does it** (specific tool names, vendor identifiers, architectural patterns proprietary to AMG, or any element that constitutes commercial trade secret).

---

## 1. EXECUTIVE OVERVIEW

AMG is a Boston-area AI infrastructure company operating three commercial product lines on a single shared platform:

- **Managed AI marketing service** (B2B subscription) — serving local businesses across hospitality, real estate, family entertainment, e-commerce, and professional services.
- **AI systems integration consulting** (project-based) — engagement scale ranging from $5,000 quick-win audits through $250,000+ full-platform white-label deployments.
- **Consumer AI product** (B2C subscription via cross-platform browser extension) — providing persistent memory + quality enforcement on top of mainstream AI assistants.

The shared platform underneath all three product lines is a multi-component AI fulfillment engine, deployed and operating today, generating recurring revenue from active clients with greater than 90% gross margin on subscription revenue and greater than 80% gross margin on project revenue.

**Built solo by the founder over approximately 12 months. Cash outlay over the build period was approximately $10,000.**

---

## 2. CAPABILITIES MATRIX

The platform performs the following classes of work simultaneously, on production-grade infrastructure, around the clock, without manual operator intervention except at human-gate decision points.

### 2.1 Client-Facing Service Delivery

| Capability | Description | Scale today |
|---|---|---|
| Multi-agent client interaction | A team of named, role-specialized AI agents handles client questions, content drafts, reputation management, SEO recommendations, and strategy discussions on behalf of subscribed clients. | 7 distinct agent personas, three model-cost tiers per persona, 24/7 availability |
| Automated content production | Long-form blog articles, social posts, email campaigns, and ad copy generated and scheduled per client subscription tier. | 4-20 long-form pieces per client per month at top tier |
| Reputation monitoring + response | Automated review monitoring across major review surfaces, draft responses written in client brand voice, escalation only when human judgment required. | Per-client SLA: response draft within 1 hour of negative review |
| Local SEO + Google Business Profile management | Audit, optimization, posting, and tracking across multi-location clients. | Up to 50 keywords tracked per client at top tier |
| Conversion rate optimization | Landing-page audits, A/B test design, heatmap interpretation, on-site copy iteration. | Up to 4 audits per month included at top subscription tier |
| Paid ad campaign management | Bid management, audience targeting, creative iteration, ROAS optimization across major paid platforms. | Ad spend range $5,000-$25,000/month per client at top tier |
| Voice AI inbound + outbound calls | Sub-60-second callback to web form leads; 24/7 inbound voice agent for booking, qualification, and lead capture. | Concurrent call capacity: limited only by upstream voice provider quota |
| Chatbot lead capture | 24/7 conversational AI on client websites, captures intent, routes to appropriate next action. | Embedded as drop-in script tag |
| Lead nurture sequences | Multi-channel (email + SMS + voice) nurture: 1 hour → daily for 7 days → weekly → biweekly cadences. | Per-client custom configurable |

### 2.2 Internal Operations + Development Velocity

| Capability | Description | Scale today |
|---|---|---|
| Autonomous code generation + deployment | The platform itself extends and improves itself through agentic code execution wrapped in deterministic safety guardrails. | 17+ commits in a single overnight session, all adversarially-reviewed at A-grade |
| Persistent cross-session memory | Decisions, tasks, sprint state, and operator standing rules persist across separate AI conversation threads via a custom memory layer. | 20+ memory tools, multiple memory types (fact / decision / preference / correction / action / narrative / episodic / entity) |
| Adversarial peer review | Every significant output is independently reviewed by at least one second AI provider before being marked complete. Minimum 9-out-of-10 quality gate. | Two independent reviewer providers wired |
| Self-healing infrastructure | Autonomous monitoring + remediation across web server, database, queue, voice, search index, credentials, backups, cost ceilings. | 10 monitored categories, 12 health timers, single supervisor daemon |
| 24/7 unattended operation | Systems operate without operator presence; alerts only on items requiring human judgment. | Operator-on-call only for explicit escalation tier |

### 2.3 Quality + Safety Enforcement

| Capability | Description |
|---|---|
| 4-layer hallucination defense | (1) Architectural enforcement via typed output contracts. (2) Adversarial review by a second AI provider. (3) Fact-check gate against a knowledge base + web search. (4) Tiered web-grounded verification for high-stakes claims. |
| Hard tier-A / tier-B / tier-C autonomy gating | Routine work auto-continues. Lockout-risk operations require explicit human confirmation. Credential-rotation operations require pre-approval and auditing. |
| Trade-secret compliance | A standing rule auto-injected into every operator session prevents specific vendor and tool names from appearing in client-facing output. |
| 4-gate lockout-prevention doctrine | Hash-pinned pre-proposal gate + cryptographically-signed audit chain + read-only forensic template + policy-as-code with timed auto-revert. |
| Anti-hallucination disclosure phrases | Mandatory tags on uncertain output: insufficient-data / proxy-data / single-source / inference / uncertain. |

### 2.4 Observability + Governance

| Capability | Description |
|---|---|
| Multiple operator dashboards | Mobile-optimized + desktop + ambient-status + aggregated-health views. |
| Governance Health Score | Numeric daily score tracking architectural drift across multiple anti-pattern categories. Currently 85.0/100 with regular adversarial validation. |
| Structured incident learning loop | Every incident generates a structured log entry feeding back into doctrine refinement. |
| Cross-track audit chain | Every significant decision is signed, timestamped, and traceable to its originating context. |

---

## 3. PRODUCT LINE DETAIL (PRICING + UNIT ECONOMICS)

### 3.1 Managed Service Subscriptions (current MRR ~$7,298)

| Tier | Monthly | Inclusions | Target buyer |
|---|---|---|---|
| Starter | $497 | Single-platform management, $500-$1,500 ad spend, 4 agents | Solo operators, < $300K revenue |
| Growth (anchor) | $797 | Dual-platform, $1,500-$5,000 ad spend, 6 agents + content production | Established SMB, $300K-$2M revenue |
| Pro | $1,497 | Full suite, $5,000-$25,000 ad spend, all 7 agents including senior strategy + CRO | Multi-location or premium SMB |
| Reputation-only standalone | $97 / $197 / $347 | Tiered reputation management without full stack | Owner-operators wanting reputation only |

14-day free trial, no credit card required.

### 3.2 Consulting / Systems Integration (engagement range $5K-$250K+)

| Engagement size | Typical scope | Timeline | Customer profile |
|---|---|---|---|
| $5,000-$10,000 | AI architecture audit + roadmap, single-domain workflow integration | 1-3 weeks | Solo agencies, SMB founders piloting AI |
| $15,000-$25,000 | Persistent cross-agent memory build, multi-agent system build-out, voice + chatbot stack | 3-6 weeks | Established agencies, mid-market businesses |
| $25,000-$50,000 | Custom fulfillment engine for one vertical, full integration build, white-label memory + agents | 6-10 weeks | Mid-market businesses with internal ops |
| $50,000-$100,000 | Partial template-export deployment (3-5 of 7 platform pillars), branded for client, with monthly retainer | 8-14 weeks | Established agencies wanting to resell, multi-location SMB chains |
| **$100,000-$250,000+** | **Full template-export deployment — all 7 pillars + custom operator-substrate trained on client's voice / SOPs / transcripts + full white-label + 6-12 month buildout + ongoing license retainer** | **4-8 months** | **Enterprise-scale clients, agencies wanting full operating system, PE-rolled-up agency portfolios** |

Single-client Year 1 LTV (standard subscription ladder): $72,500-$102,500. Full template-export Year 1 LTV: $150,000-$400,000+.

### 3.3 Consumer Product Subscriptions

Cross-platform browser extension providing persistent memory + quality enforcement on top of mainstream AI assistants.

| Tier | Monthly | Daily quota | Margin |
|---|---|---|---|
| Free | $0 | 20 calls/day | Marketing-cost (~$0.12/user/mo) |
| Basic | $4.99 | 50 calls/day | 94% |
| Plus | $9.99 | 150 calls/day | 91% |
| Pro | $19.99 | 300 calls/day | 91% |

Hard daily cost ceiling enforced per-user with auto-pause at threshold.

### 3.4 Ongoing Advisory + Memory License (retainer)

| Service | Monthly | Inclusions |
|---|---|---|
| Memory license + advisory | $1,000-$5,000 | Hosted memory layer access, monthly health report, bi-weekly office hours, security patches |
| Hourly overflow | $300-$500/hr (niche specialty $600-$1,000/hr) | Hallucination guardrail design, persistent memory engineering |

---

## 4. THE 7-PILLAR PLATFORM (FUNCTIONAL DECOMPOSITION)

The unified AI fulfillment platform is structured as 7 interlocking subsystems. The same 7 pillars deliver internal AMG operations, client-facing service, AND export-template deployments to consulting clients.

| Pillar | Function | Commercial surface |
|---|---|---|
| **A. Acquisition** | Outbound email + LinkedIn + SMS + voice + inbound chat + ambient orb status indicator | First touch with prospect |
| **B. Zero-deflection quoting** | Real-time pricing, custom hour estimation, on-the-spot proposal generation. Voice agent quotes prices and never deflects. | Convert intent into proposal |
| **C. Nurture + conversion** | Multi-channel (email / SMS / voice) cadenced sequence: 1hr → daily×7 → weekly → biweekly | Convert proposal into contract |
| **D. Onboarding** | Automated credential capture, NAP build, business-profile wiring, portal provisioning | Contract → live client |
| **E. Delivery + customer service** | Multi-agent service team, automated deliverables, sweep engine across 6 work types, automated client comms | Live client → recurring service delivery |
| **F. Client portal** | Live analytics, heatmaps, rankings, monthly reports, chat-with-agent | Client visibility + retention |
| **G. Operator escalation gate** | Triggers only for enterprise-scale / contract anomalies / legal / dollar-threshold breaches | Human-in-the-loop where it actually matters |

---

## 5. INFRASTRUCTURE ENVELOPE (SCALE + CAPACITY)

The platform runs on a single primary 12-core / 64GB-RAM Linux server (with documented secondary-provider failover lane planned). Operational ceilings under this hardware envelope:

| Metric | Ceiling |
|---|---|
| Concurrent autonomous operator sessions | 12 |
| Concurrent heavy tasks | 8 |
| Concurrent general workers / sub-agents | 10 |
| Concurrent CPU-heavy workers | 4 |
| Workflow orchestration parallel branches per workflow | 20 |
| Concurrent heavy workflows | 3 |
| **Total parallel workflow lanes** | **60** |
| Concurrent batched LLM call lanes | 8 |
| Maximum batch size per lane | 15 |
| **Theoretical maximum concurrent LLM calls** | **120** |

Soft + hard CPU + RAM throttle thresholds are enforced via policy-as-code; the system rejects new heavy work above hard limits rather than failing under load.

Monthly infrastructure cost: approximately $360 (server + AI inference + supporting services).

---

## 6. RELIABILITY DOCTRINE LIBRARY

The platform ships with multiple cross-validated operational doctrines. Each is a 1,500-2,500 line design document, backed by published reliability research (industry standard: Google SRE, Netflix Chaos Engineering, IBM MAPE-K, AgentOps 2025), and adversarially-validated 9+/10 by at least one independent AI reviewer.

| Doctrine | Status | Coverage |
|---|---|---|
| Resilience doctrine | Complete (5/5 deltas shipped) | Three-tier response model, 7 universal principles, 12 domain specs, 7 adversarial 3am scenarios, central watchdog architecture, structured incident learning loop, 5-phase implementation roadmap, 7 domain-specific SLOs |
| Security doctrine | Complete (3/3 phases shipped) | File integrity monitoring, heartbeat, encrypted backups, drift detection, isolated execution user, auth hardening, secrets remediation, RLS audit, threat model, watchdog load test, 4-source security digest |
| Governance doctrine | Complete (3/3 phases shipped, A-graded) | Behavioral baseline, drift scoring (statistical test), governance dashboard, Governance Health Score, anti-pattern monitoring across multiple categories, weekly review cadence, sister-doctrine integration, red team testing |
| Lockout-prevention doctrine | Audit-mode shipped, enforce-flip pending operator attestations | 4-gate hash-pinning + audit-chain + forensic template + policy-as-code |
| Access-redundancy doctrine | Drafted, awaiting cross-validation | Secondary provider lane for server + database access |
| Uptime doctrine | Drafted, awaiting cross-validation | 99.95% SLO design with error budget |
| Data-integrity doctrine | Drafted, awaiting cross-validation | Checksums, snapshot verification, restore drills |
| Recovery doctrine | Drafted, awaiting cross-validation | Disaster recovery runbook |

---

## 7. QUALITY ENFORCEMENT (4-LAYER HALLUCINATION DEFENSE)

| Layer | Mechanism |
|---|---|
| L1 — Architectural enforcement | Deliver-task contract: agent outputs must match expected schema. JSON schema validation, typed envelope. |
| L2 — Adversarial reviewer | Second AI provider reviews the first's output. Cross-validation, minimum 9+/10 agreement gate. |
| L3 — Fact-check gate | Knowledge-base + web grounding for factual claims. |
| L4 — Tiered web-grounded verification | Premium adversarial review for high-stakes investor or contract artifacts. |

Standing rule: adversarial review minimum is two independent providers. Self-review never counts as sole validation.

---

## 8. CURRENT FINANCIAL POSITION

| Metric | Value |
|---|---|
| MRR (recurring, 3 active clients) | ~$7,298 |
| Pending founding-member contract | 1 (real-estate investor vertical) |
| Infrastructure operating cost | ~$360/month |
| Gross margin (recurring revenue) | > 90% |
| Gross margin (project revenue) | > 80% |
| Target MRR 6-month | $15,000 - $25,000 |

---

## 9. ESTIMATED COMMERCIAL REPLACEMENT VALUE

The internal estimate (subject to independent validation, which is one purpose of this document) breaks down as follows. **Estimates exclude the founder's accumulated operational expertise + institutional context, which are not separable from the platform.**

### 9.1 Senior consultancy (Big-4 estimate) build cost

| Component | Estimate |
|---|---|
| Persistent agent memory layer (custom build) | $150K - $300K |
| 7-agent orchestration + routing + standing operator instructions | $100K - $250K |
| 4-layer hallucination guardrail | $75K - $150K |
| Workflow orchestration + workflow library | $40K - $80K |
| Persistent browser automation | $30K - $60K |
| Server + reverse proxy + security hardening + intrusion detection | $50K - $100K |
| 4 production reliability doctrines | $100K - $200K |
| Deterministic harness layer (hooks + escape-hatch + policy-as-code + lifecycle) | $40K - $80K |
| Cross-platform browser extension (consumer product MVP) | $30K - $60K |
| Specialist project + knowledge base architecture | $50K - $100K |
| Admin portal + 4 dashboards | $40K - $80K |
| **Subtotal — initial build** | **$705K - $1.46M** |
| **Annual operating cost (2 engineers + SRE + monitoring + on-call)** | **$700K / year** |

### 9.2 Boutique consultancy build cost

| Component | Estimate |
|---|---|
| Same 11-component scope above | $260K - $525K initial build |
| Annual operating cost (lighter team) | $330K / year |

### 9.3 Actual cash outlay incurred by current founder

- Time investment: approximately 12 months of intense solo work
- Infrastructure: approximately $4,320 over 12 months
- Tooling + AI subscriptions + API tokens: approximately $5,000 over the build period
- **Total cash outlay: approximately $10,000**

**Delta: roughly $250K-$1.5M+ market build value created with approximately $10,000 in direct cash outlay.**

---

## 10. MATURITY-STAGE VALUATION ARC (PLATFORM AS ASSET)

| Stage | Platform asset valuation | Rationale |
|---|---|---|
| **Today** (unfinished, internal-use proven, not yet sold as product) | $60K - $120K infrastructure value | Architecture exists, doctrines shipped, no external product sale yet |
| **Phase 1 complete (~7-10 days from snapshot date)** | $120K - $250K | First template-export consulting calls staged, near-term revenue probability priced in |
| **Phase 2 mid (~30-60 days)** | $250K - $500K | First consulting contract closed at $25K-$100K, pipeline visible, consumer apps in beta |
| **Phase 3 mature (6-12 months)** | $500K - $1M+ | Multiple recurring consulting clients + 2-3 productized verticals + template-export deals; valuation no longer "rebuild cost" but "discounted cashflow + multiple expansion on AI infrastructure category comps" |

---

## 11. SECONDARY AI PLATFORM ONBOARDING SPECIFICATION (FOR REDUNDANCY / FAILOVER)

This section is specifically for a second AI platform stepping in to provide active/active or hot-standby coverage.

### 11.1 Workloads to absorb

| Workload | Description | Volume estimate | SLA target |
|---|---|---|---|
| Operator decision-loop | Primary autonomous operator that sequences work, executes plans, reviews adversarial feedback, commits code | 1 active session, up to 12 concurrent | < 5 min handoff time on primary outage |
| Agent persona inference | 7 distinct client-facing personas, each with role + tone constraints | Variable; bursts to 120 concurrent calls | < 2 sec p50 first-token |
| Adversarial review | Independent quality grading with structured rubric | 1-5 review calls per major artifact | < 30 sec per review |
| Memory query / write | Persistent cross-session memory with semantic + hybrid search | Hundreds of operations per day | < 500 ms p95 query |
| Voice agent inbound + outbound | Real-time conversational AI with sub-60-second callback latency | Per-client subscription tier dependent | < 60 sec total callback latency end-to-end |
| Content production | Long-form blog, social, email, ad-copy generation per client tier | 4-20 long-form pieces per client per month at top tier | 24 hr turnaround per piece |
| Code authoring + commit | Autonomous code generation with adversarial review gate | 5-20 commits per active development day | A-grade adversarial review minimum |

### 11.2 Required capabilities of a viable secondary AI platform

To serve as a credible failover, a secondary platform must support:

1. **Tool-use protocol** compatible with our existing memory + web-fetch + browser-control + file-system + bash tool surface
2. **System prompt + standing rules injection** at session start (we currently inject ~20 prioritized rules per session)
3. **Long-context retention** within a single session of at least 200K tokens (current primary supports significantly more)
4. **Streaming first-token latency** under 2 seconds for routine work
5. **Adversarial review API** with structured grading output (or comparable evaluation hook)
6. **Multi-tier model routing** (light / medium / heavy model classes routed by task type)
7. **Sub-agent / sub-process spawn** for parallel work fan-out
8. **Stable JSON output mode** for structured agent contracts
9. **Persistent memory tooling** OR willingness to integrate with our existing memory layer via standard protocol
10. **Permission / safety mode** that can be configured to suppress per-tool consent prompts on routine work while preserving human-gate operations

Examples of platforms typical for this evaluation (not endorsement; require empirical benchmarking against actual workloads): the major frontier-model providers and their developer-platform variants, plus the leading agentic-IDE and code-execution platforms in market today. The reviewer is requested to recommend the strongest 2-3 candidates for our specific workload profile.

### 11.3 Recommended failover architecture

- **Active / active across two providers** for inference (already partially achieved via multi-provider gateway).
- **Single shared memory layer** continues to be the source of truth across both providers.
- **Workflow orchestration layer** continues running on our infrastructure; both AI providers connect to it as workers.
- **Adversarial review** rotates between providers; if one is reviewed-by-the-other, no single-vendor blind spot.
- **Standing operator instructions** maintained as a single canonical document (this spec sheet plus the internal full document) deployed to both providers' system-prompt slots simultaneously.

### 11.4 Critical handoff points to test before declaring failover-ready

1. Operator session can resume mid-conversation on secondary platform with no data loss.
2. Memory query results match within tolerance across both providers.
3. Adversarial review gradings agree (or document the structured disagreement) when both providers review the same artifact.
4. Voice agent first-utterance latency on secondary provider matches the < 60 sec end-to-end SLA.
5. Long-context retention of operator standing rules survives session restart on secondary provider.
6. Permission / safety mode on secondary provider does not block routine work that primary provider auto-approves.

---

## 12. WHAT THIS DOCUMENT INTENTIONALLY DOES NOT INCLUDE

To preserve commercial trade secret while providing enough detail for both valuation and failover planning, this spec sheet **deliberately omits**:

- Specific names of any AI provider, AI model, vendor, or third-party tool currently in our stack
- Specific names of any internal codename for platform subsystems, agents, doctrines, or sprints
- Specific server hostnames, IP addresses, project identifiers, file paths, database identifiers, JWT contents, or credential file paths
- Specific cost-cap thresholds, alert thresholds, cron schedules, or tunable policy values
- Specific commit hashes, sprint identifiers, task identifiers, or ticket numbers
- The full text of any of the production reliability doctrines (their existence + scope is described, but the prescriptive content remains internal)
- The founder's personal context, family details, prior business history below summary level, or operator-style preferences
- Client names, client industry combinations that could be reverse-engineered to a specific named client, or any client-specific revenue figures

A reviewer or secondary-platform team that needs additional detail to complete a valuation or onboarding should request the relevant scoped detail under NDA. The internal full encyclopedia (1,400+ lines) is available at the founder's discretion under appropriate protection.

---

## 13. COMBINED PERPLEXITY DEEP RESEARCH PROMPT (BOTH QUESTIONS IN ONE SHOT)

Copy this prompt verbatim into Perplexity Deep Research (Sonar Pro tier with extended thinking) and attach the body of this spec sheet (Sections 1-12) as the source document.

> **Brief.** I am submitting a trade-secret-scrubbed capability spec sheet for an AI infrastructure platform built solo over approximately 12 months by a Boston-area founder. The platform is production-deployed, revenue-generating (approximately $7,298 MRR with greater than 90% gross margin on subscription revenue), and supports three commercial product lines simultaneously: a managed AI marketing service for SMBs, an AI systems integration consulting practice with engagements ranging from $5,000 to $250,000+, and a cross-platform consumer browser extension subscription product. The capability spec sheet attached describes WHAT the platform does and at what scale, but intentionally omits WHAT specific vendors, tools, or platforms are used to deliver those capabilities (this is preserved as commercial trade secret).
>
> I need you to perform two assessments in a single Deep Research run. Both are equally important and the deliverable is a single integrated report.
>
> ---
>
> ### PART A — INDEPENDENT REPLACEMENT-COST AND ASSET VALUATION
>
> Assess what it would cost to commission an equivalent platform from scratch, what it would cost to operate, and what the platform is worth as an asset at progressive maturity stages.
>
> **A1. Total replacement build cost.** What would a senior AI systems integrator charge to commission an equivalent platform from scratch? Provide separate estimates for:
> - Big-4 / Tier-1 global consultancies (Deloitte, Accenture, IBM, PwC, EY)
> - Boutique AI consultancies (Boston / NYC / SF specialists, 10-50 person firms)
> - Offshore + nearshore vendors (India + LATAM)
>
> Itemize the build estimate by major capability component (memory layer, multi-agent orchestration, hallucination guardrail, workflow orchestration, browser automation, security hardening, reliability doctrines, harness layer, consumer browser extension, knowledge-base architecture, admin dashboards). Show low / mid / high range per component per integrator tier.
>
> **A2. Annual operating cost.** What headcount and infrastructure spend would an outsourced operator need to keep the platform running at the documented capacity ceilings (Section 5) plus the reliability doctrines (Section 6)? Itemize: engineering FTEs, SRE / on-call FTE, customer-success FTE, monthly cloud + AI inference + tooling spend.
>
> **A3. Founder market valuation.** The internal estimate is that the founder commands a senior AI architect market rate of $300-$500/hr (Boston market), and a niche-expertise premium of $600-$1,000/hr for hallucination-guardrail and persistent-memory work specifically. Validate or correct this against current 2026 freelance + retainer + advisory rate data for senior AI architects with proven production deployments. State the methodology used.
>
> **A4. Maturity-stage asset valuation.** Validate or correct the four-stage valuation arc proposed in Section 10: today's infrastructure-only rebuild value at $60K-$120K → Phase 1 (7-10 days from snapshot date, sales engine + first consulting calls warm) at $120K-$250K → Phase 2 mid (30-60 days, first consulting contract closed) at $250K-$500K → Phase 3 mature (6-12 months, multiple consulting clients + 2-3 productized verticals + template-export deals) at $500K-$1M+. Specify which valuation methodology (DCF, comparable-transaction, replacement-cost, multiple-of-revenue, multiple-of-EBITDA) is most appropriate per stage and why.
>
> **A5. Strategic positioning + acquirer landscape.** What is the strongest acquisition or strategic-investor thesis for this platform at each maturity stage? Identify the 3-5 most likely acquirer categories (enterprise SaaS roll-ups, AI infrastructure players, marketing-services holding companies, agency-tech consolidators, PE-rolled-up agency portfolios). What multiples would each category typically pay for an asset of this profile in 2026?
>
> ---
>
> ### PART B — SECONDARY AI PLATFORM SELECTION FOR REDUNDANCY / FAILOVER
>
> Recommend the strongest 2-3 candidate AI platforms to onboard as an active/active or hot-standby redundancy partner against single-vendor outage risk on our primary AI inference provider. We need continuous warm-mode validation, not single-shot cold-start failover.
>
> **B1. Workload coverage assessment.** For each candidate platform, indicate which of the workloads in Section 11.1 the platform can fully absorb, partially absorb, or not absorb. Use the published 2026 capability documentation for each candidate.
>
> **B2. SLA realism.** For each candidate, state which of the SLAs in Section 11.1 the platform can credibly meet (cite published latency / uptime / context-window benchmarks). Where the platform falls short of our SLA, state the realistic alternative number we would have to accept.
>
> **B3. Capability gap report.** For each item in Section 11.2 (10 required capabilities of a viable secondary platform), indicate Yes / Partial / No per candidate. Provide brief detail on each Partial and No.
>
> **B4. Pricing model.** Provide an annual contract cost estimate per candidate, assuming we route 50% of our inference traffic to the secondary in active/active mode. Use 2026 published enterprise-tier pricing where available; flag where the candidate requires custom contract negotiation.
>
> **B5. Migration risk + integration complexity.** For each candidate, what is the integration complexity (low / medium / high) and what specific items from Section 11.4 are likely to fail the failover-readiness test? Recommend the minimum sequence of pre-deployment integration tests.
>
> **B6. Continuity guarantee.** Compare the candidates on contractual continuity guarantees: model deprecation policy, regional availability, data-residency options, planned-downtime SLA, force-majeure terms. Where a candidate has weaker continuity guarantees than our primary, flag it.
>
> **B7. Final recommendation.** Rank the top 3 candidates by overall fit for active/active deployment with our workload + SLA profile. State the single strongest reason for the #1 pick and the single largest unresolved risk.
>
> ---
>
> **Deliverable format.** A single integrated report with both Part A and Part B, structured with the exact sub-section identifiers above (A1-A5, B1-B7). Cite all sources. Where you require additional scoped detail under NDA to sharpen any answer, flag it explicitly with the specific question we would need to brief you on.
>
> **Confidence flags.** Mark each conclusion with one of: HIGH (multiple independent sources agree, current 2026 data), MEDIUM (single authoritative source or recent extrapolation), LOW (inference from older data or limited evidence base).

---

## 14. INTERNAL TERM CLARIFICATION

For the founder's reference: the industry term Solon was searching for is most commonly **AI systems integrator** (commonly abbreviated "AI integrator" in casual usage). Adjacent and partially-overlapping terms used by different segments of the market include:

- **AI consultancy** (broader, often retainer-based advisory)
- **AI implementation partner** (more vendor-aligned, e.g., "Microsoft AI implementation partner")
- **Agentic AI consultancy** (newer term, 2025-2026 vintage, specifically for multi-agent systems)
- **AI engineering studio** (smaller / boutique / project-shop framing)
- **AI development house** (closest analog to "software development house" — full lifecycle build + maintain)

For Perplexity's response in Part A, the most useful term to anchor pricing benchmarks is **AI systems integrator** broken into Big-4 / boutique / offshore tiers as in the prompt above.

---

*End of capabilities spec sheet — version 1.0 (2026-04-15).*
*Internal reference: derived from AMG Encyclopedia v1.2.*
*Patch authority: founder + EOM. Editing protocol: surgical updates only.*
