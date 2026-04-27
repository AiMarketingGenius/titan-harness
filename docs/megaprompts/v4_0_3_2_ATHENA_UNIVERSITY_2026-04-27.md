# v4.0.2.3 → v4.0.3.2 PATCH ADDENDUM — ATHENA UNIVERSITY
**Source:** v4.0.2.2 (Iris mailman)
**Supersedes:** v4.0.3.1 (this is the shipping version)
**Date:** 2026-04-27
**Producer:** EOM (post-audit corrections per Solon excellence mandate)
**Scope:** Adds Athena (knowledge curator / intelligence officer / SI-delta proposer) as 28th agent class. Locks factory-wide *Deployment Portability Doctrine* (§3I.7) inherited by all non-chief agents. Corrects KB namespace references, observability metric ownership, cost attribution, and math reconciliation.

---

## CHANGELOG vs v4.0.3

| Item | Section | Change | Severity |
|---|---|---|---|
| **A** | §3I.7 NEW | *Deployment Portability Doctrine* added as factory-wide rule binding all non-chief agents (Athena, Iris, Aletheia, Argus, Hygeia, Cerberus, Warden, all chief team builders, mailmen, Mercury, Daedalus, Artisan). Chiefs exempt by hardware design. | **architectural — primary patch** |
| **B** | §3I.2 KB writes per chief | Namespace list corrected to verified-only. `kb:nestor:product` removed (was hallucinated — does not exist in MCP namespace registry). Hercules / Nestor / Alexander namespaces match `search_kb` ACL: kb:hercules:{eom, doctrine}; kb:nestor:lumina-cro; kb:alexander:{seo-content, hormozi, welby, koray, reputation, paid-ads, outbound}. | factual correction |
| **C** | §3I.2 cross-pollination | `kb:shared:current_events` flagged as **proposed new namespace requiring MCP ACL extension** OR fallback to fanout-write across all chief namespaces. Decision deferred to MCP architecture review; Athena ships with fanout fallback by default. | architectural honesty |
| **D** | §3I.2 + §3I.6 | `kb_last_write_timestamp` metric — Athena logs this herself via `athena:kb_write:<namespace>` decision tag rather than assuming external KB system tracks it. Scale-to-2 trigger then queries her own decision log. | observability ownership |
| **E** | §3I + cost block | Cost language corrected — Kimi is flat-rate, marginal cost is $0; previous "$8–16/mo bridge" attribution was misleading. Bridge phase external research budget (≤$10/mo) stated explicitly and separately from flat-rate baseline. | cosmetic |
| **F** | Math update block | Footnote — v4.0.x inventory line tracks v4.0.x agents only; chief team builders separate manifest. Combined factory totals stated. | reconciliation |
| **G** | §3I.3 + §3I.8 | Kimi flat-rate compliance qualifier added — GUI/subscription synthesis remains flat-rate; any Kimi API path is metered and must enter the v5.0.2 fleet cost gate | clarity |

---

## RATIONALE — DO WE NEED ATHENA?

**Honest framing up front: the mental model "inject knowledge into agents' brains daily" is technically inaccurate.** Model weights are frozen — DeepSeek V4, Kimi K2.6, Claude all have static parameters that we cannot edit without retraining (not in scope for ≥6 months).

**What Athena actually does — the realistic mechanism:**

| User-facing model | Real implementation |
|---|---|
| "Constantly educate the workers" | Update KB namespaces (`kb:<chief>:<topic>`) that workers read at shift bootstrap |
| "Athena attends seminars and brings knowledge back" | Daily web/intel research → curated KB writes → next shift reads fresh KB |
| "Athena keeps SI documents current" | Drafts SI delta proposals, **Solon-gated** before merge to Supabase + VPS + Claude.ai project |
| "Educate every factory worker" | Dispatcher (Iris / chief loop) attaches relevant KB chunks (RAG) to each task at delivery time |
| "Make the model smarter" | Out of scope. Fine-tuning on AMG corpus is v6.0+ backlog. |

**The user-facing effect** (workers' answers get fresher every day) is achieved through **fresher textbooks, not retrained neurons.** This is exactly how every serious production AI system works — RAG + KB curation, not model editing.

**Where Athena adds real value:**
1. **Continuous KB freshness** — every chief's domain KB gets new intelligence daily.
2. **Cross-pollination** — knowledge that affects all chiefs goes to a shared layer.
3. **SI evolution with safety gate** — Athena drafts SI updates; Solon approves before deploy. No autonomous identity drift.
4. **On-demand intelligence** — factory workers can query Athena instead of having stale internal answers.
5. **Fabrication prevention** — Aletheia mutual check verifies Athena citations are real and accessible before KB writes commit.

**Build sequencing recommendation:** Build Athena in Wave 3 (Day 31–32 within Wave 3 envelope of Day 23–32), after Iris is stable. Athena depends on AMG Sonar-Replica (CT-51 scoping) for primary research backbone — bridge phase uses Kimi flat-rate synthesis + small external research budget until Sonar-Replica live.

---

## CHANGE 1 — §3I NEW SUBSECTION — Athena Specification

**Insert new subsection §3I after §3H (Iris):**

### 3I. ATHENA — UNIVERSITY / INTELLIGENCE OFFICER / KNOWLEDGE CURATOR (NEW v4.0.3.1)

**Greek mythology:** Athena, goddess of wisdom, strategic warfare, and craft. Patron of learning. Born fully formed from Zeus's head — fitting for an agent whose entire purpose is delivering complete, current knowledge to those who need it.

#### 3I.1 Why Athena exists (knowledge layer)

The factory needs continuously fresh information to operate against a moving market. Without Athena:
- Chief KBs go stale within weeks (search rankings shift, competitor pricing moves, tools update, algorithms change).
- Factory workers operate on bootstrap context that's only as current as the last manual KB update.
- SI documents drift from current best practice; nobody owns the proactive "update SI when world changes" job.

With Athena:
- Daily intelligence sweeps land in chief-specific KB namespaces before next shift bootstraps.
- Cross-pollination layer supplies intelligence relevant to all chiefs.
- SI delta proposals filed on a regular cadence, Solon-gated for review, prevent stagnation without enabling drift.
- Workers can query Athena directly for on-demand intelligence.

#### 3I.2 Six responsibilities

1. **Daily intelligence brief** — once per shift, log via `log_decision(tag="athena:daily_brief", project_source="ATHENA")` summarizing what's new in factory-relevant domains over the last 24h.
2. **KB writes per chief** — write fresh research / intelligence to chief-specific namespaces. **Verified-only namespace list** (matches `search_kb` ACL registry):
   - **Hercules** (architecture, governance, doctrine): `kb:hercules:eom`, `kb:hercules:doctrine`
   - **Nestor** (UX, conversion, mobile, demo intel): `kb:nestor:lumina-cro`
   - **Alexander** (content, SEO, voice, paid, outbound, reputation): `kb:alexander:seo-content`, `kb:alexander:hormozi`, `kb:alexander:welby`, `kb:alexander:koray`, `kb:alexander:reputation`, `kb:alexander:paid-ads`, `kb:alexander:outbound`
   
   All KB writes attach citations + source URLs + retrieval timestamp. After every write, Athena ALSO logs `log_decision(tag="athena:kb_write:<namespace>")` so write recency is observable from MCP regardless of whether the underlying KB system exposes write-timestamp queries.
   
   **New namespace requests:** if Athena's research justifies a new chief namespace (e.g., `kb:nestor:onboarding-flows`), she files a proposal via `log_decision(tag="athena:namespace_proposal:<chief>:<topic>")` for Solon review. New namespaces require Solon approval — Athena does not auto-create.
3. **Cross-pollination brief** — for intelligence affecting all chiefs (model releases, major platform changes, regulatory shifts, AMG-relevant news). 
   
   **Implementation:** Athena attempts to write to a shared namespace `kb:shared:current_events`. **This namespace does not currently exist in the MCP ACL registry.** Two valid implementation paths:
   - **Path A (preferred, requires MCP work):** extend MCP ACL to support `kb:shared:*` namespace with read-ALL ACL + Athena-write ACL. Architectural review required.
   - **Path B (fallback, ships first):** Athena fanout-writes the cross-pollination brief identically to all 3 chief root namespaces (`kb:hercules:eom`, `kb:nestor:lumina-cro`, `kb:alexander:seo-content`) tagged `cross_pollination:YYYY-MM-DD`. Chiefs filter by tag at bootstrap.
   
   Phase 11.8 ships with Path B fallback. Path A is filed as architectural follow-up — if approved, Athena swaps from fanout to shared-namespace write transparently.
4. **SI delta proposals** — when accumulated intelligence justifies updating an SI document, Athena drafts the proposed change and files via `log_decision(tag="athena:si_delta_proposal:<agent>")`. **Critical hard rule: SI delta proposals NEVER auto-merge.** Solon must explicitly log a decision tagged `si_merge_approved:<agent>` before any SI update propagates to the three-location sync (VPS shared folder + Claude.ai project SI + Supabase `agent_config.system_prompt`).
5. **On-demand queries** — factory workers can dispatch tasks tagged `agent:athena` via the queue; Athena responds within shift on best-effort basis (priority urgent gets push notification through Iris).
6. **Daily delivery report** — `log_decision(tag="athena:daily_delivery_report")` with KB writes per chief, citation count, missed cycles, on-demand queries answered, average response time, and **per-namespace freshness** computed from her own `athena:kb_write:*` log entries.

#### 3I.3 Stack and bridge

**Primary backbone (post-CT-51):** AMG Sonar-Replica (DeepSeek V4 + Brave Search + RAG + structured citations). Zero marginal API cost.

**Bridge phase (until Sonar-Replica live):** Kimi K2.6 flat-rate for synthesis + small external research budget (≤$10/mo allocated for live web data). Kimi marginal cost is $0 only for approved GUI/subscription usage. If any Kimi API path is used instead, those calls are metered and must enter the v5.0.2 fleet cost gate. External research budget is the only other variable cost during bridge.

#### 3I.4 Athena runs on synchronized A/B/C/D cohort

4 instances (Athena-A, Athena-B, Athena-C, Athena-D) on the synchronized factory cohort schedule: A=00:00–06:00 UTC, B=06:00–12:00, C=12:00–18:00, D=18:00–24:00. **1 instance per shift initially.** Off-shift instances are COLD (not running, not consuming compute). Lcache continuity at boundary.

**Scale-to-2 trigger:** instantiate a second concurrent Athena per shift IF either:
- Athena's own `athena:kb_write:<namespace>` decision log shows any namespace with no write in last 24h, OR
- Athena daily delivery report shows >2 missed daily-brief cycles per week.

Don't over-provision. Scale only when load proves it. Both metrics are observable from MCP via Athena's own logging — no external KB-system metric required.

#### 3I.5 Mutual check: Athena ↔ Aletheia

Aletheia verifies every Athena KB write before commit:
- Cited sources actually exist and are reachable (HTTP 200 fetch on URL).
- Quoted facts match source content (no fabrication — Aletheia samples claim ↔ source pairs).
- ≥2 independent citations required for any non-obvious claim.

If Aletheia rejects, Athena revises or `flag_blocker` for Solon review.

#### 3I.6 Boundary clarifications

| Agent | Owns | Cadence |
|---|---|---|
| `Athena` | Knowledge curation: research, KB writes, SI delta proposals, namespace proposals | Daily briefs + on-demand |
| `Iris` | Task delivery to chief inboxes | Every 3 min poll |
| `shift_orchestrator` | Which instance is active per agent class | Continuous; election every 30s |
| Specialist chiefs | Strategic decisions in their domain using Athena's intelligence | Continuous |

Athena supplies intelligence. Chiefs decide what to do with it. Athena does NOT make strategic / tactical decisions for the chiefs.

#### 3I.7 *Deployment Portability Doctrine* (FACTORY-WIDE, all non-chief agents inherit)

**Principle:** An agent is defined by its **identity, capabilities, and contract** — never by its host. Process supervision and host placement are deployment-time choices, not architectural facts.

**Six binding requirements:**

1. **Code portability.** Agent process is a portable codebase (Python 3.11+ unless explicitly justified otherwise) with **zero hardcoded host paths.** All paths are config-driven via environment variables (`AMG_AGENT_INBOX_ROOT`, `AMG_LCACHE_ROOT`, `AMG_MCP_ENDPOINT`, etc.). Same source runs identically on VPS Linux and Mac macOS.

2. **State externalization.** All agent state lives in MCP (Supabase) — **no local JSON files, no local SQLite, no local persistent state.** Process restart reads state fresh from MCP. Lcache files at `/opt/amg-governance/lcache/<agent>.md` (or Mac equivalent `/Users/.../lcache/<agent>.md`) are write-only continuity buffers — not authoritative state. Authoritative state is MCP.

3. **Process supervisor abstraction.** Every non-chief agent ships **both supervision manifests** in Phase rollout:
   - `systemd` unit (`<agent>.service`) for VPS-default deployment
   - `launchd` plist (`com.amg.<agent>.plist`) for Mac-side deployment
   
   Both supervisors call the **same Python entry point** with config differing only in environment variable values. Default deployment is VPS systemd. Mac launchd ships in repository for portability — used only when explicitly chosen for a specific agent instance.

4. **Target abstraction.** Agents reference targets by **`agent_id`** (and `chief_id`, `kb_namespace_id`, `task_id`) — never by host path or hostname. Athena writes to `kb:hercules:doctrine` regardless of whether Hercules runs as a Mac Kimi app or a VPS daemon. Iris routes to `chief_id="hercules"` regardless of host. Discovery happens via MCP-resolved addresses, not hardcoded host references.

5. **Migration neutrality.** When AMG decides to move an agent from Mac to VPS (or vice versa), the change is:
   - Deactivate old supervisor unit on source host
   - Deploy new supervisor unit on destination host (manifest already exists in repo)
   - Cohort lock token transfers via MCP
   
   **No code change. No state migration. No downtime beyond cohort handoff window.**

6. **Future-proof envelope.** When AMG migrates 100% of factory to VPS (anticipated future state), the migration is supervisor-unit redeploys for any Mac-resident agents — code is already VPS-ready. When AMG (hypothetically) ever needs to add a third host class (e.g., Raspberry Pi edge nodes), a third supervisor manifest is added; code remains unchanged.

**Scope of doctrine:**
- **APPLIES TO** all non-chief agents: Iris, Athena, Aletheia, Argus, Hygeia, Cerberus, Warden, all 12 chief team builders (Iolaus, Cadmus, Themis, Nike, Ariadne, Calypso, Demeter, Pallas, Calliope, Pythia, Orpheus, Clio), all mailmen, Mercury, Daedalus, Artisan, shift_orchestrator.
- **EXEMPT BY DESIGN** Chiefs (Hercules, Nestor, Alexander). Chiefs run on **Kimi GUI runtime** — either Mac app (current: Nestor, Alexander) or web browser (current: Hercules) — both are interactive GUI environments unsuited to headless daemon supervision. Per CT-0427-41 the Mac-app variants have persona-isolated bundle IDs + per-persona phone/email credentials; the web variant uses isolated browser profile + per-persona session. Either way, chiefs are deliberately runtime-bound to Kimi GUI and are not subject to the portability doctrine. If a chief is ever migrated from Mac app to web (or vice versa), the migration is per-chief manual setup (login + persona cred swap), not the supervisor-redeploy pattern of headless agents.

**Phase 11.8 verification of doctrine:** Athena's launchd plist + systemd unit both deployed in test rollout; Athena instance cycled across hosts (VPS systemd → Mac launchd → VPS systemd) without state loss or missed daily brief.

#### 3I.8 Implementation footprint

- Single Python service: `athena.py` running per §3I.7 (default: VPS systemd; Mac launchd manifest shipped for portability).
- Reads from web (via Sonar-Replica or Kimi+external bridge), writes to MCP KB namespaces + decision log.
- Marginal API cost: $0 for approved Kimi GUI/subscription usage. If the bridge ever swaps to Kimi API, those calls become metered and must enter the v5.0.2 fleet cost gate. Bridge external research budget: ≤$10/mo until Sonar-Replica live.
- All-in monthly delta during bridge: ≤$10/mo. Steady-state post-Sonar-Replica: $0.

---

## CHANGE 2 — §3E AGENT INVENTORY — Add Athena row

**Update v4.0.2.2 §3E total count from "27 classes × 4 = 108 instances" to "28 classes × 4 = 112 instances."**

> **Footnote:** v4.0.x inventory line tracks v4.0.x agents only. Chief team builders (12 classes × 4 = 48 instances) tracked separately under CHIEF_BUILD_TEAMS_v1.x manifest. **Combined factory-wide instance count when both lines operational: 28 + 12 = 40 classes × 4 = 160 instances.**

**Insert new row after Iris row:**

| Agent class | Instances | Special handling |
|---|---|---|
| **Athena** (NEW v4.0.3.1) | 4 (synchronized A/B/C/D cohort; scale-to-2-per-shift on load trigger) | Knowledge curator; KB writes per chief; SI delta proposals (Solon-gated); mutual check with Aletheia for citation honesty; deployment-portable per §3I.7; cross-pollination via fanout fallback until shared-namespace ACL approved |

---

## CHANGE 3 — §4 IMPLEMENTATION SEQUENCE — Add Phase 11.8

**After Phase 11.7 (Iris rollout, Day 29–30), insert:**

### Phase 11.8 — Athena rollout (Day 31–32, NEW v4.0.3.1)

> Within Wave 3 envelope (Day 23–32). Argus / Hygeia at Day 23–25, Iris at Day 29–30, Athena at Day 31–32.

1. Build `athena.py` Python service implementing all 6 responsibilities per §3I.
2. Ship systemd unit (`athena.service`) for VPS-default deployment + launchd plist (`com.amg.athena.plist`) for Mac-portability per §3I.7.
3. Deploy 4 Athena instances on synchronized A/B/C/D cohort (VPS via systemd by default).
4. Confirm KB write paths to verified namespaces only: kb:hercules:{eom, doctrine}, kb:nestor:lumina-cro, kb:alexander:{seo-content, hormozi, welby, koray, reputation, paid-ads, outbound}.
5. Implement cross-pollination via fanout fallback (Path B): Athena writes identical brief to kb:hercules:eom + kb:nestor:lumina-cro + kb:alexander:seo-content tagged `cross_pollination:YYYY-MM-DD`. Concurrently file architectural proposal for `kb:shared:*` ACL extension (Path A); if approved, Athena swaps to shared-namespace write.
6. Wire Athena → AMG Sonar-Replica (if CT-51 build complete) OR Kimi+external bridge stack (≤$10/mo external research budget cap).
7. Wire Athena ↔ Aletheia mutual-check pipeline (every KB write blocks on Aletheia citation verification).
8. Wire Solon-gate for SI delta proposals: Athena writes `athena:si_delta_proposal:<agent>` decision; three-location sync watches for `si_merge_approved:<agent>` decision tagged by Solon; only after explicit Solon approval does the merge propagate.
9. **Verification:**
   - Synthetic test 1 (KB write + verification): Athena researches a known-good topic, writes to `kb:hercules:doctrine`, Aletheia verifies citations resolve → KB write commits within 6h. Athena's `athena:kb_write:kb:hercules:doctrine` decision log appears.
   - Synthetic test 2 (fabrication catch): inject a known-fabricated source into Athena's input; confirm Aletheia rejects the KB write before commit.
   - Synthetic test 3 (SI delta gate): Athena files `athena:si_delta_proposal:hercules`; confirm three-location sync does NOT propagate without Solon `si_merge_approved` decision.
   - Synthetic test 4 (cross-pollination fanout): Athena writes cross-pollination brief; confirm tag `cross_pollination:YYYY-MM-DD` appears in all 3 chief root namespaces; chiefs read at next bootstrap.
   - Synthetic test 5 (cohort sync): Athena A→B→C→D handoff in lockstep with builder cohort at boundary times.
   - Synthetic test 6 (deployment portability): cycle a single Athena instance across hosts (VPS systemd → Mac launchd → VPS systemd) via supervisor swap; verify no state loss, no missed daily-brief cycle, no KB write dropped.
   - Graceful-degradation test: kill all 4 Athena instances → confirm chiefs continue operating from last-known KB snapshot (no hard dependency).
10. **Acceptance:** 7-day stability period — Athena daily delivery report shows >95% on-time daily briefs, zero unverified citation merges, zero unauthorized SI propagations, zero state loss across portability cycles.

---

## CHANGE 4 — §5 ACCEPTANCE CRITERIA — Append

- 63. ✅ **Athena daily brief logged with citation list (NEW v4.0.3.1)** — `athena:daily_brief` decision logged once per shift; citations resolve.
- 64. ✅ **Athena KB writes verified by Aletheia (NEW v4.0.3.1)** — every `kb:<chief>:*` write passes Aletheia citation check before commit; Athena's per-write decision log present.
- 65. ✅ **Athena SI delta proposals never auto-merge (NEW v4.0.3.1)** — Solon-gate validated; no SI propagation without explicit `si_merge_approved` decision.
- 66. ✅ **Athena cross-pollination delivered (NEW v4.0.3.1)** — fanout fallback writes appear in all 3 chief root namespaces tagged `cross_pollination:*`; chiefs read at shift bootstrap.
- 67. ✅ **Athena graceful degradation (NEW v4.0.3.1)** — all 4 Athena instances down → chiefs continue from last KB snapshot, no hard dependency, factory operates at reduced freshness.
- 68. ✅ **Athena namespace ACL discipline (NEW v4.0.3.1)** — Athena writes only to verified namespaces; new namespace requests filed via `athena:namespace_proposal:*` for Solon review; no auto-create.
- 69. ✅ **Athena deployment portability (NEW v4.0.3.1)** — same `athena.py` runs identically under systemd (VPS) and launchd (Mac); state in MCP only; cycle-across-hosts produces zero state loss.

---

## CHANGE 5 — §7 RISK FLAGS — Append

- 🟡 **Athena fabrication risk → KB pollution (NEW v4.0.3.1)** — if Athena hallucinates and Aletheia misses it, KB pollution propagates to all workers reading that namespace. Mitigation: ≥2 independent citations required per non-obvious claim; Aletheia mutual check is mandatory pre-commit gate; Solon spot-audits KB writes weekly during first 30 days.
- 🟡 **SI drift via auto-merge bypass (NEW v4.0.3.1)** — if Solon-gate is ever circumvented (bug, race condition, agent confusion), agent identities can drift uncontrolled. Mitigation: hard rule documented in standing rules; three-location sync code requires explicit `si_merge_approved` decision UUID before propagation; Cerberus alerts on any SI write without prior `si_merge_approved`.
- 🟡 **Cross-pollination namespace gap (NEW v4.0.3.1)** — `kb:shared:*` namespace does not exist in current MCP ACL; fanout fallback (Path B) creates 3x write redundancy and tag-discovery overhead. Mitigation: file Path A architectural proposal for shared-namespace ACL extension; transparent swap when approved.
- 🟢 **Athena cost (NEW v4.0.3.1)** — $0 marginal (Kimi flat-rate); ≤$10/mo bridge external research budget; $0 once Sonar-Replica live. Negligible.
- 🟢 **Athena over-research / context bloat (NEW v4.0.3.1)** — risk that Athena writes too much to KB and slows agent bootstrap. Mitigation: KB write size cap per write (≤2KB); rolling pruning of stale entries by Hygeia.
- 🟢 **Host migration risk (NEW v4.0.3.1)** — Mitigated structurally by §3I.7 *Deployment Portability Doctrine*. Process portable across hosts; state in MCP; migration = supervisor-unit redeploy.

---

## NET MATH UPDATE

| Metric | v4.0.2.2 | v4.0.3.1 | Δ |
|---|---|---|---|
| Agent classes (v4.0.x line) | 27 | 28 | +1 (Athena) |
| Total instances (4-deep, v4.0.x line) | 108 | 112 | +4 |
| Marginal API cost delta | $0 | $0 | $0 (flat-rate) |
| Bridge external research budget | n/a | ≤$10/mo | ≤$10/mo (drops to $0 post-Sonar-Replica) |
| Phases | 11.7 | 11.8 | +0.1 (Phase 11.8) |
| Days to full deploy | 30 | 32 | +2 |
| Acceptance criteria items | 62 | 69 | +7 |

> **Reconciliation footnote:** v4.0.x line totals do NOT include CHIEF_BUILD_TEAMS_v1.x line (12 chief team builder classes × 4 = 48 instances). **Combined factory-wide totals when both operational: 40 classes × 4 = 160 instances.**

---

## VERIFICATION — FIRST-PASS GATE

- ✅ **Naming:** Athena fits Greek-wisdom mythology pattern; no collision with existing classes.
- ✅ **Routing:** Athena ↔ Iris, Athena ↔ Aletheia, Athena ↔ specialist chiefs all documented.
- ✅ **Pricing:** $0 marginal corrected from prior misleading attribution. Bridge external budget ≤$10/mo stated separately.
- ✅ **Tiering:** Athena joins Tier-1 alongside verifiers and Iris.
- ✅ **Trade-secrets:** internal only, not client-facing. No external tool/model names exposed in client-facing artifacts.
- ✅ **Cross-refs:** §3E updated, §4 phase added, §5 + §7 appended. v4.0.2.2 §3H.7 inheritance from this §3I.7 confirmed.
- ✅ **Math:** 27→28, 108→112, $0 marginal, +0.1 phase, +7 criteria — all verified. Reconciliation footnote present. Combined factory total stated.
- ✅ **ADHD-format:** tables + bullets, no walls of text.
- ✅ **Cohort sync:** A/B/C/D synchronized with rest of factory.
- ✅ **Solon-gate enforcement:** SI delta auto-merge prohibition is hard rule, technically enforced at three-location sync layer.
- ✅ **Mutual-check:** Athena ↔ Aletheia citation honesty pipeline mandatory pre-commit.
- ✅ **KB namespace honesty:** verified-only list (no hallucinated namespaces); new namespace requests Solon-gated; cross-pollination implementation paths documented (A preferred, B ships first).
- ✅ **Observability ownership:** Athena logs her own KB write timestamps via decision tags — no assumed external metrics.
- ✅ **Deployment portability:** §3I.7 doctrine locked, factory-wide scope defined, chief exemption explicit, future-proof envelope stated.

**Gate passed.**

---

## STRATEGIC NOTE FOR SOLON

Athena is the system that closes the loop on "AMG keeps getting smarter." Without her, the factory bootstraps once and slowly stales out. With her, every shift starts with a fresh read of what changed yesterday.

The hard rule — **SI deltas never auto-merge** — is the difference between Athena being a learning system vs. a drift system. Don't loosen this rule even when she proves trustworthy. The Solon-gate is what keeps agent identities anchored to your direction, not to whatever the latest research suggests.

The §3I.7 *Deployment Portability Doctrine* is the bigger architectural win. Locking it now means every non-chief agent built from this point forward is host-agnostic by construction. When AMG migrates Mac-resident agents to VPS (or anywhere), the change is supervisor redeploy — no rewrite. Future-proof. Backwards-compatible. This is the kind of structural decision that pays compounding interest as the factory scales.

**Build sequencing recommendation:** Defer Athena build to Wave 3 Day 31–32, after Iris is stable. Athena's full power comes online once Sonar-Replica ships (CT-51) — until then, run her on the Kimi flat-rate + bridge external research budget (≤$10/mo) and accept slightly higher transient costs for the first 30–60 days.

**END v4.0.3.1**
