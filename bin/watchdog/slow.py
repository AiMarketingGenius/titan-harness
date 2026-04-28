#!/usr/bin/env python3
"""Watchdog slow loop (15min) — top-N disk offenders, inode scan, service-health.

Per WATCHDOG_VPS_v0_1.md §4. Surfaces owner-risk candidates without auto-deletion.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (
    collect_slow_signals, overall_status, load_config, write_receipt,
    top_disk_consumers, owner_risk_classify, log_decision, log,
)

MODE = "slow"


def check_required_services(cfg: dict) -> dict:
    """Returns {service: 'active'|'inactive'|'unknown'}."""
    out = {}
    for svc in cfg.get("required_services", []):
        try:
            r = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True, text=True, timeout=5,
            )
            out[svc] = r.stdout.strip() or "unknown"
        except (subprocess.SubprocessError, OSError):
            out[svc] = "unknown"
    return out


def check_required_containers(cfg: dict) -> dict:
    """Returns {container: 'healthy'|'running'|'unhealthy'|'starting'|'missing'|'unknown'}.

    Containerized services (e.g. Redis as n8n-redis-live) cannot be probed via
    systemctl is-active because they are not registered with systemd. Use
    docker inspect — prefer Health.Status (HEALTHCHECK-aware) and fall back to
    State.Status when the image has no HEALTHCHECK configured.
    """
    out = {}
    for entry in cfg.get("required_containers", []):
        name = entry.get("name") if isinstance(entry, dict) else entry
        if not name:
            continue
        try:
            r = subprocess.run(
                ["docker", "inspect", "--format",
                 "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
                 name],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode != 0:
                out[name] = "missing"
            else:
                out[name] = r.stdout.strip() or "unknown"
        except (subprocess.SubprocessError, OSError):
            out[name] = "unknown"
    return out


def main(argv: list[str]) -> int:
    cfg = load_config()
    signals = collect_slow_signals()
    status, breached = overall_status(signals, cfg)

    # Top consumers + owner-risk classification
    consumers = top_disk_consumers(20)
    candidates = owner_risk_classify(consumers)

    # Service health (systemd) + container health (docker)
    services = check_required_services(cfg)
    containers = check_required_containers(cfg)
    flapping_services = [s for s, st in services.items() if st not in ("active", "unknown")]
    flapping_containers = [c for c, st in containers.items() if st not in ("healthy", "running", "unknown")]
    flapping = flapping_services + flapping_containers

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
        "breached": breached,
        "safe_actions": [],  # slow loop doesn't auto-remediate
        "owner_risk_candidates": candidates,
        "service_health": services,
        "container_health": containers,
        "service_failures": flapping,
        "alerts_sent": [],
        "blocked": bool(flapping) or status == "critical",
        "blocker": ", ".join(flapping) if flapping else "",
    }

    alerts = []
    if status in ("action", "critical") or flapping:
        alerts.append("mcp_decision")
        msg = (f"watchdog/slow: status={status} breached={breached}; "
               f"top-{min(5, len(candidates))} owner-risk candidates: "
               f"{[(c['path'], c['bytes_est']) for c in candidates[:5]]}; "
               f"service_failures={flapping}")
        log_decision(
            text=msg,
            tags=["ct-0427-57", "watchdog-vps", "watchdog-slow", status],
            rationale=f"slow loop: signals={signals}, consumers={candidates[:5]}, services={services}, containers={containers}",
        )

    receipt["alerts_sent"] = alerts
    write_receipt(receipt)
    log(f"status={status} top={[c['path'] for c in candidates[:3]]} flapping={flapping}", MODE)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
