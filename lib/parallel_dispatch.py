"""
lib/parallel_dispatch.py
Ironclad architecture §4.2 — fan-out sub-agent dispatcher.

For any plan with >= 3 independent tasks, Titan should route through
dispatch_parallel_tasks so the policy.yaml general-workers ceiling (10)
is respected.

Each task dict:
  {"id": str, "type": str, "prompt": str, "model": optional str}

Returns list of {"id": str, "result": str|None, "error": str|None}.

This module tries real async_pool + model_router; falls back to a serial
loop if those are not yet wired on a given node.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

_LIB = Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))


def _ceiling(name: str, default: int) -> int:
    try:
        import yaml  # type: ignore
        policy = yaml.safe_load(open(_LIB.parent / "policy.yaml"))
        return int(policy.get("capacity", {}).get(name, default))
    except Exception:
        return default


POOL_CEILING = _ceiling("max_workers_general", 10)


async def _execute_task(task: dict) -> dict:
    try:
        import model_router  # type: ignore
        import llm_client  # type: ignore
    except Exception:
        # Stub fallback: return an error rather than silently succeeding.
        return {"id": task["id"], "result": None, "error": "llm_client/model_router unavailable"}

    try:
        model = task.get("model") or model_router.route_model(task["type"])
        if hasattr(llm_client, "call_async"):
            result = await llm_client.call_async(
                model=model, prompt=task["prompt"], task_type=task["type"]
            )
        else:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: llm_client.call(model=model, prompt=task["prompt"], task_type=task["type"]),
            )
        return {"id": task["id"], "result": result, "error": None}
    except Exception as e:
        return {"id": task["id"], "result": None, "error": str(e)}


async def dispatch_parallel_tasks(tasks: list[dict]) -> list[dict]:
    """Fan out up to POOL_CEILING tasks. Respect the policy.yaml ceiling."""
    if not tasks:
        return []
    n = min(len(tasks), POOL_CEILING)
    sem = asyncio.Semaphore(n)

    async def _bounded(t: dict) -> dict:
        async with sem:
            return await _execute_task(t)

    return await asyncio.gather(*(_bounded(t) for t in tasks))


def dispatch_parallel_tasks_sync(tasks: list[dict]) -> list[dict]:
    """Sync wrapper for callers not in an asyncio context."""
    return asyncio.run(dispatch_parallel_tasks(tasks))


if __name__ == "__main__":
    import json
    demo = [{"id": f"t{i}", "type": "classify", "prompt": f"hello {i}"} for i in range(3)]
    print(json.dumps(dispatch_parallel_tasks_sync(demo), indent=2))
