# IDEA BUILDER SCORECARD v1.1 — Titan Steroids (Revised)

**Date:** 2026-04-18  
**Engines:** Perplexity Sonar Pro (LiteLLM) + Grok 4 Fast Reasoning (xAI)  
**Rubric:** Doc 02 6-dimension  
**Binding gate:** merged ≥9.0 AND both engines individually ≥9.0 = PASS (per intake)  
**Predecessor:** v1.0 scorecard — NONE of 5 candidates cleared 9.0 (see `plans/PLAN_2026-04-18_idea-builder-scorecard-titan-steroids.md`)

---

## Summary — v1.1 result

| # | Candidate | Sonar | Grok | Merged | Floor met by both? | Verdict |
|---|---|---:|---:|---:|:---:|---|
| **1** | **PROACTIVE_SCHEDULER** | **9.38** | **9.00** | **9.20** | ✓ | **🟢 PASS** |
| 2 | SELF_IMPROVEMENT_LOOP | 8.65 | 8.38 | 8.53 | ✗ | 🟡 NEEDS-WORK |
| **4** | **PREDICTIVE_CLIENT_CARE** | **9.25** | **9.00** | **9.06** | ✓ | **🟢 PASS** |

**Top-2 recommended (both engines agree):** #1 PROACTIVE_SCHEDULER + #4 PREDICTIVE_CLIENT_CARE. Both qualify for DR-prompt drafting per intake flow.

**Meta-capability (specialist consultation bundle):** Both engines endorse — auto-bundles with #1 + #4.

**Kill / park decisions from v1.0 carried forward:**
- #3 OPPORTUNITY_RADAR — parked (v1.0 merged 7.03; not re-scored in v1.1 intake).
- #5 PROFILE_V3_DEPTH — killed (v1.0 merged 6.53; not re-scored in v1.1 intake).

---

## Per-candidate detail

### 🟢 #1 PROACTIVE_SCHEDULER — merged 9.20 — PASS

Dims (merged): design 9.50 · scope 9.10 · gates **9.65** · revenue 8.75 · xval 8.65 · testing 8.95

Delta from v1.0 (8.58): **+0.62.** Both engines independently cross the 9.0 floor (Sonar 9.38, Grok 9.00).

**Sonar (9.38 PASS):**
- Explicit tiered task classes, dual drift detection, and per-class kill-switch provide robust architecture with clear boundaries.
- Numeric success metrics (≥4 exec/week, zero false alerts, 3+ hrs reclaimed) and revenue quantification ($1K–1.5K/mo) address prior v1.0 gaps in specificity.
- Hard gates via DR-AMG-ENFORCEMENT-01 and Solon approval ensure safety.

**Grok (9.00 PASS):**
- Revisions provide clear architecture with enumerated tasks and systemd integration, strengthening design and scope boundaries.
- Strong quality gates via dual drift detection and per-class kill-switches address prior ambiguity in failure modes.
- Quantified success metrics and revenue impact elevate ops integration, though cross-validation remains somewhat generic.

**Promoted.** DR prompts can draft.

### 🟡 #2 SELF_IMPROVEMENT_LOOP — merged 8.53 — NEEDS-WORK

Dims: design 8.65 · scope 8.75 · gates 8.85 · revenue 8.10 · xval 8.10 · testing 8.20

Delta from v1.0 (7.67): **+0.86** (good lift, but still 0.47 short of floor).

**Sonar (8.65 NEEDS-WORK):**
- Narrowed to correction-pattern detection with explicit corpus and structured output improves focus over v1.0 vagueness.
- Proposal-only pipeline with EOM/Solon gates is solid but lacks autonomous execution for full SI value.
- 40% reduction target is measurable but revenue impact remains indirect/qualitative.

**Grok (8.38 NEEDS-WORK):**
- Narrowed scope to correction patterns with explicit corpus improves boundaries, but design still relies on weekly cron without deeper automation safeguards.
- Gates are solid with proposal-only pipeline and EOM SLA, but lacks robust cross-validation for pattern detection accuracy.
- Revenue impact is indirect and time-saving focused; testing via frequency reduction metric is measurable but not exhaustive for edge cases like proposal quality.

**What's still needed to clear 9.0:**
- Dollar-denominated revenue impact (current 40%-review-reduction target needs $ × hours-reclaimed × Solon-hourly, calibrated to ~$7,298/mo MRR)
- Cross-validation method for pattern-detection accuracy (e.g., random-sample audit of 10% of proposals, flagged if precision < 80%)
- More granular testing of proposal-quality edge cases (false-positive proposals, proposal-fatigue cooldown validated)

**Recommendation: park pending v1.2 revision or bundle into #1's scheduler run-class as a subtask.**

### 🟢 #4 PREDICTIVE_CLIENT_CARE — merged 9.06 — PASS

Dims (merged): design 9.15 · scope 8.80 · gates 9.20 · revenue **9.25** · xval 8.75 · testing 9.10

Delta from v1.0 (8.40): **+0.66.** Both engines independently cross the 9.0 floor (Sonar 9.25, Grok 9.00).

**Sonar (9.25 PASS):**
- Explicit APIs, numeric thresholds (15% / 30%), and 30-day silent calibration directly resolve v1.0 data-quality concerns.
- Strong revenue tie ($6K–18K / churn saved) with math-first flagging + LLM narrative is production-ready.
- Calibration period + weekly cap mitigate false positives effectively.

**Grok (9.00 PASS):**
- Explicit data inputs and deterministic thresholds create a robust architecture, resolving v1.0 data quality concerns.
- Quality gates via silent calibration and numeric triggers mitigate false positives effectively.
- High revenue tie-in through churn prevention and upsell metrics; strong testing via 30-day tuning period covers edges like source outages.

**Promoted.** DR prompts can draft.

---

## Titan next-actions (EOM hand-off)

1. **EOM drafts DR prompts** for #1 + #4 per Phase 4 pattern (Perplexity Sonar Pro prompt + Grok prompt, each scoring across 5 dimensions, lock at ≥9.0 both engines). Phase 4 DR prompt template reference: `/opt/amg-docs/research/PHASE_4_MODULE_DR_PROMPTS_MeetingMinutes_Teleprompter_2026-04-18.md`.
2. **Specialist consultation bundle** auto-attaches to #1 + #4 build scope (budget cap $50-100/mo initial, per intake).
3. **#2 SELF_IMPROVEMENT_LOOP** disposition: park until v1.2 tightens revenue $ quantification + adds proposal-quality cross-validation. OR bundle as a subtask inside #1's scheduler run-class (weekly correction-pattern sweep as one of the registered task classes).
4. **Cost tracking:** v1.0 run ~$0.08 + v1.1 run ~$0.08 = ~$0.16 total idea-builder spend. Well under budget.

## Artifact inventory

- Canonical: `/opt/amg-docs/research/IDEA_BUILDER_SCORECARD_v1_1_Titan_Steroids_2026-04-18.md`
- Raw engine outputs: `/opt/amg-docs/research/sonar_score_v1_1.json`, `grok_score_v1_1.json`, `idea_builder_scorecard_v1_1.json`
- R2 mirror: `r2:amg-storage/amg-docs/research/`
- MCP log: `idea-builder-scorecard-v1-1-pass`, `titan-steroids-revised-pass`
