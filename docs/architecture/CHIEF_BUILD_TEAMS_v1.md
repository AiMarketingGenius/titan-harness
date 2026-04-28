# Chief Build Teams v1

**Target canonical path:** `/opt/amg-docs/architecture/CHIEF_BUILD_TEAMS_v1.md`
**Staged path:** `/Users/solonzafiropoulos1/titan-harness/docs/architecture/CHIEF_BUILD_TEAMS_v1.md`
**Date:** 2026-04-27
**Owner:** Achilles design pass, parallel to Titan CT-0427-36
**Status:** DESIGN ONLY. No build starts until Solon greenlights.

## 0. Context And Constraints

This design gives the three Kimi chiefs, Hercules, Nestor, and Alexander, Titan-parity operating leverage without duplicating Titan's own lieutenants. Titan's Daedalus, Artisan, and Mercury remain shared Titan-dispatched resources. The chiefs get separate execution teams with their own names, task lanes, cost gates, memory bootstrap, and verifier wiring.

The design references the current Ford-factory rule from v4.0/v4.0.1: every agent class runs four deep, one active at a time, on six-hour rotations. It also uses the v4.0.1 Argus/Hygeia pattern: one agent acts, a paired verifier checks the result, and any unresolved mismatch is logged as a blocker instead of buried.

Current MCP note: `get_recent_decisions` and `log_decision` are available in this session. The requested `get_bootstrap_context` and `search_memory` tool surfaces were not available here, which matches recent Hercules memory reporting those routes as degraded/404 while decision logging remains functional. This design treats restoration/generalization of those routes as part of the build sequence.

## 1. Architecture Principle

Each chief is a decision layer, not a hands layer. Chiefs translate Solon's intent into scoped build orders, choose the right internal builder, set acceptance criteria, enforce cost caps, and read verification receipts before calling work complete.

Each builder is owner-scoped to exactly one chief. A builder may not claim work for another chief unless the task is explicitly routed through a cross-chief escalation path. This prevents the current Titan resource pool from becoming a hidden dependency for every lane.

Every task follows the same lifecycle:

1. Chief receives or discovers an objective.
2. Chief decomposes it into a task with owner tags and acceptance criteria.
3. Builder claims atomically.
4. Builder emits structured receipt and deliverable link.
5. Verifier checks the receipt against evidence.
6. Chief logs the final decision or blocker.

## 2. Per-Chief Roster

### 2.1 Hercules Build Team

Hercules owns strategy, architecture review, operating doctrine, queue health, and cross-team orchestration. His team should be good at turning ambiguous strategic intent into safe build orders.

| Builder | Role | Why This Builder Reports To Hercules | Default Model Tier | Daily Sub-Cap |
|---|---|---|---|---|
| Iolaus | Build-order compiler | Iolaus was Hercules's helper; this role decomposes strategy into queueable work packets with acceptance criteria. | Kimi K2.6 or DeepSeek V4 Flash | $1.25 |
| Cadmus | Doctrine and registry writer | Cadmus is the founder/scribe archetype; this role maintains architecture docs, capability manifests, runbooks, and naming registries. | Local Qwen/DeepSeek first, Kimi fallback | $0.75 |
| Themis | Risk and approval gate | Themis handles law/order; this role checks owner-risk, public-facing risk, credentials, live infra, and whether Solon approval is required. | Local DeepSeek R1 first, V4 Reasoner only on high risk | $1.25 |
| Nike | Proof closer | Nike owns victory conditions; this role assembles proof packets, before/after evidence, and final verification summaries. | Kimi K2.6 or Gemini Flash-Lite | $0.75 |

Hercules family cap: $5.00/day.

### 2.2 Nestor Build Team

Nestor owns product, UX, demos, Revere/Chamber-facing artifacts, WordPress/HTML mockups, PRDs, and mobile-safe delivery. His team should be biased toward user experience and client-ready presentation, while never touching backend schema, deploys, or credentials.

| Builder | Role | Why This Builder Reports To Nestor | Default Model Tier | Daily Sub-Cap |
|---|---|---|---|---|
| Ariadne | UX flow mapper | Ariadne is the thread through the maze; this role maps user journeys, IA, onboarding paths, and demo scripts. | Kimi K2.6 for taste, local fallback | $1.25 |
| Calypso | Interface polish reviewer | Calypso owns visual surface quality, mobile fit, spacing, contrast, and screenshot review. | Kimi K2.6 or Gemini Flash | $1.00 |
| Demeter | CRM and lifecycle mapper | Demeter handles growth cycles; this role maps member lifecycle, lead flow, retention hooks, and CRM UX. | Local Qwen/DeepSeek first | $0.75 |
| Pallas | Product acceptance tester | Pallas owns practical judgment; this role defines Nestor's acceptance tests and verifies mockups against client-safe constraints. | Local DeepSeek R1 first, V4 Flash fallback | $1.00 |

Nestor family cap: $5.00/day.

### 2.3 Alexander Build Team

Alexander owns content, SEO, voice/chat AI, newsletters, offer messaging, and conversation tuning. His team should be biased toward language quality, search usefulness, and voice/demo reliability.

| Builder | Role | Why This Builder Reports To Alexander | Default Model Tier | Daily Sub-Cap |
|---|---|---|---|---|
| Calliope | Long-form content architect | Calliope is the epic muse; this role drafts content briefs, pillar pages, newsletters, and campaign narratives. | Kimi K2.6 for brand voice | $1.25 |
| Pythia | SEO and market-intent researcher | Pythia handles prophecy/search intent; this role produces keyword maps, SERP assumptions, and ranking timelines. | Local + Brave first, Perplexity/Sonar only by exception | $1.00 |
| Orpheus | Voice and chat dialogue tuner | Orpheus owns spoken flow; this role tunes voice/chat scripts, sentiment, interruption handling, and CRM note language. | Kimi K2.6 or local Qwen | $1.25 |
| Clio | Evidence and case-study keeper | Clio is memory/history; this role keeps proof claims, case studies, citations, and public-safe source snippets clean. | Local DeepSeek R1 first | $0.75 |

Alexander family cap: $5.00/day.

### 2.4 Shared Verifiers

Aletheia, Argus, Hygeia, Cerberus, and Warden remain shared infrastructure, not chief-specific builders. They do not report to Hercules/Nestor/Alexander. They verify and protect the whole factory.

| Shared Agent | Role In Chief Parity |
|---|---|
| Aletheia | Verifies task completion claims, artifact existence, and receipt honesty. |
| Hygeia | Cleans poisoned memory/KB entries and, after v4.0.1, handles safe remediation work dispatched by Argus. |
| Argus | Watches infrastructure/resource health and verifies Hygeia's remediation loops. |
| Cerberus | Watches security/anomaly signals and false-positive cascades. |
| Warden | Evicts stale locks and protects queue progress. |

## 3. MCP Integration Plan

### 3.1 Queue Contract

Chiefs and builders use the same queue pattern Titan uses today.

| Operation | MCP Tool Name | REST Route In Existing Client | Required Behavior |
|---|---|---|---|
| Queue work | `queue_operator_task` | `POST /api/queue-task` | Chief creates a scoped task with objective, instructions, acceptance criteria, priority, and tags. |
| Claim work | `claim_task` | `POST /api/claim-task` | Builder claims atomically using its own operator id. No work starts without a claim. |
| Update status | `update_task` | `POST /api/update-task` | Builder moves `approved/pending -> active -> completed/blocked/failed`; terminal states use the existing two-hop active transition. |
| Log final decision | `log_decision` | `POST /api/decisions` | Chief and builder both log receipts, decisions, and proof links. |
| Flag blocker | `flag_blocker` | MCP bridge or future REST equivalent | Any owner-risk, missing context, tool outage, approval need, or failed verifier result becomes a blocker. |

### 3.2 Tags And Routing

Every chief-family task must include:

| Tag | Example | Purpose |
|---|---|---|
| `chief:<name>` | `chief:hercules` | Owns the outcome. |
| `agent:<builder>` | `agent:iolaus` | Selects the builder daemon. |
| `owner:<chief>` | `owner:hercules` | Prevents cross-chief accidental claims. |
| `lane:<type>` | `lane:doctrine`, `lane:ux`, `lane:voice` | Helps dashboards and verifiers route correctly. |
| `cost:tier` | `cost:cheap`, `cost:local`, `cost:exception` | Feeds cost gate and review dashboards. |

Builder daemons only claim tasks matching both `agent:<builder>` and `owner:<chief>`. A task missing either tag is rejected or blocked, not silently ignored.

### 3.3 Receipt Schema

Every builder returns a strict JSON receipt:

```json
{
  "ok": true,
  "task_id": "CT-...",
  "chief": "hercules",
  "builder": "iolaus",
  "deliverables": ["absolute path or URL"],
  "claims": ["specific claim verifiable from deliverable"],
  "verification_commands": ["read-only command or check"],
  "cost_usd_est": 0.012,
  "blocked": false,
  "blocker": ""
}
```

The chief may not mark the task complete unless the receipt has a deliverable, a concrete proof path, and at least one verification signal. Aletheia verifies artifact claims. For infrastructure or memory hygiene work, Argus or Hygeia performs the paired check.

### 3.4 Chief Dispatch Loop

Each chief runs a lightweight dispatcher:

1. Polls recent decisions and task queue every 30 seconds.
2. Hydrates memory for its chief scope.
3. Selects the right builder from its roster.
4. Queues a bounded task with acceptance criteria.
5. Watches for completed receipts.
6. Calls verifier.
7. Logs either `chief_task_verified` or `chief_task_blocked`.

Chiefs do not directly edit repos, deploy, send external messages, rotate credentials, or perform destructive actions. They dispatch to builders or flag blockers.

## 4. Persistent Memory Plan

### 4.1 Universal Chief Bootstrap

Each chief needs the same cold-start memory privilege Titan has today. The build should generalize Titan's boot prompt automation into `chief_bootstrap_renderer`, producing one boot prompt per active chief and one lcache file per active builder.

On every session start, each chief should attempt:

1. `get_bootstrap_context(project_id="<chief>", scope="both", max_decisions=15)`
2. `get_recent_decisions(count=15)` with chief filtering where available
3. `search_memory(query="<chief> current project blockers queue state")`
4. `search_memory(query="v5.0 model sovereignty DeepSeek Aristotle 7 AMG agents")`
5. `search_memory(query="CT-0427-41 Kimi account isolation Vendor runtime")`

If any route is unavailable, the chief logs `bootstrap_degraded:<chief>` and uses the most recent local bootstrap file plus MCP recent decisions. It must not pretend full memory was loaded.

### 4.2 Files Of Record

| File | Purpose |
|---|---|
| `/opt/amg-docs/chiefs/hercules/bootstrap.md` | Hercules standing context and lane boundaries. |
| `/opt/amg-docs/chiefs/nestor/bootstrap.md` | Nestor product/UX/Revere context. |
| `/opt/amg-docs/chiefs/alexander/bootstrap.md` | Alexander content/SEO/voice context. |
| `/opt/amg-governance/lcache/<agent>.md` | 3KB rolling continuity cache for each chief and builder instance. |
| `/opt/amg-governance/shift_state/<agent>.json` | Active shift, lock holder, last handoff, and health state. |
| `/opt/amg-docs/architecture/CHIEF_BUILD_TEAMS_v1.md` | This design. |

### 4.3 Memory Write Discipline

Chiefs and builders write only durable facts:

| Event | Required Log |
|---|---|
| Task dispatched | `log_decision(tag="chief_dispatch:<chief>")` |
| Builder receipt accepted | `log_decision(tag="builder_receipt:<builder>")` |
| Verification passed | `log_decision(tag="chief_verified:<chief>")` |
| Verification failed | `flag_blocker(project_source="<chief>", severity=...)` |
| Memory route degraded | `log_decision(tag="bootstrap_degraded:<chief>")` |
| Shift handoff | `log_decision(tag="shift_handoff:<agent>")` |

## 5. Ford-Factory Rotation

Every chief and every builder runs four deep. Only one instance is active at a time. Off-shift instances are cold by default unless Solon explicitly chooses warm standby for faster handoff.

| Family | Shift Changes UTC | Active Pattern |
|---|---|---|
| Hercules family | 00:00, 06:00, 12:00, 18:00 | `hercules-A/B/C/D`, `iolaus-A/B/C/D`, `cadmus-A/B/C/D`, `themis-A/B/C/D`, `nike-A/B/C/D` |
| Nestor family | 02:00, 08:00, 14:00, 20:00 | `nestor-A/B/C/D`, `ariadne-A/B/C/D`, `calypso-A/B/C/D`, `demeter-A/B/C/D`, `pallas-A/B/C/D` |
| Alexander family | 04:00, 10:00, 16:00, 22:00 | `alexander-A/B/C/D`, `calliope-A/B/C/D`, `pythia-A/B/C/D`, `orpheus-A/B/C/D`, `clio-A/B/C/D` |

Handoffs happen only at safe boundaries:

| Boundary | Rule |
|---|---|
| Conversational turn | Chiefs soft-handoff with a visible save window. |
| Task completion | Builders hand off after receipt or blocker log. |
| Atomic tool call | Never kill mid-call. Wait for completion or timeout. |
| Critical work | Respect a short TTL lock; hard cap at 30 minutes unless Solon explicitly overrides. |

## 6. Cost Discipline

Initial caps should match the existing chief-cost-gate posture: $5/day per chief family and $15/day fleet total across the three chief teams. This is deliberately conservative while the system proves usefulness and avoids runaway retry loops.

| Scope | Daily Cap | Notes |
|---|---|---|
| Hercules family | $5.00 | Strategy and architecture can escalate, but Themis must mark exceptions. |
| Nestor family | $5.00 | Most UX/product checks should use local or cheap models. |
| Alexander family | $5.00 | Kimi used for voice/brand; local used for evidence/SEO preprocessing. |
| Chief-builder fleet | $15.00 | Shared hard cap; if hit, all non-P0 chief-builder work blocks. |
| P0 override | Solon explicit only | Must log `cost_exception:<chief>` with reason and expected ceiling. |

Cost gate behavior:

1. Estimate cost before every paid call.
2. Check chief-family cap and fleet cap.
3. Prefer cache hit if task fingerprint already exists.
4. Refuse premium models for routine work.
5. Record actual cost after call.
6. Block after cap hit; do not keep retrying on alternate paid models.

## 7. Verifier Wiring

The v4.0.1 mutual-check principle becomes the chief parity rule.

| Work Type | Primary Verifier | Mutual Check |
|---|---|---|
| Artifact claim, file path, receipt honesty | Aletheia | Chief proof closer reviews Aletheia failure before blocker escalation. |
| Memory/KB cleanup | Hygeia | Aletheia verifies Hygeia did not scrub valid facts. |
| Infrastructure/resource remediation | Argus verifies Hygeia | Hygeia checks Argus false positives; Cerberus flags repeated false alarms. |
| Security-sensitive task | Cerberus | Themis must approve before dispatch. |
| Cost exception | ChiefCostGate ledger | Themis validates Solon approval exists. |

Chiefs may not self-verify their own builder completions. They can accept or reject verifier outputs, but the verifier result must be present in the decision log.

## 8. Build Sequence

### Phase 0: File The Design

Create this architecture document and log the design decision. No build starts.

Exit gate: Solon greenlight.

### Phase 1: Registry And Names

Add the new builders to the capability manifest with `current_status="planned"` and `no_executor_action="reject_with_explanation"` until executors exist. This prevents phantom-agent stalls.

Exit gate: queue rejects unbuilt chief-builder names with a clear explanation.

### Phase 2: Bootstrap Generalization

Build `chief_bootstrap_renderer` and generate boot prompts for Hercules, Nestor, and Alexander. Restore or replace missing `get_bootstrap_context` and `search_memory` routes, or add a documented degraded fallback.

Exit gate: each chief can cold-start with recent decisions, owner-scoped memory, and lcache.

### Phase 3: MCP Dispatcher Skeleton

Build chief dispatch loops without builder execution. Chiefs can queue tasks, watch status, and log blockers, but no builder performs work yet.

Exit gate: synthetic task dispatch lands in queue with correct tags and cost metadata.

### Phase 4: One Builder Per Chief

Implement one low-risk builder per chief:

| Chief | First Builder | Why First |
|---|---|---|
| Hercules | Iolaus | Task decomposition is the root of clean dispatch. |
| Nestor | Ariadne | Product flow mapping is useful without repo writes. |
| Alexander | Calliope | Content briefs are bounded and easy to verify. |

Exit gate: each first builder claims, produces a structured receipt, and receives verifier pass/fail.

### Phase 5: Full Four-Builder Teams

Implement remaining builders and wire cost gates. Keep all tasks doc/spec/proof-only until receipts and verification are stable.

Exit gate: each chief can dispatch to all four builders and receive verified receipts.

### Phase 6: Four-Deep Rotation

Add A/B/C/D instances, active claim locks, lcache handoff, safe-boundary restarts, and staggered shift schedules.

Exit gate: each chief family survives two shift changes without losing queue state or duplicating work.

### Phase 7: Titan-Parity Trial

Run the acceptance tests below. No production deploys, credential changes, external sends, or public-facing publishes.

Exit gate: all three chiefs pass the dispatch, receipt, verification, memory, and timing gates.

## 9. Acceptance Tests

### 9.1 Hercules Titan-Parity Test

Dispatchable task:

`Hercules: turn the v4.0.1 Argus/Hygeia mutual-check patch into a build-order packet for Titan, with phases, acceptance criteria, rollback notes, and verifier mapping.`

Expected flow:

1. Hercules dispatches Iolaus for task decomposition.
2. Iolaus returns a structured receipt with a build-order doc.
3. Nike assembles proof packet.
4. Themis confirms no deploy/credential/destructive work is implied.
5. Aletheia verifies the artifact exists and claims are supported.

Pass criteria:

| Metric | Target |
|---|---|
| Chief dispatch latency | <= 5 minutes |
| End-to-end completion | <= 30 minutes |
| Required outputs | Build-order doc, receipt JSON, verification log decision |
| False completion tolerance | Zero unsupported artifact claims |
| Cost | <= $0.75 for the test |

### 9.2 Nestor Titan-Parity Test

Dispatchable task:

`Nestor: produce a mobile-first Revere Chamber demo UX audit and one client-safe PRD section for the next demo iteration.`

Expected flow:

1. Nestor dispatches Ariadne for journey map.
2. Calypso reviews mobile polish constraints.
3. Pallas writes acceptance tests.
4. Aletheia verifies doc artifacts and checks public-safe language.

Pass criteria:

| Metric | Target |
|---|---|
| Chief dispatch latency | <= 5 minutes |
| End-to-end completion | <= 35 minutes |
| Required outputs | UX audit doc, PRD section, mobile acceptance checklist |
| Client-safety | No internal model/tool names |
| Cost | <= $0.75 for the test |

### 9.3 Alexander Titan-Parity Test

Dispatchable task:

`Alexander: produce a Chamber AI Advantage SEO/content + voice/chat brief for one demo-safe topic, including source-safe claims and CRM note language.`

Expected flow:

1. Alexander dispatches Calliope for narrative structure.
2. Pythia checks search intent and timeline language.
3. Orpheus drafts voice/chat phrasing.
4. Clio validates claims and public-safe evidence.
5. Aletheia verifies artifacts and unsupported claims.

Pass criteria:

| Metric | Target |
|---|---|
| Chief dispatch latency | <= 5 minutes |
| End-to-end completion | <= 40 minutes |
| Required outputs | Content brief, SEO note, voice/chat script, evidence checklist |
| Timeline discipline | Uses 30-day traction and 60-day authority framing, not 90-180 days |
| Cost | <= $1.00 for the test |

### 9.4 System-Level Pass Criteria

All three chiefs are Titan-parity only when:

1. Each chief cold-starts from bootstrap memory without Solon re-explaining.
2. Each chief dispatches to a dedicated non-Titan builder.
3. Each builder claims atomically and emits a valid receipt.
4. Each completion is independently verified.
5. Each chief logs final decision with proof.
6. Cost gates enforce family and fleet caps.
7. Shift handoff preserves state.
8. No task is marked complete when the artifact or evidence is missing.

## 10. Blockers And Required Greenlights

| Blocker | Smallest Required Action |
|---|---|
| `/opt/amg-docs` is not writable in this local session | Solon/Titan runs privileged create/copy: `sudo mkdir -p /opt/amg-docs/architecture && sudo cp <staged-file> /opt/amg-docs/architecture/CHIEF_BUILD_TEAMS_v1.md` |
| `get_bootstrap_context` and `search_memory` are unavailable in this tool surface | Restore MCP routes or define REST fallback endpoints before chief bootstrap parity is claimed. |
| Chief app Finder/Gatekeeper trust remains unstable | Resolve CT-0427-41 activation before relying on Dock chiefs as operational UI. API daemon path can still be designed separately. |
| Builder executor names do not exist yet | Add registry entries first with planned status to prevent phantom tasks. |

## 11. Non-Goals

This design does not implement builders, alter launchd/systemd, change credentials, deploy services, mutate live databases, send client-facing output, or start paid model runs. It is the architecture contract Solon can approve before the build begins.

