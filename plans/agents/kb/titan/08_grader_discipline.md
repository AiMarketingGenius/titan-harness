# Titan KB — 08 Grader Discipline (premium-escalation rules)

**P10 PERMANENT 2026-04-17 — Solon correction after session where premium was used on a Gemini Flash skip without justification.** Hard-coded into `lib/dual_grader.py` + session-bootstrap-loaded via CLAUDE.md §18.4. Cannot be forgotten across sessions.

---

## The rule in one line

**Default is low-tier (Gemini 2.5 Flash + Grok 4.1 Fast). Premium tier (Gemini 2.5 Pro / Grok 4) is ONLY authorized under three specific conditions. SKIP ≠ disagreement. Never auto-promote to premium on a skip.**

## Default tier: `amg_growth` (Gemini 2.5 Flash + Grok 4.1 Fast)

- **Cost:** ~$0.004 per artifact (both low-tier graders combined)
- **Quality:** sufficient for 99% of artifact-grading work in AMG — KB docs, code, configs, client deliverables, runbooks
- **Floor:** 9.3/10 overall from BOTH graders independently

## Premium tier: `amg_pro` (Gemini 2.5 Pro / Grok 4)

- **Cost:** ~$0.04 per artifact (10× low-tier)
- **Daily cap:** shared budget with low-tier; premium burns budget faster
- **Authorization gate:** the `dual_grader.py` wrapper AUTO-DOWNGRADES `--scope-tier amg_pro` to `amg_growth` unless ONE of these three conditions is met:

### Condition A — Architecture-critical context
Auto-detected via keyword match in `--context`. Current keywords:
`contract`, `legal`, `security`, `pen-test`, `soc2`, `soc 2`, `payment`, `msa`, `nda`, `sow`, `partnership`

If none match, the wrapper downgrades + logs a warning. Expand the keyword list in `dual_grader.py` `ARCHITECTURE_CRITICAL_KEYWORDS` if new categories warrant auto-premium.

### Condition B — Explicit override with justification
Pass `--force-premium --reason "<justification>"` at the CLI. Both flags required; the wrapper refuses `--force-premium` alone.

**Every override logs to stderr + must include a specific written justification.** Justifications like "just to double-check" or "higher quality needed" are insufficient — specify the actual risk being addressed (e.g., "signing-this-tomorrow contract; need independent arch review").

### Condition C — Solon-explicit request in the task
If Solon's directive explicitly says "use premium" / "double-check with Pro" / "architecture-critical review" — Titan passes `--force-premium --reason "solon-explicit-directive-${ticket-id}"` and proceeds. Log the request quote in MCP decision.

## What to do when Gemini Flash SKIPS (policy filter, API hiccup, timeout)

The `_gemini_grade_with_retry` wrapper handles this automatically:

1. **Retry Round 1** (3s backoff) — transient API issues often resolve
2. **Retry Round 2** (9s backoff)
3. **Retry Round 3** (27s backoff)
4. **Content-transformation fallback** — if content >4000 chars, chunk in halves, grade each chunk, average
5. **Grok-only grade** — if all retries + transformation exhausted, mark as `pass_single_grader` or `revise_single_grader`

**THE WRAPPER DOES NOT ESCALATE TO PREMIUM ON SKIP.** That was the 2026-04-17 violation — SKIP is grader-stack failure, not grader disagreement, and doesn't justify burning premium budget.

## What to do when scores DISAGREE

Low-tier disagreement (e.g., Flash 7.2 + Grok 9.5) within non-premium tier:

1. **Disagreement threshold:** 1.5 points. Below threshold = trust the more conservative grader.
2. **Above threshold + architecture-critical:** consider premium escalation (use `--force-premium --reason "low-tier-disagreement-${delta}-pts"`)
3. **Above threshold + NOT architecture-critical:** trust the more conservative score, revise artifact, re-grade on low tier
4. The wrapper logs a `[dual-grader] INFO:` message when disagreement exceeds threshold to surface this choice — it does NOT auto-escalate.

## The pure-Grok single-grader path

When Gemini repeatedly skips on KB-documentation inputs (common for files that enumerate banned terms, which trigger safety filters), the wrapper returns `pass_single_grader` / `revise_single_grader`. This is NOT a failed grade — it's a tagged grade that surfaces the limitation.

When Titan ships on single-grader-only evidence:
1. Log explicitly in MCP `log_decision` — "shipped on Grok-only grade N.N; Gemini Flash skipped N retries + chunk-fallback due to content-type"
2. Include Grok's reasoning verbatim in the decision log (it's the sole validator signal)
3. Do NOT use this as a workaround to skip grading — it's a fallback for legitimate skips, not an escape hatch

## Cost discipline review

The daily grader budget is bounded:
- Gemini daily cap: $5
- Grok daily cap: $3
- Total kill-switch: $10

At default tier (~$0.004/artifact), budget supports ~2500 artifact grades per day. Plenty.
At premium tier (~$0.04/artifact), budget collapses to ~250 grades per day. Burns fast.

One premium escalation is fine. A dozen unnecessary premium escalations kills the grader budget and forces Titan to fall back to unvalidated shipping.

## Logged violations + corrections

| Date | Violation | Cost | Correction |
|---|---|---|---|
| 2026-04-17 | Gemini Flash skipped Lumina KB (policy filter on banned-term enumeration); Titan escalated to Gemini Pro without retries or justification | ~$0.04 | This KB file + `dual_grader.py` gate |

## Self-check before requesting premium tier

Before passing `--force-premium`:
1. Is this artifact signing-tomorrow or legal/security critical?
2. Have I already tried default tier 2 rounds?
3. Is my `--reason` specific and defensible?
4. Would Solon approve this spend if he saw the decision log?

4/4 → proceed with premium. Any NO → stay on default tier, accept what the low-tier graders return.

## Rule change log

- **2026-04-17 v1:** initial rule (post-Solon-correction). Hard-coded in `lib/dual_grader.py`, documented here.
