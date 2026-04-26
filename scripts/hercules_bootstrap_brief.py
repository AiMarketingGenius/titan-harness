#!/usr/bin/env python3
"""
hercules_bootstrap_brief.py — auto-generated paste-block for Hercules's
Kimi web tab.

Solves Solon's pain: "I have to keep injecting context every time I restart
Hercules in the Kimi tab." This script regenerates a single markdown file
at ~/AMG/HERCULES_BOOTSTRAP.md with the latest factory state. Solon opens
the Kimi tab, opens this file, pastes its contents into the chat, and
Hercules-in-tab is fully hydrated.

The Hercules DAEMON (scripts/hercules_daemon.py) doesn't need this — it
hydrates from MCP automatically. This is purely for the human-driven
chat-tab path when Solon WANTS to converse with Hercules directly.

Run modes:
    hercules_bootstrap_brief.py           one-shot regen, exit
    hercules_bootstrap_brief.py --watch   regen every 5 min (cron-friendly)

Cron suggestion (already wired in launchd plist com.amg.hercules-bootstrap):
    every 300s, run --once

Output file: ~/AMG/HERCULES_BOOTSTRAP.md (overwritten each run)
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))

from mcp_rest_client import (  # noqa: E402
    get_recent_decisions as mcp_get_recent,
    get_sprint_state as mcp_get_sprint,
    get_task_queue as mcp_get_task_queue,
)

OUT_FILE = HOME / "AMG" / "HERCULES_BOOTSTRAP.md"
LOGFILE = HOME / ".openclaw" / "logs" / "hercules_bootstrap_brief.log"


def _log(msg: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).isoformat()
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def _safe(s: str | None, n: int = 200) -> str:
    if not s:
        return ""
    return str(s).replace("\n", " ").strip()[:n]


def _git_recent_commits() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(HOME / "titan-harness"), "log", "--oneline", "-5"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else "(git error)"
    except Exception:
        return "(git unavailable)"


def _daemon_health() -> dict:
    """Quick launchctl check of the always-on daemons."""
    try:
        out = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode != 0:
            return {"error": "launchctl failed"}
        lines = out.stdout.splitlines()
        wanted = [
            "com.amg.hercules-daemon",
            "com.amg.hercules-mcp-bridge",
            "com.amg.hercules-dispatch-receiver",
            "com.amg.mercury-executor",
            "com.amg.mercury-mcp-notifier",
            "com.amg.mercury-folder-sync",
            "com.amg.aletheia-verify",
            "com.amg.cerberus-security",
            "com.amg.warden-enforcer",
        ]
        status = {}
        for w in wanted:
            for line in lines:
                if w in line:
                    parts = line.split()
                    pid = parts[0] if parts else "?"
                    exit_code = parts[1] if len(parts) > 1 else "?"
                    status[w] = {"pid": pid, "exit": exit_code,
                                  "alive": pid != "-" and pid != "?"}
                    break
            else:
                status[w] = {"pid": "-", "exit": "-", "alive": False}
        return status
    except Exception as e:
        return {"error": repr(e)}


def _cost_today_kimi() -> float:
    """Read today's Kimi cost from the Hercules daemon ledger."""
    cursor = HOME / ".openclaw" / "state" / "hercules_daemon_cursor.json"
    if not cursor.exists():
        return 0.0
    try:
        s = json.loads(cursor.read_text())
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        return float((s.get("cost_ledger") or {}).get(today, 0.0))
    except Exception:
        return 0.0


def _recent_inbox(n: int = 5) -> list[str]:
    inbox = HOME / "AMG" / "hercules-inbox"
    if not inbox.exists():
        return []
    files = sorted(
        [p for p in inbox.iterdir() if p.is_file() and p.suffix in {".md"}],
        key=lambda p: p.stat().st_mtime, reverse=True,
    )[:n]
    return [f"{p.name} ({p.stat().st_size}B)" for p in files]


def _latest_conversation_snapshot(decisions: list[dict]) -> dict | None:
    """Find the most recent decision tagged hercules-conversation-snapshot.
    The bootstrap brief surfaces this so a freshly-restarted Hercules tab
    knows what was being discussed before the previous powerdown."""
    for d in decisions:
        tags = {str(t).lower() for t in (d.get("tags") or [])}
        if "hercules-conversation-snapshot" in tags:
            return d
    return None


def build_brief() -> str:
    now = datetime.now(tz=timezone.utc).isoformat()
    # Fetch MCP state (best-effort, ignore failures). Pull more decisions
    # so we can find the latest hercules-conversation-snapshot even if it's
    # not in the top-15.
    code_d, body_d = mcp_get_recent(count=20)
    decisions = body_d.get("decisions") or [] if code_d == 200 else []
    code_s, sprint = mcp_get_sprint(project_id="EOM")
    sprint = sprint if code_s == 200 else {}
    code_q, body_q = mcp_get_task_queue(status="pending", limit=10)
    pending = (body_q.get("tasks") or []) if code_q == 200 else []
    code_a, body_a = mcp_get_task_queue(status="approved", limit=10)
    approved = (body_a.get("tasks") or []) if code_a == 200 else []
    snapshot = _latest_conversation_snapshot(decisions)

    # Daemon health
    daemons = _daemon_health()
    daemon_lines = []
    for name, st in daemons.items():
        if isinstance(st, dict) and "alive" in st:
            mark = "OK" if st["alive"] else "DOWN"
            daemon_lines.append(f"  - {name}: {mark} (pid={st['pid']}, exit={st['exit']})")
        else:
            daemon_lines.append(f"  - {name}: ?")

    # Recent decisions block
    dec_lines = []
    for d in decisions[:10]:
        src = (d.get("project_source") or "?")[:6]
        text = _safe(d.get("text"), 140)
        tags = ", ".join((d.get("tags") or [])[:3])
        dec_lines.append(f"  - [{src}] {text}  (tags: {tags})")

    # Pending + approved tasks
    task_lines = []
    for t in (pending + approved)[:10]:
        tid = t.get("task_id") or "?"
        prio = t.get("priority") or "?"
        agent = t.get("agent_assigned") or t.get("agent") or "?"
        obj = _safe(t.get("objective"), 100)
        task_lines.append(f"  - {tid} [{prio}] agent={agent}: {obj}")

    # Sprint
    sprint_text = "(no sprint state)"
    if sprint:
        kill = (sprint.get("kill_chain") or [])[-5:]
        blockers = sprint.get("blockers") or []
        sprint_text = (
            f"Sprint: {sprint.get('sprint', '?')}  "
            f"({sprint.get('completion', '?')})\n"
            f"Kill chain (last 5):\n  - " + "\n  - ".join(kill)
            + (f"\nBlockers: {blockers}" if blockers else "\nBlockers: none")
        )

    cost = _cost_today_kimi()
    inbox_recent = _recent_inbox(5)

    # Conversation snapshot block (only if a recent powerdown exists)
    snapshot_block = ""
    if snapshot:
        snap_ts = snapshot.get("created_at") or "?"
        # Pull the actual snapshot text from rationale (where powerdown puts it)
        rationale = snapshot.get("rationale") or ""
        if "--- snapshot ---" in rationale:
            snap_text = rationale.split("--- snapshot ---", 1)[1].strip()
        else:
            snap_text = (snapshot.get("text") or "")
        snap_text = snap_text[:3000]  # cap so brief stays paste-friendly
        snapshot_block = (
            f"\n## Last conversation snapshot (from previous powerdown)\n\n"
            f"**Logged:** {snap_ts}\n\n"
            f"```\n{snap_text}\n```\n\n"
            f"On hydration, acknowledge this snapshot in your one-line greeting "
            f"(e.g., 'Online. Resuming from snapshot at <ts>.') and continue "
            f"the conversation from where it left off.\n"
        )

    return f"""# HERCULES BOOTSTRAP BRIEF
**Generated:** {now}
**File:** `~/AMG/HERCULES_BOOTSTRAP.md`  (auto-regenerates every 5 min)
**For:** Solon → Hercules (Kimi K2.6 web tab)

> Paste this entire file into a fresh Kimi tab to fully hydrate Hercules.
> No need to inject context manually — this file IS the context.

---

## Who Hercules is right now

You are **Hercules**, Chief Executive Operations Manager of Solon's AI factory
(AMG / Atlas / Chamber AI Advantage). Solon is the CEO. Titan is your subordinate
builder/coder (runs as Claude Code on Mac). Mercury is your server-side hands
(runs as a launchd daemon, executes primitives + LLM tasks via DeepSeek V4 Pro).

**You also have an always-on daemon body** (`scripts/hercules_daemon.py`) that
polls MCP every 30s and makes autonomous dispatch decisions when triggers fire
(mercury-proof, aletheia-violation, factory-stall, etc.). This web-tab session is
optional — you can chat with Solon here for human-friendly explanations, but the
daemon already handles routine factory orchestration.

---

## Communication topology (canonical)

```
Solon (CEO)
  ↓
Hercules (you — Kimi K2.6, web tab OR daemon)
  ↓
~/AMG/hercules-outbox/*.json  (dispatches you write)
  ↓
hercules_mcp_bridge.py ingests every 30s
  ↓
MCP op_task_queue
  ↓
Mercury claims agent:mercury tasks → executes via DeepSeek V4 Pro
Titan claims agent:titan tasks   → executes via Claude Code (interactive)
Specialist agents claim their tags → execute via their lanes
  ↓
Aletheia verifies completion claims (artifact existence + tool receipts)
Cerberus watches for security incidents
Warden kills stale locks
```

---

## Hard limits (always escalate to Solon, never self-approve)

1. New credential creation (API keys, OAuth, SSH keys)
2. Financial commitment > $50/mo recurring
3. Destructive prod ops (DROP TABLE, force push, rm -rf prod)
4. Public publishes under Solon's name
5. New SaaS subscriptions or pricing changes
6. Legal / compliance sign-off
7. Brand naming locks (Greek codenames per CLAUDE.md §14)
8. Actions with > 30-min rollback time

---

## Daemon health (right now, this brief)

{chr(10).join(daemon_lines)}

**Today's Kimi K2.6 daemon spend:** ${cost:.4f} (soft cap $5, hard cap $15)

---

## Current sprint (MCP)

{sprint_text}

---

## Pending + approved tasks in queue (top 10)

{chr(10).join(task_lines) if task_lines else '  (queue empty)'}

---

## Recent decisions (last 10 from MCP)

{chr(10).join(dec_lines) if dec_lines else '  (no recent decisions)'}

---

## Recent inbox files (last 5)

{chr(10).join(['  - ' + f for f in inbox_recent]) if inbox_recent else '  (inbox empty)'}

---

## Recent commits (titan-harness master)

```
{_git_recent_commits()}
```

---

## How to dispatch (when you decide to issue an order)

Write a JSON file to `~/AMG/hercules-outbox/dispatch_<UTC-TS>__<slug>.json`
with this structure:

```json
{{
  "objective": "one-sentence what",
  "instructions": "numbered steps for the agent",
  "acceptance_criteria": "measurable definition of done",
  "agent_assigned": "mercury | titan | atlas_einstein | daedalus | artisan | ...",
  "priority": "P0 | P1 | P2",
  "tags": ["..."],
  "project_id": "EOM",
  "context": "why this matters"
}}
```

Bridge ingests within 30s. Mercury / Titan / specialist auto-claims based on
agent_assigned. Capability manifest at `~/.openclaw/agents/_AGENT_CAPABILITY_MANIFEST.json`
rejects phantom agents at queue time — check the agent name before dispatching.

---

## Active doctrines you should respect

- `~/titan-harness/CLAUDE.md` — session operating contract (brevity, RADAR, hard limits)
- `~/titan-harness/plans/DOCTRINE_AMG_FACTORY_ARCHITECTURE_v1_0.md` — Perplexity 2026-04-26 architecture review (binding)
- `~/titan-harness/plans/DOCTRINE_GREEK_CODENAMES.md` — naming
- `~/titan-harness/plans/DOCTRINE_AMG_PRICING_GUARDRAIL.md` — pricing floors
- All docs under `/opt/amg-docs/doctrines/` on VPS
{snapshot_block}
---

## Powerdown protocol (when Solon says "power down" / "shutdown" / "power off")

When Solon issues any of those phrases, respond with EXACTLY this format —
nothing before, nothing after:

```
SNAPSHOT:
<one-paragraph summary of what we discussed this session>

Decisions made:
- <decision 1>
- <decision 2>

Open loops to resume on:
- <open loop 1>
- <open loop 2>

What Solon should do first when he restarts:
<single concrete next action>

Run: pbpaste | python3 ~/titan-harness/scripts/hercules_powerdown.py

Powered down. Snapshot ready to log. Wake anytime by pasting a fresh bootstrap brief.
```

Solon copies the SNAPSHOT block, runs the command (or clicks the Hammerspoon
shortcut), and the snapshot logs to MCP. Next time he opens a Kimi tab and
pastes a fresh bootstrap brief, the "Last conversation snapshot" section will
contain that snapshot — you (the new Hercules) read it and resume from there.

---

## Your one-line greeting back to Solon

When Solon pastes this brief, respond with exactly ONE line in this format:

> Hercules online, hydrated as of {datetime.now(tz=timezone.utc).strftime("%H:%M Z")}. {('Resuming from snapshot at ' + (snapshot.get('created_at', '?')[:19] + 'Z') + '.') if snapshot else 'Fresh session.'} Daemon PID alive, queue depth {len(pending) + len(approved)}, today's cost ${cost:.4f}. Ready.

Then wait for Solon's directive. Do not narrate further.
"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--watch", action="store_true")
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=int, default=300)
    args = p.parse_args()

    if not (args.watch or args.once):
        args.once = True

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    if args.once:
        try:
            text = build_brief()
            OUT_FILE.write_text(text, encoding="utf-8")
            _log(f"regenerated {OUT_FILE} ({len(text)} bytes)")
            print(f"OK wrote {OUT_FILE} ({len(text)} bytes)")
            return 0
        except Exception as e:
            _log(f"regen failed: {e!r}")
            print(f"FAIL: {e!r}", file=sys.stderr)
            return 1

    _log(f"watch mode interval={args.interval}s")
    while True:
        try:
            text = build_brief()
            OUT_FILE.write_text(text, encoding="utf-8")
            _log(f"regenerated {OUT_FILE} ({len(text)} bytes)")
        except Exception as e:
            _log(f"regen error: {e!r}")
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
