# Chief Bootstrap Renderer v0.1

**Target canonical path:** `/opt/amg-docs/architecture/CHIEF_BOOTSTRAP_RENDERER_v0_1.md`
**Staged path:** `/Users/solonzafiropoulos1/titan-harness/docs/architecture/CHIEF_BOOTSTRAP_RENDERER_v0_1.md`
**Owner:** Achilles, CT-0427-65
**Status:** Phase 2 design only. No queue mutation, deploy, or route edit performed here.

## 1. Purpose

Phase 2 needs one component that turns MCP state into deterministic chief boot prompts and one route-restoration scope that makes those prompts truthful. This doc scopes both.

`chief_bootstrap_renderer` is the renderer. It does not decide strategy. It assembles:

- standing context
- recent decisions
- queue/blocker snapshot
- degraded-mode warnings
- chief-specific lcache handoff

For Hercules, Nestor, and Alexander.

## 2. Required Inputs

Priority order:

1. `get_bootstrap_context`
2. `get_recent_decisions`
3. `search_memory`
4. local lcache fallback

If route 1 or 3 is unavailable, the renderer must mark the boot prompt degraded. It must not pretend a full bootstrap happened.

## 3. Route Restoration Scope

Phase 2 must either restore or explicitly deprecate these routes:

| Route/Tool | Required Outcome |
|---|---|
| `search_memory` | Restored for chief operational recall |
| `get_bootstrap_context` | Restored for first-turn hydration |
| task queue read path | newest-first ordering + bounded pagination |
| claim/update task paths | tag enforcement + documented transitions |
| sprint-state read | restored or removed from chief bootstrap contract |

Non-goals:

- schema migrations
- new ACL products
- new external APIs
- chief UI work

## 4. Output Artifacts

For each chief:

- `boot_prompt.txt`
- `boot_prompt.degraded.txt` template
- `lcache/<chief>.md`
- `shift_state/<chief>.json` contract

## 5. Rendering Rules

Each rendered prompt must include:

- chief identity and lane
- top 3 live priorities
- blockers relevant to that chief
- exact degraded-route flags if any
- last verified handoff summary
- instructions to log `bootstrap_degraded:<chief>` if route set is incomplete

Each prompt must exclude:

- raw secrets
- unrelated chief backlog
- speculative route status

## 6. Degraded-Mode Contract

Degraded mode is triggered when:

- `get_bootstrap_context` fails
- `search_memory` fails
- queue read is unavailable

In degraded mode:

1. render from recent decisions + local lcache only
2. prepend a `DEGRADED CONTEXT` warning
3. suppress any claim of full memory parity
4. log the missing route names for repair

## 7. Acceptance Criteria

1. Renderer can output one bootstrap file per chief.
2. Each output contains chief-specific priorities, blockers, and handoff summary.
3. Missing `search_memory` or `get_bootstrap_context` forces degraded-mode labeling.
4. Queue snapshot uses newest-first ordering.
5. Renderer writes no secret material into boot artifacts.
6. Route restoration scope is limited to parity-critical endpoints only.
7. A synthetic chief bootstrap can be regenerated from the same inputs deterministically.
8. One test proves degraded mode is honest when both memory routes fail.

## 8. Self-Score

| Dimension | Score | Note |
|---|---:|---|
| Technical soundness | 9.1 | Simple renderer boundary, no hidden control logic. |
| Completeness | 9.0 | Covers inputs, outputs, degraded mode, and route scope. |
| Edge cases | 9.1 | Missing-route honesty is first-class. |
| Risk identification | 9.2 | Avoids false "fully loaded" claims. |
| Evidence quality | 9.0 | Acceptance tests are concrete. |
| Operational discipline | 9.2 | Narrow route scope prevents Phase 2 creep. |

Overall: 9.1/10.
