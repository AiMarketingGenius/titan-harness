#!/usr/bin/env python3
"""cerberus_security_watcher.py — security incident watcher.

Phase 2.6 of Hercules's MASTER BUILD ORDER 2026-04-26: concept-only build
TONIGHT (per Hercules's explicit "BUILD NOW — concept only" tagline).
Real security checks land in a follow-on iteration.

Design intent (from CLAUDE.md §21 + the Hercules dispatch):
  - Watch for security incidents with DUAL-SIGNAL FLOOR (no false alerts).
  - Signals to monitor (real implementation deferred):
      * Failed auth attempts > N in 5 min on amg-staging /var/log/auth.log
      * Unknown SSH connections (vs allowlist)
      * MCP API spikes from unknown IPs
      * /etc/amg/*.env file mtime changes (credential leak indicator)
      * Git diff-stat on tracked secret files
      * Daedalus/Artisan/Nestor receipts containing trade-secret terms
  - Two signals match → P0 SMS to Solon via Telnyx
  - One signal alone → log to MCP, no alert
  - Quiet hours respected (11pm-7am EST)

Tonight: scaffold + pollable health endpoint + structure for Hercules to
dispatch real security audits to via tag `agent:cerberus`. The actual
log-tail logic lands in CT-NEXT-SECURITY-IMPL.

Run modes:
    cerberus_security_watcher.py --once
    cerberus_security_watcher.py --watch
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from datetime import datetime, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))

from mcp_rest_client import (  # noqa: E402
    log_decision as mcp_log_decision,
    get_recent_decisions as mcp_get_recent,
)

LOG_FILE = HOME / ".openclaw" / "logs" / "cerberus_security_watcher.log"
STATE_FILE = HOME / ".openclaw" / "state" / "cerberus_state.json"

# Signal thresholds (concept — replace with real values when implementation lands)
DUAL_SIGNAL_WINDOW_MINUTES = 5
QUIET_HOURS_UTC = (3, 11)  # 11pm-7am EST = 3am-11am UTC


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with LOG_FILE.open("a") as f:
        f.write(f"[{ts}] {msg}\n")


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {"signals": [], "last_alert": None, "concept_status": "scaffolded 2026-04-27"}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"signals": [], "last_alert": None}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def check_concept_signals() -> list[dict]:
    """Concept-only signal collection. Returns empty list tonight; real
    signals land in CT-NEXT-SECURITY-IMPL. Logs a heartbeat decision so
    the daemon's existence is auditable from MCP."""
    return []


def drain_once() -> dict:
    state = _load_state()
    signals = check_concept_signals()
    out = {
        "scanned": True,
        "concept_status": state.get("concept_status", "scaffolded"),
        "signals_collected": len(signals),
        "alerts_fired": 0,
        "in_quiet_hours": _in_quiet_hours(),
    }
    # Heartbeat so the gist + persistent memory know Cerberus is alive
    if int(time.time()) % 1800 < 60:  # ~ every 30 min
        try:
            mcp_log_decision(
                text="CERBERUS heartbeat (concept-only build, no real signals yet)",
                rationale="Phase 2.6 scaffold per Hercules MASTER BUILD ORDER 2026-04-26. Real signal collection lands in follow-on dispatch.",
                tags=["cerberus-heartbeat", "phase-2.6", "concept-only"],
                project_source="cerberus",
            )
        except Exception as e:
            _log(f"heartbeat log fail (non-fatal): {e!r}")
    _save_state(state)
    return out


def _in_quiet_hours() -> bool:
    h = datetime.now(timezone.utc).hour
    start, end = QUIET_HOURS_UTC
    return start <= h < end


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=300)
    args = p.parse_args()

    if args.once or not args.watch:
        result = drain_once()
        print(json.dumps(result, indent=2))
        return 0

    _log(f"cerberus_security_watcher starting watch interval={args.interval}s (CONCEPT-ONLY build)")
    while True:
        try:
            drain_once()
        except Exception as e:
            _log(f"watch ERROR: {e!r}")
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
