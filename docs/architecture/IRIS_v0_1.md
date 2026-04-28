# IRIS v0.1

**Target canonical path:** `/opt/amg-docs/architecture/IRIS_v0_1.md`
**Staged path:** `/Users/solonzafiropoulos1/titan-harness/docs/architecture/IRIS_v0_1.md`
**Owner:** Achilles, CT-0427-72
**Status:** Ship-ready build spec for Titan CT-0427-73. Doc-only phase; no deploy or live queue mutation performed here.

## 1. Scope

Iris v0.1 is the pre-factory mailman daemon that removes Solon from the middleware loop for chief-level work. It is intentionally narrower than the full v4.0.2.3 Iris design:

- polls MCP every 3 minutes
- watches only approved or pre-approved work meant for Titan or Achilles lanes
- triggers task claim or delivery behavior
- does not perform chief-team routing yet
- does not own builder dispatch, cohort rotation, or chief inbox orchestration yet

This is a bridge release. Full v1.0 behavior arrives when the chief-team stack lands in Phases 4-5.

## 2. Cadence And Filters

### 2.1 Poll cadence

- Cron cadence: `*/3 * * * *`
- Execution mode: one-shot poll-and-deliver loop
- Default runtime target: VPS cron or systemd timer

### 2.2 MCP reads

Primary queue read contract:

- `get_task_queue(status=approved)`
- delivery layer further filters to `approval=pre_approved`
- separate passes by `assigned_to`

Required delivery passes:

1. `assigned_to=titan`
2. `assigned_to=manual` plus an Achilles-routing tag match

If the MCP queue surface does not support `approval` server-side, Iris v0.1 must filter client-side after fetch.

### 2.3 Eligible task classes

Iris v0.1 only touches tasks that satisfy all of the following:

- `approval=pre_approved`
- `status` is claimable or deliverable by current MCP semantics
- task has not already been delivered per idempotency state
- task is addressed to a supported recipient lane in §3

Out-of-scope rows are skipped silently except for structured debug logs.

## 3. Routing Logic

Iris v0.1 routes by `assigned_to`, not by chief/team roster.

### 3.1 Titan lane

For `assigned_to=titan`:

1. Poll queue and identify eligible row.
2. Prefer direct `claim_task(operator_id="titan", task_id=<task_id>)`.
3. If direct claim is not possible from the daemon runtime, emit a queue notification using `POST /api/queue-task` or equivalent Titan notification surface referencing the existing task id.
4. Log structured delivery receipt after successful claim or notification.

Titan lane target outcome: Titan sees or claims the task without Solon relaying it manually.

### 3.2 Achilles lane

For `assigned_to=manual` with Achilles-targeting tags:

- Accepted tag examples: `achilles`, `achilles_dispatch`, `achilles_spec`, `owner:achilles`
- Delivery surface: Mac harness webhook or direct file drop into the Achilles-side continuation/inbox path
- The daemon does not rewrite the task; it delivers a claim-ready notification bundle containing task id, objective, instructions, and acceptance criteria

Preferred delivery order:

1. Mac harness webhook when reachable
2. direct file drop when webhook is unavailable

### 3.3 Explicit non-goals

Iris v0.1 does not:

- route to builders
- interpret `agent:<builder>` tags
- reorder work across chiefs
- perform dependency sequencing
- send Slack/DM fanout by default

Those belong to the full Iris/chief-dispatcher stack later.

## 4. Idempotency

State file:

- `/var/lib/amg-iris/delivered_state.json`

Required idempotency key:

- `sha1(task_id + approval_timestamp)`

If `approval_timestamp` is absent in the MCP row, use the earliest stable equivalent in this order:

1. `updated_at` for the transition into approved/queued-ready state
2. `created_at`

Tracked fields per delivered item:

- `task_id`
- `recipient`
- `delivery_key`
- `delivered_at`
- `delivery_mode`
- `claim_result`

Rules:

- same `delivery_key` may not be delivered twice
- changed approval timestamp creates a new key and allows re-delivery
- state writes must be atomic: write temp file then rename

## 5. Delivery Receipts

Each successful delivery or claim attempt writes:

- `log_decision(project_source="iris_v0_1", tags=["mail_delivered", "<task_id>", "<recipient>"])`

Minimum decision text payload:

```text
IRIS v0.1 delivered task <task_id> to <recipient> via <delivery_mode>; claim_status=<claimed|notified|degraded>; idempotency_key=<sha1>.
```

Minimum rationale payload:

- poll timestamp
- queue status observed
- approval field observed
- why this recipient was selected

Failure receipts use tags:

- `mail_delivery_failed`
- `<task_id>`
- `<recipient>`

## 6. Self-Heal And Log Hygiene

Iris v0.1 mirrors the `dep_watcher` operational pattern:

- single append-only daemon log
- weekly logrotate
- 4-week retention
- `copytruncate`

Required files:

- `/var/log/amg-iris.log`
- `/etc/logrotate.d/amg-iris`

Self-heal behavior:

- recreate missing state directory on boot
- recreate missing log file on boot
- continue safely if logrotate config is absent, but emit a warning decision once per day

## 7. Failure Modes

### 7.1 MCP unreachable

Behavior:

- exponential backoff inside the current run up to a bounded cap
- no destructive retries across tasks
- log local error
- write degraded decision when the run ends without a successful poll

### 7.2 Recipient unreachable

Behavior:

- do not drop the task silently
- write dead-letter record to `mcp_dead_letter`
- include task id, intended recipient, delivery mode, last error, and first failure timestamp

### 7.3 Claim conflict or queue-state mismatch

If `claim_task` returns conflict or the row is still `queued` despite `approval=pre_approved`:

- do not claim success
- write a degraded receipt
- preserve idempotency state as undelivered
- surface exact MCP response in the rationale

### 7.4 Corrupt state file

Behavior:

- move bad file to `delivered_state.json.corrupt.<ts>`
- rebuild empty state
- log decision with `mail_state_reset`

## 8. v1.0 Absorption Path

Iris v0.1 must retire cleanly into the full v4.0.2.3 Iris model.

Migration contract:

1. v0.1 handles only Titan + Achilles routing.
2. Phase 4-5 introduces chief-team routing and A/B/C/D synchronized cohort ownership.
3. Full Iris takes over poll ownership and delivery ownership.
4. v0.1 daemon is disabled after parity verification.
5. Receipt format and routing semantics remain portable so historical logs survive the cutover.

Portability rule per §3I.7:

- code stays host-agnostic
- configuration is environment-driven
- state is limited to a replaceable local idempotency file in v0.1 only
- migration to full Iris is supervisor swap plus routing-scope expansion, not a rewrite

## 9. Build Shape For Titan

Minimum CT-0427-73 deliverables:

- one `iris_v0_1.py` daemon using `dep_watcher.py` / `titan_telnyx_watcher.py` operational patterns
- one queue polling function
- one Titan claim path
- one Achilles delivery path
- one idempotency state module
- one dead-letter write path
- one logrotate file
- one read-only verification mode

## 10. Acceptance Criteria

1. Iris v0.1 polls MCP on a 3-minute cadence.
2. Queue reads filter for `approval=pre_approved` before delivery.
3. Routing splits cleanly by `assigned_to=titan` versus `assigned_to=manual` plus Achilles-targeting tags.
4. Titan-path delivery prefers direct `claim_task`.
5. Achilles-path delivery uses Mac webhook or direct file drop without Solon acting as relay.
6. Idempotency is enforced with `sha1(task_id + approval_timestamp)` in `/var/lib/amg-iris/delivered_state.json`.
7. Every successful delivery writes `log_decision(project_source="iris_v0_1", tags=["mail_delivered", "<task_id>", "<recipient>"])`.
8. MCP unreachable paths back off and log honestly instead of claiming success.
9. Recipient unreachable paths dead-letter to `mcp_dead_letter`.
10. Weekly logrotate with 4-week retention and `copytruncate` is specified.
11. The next eligible pre-approved task is claimed or delivered within 3 minutes of becoming claimable.
12. v1.0 absorption path is explicit: v0.1 retires when chief-team Iris cohort takes over.

## 11. Self-Score

| Dimension | Score | Note |
|---|---:|---|
| Technical soundness | 9.2 | Matches current queue/API surfaces and keeps routing narrow. |
| Completeness | 9.1 | Covers cadence, filters, routing, idempotency, receipts, self-heal, and migration. |
| Queue honesty | 9.4 | Explicitly handles claim conflicts and queued-vs-approved mismatch without false success. |
| Operational safety | 9.2 | Dead-letter and bounded backoff prevent silent loss. |
| Titan build readiness | 9.1 | Concrete enough to build directly from watcher patterns. |
| Migration clarity | 9.0 | Clean bridge from v0.1 to full Iris cohort. |

Overall: 9.17/10.
