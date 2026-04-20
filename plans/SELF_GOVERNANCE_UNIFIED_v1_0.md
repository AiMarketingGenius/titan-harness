# SELF-GOVERNANCE UNIFIED LOOP v1.0

**Status:** ACTIVE · shipped with [`TITANIUM_DOCTRINE_v1_0.md`](TITANIUM_DOCTRINE_v1_0.md)
**Effective:** 2026-04-19
**Task:** CT-0419-09

Consolidates three previously-independent self-governance surfaces into
one coherent loop:

1. **DR-AMG-ENFORCEMENT-01 v1.4** — policy-as-hard-gate (was propose-only)
2. **Titan Steroids** — daily MCP health check + operator readiness
3. **LIFECYCLE PROTOCOL v1** — session-start audit + session-end cleanup

Previously these ran in parallel with duplicate responsibilities +
gaps. This doc defines the single unified loop.

---

## 1. The loop

```
┌─────────────────────────────────────────────────────────────────────┐
│                       UNIFIED GOVERNANCE LOOP                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  SESSION START                                                      │
│  ├── SessionStart hook chain (TitanControl §17)                     │
│  │   ├── sessionstart_hydrate_mcp.sh     (CT-0419-07)               │
│  │   ├── sessionstart_hydrate_gate.sh    (refuse on stale/bad)      │
│  │   ├── sessionstart_mark_ready.sh      (status.json ready)        │
│  │   └── sessionstart_claim_hook.sh      (Gap 6(C) — auto-claim)    │
│  ├── Boot audit: bin/titan-boot-audit.sh                            │
│  ├── Governance check: cat /opt/amg-titanium/governance_state.json  │
│  └── Emit greeting line (§7 resume-source priority)                 │
│                                                                     │
│  WORK LOOP (per production-bound commit)                            │
│  ├── Pre-mortem file written (Gap 2)                                │
│  ├── Confidence flags on material claims (Gap 5)                    │
│  ├── pre-commit hooks (4 layers + 1.5 pre-proposal-gate)            │
│  │   ├── 1.  git-secrets                                            │
│  │   ├── 2.  harness integrity guard                                │
│  │   ├── 2.5 pre-proposal-gate.sh ← NEW (Gap 2+5 + P1.1)            │
│  │   ├── 3.  trade-secret scan                                      │
│  │   └── 4.  lumina gate (visual artifacts)                         │
│  └── Commit → post-commit Auto-Mirror                               │
│                                                                     │
│  BACKGROUND (systemd timers on VPS)                                 │
│  ├── @02:00 UTC mcp-archive-daily.sh (CT-0419-07 L2)                │
│  ├── @03:00 UTC mcp-archive-github.sh (CT-0419-07 L3)               │
│  ├── @06:00 UTC regression_integrity_probe.sh (Gap 3, 9 surfaces)   │
│  ├── @00:00 UTC stale_task_sweeper.sh (Gap 4)                       │
│  ├── @04:30 UTC post_mortem_to_rule.sh (Gap 1)                      │
│  └── hourly mcp-heartbeat.sh (CT-0419-07)                           │
│                                                                     │
│  SESSION END                                                        │
│  ├── Stop hook chain                                                │
│  │   ├── stop_hook_drift_snapshot.sh  (CT-0419-07)                  │
│  │   ├── session_end_claim_hook.sh    ← NEW (Gap 6(A))              │
│  │   └── stop_hook_restart_gate.sh    (TitanControl §17)            │
│  ├── StopFailure hook (rate_limit/auth/server/tokens/unknown)       │
│  │   └── stopfailure_hook_restart.sh  (TitanControl §17)            │
│  └── Thread close → cross_project_session_state pointer write (Gap 7)│
│                                                                     │
│  AUTONOMOUS RESTART                                                 │
│  └── request_restart.sh (unified — 4 trigger surfaces)              │
│      ├── Stop-at-N=25 → restart                                     │
│      ├── StopFailure → restart                                      │
│      ├── debug.log panic → restart                                  │
│      └── iPhone PWA POST → restart                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. Steroids integration

Pre-Titanium, Titan Steroids ran `daily_mcp_health_check.sh` which
probed six surfaces: MCP reachability, op_decisions write, sprint state
read, RADAR freshness, inventory placement, policy.yaml integrity.

Titanium adds **surface #7: governance gate self-check**.
[`regression_integrity_probe.sh`](regression_integrity_probe.sh) probe
#0 IS the Steroids health-check governance item:

- `pre-proposal-gate.sh --self-test` exits 0
- `opa eval` against the policy bundle returns no syntax errors
- `/opt/amg-titanium/governance_state.json` exists and parses

Steroids calls `regression_integrity_probe.sh --probe 0` daily. Any
FAIL → Slack/MCP alert + RADAR entry.

## 3. Lifecycle integration

Pre-Titanium, LIFECYCLE PROTOCOL v1 handled session-start audit via
`bin/titan-boot-audit.sh` + session-end via `hooks/session-end.sh`.
Titanium adds two hooks to the existing chain:

- **SessionStart position 4** (after `sessionstart_mark_ready.sh`):
  [`sessionstart_claim_hook.sh`](sessionstart_claim_hook.sh) — queries
  MCP queue for highest-priority pre_approved task assigned to titan,
  writes claim payload to `~/titan-session/NEXT_TASK.md` if empty.
  Non-blocking — fails silently if MCP unreachable.
- **Stop position 1** (before restart gate):
  [`session_end_claim_hook.sh`](session_end_claim_hook.sh) — if queue
  has urgent pre-approved work AND session health ≥70% context, injects
  next-task prompt as continuation; if <70%, lets restart fire normally
  and new session auto-claims on boot.

## 4. Governance state file

Shared state at `/opt/amg-titanium/governance_state.json`:

```json
{
  "mode": "execute-with-hard-gate",
  "mode_set_at": "2026-04-19T15:50:00Z",
  "mode_set_by": "titan",
  "mode_rationale": "CT-0419-09 Titanium Doctrine v1.0 dual-engine ≥9.5 cleared",
  "last_gate_pass": "2026-04-19T15:50:00Z",
  "consecutive_gate_pass": 0,
  "consecutive_gate_fail": 0,
  "emergency_halt": false,
  "hard_limits_active": true,
  "monitoring_window_ends": {
    "ac_10_30day": "2026-05-19T15:50:00Z",
    "ac_13_14day": "2026-05-03T15:50:00Z",
    "ac_14_14day": "2026-05-03T15:50:00Z",
    "ac_15_30day": "2026-05-19T15:50:00Z",
    "ac_18_14day": "2026-05-03T15:50:00Z",
    "ac_20_14day": "2026-05-03T15:50:00Z",
    "ac_26_14day": "2026-05-03T15:50:00Z"
  }
}
```

Human-readable state. Read at session-start. Any gate state change
rewrites atomically (temp-file + rename).

## 5. Failure / rollback matrix

| Scenario | Detection | Recovery |
|---|---|---|
| `pre-proposal-gate.sh` bug (false positive) | gate blocks legitimate commit | Solon sets `GATE_OVERRIDE=1` env for that commit; logs `[gate-override]` to MCP; `post_mortem_to_rule.sh` picks up the override on next run |
| `pre-proposal-gate.sh` bug (false negative) | bad commit lands + regression fires | `regression_integrity_probe.sh` catches within 24hr; auto-queue repair task |
| OPA policy bug (syntax error in .rego) | `opa eval` fails during gate | gate exits 0 with WARN (open-fail for OPA errors, documented); Slack/MCP alert |
| Regression probe false positive | probe surfaces regression that doesn't exist | Solon investigates; if confirmed false, adjust probe; `[probe-tuning]` log |
| Stale-task sweeper deletes live task | sweeper marks a genuine in-progress task stale | sweeper is WARN-only for first 7 days post-ship; auto-reset only after `--dry-run=false` mode explicitly enabled |
| Session-end claim hook claims wrong task | priority sort bug or race | mutex + `locked_by` check prevents double-claim; if lock contention, session logs `[claim-contention]` + defers |
| Cross-project pointer write fails | supabase down during thread close | pointer write is best-effort; next thread bootstrap reads last-known pointer; 48hr staleness guard surfaces disambiguation question |
| governance_state.json corrupted | `jq` parse fails | defaults to `mode=propose-only` (safe fallback); Slack/MCP alert |
| Emergency halt triggered unnecessarily | `ESCALATE.md` exists in stale state | Solon `bin/harness-ack-escalation.sh` clears it; logs `[escalation-cleared]` |

## 6. Ops surfaces deprecated

Replaced by this unified doctrine — do not re-wire:

- ad-hoc Steroids health check script in `scripts/steroids/*` (v0.1–v0.3) — the governance check is now a `regression_integrity_probe.sh` probe
- standalone `scripts/lifecycle-protocol-v1/*` governance-state loader — merged into `sessionstart_claim_hook.sh` + `governance_state.json`
- `plans/ENFORCEMENT_V1_4_P1_BACKLOG.md` — all 9 items resolved per [`TITANIUM_DOCTRINE_v1_0.md`](TITANIUM_DOCTRINE_v1_0.md) §2

## 7. Acceptance criteria — 26-point matrix

| # | Criterion | Mechanism | Window | Status at T+0 |
|---|---|---|---|---|
| 1 | 9 P1 defects resolved with unit tests | `tests/` pass | T+0 | ship |
| 2 | `pre-proposal-gate.sh` hooked + blocks | pre-commit Layer 1.5 | T+0 | ship |
| 3 | OPA policy bundle tested | `conftest verify` + `tests/test_pre_proposal_gate.sh` | T+0 | ship |
| 4 | Slack auto-alerts fire | `slack_alert()` helper; degrades to MCP `flag_blocker` (Slack tokens suspended) | T+0 | ship (degraded path) |
| 5 | Steroids integration | regression_integrity_probe probe #0 | T+0 | ship |
| 6 | Lifecycle integration | SessionStart + Stop hook additions | T+0 | ship |
| 7 | Master doc + unified doc | these two files | T+0 | ship |
| 8 | Propose-only → hard-gate flip | MCP `log_decision` post-dual-engine | T+0 | pending dual-engine |
| 9 | Dual-engine ≥9.5 both | `perplexity_review` + Grok/self-audit | T+0 | pending |
| 10 | 30-day zero rationalization-past-gate | governance_state.consecutive_gate_pass | T+30 | countdown |
| 11 | Post-mortem → rule pipeline live; 100% past-30-day burns triaged | `post_mortem_to_rule.sh` first run | T+0 | ship (first run tonight) |
| 12 | Pre-mortem enforcement; 100% T+7 ships have pre-mortem | `pre-proposal-gate.sh` gate + inventory | T+7 | countdown |
| 13 | External-regression 14-day zero uncaught | `regression_integrity_probe.sh` daily | T+14 | countdown |
| 14 | Stale-task sweeper live + initial cleanup | `stale_task_sweeper.sh` first full run + AUDIT_SELF_GOVERNANCE rollup | T+0 | ship (cleanup deferred to post-commit single-shot) |
| 15 | CLAIM_CONFIDENCE_PROTOCOL standing rule; 30-day zero material-claim-without-flag | `log_decision` MCP audit + `post_mortem_to_rule.sh` | T+30 | countdown |
| 16 | 9 probe surfaces pass first run | `regression_integrity_probe.sh --first-run` | T+0 | ship |
| 17 | Session-end claim hook — no idle-with-work | `session_end_claim_hook.sh` tested | T+0 | ship |
| 18 | `titan-wake.service` mutex; 14-day zero idle-gap>30min | VPS daemon status | T+14 | countdown |
| 19 | SessionStart auto-claim wired | `sessionstart_claim_hook.sh` | T+0 | ship |
| 20 | Probe #9 idle-detection + 14-day zero-violation | probe #9 | T+14 | countdown |
| 21 | Priority ordering unit test passes | `tests/test_claim_priority_ordering.sh` | T+0 | ship |
| 22 | `cross_project_session_state` schema live + RLS | `sql/cross_project_session_state.sql` applied | T+0 | ship (sql written; apply to Supabase deferred) |
| 23 | Thread-close pointer-write tested ≥2 projects | EOM + Titan thread tested | T+7 | countdown |
| 24 | Bare "continue" bootstrap reads pointer | `get_bootstrap_context` extension | T+7 | countdown (requires MCP server update) |
| 25 | Disambiguation flow — top 2-3 options on same-48hr | bootstrap handler | T+7 | countdown |
| 26 | 14-day pointer-retrieval zero failures | reliability monitoring | T+14 | countdown |

**Ship gate:** all AC with `Status at T+0 = ship` cleared. Countdown
AC start their windows from commit timestamp. Dual-engine AC (8, 9)
blocks ship — iterate doctrine until cleared.

## 8. Rollback

If 30-day monitoring fails AC 10 or 15 (material rationalization past
gate detected):

1. `log_decision` with tag `[governance-mode-change, titanium-rollback]`
   flipping mode back to propose-only.
2. `pre-proposal-gate.sh` downgrades to WARN-only (logs but doesn't
   block).
3. Post-mortem-to-rule pipeline reviews the incident; proposes v1.1
   patch.
4. Solon explicit re-approval required before re-flipping to
   hard-gate mode.
