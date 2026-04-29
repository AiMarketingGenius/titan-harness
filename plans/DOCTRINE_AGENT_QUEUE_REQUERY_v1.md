# DOCTRINE — Agent Queue Re-Query Hooks v1

**Status:** Active. Mandatory for Titan + Achilles + every agent provisioned by DIR-005 Phase E onboarding template.
**Effective:** 2026-04-29 (CT-0428-40 / CT-0429-04 / DIR-009 Phase 1).
**Owner:** Titan harness; Achilles harness mirrors.
**Parent task:** CT-0429-04 (DIR-009).

## Why this exists

Agents drift when they trust the in-context sprint plan over MCP `operator_task_queue`. The drift class is "did agent see new task?" — Solon queues an urgent task mid-session; the agent finishes the current ship and starts the *next planned* item instead of the *new authoritative top of queue*. Doctrine alone (CLAUDE.md §13.1b mandatory poll triggers) reduces drift but can't eliminate it because doctrine relies on agent discipline.

These hooks make the re-query mechanical: every session start AND every ship event triggers a Supabase pull → `NEXT_TASK.md` rewrite. The agent always reads the live queue before the next claim cycle.

## Hook contract

### `hooks/session-start.sh`

- Fires on every Claude Code `SessionStart` (cold boot, not mid-session resume).
- After `titan_local_audit SESSION_START`, calls `lib/queue_requery.py --agent <name> --output ~/<name>-session/NEXT_TASK.md`.
- Failure is non-fatal — `claim_task` is still authoritative.

### `hooks/post-ship.sh`

- Fires after every `log_decision` whose tag matches `*_shipped|*_complete|*_done`.
- Same `lib/queue_requery.py` call. Re-writes `NEXT_TASK.md` so the next claim cycle reads fresh state.
- Idempotent. Safe to call multiple times per ship.
- Logs to `~/<name>-session/post-ship-hook.log`.

### `lib/queue_requery.py`

- Stdlib only. Reads `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` from the env loaded by `lib/titan-env.sh`.
- Queries `operator_task_queue`:
  - `assigned_to=eq.<agent>`
  - `status in (queued, locked)`
  - sorted urgent → high → normal → low, oldest-first within priority.
- Filters claim-ready rows: `approval=pre_approved AND status in (queued, locked)`.
- Writes atomic temp+rename to `<output>` (no partial reads).
- Exit 0 on success, 1 on missing env, 2 on fetch failure.

## NEXT_TASK.md format

```
# NEXT_TASK — <agent>

**Refreshed:** <ISO8601 UTC>
**Source:** MCP operator_task_queue

## TOP — claim this next
### `CT-XXXX-NN` — priority=urgent
- status: `queued` / approval: `pre_approved` / locked_by: `(unlocked)`
- tags: tagA, tagB
**Objective:** ...

## Full claim-ready queue
- `CT-...` ...

## All assigned (any status)
- `CT-...` ...
```

The agent's claim-cycle MUST consult `NEXT_TASK.md` before issuing a new `claim_task` call. If the file's "TOP" task differs from the agent's in-context plan, the queue wins.

## Universal application — DIR-005 Phase E onboarding template

Every new agent provisioned by `plans/agents/onboarding-template/` (or its DIR-005 successor) receives:

1. `hooks/session-start.sh` — invokes `queue_requery.py` with `--agent <new_agent_name>`.
2. `hooks/post-ship.sh` — same hook contract.
3. `lib/queue_requery.py` — copied from titan-harness or symlinked to a shared library path.
4. `~/${agent}-session/` directory created at first boot.
5. Smoke test — see below — runs once at provisioning to prove the hook fires.

Mandatory section in the onboarding template: **"Agent Queue Re-Query Hooks (REQUIRED)"** referencing this doctrine doc.

## Smoke test protocol

Per agent at provisioning, and once per quarter for every live agent:

1. With the agent session active, queue a synthetic urgent task via MCP:
   ```
   mcp queue_operator_task agent=<agent> priority=urgent
     objective="queue_requery smoke probe"
     approval=pre_approved tags="smoke,queue_requery_v1"
   ```
2. Trigger any `*_shipped` log_decision in the agent's session (or wait <60s for next session start).
3. Assert: `~/<agent>-session/NEXT_TASK.md` "TOP" block lists the synthetic task within 60 seconds.
4. Have the agent run a claim cycle. Assert: agent picks up the synthetic task, not whatever was next on the in-context plan.
5. Mark synthetic task `done` and assert next refresh removes it from the file.
6. log_decision tag `queue_requery_smoke_<agent>_pass` with timestamps + observed latency.

A failed smoke test → flag_blocker P1 + halt agent provisioning until repaired.

## Cross-agent applicability matrix

| Agent | Status | Hook source |
|---|---|---|
| titan | LIVE 2026-04-29 (DIR-009 Phase 1) | `~/titan-harness/hooks/` |
| achilles | LIVE 2026-04-29 (DIR-009 Phase 1) | `~/achilles-harness/hooks/` (mirrored from titan) |
| Harmonia / Metis / Sentinel / Argus / Hermes / Chronicler / Hephaestus | Pending DIR-005 Phase E provisioning | Inherits at build time |
| Sonar-Replica / Reasoning-Judge | Pending DIR-005 / DIR-008 Phase 3 | Inherits at build time |
| Mnemosyne / Atlas-CRM / Hermes-Mobile / Echo | Pending DIR-008 Phase 3 | Inherits at build time |
| Rally | Pending DIR-008 Phase 4 | Inherits at build time |

## Failure modes + fallbacks

- **Supabase unreachable:** `queue_requery.py` writes a stale-warning header to `NEXT_TASK.md`. Agent's next `claim_task` MCP call still hits the live queue authoritatively — the file is a hint, not a source of truth.
- **`lib/titan-env.sh` missing on a new agent harness:** queue_requery exits 1 with an in-file ERROR header; smoke fails; provisioning halts.
- **Hook script missing entirely:** session-start.sh logs the absence; agent still functions but loses the mechanical guarantee — Warden re-queue cycles will catch the drift within 90min.

## Doctrine relationships

- Implements CLAUDE.md §13.1b (MCP poll cadence) at the harness layer rather than the agent-discipline layer. The doctrine survives any single agent forgetting to poll.
- Replaces the implicit "Solon nudges agent on Slack when a new urgent task lands" pattern with a mechanical pull.
- Compatible with `bin/titan-boot-audit.sh` resume-source priority (§7) — the hook fires *after* the boot audit has already decided which RESUME_SOURCE to honor.

## Change log

- v1.0 — 2026-04-29 — Initial ship under CT-0428-40 / DIR-009 Phase 1 / CT-0429-04. Titan + Achilles harnesses mirrored; doctrine doc filed.
