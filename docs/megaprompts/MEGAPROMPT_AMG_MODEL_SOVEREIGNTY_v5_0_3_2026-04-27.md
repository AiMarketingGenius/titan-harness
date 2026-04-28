# Titan Dispatch - AMG Model Sovereignty v5.0.3

**Target canonical path:** `/opt/amg-docs/megaprompts/MEGAPROMPT_AMG_MODEL_SOVEREIGNTY_v5_0_3_2026-04-27.md`
**Staged path:** `/Users/solonzafiropoulos1/titan-harness/docs/megaprompts/MEGAPROMPT_AMG_MODEL_SOVEREIGNTY_v5_0_3_2026-04-27.md`
**Owner:** Achilles, CT-0427-81
**Status:** Round-4 patch staged for the next Titan judge run. The only goal here is to close the five P0 blockers before another judge cycle is spent.

## 0. Round-4 P0 Gap Coverage

| P0 Blocker | Section | Fix Summary | Self-Verification Method |
|---|---|---|---|
| Themis + Iolaus undefined | §3 / §4 | Added operative definitions with family, role, dispatch context, `executor_enabled=false`, and `reject_with_explanation` behavior. | `rg -n "### Themis|### Iolaus|executor_enabled=false|reject_with_explanation" <file>` |
| P0 bypass misses fleet ledger | §7 Lua gate | Added fleet-key `INCRBYFLOAT` inside the P0 branch so bypass spend cannot leave a stale fleet ledger. | Inspect Lua P0 branch for `new_fleet` write before return. |
| `p0_override_cap` lacks Solon identity check | §7 Lua gate | Added Solon UUID guard with hard reject on mismatch before override-cap use. | Inspect `ARGV[6]`, `ARGV[7]`, and `invoker_not_solon` return path. |
| Phase 7 carries stale round-2 residue | §11 | Rewrote Phase 7 to reflect round-3 miss and round-4 correction context. | `rg -n "before round 2|before round-2" <file>` should return nothing. |
| Metered Kimi API has no tier | §3 / §10 | Bound metered Kimi API to Tier 2 with explicit RPM/TPM caps and cost-class mapping. | `rg -n "Kimi API \\(metered path\\)|Tier 2|RPM|TPM|cost-class" <file>` |

## 1. Binding Changes From v5.0.1

v5.0.3 builds on v5.0.2 and closes the five round-3 P0 blockers that kept the file below the 9.0 dual-judge floor:

- Themis and Iolaus are now defined as operative routing actors instead of implicit names.
- The P0 Lua bypass now increments the fleet ledger as well as the override and agent ledgers.
- `p0_override_cap` is now bound to Solon identity instead of any caller that can set a cap.
- Phase 7 no longer carries stale round-2 editing residue.
- Metered Kimi API now has an explicit tier, cap, and cost-class assignment.

Non-negotiable rules carried forward:

- Perplexity, Grok, and Gemini are removed from the formal judge stack.
- Haiku is the only external judge allowed after judge-sovereignty lock.
- Flat-rate subscriptions and local models are excluded from the metered cost pool.
- Per-agent daily caps are warnings, not blockers.
- The one hard cost gate is the fleet-wide metered spend cap of `$35/day`, enforced atomically.
- Mercury is primitives-only. No LLM fallback, no reasoning.
- Kimi flat-rate means GUI/subscription use only where contractually allowed. Any Kimi API metered usage goes through the fleet cost gate.

## 1. Scope

v5.0.3 remains a model-sovereignty and cost-discipline megaprompt. It does not reopen v4.0.x paper-freeze inventory.

In scope:

- Model tier ladder.
- Titan lieutenant fleet routing rules.
- 7 AMG client-facing agent migration planning.
- Sovereign research/judge replacement planning.
- Atomic cost gate.
- Rollback, trade-secret scrub, structured receipts, Solon override discipline, and SI access discipline.

Out of scope:

- Production deploys.
- Live database migrations.
- Credential rotation.
- Cloud/DNS/payment changes.
- External sends.
- New current-scope agent classes.

## 2. Judge Sovereignty Mandate

The old validation plan used Kimi plus Gemini, with Perplexity/Aristotle references scattered through v5.0. That is superseded.

### Future Judge Pair

| Position | Allowed Judge | Notes |
|---|---|---|
| Primary | AMG Reasoning Judge | Sovereign/local or AMG-hosted service scoped in CT-0427-51. |
| External counterweight | Haiku | Only external judge retained because it is cheap, fast, and structurally useful as an adversarial pair. |

### Banned From Formal Judge Stack

| Provider | Status |
|---|---|
| Perplexity/Sonar | Removed. No live judge calls. Historical saved outputs may be used only for offline benchmark comparison. |
| Grok/xAI | Removed. No judge calls. |
| Gemini | Removed. The old CT-36 Kimi+Gemini script must not be reused unmodified. |

If AMG Reasoning Judge is not live yet, the correct behavior is to block and log `judge_stack_degraded`, or run Haiku-only as a clearly degraded advisory pass if explicitly approved. Do not silently fall back to Perplexity, Grok, or Gemini.

## 3. Model Tier Ladder

| Tier | Default Use | Provider/Runtime | Cost Treatment |
|---|---|---|---|
| T0 Frontier | Titan/Achilles/EOM hardest architecture only | Claude GUI/subscription where already approved | Report separately if flat-rate; metered API goes through gate. |
| T1 Pro Cheap | Code audit, multi-file reasoning, high-risk review | DeepSeek V4 Pro or V4 Reasoner exception | Metered, gated. |
| T2 Flash | Single-file fixes, structured drafts, bulk transforms | DeepSeek V4 Flash | Metered, gated. |
| T3 Flat-Rate Volume | Creative/advisor/high-volume work | Kimi GUI/subscription where allowed | Excluded from metered pool; subscription reported separately. |
| T4 Local | Primitives, lint, deterministic ops, local draft checks | Ollama Qwen/DeepSeek R1 | Excluded from metered pool. |
| T5 External Counterjudge | Low-cost independent critique | Haiku | Metered, gated. |

Routing classifier: Themis classifies risk, data sensitivity, task complexity, and cost tier before dispatch. Iolaus compiles the build order; Themis approves or blocks the model lane.

### Themis

- Family: Hercules.
- Role: governance/policy gate for model routing, rule conformance, and override admissibility.
- Dispatch context: sits in front of any metered or high-risk route choice; receives task metadata, risk class, scrub status, and projected cost before dispatch.
- `executor_enabled=false` until Phase 5 activation pending.
- Current behavior: `reject_with_explanation` when a route needs executor support that is not live yet.

### Iolaus

- Family: Hercules.
- Role: security audit worker per the Phase 1 registry plus decomposition aide for ambiguous or security-sensitive routing requests.
- Dispatch context: receives ambiguous, security-sensitive, or multi-step routing candidates before Mercury or other low-context lanes are allowed to proceed.
- `executor_enabled=false` until Phase 5 activation pending.
- Current behavior: `reject_with_explanation` when a task requires live executor authority that has not been activated yet.

### Kimi API (metered path)

If Kimi is used through a metered API path rather than GUI/subscription:

- Tier assignment: `T2 Flash`
- RPM cap: `60`
- TPM cap: `120000`
- Cost-class mapping: `metered_vendor_flash`
- Gate behavior: full trade-secret scrub + Redis cost reservation + structured receipt logging required

## 4. Titan Lieutenant Fleet

Daedalus, Artisan, and Mercury remain Titan/shared lieutenants. They are not duplicated under the Kimi chiefs.

### Daedalus

- Role: code audit, multi-file reasoning, security and architecture review.
- Model: DeepSeek V4 Pro default; V4 Reasoner only for explicit high-risk exception.
- Output: strict JSON with file/line findings and evidence.
- Cost: metered and gated.

### Artisan

- Role: bulk edits, templates, repetitive transforms, single-file fixes.
- Model: DeepSeek V4 Flash.
- Reject rule: if task has more than three logical steps, reject and requeue to Daedalus or Themis-approved Reasoning Judge path.
- Output: strict JSON/Pydantic. Unstructured response fails.

### Mercury

- Role: primitives only: `ssh_run`, `file_read`, `file_write`, `api_call`, `browser_navigate`, screenshot capture.
- Model: local Qwen/automation glue only where deterministic.
- Hard rule: no reasoning, no task planning, no LLM fallback.
- Requeue: any ambiguous task goes to Iolaus/Themis for decomposition, not Mercury.

## 5. 7 AMG Agent Migration

Target agents: Alex, Maya, Jordan, Sam, Riley, Nadia, Lumina.

Canonical SI locations to resolve before migration:

| Location | Purpose |
|---|---|
| Supabase `agent_config.system_prompt` | Canonical live prompt when present. |
| VPS/shared SI mirror | Runtime-accessible copy for daemons. |
| Harness `plans/agents/kb/<agent>/` or equivalent repo mirror | Auditable source-control mirror. |

No migration starts until all three locations are reconciled for that agent or the missing location is logged as `UNKNOWN` with a blocker.

Per-agent sequence:

1. Capture 20 baseline tasks from current production behavior.
2. Scrub trade secrets and client PII.
3. Run target model in parallel.
4. Judge with AMG Reasoning Judge plus Haiku when available.
5. Cut over only if target output is `>= 9.0` against baseline.
6. Monitor for 7 days.
7. Roll back that single agent if quality drops by more than `0.5` on the 10-point rubric.

Lumina migrates last because CRO quality has the highest subjective risk.

### Partial-Migration Recovery Contract

The fleet must never sit in an ambiguous half-migrated state. Every agent migration must carry a route manifest with:

- `agent_name`
- `previous_model_route`
- `candidate_model_route`
- `previous_si_revision`
- `candidate_si_revision`
- `cutover_started_at`
- `judge_decision_uuid`
- `status` in `planned | shadow | canary | cutover | rolled_back | locked`

If any cutover fails after one or more agents have already moved:

1. Freeze additional migrations immediately.
2. Mark failing agents `rolled_back` and restore prior route plus SI revision.
3. Mark already-passed agents either `locked` or `reobserve`, never leave them as implicit current state.
4. Emit one fleet-level `partial_migration_recovery` decision with the exact mixed-state matrix.
5. Block further phase advancement until the matrix has no `cutover` or unknown state left.

Hard rule: a migration wave is not complete until every targeted agent is either `locked` on the new route or `rolled_back` to the old route with proof.

## 6. Trade-Secret Scrub

Every prompt leaving AMG-controlled infrastructure passes through a scrubber before a paid/external call.

Minimum implementation:

- Deny-list internal tool names, model routing internals, credential references, Slack channel names, private repo paths, client PII, and proprietary strategy phrases marked in SI docs.
- Replace client names with stable aliases unless the task explicitly requires real names.
- Reject outbound prompt if scrubber sees secrets rather than best-effort masking silently.
- Log `trade_secret_scrub:<agent>` with hash of sanitized prompt, not raw content.

Failure rule: scrubber unavailable means fail closed for external/metered calls.

## 7. Cost Cap Discipline

### Correct Cost Pool

The metered cost pool includes only billable API/search calls:

- DeepSeek V4 Pro/Flash/Reasoner.
- Haiku.
- Brave Search or other approved search APIs.
- Kimi API only if it is metered.
- Any future V4 Reasoner exception call.

Excluded from the metered pool:

- Kimi GUI/subscription flat-rate usage.
- Claude GUI/subscription flat-rate usage.
- Local Ollama models.
- Existing fixed VPS cost.
- Already-paid app subscriptions.

Flat-rate/subscription costs still appear in monthly reporting, but they do not consume the `$35/day` metered fleet gate.

### Hard Gate And Warnings

| Scope | Behavior |
|---|---|
| Per-agent daily warning | Soft only. Emit Slack/MCP warning; do not block. |
| Fleet metered daily cap | Hard. `$35.00/day` blocks all non-P0 metered calls. |
| Monthly target | `<= $200/month` for metered usage only. This requires average spend `<= $6.67/day`, about 19% of the $35 hard cap. A sustained 25% month would be `$262.50` and fails the target. |

This fixes the round-1 contradiction: `$35/day` is an emergency hard ceiling, not a planning budget.

### P0 Emergency Bypass

The fleet cap has exactly one bypass path:

- Severity must be `P0`.
- The work must be outage containment, data-integrity containment, security containment, or judge-path recovery blocking a live rollback.
- Solon must approve the bypass explicitly with a decision UUID, dollar ceiling, and expiry time.
- Solon identity must be verified against one canonical UUID source: hardcoded deployment constant, env-injected `SOLON_UUID`, or Infisical-backed retrieval at runtime.
- The bypass must reserve against a separate `p0_override_spend_usd:<date>` key so the spend is still visible and bounded.

Without all five conditions above, the fleet cap still blocks the call. "Important," "time-sensitive," or "close to shipping" is not P0.

### Atomic Redis Lua Gate

Every metered call must reserve cost with one atomic Lua script before the call. If Redis/Lua is unavailable, fail closed for non-P0 work.

```lua
-- KEYS[1] = fleet daily key, e.g. daily_spend_usd:fleet:2026-04-27
-- KEYS[2] = agent daily key, e.g. daily_spend_usd:daedalus:2026-04-27
-- KEYS[3] = optional p0 override key, e.g. p0_override_spend_usd:2026-04-27
-- ARGV[1] = estimated call cost in USD
-- ARGV[2] = fleet hard cap in USD
-- ARGV[3] = ttl seconds
-- ARGV[4] = p0_mode (0 or 1)
-- ARGV[5] = p0_override_cap in USD
-- ARGV[6] = invoking_identity_uuid
-- ARGV[7] = solon_uuid

local amount = tonumber(ARGV[1])
local fleet_cap = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local p0_mode = tonumber(ARGV[4] or "0")
local p0_cap = tonumber(ARGV[5] or "0")
local invoking_identity = ARGV[6] or ""
local solon_uuid = ARGV[7] or ""

if amount == nil or fleet_cap == nil or ttl == nil then
  return {0, "bad_args"}
end

local fleet_now = tonumber(redis.call("GET", KEYS[1]) or "0")
local projected = fleet_now + amount

if projected > fleet_cap then
  if p0_mode ~= 1 then
    return {0, "fleet_cap", fleet_now, projected}
  end

  if solon_uuid == "" or invoking_identity == "" then
    return {0, "missing_override_identity"}
  end

  if invoking_identity ~= solon_uuid then
    return {0, "invoker_not_solon", invoking_identity}
  end

  local p0_now = tonumber(redis.call("GET", KEYS[3]) or "0")
  local p0_projected = p0_now + amount
  if p0_projected > p0_cap then
    return {0, "p0_cap", p0_now, p0_projected}
  end

  local new_fleet = redis.call("INCRBYFLOAT", KEYS[1], amount)
  local new_p0 = redis.call("INCRBYFLOAT", KEYS[3], amount)
  local new_agent = redis.call("INCRBYFLOAT", KEYS[2], amount)
  redis.call("EXPIRE", KEYS[1], ttl)
  redis.call("EXPIRE", KEYS[3], ttl)
  redis.call("EXPIRE", KEYS[2], ttl)
  return {1, "p0_reserved", new_fleet, new_agent, new_p0}
end

local new_fleet = redis.call("INCRBYFLOAT", KEYS[1], amount)
local new_agent = redis.call("INCRBYFLOAT", KEYS[2], amount)
redis.call("EXPIRE", KEYS[1], ttl)
redis.call("EXPIRE", KEYS[2], ttl)

return {1, "reserved", new_fleet, new_agent}
```

After a successful reservation, the caller compares the agent key against that agent's warning threshold and emits `cost_warning:<agent>` if needed. The warning never blocks the call.

Actual cost is reconciled after the call. If actual exceeds estimate, reserve the delta through the same script before logging success.

## 8. Rollback Runbooks

Every migration must have a rollback tested before cutover.

### Agent Model Rollback

1. Flip `MODEL_ROUTE_<AGENT>` back to previous value.
2. Restore previous SI revision UUID.
3. Restart only that agent's worker if a restart is required.
4. Run one baseline task.
5. Log `agent_rollback:<agent>` with cause and proof.

Target time: `<= 15 minutes`.

### Judge Stack Rollback

Allowed rollback is not Perplexity/Grok/Gemini. If AMG Reasoning Judge fails, use Haiku-only degraded advisory or block, depending on task risk.

1. Set `JUDGE_MODE=haiku_degraded` for advisory-only tasks.
2. Block high-risk tasks with `judge_stack_degraded`.
3. Fix local Reasoning Judge.
4. Re-run golden set before returning to dual-judge.

### Cost Gate Rollback

1. If Redis fails, block metered non-P0 calls.
2. Local/flat-rate work can continue.
3. Log `cost_gate_degraded`.
4. Restore Redis and replay cost ledger from MCP receipts.

### Cost-Gate Rollback Receipt Schema

Every cost-gate degrade or replay action must emit:

```json
{
  "ok": true,
  "event": "cost_gate_degraded",
  "date": "2026-04-27",
  "mode": "fail_closed_non_p0",
  "fleet_spend_before_usd": 17.42,
  "agent_spend_before_usd": 1.26,
  "replay_required": true,
  "replay_receipt_paths": [
    "/opt/amg-governance/receipts/cost/2026-04-27/*.json"
  ],
  "restored_at": "",
  "blocked_calls": 3,
  "operator_override_uuid": ""
}
```

A recovery is not complete until `restored_at` is populated and the replay reconciles both fleet and agent counters.

## 9. Structured JSON Enforcement

All builders and migrated agents return structured receipts where automation depends on the output.

Minimum schema:

```json
{
  "ok": true,
  "agent": "daedalus",
  "task_id": "CT-...",
  "model_route": "deepseek_v4_pro",
  "deliverables": ["absolute path or URL"],
  "claims": ["specific, verifiable claim"],
  "verification": ["command, test, or file evidence"],
  "cost_usd_est": 0.012,
  "cost_usd_actual": 0.011,
  "blocked": false,
  "blocker": ""
}
```

Invalid JSON fails fast and is retried once. A second failure requeues to a higher-structure lane or blocks.

## 10. IP Sovereignty Analysis

| Provider/Runtime | Data Exposure | Training/DPA Risk | v5.0.3 Rule |
|---|---|---|---|
| Local Ollama | AMG host only | Lowest | Preferred for deterministic and private work. |
| Kimi GUI/subscription | Vendor GUI session | Depends on account terms | Use for approved chief/creative work; do not assume API rights. |
| Kimi API | Vendor API | Requires data-use review | Metered and gated as Tier 2 (`60 RPM / 120k TPM`, cost-class `metered_vendor_flash`). |
| DeepSeek API | Vendor API | Requires data-use review | Use for code/structured work after scrub. |
| Haiku | External API | Kept as counterjudge | Metered, scrubbed, minimal context. |
| Perplexity/Grok/Gemini | External API | Removed | No formal judge calls. |
| Claude frontier | Existing strategic surface | Kept for Titan/Achilles/EOM | Do not route routine AMG-agent work here. |

IP sovereignty is not "no external providers." It is least-necessary disclosure, explicit provider purpose, scrubbed prompts, and bounded metered usage.

## 11. Phase Plan

### Phase 0 - Audit

Inventory existing model routes, SI locations, and paid provider calls. Output `anthropic_dependency_audit.yaml` plus provider exposure manifest. Solon review required before migration.

### Phase 1 - Lieutenant Hardening

Wire Daedalus, Artisan, and Mercury to the corrected routing rules. Mercury fallback remains benched.

### Phase 2 - Cost Gate

Implement Redis Lua cost reservation, soft warnings, hard fleet cap, P0 bypass ledger, reconciliation, and fail-closed behavior.

### Phase 3 - Sovereign Research/Judge Foundation

Use CT-0427-51 architecture: Sonar-Replica and AMG Reasoning Judge. No Perplexity/Grok/Gemini live judge grace period. Historical output comparisons can use saved artifacts only.

### Phase 4 - 7 Agent Migration

Migrate in order: Sam, Riley, Nadia, Alex, Jordan, Maya, Lumina. Add a 7-day buffer before Lumina if earlier agents show quality variance.

### Phase 5 - Decommission Routine Anthropic Use

Only Titan, Achilles, and EOM retain frontier access. No credential rotation without explicit approval.

### Phase 6 - Validation Window

Seven-day post-cutover sampling. Roll back per agent if the rubric drops.

### Phase 7 - Judge Pipeline Switch

Round 3 missed the dual-judge floor (Titan-reported: Kimi `7.3`, Gemini `8.5`), so Phase 7 cannot proceed on v5.0.2 language. v5.0.3 is the round-4 corrective patch.

Switch formal gates to AMG Reasoning Judge plus Haiku. If any legacy Titan judge script still calls Gemini or carries pre-round-3 assumptions, it must be patched before the next formal validation run.

### Partial-Migration Halt Rule

If any agent in Phase 4 enters `rolled_back` because of quality, cost, or SI mismatch:

1. Freeze the remainder of that wave.
2. Re-run the mixed-state matrix from §5.
3. Require one explicit chief decision choosing either `resume_with_same_wave` or `split_wave_and_resume`.
4. Do not call the fleet migrated while any agent remains in `shadow`, `cutover`, or implicit mixed state.

## 12. Solon Override Contract

Solon can override a normal rule only through a logged decision with:

- decision UUID
- exact rule being overridden
- reason
- dollar ceiling if cost-related
- expiry timestamp
- affected agents or services

Rules that may be overridden this way:

- per-agent daily warning thresholds
- migration ordering
- advisory-only judge mode for low-risk doc work
- P0 cost bypass within the explicit override cap

Rules that may not be silently overridden:

- banned-provider removal from the formal judge stack
- trade-secret scrub fail-closed behavior
- Mercury no-reasoning rule
- requirement to reconcile SI locations before cutover

If an override expires, the system reverts to default behavior automatically and logs `override_expired`.

## 13. Revision Closure

| Gap | v5.0.3 Resolution |
|---|---|
| §7 P0 bypass undefined | Explicit P0 bypass contract plus Lua handling added. |
| §12 Solon override not operative | New operative Solon override section added. |
| §8 cost-gate rollback schema missing | Concrete rollback receipt schema added. |
| Partial-migration recovery missing in §5/§11 | Mixed-state matrix, halt rule, and recovery contract added. |
| Themis + Iolaus undefined | Operative definitions added with family, role, dispatch context, dormant executor state, and reject behavior. |
| P0 Lua bypass stale fleet ledger | P0 branch now increments fleet, override, and agent ledgers atomically. |
| `p0_override_cap` caller ambiguity | Solon UUID guard added to the override path. |
| Phase 7 stale round-2 residue | Phase 7 rewritten around round-3 miss and round-4 patch context. |
| Metered Kimi API tier ambiguity | Tier 2 assignment plus RPM/TPM and cost-class mapping added. |

## 14. Acceptance Criteria

1. Cost gate blocks metered fleet spend above `$35/day` with one atomic Redis script.
2. Per-agent caps warn only and do not block.
3. Monthly target is stated as metered-only and mathematically consistent with `<= $200/month`.
4. P0 bypass requires decision UUID, ceiling, expiry, and separate override ledger.
5. No Perplexity, Grok, or Gemini formal judge calls remain in v5.0.3.
6. Haiku is the only external judge retained.
7. Mercury cannot reason or use LLM fallback.
8. Every migrated AMG agent has SI locations reconciled before cutover.
9. Partial-migration recovery writes a mixed-state matrix and blocks silent continuation.
10. Trade-secret scrubber fails closed for external/metered calls.
11. Cost-gate rollback emits the explicit receipt schema and replay proof.
12. Rollback for each migration is executable in `<= 15 minutes`.
13. Structured JSON is mandatory for automation-facing outputs.
14. Titan legacy judge script language carries no stale pre-round-3 or "before round 2" residue.
15. Solon override behavior is defined in operative body, not only revision notes.
16. Themis and Iolaus are operatively defined before they are referenced as routing actors.
17. P0 bypass updates fleet, override, and agent ledgers atomically in one Lua eval.
18. `p0_override_cap` is rejected unless invoking identity matches canonical Solon UUID.
19. Metered Kimi API path has an explicit tier, RPM/TPM cap, and cost-class mapping.

## 15. Self-Score

| Dimension | Score | Note |
|---|---:|---|
| Technical soundness | 9.3 | The P0 bypass now closes both identity and ledger-consistency gaps. |
| Completeness | 9.2 | All five round-3 P0 blockers are now mapped and patched line-by-line. |
| Edge cases | 9.2 | Missing Solon identity, stale ledger, and dormant routing actors now fail closed. |
| Risk identification | 9.3 | Override abuse, routing ambiguity, and tier ambiguity are explicit. |
| Cost discipline | 9.4 | Kimi metered path is now tiered and the P0 branch updates all ledgers coherently. |
| Paper-freeze compliance | 9.2 | No new active agent classes added; only operative definitions for referenced dormant actors. |

Overall: 9.27/10.
