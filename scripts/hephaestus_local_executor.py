#!/usr/bin/env python3
"""hephaestus_local_executor.py — local Codex-style code executor on Ollama.

Phase 2.8 of Hercules's MASTER BUILD ORDER 2026-04-26: $0/task code-builder
running on local Ollama. Routes to deepseek-coder-v2 by default (already
pulled per the local Ollama check). Falls back to qwen2.5-coder:7b if
deepseek-coder isn't reachable.

Same poll-claim-execute-receipt pattern as daedalus/artisan/nestor/alexander
but ZERO API cost. Uses local GPU/CPU — slower (~5-30s per task) but free.

Persona: terse code engineer. Outputs structured JSON receipt with
artifact_path/sha256 like the cloud-LLM executors so Aletheia v2's
sha256 grounding catches hallucinations.

Polls MCP for tasks tagged `agent:hephaestus` or `lane:local-coder` or
`tier:local`.

Run modes:
    hephaestus_local_executor.py --once         # drain once + exit
    hephaestus_local_executor.py --watch        # daemon, poll every --interval
    hephaestus_local_executor.py --task-id CT-X # one-shot single task

launchd: com.amg.hephaestus-local
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))

from mcp_rest_client import (  # noqa: E402
    claim_task as mcp_claim_task,
    get_task_queue as mcp_get_task_queue,
    log_decision as mcp_log_decision,
    update_task as mcp_update_task,
)

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
PRIMARY_MODEL = os.environ.get("HEPHAESTUS_MODEL", "deepseek-coder-v2:latest")
FALLBACK_MODEL = "qwen2.5-coder:7b"
LOCK_FILE = HOME / ".openclaw" / "logs" / "hephaestus_local_executor.lock"
LOG_FILE = HOME / ".openclaw" / "logs" / "hephaestus_local_executor.log"

REQUIRED_RECEIPT_KEYS = {
    "ok", "artifact_path", "artifact_hash", "stdout_tail", "exit_code", "reasoning",
}

SYSTEM_PROMPT = (
    "You are Hephaestus, AMG's local-first code engineer. You run on local "
    "Ollama (no API cost). Your specialty: code refactor, lint fix, test "
    "scaffolding, repo-wide search-and-replace. Output ONLY a single JSON "
    "object matching the schema specified in the user prompt — no markdown "
    "fences, no preamble. If the task asks you to write a file, embed the "
    "full file content in stdout_tail (the caller will write it to disk and "
    "you report the would-be path + hash). Never hallucinate paths or hashes. "
    "Be terse. Aletheia v2 verifies sha256 — fake completions get caught."
)


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with LOG_FILE.open("a") as f:
        f.write(f"[{ts}] {msg}\n")


def _matches_hephaestus(task: dict, owner: str | None = None) -> bool:
    """Match Hephaestus tasks. If owner is set, also require an owner tag — used
    by the 3-EOM-mirror so each chief gets its own dedicated Hephaestus
    instance with no cross-contamination."""
    tags = [str(t).lower() for t in (task.get("tags") or [])]
    notes = (task.get("notes") or "").lower()
    base_match = (
        "agent:hephaestus" in tags
        or "lane:local-coder" in tags
        or "tier:local" in tags
        or "dispatch: hephaestus" in notes
        or (task.get("agent_assigned") or "").lower() == "hephaestus"
    )
    if not base_match:
        return False
    if owner is None:
        # Legacy catch-all — but skip tasks with owner-style tags so the
        # owner-scoped daemons claim them exclusively (no contention).
        for tag in tags:
            if tag.startswith("owner:") or tag.startswith("for:") or tag.startswith("team:"):
                return False
        return True
    owner = owner.lower()
    return (
        f"owner:{owner}" in tags
        or f"agent:{owner}:hephaestus" in tags
        or f"team:{owner}" in tags
        or f"for:{owner}" in tags
    )


def fetch_pending(owner: str | None = None) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for status in ("approved", "pending"):
        code, body = mcp_get_task_queue(status=status, limit=50)
        if code != 200:
            continue
        for t in body.get("tasks") or []:
            tid = t.get("task_id")
            if not tid or tid in seen:
                continue
            if t.get("locked_by"):
                continue
            if _matches_hephaestus(t, owner=owner):
                out.append(t)
                seen.add(tid)
    return out


def claim(task_id: str) -> bool:
    code, body = mcp_claim_task(operator_id="hephaestus", task_id=task_id)
    return code == 200 and bool(body.get("success") or body.get("claimed"))


def update(task_id: str, status: str, summary: str | None = None,
           failure: str | None = None, deliverable: str | None = None) -> None:
    needs_hop = status in {"completed", "failed", "blocked"}
    try:
        if needs_hop:
            code1, body1 = mcp_update_task(
                task_id=task_id, status="active",
                notes="hephaestus_local: transitioning to terminal",
            )
            if code1 != 200 or not body1.get("success", True):
                _log(f"hop1-fail task={task_id} → dead_letter")
                mcp_update_task(task_id=task_id, status="dead_letter",
                                failure_reason=(failure or "hephaestus hop1 failed")[:500])
                return
        code2, body2 = mcp_update_task(
            task_id=task_id, status=status,
            result_summary=(summary or "")[:1500],
            failure_reason=(failure or None),
            deliverable_link=deliverable,
        )
        if code2 != 200 or not body2.get("success", True):
            _log(f"hop2-fail task={task_id} status={status} → dead_letter")
            mcp_update_task(task_id=task_id, status="dead_letter",
                            failure_reason=(failure or f"hop2 to {status} failed")[:500])
    except Exception as e:
        _log(f"update EXCEPTION task={task_id} → dead_letter ({e!r})")
        try:
            mcp_update_task(task_id=task_id, status="dead_letter",
                            failure_reason=f"hephaestus update exception: {e!r}"[:500])
        except Exception as e2:
            _log(f"dead_letter fallback ALSO FAILED: {e2!r}")


def _build_prompt(task: dict) -> str:
    return f"""ROLE: You are Hephaestus, AMG's local code engineer (Ollama, $0).

TASK ID: {task.get('task_id')}
OBJECTIVE: {task.get('objective','')}
CONTEXT: {task.get('context','')}
INSTRUCTIONS: {task.get('instructions','')}
ACCEPTANCE CRITERIA: {task.get('acceptance_criteria','')}

OUTPUT FORMAT — return ONLY a single JSON object (no markdown fences):
{{"ok": true|false, "artifact_path": str|null, "artifact_hash": str|null,
  "stdout_tail": str, "exit_code": 0|N, "reasoning": str}}

RULES:
- Output STARTS with `{{`, ENDS with `}}`. No prose before or after.
- For file-writing tasks: include the full file content in stdout_tail. The
  caller writes the file to disk + computes sha256. Set artifact_path to the
  intended path + artifact_hash to the sha256 you computed (or null if you
  can't compute it locally).
- For analysis tasks: put findings in stdout_tail, set artifact_path=null.
- Aletheia verifies sha256(file)==artifact_hash. Don't fake either."""


def call_ollama(model: str, prompt: str) -> tuple[dict, str]:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 4096},
        "format": "json",
    }
    req = urllib.request.Request(
        f"{OLLAMA_HOST.rstrip('/')}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read())
    msg = (resp.get("message") or {}).get("content") or ""
    return resp, msg.strip()


def parse_receipt(content: str) -> dict | None:
    s = content.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines)
    try:
        r = json.loads(s)
    except Exception:
        return None
    if not isinstance(r, dict):
        return None
    if REQUIRED_RECEIPT_KEYS - set(r.keys()):
        return None
    if not isinstance(r.get("ok"), bool):
        return None
    return r


def _maybe_write_artifact(receipt: dict) -> dict:
    """If receipt declares an artifact_path AND embeds the file body in
    stdout_tail, write it to disk and (re)compute sha256 to ensure receipt
    is grounded. Mutates receipt in place. Skips if path is None or file
    body is too short to be a real file."""
    path = receipt.get("artifact_path")
    body = receipt.get("stdout_tail") or ""
    if not path or len(body) < 50:
        return receipt
    p = pathlib.Path(path).expanduser()
    # Only write to safe directories — never overwrite arbitrary files.
    safe_roots = (HOME / "titan-harness" / "reports", HOME / "titan-harness" / "tmp",
                  pathlib.Path("/tmp"), HOME / ".openclaw" / "artifacts")
    if not any(str(p).startswith(str(r)) for r in safe_roots):
        receipt["_safe_write_skipped"] = f"path {path} outside safe-write roots"
        return receipt
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        h = hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()
        receipt["artifact_hash"] = h
        receipt["_artifact_written"] = True
    except Exception as e:
        receipt["_artifact_write_error"] = repr(e)
    return receipt


def execute_one(task: dict, owner: str | None = None) -> dict:
    tid = task.get("task_id")
    prompt = _build_prompt(task)
    t0 = time.time()
    model = PRIMARY_MODEL
    try:
        resp, content = call_ollama(model, prompt)
    except Exception as e:
        _log(f"task={tid} primary model {model} FAIL: {e!r} → trying fallback")
        try:
            model = FALLBACK_MODEL
            resp, content = call_ollama(model, prompt)
        except Exception as e2:
            _log(f"task={tid} fallback {model} also FAIL: {e2!r}")
            update(tid, "failed", failure=f"ollama call exception: {e2!r}"[:500])
            return {"ok": False, "exit_code": 1, "reasoning": f"ollama-call-exception {e2!r}"}
    latency = time.time() - t0
    receipt = parse_receipt(content)
    if receipt is None:
        _log(f"task={tid} receipt UNPARSEABLE (model={model}); raw={content[:200]!r}")
        update(tid, "failed",
               failure=f"hephaestus returned unstructured JSON; preview: {content[:300]}"[:500])
        return {"ok": False, "exit_code": 2, "reasoning": "unstructured-output"}
    receipt = _maybe_write_artifact(receipt)
    summary = (
        f"hephaestus_local receipt: ok={receipt.get('ok')} exit_code={receipt.get('exit_code')} "
        f"artifact={receipt.get('artifact_path')} hash={receipt.get('artifact_hash')} "
        f"latency={latency:.1f}s model={model} cost=$0.0000 | {receipt.get('reasoning','')[:300]}"
    )
    if receipt.get("ok"):
        update(tid, "completed", summary=summary,
               deliverable=receipt.get("artifact_path") if receipt.get("artifact_path") else None)
    else:
        update(tid, "failed",
               failure=(receipt.get("reasoning") or "ok=false")[:500])
    decision_tags = ["hephaestus-receipt", f"task:{tid}", "ollama-local", f"model:{model}"]
    if owner:
        decision_tags.extend([f"owner:{owner}", f"chief:{owner}"])
    mcp_log_decision(
        text=f"HEPHAESTUS executor receipt task={tid} ok={receipt.get('ok')} model={model} cost=$0 owner={owner or 'legacy'}",
        rationale=summary,
        tags=decision_tags,
        project_source="hephaestus",
    )
    return receipt


def drain_once(owner: str | None = None) -> dict:
    pending = fetch_pending(owner=owner)
    out = {"scanned": len(pending), "claimed": 0, "ok": 0, "fail": 0, "skipped": 0,
           "owner": owner or "legacy"}
    for t in pending:
        tid = t.get("task_id")
        if not claim(tid):
            out["skipped"] += 1
            continue
        out["claimed"] += 1
        receipt = execute_one(t, owner=owner)
        if receipt.get("ok"):
            out["ok"] += 1
        else:
            out["fail"] += 1
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=30)
    p.add_argument("--task-id", type=str, default=None)
    p.add_argument("--owner", type=str, default=None,
                   help="restrict to tasks tagged owner:<name>; per-owner lock file")
    args = p.parse_args()

    global LOCK_FILE
    if args.owner:
        LOCK_FILE = HOME / ".openclaw" / "logs" / f"hephaestus_local_executor.{args.owner}.lock"
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_fp = LOCK_FILE.open("a")
    try:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"hephaestus_local_executor (owner={args.owner or 'legacy'}): another instance holds the lock", file=sys.stderr)
        return 1

    if args.task_id:
        code, body = mcp_get_task_queue(task_id=args.task_id)
        tasks = (body or {}).get("tasks") or []
        if not tasks:
            print(f"task {args.task_id} not found")
            return 1
        if not claim(args.task_id):
            print(f"could not claim {args.task_id}")
            return 1
        receipt = execute_one(tasks[0], owner=args.owner)
        print(json.dumps(receipt, indent=2))
        return 0 if receipt.get("ok") else 1

    if args.once or not args.watch:
        result = drain_once(owner=args.owner)
        print(json.dumps(result, indent=2))
        return 0

    _log(f"hephaestus_local starting watch interval={args.interval}s primary={PRIMARY_MODEL} owner={args.owner or 'legacy'}")
    while True:
        try:
            r = drain_once(owner=args.owner)
            if r["scanned"] > 0:
                _log(f"watch drain: {r}")
        except Exception as e:
            _log(f"watch ERROR: {e!r}")
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
