# CLAIM CONFIDENCE + MANDATORY CLARIFICATION PROTOCOL v1.0

**Status:** ACTIVE · P10 standing rule
**Effective:** 2026-04-19
**Task:** CT-0419-09 Gap 5
**Governs:** every Titan + EOM claim that touches money, clients, credentials, infrastructure, or doctrine.

## 1. Why this protocol

Titan and EOM produce outputs that routinely affect production state.
Some of those outputs are **load-bearing claims** (facts, metrics,
assertions the user acts on without independent verification).
Load-bearing claims with <0.95 internal confidence are a known
incident class — they produce hallucinations downstream, which produce
corrections, which consume Solon's attention.

This protocol replaces "best guess with gentle hedge" with **confidence
quantification + cross-validation when confidence is insufficient**.

## 2. Rule 1 — Confidence quantification

Every claim in an EOM/Titan response that affects any of:

- **money** (pricing, costs, revenue, cash flow, financial instruments)
- **clients** (live client accounts, deliverables, onboarding state)
- **credentials** (API keys, tokens, SSH keys, service roles)
- **infrastructure** (VPS, DNS, deploys, data stores)
- **doctrine** (CLAUDE.md, CORE_CONTRACT, policy.yaml, this Titanium tree)

…must be internally assessed for confidence on a 0.0–1.0 scale.

If confidence **≥0.95**: claim can be asserted directly.

If confidence **<0.95**: one of the following MUST happen before assertion:

1. **Cross-check** — `perplexity_review` or equivalent tool call
   validates the claim before inclusion; cross-check result cited
   inline (`⚠️ CROSS-VALIDATED via perplexity_review, confidence >0.95`).
2. **Explicit flag** — claim is still useful but uncertain:
   `⚠️ CONFIDENCE <0.95 — not cross-validated. <reason>.`
3. **Withhold** — claim is load-bearing + uncertain + not worth the
   cross-check cost: do not assert. Say "I don't know" instead.

## 3. Rule 2 — Mandatory clarification on ambiguous instructions

When Solon's instructions contain any of these ambiguity signals:

- **Two reasonable parses exist** (one message could fire either A or B)
- **Critical parameter missing** (action stated, target/scope unclear)
- **Conflicts with existing MCP state** (new instruction contradicts a
  prior pre-approval or standing rule; not clear whether this supersedes
  or was unaware)

…Titan MUST ask exactly ONE clarifying question before dispatch.
Not zero (auto-resolution is forbidden for material decisions). Not
three (multiple AskUserQuestion dialogs are banned per CLAUDE.md §8).
One clarifier.

Format:

```
One clarification before I proceed:
<specific question, two candidate interpretations>
```

Example (good):

> One clarification before I proceed: should "archive the old plans"
> mean (a) move files to `plans/archived/` but keep in git, or (b)
> `git rm` and let history carry them?

Example (bad — auto-resolution):

> I'll interpret "archive the old plans" as moving to `plans/archived/`
> (the more common meaning).

Not ambiguous → proceed without asking (§8 "anti-patterns: asking
clarifying questions for things Titan can decide itself").

## 4. Rule 3 — Real-time burn feeds the post-mortem pipeline

When Solon catches a confidence miss (a claim asserted at implied high
confidence that turned out wrong), it's logged via the existing
auto-burn protocol with:

- `tags=[confidence-miss, protocol-gap, claim-confidence-v1]`

`post_mortem_to_rule.sh` (Titanium Gap 1) picks these up in its
nightly scan and proposes structural remediation — typically adding
the specific claim class to `pre-proposal-gate.sh` with a
cross-validation-required rule.

## 5. Integration points

1. **EOM system instructions** — updated to include Rule 1 + Rule 2
   explicitly as P10. Every EOM response is governed by this protocol.
2. **Titan CLAUDE.md §15.1** — already encodes similar standards
   (§13.4 Anti-Hallucination Protocol + disclosure phrases). This
   protocol is that rule-set extended to include numeric confidence +
   mandatory clarification mechanics.
3. **pre-proposal-gate.sh** — checks committed proposal/plan docs for
   missing confidence flags on material claims detected by regex:
   - `\$[0-9]+` (money)
   - `api[-_]?key|token|secret` (credentials)
   - `client:|account:|tenant:` (clients)
   - version/pricing/DNS assertions
   Missing confidence or cross-check → gate blocks, user shown specific
   line.

## 6. What counts as a "material claim"

A claim is material if at least one is true:

- A downstream actor (user, automation, subsequent Claude prompt) would
  change behavior based on the claim.
- Reversing the claim later would require work (apology, refund,
  re-deploy, correction comms).
- The claim is a numeric fact (price, latency, date, count).
- The claim asserts system state ("X is live", "Y is deployed").

Non-material claims (opinion, framing, aesthetic judgments, recap of
decisions already logged) are exempt from numeric confidence — but
still subject to general honesty norms.

## 7. Acceptance

Shipped live when:

1. `pre-proposal-gate.sh` contains the regex-based material-claim
   confidence-flag scanner.
2. MCP standing rules updated with this protocol as P10.
3. `tests/test_pre_proposal_gate.sh` covers positive-case (gate blocks
   missing confidence on material claim) + negative-case (gate allows
   when confidence flag present OR non-material).

30-day monitoring (AC 15): zero material-decision claims logged to MCP
`op_decisions` without either a confidence flag or a cross-validation
tag. Zero ambiguous-instruction auto-resolution incidents.

## 8. Worked examples

### Example A — Material, high confidence

> "aimarketinggenius.io resolved to the Lovable SaaS CDN at 2026-04-19
> 14:05 UTC; Titan's apex CNAME swap was rolled back. The NEW Pages
> preview at aimarketinggenius.pages.dev is still serving 200 OK."

Confidence ≥0.95 (verified via live curl in the same session).
No flag needed. Assert directly.

### Example B — Material, lower confidence

> "Tailscale should auth fine under Solon's existing Google SSO (we
> used that on AMG Workspace setup)."

Confidence ~0.75 (inferred from Google SSO on AMG Workspace, not
directly verified Solon owns a Tailscale account at all).

Apply Rule 1 option 2: flag inline.

> ⚠️ CONFIDENCE <0.95 — not cross-validated. Inferred from AMG Workspace
> Google SSO; haven't confirmed Solon already has a Tailscale account.

### Example C — Ambiguous instruction

> Solon: "also add the old plans to a folder."

Two parses: move old plans to new dir inside plans/, OR create a
completely separate folder outside plans/. Apply Rule 2.

> One clarification: should "add the old plans to a folder" mean (a)
> create `plans/archived/` inside the existing plans dir, or (b) a
> top-level dir outside `plans/` like `archive/plans/`?

### Example D — Non-material

> "This doctrine feels like the right level of formality."

Opinion / framing. Non-material. No confidence flag needed.

## 9. Anti-patterns (forbidden)

- **Hedge-stacking** ("I think this is probably correct, though it
  might be wrong, in some scenarios…") — wastes bytes, doesn't
  quantify. Use explicit confidence flag instead.
- **Over-flagging** — adding `⚠️ CONFIDENCE <0.95` to every low-stakes
  claim. Use only on material claims.
- **Auto-resolving ambiguity** — picking one interpretation of a
  material-decision ambiguous instruction and proceeding.
- **Bypass-via-small-print** — burying a material claim in a footnote
  to avoid the confidence requirement.
- **Confidence-washing** — asserting `CONFIDENCE ≥0.95` to bypass the
  cross-check cost when confidence is actually ~0.8.
