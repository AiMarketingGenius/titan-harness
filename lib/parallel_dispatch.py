"""
lib/parallel_dispatch.py
Ironclad architecture §4.2 — fan-out sub-agent dispatcher.

For any plan with >= 3 independent tasks, Titan should route through
dispatch_parallel_tasks so the policy.yaml capacity ceiling is respected.

Each task dict:
  {"id": str, "type": str, "prompt": str, "model": optional str}

Returns list of {"id": str, "result": str|None, "error": str|None,
                 "latency_ms": float, "started_at": float, "finished_at": float}.

This module dispatches LLM calls via model_router + llm_client. It is NOT
the layer that controls the Claude Code Agent tool spawn pacing — that
stagger lives in the parent Claude Code binary + upstream API rate limits
(see plans/PERF_NOTES_AGENT_SPAWN_STAGGER.md).

v1.1 (2026-04-15, CT-0414-09 series Item 5):
  - Latency instrumentation per task + aggregate min/median/p95/max
  - Honors night_grind_soft_relaxation ceilings when AMG_NIGHT_GRIND=1
  - Bounded retry with jittered exponential backoff (default off)
  - dispatch_with_metrics(...) returns (results, summary)
"""
from __future__ import annotations

import asyncio
import os
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any

_LIB = Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))


def _load_capacity() -> dict:
    try:
        import yaml  # type: ignore
        policy = yaml.safe_load(open(_LIB.parent / "policy.yaml"))
        cap = dict(policy.get("capacity", {}) or {})
        if os.environ.get("AMG_NIGHT_GRIND") == "1":
            relax = (policy.get("capacity", {}) or {}).get("night_grind_soft_relaxation", {}) or {}
            cap.update(relax)
        return cap
    except Exception:
        return {}


def _ceiling(name: str, default: int) -> int:
    cap = _load_capacity()
    try:
        return int(cap.get(name, default))
    except Exception:
        return default


POOL_CEILING = _ceiling("max_workers_general", 10)


async def _execute_task(task: dict, *, retry: int = 0, base_backoff_ms: int = 250) -> dict:
    started = time.time()
    last_error: str | None = None
    for attempt in range(retry + 1):
        try:
            import model_router  # type: ignore
            import llm_client  # type: ignore
        except Exception as e:
            last_error = f"llm_client/model_router unavailable: {e}"
            break
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
            finished = time.time()
            return {
                "id": task["id"],
                "result": result,
                "error": None,
                "started_at": started,
                "finished_at": finished,
                "latency_ms": (finished - started) * 1000.0,
                "attempts": attempt + 1,
            }
        except Exception as e:
            last_error = str(e)
            if attempt < retry:
                # Jittered exponential backoff — full-jitter to avoid burst-retry storms.
                wait_ms = base_backoff_ms * (2 ** attempt)
                jittered = random.uniform(0, wait_ms)
                await asyncio.sleep(jittered / 1000.0)
                continue
    finished = time.time()
    return {
        "id": task["id"],
        "result": None,
        "error": last_error or "unknown failure",
        "started_at": started,
        "finished_at": finished,
        "latency_ms": (finished - started) * 1000.0,
        "attempts": (retry + 1),
    }


async def dispatch_parallel_tasks(
    tasks: list[dict],
    *,
    retry: int = 0,
    base_backoff_ms: int = 250,
) -> list[dict]:
    """Fan out up to POOL_CEILING tasks. Respect the policy.yaml ceiling."""
    if not tasks:
        return []
    n = min(len(tasks), POOL_CEILING)
    sem = asyncio.Semaphore(n)

    async def _bounded(t: dict) -> dict:
        async with sem:
            return await _execute_task(t, retry=retry, base_backoff_ms=base_backoff_ms)

    return await asyncio.gather(*(_bounded(t) for t in tasks))


def dispatch_parallel_tasks_sync(tasks: list[dict], **kw: Any) -> list[dict]:
    """Sync wrapper for callers not in an asyncio context."""
    return asyncio.run(dispatch_parallel_tasks(tasks, **kw))


def summarize(results: list[dict]) -> dict:
    """Compute aggregate latency stats for a result set."""
    if not results:
        return {"count": 0}
    lat = [r["latency_ms"] for r in results if "latency_ms" in r]
    ok = sum(1 for r in results if r.get("error") is None)
    started = min((r["started_at"] for r in results if "started_at" in r), default=0.0)
    finished = max((r["finished_at"] for r in results if "finished_at" in r), default=0.0)
    return {
        "count": len(results),
        "ok": ok,
        "errors": len(results) - ok,
        "wall_clock_ms": (finished - started) * 1000.0 if started and finished else 0.0,
        "latency_min_ms": min(lat) if lat else 0.0,
        "latency_p50_ms": statistics.median(lat) if lat else 0.0,
        "latency_p95_ms": (
            statistics.quantiles(lat, n=20)[18] if len(lat) >= 20 else (max(lat) if lat else 0.0)
        ),
        "latency_max_ms": max(lat) if lat else 0.0,
        "pool_ceiling": POOL_CEILING,
        "night_grind_relaxed": os.environ.get("AMG_NIGHT_GRIND") == "1",
    }


def dispatch_with_metrics(tasks: list[dict], **kw: Any) -> tuple[list[dict], dict]:
    """Dispatch + return (results, summary)."""
    results = dispatch_parallel_tasks_sync(tasks, **kw)
    return results, summarize(results)


if __name__ == "__main__":
    import json
    demo = [{"id": f"t{i}", "type": "classify", "prompt": f"hello {i}"} for i in range(3)]
    results, summary = dispatch_with_metrics(demo, retry=1)
    print(json.dumps({"results": results, "summary": summary}, indent=2))
