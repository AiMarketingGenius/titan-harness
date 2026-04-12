#!/usr/bin/env python3
"""
lib/titan_bot.py
MP-3 §1 — Titan Bot Slack DM/Thread Handler

Listens for Slack Events API messages sent to titan-bot via DM or @mention,
classifies intent per MP-3 §1, dispatches to the correct handler, and posts
the structured reply back to Slack.

Runs as a lightweight Flask-like HTTP server (stdlib only) that receives
Slack Events API POST requests.

Usage:
  python lib/titan_bot.py  # starts on port 3847
  TITAN_BOT_PORT=3847 python lib/titan_bot.py

Environment:
  SLACK_BOT_TOKEN — xoxb-... token with chat:write, im:history, im:read
  SLACK_SIGNING_SECRET — for request verification (optional in dev)
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY — for MCP logging
"""

from __future__ import annotations

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.intent_classifier import classify
from lib.intent_handlers import dispatch


SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
BOT_USER_ID = os.environ.get("TITAN_BOT_USER_ID", "")
PORT = int(os.environ.get("TITAN_BOT_PORT", "3847"))

# Track which threads have pending approval items (in-memory for now)
_approval_threads: set[str] = set()


def _post_slack_message(channel: str, payload: dict, thread_ts: str | None = None) -> None:
    """Post a message to Slack using chat.postMessage."""
    body = {
        "channel": channel,
        **payload,
    }
    if thread_ts:
        body["thread_ts"] = thread_ts

    data = json.dumps(body).encode("utf-8")
    req = Request("https://slack.com/api/chat.postMessage", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {SLACK_BOT_TOKEN}")
    try:
        with urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            if not result.get("ok"):
                print(f"[titan_bot] Slack error: {result.get('error')}", file=sys.stderr)
    except Exception as exc:
        print(f"[titan_bot] Slack post failed: {exc!r}", file=sys.stderr)


def handle_message_event(event: dict) -> None:
    """Process a single Slack message event."""
    # Ignore bot messages (including our own)
    if event.get("bot_id") or event.get("subtype"):
        return

    text = event.get("text", "").strip()
    channel = event.get("channel", "")
    thread_ts = event.get("thread_ts")
    user = event.get("user", "")

    if not text or not channel:
        return

    # Strip bot mention if present
    if BOT_USER_ID:
        text = text.replace(f"<@{BOT_USER_ID}>", "").strip()

    # Determine thread context for approval routing
    is_thread = thread_ts is not None
    has_approval_item = thread_ts in _approval_threads if thread_ts else False

    # Classify
    classified = classify(text, is_thread_reply=is_thread, thread_has_approval_item=has_approval_item)

    print(f"[titan_bot] {user}: '{text}' → {classified.intent.value} "
          f"(conf={classified.confidence}, params={classified.parameters})")

    # Dispatch to handler
    reply_payload = dispatch(classified)

    # Post reply (in thread if message was threaded)
    reply_thread = thread_ts or event.get("ts")
    _post_slack_message(channel, reply_payload, thread_ts=reply_thread)


class TitanBotHandler(BaseHTTPRequestHandler):
    """HTTP handler for Slack Events API."""

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        # Handle Slack URL verification challenge
        if data.get("type") == "url_verification":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"challenge": data.get("challenge", "")}).encode())
            return

        # Handle event callbacks
        if data.get("type") == "event_callback":
            event = data.get("event", {})
            if event.get("type") == "message":
                handle_message_event(event)

        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress default access logs
        pass


def register_approval_thread(thread_ts: str) -> None:
    """Mark a thread as containing a pending approval item.

    Called by approval packet senders so that subsequent "approve that"
    messages in the same thread are correctly classified.
    """
    _approval_threads.add(thread_ts)


def main():
    print(f"[titan_bot] Starting on port {PORT}...")
    server = HTTPServer(("0.0.0.0", PORT), TitanBotHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[titan_bot] Shutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
