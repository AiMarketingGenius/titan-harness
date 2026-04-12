#!/usr/bin/env python3
"""
scripts/ct_0406_03_watchdog.py
CT-0406-03 — Titan Auto-Wake Watchdog (TITAN BINDING DOCTRINE v2.0 §4)

Fires every 5 minutes via systemd timer (systemd/ct_0406_03_watchdog.timer).
Queries Supabase for in-progress tasks in op_task_queue whose
last_checkpoint_at (or created_at if never checkpointed) is older than
CT0406_STALL_MINUTES (default 15), then posts one Slack message per stalled
task to SLACK_TITAN_ARISTOTLE_WEBHOOK.

Exit codes:
  0 = ran to completion (zero or more stalled tasks notified)
  1 = missing required env var or fatal HTTP error

Required env (loaded from /root/.titan-env via the systemd unit):
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
  SLACK_TITAN_ARISTOTLE_WEBHOOK

Optional env:
  CT0406_STALL_MINUTES (default: 15)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone


def _env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if not val:
        print(f"[ct_0406_03_watchdog] FATAL: missing env var {name}", file=sys.stderr)
        sys.exit(1)
    return val


SUPABASE_URL = _env("SUPABASE_URL")
SUPABASE_KEY = _env("SUPABASE_SERVICE_ROLE_KEY")
SLACK_WEBHOOK_URL = _env("SLACK_TITAN_ARISTOTLE_WEBHOOK")
STALL_MINUTES = int(os.environ.get("CT0406_STALL_MINUTES", "15"))


def _http_post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 10) -> dict:
    """Minimal urllib POST returning parsed JSON or {} on empty body."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        if not body:
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}


def fetch_stalled_tasks() -> list[dict]:
    """Call public.get_stalled_tasks(cutoff) via the Supabase RPC endpoint.

    Falls back to a REST filter query if the RPC is not yet installed in the
    target Supabase instance, so the watchdog still works the first time it
    runs after a fresh schema migration.
    """
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=STALL_MINUTES)).isoformat()

    rpc_url = f"{SUPABASE_URL}/rest/v1/rpc/get_stalled_tasks"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }

    try:
        return _http_post_json(rpc_url, {"cutoff": cutoff}, headers=headers) or []
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            print(f"[ct_0406_03_watchdog] RPC error {exc.code}: {exc.reason}", file=sys.stderr)
        # Fall through to REST filter path.
    except Exception as exc:
        print(f"[ct_0406_03_watchdog] RPC call failed: {exc!r}", file=sys.stderr)

    # REST-filter fallback: status=in_progress AND last_checkpoint_at < cutoff
    # Supabase REST does not support COALESCE in the filter layer; we fetch
    # in-progress rows and filter locally.
    list_url = (
        f"{SUPABASE_URL}/rest/v1/op_task_queue"
        "?select=id,task_id,status,assigned_to,objective,created_at,last_checkpoint_at"
        "&status=eq.in_progress"
    )
    req = urllib.request.Request(list_url, method="GET")
    req.add_header("apikey", SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            rows = json.loads(resp.read().decode("utf-8")) or []
    except Exception as exc:
        print(f"[ct_0406_03_watchdog] REST fallback failed: {exc!r}", file=sys.stderr)
        return []

    stalled: list[dict] = []
    cutoff_dt = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
    for row in rows:
        ref = row.get("last_checkpoint_at") or row.get("created_at")
        if not ref:
            continue
        try:
            ref_dt = datetime.fromisoformat(ref.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ref_dt < cutoff_dt:
            stalled.append(row)
    return stalled


def notify_slack(task: dict) -> None:
    task_id = task.get("task_id") or task.get("id") or "unknown"
    updated_at = task.get("last_checkpoint_at") or task.get("created_at")
    try:
        updated_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except Exception:
        updated_dt = datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)
    delta_min = int((now - updated_dt).total_seconds() / 60)

    objective = task.get("objective") or "(no objective set)"
    assigned_to = task.get("assigned_to") or "(unassigned)"

    text = (
        f":warning: STALLED TASK: `{task_id}` has been `in_progress` "
        f"for ~{delta_min} minutes with no checkpoint.\n"
        f"Assigned: *{assigned_to}*\n"
        f"Objective: {objective}\n"
        f"Titan: Continue `{task_id}` from last checkpoint."
    )

    try:
        _http_post_json(SLACK_WEBHOOK_URL, {"text": text})
    except Exception as exc:
        print(f"[ct_0406_03_watchdog] Slack post failed for {task_id}: {exc!r}", file=sys.stderr)


def main() -> int:
    stalled = fetch_stalled_tasks()
    if not stalled:
        print(f"[ct_0406_03_watchdog] OK — 0 stalled tasks at cutoff {STALL_MINUTES}min")
        return 0
    print(f"[ct_0406_03_watchdog] WARN — {len(stalled)} stalled task(s), notifying Slack")
    for task in stalled:
        notify_slack(task)
    return 0


if __name__ == "__main__":
    sys.exit(main())
