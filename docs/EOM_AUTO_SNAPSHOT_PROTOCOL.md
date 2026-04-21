# EOM Auto Snapshot Protocol

Date locked: 2026-04-20
Status: Active protocol with helper-backed support; not yet transport-enforced

## Purpose

Every 10 turns, EOM and Achilles should write a durable `conversation_snapshot` to MCP so the memory loop stays recoverable even if a thread dies, a window closes, or a handoff crosses builders.

## What counts as a turn

- A turn is one visible chat message in the working thread, regardless of sender.
- Count continuously across both sides of the conversation.
- Fire a snapshot at turns 10, 20, 30, and so on.
- If the session ends early, also fire a final snapshot on power-off or handoff when 5 or more turns have elapsed since the last snapshot.

## Required snapshot payload

Every snapshot must include:

- Thread label or short context identifier
- Turn window covered, for example `1-10` or `31-40`
- Current objective
- Decisions made in that window
- Blockers or risks
- Open loops still in motion
- Artifact paths, deploy targets, or commit hashes created in that window
- The single next action

Tag every write with `conversation_snapshot`.

## Lane-specific meaning

### Achilles

Use `project_source=achilles` when the thread is execution-heavy and the snapshot is meant to preserve concrete build state. Achilles snapshots should bias toward:

- file paths
- services touched
- deploy state
- MCP writes completed
- exact blockers and next commands

### EOM

Use `project_source=EOM` when the thread is acting as architect, router, or doctrine owner. EOM snapshots should bias toward:

- strategic decisions
- routing choices
- approvals needed
- delegation state
- next coordination move

## What was built tonight

The following helper support now exists in the canonical harness repo:

- `vps-scripts/mcp-common.sh`
  - new `mcp_format_conversation_snapshot`
  - new `mcp_log_conversation_snapshot`
- `vps-scripts/log-conversation-snapshot.sh`
  - standard wrapper with `--project`, `--actor`, `--thread`, `--turn-window`, `--tags`, and `--dry-run`
- `CLAUDE.md`
  - protocol clause added so Achilles sessions see the rule in their operating contract

## Current limitation

This rule is still not hard-enforced by the chat transport itself because the current bridge/session runtime does not expose a trustworthy per-thread turn counter hook. The protocol is therefore:

- behaviorally mandatory for EOM and Achilles
- helper-assisted through the new wrapper
- ready for future hard enforcement once a thread-turn hook exists

## Standard invocation

```bash
cat /tmp/snapshot.txt | /opt/titan-harness/vps-scripts/log-conversation-snapshot.sh \
  --project achilles \
  --actor Achilles \
  --thread "Achilles overnight run 2026-04-20" \
  --turn-window "11-20"
```

## Dry-run check

```bash
cat /tmp/snapshot.txt | /opt/titan-harness/vps-scripts/log-conversation-snapshot.sh \
  --project EOM \
  --actor EOM \
  --thread "Router session" \
  --turn-window "1-10" \
  --dry-run
```
