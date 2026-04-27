#!/usr/bin/env python3
"""phase_a_smoke_runner.py — direct execution of Phase A smoke tasks bypassing
queue-pagination limit (MCP /api/task-queue returns only the first 50 oldest
approved tasks; smoke tasks CT-0427-14..25 are below the cutoff).

Runs each task via the matching executor's execute_one() function imported
directly. Bypasses the daemon's fcntl lock file entirely (we're not calling
main()). Watch daemons can keep running.

This is the smoke-test harness, NOT the production polling path. Production
queue-scan has a separate follow-up task to add server-side pagination or
tag filtering to MCP /api/task-queue.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HOME = Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "scripts"))
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))

from mcp_rest_client import get_task_queue, claim_task as mcp_claim_task

# Smoke test plan: 12 tasks, 4 per chief.
SMOKE_PLAN = [
    # (task_id, executor_module, executor_role, owner, claim_operator)
    ("CT-0427-14", "daedalus_v4_pro_executor",   "daedalus",   "hercules",  "daedalus"),
    ("CT-0427-15", "artisan_v4_flash_executor",  "artisan",    "hercules",  "artisan"),
    ("CT-0427-16", "hephaestus_local_executor",  "hephaestus", "hercules",  "hephaestus"),
    ("CT-0427-17", "kimi_agent_executor",        "athena",     "hercules",  "athena"),
    ("CT-0427-18", "daedalus_v4_pro_executor",   "daedalus",   "nestor",    "daedalus"),
    ("CT-0427-19", "artisan_v4_flash_executor",  "artisan",    "nestor",    "artisan"),
    ("CT-0427-20", "hephaestus_local_executor",  "hephaestus", "nestor",    "hephaestus"),
    ("CT-0427-21", "lumina_visual_qa_executor",  "lumina",     "nestor",    "lumina"),
    ("CT-0427-22", "daedalus_v4_pro_executor",   "daedalus",   "alexander", "daedalus"),
    ("CT-0427-23", "artisan_v4_flash_executor",  "artisan",    "alexander", "artisan"),
    ("CT-0427-24", "hephaestus_local_executor",  "hephaestus", "alexander", "hephaestus"),
    ("CT-0427-25", "echo_brand_voice_executor",  "echo",       "alexander", "echo"),
]


def fetch_task(task_id: str) -> dict | None:
    code, body = get_task_queue(task_id=task_id)
    if code != 200:
        return None
    tasks = (body or {}).get("tasks") or []
    return tasks[0] if tasks else None


def run_one(task_id: str, module_name: str, role: str, owner: str, claim_op: str) -> dict:
    task = fetch_task(task_id)
    if task is None:
        return {"ok": False, "task_id": task_id, "error": "task not found"}
    if task.get("status") in {"completed", "failed", "blocked", "dead_letter"}:
        return {"ok": True, "task_id": task_id, "status": task.get("status"),
                "skipped": True, "reason": f"already {task.get('status')}"}
    if task.get("locked_by"):
        return {"ok": False, "task_id": task_id, "error": f"locked by {task.get('locked_by')}"}

    # Claim with the matching operator id
    code, body = mcp_claim_task(operator_id=claim_op, task_id=task_id)
    claimed = code == 200 and bool(body.get("success") or body.get("claimed"))
    if not claimed:
        return {"ok": False, "task_id": task_id, "error": f"claim failed code={code} body={body}"}
    # Re-fetch after claim
    task = fetch_task(task_id) or task

    mod = __import__(module_name)
    chief_gate = None
    try:
        from chief_cost_gate import ChiefCostGate
        # Vendor mapping per executor
        vendor_map = {
            "daedalus":   "deepseek-v4-pro",
            "artisan":    "deepseek-v4-flash",
            "hephaestus": "ollama-local",
            "athena":     "kimi-athena",
            "lumina":     "gemini-2.5-flash",
            "echo":       "deepseek-v3",
        }
        chief_gate = ChiefCostGate(chief=owner, role=role, vendor=vendor_map[role])
    except Exception as e:
        print(f"[{task_id}] chief_gate construct failed: {e!r}", file=sys.stderr)

    if module_name == "daedalus_v4_pro_executor":
        api_key = mod._resolve_api_key()
        ks = mod.KillSwitch(vendor="deepseek-v4-pro", daily_cap_usd=20.0, scope="executor") if mod.KillSwitch else None
        receipt = mod.execute_one(task, api_key, ks, owner=owner, chief_gate=chief_gate)
    elif module_name == "artisan_v4_flash_executor":
        api_key = mod._resolve_api_key()
        ks = mod.KillSwitch(vendor="deepseek-v4-flash", daily_cap_usd=10.0, scope="executor") if mod.KillSwitch else None
        receipt = mod.execute_one(task, api_key, ks, owner=owner, chief_gate=chief_gate)
    elif module_name == "hephaestus_local_executor":
        receipt = mod.execute_one(task, owner=owner)
    elif module_name == "kimi_agent_executor":
        api_key = mod._resolve_kimi_key()
        ks = mod.KillSwitch(vendor=f"kimi-{role}", daily_cap_usd=5.0, scope="executor") if mod.KillSwitch else None
        receipt = mod.execute_one(role, task, api_key, ks, owner=owner, chief_gate=chief_gate)
    elif module_name == "lumina_visual_qa_executor":
        api_key = mod._resolve_gemini_key()
        receipt = mod.execute_one(task, api_key, owner=owner, chief_gate=chief_gate)
    elif module_name == "echo_brand_voice_executor":
        api_key = mod._resolve_api_key()
        receipt = mod.execute_one(task, api_key, owner=owner, chief_gate=chief_gate)
    else:
        return {"ok": False, "task_id": task_id, "error": f"unknown module {module_name}"}

    return {"ok": bool(receipt.get("ok")), "task_id": task_id,
            "owner": owner, "role": role,
            "exit_code": receipt.get("exit_code"),
            "stdout_tail_preview": (receipt.get("stdout_tail") or "")[:200],
            "reasoning": (receipt.get("reasoning") or "")[:200]}


def main() -> int:
    results: list[dict] = []
    for task_id, module_name, role, owner, claim_op in SMOKE_PLAN:
        print(f"[{task_id}] running via {module_name} owner={owner}...", flush=True)
        try:
            r = run_one(task_id, module_name, role, owner, claim_op)
        except Exception as e:
            r = {"ok": False, "task_id": task_id, "error": f"exception: {e!r}"}
        results.append(r)
        print(f"[{task_id}] → {json.dumps(r)[:400]}", flush=True)
    print("\n=== SMOKE TEST SUMMARY ===")
    print(json.dumps(results, indent=2))
    ok_count = sum(1 for r in results if r.get("ok"))
    print(f"\nPASS: {ok_count}/{len(results)}")
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
