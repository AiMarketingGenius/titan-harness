#!/usr/bin/env python3
"""factory_status.py — write a compact JSON snapshot of the AMG agent
factory's live state, so Hercules (in its Kimi web tab) can fetch it via
WebFetch and stop guessing.

Hercules's #1 ask per its 2026-04-26 brief: a "live MCP read pipe" so it
can see queue depth, agent heartbeats, today's spend, and last 5
completions. This script writes that.

Output: ~/.openclaw/state/factory_status.json (atomic write)
Schema:
  {
    "ts": ISO-8601 UTC,
    "ts_unix": int,
    "queue": {
      "approved": int,           # waiting to be claimed
      "locked": int,             # in flight
      "dead_letter": int,
      "by_agent": {agent: count, ...}
    },
    "agents": {
      "mercury_executor":     {"alive": bool, "pid": int, "last_run_ts": ts},
      "hercules_mcp_bridge":  {"alive": bool, "pid": int},
      "hercules_daemon":      {"alive": bool, "pid": int},
      "mercury_mcp_notifier": {"alive": bool, "pid": int},
      "mercury_folder_sync":  {"alive": bool, "pid": int},
      "hercules_dispatch_receiver": {"alive": bool, "pid": int}
    },
    "recent_completions": [
      {"task_id": ..., "status": ..., "agent": ..., "completed_at": ...}, ...
    ],
    "recent_decisions": [
      {"ts": ..., "tags": [...], "text_preview": "first 140 chars"}, ...
    ],
    "lock_leaks": int,           # count of warden LOCK_LEAK violations last 1hr
    "sprint": {                  # current EOM sprint
      "name": str, "completion_pct": str, "blockers": [...]
    }
  }

Run modes:
    factory_status.py            # one-shot, exit 0 on success
    factory_status.py --watch    # daemon, write every 60s
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
from datetime import datetime, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))

from mcp_rest_client import (  # noqa: E402
    get_recent_decisions,
    get_sprint_state,
    get_task_queue,
)

OUT_FILE = HOME / ".openclaw" / "state" / "factory_status.json"
LOG_FILE = HOME / ".openclaw" / "logs" / "factory_status.log"
# Public gist Hercules can WebFetch from its Kimi tab. Operational metadata
# only (no source-of-truth doc content — that would leak the encyclopedia).
PUBLIC_GIST_ID = os.environ.get(
    "FACTORY_STATUS_GIST_ID",
    "05608a50c9f47954f3de19c67d581350",
)
PUBLIC_GIST_RAW_URL = (
    f"https://gist.githubusercontent.com/AiMarketingGenius/{PUBLIC_GIST_ID}"
    "/raw/factory_status.json"
)
LAUNCHCTL_LABELS = {
    "mercury_executor": "com.amg.mercury-executor",
    "hercules_mcp_bridge": "com.amg.hercules-mcp-bridge",
    "hercules_daemon": "com.amg.hercules-daemon",
    "mercury_mcp_notifier": "com.amg.mercury-mcp-notifier",
    "mercury_folder_sync": "com.amg.mercury-folder-sync",
    "hercules_dispatch_receiver": "com.amg.hercules-dispatch-receiver",
    "daedalus_v4_pro": "com.amg.daedalus-v4-pro",
    "artisan_v4_flash": "com.amg.artisan-v4-flash",
    "nestor_executor": "com.amg.nestor-executor",
    "alexander_executor": "com.amg.alexander-executor",
    "aletheia_verify": "com.amg.aletheia-verify",
    "factory_status": "com.amg.factory-status",
    "hercules_bootstrap": "com.amg.hercules-bootstrap",
}


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with LOG_FILE.open("a") as f:
        f.write(f"[{ts}] {msg}\n")


def _launchctl_state(label: str) -> dict:
    try:
        r = subprocess.run(
            ["launchctl", "list", label],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return {"alive": False, "pid": None, "last_exit": None}
        # parse plist-like output
        pid = None
        last_exit = None
        for line in r.stdout.splitlines():
            line = line.strip().rstrip(";")
            if line.startswith('"PID"'):
                v = line.split("=", 1)[1].strip()
                if v.isdigit():
                    pid = int(v)
            elif line.startswith('"LastExitStatus"'):
                v = line.split("=", 1)[1].strip()
                if v.lstrip("-").isdigit():
                    last_exit = int(v)
        return {"alive": pid is not None, "pid": pid, "last_exit": last_exit}
    except Exception as e:
        return {"alive": False, "pid": None, "error": repr(e)[:120]}


def _queue_summary() -> dict:
    counts = {"approved": 0, "locked": 0, "dead_letter": 0, "by_agent": {}}
    for status in ("approved", "locked", "dead_letter"):
        code, body = get_task_queue(status=status, include_completed=True, limit=50)
        if code != 200:
            continue
        tasks = body.get("tasks", [])
        counts[status] = len(tasks)
        for t in tasks:
            agent = t.get("assigned_to") or "unassigned"
            counts["by_agent"][agent] = counts["by_agent"].get(agent, 0) + 1
    return counts


def _recent_completions(limit: int = 5) -> list:
    code, body = get_task_queue(
        status="completed", include_completed=True, limit=limit,
    )
    if code != 200:
        return []
    out = []
    for t in body.get("tasks", [])[:limit]:
        out.append({
            "task_id": t.get("task_id"),
            "agent": t.get("assigned_to"),
            "completed_at": t.get("completed_at"),
            "objective_preview": (t.get("objective") or "")[:120],
        })
    return out


def _recent_decisions(limit: int = 10) -> list:
    code, body = get_recent_decisions(count=limit)
    if code != 200:
        return []
    out = []
    for d in body.get("decisions", []):
        out.append({
            "ts": d.get("created_at"),
            "tags": d.get("tags", [])[:5],
            "project": d.get("project_source"),
            "text_preview": (d.get("text") or "")[:140],
        })
    return out


def _lock_leak_count(decisions: list) -> int:
    return sum(
        1 for d in decisions
        if any("lock-leak" in t.lower() or "lock_leak" in t.lower() for t in d.get("tags", []))
        or "LOCK_LEAK" in (d.get("text_preview") or "")
    )


def _sprint() -> dict:
    code, body = get_sprint_state(project_id="EOM")
    if code != 200:
        return {}
    return {
        "name": body.get("sprint", ""),
        "completion_pct": body.get("completion", ""),
        "blockers": body.get("blockers", [])[:5],
    }


def build_snapshot() -> dict:
    now = datetime.now(timezone.utc)
    decisions = _recent_decisions(limit=20)
    return {
        "ts": now.isoformat(),
        "ts_unix": int(now.timestamp()),
        "schema_version": 1,
        "queue": _queue_summary(),
        "agents": {
            name: _launchctl_state(label)
            for name, label in LAUNCHCTL_LABELS.items()
        },
        "recent_completions": _recent_completions(limit=5),
        "recent_decisions": decisions[:10],
        "lock_leaks_recent": _lock_leak_count(decisions),
        "sprint": _sprint(),
    }


def write_atomic(snap: dict) -> None:
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(snap, indent=2, default=str))
    tmp.replace(OUT_FILE)


def push_to_public_gist() -> None:
    """Push local factory_status.json to the public gist so Hercules in the
    Kimi web tab can WebFetch live state without Solon re-pasting the brief.
    Best-effort; failures are logged but never raise."""
    if not PUBLIC_GIST_ID:
        return
    try:
        r = subprocess.run(
            ["gh", "gist", "edit", PUBLIC_GIST_ID, "-f", "factory_status.json", str(OUT_FILE)],
            capture_output=True, text=True, timeout=20,
        )
        if r.returncode != 0:
            _log(f"gist push FAILED rc={r.returncode} stderr={r.stderr.strip()[:200]}")
        else:
            _log(f"gist push OK → {PUBLIC_GIST_RAW_URL}")
    except Exception as e:
        _log(f"gist push exception: {e!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true", help="loop forever, write every --interval")
    ap.add_argument("--interval", type=int, default=60, help="watch interval seconds")
    args = ap.parse_args()

    if not args.watch:
        snap = build_snapshot()
        write_atomic(snap)
        push_to_public_gist()
        _log(f"one-shot wrote {OUT_FILE} (queue.locked={snap['queue']['locked']} agents_alive={sum(1 for a in snap['agents'].values() if a.get('alive'))})")
        print(json.dumps({"ok": True, "path": str(OUT_FILE), "gist_url": PUBLIC_GIST_RAW_URL, "ts": snap["ts"]}))
        return 0

    _log(f"watch starting interval={args.interval}s gist={PUBLIC_GIST_RAW_URL}")
    push_counter = 0
    while True:
        try:
            snap = build_snapshot()
            write_atomic(snap)
            # Push to public gist every 60s to keep Hercules's WebFetch view
            # fresh. Push interval ties to args.interval; if interval < 60 we
            # throttle gist updates to avoid GitHub rate limits.
            push_counter += 1
            if (push_counter * args.interval) >= 60:
                push_to_public_gist()
                push_counter = 0
            _log(f"watch wrote {OUT_FILE} (queue.locked={snap['queue']['locked']})")
        except Exception as e:
            _log(f"watch ERROR: {e!r}")
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
