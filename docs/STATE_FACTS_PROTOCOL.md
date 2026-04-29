# STATE_FACTS PROTOCOL v1.0
## Mandatory Anti-Drift Doctrine — All Future Dispatches

- **Status:** ACTIVE + NON-BYPASSABLE
- **Effective:** 2026-04-29 (CT-0429-19, EOM founder-override)
- **Scope:** every dispatch from EOM, Solon, Achilles, Titan, or any other source that asserts AMG VPS state
- **Closes:** the failure class that produced DIR-010 v1 + DIR-011 v1 hallucinated CONTEXT blocks

---

## RULE 1 — Single canonical ground-truth file

`STATE_FACTS.md` is the canonical AMG VPS state-of-the-world file.

- **VPS canonical path:** `/opt/amg-titan/STATE_FACTS.md`
- **Mac harness mirror (3-leg sync):** `docs/STATE_FACTS.md` in `~/titan-harness/`
- **Mac-side equivalent for Achilles harness:** `STATE_FACTS_MAC.md` at `/Users/solonzafiropoulos1/achilles-harness/STATE_FACTS_MAC.md` (built + maintained by Achilles, not Titan)
- **Refresh cadence:** at the start of every multi-phase dispatch + after any major build or service-state change
- **Generator:** Titan owns VPS file; Achilles owns Mac file
- **Prior version preserved for diff:** previous file moved to `STATE_FACTS.md.bak` on every regeneration

## RULE 2 — Every dispatch opens with a STATE_CHECK

Every dispatch from any source must include a STATE_CHECK section as its first executable step.

STATE_CHECK reads `STATE_FACTS.md` and verifies that every state assertion in the dispatch's CONTEXT block matches the corresponding STATE_FACTS section. Mismatch = **halt** + `flag_blocker` with tag `context_state_mismatch` + halt.

The STATE_CHECK is mechanical, not discretionary. Titan / Achilles / any executor follows the rule even when the dispatch source is trusted (EOM, Solon, founder-override).

## RULE 3 — CONTEXT blocks may not assert state without citing STATE_FACTS sections

**BANNED pattern:**

> "MP-1 complete, voice AI bridge at /opt/amg-titan/services/voice-ai-bridge/, Atlas chassis shipped via commit 6557abd."

**REQUIRED pattern:**

> "Per `STATE_FACTS.md §1`, MP-1 is at <pct>%. Per `STATE_FACTS.md §3`, voice AI bridge <exists | absent>. Per `STATE_FACTS.md §2`, commit <hash> <present | absent>."

The reference is always section-numbered + verbatim. Composers cannot invent state — they cite it.

## RULE 4 — Achilles harness gets equivalent rule wired in

Mac-side: `/Users/solonzafiropoulos1/achilles-harness/STATE_FACTS_MAC.md` is the Mac-side single source of truth (Codex CLI / Hammerspoon / Claude.app state, Mac-only services, harness mirrors).

Achilles' preflight checks `STATE_FACTS_MAC.md` before any phase fires, mirroring Titan's `STATE_FACTS.md` discipline.

This closes the gap that allowed DIR-010 v1 to bulldoze through with hallucinated Mac-side claims.

## RULE 5 — Three-judge gate runs AFTER STATE_FACTS verification

Three-judge gate (or any quality gate, including the bootstrap-mode single-judge variant) cannot pass if STATE_CHECK fails. Verification order:

1. STATE_CHECK against `STATE_FACTS.md` — pass / fail / mismatch list
2. Three-judge gate (or bootstrap single-judge) — composite score against rubric
3. Solon explicit gate (only for items on the Hard Limits list)

A dispatch that fails STATE_CHECK is short-circuited before judges spend any cycles on it.

## RULE 6 — Refresh on demand or on cadence

`STATE_FACTS.md` is regenerated when:

- Solon issues the command **"refresh state facts"**
- An EOM directive includes a `refresh_state_facts` tag
- Titan completes a build that materially changes any of the 7 fact categories (services, doctrines, agents, MCP server, factory infra, MP-1, commits)
- 24h cadence has elapsed since last regeneration

Regeneration always uses the `bin/refresh-state-facts.sh` helper (to be built as part of the doctrine rollout) so the verbatim shell output format is consistent. Manual hand-edits are banned — drift the file = drift the entire doctrine.

## RULE 7 — Verbatim shell output, not summaries

Every fact section of `STATE_FACTS.md` follows this format:

```
+++cmd: <exact command>
<verbatim shell output — newlines preserved, ANSI stripped>
```

then a single-line **INTERPRETATION:** that names the relevant DIR-011-style assertion the section confirms or refutes.

Summaries belong in dispatches and reports. `STATE_FACTS.md` is grep-fodder for future automation.

## RULE 8 — Hard halt on detected drift in dispatch authoring

If Titan or Achilles is composing a dispatch and notices that a state claim in the draft contradicts the current `STATE_FACTS.md`, the composer MUST stop, regenerate `STATE_FACTS.md`, then either rewrite the dispatch to cite the refreshed truth or escalate the conflict to Solon. Drift caught at the authoring stage costs minutes; drift caught at execution costs a sprint.

## RULE 9 — Memory-rule alignment

This protocol is the mechanical complement to the existing memory rule `feedback_find_before_placeholder.md` ("real thing beats generic"). Where that rule covers files Solon mentions in chat, this rule covers state Titan or EOM mentions in dispatches. Same root principle: **no fabrication, only citation.**

## RULE 10 — Auto-mirror under §17 (Hercules Triangle)

Every regeneration of `STATE_FACTS.md` is committed under §17 Auto-Harness + Auto-Mirror — Mac → VPS bare → GitHub → MCP — so the canonical file is replicated in three legs by the existing post-receive hook chain. The VPS canonical path is populated either via the post-receive hook copying the harness file into `/opt/amg-titan/` or via a symlink (decision deferred to DDF-MIN dispatch).

---

## Tag

`state_facts_protocol_v1_active`
