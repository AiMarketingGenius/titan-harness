# AMG Chatbot Widget — aimarketinggenius.io embedded Alex

**Status:** STAGING build (text-only); voice + orb layer deferred to next phase per Solon's 9-task directive
**CT:** CT-0417-01 partial
**Ships at:** eventual deployment to aimarketinggenius.io via `<script src="…">` embed

---

## What this is

A self-contained embeddable chatbot that connects any web page to Alex (AMG's Business Coach) via the project-backed agent pipeline:

- **Widget** (`widget.js`) — 8KB IIFE, zero-dep, loads Montserrat from Google Fonts, injects FAB + panel
- **Backend** — POSTs to `/api/alex/message` on atlas-api
- **Backend loads Alex KB** via the new `agent_context_loader` MCP tool (cacheable prefix pattern)
- **Rate limit** — 20 messages per session (RATE_LIMIT_MSGS), enforced client-side
- **Trade-secret clean** per `plans/agents/kb/titan/01_trade_secrets.md`; zero underlying-vendor mentions in widget or backend response

## Design

- **Brand tokens:** navy `#0B2572`, gold `#d4a627`, Montserrat (Google Fonts)
- **Accessibility:** ARIA roles (dialog, log, button), aria-expanded on FAB, aria-live="polite" on message log, focus management on open/close, ESC closes
- **Responsive:** mobile (≤560px) full-width; desktop fixed right-24px
- **Prefers-reduced-motion** respected

## Architecture

```
Subscriber site (aimarketinggenius.io)
  │
  │  <script src="widget.js"></script>
  ▼
widget.js (browser, IIFE)
  │
  │  POST /api/alex/message
  ▼
atlas-api service on primary production VPS
  │
  │  invoke agent_context_loader(agent='alex', client_id=null, query=user_text)
  ▼
MCP tool returns:
  - cacheable_prefix: Alex system prompt + full KB (12.6K tokens, cached)
  - query_tail: client_facts (empty for anonymous) + memory hits (up to 5)
  │
  │  wrap in Atlas messages call with cache_control: ephemeral on prefix
  ▼
Response streamed back → JSON → widget renders
```

## What's NOT in this staging build

- **Voice orb** — WebGL-shader orb w/ amplitude-reactive pulses, Atlas TTS integration, barge-in support — staged for next phase
- **Backend `/api/alex/message` endpoint** — stub spec documented below; actual integration into atlas_api.py is next session's work
- **Deployment to aimarketinggenius.io** — site infrastructure live-location unknown; ship happens after Solon confirms deployment target

## Backend endpoint spec (to be implemented in atlas_api.py)

```python
@app.post("/api/alex/message")
async def api_alex_message(request: Request) -> JSONResponse:
    body = await request.json()
    text = (body.get("text") or "").strip()
    session_id = (body.get("session_id") or "default").strip()
    client_id = body.get("client_id")  # optional; None for anonymous
    if not text:
        raise HTTPException(400, "text required")
    if len(text) > 500:
        raise HTTPException(400, "text too long (max 500)")

    # Load Alex KB + client context via MCP agent_context_loader
    ctx = await mcp_call("agent_context_loader", {
        "agent_name": "alex",
        "client_id": client_id,
        "query": text,
        "include_memory": True,
    })
    prefix = ctx["cacheable_prefix"]
    tail = ctx["query_tail"]

    # Build Atlas call with prompt caching on prefix
    system = [
        {"type": "text", "text": prefix["system_prompt"]},
        {"type": "text", "text": prefix["kb_bundle"], "cache_control": {"type": "ephemeral"}},
    ]
    user_content = f"Client facts:\n{tail['client_facts_block']}\n\nRecent context:\n{tail['memory_block']}\n\nUser query:\n{text}"

    history = _ALEX_SESSIONS.setdefault(session_id, [])
    msgs = history[-8:] + [{"role": "user", "content": user_content}]

    reply = await atlas_call(system=system, messages=msgs, max_tokens=400)

    # Trade-secret scan
    reply = sanitize_trade_secrets(reply)

    history.append({"role": "user", "content": user_content})
    history.append({"role": "assistant", "content": reply})

    # Save transcript to AMG data layer for lead nurture
    await supabase_insert("chatbot_transcripts", {
        "session_id": session_id, "user_text": text, "reply": reply,
        "client_id": client_id, "ts": datetime.now(UTC),
    })

    return JSONResponse({"reply": reply, "session_id": session_id})
```

## Files in this bundle

- `widget.js` — 8KB browser IIFE
- `demo.html` — local test page (served via any static host for dev preview)
- `README.md` — this file

## Deployment steps (when ready)

1. Implement `/api/alex/message` on atlas-api per spec above
2. Add AMG data layer `chatbot_transcripts` table (id, session_id, client_id, user_text, reply, ts, user_agent, ip)
3. Copy `widget.js` to AMG CDN (or static bundle on primary production VPS)
4. Add `<script src="…/widget.js"></script>` to aimarketinggenius.io template
5. Chrome MCP e2e test: 10 conversations across pricing / service / Chamber-program / objection categories
6. Grader ≥ 9.3 before going public

## Trade-secret compliance

- Widget UI never mentions AI vendor by name; "AMG," "Alex," "Atlas" allowed
- Backend response passes through `sanitize_trade_secrets()` before return
- Transcripts in AMG data layer are stored for lead-nurture + training signal; full CAN-SPAM/GDPR flow per subscriber opt-in
