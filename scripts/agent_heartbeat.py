#!/usr/bin/env python3
"""
agent_heartbeat.py — health monitor for the AMG agent fleet (33 agents).

Polls each agent's footprint every run and tracks:
- last config.toml mtime (proxy for "last touched")
- last MCP log_decision tagged with the agent name (proxy for "last activity")
- queue depth via the n8n webhook shim
- workspace dir presence + last-modified

If an agent has no MCP activity for 3 consecutive heartbeat runs (default 30
minutes total at 10-min cadence), the script flags it `dead` and posts a
restart hint via amg-fleet (best-effort; for OpenClaw-resident agents only).

Usage
-----
    agent_heartbeat.py              # one full poll, exit
    agent_heartbeat.py --watch      # poll every 600s
    agent_heartbeat.py --report     # daily summary to MCP for Hercules
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

HOME = pathlib.Path.home()
AGENTS_DIR = HOME / ".openclaw" / "agents"
STATE_FILE = HOME / ".openclaw" / "heartbeat_state.json"
MCP_BASE = os.environ.get("MCP_BASE", "https://memory.aimarketinggenius.io/mcp")
QUEUE_DEPTH_URL = "https://n8n.aimarketinggenius.io/webhook/queue-depth"
DEAD_THRESHOLD_RUNS = 3
POLL_INTERVAL_S = 600


def list_agents() -> list[str]:
    if not AGENTS_DIR.exists():
        return []
    out = []
    for d in sorted(AGENTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        if (d / "config.toml").exists():
            out.append(d.name)
    return out


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"runs": [], "agents": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def fetch_queue_depth() -> int | None:
    try:
        with urllib.request.urlopen(QUEUE_DEPTH_URL, timeout=5) as r:
            return int(json.loads(r.read()).get("depth", 0))
    except Exception:
        return None


def search_mcp_for_agent(name: str, limit: int = 5) -> list[dict]:
    """Search recent MCP decisions for the agent name."""
    try:
        body = json.dumps({"query": name, "limit": limit}).encode()
        req = urllib.request.Request(
            f"{MCP_BASE}/search_memory",
            data=body, headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read() or b"{}")
        return d.get("results", []) or d.get("decisions", []) or []
    except Exception:
        return []


def agent_health(name: str) -> dict:
    base = AGENTS_DIR / name
    cfg = base / "config.toml"
    cfg_mtime = cfg.stat().st_mtime if cfg.exists() else 0
    workspace_present = (base / "workspace").exists()
    mcp_hits = search_mcp_for_agent(name, limit=3)
    last_mcp_ts = 0
    if mcp_hits:
        for h in mcp_hits:
            ts_raw = h.get("created_at") or h.get("ts") or h.get("timestamp")
            if isinstance(ts_raw, str):
                try:
                    last_mcp_ts = max(last_mcp_ts,
                                      int(datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).timestamp()))
                except Exception:
                    pass
            elif isinstance(ts_raw, (int, float)):
                last_mcp_ts = max(last_mcp_ts, int(ts_raw))
    return {
        "agent": name,
        "config_mtime": int(cfg_mtime),
        "workspace_present": workspace_present,
        "mcp_recent_hits": len(mcp_hits),
        "last_mcp_ts": last_mcp_ts,
    }


def poll_all() -> dict:
    agents = list_agents()
    queue_depth = fetch_queue_depth()
    health_rows = [agent_health(a) for a in agents]
    return {
        "ts": int(time.time()),
        "queue_depth": queue_depth,
        "agent_count": len(agents),
        "agents": health_rows,
    }


def update_state(state: dict, poll: dict) -> dict:
    state.setdefault("runs", []).append({
        "ts": poll["ts"], "queue_depth": poll["queue_depth"]})
    state["runs"] = state["runs"][-100:]  # cap
    a_state = state.setdefault("agents", {})
    for row in poll["agents"]:
        n = row["agent"]
        rec = a_state.setdefault(n, {"silent_runs": 0, "last_seen_ts": 0})
        if row["last_mcp_ts"] > rec.get("last_seen_ts", 0):
            rec["last_seen_ts"] = row["last_mcp_ts"]
            rec["silent_runs"] = 0
        else:
            rec["silent_runs"] = rec.get("silent_runs", 0) + 1
        rec["last_check_ts"] = poll["ts"]
        rec["mcp_hits_last_run"] = row["mcp_recent_hits"]
    save_state(state)
    return state


def dead_agents(state: dict) -> list[str]:
    return [n for n, rec in state.get("agents", {}).items()
            if rec.get("silent_runs", 0) >= DEAD_THRESHOLD_RUNS]


def restart_via_fleet(name: str) -> dict:
    fleet = HOME / "titan-harness" / "scripts" / "amg_fleet_orchestrator.py"
    if not fleet.exists():
        return {"ok": False, "error": "fleet missing"}
    try:
        out = subprocess.run([
            "python3", str(fleet),
            "--agents", name,
            "--task", f"Heartbeat poke: report your role + current capability in one sentence.",
            "--skip-mcp",
        ], capture_output=True, text=True, timeout=120)
        return {"ok": out.returncode in (0, 1), "exit": out.returncode}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}


def report_to_mcp(state: dict, kind: str = "summary") -> None:
    rows = state.get("agents", {})
    silent = [n for n, r in rows.items() if r.get("silent_runs", 0) >= DEAD_THRESHOLD_RUNS]
    fresh = [n for n, r in rows.items() if r.get("silent_runs", 0) == 0]
    body = json.dumps({
        "text": (
            f"agent-heartbeat {kind}: agents_total={len(rows)} "
            f"fresh={len(fresh)} dead={len(silent)} dead_list={silent[:8]}"
        ),
        "rationale": "Routine heartbeat poll across the 33-agent fleet.",
        "tags": ["agent-heartbeat", kind],
        "project_source": "titan",
    }).encode()
    try:
        req = urllib.request.Request(
            f"{MCP_BASE}/log_decision",
            data=body, headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass


def main() -> int:
    p = argparse.ArgumentParser(description="agent heartbeat monitor")
    p.add_argument("--watch", action="store_true", help="loop forever (10-min cadence)")
    p.add_argument("--report", action="store_true", help="post summary to MCP after poll")
    args = p.parse_args()

    def one_poll() -> dict:
        state = load_state()
        poll = poll_all()
        state = update_state(state, poll)
        dead = dead_agents(state)
        if dead:
            for n in dead[:5]:  # cap auto-restart attempts per cycle
                restart_via_fleet(n)
        if args.report:
            report_to_mcp(state)
        return {"poll": poll, "dead": dead}

    if not args.watch:
        out = one_poll()
        print(json.dumps({
            "agent_count": out["poll"]["agent_count"],
            "queue_depth": out["poll"]["queue_depth"],
            "dead": out["dead"],
        }, indent=2))
        return 0

    while True:
        try:
            one_poll()
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            print(f"[heartbeat] error: {e!r}", file=sys.stderr)
        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    raise SystemExit(main())
