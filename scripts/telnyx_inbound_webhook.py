#!/usr/bin/env python3
"""
telnyx_inbound_webhook.py — receives inbound SMS from Telnyx, writes to MCP.

Deployed on the VPS as a Caddy-fronted Python service. Route:
    POST https://n8n.aimarketinggenius.io/webhook/telnyx-inbound

Telnyx webhook payload (v2):
{
  "data": {
    "event_type": "message.received",
    "payload": {
      "from": {"phone_number": "+1..."},
      "to":   [{"phone_number": "+1..."}],
      "text": "OK Class 3",
      "received_at": "2026-04-26T15:00:00Z",
      "id": "..."
    }
  }
}

When a message arrives:
  1. Verify the signature (Telnyx-Signature-ed25519 header) against the
     public key from Telnyx dashboard.
  2. Extract from + text + timestamp.
  3. Match the from-number against TELNYX_SOLON_NUMBER. If mismatch, log
     `telnyx-stranger-sms` decision and ignore (don't route to Hercules).
  4. Write a `solon-reply` decision to MCP via /api/decisions with the text,
     timestamp, and tags ["solon-reply", "sms-inbound"].
  5. Surface to Hercules's outbox so the next Hercules session sees the
     reply: write `~/AMG/hercules-outbox/solon_reply_<TS>.json` with the
     text wrapped as a Hercules-bound message dispatch.

Run as Flask/Fastify? Stdlib http.server is enough for a single endpoint.

Usage:
    telnyx_inbound_webhook.py --port 5681              # daemon
    telnyx_inbound_webhook.py --self-test              # smoke test
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))
try:
    from mcp_rest_client import log_decision as mcp_log_decision  # noqa: E402
except Exception:
    mcp_log_decision = None

LOGFILE = HOME / ".openclaw" / "logs" / "telnyx_inbound.log"
OUTBOX = HOME / "AMG" / "hercules-outbox"
SOLON_NUMBER = os.environ.get("TELNYX_SOLON_NUMBER", "")


def _log(msg: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    sys.stderr.write(line)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line)


def normalize_e164(num: str) -> str:
    return "".join(c for c in (num or "") if c.isdigit() or c == "+")


def handle_message(payload: dict) -> dict:
    p = payload.get("data", {}).get("payload", {})
    from_num = normalize_e164((p.get("from") or {}).get("phone_number", ""))
    text = p.get("text", "").strip()
    received_at = p.get("received_at") or datetime.now(tz=timezone.utc).isoformat()
    msg_id = p.get("id", "noid")
    if not text:
        return {"ok": False, "reason": "empty text"}
    is_solon = bool(SOLON_NUMBER) and from_num == normalize_e164(SOLON_NUMBER)
    tags = ["sms-inbound", f"from:{from_num}", f"telnyx-msg-id:{msg_id}"]
    if is_solon:
        tags.insert(0, "solon-reply")
    else:
        tags.insert(0, "telnyx-stranger-sms")
    if mcp_log_decision:
        try:
            mcp_log_decision(
                text=f"SMS inbound from {from_num}: {text[:200]}",
                rationale=(
                    f"Telnyx webhook received message_id={msg_id} at {received_at}. "
                    f"Recognized as Solon: {is_solon}. Full text: {text}"
                ),
                tags=tags,
                project_source="titan",
            )
        except Exception as e:
            _log(f"MCP log_decision failed: {e!r}")
    if is_solon:
        OUTBOX.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = OUTBOX / f"solon_reply_{stamp}.json"
        body = {
            "objective": f"Solon SMS reply received: {text[:120]}",
            "instructions": (
                "1. Read Solon's full SMS text in the context field. "
                "2. Treat as a directive — interpret intent, queue follow-up "
                "dispatches if needed. "
                "3. Acknowledge in the next reply (briefly, per brevity rule)."
            ),
            "acceptance_criteria": "Hercules acknowledges the SMS in his next session response and queues any follow-up actions.",
            "agent_assigned": "atlas_hercules",
            "priority": "P1",
            "tags": ["solon-sms", "hercules-acknowledge-required"],
            "context": text,
            "project_id": "EOM",
            "source": "telnyx-inbound",
        }
        out.write_text(json.dumps(body, indent=2))
        _log(f"WROTE outbox file for Solon SMS: {out.name}")
    return {"ok": True, "from": from_num, "is_solon": is_solon, "logged_to_mcp": bool(mcp_log_decision)}


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        try:
            raw = self.rfile.read(length)
            payload = json.loads(raw or b"{}")
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f'{{"error":"bad json: {e!r}"}}'.encode())
            return
        # NOTE: Telnyx-Signature-ed25519 verification is a P1 follow-up;
        # for v1 we accept any POST from the configured Caddy route.
        try:
            event_type = payload.get("data", {}).get("event_type", "")
            if event_type != "message.received":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(f'{{"ok":true,"ignored":"event_type={event_type}"}}'.encode())
                return
            result = handle_message(payload)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        except Exception as e:
            _log(f"handler error: {e!r}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f'{{"error":"{e!r}"}}'.encode())

    def do_GET(self):  # noqa: N802 — health check
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"telnyx-inbound"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):  # noqa: N802 — silence stdout
        _log(f"http {self.address_string()} {fmt % args}")


def main() -> int:
    p = argparse.ArgumentParser(description="Telnyx inbound webhook")
    p.add_argument("--port", type=int, default=int(os.environ.get("TELNYX_INBOUND_PORT", "5681")))
    p.add_argument("--bind", default="0.0.0.0")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()

    if args.self_test:
        sample = {
            "data": {
                "event_type": "message.received",
                "payload": {
                    "from": {"phone_number": SOLON_NUMBER or "+15551234567"},
                    "to": [{"phone_number": "+18005551212"}],
                    "text": "TEST MSG from telnyx_inbound self-test",
                    "received_at": datetime.now(tz=timezone.utc).isoformat(),
                    "id": "self-test-id",
                },
            }
        }
        print(json.dumps(handle_message(sample), indent=2))
        return 0

    server = HTTPServer((args.bind, args.port), WebhookHandler)
    _log(f"telnyx_inbound_webhook listening on {args.bind}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log("telnyx_inbound_webhook stopping")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
