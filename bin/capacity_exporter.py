#!/usr/bin/env python3
"""titan-harness/bin/capacity_exporter.py - Phase P9

Minimal Prometheus text-format exporter for the capacity gate + host stats.
Runs the check-capacity.sh script every 10s and exposes at :9101/metrics.

Metrics:
    titan_capacity_status{status="ok|soft|hard"}   (gauge, 0|1)
    titan_capacity_cpu_pct                         (gauge)
    titan_capacity_ram_gib                         (gauge)
    titan_capacity_last_check_timestamp_seconds    (gauge)
"""
from __future__ import annotations

import os
import re
import time
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PROMETHEUS_PORT", "9101"))
SCRIPT = os.environ.get("CHECK_CAPACITY_PATH", "/opt/titan-harness/bin/check-capacity.sh")
INTERVAL = int(os.environ.get("CAPACITY_CHECK_INTERVAL_SECONDS", "10"))

_state = {
    "status": "ok",
    "cpu": 0,
    "ram": 0,
    "last_check": 0,
}


def _poll_loop():
    while True:
        try:
            r = subprocess.run([SCRIPT], capture_output=True, text=True, timeout=5)
            line = r.stdout.strip()
            m = re.search(r"status=(\w+)\s+cpu=(\d+)%\s+ram=(\d+)GiB", line)
            if m:
                _state["status"] = m.group(1).replace("_block", "")
                _state["cpu"] = int(m.group(2))
                _state["ram"] = int(m.group(3))
            _state["last_check"] = int(time.time())
        except Exception:
            pass
        time.sleep(INTERVAL)


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        body = self._render()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, fmt, *args):
        return  # silence access log

    def _render(self) -> str:
        status = _state["status"]
        ok = 1 if status == "ok" else 0
        soft = 1 if status == "soft" else 0
        hard = 1 if status == "hard" else 0
        return (
            "# HELP titan_capacity_status Current capacity gate status (1=active)\n"
            "# TYPE titan_capacity_status gauge\n"
            f'titan_capacity_status{{status="ok"}} {ok}\n'
            f'titan_capacity_status{{status="soft"}} {soft}\n'
            f'titan_capacity_status{{status="hard"}} {hard}\n'
            "# HELP titan_capacity_cpu_pct Current CPU percent (1-min avg)\n"
            "# TYPE titan_capacity_cpu_pct gauge\n"
            f"titan_capacity_cpu_pct {_state['cpu']}\n"
            "# HELP titan_capacity_ram_gib Current RAM used in GiB\n"
            "# TYPE titan_capacity_ram_gib gauge\n"
            f"titan_capacity_ram_gib {_state['ram']}\n"
            "# HELP titan_capacity_last_check_timestamp_seconds Last check unix timestamp\n"
            "# TYPE titan_capacity_last_check_timestamp_seconds gauge\n"
            f"titan_capacity_last_check_timestamp_seconds {_state['last_check']}\n"
        )


def main():
    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()
    print(f"capacity_exporter listening on :{PORT}/metrics (check every {INTERVAL}s)", flush=True)
    HTTPServer(("0.0.0.0", PORT), MetricsHandler).serve_forever()


if __name__ == "__main__":
    main()
