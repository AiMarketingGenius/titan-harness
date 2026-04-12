#!/usr/bin/env python3
"""
scripts/titan_reorientation.py
MP-3 §10 — Session Reorientation Script

Mandatory first action of every new Claude Code session. Implements the 5-step
reorientation sequence from MP-3 Atlas Operations Interfaces Doctrine v1.0.

Steps:
  1. Query MCP for open tasks, pending Hard Limit approvals, active incidents.
  2. Query subsystem health flags for all 7 subsystems.
  3. If any P0/P1 incident active → flag for immediate response.
  4. If any Hard Limit approval >24h → surface to Solon in Slack.
  5. Resume highest-priority open task, or post standby.

MCP unreachable fallback: post to Slack and halt.

Exit codes:
  0 — reorientation complete
  1 — MCP unreachable (posted Slack alert, halting)
  2 — missing required env vars
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta


def _env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if not val:
        print(f"[titan_reorientation] FATAL: missing env var {name}", file=sys.stderr)
        sys.exit(2)
    return val


# --- Environment ---
SUPABASE_URL = _env("SUPABASE_URL")
SUPABASE_KEY = _env("SUPABASE_SERVICE_ROLE_KEY")
SLACK_BOT_TOKEN = _env("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.environ.get("ARISTOTLE_CHANNEL_ID", "")
SLACK_OPS_CHANNEL_ID = os.environ.get("SLACK_OPS_CHANNEL_ID", SLACK_CHANNEL_ID)

MCP_MEMORY_URL = os.environ.get("MCP_MEMORY_URL", "https://memory.aimarketinggenius.io")


def _http_json(url: str, method: str = "GET", payload: dict | None = None,
               headers: dict | None = None, timeout: int = 10) -> dict | list:
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        if not body:
            return {}
        return json.loads(body)


def _supabase_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }


def post_slack(text: str, channel: str | None = None) -> None:
    ch = channel or SLACK_OPS_CHANNEL_ID
    if not ch:
        print(f"[titan_reorientation] WARN: no Slack channel configured, printing to stdout")
        print(text)
        return
    try:
        _http_json(
            "https://slack.com/api/chat.postMessage",
            method="POST",
            payload={"channel": ch, "text": text},
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        )
    except Exception as exc:
        print(f"[titan_reorientation] Slack post failed: {exc!r}", file=sys.stderr)
        print(text)


# --- Step 1: Query MCP for open tasks, Hard Limit approvals, incidents ---

def fetch_open_tasks() -> list[dict]:
    """Fetch all non-complete tasks from op_task_queue."""
    url = (
        f"{SUPABASE_URL}/rest/v1/op_task_queue"
        "?select=id,task_id,status,priority,objective,assigned_to,approval,created_at,updated_at"
        "&status=neq.done&status=neq.failed&status=neq.cancelled"
        "&order=priority.asc,created_at.asc"
        "&limit=50"
    )
    try:
        return _http_json(url, headers=_supabase_headers()) or []
    except Exception as exc:
        print(f"[titan_reorientation] Failed to fetch tasks: {exc!r}", file=sys.stderr)
        return []


def fetch_pending_approvals(tasks: list[dict]) -> list[dict]:
    """Filter tasks with approval='pending' and check age."""
    now = datetime.now(timezone.utc)
    pending = []
    for t in tasks:
        if t.get("approval") == "pending":
            created = t.get("created_at", "")
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                age_hours = (now - created_dt).total_seconds() / 3600
            except Exception:
                age_hours = 0
            t["_age_hours"] = round(age_hours, 1)
            t["_stale"] = age_hours > 24
            pending.append(t)
    return pending


# --- Step 2: Subsystem health ---

SUBSYSTEMS = [
    "kokoro_tts", "hermes_pipeline", "mcp", "n8n", "caddy",
    "titan_processor", "titan_bot", "supabase", "r2",
    "reviewer_loop_budget", "vps_disk", "vps_cpu_memory", "atlas_portal"
]


def fetch_subsystem_health() -> dict[str, str]:
    """Read latest health status from JSONL or default to unknown."""
    health_file = "/var/log/titan-health/subsystem_health.jsonl"
    health: dict[str, str] = {s: "unknown" for s in SUBSYSTEMS}

    if not os.path.exists(health_file):
        return health

    try:
        with open(health_file) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    name = entry.get("subsystem", "")
                    status = entry.get("status", "unknown")
                    if name in health:
                        health[name] = status
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    return health


# --- Step 3: Incident check ---

def check_incidents(health: dict[str, str]) -> list[dict]:
    """Identify P0/P1 incidents from subsystem health."""
    incidents = []
    for name, status in health.items():
        if status == "dead":
            incidents.append({"subsystem": name, "severity": "P0", "status": status})
        elif status == "degraded":
            incidents.append({"subsystem": name, "severity": "P1", "status": status})
    return incidents


# --- Step 5: Build reorientation summary ---

def build_summary(
    tasks: list[dict],
    pending_approvals: list[dict],
    incidents: list[dict],
    health: dict[str, str],
) -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Task counts
    in_progress = [t for t in tasks if t.get("status") == "in_progress"]
    approved = [t for t in tasks if t.get("status") == "approved"]
    total_open = len(tasks)

    # Highest priority task
    if in_progress:
        top_task = in_progress[0]
    elif approved:
        top_task = approved[0]
    elif tasks:
        top_task = tasks[0]
    else:
        top_task = None

    top_name = top_task.get("task_id", "unknown") if top_task else "none"
    top_obj = top_task.get("objective", "") if top_task else ""

    # Approval counts
    stale_approvals = [a for a in pending_approvals if a.get("_stale")]

    # Health summary
    healthy_count = sum(1 for s in health.values() if s == "healthy")
    total_subs = len(health)
    degraded = [n for n, s in health.items() if s in ("degraded", "dead")]

    health_line = f"{healthy_count}/{total_subs} healthy"
    if degraded:
        health_line += f" | degraded: {', '.join(degraded)}"

    # P0/P1
    p0 = [i for i in incidents if i["severity"] == "P0"]
    p1 = [i for i in incidents if i["severity"] == "P1"]
    incident_line = f"{len(p0)} P0, {len(p1)} P1" if (p0 or p1) else "None"

    # Proceeding with
    if p0:
        proceed = f"RESPONDING TO P0: {p0[0]['subsystem']}"
    elif p1:
        proceed = f"RESPONDING TO P1: {p1[0]['subsystem']}"
    elif stale_approvals:
        proceed = f"SURFACING {len(stale_approvals)} stale Hard Limit approval(s) to Solon"
    elif top_task:
        proceed = f"{top_name}: {top_obj[:80]}"
    else:
        proceed = "No open tasks. Standby."

    summary = (
        f"[TITAN REORIENTED — {now_str}]\n"
        f"Open tasks: {total_open} ({top_name})\n"
        f"Pending Hard Limit approvals: {len(pending_approvals)}"
        f"{' (⚠️ ' + str(len(stale_approvals)) + ' >24h)' if stale_approvals else ''}\n"
        f"Active incidents: {incident_line}\n"
        f"Subsystem health: {health_line}\n"
        f"Proceeding with: {proceed}"
    )
    return summary


def main() -> int:
    print("[titan_reorientation] Starting 5-step reorientation sequence...")

    # Step 1: Fetch open tasks
    print("[titan_reorientation] Step 1: Querying open tasks...")
    tasks = fetch_open_tasks()
    if tasks is None:
        # MCP unreachable
        post_slack("Titan: MCP unreachable. Cannot reorient. Manual check required.")
        print("[titan_reorientation] FATAL: MCP unreachable. Halting.", file=sys.stderr)
        return 1
    print(f"[titan_reorientation]   → {len(tasks)} open task(s)")

    pending_approvals = fetch_pending_approvals(tasks)
    print(f"[titan_reorientation]   → {len(pending_approvals)} pending approval(s)")

    # Step 2: Subsystem health
    print("[titan_reorientation] Step 2: Checking subsystem health...")
    health = fetch_subsystem_health()
    healthy = sum(1 for s in health.values() if s == "healthy")
    print(f"[titan_reorientation]   → {healthy}/{len(health)} healthy")

    # Step 3: Incident check
    print("[titan_reorientation] Step 3: Checking for P0/P1 incidents...")
    incidents = check_incidents(health)
    p0 = [i for i in incidents if i["severity"] == "P0"]
    p1 = [i for i in incidents if i["severity"] == "P1"]
    if p0:
        print(f"[titan_reorientation]   → ⚠️ {len(p0)} P0 incident(s) — responding FIRST")
    elif p1:
        print(f"[titan_reorientation]   → ⚠️ {len(p1)} P1 incident(s)")
    else:
        print("[titan_reorientation]   → No active P0/P1 incidents")

    # Step 4: Stale Hard Limit approvals
    print("[titan_reorientation] Step 4: Checking Hard Limit approval age...")
    stale = [a for a in pending_approvals if a.get("_stale")]
    if stale:
        print(f"[titan_reorientation]   → ⚠️ {len(stale)} approval(s) >24h old — surfacing to Solon")
        for s in stale:
            post_slack(
                f"⚠️ STALE HARD LIMIT APPROVAL: `{s.get('task_id', 'unknown')}` — "
                f"pending for {s.get('_age_hours', '?')}h\n"
                f"Objective: {s.get('objective', '(none)')}"
            )
    else:
        print("[titan_reorientation]   → No stale approvals")

    # Step 5: Build and post summary
    print("[titan_reorientation] Step 5: Posting reorientation summary...")
    summary = build_summary(tasks, pending_approvals, incidents, health)
    print(summary)
    post_slack(summary)

    print("[titan_reorientation] Reorientation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
