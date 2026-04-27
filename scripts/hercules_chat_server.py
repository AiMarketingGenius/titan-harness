#!/usr/bin/env python3
"""hercules_chat_server.py — clean Mac-app chat UI for Hercules / Nestor /
Alexander. Stdlib-only (no Flask), runs a localhost HTTP server, serves a
modern single-page chat UI, calls hercules_api_runner.run_turn() per message.

Launched by /Applications/{Hercules,Nestor,Alexander}.app — the AppleScript
opens this server then pops a Chrome --app window. No terminal visible.

Endpoints:
  GET  /                serves the chat HTML
  GET  /api/state       current persona + session id + last 20 turns
  POST /api/chat        body {"message":"..."} → {"text":"...","cost_usd":...}
  POST /api/powerdown   logs RESTART_HANDOFF + closes server
  POST /api/awake       force re-hydrate, returns fresh brief

Run:
    python3 hercules_chat_server.py --persona hercules --port 8765
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sqlite3
import sys
import threading
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "scripts"))
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))

import hercules_api_runner as hr  # noqa: E402

# Singleton state for this server process
_PERSONA: str = "hercules"
_SESSION_ID: str = ""
_HYDRATED_BRIEF: str | None = None


PERSONA_THEMES = {
    "hercules": {"accent": "#d4af37", "label": "Hercules", "title": "Chief of Operations"},
    "nestor": {"accent": "#3b82f6", "label": "Nestor", "title": "Product + UX"},
    "alexander": {"accent": "#a855f7", "label": "Alexander", "title": "Brand + Voice"},
}


def _load_recent_turns(persona: str, session_id: str, limit: int = 30) -> list[dict]:
    """Pull rendered user/assistant turns for the chat history. Skips system
    messages (hydration context) and tool-call rounds."""
    conn = sqlite3.connect(hr._convo_db(persona))
    rows = conn.execute(
        "SELECT ts, role, content FROM messages "
        "WHERE session_id=? AND role IN ('user','assistant') "
        "  AND content IS NOT NULL AND content != '' "
        "  AND tool_calls_json IS NULL "
        "ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    out = []
    for ts, role, content in rows[-limit:]:
        if role == "user" and content.startswith("[HYDRATION_BRIEF]"):
            # Hide the synthetic hydration prompt from the UI; the assistant's
            # response to it is the visible "first message".
            continue
        out.append({"ts": ts, "role": role, "content": content})
    return out


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{label} — {title}</title>
<style>
  :root {{
    --accent: {accent};
    --bg: #0a0a0a;
    --panel: #131313;
    --border: #1f1f1f;
    --text: #e5e5e5;
    --text-soft: #888;
    --user-bubble: #1a1a1a;
    --asst-bubble: #161616;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0; padding: 0; height: 100%; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
    font-size: 15px; line-height: 1.55;
  }}
  body {{ display: flex; flex-direction: column; }}
  header {{
    padding: 14px 22px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 12px;
    background: var(--panel);
  }}
  .dot {{
    width: 10px; height: 10px; border-radius: 50%; background: var(--accent);
    box-shadow: 0 0 8px var(--accent);
  }}
  .title {{ font-weight: 600; letter-spacing: -0.01em; }}
  .subtitle {{ color: var(--text-soft); font-size: 12px; margin-left: 8px; }}
  .actions {{ margin-left: auto; display: flex; gap: 8px; }}
  button {{
    background: transparent; color: var(--text-soft); border: 1px solid var(--border);
    padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px;
    font-family: inherit;
  }}
  button:hover {{ border-color: var(--accent); color: var(--accent); }}
  #chat {{
    flex: 1; overflow-y: auto; padding: 24px 22px; display: flex; flex-direction: column; gap: 16px;
  }}
  .msg {{
    max-width: 78%; padding: 12px 16px; border-radius: 12px;
    white-space: pre-wrap; word-wrap: break-word;
  }}
  .msg.user {{
    align-self: flex-end; background: var(--user-bubble); border: 1px solid var(--border);
  }}
  .msg.asst {{
    align-self: flex-start; background: var(--asst-bubble); border: 1px solid var(--border);
  }}
  .msg.brief {{
    border-left: 2px solid var(--accent); background: transparent;
    color: var(--text-soft); font-style: italic; max-width: 100%;
  }}
  .msg.brief::before {{
    content: "Resume brief — "; color: var(--accent); font-style: normal;
    font-weight: 600;
  }}
  .role {{
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em;
    color: var(--text-soft); margin-bottom: 4px;
  }}
  .role.you {{ color: var(--accent); }}
  footer {{
    border-top: 1px solid var(--border); padding: 14px 22px; background: var(--panel);
  }}
  .input-row {{ display: flex; gap: 10px; align-items: flex-end; }}
  textarea {{
    flex: 1; resize: none; background: var(--user-bubble); color: var(--text);
    border: 1px solid var(--border); border-radius: 10px; padding: 11px 14px;
    font: inherit; min-height: 42px; max-height: 200px; outline: none;
  }}
  textarea:focus {{ border-color: var(--accent); }}
  .send {{
    background: var(--accent); color: #0a0a0a; border: none; padding: 11px 18px;
    border-radius: 10px; font-weight: 600; cursor: pointer; min-width: 80px;
  }}
  .send:disabled {{ opacity: 0.5; cursor: not-allowed; }}
  .status {{ color: var(--text-soft); font-size: 11px; margin-top: 6px; }}
  .typing {{ color: var(--text-soft); font-style: italic; }}
</style>
</head>
<body>
<header>
  <span class="dot"></span>
  <span class="title">{label}</span>
  <span class="subtitle">{title}</span>
  <div class="actions">
    <button id="awake">Awake / Re-hydrate</button>
    <button id="powerdown">Power Off</button>
  </div>
</header>
<div id="chat"></div>
<footer>
  <div class="input-row">
    <textarea id="input" placeholder="Message {label}…  (⌘+Enter to send)" rows="1"></textarea>
    <button class="send" id="send">Send</button>
  </div>
  <div class="status" id="status">Session: <span id="sid">…</span></div>
</footer>
<script>
const PERSONA = {persona_json};
const ACCENT = {accent_json};

const chat = document.getElementById('chat');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const sid = document.getElementById('sid');
const statusEl = document.getElementById('status');

function appendMsg(role, text, cls) {{
  const el = document.createElement('div');
  el.className = 'msg ' + (cls || (role === 'user' ? 'user' : 'asst'));
  const roleEl = document.createElement('div');
  roleEl.className = 'role' + (role === 'user' ? ' you' : '');
  roleEl.textContent = role === 'user' ? 'You' : (role === 'brief' ? 'Brief' : PERSONA);
  el.appendChild(roleEl);
  const body = document.createElement('div');
  body.textContent = text;
  el.appendChild(body);
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
  return el;
}}

async function loadState() {{
  const r = await fetch('/api/state');
  const j = await r.json();
  sid.textContent = j.session_id || 'new';
  if (j.brief) {{
    appendMsg('brief', j.brief, 'msg brief');
  }}
  for (const t of (j.history || [])) {{
    appendMsg(t.role === 'user' ? 'user' : 'asst', t.content);
  }}
}}

input.addEventListener('keydown', (e) => {{
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {{
    e.preventDefault();
    send();
  }}
}});

input.addEventListener('input', () => {{
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 200) + 'px';
}});

sendBtn.addEventListener('click', send);

async function send() {{
  const text = input.value.trim();
  if (!text) return;
  appendMsg('user', text);
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;
  const typing = appendMsg('asst', '…', 'msg asst typing');
  try {{
    const r = await fetch('/api/chat', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{message: text}})
    }});
    const j = await r.json();
    typing.remove();
    appendMsg('asst', j.text || '(no response)');
    if (j.cost_usd != null) {{
      statusEl.textContent = 'Session: ' + (j.session_id || sid.textContent) + '  ·  cost ' + j.cost_usd.toFixed(4);
    }}
  }} catch (e) {{
    typing.remove();
    appendMsg('asst', '(error: ' + e + ')');
  }}
  sendBtn.disabled = false;
  input.focus();
}}

document.getElementById('powerdown').addEventListener('click', async () => {{
  if (!confirm('Power off ' + PERSONA + '? This will log a RESTART_HANDOFF to MCP and close the chat.')) return;
  appendMsg('asst', '(powering down…)', 'msg brief');
  await fetch('/api/powerdown', {{method: 'POST'}});
  setTimeout(() => window.close(), 1500);
}});

document.getElementById('awake').addEventListener('click', async () => {{
  appendMsg('asst', '(re-hydrating from MCP…)', 'msg brief');
  const r = await fetch('/api/awake', {{method: 'POST'}});
  const j = await r.json();
  if (j.brief) appendMsg('brief', j.brief, 'msg brief');
}});

loadState();
input.focus();
</script>
</body>
</html>
"""


class ChatHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default access logs; we have our own logging via hr._log.
        pass

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            theme = PERSONA_THEMES.get(_PERSONA, PERSONA_THEMES["hercules"])
            html = HTML_TEMPLATE.format(
                label=theme["label"], title=theme["title"], accent=theme["accent"],
                persona_json=json.dumps(theme["label"]),
                accent_json=json.dumps(theme["accent"]),
            )
            self._send_html(html)
            return
        if path == "/api/state":
            history = _load_recent_turns(_PERSONA, _SESSION_ID, limit=30)
            self._send_json(200, {
                "persona": _PERSONA,
                "session_id": _SESSION_ID,
                "history": history,
                "brief": _HYDRATED_BRIEF,
            })
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        body_bytes = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(body_bytes or b"{}")
        except Exception:
            body = {}

        if path == "/api/chat":
            msg = (body.get("message") or "").strip()
            if not msg:
                self._send_json(400, {"error": "empty message"})
                return
            try:
                result = hr.run_turn(_PERSONA, msg, session_id=_SESSION_ID, verbose=False)
                self._send_json(200, {
                    "text": result.get("text", ""),
                    "cost_usd": result.get("cost_usd", 0),
                    "session_id": result.get("session_id"),
                })
            except Exception as e:
                self._send_json(500, {"error": repr(e)})
            return

        if path == "/api/powerdown":
            try:
                r = hr.powerdown_persona(_PERSONA, _SESSION_ID, verbose=False)
                self._send_json(200, r)
                # Schedule shutdown after response.
                threading.Timer(0.5, lambda: os._exit(0)).start()
            except Exception as e:
                self._send_json(500, {"error": repr(e)})
            return

        if path == "/api/awake":
            try:
                r = hr.force_rehydrate(_PERSONA, _SESSION_ID, verbose=False)
                self._send_json(200, r)
            except Exception as e:
                self._send_json(500, {"error": repr(e)})
            return

        self._send_json(404, {"error": "not found"})


def main() -> int:
    global _PERSONA, _SESSION_ID, _HYDRATED_BRIEF
    p = argparse.ArgumentParser()
    p.add_argument("--persona", required=True, choices=list(PERSONA_THEMES.keys()))
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--no-hydrate", action="store_true")
    args = p.parse_args()

    _PERSONA = args.persona
    _SESSION_ID = hr._current_session(args.persona)

    # Cold-start hydration before the user opens the page.
    if not args.no_hydrate:
        try:
            hyd = hr.cold_start_hydrate(args.persona, _SESSION_ID, verbose=False)
            if not hyd.get("skipped") and hyd.get("brief"):
                _HYDRATED_BRIEF = hyd["brief"]
        except Exception as e:
            print(f"[hydrate] failed (non-fatal): {e!r}", file=sys.stderr)

    server = ThreadingHTTPServer((args.host, args.port), ChatHandler)
    print(f"[hercules-chat] {args.persona} listening on http://{args.host}:{args.port}",
          file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
