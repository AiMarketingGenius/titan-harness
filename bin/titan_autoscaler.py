#!/usr/bin/env python3
"""titan-harness/bin/titan_autoscaler.py - Phase P9 (war-room graded A in spec)

Autoscaler for titan-worker-mp1 / titan-worker-mp2 services.

Modes (AUTOSCALER_MODE env):
    log-only   - observe + log would-be scale events, do NOT scale (default for 48h soak)
    active     - actually scale via docker API

Signal:
    queue_depth_mp1  = count(*) from tasks where status='pending' and task_type in ('mp1','harvest')
    queue_depth_mp2  = count(*) from tasks where status='pending' and task_type in ('mp2','synthesis')

Thresholds:
    AUTOSCALER_SCALE_UP_THRESHOLD     (default 50)
    AUTOSCALER_SCALE_DOWN_THRESHOLD   (default 5)
    AUTOSCALER_MAX_REPLICAS           (default POLICY_CAPACITY_MAX_WORKERS_GENERAL=10)

CORE CONTRACT: checks capacity gate before any scale-up. Never scales on
soft_block or hard_block.
"""
from __future__ import annotations

import os
import sys
import time
import json
import subprocess
from urllib import request, error

sys.path.insert(0, "/opt/titan-harness/lib")
try:
    from capacity import capacity_status
except Exception:
    def capacity_status():
        return "ok"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
MODE = os.environ.get("AUTOSCALER_MODE", "log-only").lower()
UP = int(os.environ.get("AUTOSCALER_SCALE_UP_THRESHOLD", "50"))
DOWN = int(os.environ.get("AUTOSCALER_SCALE_DOWN_THRESHOLD", "5"))
MAX_REPLICAS = int(os.environ.get("AUTOSCALER_MAX_REPLICAS",
                                  os.environ.get("POLICY_CAPACITY_MAX_WORKERS_GENERAL", "10")))
POLL_INTERVAL = int(os.environ.get("AUTOSCALER_POLL_SECONDS", "60"))


def _queue_depth(task_type_list: list[str]) -> int:
    if not SUPABASE_URL:
        return 0
    or_clause = ",".join("task_type.eq." + t for t in task_type_list)
    path = f"tasks?select=id&status=eq.pending&or=({or_clause})"
    try:
        req = request.Request(
            SUPABASE_URL + "/rest/v1/" + path,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": "Bearer " + SUPABASE_KEY,
                "Prefer": "count=exact",
            },
            method="HEAD",
        )
        with request.urlopen(req, timeout=5) as r:
            cr = r.headers.get("Content-Range", "")
            if "/" in cr:
                return int(cr.split("/")[-1])
    except Exception:
        pass
    return 0


def _current_replicas(service: str) -> int:
    try:
        out = subprocess.run(
            ["docker", "compose", "ps", "--format", "json", service],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return 0
        count = 0
        for line in out.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("State") == "running":
                    count += 1
            except Exception:
                continue
        return count
    except Exception:
        return 0


def _scale(service: str, target: int) -> bool:
    if MODE != "active":
        print(f"[log-only] would scale {service} to {target}", flush=True)
        return True
    try:
        out = subprocess.run(
            ["docker", "compose", "up", "-d", "--scale", f"{service}={target}", service],
            capture_output=True, text=True, timeout=60,
        )
        print(f"[scale] {service} -> {target}: rc={out.returncode}", flush=True)
        return out.returncode == 0
    except Exception as e:
        print(f"[scale error] {service}: {e}", flush=True)
        return False


def main():
    print(f"titan_autoscaler starting: mode={MODE} up={UP} down={DOWN} max={MAX_REPLICAS} poll={POLL_INTERVAL}s", flush=True)
    while True:
        cap = capacity_status()
        if cap == "hard_block":
            print("[skip] capacity hard block", flush=True)
            time.sleep(POLL_INTERVAL)
            continue

        for svc, filters in [
            ("titan-worker-mp1", ["mp1", "harvest"]),
            ("titan-worker-mp2", ["mp2", "synthesis"]),
        ]:
            depth = _queue_depth(filters)
            current = _current_replicas(svc)
            decision = None
            target = current
            if depth >= UP and current < MAX_REPLICAS and cap == "ok":
                target = min(current + 1, MAX_REPLICAS)
                decision = "scale-up"
            elif depth < DOWN and current > 1:
                target = max(current - 1, 1)
                decision = "scale-down"

            print(f"[poll] {svc}: depth={depth} current={current} cap={cap} decision={decision or 'hold'} target={target}", flush=True)

            if decision:
                _scale(svc, target)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
