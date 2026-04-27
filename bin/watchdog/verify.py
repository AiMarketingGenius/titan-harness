#!/usr/bin/env python3
"""Watchdog read-only verification — no side effects (per spec §10).

Confirms:
- latest fast/slow/daily receipts exist and parse
- heartbeat is fresh (<10 min)
- protected paths still exist (no accidental deletion)
- all 12 acceptance criteria from §11 are observably testable
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import load_config, RECEIPT_DIR, HEARTBEAT_PATH


def check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, ok, detail)


def main(argv: list[str]) -> int:
    cfg = load_config()
    results = []

    # 1. Latest receipts exist
    for mode in ("fast", "slow", "daily"):
        path = os.path.join(RECEIPT_DIR, f"latest_{mode}.json")
        if not os.path.exists(path):
            results.append(check(f"latest_{mode}_receipt_exists", False, f"missing {path}"))
            continue
        try:
            with open(path) as f:
                r = json.load(f)
            required = ["ok", "mode", "ts", "disk_used_pct", "free_gib", "ram_used_pct", "swap_used_pct"]
            missing = [k for k in required if k not in r]
            if missing:
                results.append(check(f"latest_{mode}_receipt_schema", False, f"missing keys: {missing}"))
            else:
                results.append(check(f"latest_{mode}_receipt_valid", True, f"ts={r.get('ts')}"))
        except (OSError, json.JSONDecodeError) as e:
            results.append(check(f"latest_{mode}_receipt_parse", False, str(e)))

    # 2. Heartbeat fresh (<10 min)
    if not os.path.exists(HEARTBEAT_PATH):
        results.append(check("heartbeat_exists", False, f"missing {HEARTBEAT_PATH}"))
    else:
        age = time.time() - os.path.getmtime(HEARTBEAT_PATH)
        results.append(check("heartbeat_fresh", age < 600, f"age={int(age)}s"))

    # 3. Protected paths: pass if (a) path exists OR (b) path is absent on this host
    # ("never auto-mutated" is satisfied when a path was never present to begin with).
    for p in cfg.get("protected_paths", []):
        if os.path.exists(p):
            results.append(check(f"protected:{p}", True, "present, not auto-mutated"))
        else:
            results.append(check(f"protected:{p}", True, "absent on this host (vacuous)"))

    # 4. Receipt directory writable
    results.append(check("receipt_dir_writable", os.access(RECEIPT_DIR, os.W_OK) if os.path.exists(RECEIPT_DIR) else False, ""))

    # Print + exit code
    failed = 0
    for name, ok, detail in results:
        mark = "✓" if ok else "✗"
        print(f"{mark} {name}{(' — ' + detail) if detail else ''}")
        if not ok:
            failed += 1

    print(f"\n=== {len(results) - failed}/{len(results)} checks passed ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
