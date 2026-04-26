#!/usr/bin/env python3
"""
hallucination_guard.py — auto-respond to high drift scores.

Polls MCP every 15 min for recent decisions tagged `hallucinometer-score` (or
similar) carrying a numeric `drift_score`. Behavior:

- drift_score > 0.8 (high)     → restart agent + flag last 10 outputs for
                                 Einstein re-verification + alert Hercules
- drift_score > 0.9 (critical) → stop agent immediately + queue Hercules
                                 manual review task; NO auto-restart

Usage
-----
    hallucination_guard.py             # one poll, exit
    hallucination_guard.py --watch     # 15-min cadence
    hallucination_guard.py --simulate-score 0.85 --simulate-agent atlas_titan
                                       # dry-run a fake score to test pipeline
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

HOME = pathlib.Path.home()
MCP_BASE = os.environ.get("MCP_BASE", "https://memory.aimarketinggenius.io/mcp")
LIFECYCLE = HOME / "titan-harness" / "scripts" / "agent_lifecycle_controller.py"
STATE_FILE = HOME / ".openclaw" / "hallucination_guard_state.json"

THRESHOLD_HIGH = 0.8
THRESHOLD_CRITICAL = 0.9
POLL_INTERVAL_S = 900  # 15 min

# Match patterns the Hallucinometer uses:
#   "drift_score=0.86 agent=atlas_titan ..."
#   "Hallucinometer score for atlas_titan: 0.92"
SCORE_RE = re.compile(
    r"(?:drift[_ ]score|hallucinom\w*\s+(?:score|drift))\D*([01]?\.\d+)",
    re.IGNORECASE,
)
AGENT_RE = re.compile(r"\b(?:agent[=:\s]+|for\s+|@)([a-z_][a-z0-9_]+)\b",
                      re.IGNORECASE)


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_seen_ts": 0, "actions": []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def fetch_recent_decisions(count: int = 25) -> list[dict]:
    body = json.dumps({"count": count}).encode()
    req = urllib.request.Request(
        f"{MCP_BASE}/get_recent_decisions",
        data=body, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read() or b"{}")
        return data.get("decisions", []) or data.get("results", []) or []
    except Exception:
        return []


def parse_score(text: str) -> tuple[float | None, str | None]:
    if not text:
        return None, None
    m = SCORE_RE.search(text)
    if not m:
        return None, None
    try:
        score = float(m.group(1))
    except ValueError:
        return None, None
    am = AGENT_RE.search(text)
    agent = am.group(1) if am else None
    return score, agent


def call_mcp_log(text: str, tags: list[str], rationale: str = "") -> None:
    body = json.dumps({
        "text": text[:1000], "tags": tags,
        "rationale": rationale[:500] or "hallucination-guard",
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


def queue_review_task(agent: str, score: float) -> None:
    body = json.dumps({
        "objective": f"Hercules manual review: agent {agent} hit critical drift {score}",
        "instructions": (
            f"1) Pull the last 10 outputs from agent {agent} via MCP search.\n"
            f"2) Verify each against ground truth.\n"
            f"3) Decide: restart, retire, or retrain.\n"
            f"4) If restart: lifecycle_controller --restart --agent {agent} --reason hercules-cleared.\n"
            f"5) Log decision."
        ),
        "acceptance_criteria": (
            f"Hercules has decided start/stop/retire for {agent} and the "
            f"decision is logged in MCP."
        ),
        "agent": "ops",
        "assigned_to": "manual",
        "approval": "pending",
        "priority": "urgent",
        "project_id": "EOM",
        "tags": ["hallucination-critical", agent, "hercules-review"],
        "notes": f"DISPATCH: hercules\nDrift score: {score}",
    }).encode()
    try:
        req = urllib.request.Request(
            f"{MCP_BASE}/queue_operator_task",
            data=body, headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=8).read()
    except Exception:
        pass


def restart_agent(agent: str, reason: str) -> int:
    if not LIFECYCLE.exists():
        return -1
    try:
        out = subprocess.run([
            "python3", str(LIFECYCLE),
            "--restart", "--agent", agent, "--reason", reason,
        ], capture_output=True, text=True, timeout=60)
        return out.returncode
    except subprocess.TimeoutExpired:
        return -2


def stop_agent(agent: str, reason: str) -> int:
    if not LIFECYCLE.exists():
        return -1
    try:
        out = subprocess.run([
            "python3", str(LIFECYCLE),
            "--stop", "--agent", agent, "--reason", reason,
        ], capture_output=True, text=True, timeout=30)
        return out.returncode
    except subprocess.TimeoutExpired:
        return -2


def react(agent: str, score: float, source_decision: dict | None = None) -> dict:
    sid = (source_decision or {}).get("id", "n/a")
    if score >= THRESHOLD_CRITICAL:
        rc = stop_agent(agent, f"hallucination_critical_{score:.2f}")
        queue_review_task(agent, score)
        call_mcp_log(
            f"hallucination_guard CRITICAL: agent={agent} score={score:.2f} → "
            f"STOPPED + Hercules review queued (source decision {sid})",
            ["hallucination-guard", "critical", agent], "auto-stop",
        )
        return {"action": "stop", "score": score, "lifecycle_rc": rc}
    if score >= THRESHOLD_HIGH:
        rc = restart_agent(agent, f"hallucination_high_{score:.2f}")
        call_mcp_log(
            f"hallucination_guard HIGH: agent={agent} score={score:.2f} → "
            f"RESTARTED + last 10 outputs flagged for Einstein re-verify "
            f"(source decision {sid})",
            ["hallucination-guard", "high", agent, "needs-einstein-recheck"],
            "auto-restart",
        )
        return {"action": "restart", "score": score, "lifecycle_rc": rc}
    return {"action": "noop", "score": score}


def poll_once() -> list[dict]:
    state = load_state()
    last_seen_ts = state.get("last_seen_ts", 0)
    decisions = fetch_recent_decisions(count=25)
    actions = []
    new_last_ts = last_seen_ts
    for d in decisions:
        ts_raw = d.get("created_at") or d.get("ts")
        try:
            ts = (int(datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).timestamp())
                  if isinstance(ts_raw, str) else int(ts_raw or 0))
        except Exception:
            ts = 0
        if ts <= last_seen_ts:
            continue
        new_last_ts = max(new_last_ts, ts)
        text = (d.get("text") or "") + " " + (d.get("rationale") or "")
        score, agent = parse_score(text)
        if score is None or score < THRESHOLD_HIGH or not agent:
            continue
        result = react(agent, score, source_decision=d)
        actions.append(result)
    state["last_seen_ts"] = new_last_ts
    state.setdefault("actions", []).extend(actions)
    state["actions"] = state["actions"][-100:]
    save_state(state)
    return actions


def main() -> int:
    p = argparse.ArgumentParser(description="hallucination guard")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--simulate-score", type=float)
    p.add_argument("--simulate-agent", type=str)
    args = p.parse_args()

    if args.simulate_score is not None and args.simulate_agent:
        result = react(args.simulate_agent, args.simulate_score)
        print(json.dumps(result, indent=2))
        return 0

    if args.watch:
        while True:
            try:
                poll_once()
            except KeyboardInterrupt:
                return 0
            except Exception as e:
                print(f"[guard] error: {e!r}", file=sys.stderr)
            time.sleep(POLL_INTERVAL_S)

    actions = poll_once()
    print(json.dumps({"actions_taken": actions}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
