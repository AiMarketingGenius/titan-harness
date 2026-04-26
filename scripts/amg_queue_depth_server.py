#!/usr/bin/env python3
"""
amg_queue_depth_server.py — tiny stdlib HTTP service exposing the n8n Bull
queue depth as JSON. Runs on the VPS only (queries the local n8n-redis-live
Docker container via docker exec).

Endpoint:
    GET /webhook/queue-depth   → {"depth": N, "waiting": W, "active": A,
                                  "delayed": D, "completed_recent": C, "ts": ...}
    GET /healthz               → {"status":"ok"}

Caddy in front of this routes
    https://n8n.aimarketinggenius.io/webhook/queue-depth → 127.0.0.1:5679

Reads Redis password from /etc/amg/redis-shared.env (SHARED_REDIS_PASSWORD).
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

REDIS_ENV = pathlib.Path("/etc/amg/redis-shared.env")
REDIS_CONTAINER = os.environ.get("REDIS_CONTAINER", "n8n-redis-live")
BULL_PREFIX = os.environ.get("BULL_PREFIX", "bull:jobs")
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = int(os.environ.get("PORT", "5679"))


def _load_redis_password() -> str:
    if not REDIS_ENV.exists():
        return ""
    for line in REDIS_ENV.read_text().splitlines():
        if line.startswith("SHARED_REDIS_PASSWORD="):
            return line.split("=", 1)[1].strip()
    return ""


def _redis_cli(*args: str) -> str:
    pw = _load_redis_password()
    cmd = ["docker", "exec", REDIS_CONTAINER, "redis-cli"]
    if pw:
        cmd += ["-a", pw, "--no-auth-warning"]
    cmd += list(args)
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def queue_depth_payload() -> dict:
    waiting   = int(_redis_cli("LLEN", f"{BULL_PREFIX}:waiting") or 0)
    active    = int(_redis_cli("LLEN", f"{BULL_PREFIX}:active")  or 0)
    delayed   = int(_redis_cli("ZCARD", f"{BULL_PREFIX}:delayed") or 0)
    completed = int(_redis_cli("ZCARD", f"{BULL_PREFIX}:completed") or 0)
    return {
        "depth":   waiting + active + delayed,
        "waiting": waiting,
        "active":  active,
        "delayed": delayed,
        "completed_recent": completed,
        "ts": int(time.time()),
        "source": f"redis://{REDIS_CONTAINER}/{BULL_PREFIX}",
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict) -> None:
        b = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/queue-depth", "/webhook/queue-depth"):
            self._send(200, queue_depth_payload())
        elif self.path == "/healthz":
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": "not found", "path": self.path})

    def log_message(self, fmt, *args):
        # Quieter than default; only error-level via stderr
        return


def main() -> int:
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(f"[queue-depth] listening on {LISTEN_HOST}:{LISTEN_PORT}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
