#!/usr/bin/env python3
"""kimi_agent_executor.py — generic Kimi K2.6 (api.moonshot.ai) executor for
Nestor, Alexander, and any other Kimi-stack persona Hercules wants to dispatch
to from its Kimi tab.

Same poll-claim-execute-receipt pattern as scripts/daedalus_v4_pro_executor.py
but routes through https://api.moonshot.ai/v1/chat/completions with the
kimi-k2.6 model.

Run as one launchd unit per agent — `--agent nestor` for product/UX/mockups,
`--agent alexander` for brand/copy/voice. Each instance polls MCP for tasks
tagged `agent:<name>`, claims atomically, calls Kimi, validates structured
JSON receipt, and writes the receipt back to the task row + a separate
log_decision so Aletheia can verify.

Per-agent personas + system prompts live in AGENT_PROFILES below. Add new
Kimi agents (e.g. a future copy-stylist or a brand-persona tester) by
appending to that dict + dropping a launchd plist.

Cost gate: $5/day per agent via lib/cost_kill_switch.py (sqlite, no Redis).
Model is cheap (~$0.001/task at typical sizes) so $5/day = ~5000 tasks.

Lock-leak guard: locked → active → terminal FSM hop with dead_letter
fallback (mirrors the patched mercury_executor.py:349-396 pattern). Never
leaves a task stuck.

Run modes:
    kimi_agent_executor.py --agent nestor --once
    kimi_agent_executor.py --agent alexander --watch
    kimi_agent_executor.py --agent nestor --task-id CT-MMDD-NN
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
    from cost_kill_switch import KillSwitch  # noqa: E402
except Exception:
    KillSwitch = None

KIMI_ENDPOINT = "https://api.moonshot.ai/v1/chat/completions"
MODEL = "kimi-k2.6"
SSH_HOST = "amg-staging"
DAILY_CAP_USD_PER_AGENT = 5.0

REQUIRED_RECEIPT_KEYS = {
    "ok", "artifact_path", "artifact_hash", "stdout_tail", "exit_code", "reasoning",
}

AGENT_PROFILES = {
    "nestor": {
        "label": "Nestor",
        "role": "product / UX / mockups",
        "system": (
            "You are Nestor, AMG's product + UX + mockup specialist. Your output "
            "must hit the Apple polish floor (Lumina score 9.3+). When asked to "
            "design or audit a mockup, return concrete file_path + sha256 + "
            "exact CSS/HTML/JSX deltas in stdout_tail. Never hand-wave — every "
            "claim is verified by Aletheia. Reject tasks that need brand voice "
            "(those go to Alexander) or code refactor (those go to Daedalus)."
        ),
    },
    "alexander": {
        "label": "Alexander",
        "role": "brand / copy / voice",
        "system": (
            "You are Alexander, AMG's brand + copy + voice specialist. Your "
            "output must match the AMG brand voice: confident, sentence-case, "
            "punctuated, never Title-Case-Every-Word. Reject UI/UX tasks (those "
            "go to Nestor) or code/architecture audits (those go to Daedalus). "
            "When writing copy, return the verbatim text in stdout_tail + a "
            "brief rationale in reasoning. Aletheia verifies all claims."
        ),
    },
    "athena": {
        "label": "Athena",
        "role": "research / strategy / competitive intel",
        "system": (
            "You are Athena, AMG's research + strategy + competitive-intel "
            "specialist (Phase 2.7 of Hercules's MASTER BUILD ORDER 2026-04-26). "
            "Your job: produce structured strategic reports. When asked for "
            "competitive intel, return a side-by-side table comparing AMG vs "
            "competitors with concrete metrics. When asked for market research, "
            "return a 3-section report (a) findings, (b) implications, (c) "
            "recommended actions. Cite sources when you reference specifics. "
            "Reject code-implementation tasks (those go to Daedalus / Hephaestus) "
            "or design tasks (Nestor) or copy tasks (Alexander). Aletheia "
            "verifies every claim — do not fabricate stats or sources."
        ),
    },
}


def _agent_state(agent: str) -> dict:
    return {
        "log_file": HOME / ".openclaw" / "logs" / f"{agent}_kimi_executor.log",
        "lock_file": HOME / ".openclaw" / "logs" / f"{agent}_kimi_executor.lock",
    }


def _log(agent: str, msg: str) -> None:
    state = _agent_state(agent)
    state["log_file"].parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with state["log_file"].open("a") as f:
        f.write(f"[{ts}] {msg}\n")


def _resolve_kimi_key() -> str:
    """Pull the Kimi/Moonshot API key. Order: env var → /etc/amg/moonshot.env
    on staging VPS via SSH. Same pattern as daedalus's deepseek key resolver."""
    for env_var in ("MOONSHOT_API_KEY", "KIMI_API_KEY"):
        v = os.environ.get(env_var)
        if v:
            return v
    out = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=8", SSH_HOST,
         "grep -E '^(MOONSHOT_API_KEY|KIMI_API_KEY)=' /etc/amg/moonshot.env 2>/dev/null | head -1 | cut -d= -f2-"],
        capture_output=True, text=True, timeout=15,
    )
    key = out.stdout.strip()
    if not key:
        # Fallback to local kimi.env
        local = HOME / ".config" / "amg" / "kimi.env"
        if local.exists():
            for line in local.read_text().splitlines():
                if line.startswith("MOONSHOT_API_KEY=") or line.startswith("KIMI_API_KEY="):
                    return line.split("=", 1)[1].strip()
        raise RuntimeError("Kimi API key not found in env, /etc/amg/moonshot.env, or ~/.config/amg/kimi.env")
    return key


def _matches_agent(task: dict, agent: str) -> bool:
    tags = [str(t).lower() for t in (task.get("tags") or [])]
    notes = (task.get("notes") or "").lower()
    return (
        f"agent:{agent}" in tags
        or f"dispatch: {agent}" in notes
        or (task.get("agent_assigned") or "").lower() == agent
    )


def fetch_pending(agent: str) -> list[dict]:
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
            if _matches_agent(t, agent):
                out.append(t)
                seen.add(tid)
    return out


def claim(agent: str, task_id: str) -> bool:
    code, body = mcp_claim_task(operator_id=agent, task_id=task_id)
    return code == 200 and bool(body.get("success") or body.get("claimed"))


def update(agent: str, task_id: str, status: str, summary: str | None = None,
           failure: str | None = None, deliverable: str | None = None,
           notes: str | None = None) -> None:
    needs_hop = status in {"completed", "failed", "blocked"}
    try:
        if needs_hop:
            code1, body1 = mcp_update_task(
                task_id=task_id, status="active",
                notes=f"{agent}_kimi: transitioning to terminal",
            )
            if code1 != 200 or not body1.get("success", True):
                _log(agent, f"hop1-fail task={task_id} → dead_letter")
                mcp_update_task(task_id=task_id, status="dead_letter",
                                failure_reason=(failure or f"{agent} hop1 failed")[:500])
                return
        code2, body2 = mcp_update_task(
            task_id=task_id, status=status,
            result_summary=(summary or "")[:1500],
            failure_reason=(failure or None),
            deliverable_link=deliverable,
            notes=notes,
        )
        if code2 != 200 or not body2.get("success", True):
            _log(agent, f"hop2-fail task={task_id} status={status} → dead_letter")
            mcp_update_task(task_id=task_id, status="dead_letter",
                            failure_reason=(failure or f"hop2 to {status} failed")[:500])
    except Exception as e:
        _log(agent, f"update EXCEPTION task={task_id} → dead_letter ({e!r})")
        try:
            mcp_update_task(task_id=task_id, status="dead_letter",
                            failure_reason=f"{agent} update exception: {e!r}"[:500])
        except Exception as e2:
            _log(agent, f"dead_letter fallback ALSO FAILED: {e2!r}")


def _build_prompt(agent: str, task: dict) -> str:
    profile = AGENT_PROFILES[agent]
    return f"""ROLE: You are {profile['label']} ({profile['role']}), AMG factory specialist backed by Kimi K2.6.

TASK ID: {task.get('task_id')}

OBJECTIVE: {task.get('objective','')}
CONTEXT: {task.get('context','')}
INSTRUCTIONS: {task.get('instructions','')}
ACCEPTANCE CRITERIA: {task.get('acceptance_criteria','')}

OUTPUT FORMAT — return ONLY a single JSON object, no markdown fences, no preamble:

{{"ok": true|false, "artifact_path": str|null, "artifact_hash": str|null,
  "stdout_tail": str, "exit_code": 0|N, "reasoning": str}}

NO markdown fences. Output starts with `{{` ends with `}}`. Aletheia detects
hallucinated completions and flags them. If you cannot complete the task,
set ok=false + exit_code=non-zero + reasoning explaining the gap."""


def call_kimi(api_key: str, agent: str, prompt: str) -> tuple[dict, dict]:
    profile = AGENT_PROFILES[agent]
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": profile["system"]},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        KIMI_ENDPOINT,
        data=json.dumps(body).encode(),
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
    # Kimi K2.6 pricing as of 2026-04: ~$0.55/M input, $2.20/M output (rough)
    in_tokens = len(prompt) / 4
    return (in_tokens * 0.55 + max_out_tokens * 2.20) / 1_000_000


def execute_one(agent: str, task: dict, api_key: str, ks: KillSwitch | None) -> dict:
    tid = task.get("task_id")
    prompt = _build_prompt(agent, task)
    est = estimate_cost_usd(prompt)
    if ks is not None:
        cached = ks.check_cache(prompt)
        if cached is not None:
            return cached if isinstance(cached, dict) else {"ok": True, "cached": True}
        if not ks.allow_call(estimated_cost_usd=est):
            _log(agent, f"task={tid} cost-cap hit (${DAILY_CAP_USD_PER_AGENT}/day) → block")
            update(agent, tid, "blocked",
                   failure=f"{agent} daily ${DAILY_CAP_USD_PER_AGENT} kimi cap reached")
            return {"ok": False, "exit_code": 429, "reasoning": "cost cap"}
    t0 = time.time()
    try:
        resp, msg = call_kimi(api_key, agent, prompt)
    except Exception as e:
        _log(agent, f"task={tid} Kimi call FAILED: {e!r}")
        update(agent, tid, "failed", failure=f"kimi call exception: {e!r}"[:500])
        return {"ok": False, "exit_code": 1, "reasoning": f"kimi-call-exception {e!r}"}
    latency = time.time() - t0
    usage = resp.get("usage") or {}
    cost = (usage.get("prompt_tokens", 0) * 0.55 + usage.get("completion_tokens", 0) * 2.20) / 1_000_000
    if ks is not None:
        try:
            ks.record_call(prompt, cost, msg["content"])
        except Exception as e:
            _log(agent, f"cost record failed (non-fatal): {e!r}")
    receipt = parse_receipt(msg["content"])
    if receipt is None:
        _log(agent, f"task={tid} receipt UNPARSEABLE; raw={msg['content'][:200]!r}")
        update(agent, tid, "failed",
               failure=f"{agent} returned unstructured JSON; preview: {msg['content'][:300]}"[:500])
        return {"ok": False, "exit_code": 2, "reasoning": "unstructured-output"}
    artifact_path = receipt.get("artifact_path")
    summary = (
        f"{agent}_kimi receipt: ok={receipt.get('ok')} exit_code={receipt.get('exit_code')} "
        f"artifact={artifact_path} hash={receipt.get('artifact_hash')} "
        f"latency={latency:.1f}s cost=${cost:.4f} | {receipt.get('reasoning','')[:300]}"
    )
    if receipt.get("ok"):
        update(agent, tid, "completed", summary=summary,
               deliverable=artifact_path if artifact_path else None)
    else:
        update(agent, tid, "failed",
               failure=(receipt.get("reasoning") or "ok=false")[:500])
    mcp_log_decision(
        text=f"{agent.upper()} executor receipt task={tid} ok={receipt.get('ok')} cost=${cost:.4f}",
        rationale=summary,
        tags=[f"{agent}-receipt", f"task:{tid}", "kimi-k2.6"],
        project_source=agent,
    )
    return receipt


def drain_once(agent: str) -> dict:
    api_key = _resolve_kimi_key()
    ks = KillSwitch(vendor=f"kimi-{agent}", daily_cap_usd=DAILY_CAP_USD_PER_AGENT,
                    scope="executor") if KillSwitch else None
    pending = fetch_pending(agent)
    out = {"agent": agent, "scanned": len(pending), "claimed": 0, "ok": 0, "fail": 0, "skipped": 0}
    for t in pending:
        tid = t.get("task_id")
        if not claim(agent, tid):
            out["skipped"] += 1
            continue
        out["claimed"] += 1
        receipt = execute_one(agent, t, api_key, ks)
        if receipt.get("ok"):
            out["ok"] += 1
        else:
            out["fail"] += 1
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--agent", required=True, choices=list(AGENT_PROFILES.keys()))
    p.add_argument("--once", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=30)
    p.add_argument("--task-id", type=str, default=None)
    args = p.parse_args()

    state = _agent_state(args.agent)
    state["lock_file"].parent.mkdir(parents=True, exist_ok=True)
    lock_fp = state["lock_file"].open("a")
    try:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"{args.agent}_kimi_executor: another instance holds the lock", file=sys.stderr)
        return 1

    if args.task_id:
        api_key = _resolve_kimi_key()
        ks = KillSwitch(vendor=f"kimi-{args.agent}", daily_cap_usd=DAILY_CAP_USD_PER_AGENT,
                        scope="executor") if KillSwitch else None
        code, body = mcp_get_task_queue(task_id=args.task_id)
        tasks = (body or {}).get("tasks") or []
        if not tasks:
            print(f"task {args.task_id} not found")
            return 1
        if not claim(args.agent, args.task_id):
            print(f"could not claim {args.task_id}")
            return 1
        receipt = execute_one(args.agent, tasks[0], api_key, ks)
        print(json.dumps(receipt, indent=2))
        return 0 if receipt.get("ok") else 1

    if args.once or not args.watch:
        result = drain_once(args.agent)
        print(json.dumps(result, indent=2))
        return 0

    _log(args.agent, f"{args.agent}_kimi starting watch interval={args.interval}s")
    while True:
        try:
            r = drain_once(args.agent)
            if r["scanned"] > 0:
                _log(args.agent, f"watch drain: {r}")
        except Exception as e:
            _log(args.agent, f"watch ERROR: {e!r}")
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
