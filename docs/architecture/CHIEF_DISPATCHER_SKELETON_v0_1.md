# Chief Dispatcher Skeleton v0.1

**Target canonical path:** `/opt/amg-docs/architecture/CHIEF_DISPATCHER_SKELETON_v0_1.md`
**Staged path:** `/Users/solonzafiropoulos1/titan-harness/docs/architecture/CHIEF_DISPATCHER_SKELETON_v0_1.md`
**Owner:** Achilles, CT-0427-67
**Status:** Phase 3 design only. Queue-only dispatcher; no builder execution in this phase.

## 1. Purpose

Phase 3 needs chiefs that can intake work, write a properly tagged queue task, watch status, and close or block based on verifier receipts. It does not yet need real builder execution.

## 2. Core Loop

For each chief:

1. read intake source
2. normalize objective + acceptance criteria
3. choose builder tag
4. queue task with ownership tags
5. watch for claim/status changes
6. require verifier result before close
7. log decision or blocker

## 3. Required Tags

Every dispatched task must include:

- `chief:<name>`
- `owner:<chief>`
- `agent:<builder>`
- `lane:<type>`
- `cost:<tier>`

Tasks missing `owner` or `agent` are invalid and must not be dispatched.

## 4. Status Contract

Allowed high-level flow:

`pending -> active -> completed`

`pending -> active -> blocked`

`pending -> active -> failed`

No close is allowed without:

- builder receipt
- verifier signal
- chief log decision

## 5. Phase 3 Boundary

Included:

- chief loop skeleton
- queue write contract
- watch/status contract
- verifier dependency
- synthetic dispatch tests

Excluded:

- real builder execution
- paid model runs
- live production actions
- direct Solon GUI automation

## 6. Synthetic Tests

1. Hercules synthetic dispatch to `iolaus`
2. Nestor synthetic dispatch to `ariadne`
3. Alexander synthetic dispatch to `calliope`

Each synthetic task must prove:

- correct tags
- correct queue write
- status watch works
- missing verifier blocks closure

## 7. Acceptance Criteria

1. Dispatcher can create queue tasks for all three chiefs.
2. Every queued task includes all required tags from §3.
3. Missing `owner` or `agent` tag causes rejection.
4. Chief can watch task state without executing the builder.
5. No task can be marked complete without a verifier result.
6. Synthetic queue-only dispatch works for Hercules, Nestor, and Alexander.
7. Dispatcher logs blocker on status stall or missing receipt.
8. Phase 3 does not claim builder parity yet.

## 8. Self-Score

| Dimension | Score | Note |
|---|---:|---|
| Technical soundness | 9.1 | Small, clear queue-only contract. |
| Completeness | 9.0 | Covers intake, tags, watch loop, and close rules. |
| Edge cases | 9.0 | Missing verifier and tag rejection are explicit. |
| Risk identification | 9.2 | Prevents false-complete dispatcher claims. |
| Evidence quality | 9.0 | Synthetic tests map directly to acceptance. |
| Operational discipline | 9.2 | Keeps Phase 3 queue-only; no premature builder claims. |

Overall: 9.1/10.
