#!/usr/bin/env python3
"""
agent_lifecycle_controller.py — start / stop / restart / status for the agent fleet.

OpenClaw resident agents (achilles, titan, odysseus, hector, atlas_*, amg_*,
mercury) live as background ollama_chat sessions kicked off via amg-fleet
when assigned a task. They aren't long-running daemons; "start" means
"warm them up by issuing a no-op greeting task," "stop" means "kill any
running amg-fleet process for that agent," "restart" cycles those.

Kimi-stack agents (nestor, alexander, hercules) are stateless API calls;
they have no PID. status reports last MCP activity instead.

The protected agents (atlas_einstein, atlas_hallucinometer, atlas_hercules,
mercury) refuse `--stop` and `--restart` per the doctrine in §10. They can
still be `--start`-ed for explicit warm-up.

Usage
-----
    agent_lifecycle_controller.py --start   --agent achilles
    agent_lifecycle_controller.py --stop    --agent achilles
    agent_lifecycle_controller.py --restart --agent achilles
    agent_lifecycle_controller.py --status                    # all
    agent_lifecycle_controller.py --status  --agent achilles  # one
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

HOME = pathlib.Path.home()
AGENTS_DIR = HOME / ".openclaw" / "agents"
MCP_BASE = os.environ.get("MCP_BASE", "https://memory.aimarketinggenius.io/mcp")
FLEET_SCRIPT = HOME / "titan-harness" / "scripts" / "amg_fleet_orchestrator.py"
HEARTBEAT_STATE = HOME / ".openclaw" / "heartbeat_state.json"

PROTECTED = {"atlas_einstein", "atlas_hallucinometer", "atlas_hercules",
             "atlas_eom", "mercury"}
KIMI_LANE = {"nestor", "alexander", "hercules", "kimi"}

ANSI_GREEN  = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_RED    = "\033[31m"
ANSI_DIM    = "\033[2m"
ANSI_RESET  = "\033[0m"


def log_decision(text: str, tags: list[str], rationale: str = "") -> None:
    body = json.dumps({
        "text": text[:1000], "tags": tags,
        "rationale": rationale[:500] or "agent_lifecycle_controller",
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


def list_known_agents() -> list[str]:
    if not AGENTS_DIR.exists():
        return []
    return sorted([d.name for d in AGENTS_DIR.iterdir()
                   if d.is_dir() and (d / "config.toml").exists()])


def find_pids_for(agent: str) -> list[int]:
    """amg-fleet runs python3 with `--agents <name>` in argv. Match that."""
    try:
        out = subprocess.run(
            ["pgrep", "-f", f"amg_fleet_orchestrator.*--agents.*{agent}"],
            capture_output=True, text=True, timeout=5,
        )
        return [int(p) for p in out.stdout.split() if p.strip().isdigit()]
    except Exception:
        return []


def is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def cmd_start(agent: str) -> int:
    if agent in KIMI_LANE:
        log_decision(
            f"start: {agent} (Kimi-stack stateless — warm-up via API call)",
            ["lifecycle", "start", agent],
        )
        print(f"[{agent}] Kimi-stack stateless — no PID. Use dispatch bridge "
              f"to send a real task.")
        return 0
    pids = find_pids_for(agent)
    if pids:
        print(f"[{agent}] already running (pids={pids})")
        return 0
    if not FLEET_SCRIPT.exists():
        print(f"[{agent}] fleet script missing: {FLEET_SCRIPT}", file=sys.stderr)
        return 2
    log_decision(
        f"start: {agent} via amg-fleet warm-up",
        ["lifecycle", "start", agent],
    )
    p = subprocess.Popen([
        "python3", str(FLEET_SCRIPT),
        "--agents", agent,
        "--task", f"Warm-up: identify yourself in 8 words.",
        "--skip-mcp",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
       start_new_session=True)
    print(f"[{agent}] started (pid={p.pid})")
    return 0


def cmd_stop(agent: str, reason: str = "manual") -> int:
    if agent in PROTECTED:
        print(f"[{agent}] PROTECTED — refusing to stop. "
              f"Override: STOP_PROTECTED=1 env.")
        if not os.environ.get("STOP_PROTECTED"):
            return 3
    pids = find_pids_for(agent)
    if not pids:
        print(f"[{agent}] not running")
        log_decision(
            f"stop: {agent} reason={reason} (no-op, not running)",
            ["lifecycle", "stop", agent, reason],
        )
        return 0
    log_decision(
        f"stop: {agent} pids={pids} reason={reason}",
        ["lifecycle", "stop", agent, reason],
    )
    # SIGTERM
    for p in pids:
        try:
            os.kill(p, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + 10
    while time.time() < deadline:
        if all(not is_alive(p) for p in pids):
            print(f"[{agent}] graceful stop ok ({len(pids)} procs)")
            return 0
        time.sleep(0.5)
    # SIGKILL fallback
    for p in pids:
        if is_alive(p):
            try: os.kill(p, signal.SIGKILL)
            except OSError: pass
    log_decision(
        f"stop: {agent} SIGKILL fallback after 10s grace",
        ["lifecycle", "stop", "force_kill", agent],
    )
    print(f"[{agent}] force killed ({len(pids)} procs)")
    return 0


def cmd_restart(agent: str, reason: str = "manual") -> int:
    if agent in PROTECTED:
        print(f"[{agent}] PROTECTED — refusing to restart.")
        return 3
    cmd_stop(agent, reason=f"restart-{reason}")
    time.sleep(2)
    return cmd_start(agent)


def status_one(agent: str) -> dict:
    pids = find_pids_for(agent)
    state = {}
    if HEARTBEAT_STATE.exists():
        try:
            state = json.loads(HEARTBEAT_STATE.read_text()).get("agents", {}).get(agent, {})
        except Exception:
            pass
    if pids:
        color, label = ANSI_GREEN, "GREEN"
    elif state.get("silent_runs", 0) >= 3:
        color, label = ANSI_RED, "RED"
    elif state.get("silent_runs", 0) >= 1:
        color, label = ANSI_YELLOW, "YELLOW"
    else:
        color, label = ANSI_DIM, "IDLE"
    last_seen = state.get("last_seen_ts", 0)
    last_seen_iso = (
        datetime.fromtimestamp(last_seen, tz=timezone.utc).isoformat()
        if last_seen else "never"
    )
    return {
        "agent": agent, "pids": pids, "label": label, "color": color,
        "silent_runs": state.get("silent_runs", 0),
        "last_seen_iso": last_seen_iso,
    }


def cmd_status(agent: str | None) -> int:
    agents = [agent] if agent else list_known_agents()
    rows = [status_one(a) for a in agents]
    print(f"{'AGENT':28s} {'STATUS':8s} {'PIDS':12s} {'LAST_MCP_SEEN':32s} SILENT_RUNS")
    print("-" * 90)
    for r in rows:
        pids_s = ",".join(str(p) for p in r["pids"]) or "—"
        line = f"{r['agent']:28s} {r['label']:8s} {pids_s:12s} {r['last_seen_iso']:32s} {r['silent_runs']}"
        print(f"{r['color']}{line}{ANSI_RESET}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Agent lifecycle controller")
    p.add_argument("--start", action="store_true")
    p.add_argument("--stop", action="store_true")
    p.add_argument("--restart", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--agent", help="agent name (omit for status of all)")
    p.add_argument("--reason", default="manual")
    args = p.parse_args()

    if not (args.start or args.stop or args.restart or args.status):
        p.print_help()
        return 2
    if (args.start or args.stop or args.restart) and not args.agent:
        print("--agent required for start/stop/restart", file=sys.stderr)
        return 2

    if args.start:   return cmd_start(args.agent)
    if args.stop:    return cmd_stop(args.agent, reason=args.reason)
    if args.restart: return cmd_restart(args.agent, reason=args.reason)
    if args.status:  return cmd_status(args.agent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
