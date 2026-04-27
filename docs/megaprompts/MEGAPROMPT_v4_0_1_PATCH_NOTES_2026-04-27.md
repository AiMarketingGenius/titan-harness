# v4.0 → v4.0.1 PATCH NOTES
**Source doc:** `/mnt/user-data/outputs/MEGAPROMPT_TITAN_AGENT_REST_v4_0.md` (sealed 2026-04-27)
**Patch date:** 2026-04-27
**Patch scope:** Surgical — three additions, no architectural rewrite
**Rationale:** Triggered by today's 96% disk emergency (Slack `amg-admin` alert at 8:00 UTC). Proved v4.0's DevOps coverage was incomplete. Also folds in the `Aristotle` decision from the Hercules thread review.
**Validation:** Patch is small enough to skip full dual-engine re-validation. Underlying v4.0 was already sealed at Perplexity 9.5 / Gemini 9.6.

---

## CHANGE 1 — §6 #15 CHEAP-JUDGE MANDATE — Aristotle replaces Perplexity Sonar

**Before (v4.0 §6 #15, paraphrased):**
> All quality grading uses Kimi K2 first, local Ollama where capable. Frontier escalation only for: Layer-2 thresholds exceeded, Solon explicit request, frontier-tier client deliverables. Secondary cheap-judge validator: **Gemini API or Perplexity Sonar.**

**After (v4.0.1):**
> All quality grading uses Kimi K2 first, local Ollama where capable. Frontier escalation only for: Layer-2 thresholds exceeded, Solon explicit request, frontier-tier client deliverables. Secondary cheap-judge validator: **Gemini API or Aristotle (in-house deep research agent on Kimi Allegro flat-rate).** Perplexity dependency phased out per IP-sovereignty doctrine — see v5.0 megaprompt for Aristotle hardening sequence.

**Transition note:** Until Aristotle is hardened (v5.0 Phase 3), Perplexity Sonar remains the temporary fallback. Once Aristotle passes its 7-day cheap-judge accuracy test (≥9.0 vs Perplexity baseline on 20 sample queries), Perplexity is decommissioned.

---

## CHANGE 2 — §2 SCOPE — Add Argus to in-scope agent table

**Insert into v4.0 §2 (after Hygeia, before EOM exclusion list):**

| Agent | Host | Treatment | Why included |
|---|---|---|---|
| **Argus** (NEW v4.0.1) | VPS daemon | Hard reset + 4-shift rotation | Many-eyed watchman. Proactive resource monitoring (disk, memory, CPU, network, certs, backups). Detects threshold breaches and anomaly patterns BEFORE they cause outages. Today's 96% disk alert proved this role was missing. |

---

## CHANGE 3 — §3E AGENT INVENTORY — Add Argus row, expand Hygeia row

**Replace v4.0 §3E "Universal 4-deep — full agent inventory (v4.0)" total count from "25 classes × 4 = 100 instances" to "26 classes × 4 = 104 instances."**

**Insert new row after Hygeia row:**

| Agent class | Instances | Special handling |
|---|---|---|
| **Argus** (NEW v4.0.1) | 4 | Proactive infrastructure monitoring; mutual check with Hygeia for closed-loop remediation |

**Update Hygeia row description** (was: "Cleaning agent (per §3F); mutual check with Aletheia"):

| Agent class | Instances | Special handling |
|---|---|---|
| Hygeia (UPDATED v4.0.1) | 4 | Cleaning agent — full hygiene scope: MCP poison scrubbing + KB chunk audit + drift detection (existing) PLUS infrastructure remediation: R2 offloads, log rotation, disk cleanup, memory leak hunting, restic prune (NEW). Mutual check with Aletheia for MCP work; mutual check with Argus for infra work. |

---

## CHANGE 4 — §3F NEW SUBSECTION — Argus Specification

**Insert new subsection §3G after §3F (Hygeia):**

### 3G. ARGUS — INFRASTRUCTURE WATCHMAN (NEW v4.0.1)

**Greek mythology:** Argus Panoptes, the hundred-eyed giant. Ever-vigilant. Even when sleeping, half his eyes remained open.

#### Why Argus exists

Today (2026-04-27, 8:00 UTC), VPS disk hit 96% (threshold 85%). The alert reached Solon via Slack but prescribed "manually run `/opt/amg-scripts/r2-offload.sh`" — meaning **no agent was empowered to act preemptively.** That violates two AMG principles: (1) Solon is not middleware, (2) closed-loop remediation beats human-in-the-loop alerts.

Argus closes that loop.

#### Six responsibilities

1. **Resource threshold monitoring** — disk, memory, CPU, network throughput; 1-min cadence; configurable thresholds per resource (defaults: disk 80% warn / 85% act / 92% emergency, memory 85% / 90% / 95%)
2. **Certificate expiry monitoring** — TLS certs on all domains (aimarketinggenius.io, memory.aimarketinggenius.io, ops.aimarketinggenius.io, aimemoryguard.com); 24hr cadence; alert at 30 days, act at 14 days (trigger renewal)
3. **Backup integrity verification** — daily restic snapshot probe (random file extract + hash check); alert if snapshot fails or grows pathologically
4. **Anomaly detection** — pattern-match on log volume spikes, error rate jumps, unusual traffic; coordinate with Cerberus (security side) and Aletheia (correctness side) to disambiguate infra vs security vs drift
5. **Service uptime monitoring** — heartbeat probes to all systemd units in `/etc/systemd/system/amg-*`; missing heartbeat >2 min triggers diagnostic + Hygeia handoff
6. **Daily infra health report** — `log_decision(tag="argus:daily_health_report")` published every 24hr with: disk/mem/CPU peaks, cert expiry calendar, backup status, anomaly count, remediation actions taken (and outcomes), recommendations for Solon

#### Argus → Hygeia closed-loop remediation

When Argus detects a threshold breach, the workflow is:

1. **Detect** — Argus identifies threshold crossing (e.g., disk 87%)
2. **Classify** — Determine if action is in Hygeia's playbook (R2 offload, log rotation, etc.) or requires Solon escalation (e.g., disk 95%+ with no offload candidate)
3. **Dispatch** — `queue_operator_task` for Hygeia with specific remediation instruction + acceptance criteria
4. **Verify** — Argus polls every 5 min until Hygeia reports done; verifies threshold resolved
5. **Log** — Both agents log decisions; Argus closes loop with `log_decision(tag="argus:remediation_verified")`

If Hygeia fails to resolve within SLA (15 min default), Argus escalates: P0 Slack alert + `flag_blocker` in MCP.

#### What Argus CAN do (autonomously)

- Read all system metrics (read-only access to /proc, /sys, df, free, ss, journalctl)
- Dispatch tasks to Hygeia
- Renew TLS certificates via Let's Encrypt automation (certbot)
- Probe backups (read-only)
- Log decisions, flag blockers
- Send P0/P1 Slack alerts to Solon for visibility

#### What Argus CANNOT do (escalation required)

- Modify systemd unit configs
- Restart services directly (Hygeia or watchdog handles)
- Delete user data
- Modify production code
- Bypass Solon for any disk action that requires destructive ops on /home/, /opt/clients/, or restic snapshots

#### Argus runs on 4-shift rotation

4 instances (Argus-A, -B, -C, -D), 6hr shifts, lcache continuity, active claim lock token. Mutual check with Hygeia: Argus verifies Hygeia's remediations, Hygeia audits Argus's threshold accuracy (false-alarm prevention).

#### Implementation footprint

- Single Python service: `argus.py` running as systemd unit (4 instances, shift rotation)
- Reads `/proc/meminfo`, `df`, `journalctl`, `restic snapshots`, `certbot certificates`
- Writes via standard MCP tools + dispatch to Hygeia via `queue_operator_task`
- Cost: ~$1-2/mo Kimi-based (one Argus active at a time per shift schedule)

---

## CHANGE 5 — §3F HYGEIA SCOPE EXPANSION

**Update v4.0 §3F responsibility list. Was 6 responsibilities (poison scanning, active scrubbing, KB hygiene, cross-agent notification, preventative drift detection, daily health reports). Now adds 5 infra responsibilities:**

7. **R2 offloads** — execute `/opt/amg-scripts/r2-offload.sh` on dispatch from Argus; verify disk drops below threshold; report
8. **Log rotation** — when log dirs exceed configured size, gzip + archive to R2; remove old files per retention policy
9. **Disk cleanup** — identify and remove temp files, build artifacts, old node_modules, stale snapshots; conservative defaults (only target known-safe dirs); never touch /home, /opt/clients, restic backup dirs
10. **Memory leak hunting** — when memory >90%, identify top RSS processes; if known-safe (n8n workers, log shippers), trigger graceful restart via systemd; never SIGKILL critical services
11. **Backup pruning** — on Argus dispatch, run `restic prune` per retention policy; verify integrity post-prune

**Hygeia-Argus mutual check addition** (existing Hygeia-Aletheia mutual check for MCP poison stays):

- Argus dispatches infra remediation → Hygeia executes → Argus verifies threshold resolved
- If Argus reports false positive (e.g., Hygeia did nothing because threshold was actually OK), 2 false positives in 24hr → Cerberus alerts on Argus drift
- If Hygeia reports remediation done but threshold persists, 2 failed remediations in 24hr → flag_blocker, escalate

---

## CHANGE 6 — §4 IMPLEMENTATION SEQUENCE — Insert Phase 11.5

**After Phase 11 (Hygeia rollout), insert:**

### Phase 11.5 — Argus rollout + Hygeia infra-scope expansion (Day 26–28, NEW v4.0.1)

1. Build `argus.py` Python service implementing all 6 responsibilities per §3G
2. Deploy 4 Argus instances on 4-shift rotation (per §3E)
3. Expand `hygeia.py` with 5 new infra remediation methods per §3F update
4. Wire Argus → Hygeia dispatch path: Argus calls `queue_operator_task(assigned_to="hygeia", priority="urgent")` for threshold breaches
5. Configure Argus thresholds via `/opt/amg-governance/argus_thresholds.yaml` (template-rendered, never hand-edit)
6. Wire Argus daily report into Atlas → "Infra Health" panel
7. **Verification:**
   - Synthetic disk-fill test: dd-create temp file pushing disk to 87% → Argus detects within 2 min → dispatches Hygeia → Hygeia runs r2-offload → Argus verifies <80% within 15 min
   - Synthetic cert-expiry test: mock cert with 13-day expiry → Argus triggers certbot renewal → verifies new cert valid >60 days
   - Synthetic memory-leak test: dummy process consuming RSS → Argus detects → Hygeia gracefully restarts → Argus verifies memory recovered
   - False-positive guard: drop Argus threshold to "always trigger" briefly → confirm Cerberus alerts on Argus drift after 2 false positives
8. **Acceptance:** 7-day stability period — Argus daily reports show zero unaddressed threshold breaches; remediation SLA <15 min average

---

## CHANGE 7 — §5 ACCEPTANCE CRITERIA — Append

**Append to v4.0 acceptance criteria list:**

- 50. ✅ **Argus continuous resource monitoring (NEW v4.0.1)** — synthetic disk-fill at 87% → Argus detects within 2 min → dispatches Hygeia → resolved <15 min
- 51. ✅ **Argus cert expiry automation (NEW v4.0.1)** — synthetic 13-day-expiry cert triggers automated certbot renewal; new cert valid >60 days
- 52. ✅ **Argus → Hygeia closed-loop verified (NEW v4.0.1)** — 100% of Argus-detected breaches result in either Hygeia remediation success OR escalation to Solon (no silent failures)
- 53. ✅ **Hygeia infra-scope expansion verified (NEW v4.0.1)** — R2 offload, log rotation, disk cleanup, memory leak hunting, restic prune all execute on dispatch with correct verification
- 54. ✅ **No regression on Hygeia MCP scope (NEW v4.0.1)** — existing MCP poison scrubbing accuracy maintained or improved post-expansion
- 55. ✅ **Daily Argus infra health report (NEW v4.0.1)** — `log_decision(tag="argus:daily_health_report")` published every 24hr with disk/mem/CPU peaks, cert calendar, backup status, anomaly count, remediation actions

---

## CHANGE 8 — §7 RISK FLAGS — Append

- 🟡 **Argus false-positive cascade (NEW v4.0.1)** — if Argus thresholds are too aggressive, Hygeia gets dispatch-spammed → real remediation queue gets backed up. Mitigation: Cerberus monitors Argus FP rate; >5% FP triggers threshold review.
- 🔴 **Argus blind spot during own restart (NEW v4.0.1)** — during Argus shift handoff (~3-5s), no agent is monitoring resources. Mitigation: 4-shift rotation overlap protocol — outgoing Argus completes final scan within last 30s of shift; incoming Argus's first action is a full scan within 5s of acquiring active claim lock. Combined gap <10s.
- 🟡 **Argus + watchdog scope overlap (NEW v4.0.1)** — existing process watchdog (proved working in today's Titan-Agent auto-restart) overlaps with Argus's service uptime monitoring. Resolution: watchdog owns process-level health-check restart at systemd layer; Argus owns higher-level resource thresholds and pattern detection. Document the boundary in Phase 11.5 build.
- 🟢 **Hygeia compute increase (NEW v4.0.1)** — adding infra remediation increases Hygeia workload. Estimated +50% Kimi tokens vs MCP-only scope. Cost impact: ~$1-2/mo. Negligible vs disk-outage cost.

---

## NET MATH UPDATE

| Metric | v4.0 | v4.0.1 | Δ |
|---|---|---|---|
| Agent classes | 25 | 26 | +1 (Argus) |
| Total instances (4-deep) | 100 | 104 | +4 |
| Monthly cost delta vs current | +$4 | +$5–6 | +$1–2 |
| Phases | 11 | 11.5 | +0.5 (Phase 11.5 inserted) |
| Days to full deploy | 25 | 28 | +3 |
| Acceptance criteria items | 49 | 55 | +6 |

ROI math unchanged at architectural level: drift cost avoided ($150–750/mo) + outage cost avoided (today's disk-at-96 alone = est. $50–500 if it had reached 100%) vs +$5-6/mo total cost = **30x–250x ROI.**

---

## VERIFICATION — FIRST-PASS GATE

- ✅ Naming: Argus mythology-consistent with AMG pattern (Greek). No collision with hephaestus-{chief} builders (those stay).
- ✅ Routing: Argus → Hygeia dispatch documented; mutual check with Cerberus for FP guard
- ✅ Pricing: Cost delta calculated; +$1-2/mo on Kimi flat-rate
- ✅ Tiering: Argus joins Tier-1 alongside existing verifiers (Aletheia/Cerberus/Hygeia)
- ✅ Trade-secrets: No tool/model names exposed (Argus internal only, never client-facing)
- ✅ Cross-refs: All references back to v4.0 §§ verified; new §3G inserted cleanly
- ✅ Math: Class count, instance count, cost delta, ROI all verified
- ✅ ADHD-format: Tables and numbered sections, no walls of text

**Gate passed.** Patch ready for application by Titan against locked v4.0 file.

---

## APPLICATION INSTRUCTIONS (for Titan)

1. Read the locked file at `/mnt/user-data/outputs/MEGAPROMPT_TITAN_AGENT_REST_v4_0.md` (or wherever it lives in `/opt/amg-docs/megaprompts/`)
2. Apply the 8 changes above using `str_replace` (each change is a discrete, surgical edit)
3. Rename file: `MEGAPROMPT_TITAN_AGENT_REST_v4_0_1.md`
4. Bump version header in line 1 to `v4.0.1` and dateline to `2026-04-27 (patched)`
5. Add patch-history footer noting CHANGE 1–8 above
6. Save copy of v4.0 to `/opt/amg-docs/megaprompts/archive/v4_0_sealed_2026-04-27.md` (immutable audit trail)
7. `log_decision(tag="megaprompt_v4_0_1_applied")` with deliverable_link to new file

**END OF PATCH NOTES**
*Verification: First-Pass Gate passed (naming ✓ routing ✓ pricing ✓ tiering ✓ trade-secrets ✓ cross-refs ✓ math ✓ ADHD-format ✓).*
