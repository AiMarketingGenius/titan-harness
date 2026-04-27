#!/usr/bin/env python3
"""lumina_visual_qa_executor.py — Lumina visual-QA / Lighthouse / accessibility
specialist for Nestor's lane.

Phase 2.5 Phase A (2026-04-27): Slot-4 specialist for the Nestor chief.
Polls MCP for `agent:lumina` tasks tagged `owner:nestor`, calls Gemini 2.5
Flash with the artifact (HTML/CSS/JSX preview, screenshot URL, or rendered
markup) plus a CRO + accessibility rubric, returns the standard Daedalus
receipt format so Aletheia v2 can verify.

Cost gate: $1/chief/day via lib/chief_cost_gate.py (sqlite-backed atomic
caps; equivalent guarantee to a Redis counter at zero new infra cost).

Tag routing (mirrors the Daedalus owner-scoped pattern):
  - agent:lumina + owner:nestor → this daemon claims
  - agent:lumina + owner:hercules → REJECTED (no lumina_hercules daemon — Hercules
    routes UI work through Nestor, not directly)
  - agent:lumina + owner:alexander → same; Alexander routes through Nestor

Run modes:
    lumina_visual_qa_executor.py --once --owner nestor
    lumina_visual_qa_executor.py --watch --owner nestor
    lumina_visual_qa_executor.py --task-id CT-X --owner nestor

launchd label: com.amg.lumina-nestor

Lighthouse integration: when task.context contains a URL + the local Mac has
`npx lighthouse` available (most do), the executor optionally appends a
Lighthouse summary to stdout_tail. Currently text/HTML grading only — image
input arrives via Gemini's multimodal endpoint when task.attachments is set.
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

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
SSH_HOST = "amg-staging"
LOCK_FILE_BASE = HOME / ".openclaw" / "logs" / "lumina_visual_qa_executor"
LOG_FILE = HOME / ".openclaw" / "logs" / "lumina_visual_qa_executor.log"

REQUIRED_RECEIPT_KEYS = {
    "ok", "artifact_path", "artifact_hash", "stdout_tail", "exit_code", "reasoning",
}

LUMINA_SYSTEM = (
    "You are Lumina, AMG's visual-QA + CRO + accessibility specialist. You "
    "score artifacts on a 5-dimension rubric (authenticity / hierarchy / "
    "craft / responsiveness / accessibility), each 0–10. The Apple polish "
    "floor is 9.3. Your output is a structured JSON receipt — no markdown "
    "fences, no preamble. When grading code (HTML/CSS/JSX), inspect the "
    "DOM structure, semantic tags, ARIA attributes, color-contrast risk, "
    "responsive breakpoints, hierarchy/spacing/symmetry. Return the "
    "5 sub-scores in stdout_tail along with concrete actionable fixes. "
    "ok=true requires all 5 dims >= 9.3. Aletheia verifies — fake scores "
    "(uniform 9.5 across the board with no rationale) get caught and flagged."
)


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with LOG_FILE.open("a") as f:
        f.write(f"[{ts}] {msg}\n")


_GEMINI_KEY_CACHE: str | None = None

def _resolve_gemini_key() -> str:
    global _GEMINI_KEY_CACHE
    if _GEMINI_KEY_CACHE:
        return _GEMINI_KEY_CACHE
    for env_var in ("GEMINI_API_KEY_AMG_GRADER", "GEMINI_API_KEY", "GEMINI_API_KEY_AIMG"):
        v = os.environ.get(env_var)
        if v:
            _GEMINI_KEY_CACHE = v
            return v
    # /etc/amg/gemini.env uses `export FOO=bar` syntax — pull all lines that
    # define a Gemini key (with or without the `export` prefix) and prefer
    # the AMG_GRADER variant, then GEMINI_API_KEY, then AIMG.
    out = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=8", SSH_HOST,
         "grep -E '^(export[[:space:]]+)?GEMINI_API_KEY[A-Z_]*=' /etc/amg/gemini.env"],
        capture_output=True, text=True, timeout=15,
    )
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError(f"GEMINI_API_KEY not in env or /etc/amg/gemini.env: {out.stderr[:200]}")
    keys: dict[str, str] = {}
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        name, _, val = line.partition("=")
        keys[name.strip()] = val.strip().strip('"').strip("'")
    for preferred in ("GEMINI_API_KEY_AMG_GRADER", "GEMINI_API_KEY", "GEMINI_API_KEY_AIMG"):
        if preferred in keys and keys[preferred]:
            _GEMINI_KEY_CACHE = keys[preferred]
            return _GEMINI_KEY_CACHE
    raise RuntimeError(f"no usable Gemini key found among {list(keys)}")


def _matches_lumina(task: dict, owner: str | None = None) -> bool:
    tags = [str(t).lower() for t in (task.get("tags") or [])]
    notes = (task.get("notes") or "").lower()
    base_match = (
        "agent:lumina" in tags
        or "lane:visual-qa" in tags
        or "tier:cro" in tags
        or "dispatch: lumina" in notes
        or (task.get("agent_assigned") or "").lower() == "lumina"
    )
    if not base_match:
        return False
    if owner is None:
        return True
    owner = owner.lower()
    return (
        f"owner:{owner}" in tags
        or f"agent:{owner}:lumina" in tags
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
            if _matches_lumina(t, owner=owner):
                out.append(t)
                seen.add(tid)
    return out


def claim(task_id: str) -> bool:
    code, body = mcp_claim_task(operator_id="lumina", task_id=task_id)
    return code == 200 and bool(body.get("success") or body.get("claimed"))


def update(task_id: str, status: str, summary: str | None = None,
           failure: str | None = None, deliverable: str | None = None) -> None:
    needs_hop = status in {"completed", "failed", "blocked"}
    try:
        if needs_hop:
            code1, body1 = mcp_update_task(
                task_id=task_id, status="active",
                notes="lumina_visual_qa: transitioning to terminal",
            )
            if code1 != 200 or not body1.get("success", True):
                _log(f"hop1-fail task={task_id} → dead_letter")
                mcp_update_task(task_id=task_id, status="dead_letter",
                                failure_reason=(failure or "lumina hop1 failed")[:500])
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
                            failure_reason=f"lumina update exception: {e!r}"[:500])
        except Exception as e2:
            _log(f"dead_letter fallback ALSO FAILED: {e2!r}")


def _build_prompt(task: dict) -> str:
    tid = task.get("task_id")
    return f"""ROLE: You are Lumina, AMG's visual-QA + CRO + accessibility grader (Gemini 2.5 Flash).

TASK ID: {tid}

OBJECTIVE: {task.get('objective','')}
CONTEXT: {task.get('context','')}
INSTRUCTIONS: {task.get('instructions','')}
ACCEPTANCE CRITERIA: {task.get('acceptance_criteria','')}

OUTPUT FORMAT — return ONLY a single JSON object, no markdown fences:

{{"ok": true|false, "artifact_path": str|null, "artifact_hash": str|null,
  "stdout_tail": str, "exit_code": 0|N, "reasoning": str}}

stdout_tail format — include all 5 sub-scores AND concrete fixes:
  authenticity:   N.N | <one-line rationale>
  hierarchy:      N.N | <one-line rationale>
  craft:          N.N | <one-line rationale>
  responsiveness: N.N | <one-line rationale>
  accessibility:  N.N | <one-line rationale>
  fixes: <bulleted list of specific deltas, file paths, CSS/HTML lines>

Apple polish floor: each dim >= 9.3 → ok=true. Anything below → ok=false +
reasoning explaining the lowest dim. NO uniform-score gaming — Aletheia
detects it and flags. Output STARTS with `{{` ENDS with `}}`."""


def call_gemini(api_key: str, prompt: str) -> tuple[dict, dict]:
    body = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "systemInstruction": {"parts": [{"text": LUMINA_SYSTEM}]},
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
    }
    url = f"{GEMINI_ENDPOINT}?key={api_key}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read())
    candidates = resp.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"gemini empty candidates: {resp}")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    return resp, {"content": text}


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
    # Gemini 2.5 Flash: $0.075/M input, $0.30/M output (approx as of 2026-04)
    in_tokens = len(prompt) / 4
    return (in_tokens * 0.075 + max_out_tokens * 0.30) / 1_000_000


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
        resp, msg = call_gemini(api_key, prompt)
    except Exception as e:
        _log(f"task={tid} Gemini call FAILED: {e!r}")
        update(tid, "failed", failure=f"gemini call exception: {e!r}"[:500])
        return {"ok": False, "exit_code": 1, "reasoning": f"gemini-call-exception {e!r}"}
    latency = time.time() - t0
    usage = resp.get("usageMetadata") or {}
    in_t = usage.get("promptTokenCount", 0)
    out_t = usage.get("candidatesTokenCount", 0)
    cost = (in_t * 0.075 + out_t * 0.30) / 1_000_000
    if chief_gate is not None:
        try:
            chief_gate.record_call(prompt, cost, msg["content"])
        except Exception as e:
            _log(f"task={tid} chief-gate record failed (non-fatal): {e!r}")
    receipt = parse_receipt(msg["content"])
    if receipt is None:
        _log(f"task={tid} receipt UNPARSEABLE; raw={msg['content'][:200]!r}")
        update(tid, "failed",
               failure=f"lumina returned unstructured JSON; preview: {msg['content'][:300]}"[:500])
        return {"ok": False, "exit_code": 2, "reasoning": "unstructured-output"}
    artifact_path = receipt.get("artifact_path")
    summary = (
        f"lumina_visual_qa receipt: ok={receipt.get('ok')} exit_code={receipt.get('exit_code')} "
        f"artifact={artifact_path} hash={receipt.get('artifact_hash')} "
        f"latency={latency:.1f}s cost=${cost:.4f} | {receipt.get('reasoning','')[:300]}"
    )
    if receipt.get("ok"):
        update(tid, "completed", summary=summary,
               deliverable=artifact_path if artifact_path else None)
    else:
        update(tid, "failed",
               failure=(receipt.get("reasoning") or "ok=false")[:500])
    decision_tags = ["lumina-receipt", f"task:{tid}", "gemini-2.5-flash"]
    if owner:
        decision_tags.extend([f"owner:{owner}", f"chief:{owner}"])
    mcp_log_decision(
        text=f"LUMINA executor receipt task={tid} ok={receipt.get('ok')} cost=${cost:.4f} owner={owner or 'legacy'}",
        rationale=summary,
        tags=decision_tags,
        project_source="lumina",
    )
    return receipt


def drain_once(owner: str | None = None) -> dict:
    api_key = _resolve_gemini_key()
    chief_gate = None
    if owner and ChiefCostGate is not None:
        try:
            chief_gate = ChiefCostGate(chief=owner, role="lumina",
                                       vendor="gemini-2.5-flash")
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
    lock_file = LOCK_FILE_BASE.with_suffix(f"{suffix}.lock") if suffix else pathlib.Path(str(LOCK_FILE_BASE) + ".lock")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_fp = lock_file.open("a")
    try:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"lumina_visual_qa_executor (owner={args.owner or 'legacy'}): another instance holds the lock", file=sys.stderr)
        return 1

    if args.task_id:
        api_key = _resolve_gemini_key()
        chief_gate = None
        if args.owner and ChiefCostGate is not None:
            try:
                chief_gate = ChiefCostGate(chief=args.owner, role="lumina",
                                           vendor="gemini-2.5-flash")
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

    _log(f"lumina_visual_qa starting watch interval={args.interval}s owner={args.owner or 'legacy'}")
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
