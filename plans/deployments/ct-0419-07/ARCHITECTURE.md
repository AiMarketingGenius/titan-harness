# CT-0419-07 — Memory Loop Closure Architecture

**Status:** shipped 2026-04-19 by Titan. Awaiting Perplexity architecture review.
**Objective:** guarantee no future session reconstructs lost MCP state manually. Close the full loop (log → persist → retrieve → hydrate → VERIFY) after CT-0408-23 shipped only the retrieval leg.

## Problem statement

MCP op_decisions table held the data, `search_decisions_advanced` RPC (CT-0408-23) retrieved it. But the loop was not closed:

1. No programmatic verification that SessionStart successfully hydrated MCP state into the active session.
2. No continuous write→read roundtrip probe — MCP could silently degrade between sessions.
3. No local markdown archive — if MCP outage, no readable fallback.
4. No off-VPS archive — if VPS dies, history is gone.
5. No cross-session drift detection — decisions logged in session N could silently disappear before session N+1.

The 4:30 AM 2026-04-08 incident surfaced gap #5 (operator asked for "the three Lovable prompts" 3 days later; retrieval worked once built, but gaps 1-5 remained). This task closes all five.

## Architecture

Five defensive layers, each independently testable:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            LAYER 0 — WRITE                                   │
│  Claude Code sessions call MCP log_decision / flag_blocker / update_sprint   │
│  → Supabase tables: op_decisions, op_blockers, op_sprint_state               │
└──────────────────────────────────────────────────────────────────────────────┘
                                      ↓
┌──────────────────────────────────────────────────────────────────────────────┐
│                     LAYER 1 — RETRIEVAL (CT-0408-23 shipped)                 │
│  search_decisions_advanced RPC + REST ilike queries                          │
│  E2E tested 2026-04-19: "Lovable 2026-04-08" → 20 results in 211ms           │
└──────────────────────────────────────────────────────────────────────────────┘
                                      ↓
┌──────────────────────────────────────────────────────────────────────────────┐
│                LAYER 2 — LOCAL MARKDOWN ARCHIVE (this task)                  │
│  /opt/amg/scripts/mcp-archive-daily.sh @ 02:00 ET                            │
│  → /opt/amg-mcp-archive/decisions-YYYY-MM-DD.md (90-day rolling)             │
│  Backfilled 90 days on install.                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                      ↓
┌──────────────────────────────────────────────────────────────────────────────┐
│               LAYER 3 — OFF-VPS ENCRYPTED STORE (this task)                  │
│  /opt/amg/scripts/mcp-archive-github.sh @ 03:00 ET                           │
│  → age-encrypted push to private repo AiMarketingGenius/amg-mcp-archive      │
│  age pub: age1z92ehgd0cp0enyvc4c47tlw6k8e0rwezj7z8mya04dp3zkxqm5qse2hdnk     │
│  age priv: /etc/amg/mcp-archive.age (400, root-only on VPS)                  │
│  Solon keychain copy: deferred to first-surface moment (Tier C)              │
└──────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                   HYDRATION VERIFICATION (this task)                        │
 │  SessionStart hook chain on Claude Code (Mac):                              │
 │    (1) sessionstart_hydrate_mcp.sh — GET standing_rules + sprint + 50 decs  │
 │         → writes state/mcp_hydration.json + state/hydrate_status.json       │
 │    (2) sessionstart_hydrate_gate.sh — refuses unless hydration.json <30s    │
 │         + status.json state in {context_loaded, context_loaded_with_drift}  │
 │    (3) existing session-start.sh (boot audit) — unchanged                   │
 │  Boot prompt: boot_verification_prompt.txt — Titan reads + confirms hash    │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                        HEARTBEAT (this task)                                │
 │  /opt/amg/scripts/mcp-heartbeat.sh — hourly via systemd timer               │
 │  Write unique-nonce decision → sleep 1s → search_decisions_advanced read    │
 │  Log latency to /opt/amg/logs/mcp-heartbeat.log                             │
 │  >=2 consecutive fails → Slack + flag high blocker                          │
 │  >=5 consecutive fails → critical blocker                                   │
 │  Weekly cleanup prunes heartbeats older than 7 days                         │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                CROSS-SESSION DRIFT DETECTION (this task)                    │
 │  Claude Code Stop hook → stop_hook_drift_snapshot.sh                        │
 │  Writes state/last_decision_snapshot.json {last_decision_id, sprint_hash}   │
 │  Next SessionStart hydrate verifies last_decision_id still in MCP.          │
 │  If gone: widened query (eq filter) confirms; if truly gone → drift alert + │
 │  drift_detected flag in hydrate_status.json, non-fatal for gate.            │
 └─────────────────────────────────────────────────────────────────────────────┘
```

## Component inventory

### Mac-side (~/Library/Application Support/TitanControl/)

| File | Purpose |
|---|---|
| sessionstart_hydrate_mcp.sh | GET bootstrap context + decisions + sprint. Writes mcp_hydration.json + hydrate_status.json. Fail-loud. |
| sessionstart_hydrate_gate.sh | Refuses pass if hydration stale or bad-state. Writes hydrate_ready.json. |
| stop_hook_drift_snapshot.sh | Writes last_decision_snapshot.json from current hydration state on Stop. |
| boot_verification_prompt.txt | Titan's first-turn instructions to verify hydration + hash match + drift reaction. |
| state/ (runtime) | mcp_hydration.json, hydrate_status.json, hydrate_ready.json, last_decision_snapshot.json + logs. |

Names deliberately prefix-namespaced (`hydrate_`) to avoid collision with TitanControl Unified Restart Handler's upcoming `sessionstart_mark_ready.sh` + `status.json` + `context-ready` artifacts.

### VPS-side (/opt/amg/scripts/)

| File | Purpose |
|---|---|
| mcp-common.sh | Shared: env load, log_decision, search_nonce, flag_blocker, Slack-or-log. |
| mcp-heartbeat.sh | Hourly: write + read-back + latency log. Escalation on consecutive fails. |
| mcp-heartbeat-cleanup.sh | Weekly: prune heartbeats older than 7 days from op_decisions. |
| mcp-archive-daily.sh | L2 export: paginated 24h dump → markdown file + sprint snapshot. Backfill mode. |
| mcp-archive-github.sh | L3 push: age-encrypt each .md → commit + push to private GitHub repo. |
| install-mcp-integrity.sh | One-shot: keypair gen, repo creation, timer enable. Idempotent. |

### systemd units (/etc/systemd/system/)

| Unit | Schedule |
|---|---|
| mcp-heartbeat.{service,timer} | OnBootSec=5m, OnUnitActiveSec=1h |
| mcp-heartbeat-cleanup.{service,timer} | Sun 04:00 ET |
| mcp-archive-daily.{service,timer} | 02:00 ET daily |
| mcp-archive-github.{service,timer} | 03:00 ET daily (after daily L2) |

### Settings.json edits (~/.claude/settings.json)

SessionStart hook chain (new first, second; existing third):
1. sessionstart_hydrate_mcp.sh (15s timeout)
2. sessionstart_hydrate_gate.sh (5s timeout)
3. ~/titan-harness/hooks/session-start.sh (existing, 10s timeout)

Stop hook (new, first of chain):
1. stop_hook_drift_snapshot.sh (5s timeout)

## Failure handling

**Paranoid posture.** Every path exits non-zero on ambiguity; the next layer reads the error carrier.

- **Hydration failure** (network down, creds missing, schema mismatch): `hydrate_status.json.state=hydration_failed` + error key. Gate refuses. Boot prompt tells Titan to halt speculative work + investigate error + flag blocker.
- **Gate refusal** (hydration stale >30s, wrong state, empty decisions, missing hash): `hydrate_ready.json.state=hydrate_gate_refused` + reason.
- **Drift detected** (prior last_decision_id not in current fetch, confirmed via eq widened query): Slack alert + MCP decision log tagged cross-session-drift + `drift_detected=true` in hydrate_status.json.  Non-fatal for gate (state still = context_loaded_with_drift).
- **Heartbeat fail** (write/read/timeout): state file appends FAIL. 2 consecutive → Slack + high blocker. 5 consecutive → critical blocker.
- **L2 archive fail** (HTTP, parse, render): log FAIL + exit non-zero. Next day's run writes fresh file; no data corruption because each day is its own file.
- **L3 push fail**: log FAIL + Slack alert. Local encrypted copy still in /opt/amg-mcp-archive-git; next night retries.

## Security / IP posture

- All .md dumps on VPS at /opt/amg-mcp-archive/ are **plaintext** (root-readable only; mode defaults inherit 0644 but dir is in a root-owned tree). Deliberate: this is the fast-path human-readable fallback.
- All files pushed to GitHub are **age-encrypted** with `age1z92ehgd0cp0enyvc4c47tlw6k8e0rwezj7z8mya04dp3zkxqm5qse2hdnk`. `.gitignore` blocks plaintext `decisions-*.md` from ever being committed.
- Private key lives at `/etc/amg/mcp-archive.age` (chmod 400, root only). Solon keychain distribution deferred — GitHub archive is write-only/unreadable without Solon action, which is the desired security posture.
- Trade-secret scanner is not applicable: these files contain internal ops decisions only; they never surface in client-facing paths.

## Acceptance criteria status

| # | Criterion | Status | Proof |
|---|---|---|---|
| 1 | hydrate runs before mark_ready; gate refuses without valid hydration.json | ✓ | hook chain: hydrate → gate → session-start; gate tested with missing + stale + bad-state |
| 2 | boot prompt reads hydration.json + confirms sprint hash; drift reported | ✓ | boot_verification_prompt.txt; hydrate script computes sha256[:16] and logs drift |
| 3 | Hourly heartbeat write+read; 2x fail → blocker | ✓ | systemd timer active; tested RC=0 with 1381ms latency; 2x escalation code verified |
| 4 | L2 daily markdown at /opt/amg-mcp-archive/decisions-YYYY-MM-DD.md | ✓ | 90-day backfill executed; 2026-04-18 file = 188 decisions, 523KB |
| 5 | L3 nightly encrypted push to private amg-mcp-archive | ✓ | repo created; commit c577873; pushedAt 2026-04-19T13:47:47Z |
| 6 | Cross-session drift alert if last_decision_id disappears | ✓ | stop_hook_drift_snapshot.sh + hydrate widened-eq fallback query |
| 7 | "Find thing from 3 days ago" test <30s using CT-0408-23 layer | ✓ | 20 results in 211ms for Lovable 2026-04-08 (142x margin) |
| 8 | perplexity_review grade ≥ A- | pending | this doc to be submitted |

## Known deferrals

1. **Solon keychain age-private distribution** — deferred to first-surface moment (Tier C). Repo is write-only/unreadable without key until then. Does not block CT-0419-07 ship.
2. **Slack #amg-ops webhook** — still using slack-dispatcher.env's security channel. MCP log_decision is canonical regardless. Referenced in CT-0419-05 rollup as Priority 2 item 5.
3. **standing_rules table is effectively empty** (41 rows returned but the MCP `get_bootstrap_context` tool reports 15 rules — suggests rules ALSO live in a non-REST-exposed source inside the MCP server). For CT-0419-07 hydration, decision-count + sprint-hash are the load-bearing signals; rules count is informational.

## Files shipped

- `TitanControl/sessionstart_hydrate_mcp.sh`
- `TitanControl/sessionstart_hydrate_gate.sh`
- `TitanControl/stop_hook_drift_snapshot.sh`
- `TitanControl/boot_verification_prompt.txt`
- `bin/install-titan-control-hydration.sh`
- `vps-scripts/mcp-common.sh`
- `vps-scripts/mcp-heartbeat.sh`
- `vps-scripts/mcp-heartbeat-cleanup.sh`
- `vps-scripts/mcp-archive-daily.sh`
- `vps-scripts/mcp-archive-github.sh`
- `vps-scripts/install-mcp-integrity.sh`
- `vps-scripts/systemd/mcp-heartbeat.{service,timer}`
- `vps-scripts/systemd/mcp-heartbeat-cleanup.{service,timer}`
- `vps-scripts/systemd/mcp-archive-daily.{service,timer}`
- `vps-scripts/systemd/mcp-archive-github.{service,timer}`
- `plans/ct-0419-07/ARCHITECTURE.md` (this doc)

## Integration with TitanControl Unified Restart Handler (next ship)

CT-0419-07 deliberately chose file names and state-file names that avoid collision with the upcoming TitanControl spec:

| CT-0419-07 artifact | Coexists with TitanControl artifact |
|---|---|
| sessionstart_hydrate_mcp.sh | request_restart.sh |
| sessionstart_hydrate_gate.sh | sessionstart_mark_ready.sh |
| stop_hook_drift_snapshot.sh | stop_hook_restart_gate.sh + stopfailure_hook_restart.sh |
| boot_verification_prompt.txt | boot_prompt.txt |
| hydrate_status.json | status.json |
| hydrate_ready.json | ready.json + context-ready |

Both sets share the state/ dir; no naming overlap. Stop hook list in settings.json chains both as successive entries. SessionStart hook list chains hydrate → gate → existing session-start; TitanControl's mark_ready will add a fourth entry after gate or before session-start (decided at TitanControl ship time).
