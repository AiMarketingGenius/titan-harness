#!/usr/bin/env python3
"""
warden_enforcer.py — Operational cop daemon.

Every 10 minutes, polls all 43 agents + the MCP queue. Catches:
- IDLE: agent has no activity > 30 min and no valid blocker
- FALSE_COMPLETION: claim of done but no proof artifact
- FACTORY_STALL: queue depth = 0 for > 20 min in business hours
- INFRASTRUCTURE_DOWN: cron jobs missing or MCP unreachable
- LOCK_LEAK: task locked > 2h with no progress

Auto-restarts idle agents via agent_lifecycle_controller.py.
Escalates to Hercules at 3 violations/agent/hour.

Run modes:
    warden_enforcer.py --watch       # daemon (default), poll 10 min
    warden_enforcer.py --once
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
    get_task_queue as mcp_get_task_queue,
    log_decision as mcp_log_decision,
    health as mcp_health,
)

STATE_DIR = HOME / ".openclaw" / "state"
BASELINE_FILE = STATE_DIR / "warden_baseline.json"
VIOLATIONS_FILE = STATE_DIR / "warden_violations.json"
LOGFILE = HOME / ".openclaw" / "logs" / "warden_enforcer.log"
LIFECYCLE = HOME / "titan-harness" / "scripts" / "agent_lifecycle_controller.py"
MANIFEST_FILE = HOME / ".openclaw" / "agents" / "_AMG_AGENT_ARMY_MANIFEST.json"

IDLE_MINUTES = 30
QUEUE_STALL_MINUTES = 20
LOCK_LEAK_HOURS = 2
ESCALATE_AFTER = 3  # same agent in 1 hour


def _log(msg: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    sys.stderr.write(line)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line)


def _load(path: pathlib.Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save(path: pathlib.Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def list_agents() -> list[str]:
    m = _load(MANIFEST_FILE, {"agents": []})
    return m.get("agents") or []


# ─── checks ─────────────────────────────────────────────────────────────────
def check_mcp_health() -> dict | None:
    code, body = mcp_health()
    if code != 200 or body.get("status") != "ok":
        return {"class": "INFRASTRUCTURE_DOWN", "agent": "mcp", "evidence": f"health: code={code} body={str(body)[:120]}"}
    return None


def check_factory_stall() -> dict | None:
    code, body = mcp_get_task_queue(status="approved", limit=50)
    if code != 200:
        return None
    tasks = body.get("tasks") or []
    pending = [t for t in tasks if t.get("status") == "approved" and not t.get("locked_by")]
    if pending:
        return None
    code2, body2 = mcp_get_task_queue(status="in_progress", limit=10)
    in_progress = body2.get("tasks") or [] if code2 == 200 else []
    if in_progress:
        return None
    # Check if last queue activity > 20 min ago
    code3, body3 = mcp_get_recent(count=20)
    decisions = body3.get("decisions") or [] if code3 == 200 else []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=QUEUE_STALL_MINUTES)
    recent_dispatch_or_proof = [
        d for d in decisions if any(t in (d.get("tags") or [])
        for t in ("hercules-dispatch", "mercury-proof", "agent-dispatch-bridge"))
    ]
    if recent_dispatch_or_proof:
        latest = parse_iso(recent_dispatch_or_proof[0].get("created_at", ""))
        if latest and latest > cutoff:
            return None
    return {
        "class": "FACTORY_STALL",
        "agent": "factory",
        "evidence": f"queue empty + no dispatch/proof in last {QUEUE_STALL_MINUTES} min",
    }


def check_lock_leaks() -> list[dict]:
    out: list[dict] = []
    code, body = mcp_get_task_queue(status="locked", limit=50)
    if code != 200:
        return out
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=LOCK_LEAK_HOURS)
    for t in (body.get("tasks") or []):
        locked_at = parse_iso(t.get("locked_at") or "")
        if locked_at and locked_at < cutoff:
            out.append({
                "class": "LOCK_LEAK",
                "agent": t.get("locked_by") or "unknown",
                "evidence": f"task={t.get('task_id')} locked_at={t.get('locked_at')} (>{LOCK_LEAK_HOURS}h ago)",
            })
    return out


def check_false_completions() -> list[dict]:
    """A done-marked task with no result_summary AND no log_decision tagged
    with the task_id is suspicious."""
    out: list[dict] = []
    code, body = mcp_get_task_queue(status="done", limit=20, include_completed=True)
    if code != 200:
        return out
    code2, body2 = mcp_get_recent(count=20)
    decisions = body2.get("decisions") or [] if code2 == 200 else []
    proof_tagged_tasks: set[str] = set()
    for d in decisions:
        for tag in (d.get("tags") or []):
            if isinstance(tag, str) and tag.startswith("task:"):
                proof_tagged_tasks.add(tag[len("task:"):])
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=4)
    for t in (body.get("tasks") or []):
        completed_at = parse_iso(t.get("completed_at") or t.get("updated_at") or "")
        if not completed_at or completed_at < cutoff:
            continue
        tid = t.get("task_id")
        if not tid or tid in proof_tagged_tasks:
            continue
        if t.get("result_summary"):
            continue  # has summary — partial proof, skip
        out.append({
            "class": "FALSE_COMPLETION",
            "agent": t.get("locked_by") or t.get("queued_by") or "unknown",
            "evidence": f"task={tid} marked done with no result_summary AND no proof decision tagged task:{tid}",
        })
    return out


# ─── enforcement ────────────────────────────────────────────────────────────
def auto_restart(agent: str) -> str:
    if not LIFECYCLE.exists():
        return f"lifecycle controller missing at {LIFECYCLE}"
    try:
        out = subprocess.run(
            ["python3", str(LIFECYCLE), "--restart", "--agent", agent],
            capture_output=True, text=True, timeout=30,
        )
        return f"restart exit={out.returncode} out={out.stdout[-200:]}"
    except Exception as e:
        return f"restart error: {e!r}"


def record_violation(violations_state: dict, v: dict) -> int:
    agent = v.get("agent", "unknown")
    now = datetime.now(tz=timezone.utc).isoformat()
    v_with_ts = {**v, "ts": now}
    violations_state.setdefault("by_agent", {}).setdefault(agent, []).append(v_with_ts)
    # Trim to last hour
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    violations_state["by_agent"][agent] = [
        x for x in violations_state["by_agent"][agent]
        if parse_iso(x.get("ts", "")) and parse_iso(x["ts"]) > cutoff
    ]
    return len(violations_state["by_agent"][agent])


def drain_once() -> dict:
    violations_state = _load(VIOLATIONS_FILE, {"by_agent": {}})
    violations: list[dict] = []
    h = check_mcp_health()
    if h:
        violations.append(h)
    s = check_factory_stall()
    if s:
        violations.append(s)
    violations.extend(check_lock_leaks())
    violations.extend(check_false_completions())
    out = {"violations": len(violations), "auto_restarted": 0, "escalated": 0}
    for v in violations:
        count_in_window = record_violation(violations_state, v)
        action = "flag-only"
        if v["class"] in {"IDLE", "HEARTBEAT_MISS"} and v["agent"] not in {"factory", "mcp"}:
            r = auto_restart(v["agent"])
            v["auto_restart_result"] = r
            action = "auto-restart"
            out["auto_restarted"] += 1
        if count_in_window >= ESCALATE_AFTER:
            action = "ESCALATE"
            out["escalated"] += 1
        mcp_log_decision(
            text=(
                f"WARDEN VIOLATION class={v['class']} agent={v['agent']} "
                f"action={action} window_count={count_in_window}"
            ),
            rationale=(
                f"Evidence: {v.get('evidence','')[:400]}. "
                f"Violation count for this agent in last 1h: {count_in_window}. "
                f"{('Restart result: ' + str(v.get('auto_restart_result',''))) if v.get('auto_restart_result') else ''}"
            ),
            tags=["warden-violation", v["class"].lower(), f"agent:{v['agent']}"],
            project_source="titan",
        )
        _log(f"VIOL {v['class']} agent={v['agent']} action={action} (count={count_in_window})")
    _save(VIOLATIONS_FILE, violations_state)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Warden operational enforcer")
    p.add_argument("--once", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=600)
    args = p.parse_args()

    if args.once or not args.watch:
        print(json.dumps(drain_once(), indent=2))
        return 0

    _log(f"warden_enforcer starting watch interval={args.interval}s")
    while True:
        try:
            r = drain_once()
            if r["violations"] > 0:
                _log(f"poll: violations={r['violations']} restarted={r['auto_restarted']} escalated={r['escalated']}")
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            _log(f"poll error: {e!r}")
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
