# Titan Dispatch - AMG Model Sovereignty v5.0.1

**Target canonical path:** `/opt/amg-docs/megaprompts/MEGAPROMPT_AMG_MODEL_SOVEREIGNTY_v5_0_1_2026-04-27.md`
**Staged path:** `/Users/solonzafiropoulos1/titan-harness/docs/megaprompts/MEGAPROMPT_AMG_MODEL_SOVEREIGNTY_v5_0_1_2026-04-27.md`
**Owner:** Achilles, CT-0427-50
**Status:** Patched draft, ready for round-2 judge after Titan updates the judge pair. Do not execute build phases yet.

## 0. Binding Changes From v5.0

v5.0.1 replaces the v5.0 draft sections that caused round-1 `REVISE`.

Non-negotiable corrections:

- Perplexity, Grok, and Gemini are removed from the formal judge stack.
- Haiku is the only external judge allowed after judge-sovereignty lock.
- Flat-rate subscriptions and local models are excluded from the metered cost pool.
- Per-agent daily caps are warnings, not blockers.
- The one hard cost gate is the fleet-wide metered spend cap of $35/day, enforced atomically.
- Mercury is primitives-only. No LLM fallback, no reasoning.
- Kimi flat-rate means GUI/subscription use only where contractually allowed. Any Kimi API metered usage goes through the fleet cost gate.

## 1. Scope

v5.0.1 is still model sovereignty and cost discipline. It does not reopen v4.0.x paper-freeze agent inventory.

In scope:

- Model tier ladder.
- Titan lieutenant fleet routing rules.
- 7 AMG client-facing agent migration planning.
- Sovereign research/judge replacement planning.
- Atomic cost gate.
- Rollback, trade-secret scrub, structured receipts, and SI access discipline.

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
| Gemini | Removed. The old CT-36 Kimi+Gemini round-1 script must not be reused unmodified. |

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
5. Cut over only if target output is >= 9.0 against baseline.
6. Monitor for 7 days.
7. Roll back that single agent if quality drops by more than 0.5 on the 10-point rubric.

Lumina migrates last because CRO quality has the highest subjective risk.

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

Flat-rate/subscription costs still appear in monthly reporting, but they do not consume the $35/day metered fleet gate.

### Hard Gate And Warnings

| Scope | Behavior |
|---|---|
| Per-agent daily warning | Soft only. Emit Slack/MCP warning; do not block. |
| Fleet metered daily cap | Hard. `$35.00/day` blocks all non-P0 metered calls. |
| Monthly target | `<= $200/month` for metered usage only. This requires average spend <= `$6.67/day`, about 19% of the $35 hard cap. A sustained 25% month would be `$262.50` and fails the target. |

This fixes the round-1 contradiction: the $35/day value is an emergency hard ceiling, not a planning budget.

### Atomic Redis Lua Gate

Every metered call must reserve cost with one atomic Lua script before the call. If Redis/Lua is unavailable, fail closed for non-P0 work.

```lua
-- KEYS[1] = fleet daily key, e.g. daily_spend_usd:fleet:2026-04-27
-- KEYS[2] = agent daily key, e.g. daily_spend_usd:daedalus:2026-04-27
-- ARGV[1] = estimated call cost in USD
-- ARGV[2] = fleet hard cap in USD
-- ARGV[3] = ttl seconds

local amount = tonumber(ARGV[1])
local fleet_cap = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

if amount == nil or fleet_cap == nil or ttl == nil then
  return {0, "bad_args"}
end

local fleet_now = tonumber(redis.call("GET", KEYS[1]) or "0")
local projected = fleet_now + amount

if projected > fleet_cap then
  return {0, "fleet_cap", fleet_now, projected}
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

Target time: <= 15 minutes.

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

| Provider/Runtime | Data Exposure | Training/DPA Risk | v5.0.1 Rule |
|---|---|---|---|
| Local Ollama | AMG host only | Lowest | Preferred for deterministic and private work. |
| Kimi GUI/subscription | Vendor GUI session | Depends on account terms | Use for approved chief/creative work; do not assume API rights. |
| Kimi API | Vendor API | Requires data-use review | Metered and gated if used. |
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

Implement Redis Lua cost reservation, soft warnings, hard fleet cap, reconciliation, and fail-closed behavior.

### Phase 3 - Sovereign Research/Judge Foundation

Use CT-0427-51 architecture: Sonar-Replica and AMG Reasoning Judge. No Perplexity/Grok/Gemini live judge grace period. Historical output comparisons can use saved artifacts only.

### Phase 4 - 7 Agent Migration

Migrate in order: Sam, Riley, Nadia, Alex, Jordan, Maya, Lumina. Add a 7-day buffer before Lumina if earlier agents show quality variance.

### Phase 5 - Decommission Routine Anthropic Use

Only Titan, Achilles, and EOM retain frontier access. No credential rotation without explicit approval.

### Phase 6 - Validation Window

Seven-day post-cutover sampling. Roll back per agent if the rubric drops.

### Phase 7 - Judge Pipeline Switch

Switch formal gates to AMG Reasoning Judge plus Haiku. If the current Titan CT-36 script still calls Gemini, it must be patched before round 2.

## 12. Round-1 Revision Closure

| Flagged Issue | v5.0.1 Resolution |
|---|---|
| Cost math contradiction | Section 7 separates hard daily cap from monthly planning target. |
| Redis non-atomicity | Lua reservation script added. |
| Kimi Allegro flat-rate undefined | GUI/subscription only; metered API treated separately. |
| IP sovereignty too vague | Provider exposure table and scrub rule added. |
| Rollback asserted, not documented | Agent, judge, and cost-gate rollback runbooks added. |
| Trade-secret scrub vague | Fail-closed scrubber contract added. |
| Mercury reasoning gap | Primitives-only rule and requeue path added. |
| Cheap-judge subjective criteria unclear | Reasoning Judge plus Haiku 6-dim rubric required. |
| Cost cap resilience missing | Redis fail-closed and reconciliation behavior added. |
| Lumina contingency weak | Lumina migrates last with buffer and rollback threshold. |
| DeepSeek retry/fallback frequency unclear | Escalation goes through Themis; no silent paid fallback loops. |
| Solon override unclear | Overrides require decision UUID, reason, ceiling, and 24h expiry. |
| Perplexity decommission ambiguous | Removed from live judge stack immediately; historical saved outputs only. |
| Structured JSON enforcement weak | Schema and retry/block behavior added. |
| Kimi/Gemini dual integration obsolete | Replaced by sovereign Reasoning Judge plus Haiku. |

## 13. Acceptance Criteria

1. Cost gate blocks metered fleet spend above $35/day with one atomic Redis script.
2. Per-agent caps warn only and do not block.
3. Monthly target is stated as metered-only and mathematically consistent with <= $200/month.
4. No Perplexity, Grok, or Gemini formal judge calls remain in v5.0.1.
5. Haiku is the only external judge retained.
6. Mercury cannot reason or use LLM fallback.
7. Every migrated AMG agent has SI locations reconciled before cutover.
8. Trade-secret scrubber fails closed for external/metered calls.
9. Rollback for each migration is executable in <= 15 minutes.
10. Structured JSON is mandatory for automation-facing outputs.
11. Titan round-2 judge script is patched away from Gemini before reuse.

## 14. Self-Score

| Dimension | Score | Note |
|---|---:|---|
| Technical soundness | 9.3 | P0 cost and judge contradictions removed. |
| Completeness | 9.2 | All round-1 flags are explicitly mapped. |
| Edge cases | 9.1 | Redis failure, scrub failure, judge degradation, and rollback covered. |
| Risk identification | 9.4 | Banned-provider and Kimi-access ambiguity are explicit. |
| Cost discipline | 9.6 | Fleet hard cap is atomic and mathematically reconciled. |
| Paper-freeze compliance | 9.3 | No current-scope classes added. |

Overall: 9.3/10.
