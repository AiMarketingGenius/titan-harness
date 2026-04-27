#!/usr/bin/env python3
"""daedalus_v4_pro_executor.py — Daedalus poll-execute daemon backed by
DeepSeek V4 Pro (api.deepseek.com).

Polls MCP `op_task_queue` every 30s for tasks where ANY of the following
are true (no AND-ing):
  - tag `agent:daedalus`
  - tag `tier:v4_pro`
  - notes contains `DISPATCH: daedalus`

For each match: claim_task → call DeepSeek → validate structured JSON →
save artifact → mark completed/failed via locked→active→terminal hop.

Hercules dispatch 2026-04-26: forced structured JSON output. The model
must produce {ok, artifact_path, artifact_hash, stdout_tail, exit_code,
reasoning}. If the response can't be parsed as that shape, the task is
marked failed (NEVER saved as a fake completion — Aletheia would catch
it on the next pass anyway).

Cost gate: lib/cost_kill_switch.py at $20/day. Sqlite, NOT Redis. If cap
hit, task gets requeued to artisan (cheaper) automatically.

Run modes:
    daedalus_v4_pro_executor.py --once         # drain once, exit
    daedalus_v4_pro_executor.py --watch        # daemon, poll every --interval
    daedalus_v4_pro_executor.py --task-id CT-X # claim a specific task

Logs: ~/.openclaw/logs/daedalus_v4_pro_executor.{out,err}.log
launchd: com.amg.daedalus-v4-pro
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

try:
    from cost_kill_switch import KillSwitch  # noqa: E402
except Exception:
    KillSwitch = None  # cost gate optional; warns at runtime if missing

DEEPSEEK_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-v4-pro"
SSH_HOST = "amg-staging"
DAILY_CAP_USD = 20.0
LOCK_FILE = HOME / ".openclaw" / "logs" / "daedalus_v4_pro_executor.lock"
LOG_FILE = HOME / ".openclaw" / "logs" / "daedalus_v4_pro_executor.log"
ARTIFACTS_DIR = HOME / "titan-harness" / "reports" / "daedalus"

REQUIRED_RECEIPT_KEYS = {
    "ok", "artifact_path", "artifact_hash", "stdout_tail", "exit_code", "reasoning",
}


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with LOG_FILE.open("a") as f:
        f.write(f"[{ts}] {msg}\n")


def _resolve_api_key() -> str:
    """Pull DEEPSEEK_API_KEY from VPS /etc/amg/deepseek.env (matches the
    pattern in scripts/run_daedalus_audit.py:_resolve_api_key)."""
    out = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=8", SSH_HOST,
         "grep '^DEEPSEEK_API_KEY=' /etc/amg/deepseek.env | cut -d= -f2-"],
        capture_output=True, text=True, timeout=15,
    )
    if out.returncode != 0:
        raise RuntimeError(f"could not read DEEPSEEK_API_KEY from VPS: {out.stderr[:200]}")
    key = out.stdout.strip()
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY empty on VPS")
    return key


def _matches_daedalus(task: dict, owner: str | None = None) -> bool:
    """Match Daedalus tasks. If owner is set, ALSO require owner:<owner> tag
    or agent:<owner>:daedalus shorthand — used by the 3-EOM-mirror
    architecture so each Kimi orchestrator (hercules/nestor/alexander) has
    its OWN daedalus instance and they don't steal each other's work."""
    tags = [str(t).lower() for t in (task.get("tags") or [])]
    notes = (task.get("notes") or "").lower()
    base_match = (
        "agent:daedalus" in tags
        or "tier:v4_pro" in tags
        or "dispatch: daedalus" in notes
    )
    if not base_match:
        return False
    if owner is None:
        # Legacy mode — catch-all (used by the original com.amg.daedalus-v4-pro
        # daemon for Hercules + any unowned task).
        return True
    owner = owner.lower()
    # Owner-scoped match: require explicit owner tag.
    return (
        f"owner:{owner}" in tags
        or f"agent:{owner}:daedalus" in tags
        or f"team:{owner}" in tags
        or f"for:{owner}" in tags
    )


def fetch_pending(owner: str | None = None) -> list[dict]:
    """Pull approved+pending tasks tagged for Daedalus (optionally scoped to
    an owner). Server-side tag filtering isn't supported, so we client-filter
    the top 50."""
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
            if _matches_daedalus(t, owner=owner):
                out.append(t)
                seen.add(tid)
    return out


def claim(task_id: str) -> bool:
    code, body = mcp_claim_task(operator_id="daedalus", task_id=task_id)
    return code == 200 and bool(body.get("success") or body.get("claimed"))


def update(task_id: str, status: str, summary: str | None = None,
           failure: str | None = None, deliverable: str | None = None) -> None:
    """FSM hop locked→active→terminal with same fall-through-to-dead_letter
    safety as the patched mercury_executor.py (no lock leaks)."""
    needs_hop = status in {"completed", "failed", "blocked"}
    try:
        if needs_hop:
            code1, body1 = mcp_update_task(
                task_id=task_id, status="active",
                notes="daedalus_v4_pro: transitioning to terminal",
            )
            if code1 != 200 or not body1.get("success", True):
                _log(f"hop1-fail task={task_id} → dead_letter")
                mcp_update_task(task_id=task_id, status="dead_letter",
                                failure_reason=(failure or "daedalus hop1 failed")[:500])
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
                            failure_reason=f"daedalus update exception: {e!r}"[:500])
        except Exception as e2:
            _log(f"dead_letter fallback ALSO FAILED task={task_id}: {e2!r}")


def _build_prompt(task: dict) -> str:
    tid = task.get("task_id")
    objective = task.get("objective") or ""
    instructions = task.get("instructions") or ""
    accept = task.get("acceptance_criteria") or ""
    context = task.get("context") or ""
    return f"""ROLE: You are Daedalus, AMG factory's premium code+architecture executor backed by DeepSeek V4 Pro.

TASK ID: {tid}

OBJECTIVE:
{objective}

CONTEXT:
{context}

INSTRUCTIONS:
{instructions}

ACCEPTANCE CRITERIA:
{accept}

OUTPUT FORMAT — return ONLY a single JSON object with exactly these keys, no markdown fences, no preamble:

{{
  "ok": true|false,
  "artifact_path": "/absolute/path/to/file/you/wrote OR null if no file",
  "artifact_hash": "sha256-hex of artifact content OR null",
  "stdout_tail": "last 600 chars of any stdout you'd return to caller",
  "exit_code": 0|N,
  "reasoning": "1-3 sentences on what you did and why ok=true|false"
}}

RULES:
- Do NOT include a markdown fence around the JSON. Output STARTS with `{{` and ENDS with `}}`.
- If you cannot complete the task, set ok=false + exit_code=non-zero + reasoning explaining what's missing.
- If the task requires writing a file, write it via your own tool and report the absolute path + sha256.
- If the task requires reading + analyzing, embed your finding in `stdout_tail` and set artifact_path=null.
- DO NOT fabricate file paths or hashes. Either you wrote a real file or artifact_path=null.
"""


def call_deepseek(api_key: str, prompt: str) -> tuple[dict, dict]:
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": (
                "You are Daedalus. Output ONLY a single JSON object matching "
                "the exact schema specified in the user prompt. No prose before "
                "or after. No markdown fences. Be honest about ok/exit_code: "
                "fake completions are detected by Aletheia and will be flagged."
            )},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 8192,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        DEEPSEEK_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.loads(r.read())
    choices = resp.get("choices") or []
    if not choices:
        raise RuntimeError(f"empty choices: {resp}")
    msg = choices[0].get("message") or {}
    content = (msg.get("content") or "").strip()
    return resp, {"content": content, "reasoning": msg.get("reasoning_content") or ""}


def parse_receipt(content: str) -> dict | None:
    """Strict shape validation. Returns dict if valid, None if garbage."""
    # Strip any accidental markdown fences
    s = content.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines)
    try:
        receipt = json.loads(s)
    except Exception:
        return None
    if not isinstance(receipt, dict):
        return None
    missing = REQUIRED_RECEIPT_KEYS - set(receipt.keys())
    if missing:
        return None
    if not isinstance(receipt.get("ok"), bool):
        return None
    return receipt


def estimate_cost_usd(prompt: str, max_out_tokens: int = 8192) -> float:
    in_tokens = len(prompt) / 4  # rough
    return (in_tokens * 0.27 + max_out_tokens * 1.10) / 1_000_000


def execute_one(task: dict, api_key: str, ks: KillSwitch | None) -> dict:
    tid = task.get("task_id")
    prompt = _build_prompt(task)
    est = estimate_cost_usd(prompt)
    cached = None
    if ks is not None:
        cached = ks.check_cache(prompt)
        if cached is not None:
            _log(f"task={tid} cache-hit → returning cached receipt")
            return cached if isinstance(cached, dict) else {"ok": True, "cached": True}
        if not ks.allow_call(estimated_cost_usd=est):
            _log(f"task={tid} cost-cap hit (vendor=deepseek-v4-pro est=${est:.3f}) → REQUEUE for artisan")
            update(tid, "blocked",
                   failure="daedalus daily $20 cap reached; requeued tier:v4_flash for Artisan")
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
    cost = (usage.get("prompt_tokens", 0) * 0.27 + usage.get("completion_tokens", 0) * 1.10) / 1_000_000
    if ks is not None:
        try:
            ks.record_call(prompt, cost, msg["content"])
        except Exception as e:
            _log(f"task={tid} cost record failed (non-fatal): {e!r}")
    receipt = parse_receipt(msg["content"])
    if receipt is None:
        _log(f"task={tid} receipt UNPARSEABLE; raw_preview={msg['content'][:200]!r}")
        update(tid, "failed",
               failure=f"daedalus returned unstructured/invalid JSON; preview: {msg['content'][:300]}"[:500])
        return {"ok": False, "exit_code": 2, "reasoning": "unstructured-output"}
    artifact_path = receipt.get("artifact_path")
    summary = (
        f"daedalus_v4_pro receipt: ok={receipt.get('ok')} exit_code={receipt.get('exit_code')} "
        f"artifact={artifact_path} hash={receipt.get('artifact_hash')} "
        f"latency={latency:.1f}s cost=${cost:.4f} | {receipt.get('reasoning','')[:300]}"
    )
    if receipt.get("ok"):
        update(tid, "completed", summary=summary,
               deliverable=artifact_path if artifact_path else None)
    else:
        update(tid, "failed",
               failure=(receipt.get("reasoning") or "ok=false")[:500])
    mcp_log_decision(
        text=f"DAEDALUS executor receipt task={tid} ok={receipt.get('ok')} cost=${cost:.4f}",
        rationale=summary,
        tags=["daedalus-receipt", f"task:{tid}", "deepseek-v4-pro"],
        project_source="daedalus",
    )
    return receipt


def drain_once(owner: str | None = None) -> dict:
    api_key = _resolve_api_key()
    vendor = f"deepseek-v4-pro-{owner}" if owner else "deepseek-v4-pro"
    ks = KillSwitch(vendor=vendor, daily_cap_usd=DAILY_CAP_USD,
                    scope="executor") if KillSwitch else None
    pending = fetch_pending(owner=owner)
    out = {"owner": owner or "all", "scanned": len(pending), "claimed": 0, "ok": 0, "fail": 0, "skipped": 0}
    for t in pending:
        tid = t.get("task_id")
        if not claim(tid):
            out["skipped"] += 1
            continue
        out["claimed"] += 1
        receipt = execute_one(t, api_key, ks)
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
                   help="3-EOM-mirror scope. One of: hercules, nestor, alexander. "
                        "If unset, daemon runs in legacy catch-all mode (claims any agent:daedalus task).")
    args = p.parse_args()

    # Per-owner lock file so 3 owner-scoped daedalus daemons can coexist
    # without fighting for the same lock.
    global LOCK_FILE
    if args.owner:
        LOCK_FILE = HOME / ".openclaw" / "logs" / f"daedalus_v4_pro_executor.{args.owner}.lock"

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_fp = LOCK_FILE.open("a")
    try:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"daedalus_v4_pro_executor (owner={args.owner or 'legacy'}): another instance holds the lock", file=sys.stderr)
        return 1

    if args.task_id:
        # one-shot single-task
        api_key = _resolve_api_key()
        ks = KillSwitch(vendor="deepseek-v4-pro", daily_cap_usd=DAILY_CAP_USD,
                        scope="executor") if KillSwitch else None
        code, body = mcp_get_task_queue(task_id=args.task_id)
        tasks = (body or {}).get("tasks") or []
        if not tasks:
            print(f"task {args.task_id} not found")
            return 1
        if not claim(args.task_id):
            print(f"could not claim {args.task_id}")
            return 1
        receipt = execute_one(tasks[0], api_key, ks)
        print(json.dumps(receipt, indent=2))
        return 0 if receipt.get("ok") else 1

    if args.once or not args.watch:
        result = drain_once(owner=args.owner)
        print(json.dumps(result, indent=2))
        return 0

    _log(f"daedalus_v4_pro starting watch interval={args.interval}s owner={args.owner or 'legacy'}")
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
