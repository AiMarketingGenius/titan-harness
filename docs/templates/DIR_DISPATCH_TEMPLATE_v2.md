# DIR Dispatch Template v2

Use for all future CLASS_A dispatches. Step 0 is mandatory and happens before claim, implementation, or ship language.

## Header

```text
# DISPATCH — <DIR-ID>
## <Title>
Authorized: <ISO8601> | EOM | <approval> | <priority> | <class>

Task ID:
Owner:
Host:
Project:
Dependencies:
Estimated effort:
```

## Step 0 — Packet / Reality Verification

Mandatory before claim.

The receiving agent must verify the packet against live state and log the result before executing. This prevents stale packet assumptions, missing artifacts, wrong owners, and false green claims.

### 0.1 Queue Truth

- Query `op_task_queue` for the task id.
- Verify `status`, `approval`, `assigned_to`, `locked_by`, `claimed_at`, `tags`, and notes.
- If packet says pre_approved but queue does not, queue wins.
- If packet says blocked but queue has newer EOM override, queue notes must be cited.

### 0.2 Dependency Truth

- Verify every named dependency by MCP tag or direct endpoint.
- For tags, query `op_decisions`.
- For services, run health endpoints or read-only status checks.
- If dependency state shifted, inline the delta in claim log.

### 0.3 Owner / Host Boundary

- Confirm the task belongs to this agent and host.
- Titan owns VPS infra, systemd, n8n, Redis, MCP server deploys, Postgres.
- Achilles owns Mac harness, browser courier, doctrine/design, audit/control tower.
- Cross-host destructive work requires dual signoff in MCP.

### 0.4 Artifact Path Reality

- Verify every source file, target file, and output directory exists or can be created.
- If target path is unavailable, log a path delta and use an approved staging fallback.
- Never claim an artifact was written to an unavailable path.

### 0.5 Worktree And Dirty-State Window

- Run `git status --short --branch`.
- Classify existing dirty files before edits.
- Do not overwrite or revert unowned changes.
- If dirty-state-window work is being audited, HIGH findings require co-verifier.

### 0.6 Mirror / SHA Truth

- Verify current local SHA.
- Verify configured remote SHA when a mirror claim is required.
- If multiple remotes are claimed, list each SHA.
- Never claim a mirror leg that was not checked.

### 0.7 Live Behavior Probe

- For code/server work, run the smallest live read-only or synthetic probe before implementation.
- Capture exact response or command output.
- If packet acceptance depends on an endpoint behavior, test that behavior directly.

### 0.8 Acceptance Delta

- Compare packet acceptance criteria to live behavior.
- List any criterion now impossible, already satisfied, or requiring different owner.
- If any criterion is impossible without cross-host work, queue blocker and do not fake ship.

### Step 0 Log

Required MCP decision tag:

```text
<dir_id>_step0_verified
```

Log must include:
- queue row summary
- dependency evidence
- owner/host confirmation
- artifact path check
- worktree summary
- mirror/SHA check if relevant
- live probe output
- acceptance deltas
- claim or blocker decision

## Objective

State one measurable outcome.

## Scope

In scope:
- item

Out of scope:
- item

## Execution Plan

1. Step
2. Step
3. Step

## Acceptance Criteria

- [ ] Criterion with direct verification method.
- [ ] Criterion with file path / endpoint / log tag.
- [ ] Rollback or no-op behavior verified.

## Test Plan

Commands/probes:

```bash
<command>
```

Expected result:

```text
<output or invariant>
```

## Rollback

Describe exact rollback, owner, and safety limits.

## Reporting

Required logs:
- `<dir_id>_step0_verified`
- `<dir_id>_shipped` or `<dir_id>_blocked`

Ship log must include:
- commit SHA if files changed
- test output
- path deltas
- unresolved risks
- follow-up task ids

## Prohibitions

- No force-push unless explicitly approved.
- No cross-host destructive ops without dual signoff.
- No protected Voice AI asset touches.
- No banned vendor API calls in factory paths.
- No partial ship language for all-or-nothing acceptance.

