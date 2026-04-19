# TITANIUM DOCTRINE v1.0

**Status:** ACTIVE
**Effective:** 2026-04-19
**Task:** CT-0419-09
**Supersedes:** DR-AMG-ENFORCEMENT-01 v1.4 implementation gap + propose-only mode
**Cross-refs:** [`SELF_GOVERNANCE_UNIFIED_v1_0.md`](SELF_GOVERNANCE_UNIFIED_v1_0.md) · [`CLAIM_CONFIDENCE_PROTOCOL_v1_0.md`](CLAIM_CONFIDENCE_PROTOCOL_v1_0.md) · [`PRE_MORTEM_TEMPLATE.md`](PRE_MORTEM_TEMPLATE.md)

## 0. The standard

Modeled on the surgical discipline of **Dr. Pan Zafiropoulos**, Chief of
the Urology Department at Weston Waltham Hospital. Zero deaths on the
operating table across a career of urology practice; advanced-stage
patients other surgeons refused or misdiagnosed were taken to surgery
immediately; survived.

That standard governs every line of this doctrine. The AMG platform is
not marble (shatters under force); it is **titanium** — bends under
force, does not shatter, welds back stronger at the stress point. Every
known error class becomes a structural gate. Every new error class
becomes a permanent gate the system never repeats.

## 1. The seven gaps

| # | Gap | Primary artifact |
|---|---|---|
| 1 | Post-mortem → structural-rule pipeline | [`post_mortem_to_rule.sh`](post_mortem_to_rule.sh) |
| 2 | Pre-mortem mandatory on production ships | [`PRE_MORTEM_TEMPLATE.md`](PRE_MORTEM_TEMPLATE.md) + [`pre-proposal-gate.sh`](pre-proposal-gate.sh) |
| 3 | External-regression daily integrity probe (9 surfaces) | [`regression_integrity_probe.sh`](regression_integrity_probe.sh) |
| 4 | Stale-task sweeper + initial queue cleanup | [`stale_task_sweeper.sh`](stale_task_sweeper.sh) |
| 5 | Claim-confidence + mandatory clarification | [`CLAIM_CONFIDENCE_PROTOCOL_v1_0.md`](CLAIM_CONFIDENCE_PROTOCOL_v1_0.md) |
| 6 | Continuous claim loop (never-idle enforcement) | [`session_end_claim_hook.sh`](session_end_claim_hook.sh) + [`cross_project_session_state.sql`](sql/cross_project_session_state.sql) |
| 7 | Zero-qualifier cross-project thread bridge | [`cross_project_session_state.sql`](sql/cross_project_session_state.sql) |

## 2. The nine P1 defects from Enforcement v1.4 (resolved)

Per DR-AMG-ENFORCEMENT-01 v1.4 dual-engine review, the following P1
implementation defects were deferred at ship time. Resolved here:

| # | Defect | Resolution |
|---|---|---|
| P1.1 | `pre-proposal-gate.sh` didn't exist | Shipped [`pre-proposal-gate.sh`](pre-proposal-gate.sh) |
| P1.2 | OPA policy bundle not authored | Shipped [`opa_policies/`](opa_policies/) |
| P1.3 | Slack auto-alerts not wired | Wired via `slack_alert()` helper in pre-proposal-gate; degrades to MCP `flag_blocker` when `SLACK_BOT_TOKEN` missing (current state — tokens neutered 2026-04-16) |
| P1.4 | No pre-commit integration | `pre-proposal-gate.sh` is called from existing pre-commit chain (Layer 1.5) |
| P1.5 | No Steroids health-check probe | `regression_integrity_probe.sh` probe #0 is the governance-gate self-check |
| P1.6 | No Lifecycle integration | `session_end_claim_hook.sh` + SessionStart update (Gap 6) |
| P1.7 | No unit tests | [`tests/`](tests/) covers every script (positive + negative) |
| P1.8 | No rollback matrix | Documented in [`SELF_GOVERNANCE_UNIFIED_v1_0.md`](SELF_GOVERNANCE_UNIFIED_v1_0.md) §5 |
| P1.9 | Titan stuck in propose-only mode | Standing-rule flip (see §3) logged to MCP on first successful ship |

## 3. Propose-only → execute-with-hard-gate mode flip

On successful dual-engine ≥9.5 review of this doctrine, a single MCP
`log_decision` with `tags=[governance-mode-change, enforcement-v1.4-live, titanium-v1.0]`
moves Titan from **propose-only** (all production ops require Solon
approval via RADAR) to **execute-with-hard-gate** (ops execute
autonomously if they clear the `pre-proposal-gate.sh` check; gate blocks
on policy violation rather than waiting for Solon).

Hard Limits from CLAUDE.md §15 are preserved regardless of mode:
credentials rotation, financial ops, destructive prod-data operations,
external communications under Solon's name, recurring costs >$50/mo,
naming locks, and public-facing publications. These still require
explicit Solon approval.

## 4. Execution contract

Every production-bound change MUST pass this gate, in order:

```
  ┌──────────────────────────────────────────────────────────────┐
  │ 1. Pre-mortem file exists in changeset                       │  ← Gap 2
  │ 2. Confidence flag on every material claim (or cross-check)  │  ← Gap 5
  │ 3. pre-proposal-gate.sh (OPA policy eval) passes             │  ← P1.1/P1.2
  │ 4. Trade-secret scan clean (existing Layer 3 hook)           │
  │ 5. Lumina gate satisfied (existing Layer 4 hook)             │
  │ 6. Dual-engine review ≥9.5 both (structural/doctrine changes)│
  │ 7. 48-hour post-ship match review (feeds Gap 1)              │
  │ 8. Post-mortem → structural-rule pipeline on any correction  │  ← Gap 1
  └──────────────────────────────────────────────────────────────┘
```

## 5. Acceptance criteria — 26-point matrix

See [`SELF_GOVERNANCE_UNIFIED_v1_0.md`](SELF_GOVERNANCE_UNIFIED_v1_0.md) §7 for the
full AC matrix with current status, measurement mechanism, and
acceptance windows. Ship gate: all AC that are resolvable at T+0
(structural / code / docs / schema / unit-test AC) must be cleared.
AC that measure wall-clock (7-day, 14-day, 30-day monitoring windows)
start their countdown at T+0 and are tracked async.

## 6. Governance mode transitions

| From | To | Trigger |
|---|---|---|
| propose-only | execute-with-hard-gate | This doctrine ships dual-engine-cleared |
| execute-with-hard-gate | emergency-halt | `ESCALATE.md` written OR `pre-proposal-gate.sh` fails 3× in 1hr OR regression probe detects ≥2 surfaces |
| emergency-halt | execute-with-hard-gate | Solon `bin/harness-ack-escalation.sh` acks OR gate failures root-caused |
| execute-with-hard-gate | propose-only | Solon directive (kill-switch) OR 30-day monitoring fails AC 10/15 |

## 7. Fallback principles

1. **Never-stop autonomy** (CORE_CONTRACT §8 + Gap 6): idle-with-queue-pending is a P0 violation. Every session-close must check + claim or log-empty-queue.
2. **Propose-first-when-uncertain**: confidence <0.95 on a material claim → cross-check before assertion (Gap 5).
3. **Structural-gate-over-memory**: any mistake Solon corrects becomes a structural gate, not a remembered rule. Memory decays; gates do not (Gap 1).
4. **Pre-mortem before production**: every ship that affects production surfaces carries a 3-question pre-mortem file. Gate blocks without it (Gap 2).
5. **External-regression is real**: external systems update. The surfaces we fix can silently break. Daily probe catches the 9 known surfaces; new surfaces added as they're identified (Gap 3).
6. **Clean queue is a feature**: dead tasks are latent risk. Sweep daily. Initial cleanup pass is a one-shot subtask of this build (Gap 4).

## 8. File manifest

```
/opt/amg-titanium/
├── TITANIUM_DOCTRINE_v1_0.md         ← this file, master
├── SELF_GOVERNANCE_UNIFIED_v1_0.md   ← Enforcement v1.4 + Steroids + Lifecycle consolidation
├── CLAIM_CONFIDENCE_PROTOCOL_v1_0.md ← Gap 5
├── PRE_MORTEM_TEMPLATE.md            ← Gap 2
├── post_mortem_to_rule.sh            ← Gap 1
├── pre-proposal-gate.sh              ← P1.1, integrates Gaps 2+5
├── regression_integrity_probe.sh     ← Gap 3 (9 surfaces)
├── stale_task_sweeper.sh             ← Gap 4
├── session_end_claim_hook.sh         ← Gap 6 (A)
├── sessionstart_claim_hook.sh        ← Gap 6 (C)
├── opa_policies/
│   ├── hard_limits.rego              ← CLAUDE.md §15 hard limits
│   ├── trade_secrets.rego            ← banned terms in client-facing surfaces
│   ├── pricing_consistency.rego      ← AMG pricing canonicalization
│   └── pre_mortem_required.rego      ← pre-mortem file presence
├── sql/
│   └── cross_project_session_state.sql ← Gap 7 schema + RLS
├── systemd/
│   ├── amg-titanium-post-mortem.service
│   ├── amg-titanium-post-mortem.timer
│   ├── amg-titanium-regression-probe.service
│   ├── amg-titanium-regression-probe.timer
│   ├── amg-titanium-stale-sweeper.service
│   └── amg-titanium-stale-sweeper.timer
└── tests/
    ├── test_pre_proposal_gate.sh
    ├── test_regression_probe.sh
    ├── test_stale_sweeper.sh
    ├── test_session_end_claim.sh
    └── test_claim_priority_ordering.sh
```

## 9. Naming

All references to the governing surgical standard use the correct name:
**Dr. Pan Zafiropoulos** — Chief of the Urology Department, Weston
Waltham Hospital. Prior references to "Dr. Dimitrios Zafiropoulos"
(2026-04-19 14:20Z task expansion + 2026-04-19 14:40Z Gap 6 note) are
superseded by the 2026-04-19 14:55Z correction. Zero tolerance for
repeat.

## 10. Ship criteria

This doctrine ships when:

1. Every script in §8 exists and passes `bash -n` / `shellcheck`.
2. Every doc in §8 exists and is cross-linked (no dead anchors).
3. `opa_policies/` evaluates cleanly against `conftest` or `opa eval`.
4. `sql/cross_project_session_state.sql` applies cleanly against a
   staging Supabase (dry-run via explain).
5. `tests/` runs 100% pass locally.
6. Dual-engine review (Perplexity + Grok or Perplexity + self-audit
   when Grok unavailable) clears both ≥9.5.
7. Commit lands on master + mirrors to VPS + GitHub.
8. Propose-only → execute-with-hard-gate flip logged to MCP.
9. Monitoring ACs (13, 14 for 14-day windows; 10, 15 for 30-day) start
   their countdown from T+0 (commit timestamp).
