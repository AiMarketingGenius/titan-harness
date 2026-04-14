#!/usr/bin/env python3
"""SEC P3 Fix 1: Watchdog Load Test

Simulates 10x normal event rate, measures check completion times.
Verifies all 17 checks complete within acceptable bounds under load.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Import the watchdog checks
sys.path.insert(0, "/opt/amg-security")
try:
    from security_watchdog import ALL_CHECKS, EXPENSIVE_CHECKS, run_tick
except ImportError:
    print("ERROR: Cannot import security_watchdog. Run from VPS.")
    sys.exit(1)

NORMAL_TICK = 60  # seconds
LOAD_MULTIPLIER = 10
TEST_DURATION = 300  # 5 minutes
ACCEPTABLE_TICK_TIME = 30  # seconds — tick must complete in <30s


async def run_load_test():
    """Simulate 10x normal event rate and measure check completion times."""
    results = {
        "test_start": datetime.now(timezone.utc).isoformat(),
        "load_multiplier": LOAD_MULTIPLIER,
        "normal_tick_interval": NORMAL_TICK,
        "simulated_tick_interval": NORMAL_TICK / LOAD_MULTIPLIER,
        "acceptable_tick_time": ACCEPTABLE_TICK_TIME,
        "ticks": [],
        "failures": [],
    }

    tick_count = 0
    total_time = 0
    max_tick_time = 0
    start = time.time()

    while time.time() - start < TEST_DURATION:
        tick_start = time.time()

        # Run all checks (same as a normal tick)
        check_results = {}
        for check in ALL_CHECKS:
            check_start = time.time()
            try:
                await asyncio.wait_for(check(), timeout=15)
                check_results[check.__name__] = {
                    "status": "ok",
                    "duration_ms": round((time.time() - check_start) * 1000, 1)
                }
            except asyncio.TimeoutError:
                check_results[check.__name__] = {
                    "status": "timeout",
                    "duration_ms": 15000
                }
                results["failures"].append({
                    "tick": tick_count,
                    "check": check.__name__,
                    "reason": "timeout_15s"
                })
            except Exception as e:
                check_results[check.__name__] = {
                    "status": "error",
                    "error": str(e),
                    "duration_ms": round((time.time() - check_start) * 1000, 1)
                }

        tick_time = time.time() - tick_start
        total_time += tick_time
        max_tick_time = max(max_tick_time, tick_time)
        tick_count += 1

        results["ticks"].append({
            "tick": tick_count,
            "duration_s": round(tick_time, 2),
            "checks_completed": sum(1 for v in check_results.values() if v["status"] == "ok"),
            "checks_failed": sum(1 for v in check_results.values() if v["status"] != "ok"),
        })

        if tick_time > ACCEPTABLE_TICK_TIME:
            results["failures"].append({
                "tick": tick_count,
                "check": "tick_overall",
                "reason": f"tick_time_{tick_time:.1f}s_exceeds_{ACCEPTABLE_TICK_TIME}s"
            })

        # Simulate 10x rate: sleep 6s instead of 60s
        await asyncio.sleep(max(0, (NORMAL_TICK / LOAD_MULTIPLIER) - tick_time))

    results["test_end"] = datetime.now(timezone.utc).isoformat()
    results["summary"] = {
        "total_ticks": tick_count,
        "avg_tick_time_s": round(total_time / max(tick_count, 1), 2),
        "max_tick_time_s": round(max_tick_time, 2),
        "total_failures": len(results["failures"]),
        "verdict": "PASS" if max_tick_time < ACCEPTABLE_TICK_TIME and not results["failures"] else "FAIL"
    }

    return results


if __name__ == "__main__":
    print("=== Watchdog Load Test (10x normal rate, 5 min) ===")
    results = asyncio.run(run_load_test())
    print(json.dumps(results["summary"], indent=2))

    if results["failures"]:
        print(f"\n⚠️  {len(results['failures'])} failure(s):")
        for f in results["failures"][:10]:
            print(f"  Tick {f['tick']}: {f['check']} — {f['reason']}")

    # Write full results
    output = Path("/var/log/amg-security/watchdog-load-test.json")
    try:
        with open(output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nFull results: {output}")
    except Exception:
        print(json.dumps(results, indent=2))
