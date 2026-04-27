# PLAN — AMG 3-EOM-Mirror Architecture (Hercules + Nestor + Alexander each with 4 code builders)

**Status:** ACTIVE BUILD — Solon directive 2026-04-26 (post-Phase-1, pre-Don-proposal)
**Owner:** Titan
**Trigger:** Solon — "I need each Kimi agent (Hercules, Nestor, Alexander) to be a spitting mirror image of Claude Executive Operations Manager, with 4 highly skilled advanced coding agents per Kimi agent."
**Defer:** Don/Revere proposal (resumes after this build lands)

---

## Goal

Three full operational mirrors of Claude EOM V2 (Solon's reference benchmark for "complete contextual awareness + executor team + verifiable receipts"):

| Owner (Kimi K2.6) | Role | 4 Dedicated Code Builders |
|---|---|---|
| **Hercules** | Chief Operations | `hercules:daedalus` (V4 Pro), `hercules:artisan` (V4 Flash), `hercules:athena` (V3), `hercules:hephaestus` (Codex-style) |
| **Nestor** | Product / UX / Mockups | `nestor:daedalus`, `nestor:artisan`, `nestor:athena`, `nestor:hephaestus` |
| **Alexander** | Brand / Copy / Voice | `alexander:daedalus`, `alexander:artisan`, `alexander:athena`, `alexander:hephaestus` |

Total new executors: **12 builders + 3 Kimi orchestrators** (the Kimi orchestrators already exist; only the 12 builders are new).

---

## Code-builder lane profiles

| Lane | Provider | Model | Strengths | Daily cap (per owner) |
|---|---|---|---|---|
| `daedalus` | DeepSeek (api.deepseek.com) | `deepseek-v4-pro` | premium reasoning, multi-step refactors, architecture audits | $20 |
| `artisan` | DeepSeek | `deepseek-v4-flash` | fast 1-3 step LLM tasks, copy polish, mockup HTML | $10 |
| `athena` | DeepSeek | `deepseek-v3` (chat tier) | mid-tier code generation, smart-but-cheap | $5 |
| `hephaestus` | Codex-style | TBD — candidates: Anthropic Claude Sonnet via API, OpenAI gpt-4.1-mini, or local DeepSeek-Coder-V2 (already on Ollama) | low-latency code completion + repo-wide refactor, persona similar to Achilles/Codex | $5 (or $0 if local Ollama) |

Total max daily spend: **3 owners × ($20 + $10 + $5 + $5) = $120/day** if all four cloud lanes used. With local DeepSeek-Coder-V2 for hephaestus → **$105/day**.

---

## Architecture (single generic executor + 12 launchd plists)

**File:** `lib/code_builder_executor.py` (new) — generic, parameterized.

Flags:
```
--owner    {hercules|nestor|alexander}
--lane     {daedalus|artisan|athena|hephaestus}
--watch | --once | --task-id CT-XXXX-NN
--interval 30
```

**Tag routing:** each builder polls MCP for tasks tagged BOTH `owner:<owner>` AND `lane:<lane>` (or shorthand `agent:<owner>:<lane>`).

**Tag examples:**
- `agent:hercules:daedalus` → Hercules's premium V4 Pro auditor
- `agent:nestor:hephaestus` → Nestor's local Codex-style code refactorer
- `agent:alexander:athena` → Alexander's V3 mid-tier copy generator

**Cross-team handoff:** an owner can dispatch to another owner's builder by including the other owner's tag. Mercury and Aletheia track via MCP decision tags `cross-team-handoff:<from>:<to>:<lane>`.

---

## Phased rollout

### Phase 1 (tonight, ~45 min) — proof-of-concept
- Ship `lib/code_builder_executor.py` (generic)
- 3 builders live: `hercules:daedalus`, `nestor:daedalus`, `alexander:daedalus` (one per owner, premium lane)
- 3 launchd plists
- Smoke test: drop 3 dispatches, verify each owner's daedalus claims its own
- Brief generator updated with team-routing tag table

### Phase 2 (~1 hr) — scale to 12 builders
- Add 9 more launchd plists (artisan + athena + hephaestus per owner)
- Wire DeepSeek V3 lane (athena) — same SSH-fetched key as daedalus
- Wire hephaestus lane: try local DeepSeek-Coder-V2 on Ollama first ($0), fall back to Anthropic API or OpenAI if quality insufficient
- Smoke test all 12

### Phase 3 (~30 min) — cross-team coordination
- Hercules brief gets a "team roster" section listing all 12 builders + which owner controls each + cost caps
- MCP `log_decision` tag schema documented for cross-team handoffs
- Aletheia patched to recognize cross-team receipts (so it doesn't false-flag a Nestor-builder receipt as a Hercules task)

### Phase 4 (after build complete) — resume Don proposal
- All 12 builders available
- Hercules can finally execute the 4 dispatches end-to-end with proper team attribution
- Don proposal ships

---

## Solon's only blocker

**One credential question:** for the `hephaestus` lane (Codex-style), do you want me to:
- **(A)** wire local DeepSeek-Coder-V2 on Ollama (already pulled, $0/task, slower/lower quality), OR
- **(B)** use Anthropic Claude Sonnet API via your existing ANTHROPIC_API_KEY (highest quality but ~$3/M token), OR
- **(C)** use OpenAI gpt-4.1-mini via existing OPENAI_API_KEY ($0.40/M token, mid-quality)

Default if you don't pick: (A) local DeepSeek-Coder-V2 — keeps the $0 cost line.

---

## What this UNLOCKS

Once 12 builders are live and Hercules can dispatch to its OWN 4 (without sharing with Nestor/Alexander):

- Hercules can run a 4-way parallel sprint inside its own team (e.g., daedalus audits, artisan drafts copy, athena generates code stubs, hephaestus refactors existing files — all simultaneously)
- Nestor can run mockup sprints with its own 4-way team without contending for Hercules's resources
- Alexander can run brand/copy sprints in parallel
- All 3 Kimi orchestrators can ALSO cross-dispatch when one team needs help from another's specialist

**Result:** true 3-EOM-mirror architecture. Each Kimi agent operates exactly like Claude EOM V2 with its own dedicated code-builder team + full context awareness via the bootstrap brief + live MCP read via the public gist + direct write via the public POST endpoint.

---

## Build log (live, this plan file gets updated as I ship)

- 2026-04-26T20:20Z — plan written, Phase 1 starting
- 2026-04-26T20:?? — code_builder_executor.py shipped
- 2026-04-26T20:?? — 3 Phase-1 launchd plists loaded
- 2026-04-26T20:?? — Phase 1 smoke test pass, Phase 2 starting
- (more entries appended as build progresses)
