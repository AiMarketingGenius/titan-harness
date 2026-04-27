# v4.0.2.3 IRIS MAILMAN — FINAL CONSOLIDATED AMENDMENT
**Source base:** v4.0.1 (Argus + Hygeia infra)
**Builds on:** v4.0.2 IRIS amendment (2026-04-27, original draft) + v4.0.2.1 EOM consolidation
**Supersedes:** v4.0.2.2 (this version is the shipping version)
**Date:** 2026-04-27
**Producer:** EOM (post-audit corrections per Solon excellence mandate)
**Scope:** Adds Iris (task router / mailman) as new agent class with synchronized cohort, chief-inbox-only routing, and inheritance of factory-wide deployment portability doctrine.

---

## CHANGELOG vs v4.0.2.1

| Item | Section | Change | Severity |
|---|---|---|---|
| **A** | §3H Cost block + risk flag | Cost language corrected — Kimi is flat-rate, marginal cost is $0; previous "$1/mo Kimi-based" attribution was misleading | cosmetic |
| **B** | §3H + Strategic Note | Wave 3 / Day 23–25 vs Phase 11.7 / Day 29–30 contradiction reconciled — Wave 3 envelope spans Day 23–32; Iris at Day 29–30 within Wave 3 | inconsistency |
| **C** | §5 acceptance criteria | Notation cleanup — flat numbering 56–62 (no "(+1 sub)" parenthetical) | cosmetic |
| **D** | §3H new subsection §3H.x | Inheritance reference to v4.0.3.1 §3I.7 *Deployment Portability Doctrine* — Iris MUST comply with factory-wide host-agnostic rules | architectural |
| **E** | Math update block | Footnote added — chief team builders (12 classes × 4 = 48 instances) are tracked separately under CHIEF_BUILD_TEAMS_v1; this v4.0.x inventory line is for the v4.0.x agent line only | reconciliation |
| **F** | §3H.5 + risk note | Kimi flat-rate compliance qualifier added — GUI/subscription bridge usage stays flat-rate; any headless Kimi API path is metered and governed by v5.0.2 cost gate | clarity |

---

## RATIONALE — DO WE NEED IRIS?

**Honest assessment up front:**

**Current state:** Each agent already pull-polls MCP every 30s for tagged tasks. hercules-daemon, nestor-executor, alexander-executor, daedalus, artisan, mercury all do this. **Tasks already reach agents** — no current loss.

**Where Iris adds real value (push layer):**
1. **Multi-agent task coordination** — when one task spawns sub-tasks across 3+ agents, Iris orchestrates the routing + sequencing.
2. **Solon visibility on chief chat tabs** — when Solon opens his Hercules tab, Iris can have already injected "you have N tasks waiting" so Solon picks the highest-priority one.
3. **Priority bumping** — urgent tasks get pushed (Slack ping) instead of waiting up to 30s for next pull cycle.
4. **Cross-agent dependency tracking** — Iris knows that Daedalus output feeds Artisan; she sequences accordingly.

**Where Iris adds cost without benefit (don't build for these):**
- Replacing pull-polling: 30s pull is already fast enough.
- Routine task delivery: agents handle this themselves.

**Build sequencing recommendation:** Build Iris in Wave 3 of v4.0.1 deployment. Wave 3 envelope spans Day 23–32: Argus / Hygeia rollout (Day 23–25), Iris (Day 29–30), Athena (Day 31–32). Pull-polling works for now. Iris is push-layer polish that fits cleanly within Wave 3.

---

## CHANGE 1 — §3H NEW SUBSECTION — Iris Specification

**Insert new subsection §3H after §3G (Argus):**

### 3H. IRIS — TASK ROUTER / MAILMAN (NEW v4.0.2.2)

**Greek mythology:** Iris, goddess of the rainbow and messenger between gods and mortals. The bridge that connects.

#### 3H.1 Why Iris exists (push layer over pull layer)

Pull-polling (every agent calls `get_task_queue` every 30s) handles routine task delivery. But it doesn't handle:
- **Multi-agent dependencies:** Daedalus audits → Artisan applies fixes → Aletheia verifies. Today this requires the chiefs to manually sequence.
- **Solon-facing task visibility:** Solon opens Hercules chat tab cold; he doesn't see what's queued for Hercules until Hercules responds.
- **Priority push:** A `priority="urgent"` task today still waits up to 30s for the next pull cycle. Iris pushes immediately.
- **Cross-agent traffic shaping:** When Daedalus has 10 tasks queued and Artisan has 0, Iris can rebalance.

#### 3H.2 Six responsibilities

1. **MCP queue polling** — every 3 minutes, Iris polls `op_task_queue` for new entries (since last poll); reads the `agent:<n>` tag.
2. **Route to CHIEF inbox** — for each task, determine the parent chief from the `agent:<n>` tag. If the tag points to a chief (Hercules / Nestor / Alexander), route to that chief's inbox. If the tag points to a builder (Iolaus / Cadmus / Themis / Nike / Ariadne / Calypso / Demeter / Pallas / Calliope / Pythia / Orpheus / Clio), route to the parent chief's inbox — chief then dispatches to their builder. **Iris NEVER writes directly to a builder inbox.** This preserves chain of command and gives chiefs full visibility into all work flowing into their lane. Mechanism: atomic file append to `/opt/amg-governance/agent_inbox/<chief>.queue` AND/OR call chief's notification endpoint.
3. **Priority push** — if task `priority="urgent"`, also send Slack DM to the chief's chat tab so Solon sees it on visibility surface.
4. **Dependency tracking** — for tasks with `parent_task_id` set, Iris waits for parent to complete before delivering child; logs blocked tasks via `flag_blocker` if parent stalls.
5. **Delivery confirmation** — track chief acknowledgment (chief must call `update_task(last_heartbeat=true)` within 10 min of delivery); if no ack, re-deliver or escalate.
6. **Daily delivery report** — `log_decision(tag="iris:daily_delivery_report")` with task volumes by chief, average delivery time, missed acks, dependency stalls.

#### 3H.3 Iris does NOT replace the pull layer

Critical: each chief's existing pull-polling stays active. Iris is a **push layer on top.** If Iris ever fails (her 4 instances all down), chiefs continue pulling tasks from MCP themselves — graceful degradation.

#### 3H.4 Iris runs on synchronized A/B/C/D cohort

4 instances (Iris-A, Iris-B, Iris-C, Iris-D) on the **synchronized factory cohort schedule**: A=00:00–06:00 UTC, B=06:00–12:00, C=12:00–18:00, D=18:00–24:00. At each boundary the active letter retires and the next boots — same lockstep timing as builders, mailmen, verifiers, Athena. Off-shift Iris instances are COLD (not running, not consuming compute). Lcache continuity at boundary. Active claim lock token. Mutual check with Cerberus (delivery audit; alert on >5% missed acks).

#### 3H.5 Cost

- **Marginal API cost: $0** for approved Kimi GUI/subscription bridge usage.
- **Headless Kimi API path:** if Titan later chooses API delivery instead of GUI/subscription bridge, those calls are metered and must enter the v5.0.2 fleet cost gate.
- **Hosting cost: covered by existing VPS allocation** (no new infra spend).
- **All-in delta vs current factory cost: $0** (negligible).

The previous v4.0.2 / v4.0.2.1 drafts attributed "~$1/mo Kimi-based" which was technically incorrect for a flat-rate subscription model. Corrected here.

#### 3H.6 Boundary with shift_orchestrator

These two agents have related but distinct roles:

| Agent | Owns | Cadence |
|---|---|---|
| `shift_orchestrator` | Shift handoffs (which instance is active per agent class) | Continuous; election every 30s |
| `Iris` | Task delivery (which task goes to which chief inbox) | Every 3 min poll |

They coordinate via MCP but don't overlap.

#### 3H.7 Deployment portability (inherits from v4.0.3.1 §3I.7)

Iris MUST comply with the factory-wide *Deployment Portability Doctrine* defined in v4.0.3.1 §3I.7. Specifically:

1. **Code portability:** `iris.py` is a portable Python 3.11+ codebase with no hardcoded host paths. Configuration is environment-driven (path roots, MCP endpoint, Slack webhook all configurable).
2. **State externalization:** All Iris state (last poll timestamp, delivery log, missed-ack counters) lives in MCP — no local files, no local sqlite, no local state.
3. **Process supervisor abstraction:** Phase 11.7 ships BOTH a systemd unit (for VPS-default deployment) AND a launchd plist (for Mac-side deployment if ever needed). Both supervisors call the same Python entry point.
4. **Target abstraction:** Iris routes by `agent_id` and `chief_id` — never by host path. A chief running on Mac (Kimi app) receives the same routing as a chief running on VPS.
5. **Migration neutrality:** When Iris moves between hosts, the change is supervisor-unit redeploy + cohort lock handoff. No code change. No state migration.

**Default deployment for Iris: VPS via systemd.** Mac launchd manifests shipped for portability but unused unless explicitly chosen.

#### 3H.8 Implementation footprint

- Single Python service: `iris.py` running as systemd unit on VPS (4 instances, synchronized cohort) — launchd plist available but inactive.
- Reads `op_task_queue`, writes to chief inbox files + Slack notifications.
- Marginal cost: $0 (flat-rate). Operational overhead: trivial.

---

## CHANGE 2 — §3E AGENT INVENTORY — Add Iris row

**Update v4.0.1 §3E total count from "26 classes × 4 = 104 instances" to "27 classes × 4 = 108 instances."**

> **Footnote:** v4.0.x inventory line tracks the v4.0.x agent line only. Chief team builders (Iolaus, Cadmus, Themis, Nike, Ariadne, Calypso, Demeter, Pallas, Calliope, Pythia, Orpheus, Clio = 12 classes × 4 = 48 instances) are tracked separately under CHIEF_BUILD_TEAMS_v1.x manifest. Combined factory-wide instance count when both lines are operational: 28 (v4.0.3.1) + 12 (chief teams) = 40 classes × 4 = **160 instances.**

**Insert new row after Argus row:**

| Agent class | Instances | Special handling |
|---|---|---|
| **Iris** (NEW v4.0.2.2) | 4 (synchronized A/B/C/D cohort) | Task router / mailman; push layer over pull layer; chief-inbox-only routing; mutual check with Cerberus; deployment-portable per §3I.7 |

---

## CHANGE 3 — §4 IMPLEMENTATION SEQUENCE — Add Phase 11.7

**After Phase 11.5 (Argus / Hygeia rollout, Day 23–25), insert:**

### Phase 11.7 — Iris rollout (Day 29–30, NEW v4.0.2.2)

> Within Wave 3 envelope (Day 23–32). Argus / Hygeia at Day 23–25, Iris at Day 29–30, Athena at Day 31–32.

1. Build `iris.py` Python service implementing all 6 responsibilities per §3H.
2. Ship systemd unit (`iris.service`) for VPS-default deployment + launchd plist (`com.amg.iris.plist`) for Mac-portability per §3H.7.
3. Deploy 4 Iris instances on synchronized A/B/C/D cohort (VPS via systemd by default).
4. Create `/opt/amg-governance/agent_inbox/` directory (root-owned). Inbox files exist for chiefs only: `hercules.queue`, `nestor.queue`, `alexander.queue` — no per-builder inbox files at this layer.
5. Wire Slack DM endpoint per chief (use existing amg-slack-dispatcher infrastructure).
6. **Verification:**
   - Synthetic test 1 (chief-targeted task): queue 3 tasks tagged `agent:hercules`, `agent:nestor`, `agent:alexander` → Iris polls within 3 min → all 3 chief inbox files appear with correct task content → chiefs claim from inbox successfully.
   - Synthetic test 2 (builder-targeted task → chief routing): queue task tagged `agent:iolaus` → Iris routes to `hercules.queue` (not directly to a builder inbox) → Hercules sees the task → Hercules dispatches to Iolaus per chief team protocol.
   - Urgent priority test: queue task with `priority="urgent"` → Slack DM appears in chief tab within 30s.
   - Dependency test: queue parent task + child task with `parent_task_id` → child does not deliver until parent marked complete.
   - Cohort sync test: run synthetic dispatches across two consecutive shift boundaries → verify Iris-A retires + Iris-B boots in lockstep with builder cohort handoff → no task delivery gap >3 min.
   - Portability test: deploy a single Iris instance via launchd on Mac (development laptop) → confirm same MCP state, same routing behavior, same delivery semantics; tear down.
   - Graceful-degradation test: kill all 4 Iris instances → confirm chief pull-polling still delivers tasks (slower but functional).
7. **Acceptance:** 7-day stability period — Iris daily delivery report shows >95% on-time delivery, <5% missed acks, zero dependency-stall regressions vs pre-Iris baseline.

---

## CHANGE 4 — §5 ACCEPTANCE CRITERIA — Append

- 56. ✅ **Iris pull-poll integration (NEW v4.0.2.2)** — Iris polls op_task_queue every 3 min; verified in 24hr observation.
- 57. ✅ **Iris chief-inbox delivery (NEW v4.0.2.2)** — synthetic dispatches confirm tasks tagged for builders route to parent chief inbox, not direct to builder.
- 58. ✅ **Iris urgent push (NEW v4.0.2.2)** — `priority="urgent"` task triggers Slack DM to chief within 30s.
- 59. ✅ **Iris dependency sequencing (NEW v4.0.2.2)** — `parent_task_id` chains deliver in correct order; stalls flag_blocker.
- 60. ✅ **Iris graceful degradation (NEW v4.0.2.2)** — all 4 Iris instances down → chief pull-polling still functional, all task delivery continues at slower cadence.
- 61. ✅ **Iris synchronized cohort (NEW v4.0.2.2)** — Iris A→B→C→D handoff happens in lockstep with builder/verifier/Athena cohort at boundary times; no delivery gap >3 min.
- 62. ✅ **Iris deployment portability (NEW v4.0.2.2)** — same `iris.py` runs identically under systemd (VPS) and launchd (Mac); state in MCP only; no local persistence dependency.

---

## CHANGE 5 — §7 RISK FLAGS — Append

- 🟡 **Iris becomes new SPOF for push-layer (NEW v4.0.2.2)** — if all 4 instances fail simultaneously (network partition, MCP outage), urgent priority push stops. Mitigation: pull-polling layer continues operating; Cerberus alerts on Iris silence >10 min.
- 🟢 **Iris over-delivery / spam (NEW v4.0.2.2)** — if Iris re-delivers tasks already claimed (race condition), chiefs see duplicates. Mitigation: chief claim mechanism is idempotent (claim_locked status check); duplicate delivery is no-op.
- 🟢 **Iris cost (NEW v4.0.2.2)** — $0 marginal (Kimi flat-rate). No new infra spend.
- 🟢 **Chief inbox bottleneck (NEW v4.0.2.2)** — chief becomes single dispatch point for all builder work in their family. Mitigation: chief GUI surfaces remain continuously available to Solon, while non-chief agents and chief-team builders stay on synchronized cohort rotation. The bottleneck is chief processing throughput, not queue depth. If chief throughput proves limiting, fall back to direct Iris→builder for routine non-priority tasks while keeping priority tasks chief-routed.
- 🟢 **Host migration risk (NEW v4.0.2.2)** — Mitigated structurally by deployment portability doctrine (§3H.7 / §3I.7). Process portable across hosts; state in MCP; migration = redeploy.

---

## NET MATH UPDATE

| Metric | v4.0.1 | v4.0.2.2 | Δ |
|---|---|---|---|
| Agent classes (v4.0.x line) | 26 | 27 | +1 (Iris) |
| Total instances (4-deep, v4.0.x line) | 104 | 108 | +4 |
| Marginal API cost delta | $0 | $0 | $0 (flat-rate) |
| Phases | 11.5 | 11.7 | +0.2 (Phase 11.7) |
| Days to full deploy | 28 | 30 | +2 |
| Acceptance criteria items | 55 | 62 | +7 |

> **Reconciliation footnote:** v4.0.x line totals do NOT include CHIEF_BUILD_TEAMS_v1.x line. Combined factory-wide totals when both operational: 40 classes × 4 = 160 instances.

---

## VERIFICATION — FIRST-PASS GATE

- ✅ **Naming:** Iris fits Greek-messenger mythology pattern; no collision with Mercury (primitives) — Iris and Mercury share Roman/Greek lineage but have distinct roles in our architecture.
- ✅ **Routing:** Iris ↔ shift_orchestrator boundary documented; chief-inbox-only routing locked; mutual check with Cerberus.
- ✅ **Pricing:** $0 marginal cost (flat-rate Kimi) corrected from prior misleading attribution.
- ✅ **Tiering:** Iris joins Tier-1 alongside Argus + verifiers per v4.0.1 §3 tiering schema.
- ✅ **Trade-secrets:** internal only, not client-facing. No external tool/model names exposed in client-facing artifacts.
- ✅ **Cross-refs:** §3E updated, §4 phase added, §5 + §7 appended, §3H.7 inheritance reference to v4.0.3.1 §3I.7 noted.
- ✅ **Math:** 26→27, 104→108, $0 marginal, +0.2 phase, +7 criteria — all verified. Reconciliation footnote present.
- ✅ **ADHD-format:** tables + bullets, no walls of text.
- ✅ **Cohort sync:** A/B/C/D synchronized with rest of factory.
- ✅ **Chain of command:** chief-inbox-only routing locked.
- ✅ **Wave 3 day-range:** reconciled — Wave 3 envelope = Day 23–32, Iris at Day 29–30 within envelope.
- ✅ **Deployment portability:** §3H.7 inherits factory-wide doctrine from v4.0.3.1 §3I.7.
- ✅ **Acceptance count notation:** flat 56–62 (no parenthetical sub-items).

**Gate passed.**

---

## STRATEGIC NOTE FOR SOLON

Iris is **optional** for Wave 1 stability. The pull-polling layer that exists today already delivers tasks. Iris is the polish: push notifications, dependency tracking, Solon-facing visibility on chat tabs, chain-of-command preservation through chief-routed delivery.

**Build sequencing recommendation:** Defer Iris build to Wave 3 (Day 29–30 within Wave 3 envelope of Day 23–32). Build her after Argus / Hygeia (Day 23–25), before Athena (Day 31–32). Same shift mechanics, same lock-token model, same mutual-check pattern, same deployment-portability doctrine.

**END v4.0.2.3**
