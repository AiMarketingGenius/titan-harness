# ACHILLES INBOX DAEMON v0.1

**Target canonical path:** `/opt/amg-docs/architecture/ACHILLES_INBOX_DAEMON_v0_1.md`
**Staged path:** `/Users/solonzafiropoulos1/titan-harness/docs/architecture/ACHILLES_INBOX_DAEMON_v0_1.md`
**Owner:** Achilles, CT-0427-82
**Status:** Ship-ready build spec for the Mac-side mailbox courier that claims Achilles work from MCP and wakes the harness without Solon acting as middleware.

## 1. Scope

Achilles Inbox Daemon v0.1 is a Mac-side `launchd` daemon that runs every 3 minutes and does one narrow job:

- poll MCP for Achilles-eligible pre-approved work
- claim the task atomically
- write a local execution marker
- trigger the existing Achilles session-launch path so the harness starts working

This daemon does not:

- introduce chief-team routing
- manage builder dispatch
- replace Iris v1.0
- mutate queue schema in v0.1

It is a bridge component that removes the last "Solon nudge Achilles manually" dependency.

## 2. Routing Decision

### Recommendation

Keep `assigned_to=manual` and filter by Achilles-targeting tags in v0.1.

### Rationale

This is the lowest-risk option for the current stack:

- MCP queue surfaces already use `assigned_to in {titan, manual, n8n}`.
- Current bridge code validates only those enum values.
- Adding `assigned_to=achilles` requires MCP schema/client changes before the daemon even exists.
- Tag filtering is already doctrinally normal for agent ownership in the broader harness.

### Required filter contract

The daemon polls:

- `get_task_queue(status=approved)`

Then filters client-side to rows where:

- `approval=pre_approved`
- `assigned_to=manual`
- tags contain one of:
  - `achilles`
  - `achilles_spec`
  - `achilles_dispatch`
  - `owner:achilles`

If a future MCP revision adds `assigned_to=achilles`, that becomes a v1.0 simplification, not a v0.1 prerequisite.

## 3. Harness Wake Mechanism

### Recommendation

Use a local marker file plus the existing Achilles restart flag / autorestart launcher, not direct CLI invocation and not a named pipe.

### Why this fits the current harness

The current repo already has the right primitives:

- `bin/achilles-restart-launch.sh` consumes `~/.claude/achilles-restart.flag`
- `com.amg.achilles-autorestart.plist` is the existing launchd relaunch path
- the launch script already opens Terminal/iTerm/tmux and runs `codex` from `~/achilles-harness`

That means v0.1 does not need to invent a second session-launch system. It should just feed the one that exists.

### Concrete wake flow

1. Daemon claims `CT-...` from MCP.
2. Daemon writes a task marker bundle to:
   - `~/.achilles-daemon/pending/<task_id>.json`
3. Daemon touches:
   - `~/.claude/achilles-restart.flag`
4. Existing launchd autorestart path spawns or resumes the harness session.
5. Boot/resume logic sees the local marker and/or MCP lock and begins execution.

### Why not the alternatives

- Direct CLI invocation like `achilles execute --task=<id>`: no stable Achilles-specific CLI entrypoint is present today.
- Named pipe: more fragile, unnecessary on macOS for this use case, and adds a second process-coordination surface.
- Pure harness-side polling loop with no daemon wake: reintroduces latency and requires the session to already be open.

## 4. Iris v0.1 Integration

### Recommendation

Drop the file-drop delivery path for Achilles and have Iris use the same `claim_task`-first queue path conceptually used for Titan, with the Achilles Inbox Daemon handling local wake after claim.

### Why

One queue truth is cleaner than dual delivery surfaces:

- MCP already tracks approval, locking, and result state.
- File-drop duplicates routing state and risks drift.
- Claim semantics are already how Titan-side automation works.
- Achilles v0.1 only needs a local wake marker after claim, not a second mailbox as source of truth.

### Required Iris v0.1 delta

For Achilles-directed tasks:

- keep queue row in MCP as source of truth
- do not depend on `/opt/amg-titan/achilles-inbox/` file drops
- let the Achilles Inbox Daemon poll/claim
- after claim, local marker + restart flag wake the harness

If file-drop must temporarily remain for compatibility, it is debug-only and non-authoritative. MCP lock state wins.

## 5. Idempotency

State file:

- `~/.achilles-daemon/state.json`

Key:

- `sha1(task_id + claim_timestamp)`

Tracked fields:

- `task_id`
- `claim_key`
- `claimed_at`
- `wake_triggered_at`
- `marker_path`
- `status`

Rules:

- same `claim_key` may not wake twice
- writes must be atomic via temp-file + rename
- if the daemon restarts mid-run, state replay must avoid duplicate wake calls

## 6. Dead-Letter And Failure Handling

If MCP is unreachable:

- bounded retry within the current run
- no fake claim success
- log degraded receipt

If claim succeeds but local marker write fails:

- do not mark the task complete
- write dead-letter record locally and to MCP notes/decision log

If restart flag touch succeeds but harness launch appears not to happen:

- leave task locked
- emit blocker after one retry cycle
- require manual inspection of `~/.claude/achilles-restart.log`

Dead-letter local path:

- `~/.achilles-daemon/dead-letter/<task_id>.json`

## 7. Receipt Format

On successful pickup:

- `log_decision(project_source="achilles_inbox_daemon", decision_text="claimed + executing <task_id>", tags=["mail_picked_up", "<task_id>"])`

Minimum rationale payload:

- claim timestamp
- filter reason
- marker path
- wake mechanism used

Failure tags:

- `mail_pickup_failed`
- `<task_id>`

## 8. Launchd Manifest

Manifest path:

- `~/Library/LaunchAgents/com.amg.achilles-inbox.plist`

Required properties:

- interval: `180` seconds
- program: `~/achilles-harness/bin/achilles-inbox-daemon.sh` or equivalent Python entrypoint
- stdout/stderr:
  - `~/Library/Logs/amg-achilles-inbox.log`

Behavior:

- fast one-shot run
- no long-lived resident loop
- safe to re-enter every 180 seconds

## 9. Deployment Portability (§3I.7)

This daemon is intentionally transitional.

Portability rules:

- code remains portable Python/shell with env-driven paths
- queue truth stays in MCP
- local state is minimal and replaceable
- the daemon retires when Iris v1.0 + chief routing absorb the wake/delivery function in Phases 4-5

Retirement contract:

1. Iris/chief-routing path can claim Achilles work directly.
2. Harness wake becomes part of the unified chief-routing substrate.
3. Local marker/restart shim is removed after parity validation.

## 10. Acceptance Criteria

1. Daemon polls every 3 minutes via `launchd`.
2. MCP is the source of truth for Achilles pickup.
3. v0.1 keeps `assigned_to=manual` and filters by Achilles tags rather than changing the enum immediately.
4. The daemon uses `claim_task` before any wake action.
5. Claimed work writes a local marker bundle under `~/.achilles-daemon/pending/`.
6. Wake mechanism uses the existing Achilles restart flag / launchd autorestart path.
7. Idempotency is enforced with `sha1(task_id + claim_timestamp)`.
8. Successful pickup emits `project_source=achilles_inbox_daemon` receipt logs.
9. Local dead-letter path exists for claim/write/wake failures.
10. The design states the exact Iris v0.1 change: MCP claim path authoritative, file-drop non-authoritative or removed.
11. Any pending Achilles task with `approval=pre_approved` can be claimed and trigger harness execution within 3 minutes.

## 11. Self-Score

| Dimension | Score | Note |
|---|---:|---|
| Technical soundness | 9.2 | Reuses the existing autorestart/launchd path instead of inventing another session runner. |
| Completeness | 9.1 | Covers polling, routing, wake, idempotency, dead-letter, manifest, and retirement path. |
| Queue honesty | 9.4 | Keeps MCP as the only authoritative state and demotes file-drop. |
| Operational fit | 9.3 | Matches `achilles-harness` HEAD `1e7ac3a` session-control reality closely. |
| Migration clarity | 9.1 | Cleanly hands off to Iris v1.0 / chief routing later. |
| Safety | 9.2 | Failures are explicit and idempotent rather than silently retried forever. |

Overall: 9.22/10.
