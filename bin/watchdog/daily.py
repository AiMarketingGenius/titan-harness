#!/usr/bin/env python3
"""Watchdog daily summary — trend delta, repeated offender list, receipt rollup.

Per WATCHDOG_VPS_v0_1.md §4 daily cadence.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (
    collect_slow_signals, overall_status, load_config, write_receipt,
    top_disk_consumers, log_decision, log, RECEIPT_DIR,
)

MODE = "daily"


def load_recent_receipts(hours: int = 24) -> list[dict]:
    cutoff = time.time() - (hours * 3600)
    receipts = []
    for path in glob.glob(os.path.join(RECEIPT_DIR, "*.json")):
        if os.path.basename(path).startswith("latest_"):
            continue
        try:
            if os.path.getmtime(path) < cutoff:
                continue
            with open(path) as f:
                receipts.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(receipts, key=lambda r: r.get("ts", ""))


def main(argv: list[str]) -> int:
    cfg = load_config()
    signals = collect_slow_signals()
    status, breached = overall_status(signals, cfg)

    recent = load_recent_receipts(24)
    breach_counts = {}
    for r in recent:
        for b in r.get("breached") or []:
            metric = b.split("=")[0]
            breach_counts[metric] = breach_counts.get(metric, 0) + 1

    repeated_offenders = sorted(
        [{"metric": m, "breach_count_24h": c} for m, c in breach_counts.items()],
        key=lambda x: -x["breach_count_24h"],
    )

    consumers = top_disk_consumers(10)

    summary_text = (
        f"watchdog/daily 24h summary: current status={status}; "
        f"receipts in window={len(recent)}; "
        f"repeated offenders={repeated_offenders}; "
        f"top consumers (>=100MB): {[(c['path'], c['bytes_est']) for c in consumers[:5]]}"
    )

    receipt = {
        "ok": True,
        "mode": MODE,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "disk_used_pct": signals.get("disk_used_pct", -1),
        "free_gib": signals.get("free_gib", -1),
        "inode_used_pct": signals.get("inode_used_pct", -1),
        "ram_used_pct": signals.get("ram_used_pct", -1),
        "swap_used_pct": signals.get("swap_used_pct", -1),
        "status": status,
        "summary_24h_receipts": len(recent),
        "repeated_offenders": repeated_offenders,
        "top_consumers": consumers,
        "alerts_sent": ["mcp_decision"],
        "blocked": False,
        "blocker": "",
    }

    log_decision(
        text=summary_text,
        tags=["ct-0427-57", "watchdog-vps", "watchdog-daily", status],
        rationale=f"24h aggregate of {len(recent)} fast/slow receipts.",
    )

    write_receipt(receipt)
    log(summary_text, MODE)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
