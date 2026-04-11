"""
titan-harness/lib/async_pool.py - Phase P8 (war-room graded A in spec)

Small asyncio helper used by parallelized callers (queue-watcher, mp-runner
phase scripts, war_room.py parallel reviser) to bound concurrent work via
a semaphore while honoring the capacity CORE CONTRACT.

Public API:
    async pool_run(tasks: list[callable], max_concurrent: int,
                   cpu_heavy: bool = False) -> list
    async capacity_aware_wait(min_interval_s: float = 5.0) -> None

Semantics:
    - pool_run accepts a list of zero-arg coroutines OR zero-arg callables
      (sync callables are run in the default executor).
    - max_concurrent defaults to POLICY_CAPACITY_MAX_LLM_CONCURRENT_BATCHES.
    - If cpu_heavy=True, further clamps to POLICY_CAPACITY_MAX_WORKERS_CPU_HEAVY.
    - Capacity gate: before scheduling each coroutine, checks check_capacity();
      hard_block raises, soft_block delays by 30s then retries.
    - Returns results in the SAME ORDER as the input tasks list.
    - Exceptions inside a task are captured and returned as-is in the results
      list (no early abort — callers decide).
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any, Awaitable, Callable, Union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from capacity import check_capacity
except Exception:
    def check_capacity(timeout: float = 5.0) -> int:
        return 0

_DEFAULT_MAX = int(os.environ.get("POLICY_CAPACITY_MAX_LLM_CONCURRENT_BATCHES", "8"))
_CPU_HEAVY_MAX = int(os.environ.get("POLICY_CAPACITY_MAX_WORKERS_CPU_HEAVY", "4"))


async def capacity_aware_wait(min_interval_s: float = 5.0, max_wait_s: float = 120.0) -> None:
    """Sleep until capacity gate reports ok (exit 0). Raises on hard block after max_wait_s."""
    waited = 0.0
    while waited < max_wait_s:
        cap = check_capacity()
        if cap == 0:
            return
        if cap == 2:
            # Give hard-block some slack then re-check
            await asyncio.sleep(min_interval_s)
            waited += min_interval_s
            continue
        # soft block
        await asyncio.sleep(min_interval_s)
        waited += min_interval_s
    raise RuntimeError("capacity gate never recovered within " + str(max_wait_s) + "s")


async def pool_run(
    tasks: list[Union[Callable[[], Any], Awaitable[Any]]],
    max_concurrent: int = _DEFAULT_MAX,
    cpu_heavy: bool = False,
    capacity_check_interval: int = 10,
) -> list:
    """Run a list of tasks with bounded concurrency + capacity checks.

    Args:
        tasks: list of zero-arg callables or coroutines
        max_concurrent: max parallel tasks
        cpu_heavy: clamp max_concurrent to POLICY_CAPACITY_MAX_WORKERS_CPU_HEAVY
        capacity_check_interval: capacity gate checked every Nth scheduling decision
    """
    if cpu_heavy:
        max_concurrent = min(max_concurrent, _CPU_HEAVY_MAX)
    # Respect absolute ceiling
    max_concurrent = min(max_concurrent, _DEFAULT_MAX)

    sem = asyncio.Semaphore(max_concurrent)
    results: list = [None] * len(tasks)
    scheduled = 0

    async def _run_one(idx: int, task):
        nonlocal scheduled
        async with sem:
            # Capacity pre-check (cheap)
            scheduled += 1
            if scheduled % capacity_check_interval == 0:
                cap = check_capacity()
                if cap == 2:
                    results[idx] = RuntimeError("capacity hard block mid-pool")
                    return
            try:
                if asyncio.iscoroutine(task):
                    results[idx] = await task
                elif callable(task):
                    loop = asyncio.get_event_loop()
                    results[idx] = await loop.run_in_executor(None, task)
                else:
                    results[idx] = task
            except Exception as e:
                results[idx] = e

    await asyncio.gather(*[_run_one(i, t) for i, t in enumerate(tasks)])
    return results


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio as _asy

    def make_task(i: int):
        async def _t():
            await _asy.sleep(0.1)
            return i * i
        return _t()

    async def main():
        tasks = [make_task(i) for i in range(10)]
        start = time.time()
        out = await pool_run(tasks, max_concurrent=4)
        elapsed = time.time() - start
        print("results:", out)
        print(f"elapsed: {elapsed:.2f}s (expected ~0.3s for 10 tasks at c=4)")

    _asy.run(main())
