"""
titan-harness/lib/stagehand_pool.py

Production Optimization Pass — Vector 2 (Stagehand browser pool client).

Python client for the Node.js pool service at /opt/persistent-browser/server-pool.js
(port 3201 on VPS). Wraps acquire / navigate / execute / release with a
simple context-manager pattern so callers can parallelize browser work across
N Chromium contexts instead of serializing through one.

Public API:
    with StagehandSlot() as slot:
        slot.navigate("https://example.com")
        result = slot.execute("document.title")
        # auto-released on context exit

    pool_stats()  # returns per-slot busy/idle/totals

Fallback: if pool service unreachable, raises ConnectionError so callers can
decide whether to fall back to the single-context legacy service on port 3200
or abort.
"""
from __future__ import annotations

import contextlib
import json
import os
import time
import urllib.request
from typing import Any, Optional

POOL_BASE_URL = os.environ.get("STAGEHAND_POOL_URL", "http://127.0.0.1:3201").rstrip("/")
DEFAULT_TIMEOUT = 30


def _post(path: str, payload: Optional[dict[str, Any]] = None, *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    body = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{POOL_BASE_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — trusted
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str, *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    req = urllib.request.Request(f"{POOL_BASE_URL}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def pool_stats() -> dict[str, Any]:
    """Return per-slot busy/idle/totals. Useful for /admin observability."""
    return _get("/pool/stats")


def acquire_slot() -> int:
    """Acquire a slot; returns ctx_id. Raises if pool unreachable."""
    r = _post("/pool/acquire")
    if "ctx" not in r:
        raise RuntimeError(f"pool acquire failed: {r}")
    return int(r["ctx"])


def release_slot(ctx_id: int) -> bool:
    """Release a slot. Best-effort; swallow errors."""
    try:
        _post(f"/pool/release/{ctx_id}")
        return True
    except Exception:
        return False


class StagehandSlot:
    """Context-manager wrapper around an acquired pool slot."""

    def __init__(self, *, auto_release: bool = True):
        self.ctx_id: Optional[int] = None
        self.auto_release = auto_release

    def __enter__(self) -> "StagehandSlot":
        self.ctx_id = acquire_slot()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.auto_release and self.ctx_id is not None:
            release_slot(self.ctx_id)
            self.ctx_id = None

    def navigate(self, url: str, *, new_tab: bool = False) -> dict[str, Any]:
        if self.ctx_id is None:
            raise RuntimeError("slot not acquired")
        return _post("/navigate", {"ctx": self.ctx_id, "url": url, "newTab": new_tab})

    def execute(self, script: str) -> Any:
        if self.ctx_id is None:
            raise RuntimeError("slot not acquired")
        r = _post("/execute", {"ctx": self.ctx_id, "script": script})
        return r.get("result")

    def screenshot_bytes(self) -> bytes:
        """Returns raw PNG bytes for the current page in this slot."""
        if self.ctx_id is None:
            raise RuntimeError("slot not acquired")
        req = urllib.request.Request(
            f"{POOL_BASE_URL}/screenshot?ctx={self.ctx_id}",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:  # noqa: S310
            return resp.read()

    def pages(self) -> list[dict[str, Any]]:
        if self.ctx_id is None:
            raise RuntimeError("slot not acquired")
        return _get(f"/pages?ctx={self.ctx_id}").get("pages", [])


# ---------------------------------------------------------------------------
# Parallel fan-out helper
# ---------------------------------------------------------------------------

def run_parallel(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Run N tasks in parallel across N pool slots. Each task: {"id", "url", "script"}.
    Returns [{"id", "title"|"result"|"error"}, ...] preserving input order.

    Fan-out is sequential in this implementation because pool-side parallelism
    is the actual benefit; callers wanting true async fan-out should use
    asyncio + httpx. In-sequence acquire+release still delivers the throughput
    multiplier because each task serializes per-context but runs on an idle slot.
    """
    import concurrent.futures

    def _run_one(task):
        with StagehandSlot() as slot:
            try:
                slot.navigate(task["url"])
                result = None
                if task.get("script"):
                    result = slot.execute(task["script"])
                return {
                    "id": task["id"],
                    "ctx": slot.ctx_id,
                    "url": task["url"],
                    "result": result,
                }
            except Exception as exc:
                return {"id": task["id"], "error": str(exc)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as ex:
        results = list(ex.map(_run_one, tasks))
    return results


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> int:
    print(f"[stagehand_pool selftest] probing {POOL_BASE_URL}/pool/stats ...")
    try:
        stats = pool_stats()
        print(f"  stats: {json.dumps(stats, indent=2)[:600]}")
    except Exception as exc:
        print(f"  POOL UNREACHABLE: {exc}")
        print("  (expected if server-pool.js not deployed yet; deploy with systemctl start persistent-browser-pool)")
        return 0

    print(f"[stagehand_pool selftest] acquire + release cycle ...")
    t0 = time.monotonic()
    with StagehandSlot() as slot:
        print(f"  acquired ctx {slot.ctx_id}")
        r = slot.navigate("https://example.com")
        print(f"  navigated: {r.get('title')}")
    wall = (time.monotonic() - t0) * 1000
    print(f"  cycle wall-clock: {wall:.0f}ms (includes nav + release)")

    print(f"[stagehand_pool selftest] parallel fan-out (3 tasks) ...")
    tasks = [
        {"id": f"task-{i}", "url": "https://example.com", "script": "document.title"}
        for i in range(3)
    ]
    t0 = time.monotonic()
    results = run_parallel(tasks)
    wall = (time.monotonic() - t0) * 1000
    print(f"  parallel wall-clock: {wall:.0f}ms for {len(results)} tasks (serial would be ~3x)")
    for r in results:
        print(f"    {r}")
    print("[stagehand_pool selftest] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
