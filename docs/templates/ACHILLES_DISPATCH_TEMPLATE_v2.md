# Achilles Dispatch Template v2

Use for Achilles-owned CLASS_A Mac harness, courier, audit, doctrine, and design dispatches.

## Header

```text
# ACHILLES DISPATCH — <DIR-ID>
## <Title>
Authorized: <ISO8601> | EOM | <approval> | <priority> | <class>

Task ID:
Owner: Achilles
Host: Mac
Project:
Dependencies:
Estimated effort:
```

## Mandatory Step 0 — Packet / Reality Verification

Achilles must complete and log Step 0 before claim or execution.

### 0.1 MCP Queue Reality

Check:
- task id exists
- `approval=pre_approved` or explicit override exists
- status is claimable
- no conflicting lock
- tags match packet
- notes do not supersede packet text

If Achilles work is assigned to `manual`, verify an `achilles_execute` tag or explicit EOM instruction.

### 0.2 Claim-Cycle Reality

Run or verify:

```bash
AchillesControl/sessionstart_claim_hook.sh
python3 scripts/write_next_task.py --assigned-to achilles --output /tmp/achilles-next-task.md --force
```

Confirm the rendered task matches the dispatch. If not:
- diagnose override files
- diagnose assignment filters
- diagnose priority ordering
- diagnose missing claim tool
- log `achilles_claim_cycle_diagnostic_complete`

### 0.3 Capacity Reality

Run:

```bash
bin/check-capacity.sh
bin/harness-preflight.sh
```

If hard-blocked:
- identify top processes
- do not kill active Solon desktop, Voice AI, Ollama, or unknown critical processes
- proceed only with light read/doc work
- defer heavy browser/courier work

### 0.4 Artifact And Path Reality

For every requested path:
- verify path exists or can be created
- if `/mnt/user-data/outputs` is unavailable on Mac, stage in repo `outputs/` and log path delta
- never claim exact-path completion when the path was unavailable

### 0.5 Worktree Reality

Run:

```bash
git status --short --branch
```

Rules:
- classify unowned dirty files
- do not revert user/other-agent work
- stage/commit only files owned by the current task
- record stash labels if preserving prior work

### 0.6 Browser/Profile Reality

For courier work:
- verify `~/.amg/courier/selectors.yaml`
- verify dependency runtime
- verify persistent profile path per judge
- verify session state before smoke
- if any judge lacks a valid session, mark blocked; partial courier ship is forbidden

### 0.7 Server Reality

For gate/courier work:
- verify `/api/judgments/submit`
- verify `/api/judgments/:id/score`
- verify `/api/judgments/:id/finalize`
- run the smallest synthetic probe matching acceptance
- if server behavior contradicts packet, queue Titan-owned blocker

### 0.8 Acceptance Delta

List:
- criteria already green
- criteria blocked by Titan-owned infra
- criteria blocked by missing profile/session
- criteria impossible due path/host mismatch
- adapted path

## Step 0 MCP Log

Required tag:

```text
<dir_id>_step0_verified
```

If claim-cycle itself is the task, also log:

```text
achilles_claim_cycle_diagnostic_complete
```

## Objective

One measurable outcome.

## Achilles Lane Boundaries

Achilles may:
- edit Mac harness code
- manage Mac launchd/Hammerspoon harness files
- build doctrine/design/audit artifacts
- run browser courier on Mac profiles
- log and queue MCP tasks

Achilles may not:
- deploy MCP server routes on VPS
- restart VPS services
- patch Postgres/n8n/Redis without Titan signoff
- touch protected Voice AI or Ollama assets
- force-push

## Execution Steps

1. Step
2. Step
3. Step

## Acceptance Criteria

- [ ] Criterion with direct evidence.
- [ ] Criterion with command/probe output.
- [ ] Criterion with MCP tag.

## Reporting

Required:
- Step 0 log
- checkpoint every 15 minutes for long execution
- final `<dir_id>_shipped` or `<dir_id>_blocked`

Ship log includes:
- commit SHA
- tests
- smokes
- path deltas
- blockers/follow-up task ids

## Rollback

Define the smallest safe rollback. For courier work, manual paste resumes if automated gate fails.

