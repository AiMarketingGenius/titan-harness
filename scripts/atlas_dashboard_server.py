#!/usr/bin/env python3
"""atlas_dashboard_server.py — Atlas Dashboard MVP (Solon-approved scope, 2026-04-27).

Single-user, local-network only. Four panels, no auth, no styling beyond
Tailwind defaults, no mobile, no animations. Stdlib http.server + vanilla
JS fetch + Tailwind CDN. Reuses today's direct-Supabase + Ollama paths.

Panels (LOCKED — do not extend):
  1. Factory status — pulled from the live factory_status.json gist
  2. Recent decisions — last 20 from op_decisions via direct Supabase REST
  3. Dispatch entry — POST /api/queue-task on MCP server with persona/agent/priority dropdowns
  4. search_kb query — namespace dropdown + query input + raw similarity-scored results

Endpoints:
  GET  /                       serves the HTML
  GET  /api/factory-status     proxies the gist
  GET  /api/recent-decisions   last 20 op_decisions, newest first
  POST /api/dispatch           forwards to MCP /api/queue-task
  POST /api/search-kb          uses the runner's tool_search_kb directly

Run:
  python3 scripts/atlas_dashboard_server.py [--port 8800]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "scripts"))
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))

import hercules_api_runner as hr  # reuses tool_search_kb + _resolve_supabase_key
from mcp_rest_client import queue_task as mcp_queue_task

GIST_URL = (
    "https://gist.githubusercontent.com/AiMarketingGenius/"
    "05608a50c9f47954f3de19c67d581350/raw/factory_status.json"
)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://egoazyasyrhslluossli.supabase.co")

KB_NAMESPACES = [
    "kb:hercules:eom",
    "kb:hercules:doctrine",
    "kb:nestor:lumina-cro",
    "kb:alexander:outbound",
    "kb:alexander:seo-content",
    "kb:alexander:hormozi",
    "kb:alexander:welby",
    "kb:alexander:koray",
    "kb:alexander:reputation",
    "kb:alexander:paid-ads",
]

PERSONAS = ["hercules", "nestor", "alexander", "ops"]
AGENTS = ["alex", "maya", "jordan", "sam", "riley", "nadia", "lumina", "ops",
          "athena", "daedalus", "artisan", "hephaestus", "echo"]
PRIORITIES = ["urgent", "normal", "low"]


# ─── data fetchers ──────────────────────────────────────────────────────────
def fetch_factory_status() -> dict:
    try:
        with urllib.request.urlopen(GIST_URL, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": f"gist fetch failed: {e!r}"}


def fetch_recent_decisions(limit: int = 20) -> list[dict]:
    key = hr._resolve_supabase_key()
    if not key:
        return [{"error": "supabase key unavailable"}]
    url = (f"{SUPABASE_URL.rstrip('/')}/rest/v1/op_decisions"
           f"?select=id,decision_text,project_source,tags,created_at,rationale"
           f"&order=created_at.desc&limit={limit}")
    req = urllib.request.Request(
        url, headers={"apikey": key, "Authorization": f"Bearer {key}",
                      "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        return data if isinstance(data, list) else []
    except Exception as e:
        return [{"error": f"supabase fetch failed: {e!r}"}]


def dispatch_task(payload: dict) -> dict:
    """Forward to MCP /api/queue-task. Returns the {task_id, status} dict."""
    code, body = mcp_queue_task(payload)
    return {"http_code": code, "result": body}


# ─── HTML (single page, Tailwind CDN, vanilla JS) ───────────────────────────
HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Atlas Dashboard — AMG</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif; }
  .panel { border: 1px solid #1f1f1f; border-radius: 8px; background: #131313; }
  .panel-header { border-bottom: 1px solid #1f1f1f; padding: 10px 16px; font-weight: 600; }
  .scroll-y { max-height: 380px; overflow-y: auto; }
  pre { white-space: pre-wrap; word-wrap: break-word; }
  input, select, textarea, button { font: inherit; }
</style>
</head>
<body class="bg-neutral-950 text-neutral-200 p-6 min-h-screen">
  <header class="flex items-center gap-3 mb-6">
    <span class="w-3 h-3 rounded-full bg-amber-400 shadow-[0_0_8px_#fbbf24]"></span>
    <h1 class="text-xl font-semibold">Atlas Dashboard</h1>
    <span class="text-neutral-500 text-sm">— AMG factory + memory</span>
    <button id="refresh-all" class="ml-auto text-xs border border-neutral-800 px-3 py-1.5 rounded hover:border-amber-400 hover:text-amber-400">Refresh</button>
  </header>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">

    <!-- 1. Factory Status -->
    <section class="panel">
      <div class="panel-header flex items-center">
        <span>Factory Status</span>
        <span id="factory-ts" class="ml-auto text-xs text-neutral-500"></span>
      </div>
      <div class="p-4 scroll-y" id="factory-body">
        <div class="text-neutral-500">Loading…</div>
      </div>
    </section>

    <!-- 2. Recent Decisions -->
    <section class="panel">
      <div class="panel-header">Recent Decisions (last 20)</div>
      <div class="p-4 scroll-y" id="decisions-body">
        <div class="text-neutral-500">Loading…</div>
      </div>
    </section>

    <!-- 3. Dispatch Entry -->
    <section class="panel">
      <div class="panel-header">Dispatch Task</div>
      <div class="p-4 space-y-3">
        <div class="grid grid-cols-3 gap-2">
          <select id="d-persona" class="bg-neutral-900 border border-neutral-800 rounded px-2 py-1.5 text-sm">
            <option value="">queued_by…</option>
          </select>
          <select id="d-agent" class="bg-neutral-900 border border-neutral-800 rounded px-2 py-1.5 text-sm">
            <option value="">agent…</option>
          </select>
          <select id="d-priority" class="bg-neutral-900 border border-neutral-800 rounded px-2 py-1.5 text-sm">
          </select>
        </div>
        <input id="d-objective" placeholder="objective (1 sentence)…" class="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-sm" />
        <textarea id="d-instructions" placeholder="instructions (numbered steps)…" rows="3" class="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-sm"></textarea>
        <input id="d-acceptance" placeholder="acceptance criteria…" class="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-sm" />
        <input id="d-tags" placeholder='tags (comma-sep, e.g. agent:athena,owner:hercules)' class="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-sm" />
        <div class="flex gap-2 items-center">
          <label class="text-xs text-neutral-500">approval:</label>
          <select id="d-approval" class="bg-neutral-900 border border-neutral-800 rounded px-2 py-1 text-sm">
            <option value="pre_approved" selected>pre_approved</option>
            <option value="pending">pending</option>
          </select>
          <button id="dispatch-btn" class="ml-auto bg-amber-400 text-neutral-950 font-semibold px-4 py-1.5 rounded text-sm hover:bg-amber-300">Dispatch</button>
        </div>
        <div id="dispatch-result" class="text-xs text-neutral-400 mt-2 font-mono"></div>
      </div>
    </section>

    <!-- 4. search_kb -->
    <section class="panel">
      <div class="panel-header">Search KB</div>
      <div class="p-4 space-y-3">
        <div class="grid grid-cols-2 gap-2">
          <select id="kb-ns" class="bg-neutral-900 border border-neutral-800 rounded px-2 py-1.5 text-sm">
          </select>
          <select id="kb-count" class="bg-neutral-900 border border-neutral-800 rounded px-2 py-1.5 text-sm">
            <option value="5">5 results</option>
            <option value="10">10 results</option>
          </select>
        </div>
        <div class="flex gap-2">
          <input id="kb-query" placeholder="query…" class="flex-1 bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-sm" />
          <button id="kb-btn" class="bg-amber-400 text-neutral-950 font-semibold px-4 py-1.5 rounded text-sm hover:bg-amber-300">Search</button>
        </div>
        <div id="kb-result" class="scroll-y space-y-2 mt-2"></div>
      </div>
    </section>

  </div>

<script>
const PERSONAS = __PERSONAS__;
const AGENTS = __AGENTS__;
const PRIORITIES = __PRIORITIES__;
const KB_NAMESPACES = __KB_NAMESPACES__;

function fillSelect(id, opts, includeBlank) {
  const el = document.getElementById(id);
  if (includeBlank) el.innerHTML = '<option value="">' + includeBlank + '</option>';
  else el.innerHTML = '';
  for (const o of opts) {
    const opt = document.createElement('option');
    opt.value = o; opt.textContent = o;
    el.appendChild(opt);
  }
}
fillSelect('d-persona', PERSONAS, 'queued_by…');
fillSelect('d-agent', AGENTS, 'agent…');
fillSelect('d-priority', PRIORITIES);
document.getElementById('d-priority').value = 'normal';
fillSelect('kb-ns', KB_NAMESPACES);

async function loadFactory() {
  const body = document.getElementById('factory-body');
  body.innerHTML = '<div class="text-neutral-500">Loading…</div>';
  try {
    const r = await fetch('/api/factory-status');
    const j = await r.json();
    if (j.error) { body.innerHTML = '<div class="text-red-400 text-sm">' + j.error + '</div>'; return; }
    document.getElementById('factory-ts').textContent = (j.ts || '').slice(0,19) + 'Z';
    const sections = [];
    if (j.queue) {
      sections.push('<div class="font-mono text-xs"><div class="text-neutral-500 mb-1">queue:</div>' +
        Object.entries(j.queue).map(([k,v]) => '  ' + k + ': ' + v).join('<br>') + '</div>');
    }
    if (j.agents) {
      sections.push('<div class="font-mono text-xs mt-3"><div class="text-neutral-500 mb-1">agents (' + Object.keys(j.agents).length + '):</div>' +
        Object.entries(j.agents).map(([name, info]) => {
          const alive = info && info.alive ? '🟢' : '🔴';
          const pid = info && info.pid ? ' pid=' + info.pid : '';
          return '  ' + alive + ' ' + name + pid;
        }).join('<br>') + '</div>');
    }
    if (j.sprint) {
      sections.push('<div class="font-mono text-xs mt-3"><div class="text-neutral-500 mb-1">sprint:</div>' +
        Object.entries(j.sprint).slice(0,5).map(([k,v]) => '  ' + k + ': ' + JSON.stringify(v).slice(0,80)).join('<br>') + '</div>');
    }
    body.innerHTML = sections.join('') || '<pre class="text-xs">' + JSON.stringify(j, null, 2).slice(0, 2000) + '</pre>';
  } catch(e) { body.innerHTML = '<div class="text-red-400 text-sm">' + e + '</div>'; }
}

async function loadDecisions() {
  const body = document.getElementById('decisions-body');
  body.innerHTML = '<div class="text-neutral-500">Loading…</div>';
  try {
    const r = await fetch('/api/recent-decisions');
    const data = await r.json();
    if (!Array.isArray(data) || data.length === 0) {
      body.innerHTML = '<div class="text-neutral-500 text-sm">no decisions</div>';
      return;
    }
    body.innerHTML = data.map(d => {
      const ts = (d.created_at || '').slice(0,19);
      const tags = (d.tags || []).slice(0,4).join(', ');
      const text = (d.decision_text || '').slice(0,300);
      return '<div class="border-b border-neutral-800 py-2 text-sm">' +
        '<div class="text-neutral-500 text-xs">' + ts + ' · [' + (d.project_source||'?') + '] ' + tags + '</div>' +
        '<div class="mt-1">' + text.replace(/</g,'&lt;') + '</div></div>';
    }).join('');
  } catch(e) { body.innerHTML = '<div class="text-red-400 text-sm">' + e + '</div>'; }
}

document.getElementById('dispatch-btn').addEventListener('click', async () => {
  const persona = document.getElementById('d-persona').value;
  const agent = document.getElementById('d-agent').value;
  const priority = document.getElementById('d-priority').value;
  const objective = document.getElementById('d-objective').value.trim();
  const instructions = document.getElementById('d-instructions').value.trim();
  const acceptance = document.getElementById('d-acceptance').value.trim();
  const tagsRaw = document.getElementById('d-tags').value.trim();
  const approval = document.getElementById('d-approval').value;

  if (!objective || !instructions || !acceptance) {
    document.getElementById('dispatch-result').innerHTML = '<span class="text-red-400">objective + instructions + acceptance all required</span>';
    return;
  }
  const tags = tagsRaw ? tagsRaw.split(',').map(t => t.trim()).filter(Boolean) : [];
  const payload = {
    objective, instructions, acceptance_criteria: acceptance,
    priority, tags, approval,
    project_id: 'EOM',
    queued_by: persona || 'atlas-ui',
    agent: agent || 'ops',
  };
  document.getElementById('dispatch-result').textContent = 'dispatching…';
  try {
    const r = await fetch('/api/dispatch', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    const j = await r.json();
    document.getElementById('dispatch-result').textContent = JSON.stringify(j, null, 2);
    loadDecisions();
  } catch(e) {
    document.getElementById('dispatch-result').innerHTML = '<span class="text-red-400">' + e + '</span>';
  }
});

document.getElementById('kb-btn').addEventListener('click', async () => {
  const namespace = document.getElementById('kb-ns').value;
  const query = document.getElementById('kb-query').value.trim();
  const count = parseInt(document.getElementById('kb-count').value, 10);
  const result = document.getElementById('kb-result');
  if (!query) { result.innerHTML = '<div class="text-red-400 text-sm">query required</div>'; return; }
  result.innerHTML = '<div class="text-neutral-500 text-sm">searching…</div>';
  try {
    const r = await fetch('/api/search-kb', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ namespace, query, count }) });
    const j = await r.json();
    if (j.error) { result.innerHTML = '<div class="text-red-400 text-sm">' + (j.error || JSON.stringify(j)).slice(0,300) + '</div>'; return; }
    const rows = (j.results || []);
    if (rows.length === 0) { result.innerHTML = '<div class="text-neutral-500 text-sm">no matches</div>'; return; }
    result.innerHTML = rows.map((m, i) => {
      const sim = m.similarity != null ? (m.similarity * 100).toFixed(1) + '%' : '?';
      const summary = (m.summary || m.content || '').slice(0,400).replace(/</g,'&lt;');
      return '<div class="border border-neutral-800 rounded p-3 text-sm">' +
        '<div class="text-xs text-neutral-500">' + (i+1) + '. ' + namespace + ' · sim ' + sim + '</div>' +
        '<div class="mt-1 font-mono text-xs whitespace-pre-wrap">' + summary + '</div></div>';
    }).join('');
  } catch(e) {
    result.innerHTML = '<div class="text-red-400 text-sm">' + e + '</div>';
  }
});

document.getElementById('refresh-all').addEventListener('click', () => { loadFactory(); loadDecisions(); });
loadFactory(); loadDecisions();
setInterval(loadFactory, 30000);  // auto-refresh factory every 30s
</script>
</body>
</html>
"""


def _render_html() -> str:
    return (HTML
            .replace("__PERSONAS__", json.dumps(PERSONAS))
            .replace("__AGENTS__", json.dumps(AGENTS))
            .replace("__PRIORITIES__", json.dumps(PRIORITIES))
            .replace("__KB_NAMESPACES__", json.dumps(KB_NAMESPACES)))


# ─── HTTP handler ───────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args, **kwargs): pass

    def _json(self, code: int, payload):
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self._html(_render_html())
            return
        if path == "/api/factory-status":
            self._json(200, fetch_factory_status())
            return
        if path == "/api/recent-decisions":
            self._json(200, fetch_recent_decisions())
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except Exception:
            body = {}

        if path == "/api/dispatch":
            try:
                self._json(200, dispatch_task(body))
            except Exception as e:
                self._json(500, {"error": repr(e)})
            return

        if path == "/api/search-kb":
            namespace = (body.get("namespace") or "").strip()
            query = (body.get("query") or "").strip()
            count = int(body.get("count", 5) or 5)
            if not namespace or not query:
                self._json(400, {"error": "namespace + query required"})
                return
            # Derive persona from namespace; ACL enforced inside tool_search_kb.
            parts = namespace.split(":", 2)
            persona = parts[1] if len(parts) >= 3 else "hercules"
            hr._CURRENT_PERSONA = persona
            try:
                r = hr.tool_search_kb({"namespace": namespace, "query": query, "count": count})
                self._json(200, r)
            except Exception as e:
                self._json(500, {"error": repr(e)})
            return

        self._json(404, {"error": "not found"})


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8800)
    p.add_argument("--host", default="127.0.0.1")
    args = p.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[atlas-dashboard] http://{args.host}:{args.port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
