#!/usr/bin/env python3
"""Watchdog fast loop (5min) — disk %, free GiB, RAM %, swap %, heartbeat.

Per WATCHDOG_VPS_v0_1.md §4. Emits structured receipt per §8.
Action threshold: safe remediation. Critical threshold: blocker.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (
    collect_fast_signals, evaluate_threshold, overall_status,
    load_config, write_receipt, write_heartbeat,
    safe_journal_vacuum, safe_cache_wipe, safe_docker_dangling_prune,
    log_decision, flag_blocker, log,
)

MODE = "fast"


def main(argv: list[str]) -> int:
    cfg = load_config()
    signals = collect_fast_signals()
    status, breached = overall_status(signals, cfg)

    safe_actions = []
    if status in ("action", "critical"):
        log(f"status={status} breached={breached} → safe remediation", MODE)
        rem = cfg.get("safe_remediation", {})
        # 1. journal vacuum
        if rem.get("journal_vacuum_size"):
            safe_actions.append(safe_journal_vacuum(rem["journal_vacuum_size"]))
        # 2-3. tool cache wipes (always safe; tools repopulate)
        if rem.get("playwright_cache_path"):
            safe_actions.append(safe_cache_wipe(rem["playwright_cache_path"]))
        if rem.get("trivy_cache_path"):
            safe_actions.append(safe_cache_wipe(rem["trivy_cache_path"]))
        # 4. docker dangling prune
        if rem.get("docker_dangling_prune_enabled"):
            safe_actions.append(safe_docker_dangling_prune())

    receipt = {
        "ok": True,
        "mode": MODE,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "disk_used_pct": signals.get("disk_used_pct", -1),
        "free_gib": signals.get("free_gib", -1),
        "inode_used_pct": -1,  # slow loop covers
        "ram_used_pct": signals.get("ram_used_pct", -1),
        "swap_used_pct": signals.get("swap_used_pct", -1),
        "heartbeat_age_sec": signals.get("heartbeat_age_sec", -1),
        "status": status,
        "breached": breached,
        "safe_actions": safe_actions,
        "owner_risk_candidates": [],  # slow loop surfaces these
        "alerts_sent": [],
        "blocked": False,
        "blocker": "",
    }

    alerts = []
    if status == "warn":
        alerts.append("mcp_decision")
        log_decision(
            text=f"watchdog/fast: WARN — {breached}",
            tags=["ct-0427-57", "watchdog-vps", "watchdog-fast", "warn"],
            rationale=f"signals={signals}",
        )
    elif status == "action":
        alerts.append("mcp_decision")
        log_decision(
            text=f"watchdog/fast: ACTION — {breached}; safe remediation applied: {[a['name'] for a in safe_actions]}",
            tags=["ct-0427-57", "watchdog-vps", "watchdog-fast", "action"],
            rationale=f"signals={signals}, actions={safe_actions}",
        )
    elif status == "critical":
        alerts.append("mcp_decision")
        alerts.append("flag_blocker")
        receipt["blocked"] = True
        receipt["blocker"] = f"critical thresholds breached: {breached}"
        flag_blocker(
            text=f"watchdog/fast CRITICAL — {breached}; safe remediation alone insufficient. "
                 f"Owner-risk escalation needed (see slow-loop receipt for candidates).",
            severity="critical",
        )

    receipt["alerts_sent"] = alerts
    write_receipt(receipt)
    write_heartbeat()
    log(f"status={status} signals={signals} alerts={alerts}", MODE)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
