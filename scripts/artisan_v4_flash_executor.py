#!/usr/bin/env python3
"""artisan_v4_flash_executor.py — Artisan poll-execute daemon backed by
DeepSeek V4 Flash (api.deepseek.com).

Same shape as daedalus_v4_pro_executor.py with two differences:
  1. Cheaper model (V4 Flash) at lower per-task cost
  2. Auto-rejects tasks with >3 distinct steps (counted by numbered list
     in `instructions`); requeues them for Daedalus by appending an
     agent:daedalus tag via update_task notes.

Cost gate: $10/day via lib/cost_kill_switch.py (sqlite, NOT Redis).

Polls MCP for tasks tagged:
  - agent:artisan
  - tier:v4_flash
  - or notes contains DISPATCH: artisan

Logs: ~/.openclaw/logs/artisan_v4_flash_executor.{out,err}.log
launchd: com.amg.artisan-v4-flash
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import pathlib
import re
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

try:
    from cost_kill_switch import KillSwitch  # noqa: E402
except Exception:
    KillSwitch = None

try:
    from chief_cost_gate import ChiefCostGate  # noqa: E402
except Exception:
    ChiefCostGate = None

DEEPSEEK_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-v4-flash"
SSH_HOST = "amg-staging"
DAILY_CAP_USD = 10.0
MAX_STEPS = 3
LOCK_FILE = HOME / ".openclaw" / "logs" / "artisan_v4_flash_executor.lock"
LOG_FILE = HOME / ".openclaw" / "logs" / "artisan_v4_flash_executor.log"

REQUIRED_RECEIPT_KEYS = {
    "ok", "artifact_path", "artifact_hash", "stdout_tail", "exit_code", "reasoning",
}

STEP_PATTERN = re.compile(r"(?m)^\s*(?:\d+[.)]|step\s+\d+[:.])\s+", re.IGNORECASE)
PHASE_PATTERN = re.compile(r"(?m)^\s*phase\s+\d+", re.IGNORECASE)


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with LOG_FILE.open("a") as f:
        f.write(f"[{ts}] {msg}\n")


_API_KEY_CACHE: str | None = None

def _resolve_api_key() -> str:
    """Cached after first hit — avoids per-poll SSH (VPS sshd throttling)."""
    global _API_KEY_CACHE
    if _API_KEY_CACHE:
        return _API_KEY_CACHE
    env_key = os.environ.get("DEEPSEEK_API_KEY")
    if env_key:
        _API_KEY_CACHE = env_key
        return env_key
    out = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=8", SSH_HOST,
         "grep '^DEEPSEEK_API_KEY=' /etc/amg/deepseek.env | cut -d= -f2-"],
        capture_output=True, text=True, timeout=15,
    )
    if out.returncode != 0:
        raise RuntimeError(f"could not read DEEPSEEK_API_KEY: {out.stderr[:200]}")
    key = out.stdout.strip()
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY empty on VPS")
    _API_KEY_CACHE = key
    return key


def _matches_artisan(task: dict, owner: str | None = None) -> bool:
    """Match Artisan tasks. If owner is set, ALSO require an owner tag — used by
    the 3-EOM-mirror so each chief (hercules/nestor/alexander) has its own
    Artisan instance and they don't steal each other's work."""
    tags = [str(t).lower() for t in (task.get("tags") or [])]
    notes = (task.get("notes") or "").lower()
    base_match = (
        "agent:artisan" in tags
        or "tier:v4_flash" in tags
        or "dispatch: artisan" in notes
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
        or f"agent:{owner}:artisan" in tags
        or f"team:{owner}" in tags
        or f"for:{owner}" in tags
    )


def _count_steps(task: dict) -> int:
    """Count numbered steps + phases in the task instructions. Used to
    reject too-complex tasks that should go to Daedalus instead."""
    text = (task.get("instructions") or "") + "\n" + (task.get("objective") or "")
    return len(STEP_PATTERN.findall(text)) + len(PHASE_PATTERN.findall(text))


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
            if _matches_artisan(t, owner=owner):
                out.append(t)
                seen.add(tid)
    return out


def claim(task_id: str) -> bool:
    code, body = mcp_claim_task(operator_id="artisan", task_id=task_id)
    return code == 200 and bool(body.get("success") or body.get("claimed"))


def update(task_id: str, status: str, summary: str | None = None,
           failure: str | None = None, deliverable: str | None = None,
           notes: str | None = None) -> None:
    needs_hop = status in {"completed", "failed", "blocked"}
    try:
        if needs_hop:
            code1, body1 = mcp_update_task(
                task_id=task_id, status="active",
                notes="artisan_v4_flash: transitioning to terminal",
            )
            if code1 != 200 or not body1.get("success", True):
                _log(f"hop1-fail task={task_id} → dead_letter")
                mcp_update_task(task_id=task_id, status="dead_letter",
                                failure_reason=(failure or "artisan hop1 failed")[:500])
                return
        code2, body2 = mcp_update_task(
            task_id=task_id, status=status,
            result_summary=(summary or "")[:1500],
            failure_reason=(failure or None),
            deliverable_link=deliverable,
            notes=notes,
        )
        if code2 != 200 or not body2.get("success", True):
            _log(f"hop2-fail task={task_id} status={status} → dead_letter")
            mcp_update_task(task_id=task_id, status="dead_letter",
                            failure_reason=(failure or f"hop2 to {status} failed")[:500])
    except Exception as e:
        _log(f"update EXCEPTION task={task_id} → dead_letter ({e!r})")
        try:
            mcp_update_task(task_id=task_id, status="dead_letter",
                            failure_reason=f"artisan update exception: {e!r}"[:500])
        except Exception as e2:
            _log(f"dead_letter fallback ALSO FAILED task={task_id}: {e2!r}")


def _build_prompt(task: dict) -> str:
    tid = task.get("task_id")
    return f"""ROLE: You are Artisan, AMG factory's fast LLM executor backed by DeepSeek V4 Flash.

TASK ID: {tid}

OBJECTIVE: {task.get('objective','')}
CONTEXT: {task.get('context','')}
INSTRUCTIONS: {task.get('instructions','')}
ACCEPTANCE CRITERIA: {task.get('acceptance_criteria','')}

OUTPUT FORMAT — return ONLY a single JSON object with exactly these keys:
{{"ok": true|false, "artifact_path": str|null, "artifact_hash": str|null,
  "stdout_tail": str, "exit_code": 0|N, "reasoning": str}}

NO markdown fences. Output starts with `{{` ends with `}}`. Do not fabricate
file paths or hashes. Aletheia detects fake completions and flags them."""


def call_deepseek(api_key: str, prompt: str) -> tuple[dict, dict]:
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": (
                "You are Artisan. Output ONLY a single JSON object matching "
                "the schema. Be honest about ok/exit_code. Fake completions "
                "are detected by Aletheia."
            )},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        DEEPSEEK_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read())
    choices = resp.get("choices") or []
    if not choices:
        raise RuntimeError(f"empty choices: {resp}")
    msg = choices[0].get("message") or {}
    return resp, {"content": (msg.get("content") or "").strip()}


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


def estimate_cost_usd(prompt: str, max_out_tokens: int = 4096) -> float:
    # V4 Flash: rough estimate $0.07/M input, $0.28/M output (~25% of V4 Pro)
    in_tokens = len(prompt) / 4
    return (in_tokens * 0.07 + max_out_tokens * 0.28) / 1_000_000


def execute_one(task: dict, api_key: str, ks: KillSwitch | None,
                owner: str | None = None,
                chief_gate: "ChiefCostGate | None" = None) -> dict:
    tid = task.get("task_id")
    steps = _count_steps(task)
    if steps > MAX_STEPS:
        # Reject + requeue for Daedalus by appending an agent:daedalus marker
        # to notes (the daedalus poller will pick it up next pass).
        existing_notes = task.get("notes") or ""
        update(tid, "blocked",
               failure=f"artisan rejects: {steps} steps > {MAX_STEPS}; requeue agent:daedalus",
               notes=f"{existing_notes}\nREQUEUE_TAG: agent:daedalus reason=artisan-too-complex steps={steps}")
        _log(f"task={tid} REJECT steps={steps} → requeue daedalus")
        return {"ok": False, "exit_code": 100, "reasoning": f"too-many-steps={steps}"}
    prompt = _build_prompt(task)
    est = estimate_cost_usd(prompt)
    # Per-chief + fleet gate (if owner-scoped). Stops over-spend BEFORE the
    # per-vendor gate fires.
    if chief_gate is not None:
        cached = chief_gate.check_cache(prompt)
        if cached is not None:
            return cached if isinstance(cached, dict) else {"ok": True, "cached": True}
        if not chief_gate.allow_call(estimated_cost_usd=est):
            deny = chief_gate.deny_response()
            _log(f"task={tid} chief-gate DENIED owner={owner} {deny}")
            update(tid, "blocked",
                   failure=f"chief-gate cap hit owner={owner} chief_spend=${deny['chief_spend_usd']:.4f}/${deny['chief_cap_usd']:.2f} fleet=${deny['fleet_spend_usd']:.4f}/${deny['fleet_cap_usd']:.2f}")
            return {"ok": False, "exit_code": 429, "reasoning": "chief-cost-cap"}
    if ks is not None:
        cached = ks.check_cache(prompt)
        if cached is not None:
            return cached if isinstance(cached, dict) else {"ok": True, "cached": True}
        if not ks.allow_call(estimated_cost_usd=est):
            _log(f"task={tid} cost-cap hit (artisan $10/day) → block")
            update(tid, "blocked", failure="artisan daily $10 cap reached")
            return {"ok": False, "exit_code": 429, "reasoning": "cost cap"}
    t0 = time.time()
    try:
        resp, msg = call_deepseek(api_key, prompt)
    except Exception as e:
        _log(f"task={tid} DeepSeek call FAILED: {e!r}")
        update(tid, "failed", failure=f"deepseek call exception: {e!r}"[:500])
        return {"ok": False, "exit_code": 1, "reasoning": f"deepseek-call-exception {e!r}"}
    latency = time.time() - t0
    usage = resp.get("usage") or {}
    cost = (usage.get("prompt_tokens", 0) * 0.07 + usage.get("completion_tokens", 0) * 0.28) / 1_000_000
    if ks is not None:
        try:
            ks.record_call(prompt, cost, msg["content"])
        except Exception as e:
            _log(f"task={tid} cost record failed (non-fatal): {e!r}")
    if chief_gate is not None:
        try:
            chief_gate.record_call(prompt, cost, msg["content"])
        except Exception as e:
            _log(f"task={tid} chief-gate record failed (non-fatal): {e!r}")
    receipt = parse_receipt(msg["content"])
    if receipt is None:
        _log(f"task={tid} receipt UNPARSEABLE; raw={msg['content'][:200]!r}")
        update(tid, "failed",
               failure=f"artisan returned unstructured JSON; preview: {msg['content'][:300]}"[:500])
        return {"ok": False, "exit_code": 2, "reasoning": "unstructured-output"}
    artifact_path = receipt.get("artifact_path")
    summary = (
        f"artisan_v4_flash receipt: ok={receipt.get('ok')} exit_code={receipt.get('exit_code')} "
        f"artifact={artifact_path} hash={receipt.get('artifact_hash')} "
        f"latency={latency:.1f}s cost=${cost:.4f} | {receipt.get('reasoning','')[:300]}"
    )
    if receipt.get("ok"):
        update(tid, "completed", summary=summary,
               deliverable=artifact_path if artifact_path else None)
    else:
        update(tid, "failed",
               failure=(receipt.get("reasoning") or "ok=false")[:500])
    decision_tags = ["artisan-receipt", f"task:{tid}", "deepseek-v4-flash"]
    if owner:
        decision_tags.extend([f"owner:{owner}", f"chief:{owner}"])
    mcp_log_decision(
        text=f"ARTISAN executor receipt task={tid} ok={receipt.get('ok')} cost=${cost:.4f} owner={owner or 'legacy'}",
        rationale=summary,
        tags=decision_tags,
        project_source="artisan",
    )
    return receipt


def drain_once(owner: str | None = None) -> dict:
    api_key = _resolve_api_key()
    ks = KillSwitch(vendor="deepseek-v4-flash", daily_cap_usd=DAILY_CAP_USD,
                    scope="executor") if KillSwitch else None
    chief_gate = None
    if owner and ChiefCostGate is not None:
        try:
            chief_gate = ChiefCostGate(chief=owner, role="artisan",
                                       vendor="deepseek-v4-flash")
        except Exception as e:
            _log(f"chief-gate construct failed (non-fatal): {e!r}")
    pending = fetch_pending(owner=owner)
    out = {"scanned": len(pending), "claimed": 0, "ok": 0, "fail": 0, "skipped": 0, "rejected": 0,
           "owner": owner or "legacy"}
    for t in pending:
        tid = t.get("task_id")
        if not claim(tid):
            out["skipped"] += 1
            continue
        out["claimed"] += 1
        receipt = execute_one(t, api_key, ks, owner=owner, chief_gate=chief_gate)
        if receipt.get("exit_code") == 100:
            out["rejected"] += 1
        elif receipt.get("ok"):
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
        LOCK_FILE = HOME / ".openclaw" / "logs" / f"artisan_v4_flash_executor.{args.owner}.lock"
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_fp = LOCK_FILE.open("a")
    try:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"artisan_v4_flash_executor (owner={args.owner or 'legacy'}): another instance holds the lock", file=sys.stderr)
        return 1

    if args.task_id:
        api_key = _resolve_api_key()
        ks = KillSwitch(vendor="deepseek-v4-flash", daily_cap_usd=DAILY_CAP_USD,
                        scope="executor") if KillSwitch else None
        chief_gate = None
        if args.owner and ChiefCostGate is not None:
            try:
                chief_gate = ChiefCostGate(chief=args.owner, role="artisan",
                                           vendor="deepseek-v4-flash")
            except Exception as e:
                _log(f"chief-gate construct failed (non-fatal): {e!r}")
        code, body = mcp_get_task_queue(task_id=args.task_id)
        tasks = (body or {}).get("tasks") or []
        if not tasks:
            print(f"task {args.task_id} not found")
            return 1
        if not claim(args.task_id):
            print(f"could not claim {args.task_id}")
            return 1
        receipt = execute_one(tasks[0], api_key, ks, owner=args.owner, chief_gate=chief_gate)
        print(json.dumps(receipt, indent=2))
        return 0 if receipt.get("ok") else 1

    if args.once or not args.watch:
        result = drain_once(owner=args.owner)
        print(json.dumps(result, indent=2))
        return 0

    _log(f"artisan_v4_flash starting watch interval={args.interval}s owner={args.owner or 'legacy'}")
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
