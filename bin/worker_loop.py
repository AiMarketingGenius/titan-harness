#!/usr/bin/env python3
"""titan-harness/bin/worker_loop.py - Phase P9 PLACEHOLDER

Minimal worker loop for the titan-base Docker image. In P9.1 this will be
replaced by the full titan_queue_watcher refactor using async_pool +
SELECT FOR UPDATE SKIP LOCKED claim pattern.

For the P9 substrate ship, this is a no-op loop that:
    - Respects check_capacity()
    - Emits heartbeat to titan_workers table every 60s
    - Logs filter config and exits cleanly on SIGTERM

The existing /usr/local/bin/titan_queue_watcher.py continues to process
tasks as the systemd service titan-queue-watcher.service until P9.1 cutover.
"""
from __future__ import annotations

import os
import sys
import time
import signal
import json
import socket
sys.path.insert(0, "/opt/titan-harness/lib")
from urllib import request, error

try:
    from capacity import capacity_status
except Exception:
    def capacity_status():
        return "ok"

INSTANCE = os.environ.get("TITAN_INSTANCE", "titan-worker-main")
FILTER = os.environ.get("TITAN_WORKER_FILTER", "any")
HEARTBEAT_INTERVAL = 60
SUPA_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPA_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

_shutdown = False

def _sigterm(sig, frame):
    global _shutdown
    _shutdown = True
    print(f"[worker] received signal {sig}, shutting down")

signal.signal(signal.SIGTERM, _sigterm)
signal.signal(signal.SIGINT, _sigterm)


def _heartbeat():
    if not SUPA_URL:
        return
    body = {
        "instance_id": INSTANCE,
        "worker_idx": 0,
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "active": True,
        "last_heartbeat": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        req = request.Request(
            SUPA_URL + "/rest/v1/titan_workers?on_conflict=instance_id,worker_idx",
            data=json.dumps(body).encode(),
            headers={
                "apikey": SUPA_KEY,
                "Authorization": "Bearer " + SUPA_KEY,
                "Content-Type": "application/json",
                "Prefer": "return=minimal,resolution=merge-duplicates",
            },
            method="POST",
        )
        request.urlopen(req, timeout=5).read()
    except Exception as e:
        print(f"[worker] heartbeat failed: {e}")


def main():
    print(f"[worker] boot: instance={INSTANCE} filter={FILTER} pid={os.getpid()}")
    print(f"[worker] P9 substrate mode — not claiming tasks (titan-queue-watcher.service still owns the claim loop)")
    while not _shutdown:
        cap = capacity_status()
        if cap == "hard_block":
            print(f"[worker] capacity hard block, sleeping {HEARTBEAT_INTERVAL}s")
        _heartbeat()
        for _ in range(HEARTBEAT_INTERVAL):
            if _shutdown:
                break
            time.sleep(1)
    print("[worker] clean shutdown")


if __name__ == "__main__":
    main()
