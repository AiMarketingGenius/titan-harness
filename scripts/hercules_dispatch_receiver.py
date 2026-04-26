#!/usr/bin/env python3
"""
hercules_dispatch_receiver.py — local Mac HTTP receiver for the Chrome
extension's auto-extracted dispatch blocks.

Listens on http://127.0.0.1:5680/dispatch (POST) and /health (GET).
On valid POST: pipes the text payload through bin/hercules-paste internally,
which writes a JSON dispatch into ~/AMG/hercules-outbox/ — the bridge daemon
ingests it within 30s and Mercury wakes within 1s.

Local-only by design (binds 127.0.0.1, NOT 0.0.0.0). Runs under launchd as
com.amg.hercules-dispatch-receiver. Restarts on failure.

Run:
    hercules_dispatch_receiver.py --port 5680
    hercules_dispatch_receiver.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

HOME = pathlib.Path.home()
OUTBOX = HOME / "AMG" / "hercules-outbox"
LOGFILE = HOME / ".openclaw" / "logs" / "hercules_dispatch_receiver.log"
HERCULES_PASTE = HOME / "titan-harness" / "bin" / "hercules-paste"

ALLOWED_ORIGINS = {
    "https://kimi.moonshot.cn",
    "https://www.kimi.moonshot.cn",
    "https://kimi.com",
    "https://www.kimi.com",
}


def _log(msg: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    sys.stderr.write(line)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line)


def ingest_dispatch(text: str, source: str = "kimi-web-extension") -> dict:
    if not text or len(text) < 20:
        return {"ok": False, "error": "text too short"}
    if not HERCULES_PASTE.exists():
        return {"ok": False, "error": f"hercules-paste missing at {HERCULES_PASTE}"}
    try:
        proc = subprocess.run(
            ["python3", str(HERCULES_PASTE), "--tag", "auto-extracted", "--tag", source],
            input=text, capture_output=True, text=True, timeout=15,
        )
        if proc.returncode != 0:
            return {"ok": False, "error": f"hercules-paste exit {proc.returncode}: {proc.stderr[-300:]}"}
        return {"ok": True, "stdout": proc.stdout.strip()[-500:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "hercules-paste timeout 15s"}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


class ReceiverHandler(BaseHTTPRequestHandler):

    def _cors_headers(self):
        # CORS: allow only Kimi origins for the POST. Browser-preview tooling
        # can't install Chrome extensions, so only real Kimi tabs hit this.
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        else:
            # Allow all in dev; the bind is 127.0.0.1 so external traffic
            # can't reach this anyway.
            self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):  # noqa: N802 — CORS preflight
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "service": "hercules-dispatch-receiver",
                "outbox": str(OUTBOX),
                "ts": datetime.now(tz=timezone.utc).isoformat(),
            }).encode())
        else:
            self.send_response(404)
            self._cors_headers()
            self.end_headers()

    def do_POST(self):  # noqa: N802
        if self.path != "/dispatch":
            self.send_response(404)
            self._cors_headers()
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            raw = self.rfile.read(length)
            payload = json.loads(raw or b"{}")
            text = payload.get("text", "")
            source = payload.get("source", "kimi-web-extension")
        except Exception as e:
            self.send_response(400)
            self._cors_headers()
            self.end_headers()
            self.wfile.write(f'{{"error":"bad json: {e!r}"}}'.encode())
            return
        result = ingest_dispatch(text, source)
        _log(f"POST /dispatch source={source} chars={len(text)} ok={result.get('ok')}")
        self.send_response(200 if result.get("ok") else 422)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def log_message(self, fmt, *args):  # noqa: N802 — silence default stdout
        _log(f"http {self.address_string()} {fmt % args}")


def main() -> int:
    p = argparse.ArgumentParser(description="Local Mac receiver for Hercules dispatches from Kimi web")
    p.add_argument("--port", type=int, default=int(os.environ.get("HERCULES_RECEIVER_PORT", "5680")))
    p.add_argument("--bind", default="127.0.0.1", help="bind address (default 127.0.0.1, local only)")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()

    if args.self_test:
        sample = "🎖️ DISPATCH ORDER\nAgent: Mercury\nTask: smoke test from receiver self-test\nETA: 30s\nProof Required: log_decision tagged self-test"
        result = ingest_dispatch(sample, "self-test")
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    server = HTTPServer((args.bind, args.port), ReceiverHandler)
    _log(f"hercules_dispatch_receiver listening on {args.bind}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log("hercules_dispatch_receiver stopping")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
