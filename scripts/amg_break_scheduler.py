#!/usr/bin/env python3
"""
amg_break_scheduler.py — 90/15 work-break cadence + 03:00 deep clean.

Reads the schedule from `~/.openclaw/break_schedule.json` (auto-created with
factory defaults if missing). Default schedule:
  - 90 min work block (matches Achilles auto-restart protocol)
  - 15 min break: stop agent, archive log to R2, clear tmp, restart fresh
  - Daily 03:00 deep clean: restart all non-protected agents

Protected (never break or restart): atlas_einstein, atlas_hallucinometer,
atlas_hercules, atlas_eom, mercury.

Override hooks (by polling MCP for recent decisions):
  - tag `SKIP_BREAK` for an agent → skip the upcoming break
  - tag `EMERGENCY_RESTART` for an agent → immediate restart on next tick

Usage
-----
    amg_break_scheduler.py            # tick once (cron-friendly)
    amg_break_scheduler.py --watch    # loop with 60-s tick
    amg_break_scheduler.py --status   # print schedule + last actions
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
from datetime import datetime, timezone

HOME = pathlib.Path.home()
SCHED_FILE = HOME / ".openclaw" / "break_schedule.json"
STATE_FILE = HOME / ".openclaw" / "break_scheduler_state.json"
MCP_BASE = os.environ.get("MCP_BASE", "https://memory.aimarketinggenius.io/mcp")
LIFECYCLE = HOME / "titan-harness" / "scripts" / "agent_lifecycle_controller.py"
ARCHIVE_DIR = HOME / ".openclaw" / "archives"

PROTECTED = {"atlas_einstein", "atlas_hallucinometer", "atlas_hercules",
             "atlas_eom", "mercury"}

DEFAULT_SCHEDULE = {
    "work_block_minutes": 90,
    "break_minutes": 15,
    "deep_clean_hour_utc": 7,  # 03:00 ET ≈ 07:00-08:00 UTC, pick 7
    "agents_in_rotation": [
        "achilles", "titan", "odysseus", "hector",
        "atlas_titan", "atlas_achilles", "atlas_odysseus", "atlas_hector",
        "atlas_judge_perplexity", "atlas_judge_deepseek",
        "atlas_research_perplexity", "atlas_research_gemini",
    ],
}


def load_schedule() -> dict:
    if not SCHED_FILE.exists():
        SCHED_FILE.write_text(json.dumps(DEFAULT_SCHEDULE, indent=2))
        return DEFAULT_SCHEDULE.copy()
    try:
        return json.loads(SCHED_FILE.read_text())
    except Exception:
        return DEFAULT_SCHEDULE.copy()


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"agents": {}, "last_deep_clean_ts": 0, "actions": []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def lifecycle(action: str, agent: str, reason: str = "break") -> int:
    if not LIFECYCLE.exists():
        return -1
    try:
        out = subprocess.run([
            "python3", str(LIFECYCLE),
            f"--{action}", "--agent", agent, "--reason", reason,
        ], capture_output=True, text=True, timeout=60)
        return out.returncode
    except subprocess.TimeoutExpired:
        return -2


def archive_logs(agent: str) -> str | None:
    """Move agent workspace logs to ~/.openclaw/archives/<agent>/<ts>/.
    No-op if no logs."""
    src = HOME / ".openclaw" / "agents" / agent / "workspace"
    if not src.exists() or not any(src.iterdir()):
        return None
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    dst = ARCHIVE_DIR / agent / now_utc().strftime("%Y%m%dT%H%M%SZ")
    dst.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in src.iterdir():
        if f.suffix in (".log", ".json", ".txt", ".jsonl"):
            try:
                f.rename(dst / f.name)
                moved += 1
            except Exception:
                pass
    return str(dst) if moved else None


def fetch_overrides() -> tuple[set[str], set[str]]:
    """Return (skip_break, emergency_restart) sets keyed on agent name."""
    body = json.dumps({"count": 15}).encode()
    skip, emerg = set(), set()
    try:
        req = urllib.request.Request(
            f"{MCP_BASE}/get_recent_decisions",
            data=body, headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read() or b"{}")
        for d in (data.get("decisions") or data.get("results") or []):
            tags = d.get("tags") or []
            text = (d.get("text") or "").lower()
            for tag in tags:
                if tag.startswith("skip_break:"):
                    skip.add(tag.split(":", 1)[1].strip())
                elif tag.startswith("emergency_restart:"):
                    emerg.add(tag.split(":", 1)[1].strip())
            # alternative: text-mention pattern "SKIP_BREAK <agent>"
            if "skip_break" in text:
                for tok in text.split():
                    if tok.replace("_", "").isalpha():
                        skip.add(tok)
    except Exception:
        pass
    return skip, emerg


def log(text: str, tags: list[str]) -> None:
    body = json.dumps({
        "text": text[:1000], "tags": tags,
        "rationale": "amg_break_scheduler", "project_source": "titan",
    }).encode()
    try:
        req = urllib.request.Request(
            f"{MCP_BASE}/log_decision",
            data=body, headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass


def tick() -> dict:
    sched = load_schedule()
    state = load_state()
    skip, emerg = fetch_overrides()
    actions = []
    n = now_utc()
    work_s = sched["work_block_minutes"] * 60
    break_s = sched["break_minutes"] * 60

    # 1. Emergency restart overrides — fire immediately
    for agent in emerg:
        if agent in PROTECTED:
            continue
        rc = lifecycle("restart", agent, reason="emergency_restart")
        actions.append({"agent": agent, "action": "emergency_restart", "rc": rc})
        log(f"break_scheduler: emergency_restart {agent} rc={rc}",
            ["break-scheduler", "emergency_restart", agent])

    # 2. Per-agent break cadence
    for agent in sched.get("agents_in_rotation", []):
        if agent in PROTECTED or agent in skip:
            continue
        a_state = state["agents"].setdefault(agent, {
            "phase": "work",
            "phase_started_ts": int(n.timestamp()),
        })
        elapsed = int(n.timestamp()) - a_state["phase_started_ts"]
        if a_state["phase"] == "work" and elapsed >= work_s:
            arch = archive_logs(agent)
            rc = lifecycle("stop", agent, reason="scheduled_break")
            a_state.update({"phase": "break", "phase_started_ts": int(n.timestamp())})
            actions.append({"agent": agent, "action": "break_start",
                            "archive": arch, "rc": rc})
            log(f"break_scheduler: {agent} → break (archive={arch})",
                ["break-scheduler", "break_start", agent])
        elif a_state["phase"] == "break" and elapsed >= break_s:
            rc = lifecycle("start", agent, reason="break_complete")
            a_state.update({"phase": "work", "phase_started_ts": int(n.timestamp())})
            actions.append({"agent": agent, "action": "break_end", "rc": rc})
            log(f"break_scheduler: {agent} → work (refreshed)",
                ["break-scheduler", "break_end", agent])

    # 3. Daily deep clean at scheduled UTC hour
    if (n.hour == sched["deep_clean_hour_utc"]
        and n.timestamp() - state.get("last_deep_clean_ts", 0) > 3600):
        cleaned = []
        for agent in sched.get("agents_in_rotation", []):
            if agent in PROTECTED:
                continue
            rc = lifecycle("restart", agent, reason="daily_deep_clean")
            cleaned.append({"agent": agent, "rc": rc})
        state["last_deep_clean_ts"] = int(n.timestamp())
        actions.append({"action": "deep_clean", "agents": cleaned})
        log(f"break_scheduler: deep_clean restarted {len(cleaned)} agents",
            ["break-scheduler", "deep_clean"])

    state["actions"] = (state.get("actions", []) + actions)[-100:]
    save_state(state)
    return {"now_utc": n.isoformat(), "actions": actions}


def cmd_status() -> int:
    sched = load_schedule()
    state = load_state()
    print(json.dumps({"schedule": sched, "state_summary": {
        "agents_known": len(state.get("agents", {})),
        "last_deep_clean_ts": state.get("last_deep_clean_ts", 0),
        "recent_actions": state.get("actions", [])[-10:],
    }}, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="AMG break scheduler")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--status", action="store_true")
    args = p.parse_args()

    if args.status:
        return cmd_status()

    if args.watch:
        while True:
            try:
                tick()
            except KeyboardInterrupt:
                return 0
            except Exception as e:
                print(f"[break] error: {e!r}", file=sys.stderr)
            time.sleep(60)

    print(json.dumps(tick(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
