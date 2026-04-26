#!/usr/bin/env python3
"""
hercules_mcp_bridge.py — Hercules' outbox → MCP op_task_queue daemon.

Hercules (Kimi K2.6 in Solon's web tab) cannot write to MCP directly. He
writes a dispatch JSON to ~/AMG/hercules-outbox/dispatch_<TS>.json (either
manually via `bin/hercules-paste`, a future Chrome extension, or by Solon
copy-pasting). This daemon watches that folder, validates each JSON, posts it
to MCP via `queue_operator_task`, and archives the file to
~/AMG/hercules-archive/dispatched/.

Schema for outbox JSON (minimum required):
    {
      "objective": "...",                       (required)
      "instructions": "...",                    (required, numbered steps)
      "acceptance_criteria": "...",             (required)
      "agent_assigned": "mercury",              (default mercury if absent)
      "priority": "P0|P1|P2|P3",                (default P2)
      "tags": ["hercules-dispatch", ...],
      "proof_required": "...",
      "escalation_on_failure": "...",
      "context": "...",
      "campaign_id": "...",
      "project_id": "EOM",
      "mercury_action": {                       (optional — explicit primitive)
        "type": "ssh_run | file_read | file_write | infisical_get | browser_navigate | delegate",
        "params": { ... }
      }
    }

Run modes:
    hercules_mcp_bridge.py --watch        # daemon, poll every 30s (default)
    hercules_mcp_bridge.py --once         # drain once, exit
    hercules_mcp_bridge.py --interval 30  # custom poll interval (seconds)

Logs to ~/.openclaw/logs/hercules_mcp_bridge.log and posts every ingestion to
MCP `log_decision` with tag `hercules-mcp-bridge`.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))
from mcp_rest_client import queue_task as mcp_queue_task, log_decision as mcp_log_decision  # noqa: E402

OUTBOX = HOME / "AMG" / "hercules-outbox"
ARCHIVE = HOME / "AMG" / "hercules-archive" / "dispatched"
ERRORS = HOME / "AMG" / "hercules-archive" / "errors"
LOGFILE = HOME / ".openclaw" / "logs" / "hercules_mcp_bridge.log"
MERCURY_EXECUTOR = HOME / "titan-harness" / "scripts" / "mercury_executor.py"

VALID_PRIORITIES = {"P0", "P1", "P2", "P3", "urgent", "normal", "low"}
PRIORITY_MAP = {"P0": "urgent", "P1": "urgent", "P2": "normal", "P3": "low"}

REQUIRED_FIELDS = {"objective", "instructions", "acceptance_criteria"}


def _log(msg: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    sys.stderr.write(line)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line)


def validate_dispatch(d: dict) -> tuple[bool, str]:
    missing = REQUIRED_FIELDS - set(d.keys())
    if missing:
        return False, f"missing required fields: {sorted(missing)}"
    pri = d.get("priority", "P2")
    if pri not in VALID_PRIORITIES:
        return False, f"invalid priority: {pri}"
    return True, "ok"


def to_mcp_payload(d: dict) -> dict:
    pri = d.get("priority", "P2")
    pri_norm = PRIORITY_MAP.get(pri, pri if pri in {"urgent", "normal", "low"} else "normal")
    agent_assigned = d.get("agent_assigned", "mercury")
    tags = list(d.get("tags") or [])
    if "hercules-dispatch" not in tags:
        tags.append("hercules-dispatch")
    if agent_assigned and f"agent:{agent_assigned}" not in tags:
        tags.append(f"agent:{agent_assigned}")
    notes_lines = [f"DISPATCH: {agent_assigned}"]
    if d.get("proof_required"):
        notes_lines.append(f"PROOF: {d['proof_required']}")
    if d.get("escalation_on_failure"):
        notes_lines.append(f"ESCALATE: {d['escalation_on_failure']}")
    if d.get("mercury_action"):
        notes_lines.append("MERCURY_ACTION: " + json.dumps(d["mercury_action"]))
    if d.get("source"):
        notes_lines.append(f"SOURCE: {d['source']}")
    if d.get("hercules_session_id"):
        notes_lines.append(f"HERCULES_SESSION: {d['hercules_session_id']}")
    payload = {
        "objective": d["objective"][:500],
        "instructions": d["instructions"][:5000],
        "acceptance_criteria": d["acceptance_criteria"][:1000],
        "priority": pri_norm,
        "approval": d.get("approval", "pre_approved"),
        "assigned_to": "titan" if agent_assigned not in {"alex", "maya", "jordan", "sam", "riley", "nadia", "lumina", "ops"} else "titan",
        "agent": d.get("agent") or ("ops" if agent_assigned not in {"alex", "maya", "jordan", "sam", "riley", "nadia", "lumina"} else agent_assigned),
        "tags": tags[:10],
        "notes": "\n".join(notes_lines)[:2000],
    }
    if d.get("context"):
        payload["context"] = d["context"][:2000]
    if d.get("campaign_id"):
        payload["campaign_id"] = d["campaign_id"]
    if d.get("project_id"):
        payload["project_id"] = d["project_id"]
    if d.get("output_target"):
        payload["output_target"] = d["output_target"]
    return payload


MERCURY_WAKE_FILE = HOME / ".openclaw" / "state" / "mercury_wake_now"


def _wake_mercury_now(task_id: str, agent_assigned: str) -> None:
    """Push-notification pattern. When a Mercury dispatch lands, write the
    task_id to the wake file. The supervised mercury_executor polls the file
    every 1s during its sleep cycle, reads the task_id, and does an O(1)
    direct lookup + claim + execute. Net effect: ~1s end-to-end (outbox JSON
    → executor execution)."""
    if agent_assigned != "mercury":
        return
    try:
        MERCURY_WAKE_FILE.parent.mkdir(parents=True, exist_ok=True)
        MERCURY_WAKE_FILE.write_text(str(task_id))
        _log(f"wake-file written task_id={task_id}")
    except Exception as e:
        _log(f"wake-file write failed: {e!r} — falling back to spawn")
        if MERCURY_EXECUTOR.exists():
            try:
                subprocess.Popen(
                    ["python3", str(MERCURY_EXECUTOR), "--once", "--limit", "10"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                _log(f"fallback spawn fired mercury_executor for task={task_id}")
            except Exception as e2:
                _log(f"fallback spawn failed: {e2!r}")


def ingest_one(path: pathlib.Path) -> tuple[bool, str]:
    try:
        raw = path.read_text(encoding="utf-8")
        d = json.loads(raw)
    except Exception as e:
        return False, f"parse error: {e!r}"
    ok, reason = validate_dispatch(d)
    if not ok:
        return False, reason
    payload = to_mcp_payload(d)
    code, body = mcp_queue_task(payload)
    if code != 200 or not body.get("success", body.get("task_id")):
        return False, f"MCP queue failed code={code} body={str(body)[:300]}"
    task_id = body.get("task_id") or body.get("id") or body.get("task") or "unknown"
    agent_assigned = d.get("agent_assigned", "mercury")
    mcp_log_decision(
        text=(
            f"Hercules dispatch ingested: task_id={task_id} agent={agent_assigned} "
            f"objective={d['objective'][:200]}"
        ),
        rationale=(
            f"hercules_mcp_bridge.py picked up {path.name} from outbox, validated, queued. "
            f"priority={payload['priority']} tags={payload['tags']}"
        ),
        tags=["hercules-mcp-bridge", "hercules-dispatch", f"agent:{agent_assigned}"],
        project_source="titan",
    )
    _wake_mercury_now(task_id, agent_assigned)
    return True, f"queued task_id={task_id} (mercury wake={'yes' if agent_assigned=='mercury' else 'no'})"


def drain_outbox(once: bool = False) -> dict:
    OUTBOX.mkdir(parents=True, exist_ok=True)
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    ERRORS.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in OUTBOX.glob("*.json") if p.is_file())
    results = {"scanned": len(files), "queued": 0, "errors": 0}
    for p in files:
        ok, msg = ingest_one(p)
        if ok:
            target = ARCHIVE / p.name
            shutil.move(str(p), str(target))
            _log(f"INGEST OK {p.name} → {msg}")
            results["queued"] += 1
        else:
            stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            target = ERRORS / f"{stamp}__{p.name}"
            shutil.move(str(p), str(target))
            _log(f"INGEST ERR {p.name} → {msg} [moved to errors/]")
            results["errors"] += 1
    return results


def main() -> int:
    p = argparse.ArgumentParser(description="Hercules outbox → MCP queue bridge")
    p.add_argument("--once", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=30, help="poll interval (seconds)")
    args = p.parse_args()

    if args.once or not args.watch:
        results = drain_outbox(once=True)
        print(json.dumps(results, indent=2))
        return 0

    _log(f"hercules_mcp_bridge starting watch mode interval={args.interval}s outbox={OUTBOX}")
    while True:
        try:
            results = drain_outbox()
            if results["scanned"] > 0:
                _log(f"poll: scanned={results['scanned']} queued={results['queued']} errors={results['errors']}")
        except KeyboardInterrupt:
            _log("hercules_mcp_bridge stopping (KeyboardInterrupt)")
            return 0
        except Exception as e:
            _log(f"poll error: {e!r}")
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
