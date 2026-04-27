# Chief Build Teams v1.1

**Target canonical path:** `/opt/amg-docs/architecture/CHIEF_BUILD_TEAMS_v1_1.md`
**Staged path:** `/Users/solonzafiropoulos1/titan-harness/docs/architecture/CHIEF_BUILD_TEAMS_v1_1.md`
**Date:** 2026-04-27
**Owner:** Achilles, CT-0427-49
**Status:** Design only. No executor build, deploy, credential change, or live queue mutation.

## 0. Scope

This is the v1.1 patch to `CHIEF_BUILD_TEAMS_v1.md`. It keeps the same three-chief design and closes four gaps called out by EOM:

- Account isolation.
- Solon-to-chief dispatch UX.
- MCP route restoration scope.
- Naming registry audit.

It also binds three directives:

- Judge sovereignty: no Perplexity, Grok, or Gemini in the formal judge stack. The future judge pair is AMG Reasoning Judge plus Haiku as the only external counterweight.
- Synchronized A/B/C/D cohort: chief-team builders rotate in lockstep with the v4.0.2.2 Iris and v4.0.3.1 Athena pattern.
- Post-factory pair-programmer: after the factory build is stable, Solon gets a low-friction pair-programmer surface over the existing chiefs/builders. This is a UX layer, not a new agent class.

Paper freeze note: v1.1 introduces no new current-scope agent classes beyond the v1 roster. Anything not already named here or in the v4.0.x finals is v6.0+ backlog.

## 1. Per-Chief Roster

Titan's Daedalus, Artisan, and Mercury remain shared resources dispatched by Titan. They are not duplicated under the chiefs.

### Hercules

Hercules owns architecture, doctrine, queue honesty, risk gates, and cross-team orchestration.

| Builder | Role | Why It Reports To Hercules | Default Lane | Daily Warning |
|---|---|---|---|---|
| Iolaus | Build-order compiler | Converts strategy into bounded task packets with acceptance criteria. | local/DeepSeek first, Kimi only if approved | $1.25 |
| Cadmus | Doctrine and registry writer | Maintains architecture docs, capability manifests, and naming registry. | local first | $0.75 |
| Themis | Risk and approval gate | Classifies owner-risk, public-facing risk, credential risk, and cost exceptions. | local R1 first, V4 Reasoner exception | $1.25 |
| Nike | Proof closer | Assembles receipts, proof packets, and verifier-ready summaries. | local/Kimi low-cost lane | $0.75 |

Family daily warning: $5.00. Fleet hard gate still lives at the metered-cost layer, not in this design doc.

### Nestor

Nestor owns product, UX, demos, client-safe presentation, Revere/Chamber artifacts, and Atlas onboarding experience.

| Builder | Role | Why It Reports To Nestor | Default Lane | Daily Warning |
|---|---|---|---|---|
| Ariadne | UX flow mapper | Maps user journeys, onboarding paths, IA, and demo scripts. | Kimi for taste, local fallback | $1.25 |
| Calypso | Interface polish reviewer | Reviews mobile fit, contrast, spacing, screenshots, and client polish. | Kimi or local vision substitute | $1.00 |
| Demeter | CRM and lifecycle mapper | Maps leads, member lifecycle, retention hooks, and CRM-facing UX. | local first | $0.75 |
| Pallas | Product acceptance tester | Defines product acceptance checks and client-safe constraints. | local R1 first | $1.00 |

Family daily warning: $5.00.

### Alexander

Alexander owns content, SEO, voice/chat, brand language, offer positioning, newsletters, and conversation tuning.

| Builder | Role | Why It Reports To Alexander | Default Lane | Daily Warning |
|---|---|---|---|---|
| Calliope | Long-form content architect | Drafts pillar briefs, newsletters, offers, and campaign narratives. | Kimi for voice | $1.25 |
| Pythia | SEO and market-intent researcher | Produces keyword maps, SERP assumptions, and timing language. | Brave/RAG/local first | $1.00 |
| Orpheus | Voice and chat dialogue tuner | Tunes voice scripts, interruption handling, sentiment, and CRM notes. | Kimi/local | $1.25 |
| Clio | Evidence and case-study keeper | Keeps claims, citations, proof snippets, and case-study facts clean. | local R1 first | $0.75 |

Family daily warning: $5.00.

## 2. Account Isolation Plan

### Chiefs

The three chiefs keep persona-isolated Kimi GUI runtimes per CT-0427-41:

| Chief | Runtime | Isolation Boundary |
|---|---|---|
| Hercules | Kimi GUI profile/app path | `io.achilles.hercules.dock`, Hercules profile, Hercules persona credentials. |
| Nestor | Kimi GUI app/profile | `io.achilles.nestor.dock`, Nestor profile, Nestor persona credentials. |
| Alexander | Kimi GUI app/profile | `com.amg.alexander.app`, Alexander profile, Alexander persona credentials. |

Rules:

- No chief shares cookies, phone/email login credentials, LaunchServices identity, or browser profile with another chief.
- Rebuilding app bundles does not merge accounts. If a bundle breaks, repair the wrapper and keep the persona profile isolated.
- Chiefs are GUI-bound by design and exempt from the deployment portability doctrine that applies to headless agents.

### Builders

Chief-team builders are not separate Kimi GUI accounts by default. They are headless execution identities with:

- Unique `agent_id`, `owner:<chief>`, and `chief:<chief>` tags.
- Separate lcache and shift state.
- Provider access through approved service credentials, local models, or family-scoped API lanes.
- No access to the chief's GUI cookies or phone/email identity.

If a future builder truly needs a Kimi GUI session, it requires explicit Solon approval, a new isolated profile, a unique bundle id if app-based, and a cost/credential entry before any task dispatch. Until then, builders use API/local lanes only.

## 3. Solon-To-Chief Dispatch UX

Primary path: one structured Slack/admin dispatch line that Iris/EOM converts into MCP queue work.

```text
DISPATCH <chief>: <objective>
AC: <acceptance criteria>
RISK: <safe | owner-risk | deploy-risk | public-risk>
DUE: <optional timebox>
```

Example:

```text
DISPATCH Alexander: draft a demo-safe voice/chat brief for Revere Chamber follow-up.
AC: brief path, 3 claims with evidence, no internal tool names.
RISK: safe
DUE: 45m
```

Backup path: direct Dock chief chat when Slack/MCP is degraded. The chief must then log the manual intake decision and queue the work when MCP is available. Solon never chooses the builder unless he explicitly wants to; the chief maps the objective to Calliope/Pythia/etc.

UX guardrails:

- Solon can say "Dispatch Hercules/Nestor/Alexander" without remembering builder names.
- Every dispatch gets an MCP `task_id` or a degraded-mode decision log.
- No silent handoff through Solon as middleware. Chiefs and EOM use MCP decisions/queue directly.

## 4. MCP Integration And Route Restoration Scope

Chief parity means chiefs use the same queue tools Titan uses: `queue_operator_task`, `claim_task`, `update_task`, `log_decision`, and `flag_blocker`.

### Required Task Lifecycle

| Step | Required Action |
|---|---|
| Intake | Chief receives structured Solon/EOM/Iris dispatch. |
| Queue | Chief writes a scoped queue task with `chief:<name>`, `owner:<chief>`, and `agent:<builder>`. |
| Claim | Builder claims atomically. Missing owner/agent tags block the task. |
| Execute | Builder emits a JSON receipt with artifact paths and proof. |
| Verify | Aletheia or the relevant shared verifier checks claims. |
| Close | Chief logs `chief_verified:<chief>` or flags a blocker. |

### Route Probe And Restoration Matrix

Local probes on 2026-04-27 show this route state:

| Route/Tool | Observed State | v1.1 Scope |
|---|---|---|
| `GET /health` | 200 OK | Keep as liveness check. |
| `GET /api/task-queue` | 200 OK, but CT-0427-30 says pagination/order are broken | Restore newest-first ordering, offset/cursor, bounded limit >= 200. |
| `POST /api/queue-task` | Present in client code | Add smoke test; required for chiefs to dispatch. |
| `POST /api/claim-task` | Present in client code | Add owner/agent tag enforcement tests. |
| `POST /api/update-task` | Present, but status transitions are strict | Document allowed transitions; builders must lock/claim before active/completed. |
| `POST /api/decisions` and `GET /api/recent-decisions-json` | Working via MCP bridge | Keep as source of record. |
| `POST /api/bootstrap-context` | 404 per CT-0427-31 | Restore before chief memory parity can be claimed. |
| `POST /api/search-memory` | 404 per CT-0427-43 | Restore for Claude/n8n/uniform clients; direct Supabase workaround is not parity. |
| `GET /api/sprint-state` | 404 in local probe | Either restore or remove from bootstrap contract. |
| `GET /api/vault/search?q=...&tenant_slug=amg-internal` | 200 OK, empty result for test query | Keep as low-level fallback, not replacement for semantic `search_memory`. |

Restoration scope is route parity and tests only. Do not add new product behavior, ACL namespaces, schema migrations, or cloud changes under this patch. Shared namespace ACL work remains a separately approved follow-up.

## 5. Persistent Memory Plan

Each chief gets a bootstrap equivalent to Titan's `boot_prompt.txt`, rendered from the same MCP sources and degraded honestly if routes are down.

Startup sequence:

1. `get_bootstrap_context(project_id="<chief>", scope="both", max_decisions=15)`.
2. `get_recent_decisions(count=15)` filtered by chief when available.
3. `search_memory(query="<chief> current queue blockers handoffs")`.
4. `search_memory(query="v5.0 model sovereignty DeepSeek Aristotle 7 AMG agents")`.
5. `search_memory(query="CT-0427-41 Kimi account isolation Vendor runtime")`.

Degraded rule: if bootstrap/search routes are unavailable, the chief logs `bootstrap_degraded:<chief>` and uses the most recent local boot file plus recent decisions. It must not claim full context.

Files of record after build approval:

| File | Purpose |
|---|---|
| `/opt/amg-docs/chiefs/hercules/boot_prompt.txt` | Hercules standing context. |
| `/opt/amg-docs/chiefs/nestor/boot_prompt.txt` | Nestor product/UX context. |
| `/opt/amg-docs/chiefs/alexander/boot_prompt.txt` | Alexander content/voice context. |
| `/opt/amg-governance/lcache/<agent>.md` | Rolling continuity cache, max 3 KB. |
| `/opt/amg-governance/shift_state/<agent>.json` | Active shift, lock holder, last heartbeat, handoff. |

## 6. Synchronized Ford Factory Rotation

v1 staggered times are replaced by synchronized A/B/C/D cohorts.

| Cohort | UTC Window | Active Instances |
|---|---|---|
| A | 00:00-05:59 | `*-A` for chiefs, builders, Iris, Athena, verifiers. |
| B | 06:00-11:59 | `*-B`. |
| C | 12:00-17:59 | `*-C`. |
| D | 18:00-23:59 | `*-D`. |

Safe handoff rules:

- No mid-tool-call kill.
- No handoff without lcache write.
- Task locks survive shift change and transfer only after receipt, blocker, timeout, or owner override.
- Mid-task handoff requires a receipt stub with current state and exact next action.

## 7. Naming Registry Audit

### Names Already In Current Scope

| Name | Category | Status | Collision/Notes |
|---|---|---|---|
| Hercules | Chief | active/planned parity | Keep distinct from Hercules helper `Iolaus`. |
| Nestor | Chief | active/planned parity | Product/UX chief. |
| Alexander | Chief | active/planned parity | Do not shorten to `Alex`; `Alex` is an AMG client-facing agent. |
| Iolaus, Cadmus, Themis, Nike | Hercules builders | planned only | Not Titan lieutenants; no executor until registry-first phase. |
| Ariadne, Calypso, Demeter, Pallas | Nestor builders | planned only | No duplicate in current registry found. |
| Calliope, Pythia, Orpheus, Clio | Alexander builders | planned only | Orpheus/Calliope may later support music, but no v4.0.x scope expansion. |
| Daedalus, Artisan, Mercury | Titan/shared lieutenants | existing/shared | Must not be placed under chiefs. |
| Aletheia, Argus, Hygeia, Cerberus, Warden | Shared verifiers/guards | existing/shared | Verify all chiefs; not chief builders. |
| Iris | v4.0.2.2 mailman | paper-freeze final | Routes to chief inbox only. |
| Athena | v4.0.3.1 knowledge curator | paper-freeze final | Writes KB, proposes SI deltas; does not dispatch tasks. |
| Aristotle | old Perplexity-linked validator vs future in-house research | conflicted/retired pending v5 | Old Perplexity Aristotle is retired by judge sovereignty. Future sovereign research service must not use Perplexity/Grok/Gemini. |
| Alex, Maya, Jordan, Sam, Riley, Nadia, Lumina | AMG client-facing agents | existing migration targets | `Alex` must not collide with `Alexander`. |
| Apollo | music v6 proposal only | backlog | Excluded from current paper-freeze scope. |

Registry action for Phase 1: add planned entries for the 12 chief builders with `status: planned`, `executor_enabled: false`, and `reject_with_explanation` so phantom tasks cannot stall.

## 8. CT-0427-43 Aletheia Scope Fix Status

Status: open, not proven fixed.

Evidence found:

- v4.0.1 notes say Aletheia may falsely fail a completion because the relevant commit lived in `amg-mcp-server`, not `titan-harness` or `achilles-harness`.
- Current queue includes CT-0427-43/route work showing `/api/search-memory` is still missing on the live MCP HTTP surface.
- No decision log found proving Aletheia's repo scan list now includes all repos it is asked to judge.

Smallest acceptable fix:

1. Create a canonical repo registry for Aletheia claim verification.
2. Include at least `titan-harness`, `achilles-harness`, `amg-mcp-server`, `amg-operator-memory`, and any `/opt/amg-*` repo used by task receipts.
3. Teach Aletheia to resolve artifact claims against the registry before failing a receipt.
4. Run TEST 0B from the v4.0.1 note: a known commit outside Titan/Achilles must verify without false failure.
5. Do not enable strict Layer 2 completion gates on Titan until TEST 0B passes.

## 9. Build Sequence

### Phase 0 - File v1.1

Stage this document, log the decision, and report blockers. No build.

### Phase 1 - Registry Only

Add planned registry rows for the 12 builders. Unknown/unbuilt builders must reject with a clear explanation. No executor claims yet.

### Phase 2 - MCP Route Repair

Restore route parity for task queue, claim/update, bootstrap-context, search-memory, sprint-state or remove stale calls. Add route tests.

### Phase 3 - Chief Bootstrap

Render boot prompts and lcache for Hercules, Nestor, and Alexander. Prove degraded-mode honesty when memory search is unavailable.

### Phase 4 - Dispatcher Skeleton

Chiefs can queue and watch tasks but no builder executes work. Synthetic queue-only dispatch must include tags, cost metadata, and acceptance criteria.

### Phase 5 - One Builder Per Chief

Implement Iolaus, Ariadne, and Calliope only, all doc/spec-only first. Each must claim, receipt, and submit to verifier.

### Phase 6 - Full Roster

Implement remaining builders after Phase 5 proves receipts and verification. Keep all work bounded and non-destructive until Solon expands scope.

### Phase 7 - Synchronized Rotation

Turn on A/B/C/D lock handoff for chiefs/builders and verify two full handoffs without duplicate completion.

### Phase 8 - Post-Factory Pair-Programmer UX

After factory stability, add Solon's pair-programmer surface as a dispatch UX over existing chiefs/builders. No new class; no paper-freeze change.

## 10. Acceptance Tests

### Hercules Parity

Dispatch: "Hercules, turn the v4.0.1 Argus/Hygeia mutual-check patch into a build-order packet with phases, acceptance criteria, rollback notes, and verifier mapping."

Expected: Hercules dispatches Iolaus, Themis checks safety, Nike assembles proof, Aletheia verifies artifact claims.

Pass: dispatch latency <= 5 minutes, end-to-end <= 30 minutes, zero unsupported claims, metered cost <= $0.75.

### Nestor Parity

Dispatch: "Nestor, produce a mobile-first Revere Chamber demo UX audit and one client-safe PRD section."

Expected: Nestor dispatches Ariadne, Calypso reviews polish, Pallas writes acceptance tests, Aletheia verifies artifacts.

Pass: dispatch latency <= 5 minutes, end-to-end <= 35 minutes, no internal model/tool names, metered cost <= $0.75.

### Alexander Parity

Dispatch: "Alexander, produce a demo-safe SEO/content plus voice/chat brief for one Chamber AI Advantage topic."

Expected: Alexander dispatches Calliope, Pythia checks search intent, Orpheus tunes voice phrasing, Clio validates claims, Aletheia verifies.

Pass: dispatch latency <= 5 minutes, end-to-end <= 40 minutes, evidence checklist present, no 90-180 day overclaim, metered cost <= $1.00.

## 11. Blockers

| Blocker | Smallest Required Action |
|---|---|
| `/opt/amg-docs` is not writable from this session | Titan/Solon privileged copy or chown for `/opt/amg-docs/architecture`. |
| MCP bootstrap/search/sprint routes are degraded | Repair CT-0427-31/43 route set before memory parity is claimed. |
| Aletheia scope fix not proven | Complete TEST 0B against a non-Titan repo before strict false-completion gating. |
| Chief app Finder trust has been unstable | Keep GUI repair separate from builder design; API/headless builders do not depend on Finder. |

## 12. Self-Score

| Dimension | Score | Note |
|---|---:|---|
| Architecture clarity | 9.5 | Clear chief/builder/verifier separation. |
| Receipt/contract specificity | 9.4 | Tags, lifecycle, receipt, and acceptance gates are explicit. |
| Cost discipline | 9.2 | Per-family warnings plus fleet hard-gate handoff to v5.0.1. |
| Phasing | 9.6 | Registry-first prevents phantom-agent stalls. |
| Honesty/blockers | 9.7 | Route and `/opt` blockers not hidden. |
| Paper-freeze compliance | 9.6 | No new current-scope classes; post-factory UX is not an agent. |

Overall: 9.5/10.
