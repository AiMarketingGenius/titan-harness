#!/usr/bin/env python3
"""echo_brand_voice_executor.py — Echo brand-voice grader for Alexander's lane.

Phase 2.5 Phase A (2026-04-27): Slot-4 specialist for the Alexander chief.
Polls MCP for `agent:echo` tasks tagged `owner:alexander`, calls DeepSeek V3
with a 5-dimension brand-voice rubric, returns the standard receipt format
so Aletheia v2 can verify.

DeepSeek V3 (not V4) keeps the API surface consistent with Daedalus (V4 Pro)
+ Artisan (V4 Flash) — same vendor, different tier — without expanding the
factory's vendor inventory.

Cost gate: $1/chief/day via lib/chief_cost_gate.py.

Tag routing:
  - agent:echo + owner:alexander → this daemon claims
  - agent:echo + owner:nestor or owner:hercules → REJECTED (no sibling daemon
    for those chiefs; they route brand work through Alexander)

Run modes:
    echo_brand_voice_executor.py --once --owner alexander
    echo_brand_voice_executor.py --watch --owner alexander
    echo_brand_voice_executor.py --task-id CT-X --owner alexander

launchd label: com.amg.echo-alexander
"""
from __future__ import annotations

import argparse
import fcntl
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
    from chief_cost_gate import ChiefCostGate  # noqa: E402
except Exception:
    ChiefCostGate = None

DEEPSEEK_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
# DeepSeek V3 model name. The api.deepseek.com chat endpoint accepts the
# official model alias "deepseek-chat" which routes to the latest V3-class
# checkpoint (per DeepSeek's documented model-routing as of 2026-04). The
# raw "deepseek-v3" string returns HTTP 400 ("model_not_found"); use the
# alias instead, with env override available for future model switches.
MODEL = os.environ.get("ECHO_MODEL", "deepseek-chat")
SSH_HOST = "amg-staging"
LOG_FILE = HOME / ".openclaw" / "logs" / "echo_brand_voice_executor.log"

REQUIRED_RECEIPT_KEYS = {
    "ok", "artifact_path", "artifact_hash", "stdout_tail", "exit_code", "reasoning",
}

ECHO_SYSTEM = (
    "You are Echo, AMG's brand-voice grader. You score copy on a 5-dim "
    "rubric (voice-fit / clarity / conversion / authenticity / scannability), "
    "each 0–10. Floor for ok=true is 9.3 across all 5. AMG voice = sentence "
    "case with periods, never Title-Case-Every-Word, confident not cute, "
    "concrete not hand-wavy. Output ONLY a single JSON object — no markdown "
    "fences, no preamble. stdout_tail must include all 5 sub-scores plus "
    "concrete rewrites (verbatim suggested copy) for any dim < 9.3. "
    "Aletheia verifies — no uniform-9.5 sandbagging."
)


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
    for env_var in ("DEEPSEEK_API_KEY",):
        v = os.environ.get(env_var)
        if v:
            _API_KEY_CACHE = v
            return v
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


def _matches_echo(task: dict, owner: str | None = None) -> bool:
    tags = [str(t).lower() for t in (task.get("tags") or [])]
    notes = (task.get("notes") or "").lower()
    base_match = (
        "agent:echo" in tags
        or "lane:brand-voice" in tags
        or "tier:grader" in tags
        or "dispatch: echo" in notes
        or (task.get("agent_assigned") or "").lower() == "echo"
    )
    if not base_match:
        return False
    if owner is None:
        return True
    owner = owner.lower()
    return (
        f"owner:{owner}" in tags
        or f"agent:{owner}:echo" in tags
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
            if _matches_echo(t, owner=owner):
                out.append(t)
                seen.add(tid)
    return out


def claim(task_id: str) -> bool:
    code, body = mcp_claim_task(operator_id="echo", task_id=task_id)
    return code == 200 and bool(body.get("success") or body.get("claimed"))


def update(task_id: str, status: str, summary: str | None = None,
           failure: str | None = None, deliverable: str | None = None) -> None:
    needs_hop = status in {"completed", "failed", "blocked"}
    try:
        if needs_hop:
            code1, body1 = mcp_update_task(
                task_id=task_id, status="active",
                notes="echo_brand_voice: transitioning to terminal",
            )
            if code1 != 200 or not body1.get("success", True):
                _log(f"hop1-fail task={task_id} → dead_letter")
                mcp_update_task(task_id=task_id, status="dead_letter",
                                failure_reason=(failure or "echo hop1 failed")[:500])
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
                            failure_reason=f"echo update exception: {e!r}"[:500])
        except Exception as e2:
            _log(f"dead_letter fallback ALSO FAILED: {e2!r}")


def _build_prompt(task: dict) -> str:
    tid = task.get("task_id")
    return f"""ROLE: You are Echo, AMG's brand-voice grader (DeepSeek V3).

TASK ID: {tid}

OBJECTIVE: {task.get('objective','')}
CONTEXT: {task.get('context','')}
INSTRUCTIONS: {task.get('instructions','')}
ACCEPTANCE CRITERIA: {task.get('acceptance_criteria','')}

OUTPUT FORMAT — return ONLY a single JSON object, no markdown fences:

{{"ok": true|false, "artifact_path": str|null, "artifact_hash": str|null,
  "stdout_tail": str, "exit_code": 0|N, "reasoning": str}}

stdout_tail format — include 5 sub-scores + rewrites:
  voice-fit:      N.N | <one-line rationale>
  clarity:        N.N | <one-line rationale>
  conversion:     N.N | <one-line rationale>
  authenticity:   N.N | <one-line rationale>
  scannability:   N.N | <one-line rationale>
  rewrites: <verbatim suggested copy for any dim < 9.3>

ok=true requires all 5 dims >= 9.3. AMG voice = sentence case + periods,
confident, concrete. Never Title-Case-Every-Word. Output STARTS with `{{`,
ENDS with `}}`."""


def call_deepseek(api_key: str, prompt: str) -> tuple[dict, dict]:
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": ECHO_SYSTEM},
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
        raise RuntimeError(f"deepseek empty choices: {resp}")
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
    # DeepSeek V3 pricing (rough): $0.14/M input, $0.28/M output
    in_tokens = len(prompt) / 4
    return (in_tokens * 0.14 + max_out_tokens * 0.28) / 1_000_000


def execute_one(task: dict, api_key: str, owner: str | None = None,
                chief_gate: "ChiefCostGate | None" = None) -> dict:
    tid = task.get("task_id")
    prompt = _build_prompt(task)
    est = estimate_cost_usd(prompt)
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
    t0 = time.time()
    try:
        resp, msg = call_deepseek(api_key, prompt)
    except Exception as e:
        _log(f"task={tid} DeepSeek V3 call FAILED: {e!r}")
        update(tid, "failed", failure=f"deepseek call exception: {e!r}"[:500])
        return {"ok": False, "exit_code": 1, "reasoning": f"deepseek-call-exception {e!r}"}
    latency = time.time() - t0
    usage = resp.get("usage") or {}
    cost = (usage.get("prompt_tokens", 0) * 0.14 + usage.get("completion_tokens", 0) * 0.28) / 1_000_000
    if chief_gate is not None:
        try:
            chief_gate.record_call(prompt, cost, msg["content"])
        except Exception as e:
            _log(f"task={tid} chief-gate record failed (non-fatal): {e!r}")
    receipt = parse_receipt(msg["content"])
    if receipt is None:
        _log(f"task={tid} receipt UNPARSEABLE; raw={msg['content'][:200]!r}")
        update(tid, "failed",
               failure=f"echo returned unstructured JSON; preview: {msg['content'][:300]}"[:500])
        return {"ok": False, "exit_code": 2, "reasoning": "unstructured-output"}
    artifact_path = receipt.get("artifact_path")
    summary = (
        f"echo_brand_voice receipt: ok={receipt.get('ok')} exit_code={receipt.get('exit_code')} "
        f"artifact={artifact_path} hash={receipt.get('artifact_hash')} "
        f"latency={latency:.1f}s cost=${cost:.4f} | {receipt.get('reasoning','')[:300]}"
    )
    if receipt.get("ok"):
        update(tid, "completed", summary=summary,
               deliverable=artifact_path if artifact_path else None)
    else:
        update(tid, "failed",
               failure=(receipt.get("reasoning") or "ok=false")[:500])
    decision_tags = ["echo-receipt", f"task:{tid}", f"model:{MODEL}"]
    if owner:
        decision_tags.extend([f"owner:{owner}", f"chief:{owner}"])
    mcp_log_decision(
        text=f"ECHO executor receipt task={tid} ok={receipt.get('ok')} cost=${cost:.4f} owner={owner or 'legacy'}",
        rationale=summary,
        tags=decision_tags,
        project_source="echo",
    )
    return receipt


def drain_once(owner: str | None = None) -> dict:
    api_key = _resolve_api_key()
    chief_gate = None
    if owner and ChiefCostGate is not None:
        try:
            chief_gate = ChiefCostGate(chief=owner, role="echo",
                                       vendor=MODEL)
        except Exception as e:
            _log(f"chief-gate construct failed (non-fatal): {e!r}")
    pending = fetch_pending(owner=owner)
    out = {"scanned": len(pending), "claimed": 0, "ok": 0, "fail": 0, "skipped": 0,
           "owner": owner or "legacy"}
    for t in pending:
        tid = t.get("task_id")
        if not claim(tid):
            out["skipped"] += 1
            continue
        out["claimed"] += 1
        receipt = execute_one(t, api_key, owner=owner, chief_gate=chief_gate)
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

    suffix = f".{args.owner}" if args.owner else ""
    lock_file = HOME / ".openclaw" / "logs" / f"echo_brand_voice_executor{suffix}.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_fp = lock_file.open("a")
    try:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"echo_brand_voice_executor (owner={args.owner or 'legacy'}): another instance holds the lock", file=sys.stderr)
        return 1

    if args.task_id:
        api_key = _resolve_api_key()
        chief_gate = None
        if args.owner and ChiefCostGate is not None:
            try:
                chief_gate = ChiefCostGate(chief=args.owner, role="echo",
                                           vendor=MODEL)
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
        receipt = execute_one(tasks[0], api_key, owner=args.owner, chief_gate=chief_gate)
        print(json.dumps(receipt, indent=2))
        return 0 if receipt.get("ok") else 1

    if args.once or not args.watch:
        result = drain_once(owner=args.owner)
        print(json.dumps(result, indent=2))
        return 0

    _log(f"echo_brand_voice starting watch interval={args.interval}s owner={args.owner or 'legacy'}")
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
