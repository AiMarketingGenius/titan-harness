# IDEA BUILDER SCORECARD — Titan Steroids 5 Candidates

**Date:** 2026-04-18  
**Engines:** Perplexity Sonar Pro (via LiteLLM gateway) + Grok 4 Fast Reasoning (via xAI API)  
**Rubric:** Doc 02 6-dimension framework (adapted for idea-stage evaluation)  
**Binding gate:** merged overall ≥9.0 AND both engines individually ≥9.0 = PASS (per intake §gate rule)

---

## Summary

| # | Candidate | Sonar | Grok | Merged | Gate | Floor met by both ≥9? |
|---|---|---:|---:|---:|---|:---:|
| 1 | PROACTIVE_SCHEDULER | 8.45 | 8.83 | 8.58 | NEEDS-WORK | ✗ |
| 2 | SELF_IMPROVEMENT_LOOP | 7.75 | 7.50 | 7.67 | NEEDS-WORK | ✗ |
| 3 | OPPORTUNITY_RADAR | 6.25 | 8.00 | 7.03 | NEEDS-WORK | ✗ (large Δ) |
| 4 | PREDICTIVE_CLIENT_CARE | 8.05 | 9.33 | 8.40 | NEEDS-WORK | ✗ (Grok PASS alone) |
| 5 | PROFILE_V3_DEPTH | 5.95 | 7.33 | 6.53 | **FAIL** | ✗ |

**Binding verdict: NONE clear the ≥9.0 floor.** Per intake gate rule "Below 9.0 = concept dies or revises. No skipping gates."

**Top-2 (despite sub-threshold):**
- **Sonar** picks #1 PROACTIVE_SCHEDULER and #4 PREDICTIVE_CLIENT_CARE — the two closest to pass.
- **Grok** returned no top-2 field. Grok's own PASS-verdict marks are #1 and #4 as well.

**Meta-capability — specialist consultation bundle:** Both engines **recommend YES** to bundle specialist consultation rights with any passing candidate. Rationale (both): force-multiplier that removes Solon bottleneck on domain expertise; budget cap + MCP-logged audits address drift/cost risks. Since no candidate passes yet, meta-capability stays queued.

---

## Per-candidate detail

### 1 · PROACTIVE_SCHEDULER — merged 8.58 — NEEDS-WORK

Dims (merged): design 9.0 · scope 8.5 · gates 8.5 · revenue 8.5 · xval 9.0 · testing 7.5

**Sonar (8.45 NEEDS-WORK):**
- Strong design: explicit cron triggers + pre-authorized scopes + hard limits via DR-AMG-ENFORCEMENT-01.
- Revenue quantified ($1K–1.5K/mo) and Solon-scale calibrated, but lacks explicit formula.
- Risks mitigated; testing could specify more multi-step failure modes.

**Grok (8.83 PASS):**
- Strong design with clear implementation via cron + pre-authorized scopes; directly addresses Solon overhead.
- High revenue impact through time savings + error prevention, solid risk mitigation via hard limits.
- Feasible testing of schedules + logs; edge cases in drift require monitoring.

**What's needed to clear 9.0:** explicit $ formula per task class (time-saved × hourly × frequency = $/mo), named edge-case matrix (multi-step failure modes, drift vectors), numeric pass/fail thresholds for every task class.

### 2 · SELF_IMPROVEMENT_LOOP — merged 7.67 — NEEDS-WORK

Dims: design 8.0 · scope 7.5 · gates 8.5 · revenue 6.5 · xval 8.0 · testing 7.0

**Sonar (7.75 NEEDS-WORK):**
- Coherent design (QES logs → pattern analysis → EOM/Solon gated proposals); strong human-in-loop gates.
- Revenue (~10–15% review reduction) is directional but lacks $ quantification or Solon-scale calibration.
- Self-drift risk well-mitigated; cross-validation reveals proposal-fatigue risk.

**Grok (7.50 NEEDS-WORK):**
- Good conceptual design but scope limited by EOM/Solon approval dependency.
- Indirect revenue via quality improvements; testing self-improvement patterns is challenging + subjective.
- Risk of intent drift well-gated; impact may be incremental without autonomous patching.

**What's needed:** $ quantification of review-cycle reduction; anti-proposal-fatigue rate cap (e.g., ≤3 proposals/week); explicit pattern-detection threshold before proposal triggers.

### 3 · OPPORTUNITY_RADAR — merged 7.03 — NEEDS-WORK (largest engine disagreement, Δ=1.75)

Dims: design 7.5 · scope 7.5 · gates 6.0 · revenue 7.0 · xval 7.5 · testing 6.5

**Sonar (6.25 FAIL):**
- Design sketched (Perplexity API + profiles → Ntfy) but lacks explicit ranking thresholds or hard-limits.
- Scope bounded by profiles but signal-to-noise risk unquantified; no numeric pass/fail criteria.
- Revenue estimated ($500–2K/mo) but vague; false-positive risk generic without tiered mitigation.

**Grok (8.00 NEEDS-WORK):**
- Effective use of APIs for scanning; tunable profiles enhance scope feasibility.
- Revenue potential promising; noise/false positives pose gate risks.
- Starting narrow mitigates but requires iteration.

**Why the disagreement:** Sonar penalizes the missing numeric thresholds (dim3 gates = FAIL); Grok credits the tunable profile pattern. Sonar is stricter; Grok more generous.

**What's needed:** numeric signal-to-noise threshold per profile, concrete $ formula for opportunity capture rate, tiered false-positive mitigation (3-level cooldown/escalation).

### 4 · PREDICTIVE_CLIENT_CARE — merged 8.40 — NEEDS-WORK (Grok alone clears 9.0)

Dims: design 8.5 · scope 8.5 · gates 7.5 · revenue **9.5** · xval 9.0 · testing 7.5

**Sonar (8.05 NEEDS-WORK):**
- Strongest revenue case ($6K–18K/client retention at $497–1.5K MRR); clear business logic.
- Anomaly detection with thresholds + risk tiers specified; LLM interpretation lacks anti-hallucination gates.
- Client data deps clear; false-positive calibration plan generic.

**Grok (9.33 PASS):**
- Robust design leveraging existing integrations for anomaly detection.
- Exceptional revenue impact through churn prevention + loyalty, with conservative thresholds managing false positives.
- High extra value in proactive moat; threshold calibration ensures reliability.

**What's needed to clear 9.0 from BOTH:** anti-hallucination gate on LLM interpretation layer (explicit "⚠️ INSUFFICIENT DATA" rule inherited from Doc 02), concrete baseline-calibration protocol (how many weeks of data before thresholds fire), numeric false-positive rate ceiling.

### 5 · PROFILE_V3_DEPTH — merged 6.53 — **FAIL**

Dims: design 7.5 · scope 7.0 · gates 5.0 · revenue 6.0 · xval 6.5 · testing 7.0

**Sonar (5.95 FAIL):**
- Design viable (dual-grade extraction → prompt caching) but over-engineering risk explicit in own spec.
- Revenue impact (brand consistency) indirect/vague; no $ quantification or Solon-scale calibration.
- Weakest gates/testing: "Solon sample-dialog test" is subjective, lacks numeric criteria.

**Grok (7.33 NEEDS-WORK):**
- Solid expansion for agent consistency; over-engineering risk real if v2.1 suffices.
- Indirect revenue via trust lift; good testing via dialog validation.
- Gates weak on diminishing returns; requires proof of measurable lift over current version.

**Disposition:** Candidate 5 is the weakest. Its OWN intake flags "Over-engineering. v2.1 may already suffice." Both engines agree this may be diminishing-returns polish. **Recommend: kill cleanly** unless a specific measurable-lift hypothesis over v2.1 is added + quantified.

---

## Titan recommendation (COO-level, not gate-overriding)

**If one must proceed before iteration:**
1. **PROACTIVE_SCHEDULER (merged 8.58)** — closest to pass; additions to clear 9.0 are additive (formulas + edge-case matrix + thresholds), not architectural. Cheapest revise → pass.
2. **PREDICTIVE_CLIENT_CARE (merged 8.40)** — highest revenue dim (9.5). Grok already passes it alone. Sonar's objection is concrete + fixable (anti-hallucination gate + calibration protocol).

**Revise pattern for both:** address the specific deltas flagged above; re-run dual-engine; expect both to clear 9.0 on round 2.

**Kill candidates:** #5 PROFILE_V3_DEPTH (diminishing returns self-acknowledged).

**Park candidates (revise later):** #2 SELF_IMPROVEMENT_LOOP (needs $ quantification), #3 OPPORTUNITY_RADAR (needs concrete thresholds + engine disagreement to resolve).

**Meta-capability lock-in:** keep specialist consultation bundle queued — both engines endorse; bundles with whichever candidate passes first.

---

## Artifact inventory

- `/opt/amg-docs/research/IDEA_BUILDER_SCORECARD_Titan_Steroids_2026-04-18.md` — scorecard canonical copy (filed under §19)
- `/tmp/sonar_score.json` — raw Sonar Pro output (on VPS)
- `/tmp/grok_score.json` — raw Grok output (on VPS)
- `/tmp/idea_builder_scorecard.json` — merged structured output (on VPS)
- MCP log: `idea-builder-scorecard`, `titan-steroids-5-candidates`, `dual-engine-hash-complete` tags

API cost this scoring cycle: ~$0.08 (Sonar Pro 1 call + Grok 1 call, ~3K tokens each output).

---

## Gmail / Task 1 honest status

Separate .md with full detail → [plans/PLAN_2026-04-18_gmail-send-exhaustion.md](PLAN_2026-04-18_gmail-send-exhaustion.md)

Short version: I searched everywhere Solon pointed me to. 5 Gmail API creds found across the VPS, ALL scoped read-only. Both service accounts fail DWD impersonation for `gmail.send` (403 insufficient scopes). OAuth client on `adc.json` returns `restricted_client: Unregistered scope(s)` when asked to refresh with `gmail.send`. The creds ARE set up, as Solon said — they just don't carry the send permission. Draft is staged in Drafts folder (ID `19da0f6b1abcb892`); 1-click send remains the fastest path. OR 2-minute Workspace admin action to grant DWD gmail.send on the existing `titan-vertex@amg-vertex-prod.iam.gserviceaccount.com` SA — then every future send from any AMG alias is autonomous.
