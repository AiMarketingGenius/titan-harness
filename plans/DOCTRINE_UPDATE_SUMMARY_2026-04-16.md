# DOCTRINE UPDATE SUMMARY — 2026-04-16

**Purpose:** shareable change-summary for Perplexity / external audit.
Generated per Solon's doctrine-maintenance rule (2026-04-16 directive).

Two canonical doctrine files updated in lockstep:

| File | Version | Audience | Commit |
|---|---|---|---|
| `plans/DOCTRINE_AMG_ENCYCLOPEDIA.md` | v1.5 → **v1.6** | INTERNAL (full vendor + model names + infra identifiers) | `80a0fdf` |
| `plans/DOCTRINE_AMG_CAPABILITIES_SPEC.md` | v1.1 → **v1.2** | EXTERNAL (trade-secret-scrubbed — no vendor / model / host names) | `80a0fdf` |

Both files live on master, mirrored clean Mac = VPS = GitHub at `80a0fdf`.

---

## What changed in DOCTRINE_AMG_ENCYCLOPEDIA (v1.5 → v1.6)

Five material deltas — all five new facts from Solon's 2026-04-16 directive are now in the body, with the superseded v1.5 content moved to a new **APPENDIX E CHANGELOG / ARCHIVE**.

### 1. Beast VPS commissioned as primary production (§3.1)

Two-tier topology is now canonical:
- **Primary prod:** beast VPS (specs pending Solon confirmation — deliberately left as placeholders, no fabrication).
- **Staging + DR failover:** HostHatch VPS, 170.205.37.148, 12c/64G/200GB NVMe, $60/mo, Ubuntu 22.04 — demoted from primary 2026-04-16, retains full operational role as canary + failover mirror.
- **Tertiary (planned):** Hetzner 2× CX32 EU lane — under re-evaluation given beast-primary topology change (may be absorbed into HostHatch-as-failover).

Services mirror-deploy to both VPS via the existing post-receive hook chain; no data loss or credential rotation for the topology move.

### 2. 140-lane n8n parallelism (§3.2.1 + new §3.2.2)

Canonical performance spec updated:
- `Concurrent heavy n8n workflows`: 3 → **7**
- `Total parallel n8n lanes`: 60 → **140** (= 20 × 7 on beast)

New **§3.2.2** allocation map specifies how the 140 are used:
- ~30 Pillar A (Acquisition — outbound + inbound)
- ~30 Pillar C (Nurture & Conversion — multi-channel cadences)
- ~28 Pillar E (Delivery & Customer Service — 7 WoZ agents × ~4 avg)
- ~20 Pillar F (Client Portal + reporting)
- ~20 internal ops (self-heal layer)
- ~12 burst headroom

Policy hard caps (CPU 90%, RAM 56 GiB) still bound the worst case; `bin/check-capacity.sh` fails closed on exceed, not crash.

### 3. Sonar A- floor on implementation-phase tasks (new §12.5)

Hard rule, enforced at **three independent layers** (no single bypass path):

| Layer | Location | Mechanism |
|---|---|---|
| Worker refusal | `lib/dual_ai_phase_worker.py` | Refuses completion transition if graded below A- |
| MCP application gate | `/opt/amg-mcp-server/src/tools/task-queue.js` ~line 209 | `update_task(status='completed')` returns `QC_GRADE_REQUIRED` / `QC_GRADE_BELOW_FLOOR` error |
| DB trigger (last-line guard) | `sql/140_implementation_qc_gate.sql` | `BEFORE UPDATE` raises `IMPLEMENTATION_QC_GATE_VIOLATION` even on direct REST calls |

Two-tier grade floor coexists:
- **Implementation-phase tasks** (`task_risk_tier='implementation'`) — **A- floor** (≥ 9.0/10).
- **Doctrine ship / permanent canon** (§10.5, §12 Idea Builder) — **A floor** (≥ 9.4/10).

Cost gate: `policy.yaml war_room.budget.*` (currently $150/month + 20/hour ceiling). Budget-exhausted state escalates; no silent self-grade fallback.

### 4. Dual-AI phase worker (Claude + GPT-5.4) — high-level (new §12.6)

For every implementation-phase task:

1. **Solution A** — Claude (primary frontier, Opus/Sonnet/Haiku routed by task class).
2. **Solution B** — secondary frontier model (GPT-5.4 via OpenAI API once wired; `lib/secondary_model.py` abstracts provider + model + API key + base URL from `/etc/amg/secondary_model.env` — swap providers with no code change).
3. **Adjudication** — both solutions → Sonar (Perplexity sonar-pro) with 10-dimension rubric → winner + merge recommendation.
4. **Completion gate** — A- floor applied; below-floor → `revision_needed` with structured remediation feedback.
5. **Audit** — one row per run in new `dual_ai_exchanges` table (both solutions + verdict + per-lane cost + winner + merged output).

Tier-gated routing:
- `exempt` / `low` / `standard` / `critical` → existing `titan_queue_watcher.py` (single-model + 4-layer QES).
- `implementation` → new `dual_ai_phase_worker.py` (dual-AI + A- floor).

Flag per tier in `policy.yaml dual_ai_phase_worker.mandatory_for_tiers` (tightenable without code change).

Cost caps per-task / daily / monthly in `policy.yaml dual_ai_phase_worker.budget.*`. Budget-exhausted → `status='escalated'` + operator ping.

**Status:** doctrine drafted, file-by-file foreman plan reviewed with Solon 2026-04-16; code ship pending go/no-go.

### 5. Maintenance rule codified (metadata header + APPENDIX E standing rule)

- Update body AND add CHANGELOG entry within 48h of any material infra / quality-gate / dual-AI change.
- Body reads as current state, always.
- Short change summary generated after each update for Solon to share with Perplexity (this document is that summary for v1.6).
- Surgical `str_replace` patches only; no full rewrites without explicit Solon approval.

### Archived to APPENDIX E (no longer in body)

- Full §3.1 HostHatch-as-primary block (was current v1.0 → v1.5).
- §3.2.1 row showing 20 × 3 = 60 lanes.
- §14.2 sprint status language that assumed HostHatch-primary.
- Appendix D row showing "n8n queue mode (60 lanes capacity)" — replaced with 140-lane row.

---

## What changed in DOCTRINE_AMG_CAPABILITIES_SPEC (v1.1 → v1.2)

Same five facts, expressed in **external-safe language** — no vendor names, no model names, no hostnames / IPs, no commit hashes.

### Summary of changes

1. **§5 Infrastructure Envelope** split into four subsections:
   - §5.1 two-tier topology (primary + staging/failover + tertiary planned) — described structurally without vendor names.
   - §5.2 capacity ceilings updated: concurrent heavy workflows 3 → 7, total parallel workflow lanes 60 → 140.
   - §5.3 allocation map (30/30/28/20/20/12 across the 7 pillars + burst headroom).
   - §5.4 operating cost range updated to $360–$500/month.

2. **§2.3 Quality + Safety Enforcement table** gains two new rows:
   - **Implementation-phase A-minus floor** — described as "three-layer enforcement (worker refusal, application-layer gate, database-layer trigger), non-completable without ≥ 9.0/10 grade, two-tier floor with A for doctrine-ship still in place."
   - **Dual-AI phase-worker pattern** — described at high level: "two independent frontier AI providers each generate a candidate solution; a third web-grounded adjudicator grades both against the 10-dimension rubric and returns a winner. Durable audit row captures everything. Cost bounded by per-task / daily / monthly caps."

3. **§7 Quality Enforcement** gains two new subsections with the same substance as the §2.3 rows but in full prose:
   - §7.1 implementation-phase A-minus floor (three-layer enforcement + two-tier coexistence).
   - §7.2 dual-AI phase-worker pattern (5-step flow: Solution A → Solution B → adjudication → completion gate → audit row, tier-gated cost awareness).

4. **New §16 CHANGELOG** holding superseded v1.0 → v1.1 content (single-primary narrative + 60-lane figures).

### External-safe wording guarantees (maintained)

- No vendor names used (no "beast", no "HostHatch", no "Hetzner", no "Cloudflare", no "Supabase").
- No model names used (no "Claude", no "GPT-5.4", no "Sonar / Perplexity").
- No IPs / hostnames / file paths / commit hashes.
- Dual-AI phrased as "two independent frontier AI providers"; adjudicator as "third web-grounded adjudicator"; A- floor as "≥ 9.0/10 on 10-dimension rubric"; infrastructure as "primary production server" / "staging + DR failover server".

---

## How to share this with Perplexity

Three paths, in order of preference:

### Path A — Share Encyclopedia v1.6 (internal, full detail) under NDA

```
https://github.com/AiMarketingGenius/titan-harness/blob/80a0fdf/plans/DOCTRINE_AMG_ENCYCLOPEDIA.md
```

Full infrastructure identifiers + vendor names + model names visible. Use only when the reviewer is under NDA (the master NDA Solon has in use for adversarial-review relationships).

### Path B — Share Capabilities Spec v1.2 (external, scrubbed) — default

```
https://github.com/AiMarketingGenius/titan-harness/blob/80a0fdf/plans/DOCTRINE_AMG_CAPABILITIES_SPEC.md
```

All proprietary detail scrubbed. Safe to share with any external reviewer without NDA. Captures all five 2026-04-16 facts in public-safe language.

### Path C — Share this summary document

```
https://github.com/AiMarketingGenius/titan-harness/blob/80a0fdf/plans/DOCTRINE_UPDATE_SUMMARY_2026-04-16.md
```

Perplexity-ready audit trail of exactly what changed and why. Use when the reviewer needs the diff-level summary rather than the full spec.

---

## Suggested prompt for Perplexity audit

```
I've updated two canonical doctrine documents for my production AI
infrastructure platform. The scrubbed external version is attached
(DOCTRINE_AMG_CAPABILITIES_SPEC v1.2). Five material changes landed
2026-04-16:

1. Two-tier VPS topology: a higher-capacity primary server was
   commissioned; the previous primary was demoted to staging + DR
   failover (same hardware, new role).
2. Workflow parallelism increased from 60 lanes to 140, allocated
   across seven platform pillars + internal ops + burst headroom.
3. Implementation-phase tasks now require a ≥ 9.0/10 grade from an
   independent web-grounded adjudicator before they can be marked
   complete. Enforcement is three-layer (worker refusal, application
   gate, database trigger). Doctrine-ship work keeps the stricter
   ≥ 9.4/10 floor.
4. A new dual-AI pattern for implementation phases: two independent
   frontier AI providers each generate a solution, a third adjudicator
   picks a winner, and only a winning solution that clears the A-minus
   floor completes the task. Full audit row per run; cost capped
   per-task / per-day / per-month.
5. Maintenance rule: body of the doctrine = current state only;
   superseded content moves to CHANGELOG section.

Please audit:
- Are the capacity ceilings (140 lanes, per-pillar allocation)
  internally consistent with the claimed 7-pillar commercial workload?
- Is the three-layer enforcement of the A-minus floor an appropriately
  designed defense-in-depth pattern for this threat model, or are
  there attack surfaces I'm missing?
- Is the dual-AI adjudication pattern (A vs B → third-party grade →
  winner + audit) sound, or does it introduce new failure modes I
  should watch for?
- Does the two-tier VPS topology with staging/failover mirror give me
  actual DR coverage, or does it need a true third provider to hit
  the SLA targets in §6?
- Where is this architecture under-specified for a buyer or acquirer
  to complete due diligence without NDA?

Confidence flags on each finding. No summarization — detailed review.
```

---

**Change summary produced:** 2026-04-16 by Titan per Solon's 2026-04-16 doctrine-maintenance-rule directive.
**Commit:** `80a0fdf` on `master` (Mac == VPS == GitHub).
**Next doctrine-update trigger:** beast VPS specs finalized, dual-AI code ship, first implementation-phase task graded live, or 48h — whichever comes first.
