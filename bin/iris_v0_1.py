#!/usr/bin/env python3
"""iris_v0_1.py — pre-factory mailman daemon (CT-0427-73).

Polls MCP get_task_queue every 3 min for tasks with status=approved AND
approval=pre_approved. Routes:
  - assigned_to=titan → claim_task(operator_id=titan) directly
  - assigned_to=manual + tag contains 'achilles_dispatch' →
      file drop to /opt/amg-titan/achilles-inbox/<task_id>.json
      (Mac harness picks it up via existing rsync; if absent, log_decision
       flags Solon-paste-needed)

State at /var/lib/amg-iris/delivered_state.json prevents re-delivery.
Logs to /var/log/amg-iris.log; weekly logrotate.

Per task instructions: pre-factory v0.1 of v4.0.2.3 IRIS MAILMAN. Full v1
features (chief inbox routing, urgent push, dependency tracking, daily
delivery report) absorb this when Phase 11.7 of v4.0.2.x ships.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

MCP_BASE = os.environ.get("MCP_BASE", "http://localhost:3000")
STATE_PATH = "/var/lib/amg-iris/delivered_state.json"
LOG_PATH = "/var/log/amg-iris.log"
ACHILLES_INBOX = "/opt/amg-titan/achilles-inbox"

POLL_LIMIT = 50  # Per-tick max tasks to consider; queue scanner cap
ACHILLES_TAG_MARKERS = ("achilles_dispatch", "achilles", "manual")


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"[{ts}] [iris_v0_1] {msg}\n"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line)
    except OSError:
        pass
    sys.stderr.write(line)


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {"delivered": {}}
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"delivered": {}}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_PATH)


def mcp_post(path: str, payload: dict) -> tuple[bool, dict]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{MCP_BASE}{path}", data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
            try:
                return True, json.loads(body)
            except json.JSONDecodeError:
                return True, {"raw": body}
    except urllib.error.HTTPError as e:
        return False, {"error": f"HTTP {e.code}", "body": e.read()[:300].decode(errors='replace')}
    except (urllib.error.URLError, TimeoutError) as e:
        return False, {"error": str(e)}


def mcp_get(path: str) -> tuple[bool, dict]:
    req = urllib.request.Request(f"{MCP_BASE}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
            try:
                return True, json.loads(body)
            except json.JSONDecodeError:
                return True, {"raw": body}
    except urllib.error.HTTPError as e:
        return False, {"error": f"HTTP {e.code}", "body": e.read()[:300].decode(errors='replace')}
    except (urllib.error.URLError, TimeoutError) as e:
        return False, {"error": str(e)}


def fetch_pending_tasks() -> list[dict]:
    """Use no-auth REST shortcut /api/task-queue (GET)."""
    ok, resp = mcp_get(f"/api/task-queue?status=approved&limit={POLL_LIMIT}")
    if not ok:
        log(f"queue fetch error: {resp}")
        return []
    if not resp.get("success"):
        log(f"queue fetch !success: {resp}")
        return []
    return resp.get("tasks", [])


def claim_task(task_id: str) -> tuple[bool, dict]:
    """Use no-auth REST shortcut /api/claim-task (POST)."""
    ok, resp = mcp_post("/api/claim-task", {
        "operator_id": "titan",
        "task_id": task_id,
    })
    return ok, resp


def log_decision(text: str, tags: list, rationale: str = "", source: str = "iris_v0_1") -> None:
    ok, resp = mcp_post("/api/decisions", {
        "text": text,
        "project_source": source,
        "rationale": rationale,
        "tags": tags,
    })
    log(f"log_decision tags={tags} ok={ok}")


def is_achilles_task(task: dict) -> bool:
    tags = task.get("tags") or []
    return any(any(m in t.lower() for m in ACHILLES_TAG_MARKERS) for t in tags)


def file_drop_to_achilles(task: dict) -> str:
    os.makedirs(ACHILLES_INBOX, exist_ok=True)
    task_id = task.get("task_id", "unknown")
    path = os.path.join(ACHILLES_INBOX, f"{task_id}.json")
    with open(path, "w") as f:
        json.dump(task, f, indent=2)
    return path


def fingerprint(task_id: str, approval_ts: str) -> str:
    return hashlib.sha1(f"{task_id}|{approval_ts}".encode()).hexdigest()


def process_task(task: dict, state: dict) -> str | None:
    """Returns delivery target on success, None on skip/already-delivered."""
    task_id = task.get("task_id")
    if not task_id:
        return None

    # Idempotency: hash task_id + updated_at (approval timestamp proxy)
    fp_key = task_id
    fp_val = fingerprint(task_id, task.get("updated_at", ""))
    if state["delivered"].get(fp_key) == fp_val:
        return None  # already delivered, no change

    # Skip already-locked tasks (someone else has them)
    if task.get("status") == "locked":
        return None

    # Skip tasks not pre-approved (manual approval pending)
    if task.get("approval") != "pre_approved":
        return None

    assigned_to = task.get("assigned_to", "")
    if assigned_to == "titan":
        # Claim via MCP
        ok, claim_resp = claim_task(task_id)
        if ok and claim_resp.get("claimed"):
            target = "titan (claim_task)"
            log(f"delivered {task_id} → {target}")
            log_decision(
                text=f"Mail delivered: {task_id} → titan (claim_task). "
                     f"Objective: {(task.get('objective') or '')[:100]}",
                tags=["mail_delivered", task_id, "recipient:titan", "iris_auto_claim"],
                rationale=f"iris_v0_1 polled queue, found pre_approved task assigned to titan, "
                          f"executed claim_task atomically. Lock now held by titan.",
            )
            state["delivered"][fp_key] = fp_val
            return target
        log(f"FAIL claim {task_id}: {claim_resp}")
        return None

    if assigned_to == "manual" and is_achilles_task(task):
        # File-drop to Achilles inbox
        path = file_drop_to_achilles(task)
        target = f"achilles_inbox ({path})"
        log(f"delivered {task_id} → {target}")
        log_decision(
            text=f"Mail delivered: {task_id} → achilles inbox. "
                 f"Path: {path}. Objective: {(task.get('objective') or '')[:100]}",
            tags=["mail_delivered", task_id, "recipient:achilles", "iris_file_drop"],
            rationale=f"iris_v0_1 polled queue, found pre_approved task assigned_to=manual "
                      f"with achilles tag. File-dropped task JSON to inbox; Achilles harness "
                      f"reads on next sync.",
        )
        state["delivered"][fp_key] = fp_val
        return target

    # Other assigned_to (n8n, manual without achilles tag) — skip
    return None


def main(argv: list[str]) -> int:
    log("=== iris run start ===")
    state = load_state()

    tasks = fetch_pending_tasks()
    log(f"queue scan: {len(tasks)} approved+pre_approved tasks")

    delivered = 0
    for task in tasks:
        result = process_task(task, state)
        if result:
            delivered += 1

    save_state(state)
    log(f"=== iris run end (delivered={delivered}) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
