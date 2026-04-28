#!/usr/bin/env python3
"""
mercury_executor.py — Mercury's fast-poll execution daemon.

Mercury is Hercules' permanent server-side hands. He polls MCP every 30s for
tasks where `agent_assigned=mercury` (or `assigned_to=mercury`) status=pending,
atomically claims them via MCP `claim_task`, and executes.

Two execution modes:

A) Direct primitive (fast path)
   When the task's `notes` field contains a `MERCURY_ACTION:` line with a JSON
   payload describing one of:
     - ssh_run        → run an exact shell command on the VPS via SSH
     - file_read      → read a file on Mac or VPS
     - file_write     → write a file (within ~/AMG/ or /tmp/secure_staging/)
     - infisical_get  → fetch a secret from Infisical (logs only fingerprint)
     - browser_navigate / browser_screenshot → Playwright via amg_browser
     - delegate       → spawn a sub-task with new agent_assigned, then dispatch
   Mercury executes the primitive directly (no LLM), logs proof, marks done.

B) LLM-driven (fallback path)
   When no MERCURY_ACTION is present, Mercury hands the task to
   `agent_dispatch_bridge.py --task <id>` which routes through amg_fleet
   (Ollama qwen2.5:32b on VPS) with Mercury's digital_hands tools.

Concurrency: lock file at ~/.openclaw/logs/mercury_executor.lock prevents two
instances from racing.

Run modes:
    mercury_executor.py --watch       # daemon (default), poll every 30s
    mercury_executor.py --once        # drain once, exit
    mercury_executor.py --interval 30 # custom poll interval

Logs to ~/.openclaw/logs/mercury_executor.log + MCP `log_decision` tagged
`mercury-executor`.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import pathlib
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))
from mcp_rest_client import (  # noqa: E402
    queue_task as mcp_queue_task,
    get_task_queue as mcp_get_task_queue,
    claim_task as mcp_claim_task,
    update_task as mcp_update_task,
    log_decision as mcp_log_decision,
)

LOGFILE = HOME / ".openclaw" / "logs" / "mercury_executor.log"
LOCKFILE = HOME / ".openclaw" / "logs" / "mercury_executor.lock"
WAKE_FILE = HOME / ".openclaw" / "state" / "mercury_wake_now"
SSH_HOST = os.environ.get("AMG_VPS_SSH_HOST", "amg-staging")
DISPATCH_BRIDGE = HOME / "titan-harness" / "scripts" / "agent_dispatch_bridge.py"
SECURE_STAGING_VPS = "/tmp/secure_staging"
ALLOWED_WRITE_ROOTS = [
    HOME / "AMG",
    pathlib.Path("/tmp"),
    HOME / "Library" / "Logs" / "AMG",
]


def _log(msg: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    sys.stderr.write(line)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line)


def _safe_write_path(path: str) -> pathlib.Path | None:
    p = pathlib.Path(path).expanduser().resolve()
    for root in ALLOWED_WRITE_ROOTS:
        try:
            p.relative_to(root.resolve())
            return p
        except ValueError:
            continue
    return None


def parse_mercury_action(notes: str) -> dict | None:
    if not notes:
        return None
    for line in notes.splitlines():
        if line.strip().startswith("MERCURY_ACTION:"):
            payload = line.split(":", 1)[1].strip()
            try:
                return json.loads(payload)
            except Exception:
                return None
    return None


# ─── primitives ─────────────────────────────────────────────────────────────
def primitive_ssh_run(params: dict) -> dict:
    cmd = params.get("command")
    host = params.get("host", SSH_HOST)
    timeout = int(params.get("timeout_s", 60))
    if not cmd:
        return {"ok": False, "error": "ssh_run: missing command"}
    try:
        out = subprocess.run(
            ["ssh", host, cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return {
            "ok": out.returncode == 0,
            "exit": out.returncode,
            "stdout": out.stdout[-2000:],
            "stderr": out.stderr[-1000:],
            "host": host,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"ssh_run timeout {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


def primitive_file_read(params: dict) -> dict:
    path = params.get("path")
    if not path:
        return {"ok": False, "error": "file_read: missing path"}
    location = params.get("location", "local")
    if location == "vps":
        return primitive_ssh_run({"command": f"cat {shlex.quote(path)}"})
    p = pathlib.Path(path).expanduser()
    if not p.exists():
        return {"ok": False, "error": f"not found: {path}"}
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        return {"ok": True, "path": str(p), "size": len(text), "content": text[:50000]}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


def primitive_file_write(params: dict) -> dict:
    path = params.get("path")
    content = params.get("content", "")
    if not path:
        return {"ok": False, "error": "file_write: missing path"}
    safe = _safe_write_path(path)
    if not safe:
        return {"ok": False, "error": f"path outside allowed roots: {path}"}
    try:
        safe.parent.mkdir(parents=True, exist_ok=True)
        safe.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(safe), "bytes_written": len(content)}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


def primitive_infisical_get(params: dict) -> dict:
    name = params.get("name")
    env = params.get("env", "prod")
    stage_to = params.get("stage_to", f"{SECURE_STAGING_VPS}/{name}")
    if not name:
        return {"ok": False, "error": "infisical_get: missing name"}
    cmd = (
        f"mkdir -p {SECURE_STAGING_VPS} && chmod 700 {SECURE_STAGING_VPS} && "
        f"VAL=$(infisical secrets get {shlex.quote(name)} --env={shlex.quote(env)} --plain 2>/dev/null) && "
        f"if [ -z \"$VAL\" ]; then echo MISSING; exit 1; fi && "
        f"echo -n \"$VAL\" > {shlex.quote(stage_to)} && chmod 600 {shlex.quote(stage_to)} && "
        f"echo -n \"$VAL\" | shasum -a 256 | cut -c1-8"
    )
    res = primitive_ssh_run({"command": cmd, "timeout_s": 30})
    if res.get("ok"):
        fp = (res.get("stdout") or "").strip().split("\n")[-1][:8]
        return {
            "ok": True,
            "secret_name": name,
            "staged_to": stage_to,
            "fingerprint_sha256_first8": fp,
            "raw_NEVER_LOG": "[redacted]",
        }
    return {"ok": False, "error": f"infisical_get failed: {res.get('stderr') or res.get('error')}"}


def primitive_browser(params: dict, mode: str) -> dict:
    fleet = HOME / "titan-harness" / "scripts" / "amg_fleet_orchestrator.py"
    if not fleet.exists():
        return {"ok": False, "error": "fleet orchestrator missing"}
    url = params.get("url", "")
    out_path = params.get("out_path", f"/tmp/mercury_browser_{int(time.time())}.png")
    task = (
        f"Use browser_{mode} to {mode} {url}. "
        f"Save screenshot to {out_path}. Return only the file path."
    ) if mode == "screenshot" else f"Use browser_navigate to {url}. Return final URL + page title."
    try:
        out = subprocess.run(
            ["python3", str(fleet), "--agents", "mercury", "--task", task, "--skip-mcp"],
            capture_output=True, text=True, timeout=180,
        )
        return {
            "ok": out.returncode == 0,
            "exit": out.returncode,
            "stdout": out.stdout[-1500:],
            "stderr": out.stderr[-500:],
            "out_path": out_path,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "browser timeout 180s"}


def primitive_delegate(params: dict, parent_task_id: str) -> dict:
    target = params.get("delegate_to") or params.get("agent")
    if not target:
        return {"ok": False, "error": "delegate: missing delegate_to/agent"}
    payload = {
        "objective": params.get("objective", f"Delegated by Mercury → {target}")[:500],
        "instructions": params.get("instructions", "")[:5000],
        "acceptance_criteria": params.get("acceptance_criteria", "Mercury sub-task completed")[:1000],
        "priority": params.get("priority", "normal"),
        "approval": "pre_approved",
        "assigned_to": "titan",
        "agent": target if target in {"alex", "maya", "jordan", "sam", "riley", "nadia", "lumina", "ops"} else "ops",
        "tags": ["mercury-delegated", f"agent:{target}", f"parent:{parent_task_id}"],
        "notes": f"DISPATCH: {target}\nDELEGATED_FROM: mercury\nPARENT: {parent_task_id}",
        "parent_task_id": parent_task_id,
    }
    code, body = mcp_queue_task(payload)
    if code == 200 and (body.get("success") or body.get("task_id")):
        new_id = body.get("task_id") or body.get("id")
        # immediate dispatch — don't wait for the */5 cron
        try:
            subprocess.Popen(
                ["python3", str(DISPATCH_BRIDGE), "--task-id", str(new_id)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            _log(f"delegate-dispatch-spawn failed: {e!r}")
        return {"ok": True, "delegated_task_id": new_id, "delegated_to": target}
    return {"ok": False, "error": f"delegate queue failed: code={code} body={str(body)[:200]}"}


# ─── execution dispatch ─────────────────────────────────────────────────────
def execute_task(task: dict) -> dict:
    task_id = task.get("task_id") or task.get("id")
    notes = task.get("notes") or ""
    action = parse_mercury_action(notes)

    if action and action.get("type"):
        kind = action["type"]
        params = action.get("params", {}) or {}
        t0 = time.time()
        if kind == "ssh_run":
            result = primitive_ssh_run(params)
        elif kind == "file_read":
            result = primitive_file_read(params)
        elif kind == "file_write":
            result = primitive_file_write(params)
        elif kind == "infisical_get":
            result = primitive_infisical_get(params)
        elif kind in {"browser_navigate", "browser_screenshot"}:
            mode = "navigate" if kind == "browser_navigate" else "screenshot"
            result = primitive_browser(params, mode)
        elif kind == "delegate":
            result = primitive_delegate(params, task_id or "unknown")
        else:
            result = {"ok": False, "error": f"unknown mercury_action.type: {kind}"}
        result["mode"] = "primitive"
        result["primitive"] = kind
        result["latency_ms"] = int((time.time() - t0) * 1000)
        return result

    # Hercules dispatch 2026-04-26: BENCH the LLM-fallback path. Mercury's
    # job is now primitives ONLY (ssh_run, file_read, file_write,
    # infisical_get, browser_*, delegate). Tasks without a MERCURY_ACTION
    # directive are REJECTED + requeued for Daedalus / Artisan via a
    # tag-injection in notes. The old fallback caused fake completions
    # (CT-0426-37) because Mercury saved Qwen 32B's tool-call argument
    # JSON verbatim into result_summary without verification. New path is
    # mechanically reject-and-requeue — never produce a fake completion.
    #
    # Override (NOT recommended): set MERCURY_LLM_FALLBACK_ENABLED=true to
    # restore the legacy behavior. Logs a warning every fallback so it's
    # auditable.
    if not task_id:
        return {"ok": False, "error": "no task_id for reject/requeue", "mode": "no-primitive"}
    if os.environ.get("MERCURY_LLM_FALLBACK_ENABLED", "").lower() == "true":
        _log(f"WARNING task={task_id} using LEGACY LLM-fallback path (MERCURY_LLM_FALLBACK_ENABLED=true)")
        try:
            out = subprocess.run(
                ["python3", str(DISPATCH_BRIDGE), "--task-id", str(task_id)],
                capture_output=True, text=True, timeout=420,
            )
            return {
                "ok": out.returncode == 0,
                "mode": "llm-legacy",
                "stdout": out.stdout[-2000:],
                "stderr": out.stderr[-800:],
                "error": None if out.returncode == 0 else f"dispatch_bridge exit {out.returncode}: {(out.stderr or out.stdout or '')[-300:]}",
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "mode": "llm-legacy", "error": "dispatch_bridge timeout 420s"}
        except Exception as e:
            return {"ok": False, "mode": "llm-legacy", "error": f"dispatch_bridge exception: {e!r}"}
    # Default path: reject + requeue to Daedalus.
    existing_notes = task.get("notes") or ""
    requeue_marker = f"\nREQUEUE_TAG: agent:daedalus reason=mercury-no-primitive ts={datetime.now(timezone.utc).isoformat()}"
    try:
        mcp_update_task(
            task_id=task_id, status="active",
            notes=existing_notes + requeue_marker,
        )
        mcp_update_task(
            task_id=task_id, status="approved",
            notes=existing_notes + requeue_marker,
        )
    except Exception as e:
        _log(f"reject-requeue update failed task={task_id}: {e!r}")
    _log(f"task={task_id} REJECT-REQUEUE: no MERCURY_ACTION primitive; tagged for daedalus")
    return {
        "ok": False,
        "mode": "reject-requeue",
        "error": "mercury accepts primitives only; requeued for agent:daedalus",
    }


# ─── MCP loop ───────────────────────────────────────────────────────────────
def fetch_one_by_id(task_id: str) -> dict | None:
    """Direct task lookup — O(1). Used when wake-file delivers a specific id."""
    code, body = mcp_get_task_queue(task_id=task_id)
    if code != 200:
        return None
    tasks = body.get("tasks") or []
    return tasks[0] if tasks else None


def is_mercury_eligible(task: dict) -> tuple[bool, str]:
    """CT-0428-recovery / mercury_phase1_patch (Solon directive 2026-04-28).

    Mercury claims ONLY rows that carry a Mercury or Hercules domain marker.
    Raw assigned_to='titan' rows WITHOUT those markers are SKIPPED — Iris v0.3
    mails them and Titan-the-Claude-Code-session picks up manually. Same
    skip applies to raw assigned_to='manual' / 'n8n' / 'achilles' rows that
    landed in Mercury's titan-scoped fetch via tag/note quirk.

    Returns (eligible, reason). Reason is logged on every skip.
    """
    notes = (task.get("notes") or "").lower()
    tags = [str(x).lower() for x in (task.get("tags") or [])]
    assigned_to = (task.get("assigned_to") or "").lower()
    agent_assigned = (task.get("agent_assigned") or "").lower()

    has_mercury_marker = (
        "dispatch: mercury" in notes
        or "agent:mercury" in tags
        or "mercury" in tags
        or agent_assigned == "mercury"
    )
    has_hercules_marker = (
        "dispatch: hercules" in notes
        or "agent:hercules" in tags
        or "hercules" in tags
        or "hercules-domain" in tags
        or agent_assigned == "hercules"
    )

    if has_mercury_marker:
        return True, "mercury-marker"
    if has_hercules_marker:
        return True, "hercules-domain"
    return False, f"raw-{assigned_to or 'unknown'}-no-marker (mercury_phase1_patch)"


def fetch_pending_for_mercury(limit: int = 5) -> list[dict]:
    """Polling fallback. When no wake-file fires (task queued by something
    other than the bridge — e.g., another agent calling queue_operator_task
    directly via MCP), Mercury still needs to find its work.

    Server can't filter on tags/notes, so we pull a wider window (50) and
    client-side filter for `dispatch: mercury` or `agent:mercury`."""
    out: list[dict] = []
    seen_ids: set[str] = set()
    SCAN_LIMIT = 50
    for status in ("approved", "pending"):
        code, body = mcp_get_task_queue(status=status, assigned_to="titan", limit=SCAN_LIMIT)
        if code != 200:
            continue
        for t in body.get("tasks") or []:
            tid = t.get("task_id") or t.get("id")
            if not tid or tid in seen_ids:
                continue
            # skip already-locked tasks
            if t.get("locked_by") and t.get("locked_by") != "mercury":
                continue
            eligible, reason = is_mercury_eligible(t)
            if eligible:
                out.append(t)
                seen_ids.add(tid)
            else:
                _log(f"FETCH-SKIP task={tid} reason={reason}")
            if len(out) >= limit:
                break
        if len(out) >= limit:
            break
    return out


def claim_task(task_id: str) -> bool:
    code, body = mcp_claim_task(operator_id="mercury", task_id=task_id)
    return code == 200 and bool(body.get("success") or body.get("claimed"))


def update_task(task_id: str, status: str, summary: str | None = None, error: str | None = None) -> None:
    """The MCP server FSM:
      locked → active|approved|dead_letter
      active → completed|failed|blocked|pending_qc|dead_letter
    Direct locked → completed is rejected — must hop through active first.
    The terminal-success state is 'completed' (not 'done').

    Lock-leak guard: if the second hop (active → terminal) fails for any reason,
    fall back to dead_letter (allowed direct from locked) so the task never
    stays stuck. Logs every step so warden can correlate."""
    if status == "done":
        status = "completed"  # MCP terminology
    needs_hop = status in {"completed", "failed", "blocked"}
    try:
        if needs_hop:
            code1, body1 = mcp_update_task(
                task_id=task_id, status="active",
                notes="mercury_executor: transitioning to terminal",
            )
            if code1 != 200 or not body1.get("success", True):
                # First hop failed — try direct dead_letter (allowed from locked)
                _log(f"update_task hop1-fail task={task_id} code={code1} body={body1!r:.200} → falling to dead_letter")
                mcp_update_task(
                    task_id=task_id, status="dead_letter",
                    failure_reason=(error or "mercury hop1 failed")[:500],
                )
                return
        code2, body2 = mcp_update_task(
            task_id=task_id, status=status,
            result_summary=summary, failure_reason=error,
        )
        if code2 != 200 or not body2.get("success", True):
            _log(f"update_task hop2-fail task={task_id} status={status} code={code2} body={body2!r:.200} → falling to dead_letter")
            mcp_update_task(
                task_id=task_id, status="dead_letter",
                failure_reason=(error or f"mercury hop2 to {status} failed")[:500],
            )
    except Exception as e:
        # Final safety net — never leave a task locked
        _log(f"update_task EXCEPTION task={task_id} status={status} err={e!r} → dead_letter")
        try:
            mcp_update_task(
                task_id=task_id, status="dead_letter",
                failure_reason=f"mercury update_task exception: {e!r}"[:500],
            )
        except Exception as e2:
            _log(f"update_task dead_letter fallback ALSO FAILED task={task_id} err={e2!r} — task may leak")
            raise


def log_proof(task: dict, result: dict) -> None:
    task_id = task.get("task_id") or task.get("id") or "unknown"
    summary = (
        f"Mercury executed task {task_id} mode={result.get('mode')} "
        f"primitive={result.get('primitive', 'n/a')} ok={result.get('ok')} "
        f"latency_ms={result.get('latency_ms', 'n/a')}"
    )
    redacted = {k: v for k, v in result.items() if k != "raw_NEVER_LOG"}
    mcp_log_decision(
        text=summary,
        rationale=(
            f"mercury_executor.py picked up task and ran. Result snapshot: "
            f"{json.dumps(redacted)[:1500]}"
        ),
        tags=["mercury-executor", "mercury-proof", f"task:{task_id}", "hercules"],
        project_source="titan",
    )


def drain_once(limit: int = 5, wake_task_id: str | None = None) -> dict:
    """If wake_task_id is given, do O(1) lookup + claim + execute that one
    task. Otherwise broader poll fallback."""
    if wake_task_id:
        t = fetch_one_by_id(wake_task_id)
        if not t:
            _log(f"wake task_id={wake_task_id} not found in queue")
            return {"scanned": 0, "claimed": 0, "executed": 0, "failed": 0,
                    "wake_id_not_found": wake_task_id}
        eligible, reason = is_mercury_eligible(t)
        if not eligible:
            _log(f"wake task_id={wake_task_id} not Mercury-eligible reason={reason}; skipping")
            return {"scanned": 1, "claimed": 0, "executed": 0, "failed": 0,
                    "wake_id_not_eligible": wake_task_id, "reason": reason}
        tasks = [t]
    else:
        tasks = fetch_pending_for_mercury(limit=limit)
    results = {"scanned": len(tasks), "claimed": 0, "executed": 0, "failed": 0, "skipped_phase1": 0}
    for t in tasks:
        tid = t.get("task_id") or t.get("id")
        if not tid:
            continue
        # Belt-and-suspenders: re-verify Mercury eligibility right before claim.
        # Even if fetch_pending_for_mercury / wake-path drift, we never claim a
        # raw-titan row without markers (mercury_phase1_patch).
        eligible, reason = is_mercury_eligible(t)
        if not eligible:
            _log(f"CLAIM-SKIP task={tid} reason={reason}")
            results["skipped_phase1"] += 1
            continue
        if not claim_task(tid):
            _log(f"claim failed for {tid} (already claimed?)")
            continue
        results["claimed"] += 1
        update_task(tid, "in_progress", summary="claimed by mercury_executor")
        try:
            res = execute_task(t)
        except Exception as e:
            res = {"ok": False, "error": f"executor exception: {e!r}", "mode": "exception"}
        log_proof(t, res)
        if res.get("ok"):
            update_task(tid, "done", summary=json.dumps({k: v for k, v in res.items() if k != "raw_NEVER_LOG"})[:1500])
            results["executed"] += 1
            _log(f"OK task={tid} mode={res.get('mode')} primitive={res.get('primitive','n/a')}")
        else:
            update_task(tid, "failed", error=str(res.get("error") or "unknown"))
            results["failed"] += 1
            _log(f"FAIL task={tid} err={res.get('error')!r}")
    return results


def acquire_lock() -> int:
    LOCKFILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(LOCKFILE), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return -1
    os.write(fd, str(os.getpid()).encode())
    return fd


def main() -> int:
    p = argparse.ArgumentParser(description="Mercury executor — fast-poll MCP for Mercury tasks")
    p.add_argument("--once", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=30)
    p.add_argument("--limit", type=int, default=5)
    args = p.parse_args()

    fd = acquire_lock()
    if fd < 0:
        _log("another mercury_executor is running; exiting")
        return 0

    if args.once or not args.watch:
        results = drain_once(limit=args.limit)
        print(json.dumps(results, indent=2))
        return 0

    _log(f"mercury_executor starting watch interval={args.interval}s wake_file={WAKE_FILE}")
    WAKE_FILE.parent.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            results = drain_once(limit=args.limit)
            if results["scanned"] > 0:
                _log(f"poll: scanned={results['scanned']} executed={results['executed']} failed={results['failed']}")
            # Sleep loop with wake-file check every 1s. When bridge writes a
            # task_id to the wake file, executor breaks out and does an O(1)
            # claim + execute on that specific task.
            slept = 0
            while slept < args.interval:
                if WAKE_FILE.exists():
                    try:
                        wake_content = WAKE_FILE.read_text().strip()
                    except Exception:
                        wake_content = ""
                    try:
                        WAKE_FILE.unlink()
                    except FileNotFoundError:
                        pass
                    if wake_content:
                        _log(f"wake-file triggered: task_id={wake_content}")
                        wake_results = drain_once(limit=1, wake_task_id=wake_content)
                        if wake_results.get("executed"):
                            _log(f"wake-execute OK task_id={wake_content}")
                        elif wake_results.get("failed"):
                            _log(f"wake-execute FAIL task_id={wake_content}")
                    else:
                        _log("wake-file triggered (no task_id) — broad poll")
                        drain_once(limit=args.limit)
                    break
                time.sleep(1)
                slept += 1
        except KeyboardInterrupt:
            _log("mercury_executor stopping (KeyboardInterrupt)")
            return 0
        except Exception as e:
            _log(f"poll error: {e!r}")
            time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
