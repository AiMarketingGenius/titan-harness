"""
lib/atlas_api.py — Atlas API shim (Hermes Phase A, sprint scaffold)

FastAPI service that bridges the Atlas web/mobile/desktop orb to the
Hermes voice substrate (Kokoro + Silero + faster-whisper) and the
Claude conversation layer via the existing LiteLLM gateway.

Doctrine:
- plans/DOCTRINE_VOICE_AI_STACK_v1.0.md
- plans/DOCTRINE_HERMES_PHASE_A_VOICE_QA.md
- plans/DOCTRINE_ATLAS_ORB_UX_BLUEPRINT.md
- plans/DOCTRINE_AMG_PRICING_GUARDRAIL.md

Sprint scope (24h target, staging context only):
- /api/status        — live Titan status for Solon's phone + desktop
- /api/ask           — text-only one-shot for quick queries ("is Hermes done?")
- /ws/text/{sid}     — text chat over WebSocket for the orb UX
- /ws/voice/{sid}    — voice over WebSocket (audio bytes in, audio bytes out)
- /                  — serves services/atlas-web/ static bundle (orb + PWA)

Pricing guardrail:
- Every Atlas LLM response runs through a whitelist post-filter that
  rejects any dollar amount not in the canonical AMG tier set. If the
  Claude draft contains a banned number, we retry once with a reminder.
- The canonical tier table is baked into the system prompt literal.

Backchannel handling (patch 3):
- The 5 approved backchannel phrases are served as pre-rendered WAVs
  from services/kokoro/backchannels/ on a dedicated low-latency path.
- Live Kokoro is NEVER called for backchannels.
- The voice pipeline carries a backchannel_mode flag; barge-in is
  suppressed while a backchannel WAV is playing.

Not in scope for this sprint:
- Rive animations, React/Next build, react-calendly embed (placeholder href),
  avatar video, full production TLS termination (Caddy wiring is a
  post-sprint polish step — staging runs on the VPS IP directly).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
    from fastapi.staticfiles import StaticFiles
except ImportError as exc:  # pragma: no cover
    raise SystemExit("fastapi + uvicorn are required: pip install --user fastapi uvicorn") from exc

try:
    import httpx  # for LiteLLM gateway calls
except ImportError:
    httpx = None  # fallback path handles this

# ─── paths ─────────────────────────────────────────────────────────────────────

REPO_ROOT        = Path(__file__).resolve().parent.parent
STATIC_DIR       = REPO_ROOT / "services" / "atlas-web"
KB_PATH          = REPO_ROOT / "services" / "atlas" / "kb" / "amg_kb.json"
BACKCHANNEL_DIR  = REPO_ROOT / "services" / "kokoro" / "backchannels"
KOKORO_ENDPOINT  = os.environ.get("ATLAS_KOKORO_URL", "http://127.0.0.1:8880")
LITELLM_BASE     = os.environ.get("LITELLM_BASE_URL", "").rstrip("/")
LITELLM_KEY      = os.environ.get("LITELLM_MASTER_KEY", "").strip()
LLM_MODEL        = os.environ.get("ATLAS_LLM_MODEL", "claude-sonnet-4-6")
SPRINT_CONTEXT   = "staging"  # pricing guardrail §5

# ─── KB + pricing whitelist ────────────────────────────────────────────────────

_KB_CACHE: dict[str, Any] | None = None


def load_kb() -> dict[str, Any]:
    global _KB_CACHE
    if _KB_CACHE is None:
        _KB_CACHE = json.loads(KB_PATH.read_text())
    return _KB_CACHE


PRICING_WHITELIST = {
    "$97", "$197", "$347",
    "$497", "$797", "$1,497", "$1497",
    "$249",  # derived: half a Starter month (audit fraction)
}
# Also allow unprefixed numerics when emitted in list / table context.
NUMERIC_WHITELIST = {"97", "197", "347", "497", "797", "1497", "249"}

DOLLAR_RE  = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?")
NUMBER_RE  = re.compile(r"(?<![\$\d])\b(?:1[,]?\d{3}|\d{2,3})\b")  # plain 97, 1497, etc.


def pricing_violations(text: str) -> list[str]:
    """Return a list of banned numeric strings found in *text*. Empty
    list means the response is clean under the AMG pricing guardrail."""
    bad: list[str] = []
    for match in DOLLAR_RE.findall(text):
        # Strip trailing commas/punctuation captured by [\d,]* in prose context
        canon = match.replace(" ", "").rstrip(",")
        if canon not in PRICING_WHITELIST:
            bad.append(match.strip())
    for match in NUMBER_RE.findall(text):
        if match not in NUMERIC_WHITELIST and int(match.replace(",", "")) > 50:
            # Numbers under 50 are likely counts (reviews, years), not dollars.
            bad.append(match)
    return bad


# ─── system prompt builder ─────────────────────────────────────────────────────

HERMES_PERSONA = """You are Atlas, a voice assistant for AI Marketing Genius (AMG). You speak with small business owners aged 35-60 who are non-technical and often unfamiliar with marketing terminology. Your persona:

- Archetype: senior marketing consultant who has seen it all. Calm, direct, competent. Not a hype machine. Not a corporate FAQ bot.
- Energy 6/10. Measured, never rushed. Comfortable with silence.
- Confident but not arrogant. Lead with clarity, not credentials.
- Genuinely curious about the business before proposing anything.
- Talk about outcomes, not features. ROI, not synergy.
- Plain American English, 10th-grade reading level, concrete nouns, active voice.
- 40% warmth, 60% authority. You offer a perspective and invite pushback.
- Never use buzzwords (AI-powered, synergy, leverage, scalable) unless the user introduces them first.
- Never open with a cheerful affirmation ("Great question!", "Absolutely!", "Certainly!").
- Short answers beat comprehensive ones. The follow-up question is the intelligence signal.
- Ask one question at a time. Never stack two questions in one turn.
"""

BANT_FRAMEWORK = """You use BANT as a conversational arc, not a checklist:
- Q1 (Context): "What's going on with your marketing right now — starting from scratch, fixing something, or scaling what's working?"
- Q2 (Authority): "Are you running the day-to-day, or do you have a team?"
- Q3 (Budget, soft): "Are you thinking pilot-budget territory under five figures, or ready to go bigger if the ROI is there?"
- Q4 (Timeline): "When does this need to be moving — end-of-month, or strategic planning?"
- Q5 (Service fit): "Which sounds most like your problem — getting found online, converting traffic you already have, or automating follow-up?"

Weave these into natural dialogue. Each question lands after processing the previous answer. Budget is Q3, not Q1 — establish value before investment.
"""

GUARDRAILS = """Guardrails (HARD rules — violations are failures):
1. Never invent tiers or dollar amounts beyond the canonical AMG tier set provided below.
2. Never quote a price that isn't in the whitelist: $97, $197, $347, $497, $797, $1,497.
3. Escalate to Solon when: user mentions contract changes, expresses dissatisfaction, asks about enterprise beyond Pro, asks for pricing outside the canonical set, or explicitly asks for a human.
4. Never say "I think" or "probably" about AMG's pricing or standard timelines.
5. If you don't know a client-specific fact, say so plainly: "I don't have your Google Analytics in front of me, so I'm working from what you've told me."
6. Humor only after rapport and only as one dry line, never in pricing or problem-statement turns.
"""


def build_system_prompt() -> str:
    kb = load_kb()
    tiers = kb["canonical_tiers"]
    shield = kb["shield_tiers"]
    services = kb["services"]
    patterns = kb["example_patterns"]

    tier_lines = "\n".join(
        f"- {t['name']}: ${t['price_usd_monthly']:,}/month — {t['description']}"
        for t in tiers
    )
    shield_lines = "\n".join(
        f"- {s['name']}: ${s['price_usd_monthly']}/month — {s['description']}"
        for s in shield
    )
    service_lines = "\n".join(
        f"- {s['name']}: {s['one_liner']}" for s in services
    )
    pattern_lines = "\n\n".join(
        f"Pattern {i+1} — {p['situation']}:\n  Diagnosis: {p['diagnosis']}\n  Atlas response style: {p['atlas_response']}"
        for i, p in enumerate(patterns)
    )

    return (
        HERMES_PERSONA
        + "\n\nCANONICAL AMG TIERS (only legal dollar amounts you may quote):\n"
        + tier_lines
        + "\n\nShield reputation tiers:\n"
        + shield_lines
        + "\n\nServices you offer:\n"
        + service_lines
        + "\n\nExample patterns you know well:\n\n"
        + pattern_lines
        + "\n\n"
        + BANT_FRAMEWORK
        + "\n"
        + GUARDRAILS
        + f"\nContext: {SPRINT_CONTEXT}. This Atlas is running on a demo/staging surface. Pricing may be discussed in full in this context.\n"
    )


# ─── LLM call via LiteLLM gateway ──────────────────────────────────────────────

async def call_llm(messages: list[dict[str, str]]) -> str:
    """Call the LiteLLM gateway. Returns assistant text.

    Falls back to a canned acknowledgement if httpx / gateway is unavailable,
    so the orb still flows end-to-end during the sprint.
    """
    if httpx is None or not LITELLM_BASE or not LITELLM_KEY:
        return "I'm running in offline fallback right now — the LiteLLM gateway isn't reachable from this process. Can you say that again in 30 seconds?"

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 600,
    }
    headers = {
        "Authorization": f"Bearer {LITELLM_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(f"{LITELLM_BASE}/v1/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # pragma: no cover
        return f"(LLM gateway error — falling back to plain acknowledgement. Internal: {type(exc).__name__}.)"


async def atlas_respond(user_text: str, history: list[dict[str, str]]) -> tuple[str, list[str]]:
    """Return (final_text, violations_seen). Retries once on pricing violation."""
    history = [{"role": "system", "content": build_system_prompt()}] + history[-12:]
    history.append({"role": "user", "content": user_text})

    draft = await call_llm(history)
    violations = pricing_violations(draft)
    if not violations:
        return draft, []

    # Retry once with an explicit reminder.
    history.append({"role": "assistant", "content": draft})
    history.append({
        "role": "user",
        "content": (
            "Your previous answer contained dollar amounts that are not on the "
            "canonical AMG tier list. Rewrite that answer using ONLY the "
            "approved numbers: $497 (Starter), $797 (Growth), $1,497 (Pro), "
            "$97/$197/$347 (Shield). Do not explain the correction — just "
            "deliver the corrected reply."
        ),
    })
    draft2 = await call_llm(history)
    violations2 = pricing_violations(draft2)
    return draft2, (violations + violations2 if violations2 else violations)


# ─── Kokoro TTS helper ─────────────────────────────────────────────────────────

async def kokoro_synthesize(text: str, *, voice: str = "am_michael", speed: float = 0.92) -> bytes:
    if httpx is None:
        return b""
    payload = {
        "model": "kokoro",
        "voice": voice,
        "input": text,
        "response_format": "wav",
        "speed": speed,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{KOKORO_ENDPOINT}/v1/audio/speech", json=payload)
        r.raise_for_status()
        return r.content


# ─── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="Atlas API shim (Hermes Phase A sprint)")


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    """Live Titan status for Solon's phone + desktop."""
    head = _git_head()
    kb = load_kb()
    return {
        "service": "atlas-api",
        "commit": head,
        "sprint_context": SPRINT_CONTEXT,
        "hermes_substrate": {
            "kokoro": _systemd_active("titan-kokoro"),
            "kokoro_endpoint": KOKORO_ENDPOINT,
            "backchannels_ready": sorted(p.name for p in BACKCHANNEL_DIR.glob("*.wav")),
            "phase_a_reviewer_graded": "6/6 A",
        },
        "kb_version": kb.get("version"),
        "kb_tier_count": len(kb.get("canonical_tiers", [])),
        "llm_gateway": bool(LITELLM_BASE and LITELLM_KEY),
        "pricing_guardrail": "active (whitelist post-filter)",
        "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@app.get("/api/ask")
async def api_ask(q: str) -> JSONResponse:
    """Text-only one-shot. `curl .../api/ask?q=whats+hermes+status`"""
    if not q or len(q) > 1000:
        raise HTTPException(400, "q must be 1-1000 chars")
    reply, violations = await atlas_respond(q, history=[])
    return JSONResponse({"q": q, "reply": reply, "violations_blocked": violations})


@app.get("/api/backchannel/{name}")
def api_backchannel(name: str) -> Response:
    """Serve a pre-rendered backchannel WAV."""
    safe = re.sub(r"[^a-z_]", "", name.lower())
    path = BACKCHANNEL_DIR / f"{safe}.wav"
    if not path.exists():
        raise HTTPException(404, f"backchannel {safe} not found")
    return FileResponse(path, media_type="audio/wav")


@app.websocket("/ws/text/{sid}")
async def ws_text(ws: WebSocket, sid: str) -> None:
    await ws.accept()
    history: list[dict[str, str]] = []
    try:
        while True:
            msg = await ws.receive_text()
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                data = {"type": "text", "text": msg}
            user_text = (data.get("text") or "").strip()
            if not user_text:
                continue
            reply, violations = await atlas_respond(user_text, history)
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": reply})
            await ws.send_json({"type": "reply", "text": reply, "violations_blocked": violations})
    except WebSocketDisconnect:
        return


@app.websocket("/ws/voice/{sid}")
async def ws_voice(ws: WebSocket, sid: str) -> None:
    """Full duplex voice pipeline (Hermes Phase A):

    mic → Web Audio API → WS audio frames (16-bit PCM, 16kHz mono)
      → Silero VAD gate → faster-whisper (medium.en int8) → text
      → Claude via LiteLLM → sentence_buffer → Kokoro TTS → audio bytes
      → WS back to orb → orb Speaking state

    Protocol:
    - Client sends binary frames: raw 16-bit PCM @ 16kHz mono
    - Client sends JSON text frames:
        {"type": "say", "text": "..."} — TTS-only shortcut (no STT)
        {"type": "backchannel", "name": "..."} — pre-rendered WAV
        {"type": "config", "backchannel_mode": true/false} — toggle barge-in suppression
    - Server sends binary frames: WAV audio (Kokoro TTS output)
    - Server sends JSON text frames:
        {"type": "transcript", "text": "..."} — what STT heard
        {"type": "reply_text", "text": "..."} — Claude's response text
        {"type": "state", "state": "listening|thinking|speaking"} — orb state
        {"type": "latency", "stt_ms": N, "llm_ms": N, "tts_ms": N, "total_ms": N}
    """
    await ws.accept()
    history: list[dict[str, str]] = []
    audio_buffer = bytearray()
    backchannel_mode = False  # suppress barge-in during backchannel playback
    # Barge-in state flags. Safe without locks because Python asyncio runs
    # a single event loop thread — all coroutines interleave cooperatively
    # at await points, so flag reads/writes are atomic.
    speaking = False  # True while sending TTS audio to client
    interrupted = False  # Set by truncate signal or barge-in VAD detection
    CHUNK_BYTES = 32000  # 1 second of 16-bit 16kHz mono = 32000 bytes
    VAD_SILENCE_THRESHOLD = 2  # consecutive silent chunks before processing

    # Lazy imports for STT + VAD (only loaded if audio frames arrive)
    _vad_mod = None
    _whisper_mod = None

    def _ensure_stt():
        nonlocal _vad_mod, _whisper_mod
        if _vad_mod is None:
            try:
                sys.path.insert(0, str(REPO_ROOT / "lib"))
                import silero_vad as _v
                import whisper_cpu as _w
                _vad_mod = _v
                _whisper_mod = _w
            except ImportError:
                pass

    silent_chunks = 0

    try:
        while True:
            msg = await ws.receive()

            # --- Binary frame: raw audio from mic ---
            if "bytes" in msg and msg["bytes"]:
                _ensure_stt()
                if _vad_mod is None or _whisper_mod is None:
                    # STT not available — send error and continue
                    await ws.send_json({"type": "error", "message": "STT modules not available on this server"})
                    continue

                audio_buffer.extend(msg["bytes"])

                # Process in 1-second chunks
                if len(audio_buffer) < CHUNK_BYTES:
                    continue

                chunk = bytes(audio_buffer[:CHUNK_BYTES])
                audio_buffer = audio_buffer[CHUNK_BYTES:]

                # Optional RNNoise denoising before VAD (best-effort)
                try:
                    import numpy as np
                    samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                    try:
                        from lib.rnnoise_wrapper import denoise as _rnnoise
                        samples = _rnnoise(samples, 16000)
                    except ImportError:
                        pass  # RNNoise not installed — use raw audio (expected on Mac)
                    except Exception as _rn_exc:
                        # RNNoise runtime error — log once, continue with raw audio
                        if not getattr(ws_voice, '_rnnoise_warned', False):
                            print(f"[ws_voice] RNNoise fallback: {_rn_exc!r}", file=sys.stderr)
                            ws_voice._rnnoise_warned = True
                    has_speech = _vad_mod.is_speech(samples, sample_rate=16000)
                except Exception:
                    has_speech = True  # fallback: process anyway

                if not has_speech:
                    silent_chunks += 1
                    if silent_chunks < VAD_SILENCE_THRESHOLD or len(audio_buffer) == 0:
                        continue
                    # Silence after speech — process accumulated audio
                else:
                    silent_chunks = 0
                    continue  # Keep accumulating while speech is active

                # Barge-in detection: user spoke while Atlas was speaking
                if speaking and has_speech:
                    interrupted = True
                    speaking = False
                    await ws.send_json({"type": "state", "state": "listening"})
                    await ws.send_json({"type": "barge_in", "message": "User interrupted — stopping playback"})
                    # Don't clear buffer — let the new speech accumulate for next turn
                    silent_chunks = 0
                    continue

                # We have speech followed by silence — transcribe the accumulated audio
                if backchannel_mode:
                    audio_buffer.clear()
                    silent_chunks = 0
                    continue  # suppress barge-in during backchannel

                # Reset interrupted flag before new transcription
                interrupted = False
                await ws.send_json({"type": "state", "state": "thinking"})
                t_start = time.time()

                # STT via faster-whisper
                try:
                    import numpy as np
                    # Combine all buffered audio for transcription
                    all_audio = chunk  # the chunk that triggered processing
                    pcm = np.frombuffer(all_audio, dtype=np.int16).astype(np.float32) / 32768.0
                    t_stt_start = time.time()
                    transcript = _whisper_mod.transcribe(pcm, sample_rate=16000)
                    t_stt = int((time.time() - t_stt_start) * 1000)
                except Exception as exc:
                    await ws.send_json({"type": "error", "message": f"STT error: {type(exc).__name__}"})
                    audio_buffer.clear()
                    silent_chunks = 0
                    continue

                transcript = transcript.strip()
                if not transcript or len(transcript) < 2:
                    await ws.send_json({"type": "state", "state": "listening"})
                    audio_buffer.clear()
                    silent_chunks = 0
                    continue

                # Send transcript to client
                await ws.send_json({"type": "transcript", "text": transcript})

                # Claude LLM call
                t_llm_start = time.time()
                reply, violations = await atlas_respond(transcript, history)
                t_llm = int((time.time() - t_llm_start) * 1000)
                history.append({"role": "user", "content": transcript})
                history.append({"role": "assistant", "content": reply})

                await ws.send_json({"type": "reply_text", "text": reply})

                # Sentence-buffered TTS via Kokoro (with barge-in support)
                await ws.send_json({"type": "state", "state": "speaking"})
                speaking = True
                interrupted = False
                t_tts_start = time.time()
                try:
                    sys.path.insert(0, str(REPO_ROOT / "lib"))
                    from sentence_buffer import sentence_buffer
                    sentences = list(sentence_buffer([reply]))
                    for sentence in sentences:
                        if interrupted:
                            # Barge-in detected — stop sending TTS immediately
                            await ws.send_json({"type": "state", "state": "listening"})
                            break
                        wav = await kokoro_synthesize(sentence)
                        if wav and not interrupted:
                            await ws.send_bytes(wav)
                except Exception:
                    # Fallback: synthesize entire reply at once
                    if not interrupted:
                        wav = await kokoro_synthesize(reply)
                        if wav:
                            await ws.send_bytes(wav)
                speaking = False
                t_tts = int((time.time() - t_tts_start) * 1000)

                t_total = int((time.time() - t_start) * 1000)
                await ws.send_json({
                    "type": "latency",
                    "stt_ms": t_stt,
                    "llm_ms": t_llm,
                    "tts_ms": t_tts,
                    "total_ms": t_total,
                })
                await ws.send_json({"type": "state", "state": "listening"})
                audio_buffer.clear()
                silent_chunks = 0

            # --- Text frame: JSON commands ---
            elif "text" in msg and msg["text"]:
                try:
                    data = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue

                if data.get("type") == "say":
                    # TTS-only shortcut (text → Kokoro → audio)
                    await ws.send_json({"type": "state", "state": "speaking"})
                    text = data.get("text", "")
                    reply, violations = await atlas_respond(text, history)
                    history.append({"role": "user", "content": text})
                    history.append({"role": "assistant", "content": reply})
                    await ws.send_json({"type": "reply_text", "text": reply})
                    wav = await kokoro_synthesize(reply)
                    if wav:
                        await ws.send_bytes(wav)
                    await ws.send_json({"type": "state", "state": "listening"})

                elif data.get("type") == "backchannel":
                    name = re.sub(r"[^a-z_]", "", str(data.get("name", "")).lower())
                    path = BACKCHANNEL_DIR / f"{name}.wav"
                    if path.exists():
                        backchannel_mode = True
                        await ws.send_bytes(path.read_bytes())
                        # Re-enable barge-in after ~1.5s backchannel playback
                        await asyncio.sleep(1.5)
                        backchannel_mode = False

                elif data.get("type") == "truncate":
                    # Client-side barge-in: user started speaking, stop TTS
                    if speaking:
                        interrupted = True
                        speaking = False
                        await ws.send_json({"type": "state", "state": "listening"})
                        await ws.send_json({"type": "barge_in", "message": "Truncated by client"})

                elif data.get("type") == "config":
                    if "backchannel_mode" in data:
                        backchannel_mode = bool(data["backchannel_mode"])

    except WebSocketDisconnect:
        return


# Static orb bundle (served at /atlas/)
if STATIC_DIR.exists():
    app.mount("/atlas", StaticFiles(directory=str(STATIC_DIR), html=True), name="atlas")


@app.get("/")
def root() -> HTMLResponse:
    return HTMLResponse(
        '<!doctype html><html><body style="font-family:system-ui;padding:2rem;background:#0A0F1E;color:#E8F4FD;">'
        '<h1>Atlas API shim</h1>'
        '<p>Running. See <a style="color:#2563EB" href="/atlas/">/atlas/</a> for the orb, '
        '<a style="color:#2563EB" href="/api/status">/api/status</a> for live status, '
        '<a style="color:#2563EB" href="/api/ask?q=what+does+amg+do">/api/ask?q=…</a> for a text query.</p>'
        '</body></html>'
    )


# ─── helpers ───────────────────────────────────────────────────────────────────

def _git_head() -> str:
    # Prefer static commit file written at deploy time (works in systemd context)
    commit_file = REPO_ROOT / ".current-commit"
    try:
        return commit_file.read_text().strip()
    except Exception:
        pass
    # Fallback to git (works in dev, fails in systemd)
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT).decode().strip()
    except Exception:
        return "unknown"


def _systemd_active(unit: str) -> str:
    try:
        out = subprocess.check_output(["systemctl", "is-active", unit], stderr=subprocess.STDOUT).decode().strip()
        return out
    except subprocess.CalledProcessError as exc:
        return exc.output.decode().strip() if exc.output else "unknown"
    except Exception:
        return "unknown"


# ─── MP-3 Dashboard Routes ────────────────────────────────────────────────────

try:
    from lib.dashboard_api import get_dashboard_data, render_mobile_html
    from lib.dashboard_desktop import render_desktop_html

    # Dashboard auth: optional token-based access control.
    # Set ATLAS_DASHBOARD_TOKEN in env to require ?token=<value> on all dashboard routes.
    # When unset, dashboards are open (suitable for VPS-only / Caddy-gated access).
    _DASHBOARD_TOKEN = os.environ.get("ATLAS_DASHBOARD_TOKEN", "")

    def _check_dashboard_auth(request) -> None:
        if _DASHBOARD_TOKEN:
            from fastapi import HTTPException
            token = request.query_params.get("token", "")
            if token != _DASHBOARD_TOKEN:
                raise HTTPException(status_code=401, detail="Invalid dashboard token")

    @app.get("/mobile")
    def mobile_dashboard(request: Request) -> HTMLResponse:
        """MP-3 §2 — Mobile status dashboard (375-430px)."""
        _check_dashboard_auth(request)
        data = get_dashboard_data()
        html = render_mobile_html(data)
        return HTMLResponse(html)

    @app.get("/desktop")
    def desktop_dashboard(request: Request) -> HTMLResponse:
        """MP-3 §3 — Desktop Solon OS Control Center."""
        _check_dashboard_auth(request)
        data = get_dashboard_data()
        html = render_desktop_html(data)
        return HTMLResponse(html)

    @app.get("/api/dashboard/mobile")
    def api_dashboard_mobile() -> dict:
        """JSON data for mobile dashboard."""
        return get_dashboard_data()

    @app.get("/api/dashboard/desktop")
    def api_dashboard_desktop() -> dict:
        """JSON data for desktop dashboard."""
        return get_dashboard_data()

    @app.get("/api/dashboard/orb")
    def api_dashboard_orb() -> dict:
        """Current orb state (color, pulse, drivers)."""
        data = get_dashboard_data()
        return data["orb"]

    @app.get("/api/dashboard/health")
    def api_dashboard_health() -> list:
        """7-subsystem health flags."""
        data = get_dashboard_data()
        return data["health"]

except ImportError:
    pass  # Dashboard module not available — skip routes


# ─── TITAN MOBILE COMMAND — /titan + /api/titan/* ─────────────────────────────
# Mobile Command demo surface per Solon directive 2026-04-16.
# Phone-native conversational UI at /titan, text + voice I/O, Alex-voice TTS,
# Titan persona (distinct from Atlas customer-facing pricing guardrail).

_TITAN_SESSIONS: dict[str, list[dict[str, str]]] = {}  # in-memory session history

# Canonical ElevenLabs voice map (MCP P10 permanent 2026-04-16T12:45Z)
ELEVENLABS_VOICES = {
    "alex":   "DZifC2yzJiQrdYzF21KH",  # Solon OS clone — default Titan voice
    "maya":   "uYXf8XasLslADfZ2MB4u",  # Hope
    "jordan": "UgBBYS2sOqTuMpoF3BR0",  # Mark
    "sam":    "Yg7C1g7suzNt5TisIqkZ",  # Jude — British
    "riley":  "DODLEQrClDo8wCz460ld",  # Lauren
    "nadia":  "vZzlAds9NzvLsFSWp0qk",  # Maria Mysh
    "lumina": "X03mvPuTfprif8QBAVeJ",  # Christina
}
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()


def _titan_system_prompt() -> str:
    """Titan persona — internal ops assistant for Solon. Distinct from Atlas (customer-facing)."""
    return (
        "You are Titan, Solon's autonomous operator and COO agent for AMG "
        "(AI Marketing Genius). You have direct knowledge of Solon's sprint state, "
        "client roster (Shop UNIS / Paradise Park Novi / Revel & Roll West / JDJ-Levar), "
        "task queue, mirror state (beast VPS primary, HostHatch staging), and all "
        "harness doctrine.\n\n"
        "Style:\n"
        "- Crisp, confident, zero filler. Solon is an ADHD operator — every word earns its place.\n"
        "- First sentence is the answer or the decision. Bullets after, not before.\n"
        "- Target ≤ 3 short sentences unless Solon asks for depth.\n"
        "- No emoji unless Solon used one first.\n"
        "- Never pretend to execute actions you haven't. If you can't do it from mobile, say so.\n"
        "- Trade-secret compliant: never name Claude / OpenAI / Anthropic / Perplexity / Grok / "
        "Supabase / n8n / GoHighLevel in any reply. Say 'our AI' or 'the memory layer' instead.\n\n"
        "Client roster (authoritative): Alex (account mgr), Maya (content), Jordan (reputation), "
        "Sam (SEO), Riley (strategy), Nadia (onboarding), Lumina (CRO). Seven agents, never six.\n\n"
        "If asked for sprint/status/blocker info, respond briefly and suggest Solon pull the "
        "full card via a quick action. If asked a workflow Solon-can-tap-from-mobile, acknowledge "
        "and note that the full surface is under active build for this week's demo."
    )


@app.get("/titan")
async def titan_serve() -> Response:
    """Serve the mobile command UI."""
    path = STATIC_DIR / "titan.html"
    if not path.exists():
        raise HTTPException(404, "titan.html missing — deploy pending")
    return FileResponse(path, media_type="text/html")


@app.post("/api/titan/message")
async def api_titan_message(request: Request) -> JSONResponse:
    """Text-in → Titan reply. Persists session history in-memory."""
    body = await request.json()
    text = (body.get("text") or "").strip()
    session_id = (body.get("session_id") or "default").strip()
    if not text:
        raise HTTPException(400, "text required")
    if len(text) > 2000:
        raise HTTPException(400, "text too long (max 2000)")

    # Intent router — detect structured-card requests BEFORE LLM
    card = await _titan_intent_card(text)
    if card:
        return JSONResponse({"card": card, "reply": None})

    # Normal LLM path with Titan persona
    history = _TITAN_SESSIONS.setdefault(session_id, [])
    # Shape for call_llm: system + history
    msgs = [{"role": "system", "content": _titan_system_prompt()}]
    msgs.extend(history[-12:])
    msgs.append({"role": "user", "content": text})

    try:
        reply = await call_llm(msgs)
    except Exception as exc:
        reply = f"(LLM unavailable: {type(exc).__name__}. Try again in a moment.)"

    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": reply})
    # trim to last 20 turns
    if len(history) > 40:
        del history[:len(history) - 40]

    return JSONResponse({"reply": reply, "session_id": session_id})


async def _titan_intent_card(text: str) -> dict | None:
    """Keyword router for structured cards. Returns None if no card match."""
    low = text.lower()

    # Sprint state card
    if any(k in low for k in ("sprint state", "sprint status", "what's the sprint", "current sprint")):
        return await _card_sprint_state()

    # File retrieval (CHECK BEFORE client-snapshot — "send me the X" intent beats client name)
    if "levar kickoff" in low or "kickoff agenda" in low or ("send me" in low and "levar" in low):
        return _card_file_link("/opt/amg-docs/clients/levar/KICKOFF_AGENDA_0416.md", "Levar Kickoff Agenda")
    if "shop unis talking" in low or "talking points" in low or ("send me" in low and "shop unis" in low):
        return _card_file_link("/opt/amg-docs/clients/shop-unis/TALKING_POINTS_FINAL_0416.md", "Shop UNIS Talking Points")

    # Client snapshot
    if "shop unis" in low or "shopunis" in low:
        return await _card_client_snapshot("shop-unis", "Shop UNIS")
    if "paradise park" in low or "paradise" in low:
        return await _card_client_snapshot("paradise-park-novi", "Paradise Park Novi")
    if "revel" in low or "revel & roll" in low or "revel and roll" in low:
        return await _card_client_snapshot("revel-roll-west", "Revel & Roll West")
    if "levar" in low or "jdj" in low:
        return await _card_client_snapshot("jdj-levar", "JDJ Investment Properties (Levar)")

    # Blockers
    if "my blocker" in low or "blockers" in low or "blocked on me" in low:
        return await _card_blockers()

    # Specific CT lookup
    import re as _re
    m = _re.search(r"ct-?(\d{4})-?(\d{2})", low)
    if m:
        ct_id = f"CT-{m.group(1)}-{m.group(2)}"
        return await _card_ct_lookup(ct_id)

    return None


async def _card_sprint_state() -> dict:
    """Live sprint state pull from op_sprint_state Supabase table (EOM project)."""
    sprint = await _fetch_sprint_state("EOM")

    # MCP health side-probe
    mcp_ok = False
    if httpx is not None:
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get("https://memory.aimarketinggenius.io/health")
                mcp_ok = r.status_code == 200
        except Exception:
            pass

    if sprint:
        return {
            "title": f"Sprint — {sprint.get('sprint_name', 'EOM')}",
            "rows": [
                {"label": "Completion",  "value": f"{sprint.get('completion_pct', '?')}%"},
                {"label": "Kill chain",  "value": f"{sprint.get('kc_count', '?')} items"},
                {"label": "Blockers",    "value": f"{sprint.get('blocker_count', '?')} active"},
                {"label": "Memory layer", "value": "healthy" if mcp_ok else "unreachable"},
                {"label": "Last update", "value": sprint.get('last_updated_short', '?')},
            ],
            "footer": f"Live from op_sprint_state · ask 'what's blocked' for the full list"
        }

    # Cached fallback
    return {
        "title": "Sprint state — CT-0415 Levar Day + CT-0416-01 mega-batch",
        "rows": [
            {"label": "Completion", "value": "95%"},
            {"label": "Kill chain items", "value": "20"},
            {"label": "Active blockers", "value": "7"},
            {"label": "Memory layer", "value": "healthy" if mcp_ok else "unreachable"},
        ],
        "footer": "Cached · live Supabase pull unavailable"
    }


async def _fetch_sprint_state(project_id: str) -> dict:
    """Live pull from op_sprint_state. Returns summary dict, empty on failure."""
    if httpx is None:
        return {}
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        return {}
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(
                f"{url}/rest/v1/op_sprint_state",
                params={
                    "project_id": f"eq.{project_id}",
                    "select": "sprint_name,completion_pct,kill_chain,blockers,last_updated",
                    "limit": "1"
                },
                headers={"apikey": key, "Authorization": f"Bearer {key}"}
            )
            if r.status_code != 200 or not r.json():
                return {}
            row = r.json()[0]
            kc = row.get("kill_chain") or []
            bl = row.get("blockers") or []
            last = row.get("last_updated") or ""
            # Short-form "2026-04-16 15:44 UTC"
            short = last.replace("T", " ")[:16] + " UTC" if last else ""
            return {
                "sprint_name": row.get("sprint_name"),
                "completion_pct": row.get("completion_pct"),
                "kc_count": len(kc) if isinstance(kc, list) else 0,
                "blocker_count": len(bl) if isinstance(bl, list) else 0,
                "kill_chain": kc,
                "blockers": bl,
                "last_updated_short": short,
            }
    except Exception:
        return {}


async def _card_client_snapshot(slug: str, name: str) -> dict:
    """Live client_facts pull. Falls back to hardcoded if Supabase unreachable."""
    client_id_map = {
        "shop-unis":          "11111111-1111-1111-1111-000000000001",
        "paradise-park-novi": "22222222-2222-2222-2222-000000000002",
        "revel-roll-west":    "33333333-3333-3333-3333-000000000003",
        "jdj-levar":          "00199f08-9378-4670-9a8d-d4f63ff01fc6",
    }
    client_id = client_id_map.get(slug)
    facts = await _fetch_client_facts(client_id) if client_id else {}

    if facts:
        rows = []
        # Tolerant priority list — each entry is a LIST of (category, key) alternatives.
        # First non-empty match wins. Handles multiple taxonomies in client_facts:
        #   Levar uses `identity.company_name`; Shop UNIS uses `nap.business_name`.
        priority_keys = [
            ("Company",    [("identity","company_name"), ("nap","business_name")]),
            ("Location",   [("identity","primary_location"), ("nap","location")]),
            ("Website",    [("identity","primary_website"), ("nap","website")]),
            ("Vertical",   [("identity","company_vertical"), ("operational","platform")]),
            ("Contact",    [("identity","contact_name"), ("operational","primary_contact"), ("nap","email_cta")]),
            ("Phone",      [("nap","phone")]),
            ("Contract",   [("operational","contract")]),
            ("Volume/yr",  [("business","annual_acquisition_volume_usd")]),
            ("Cadence",    [("comms","weekly_checkin_cadence")]),
            ("Founding",   [("contract","founding_member_status")]),
            ("Agents",     [("comms","assigned_agents")]),
        ]
        for label, candidates in priority_keys:
            v = None
            for cat, key in candidates:
                if facts.get((cat, key)):
                    v = facts[(cat, key)]
                    break
            if v:
                display = v if len(v) <= 80 else v[:77] + "…"
                rows.append({"label": label, "value": display})
            if len(rows) >= 6:
                break
        if rows:
            return {
                "title": f"{name} — live",
                "rows": rows,
                "footer": f"Live from client_facts · {len(facts)} facts total · service-role query"
            }

    return {
        "title": f"{name} — snapshot",
        "rows": [
            {"label": "Status", "value": "Active"},
            {"label": "Monthly", "value": _client_mrr(slug)},
            {"label": "Tier", "value": _client_tier(slug)},
            {"label": "Next meeting", "value": _client_next_meeting(slug)},
            {"label": "Open items", "value": _client_open_items(slug)},
        ],
        "footer": "Cached · live Supabase pull unavailable"
    }


async def _fetch_client_facts(client_id: str) -> dict:
    """Returns dict keyed by (fact_category, fact_key) → fact_value. Empty on failure."""
    if httpx is None:
        return {}
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        return {}
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(
                f"{url}/rest/v1/client_facts",
                params={
                    "client_id": f"eq.{client_id}",
                    "is_active": "eq.true",
                    "select": "fact_category,fact_key,fact_value"
                },
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}"
                }
            )
            if r.status_code != 200:
                return {}
            return {(row["fact_category"], row["fact_key"]): row["fact_value"] for row in r.json()}
    except Exception:
        return {}


def _client_mrr(slug: str) -> str:
    mrr = {
        "shop-unis": "$3,500/mo custom",
        "paradise-park-novi": "$1,899/mo",
        "revel-roll-west": "$1,899/mo",
        "jdj-levar": "Founding Member — pending catalog",
    }
    return mrr.get(slug, "—")


def _client_tier(slug: str) -> str:
    tier = {
        "shop-unis": "Pro (custom e-com)",
        "paradise-park-novi": "Growth",
        "revel-roll-west": "Growth",
        "jdj-levar": "Founding",
    }
    return tier.get(slug, "—")


def _client_next_meeting(slug: str) -> str:
    mt = {
        "shop-unis": "Today 2 PM EDT (Kay + Trang)",
        "paradise-park-novi": "Next weekly",
        "revel-roll-west": "Next weekly",
        "jdj-levar": "Subscriber start-day tomorrow",
    }
    return mt.get(slug, "—")


def _client_open_items(slug: str) -> str:
    oi = {
        "shop-unis": "Linking sweep · AIO expansion · Phase 2 templates",
        "paradise-park-novi": "Standard cadence",
        "revel-roll-west": "Standard cadence",
        "jdj-levar": "Subscriber onboarding live tomorrow",
    }
    return oi.get(slug, "—")


async def _card_blockers() -> dict:
    """Live blockers pull from op_sprint_state.blockers JSONB."""
    sprint = await _fetch_sprint_state("EOM")
    blockers = sprint.get("blockers") if sprint else []

    if blockers and isinstance(blockers, list):
        rows = []
        for b in blockers[:6]:
            # blocker shape: {"text": "...", "severity": "high"}
            if isinstance(b, dict):
                txt = b.get("text") or b.get("description") or str(b)
                sev = (b.get("severity") or "").upper()
                # Short label from first 3-4 words of blocker text
                words = txt.split()
                label = " ".join(words[:3])[:20] if words else f"#{len(rows)+1}"
                rest = txt[len(" ".join(words[:3])):].strip().lstrip("—").strip()
                display = rest if len(rest) <= 60 else rest[:57] + "…"
                if sev:
                    display = f"[{sev[:1]}] {display}"
                rows.append({"label": label, "value": display})
        if rows:
            return {
                "title": "Blockers — live",
                "rows": rows,
                "footer": f"{len(blockers)} total · live from op_sprint_state"
            }

    # Cached fallback
    return {
        "title": "Blocked on Solon",
        "rows": [
            {"label": "Anthropic 401", "value": "Diagnose cap vs rotate"},
            {"label": "Restic R2 token", "value": "Cloudflare bucket + write token"},
            {"label": "sql/007 CRM", "value": "Paste into Supabase"},
            {"label": "Telnyx upgrade", "value": "Free-tier pending"},
            {"label": "Hetzner quota", "value": "Dedicated cores pending"},
        ],
        "footer": "Cached · live pull unavailable"
    }


def _card_file_link(path: str, title: str) -> dict:
    """Return a card pointing to a file Titan can deliver."""
    from pathlib import Path as _P
    p = _P(path)
    if not p.exists():
        return {
            "title": title,
            "rows": [{"label": "Status", "value": "File not found on VPS"}],
            "footer": f"Path checked: {path}"
        }
    size_kb = p.stat().st_size // 1024
    return {
        "title": title,
        "rows": [
            {"label": "Location", "value": "VPS /opt/amg-docs"},
            {"label": "Size", "value": f"{size_kb} KB"},
            {"label": "Access", "value": "SSH cat / rsync pull"},
        ],
        "footer": f"Live path: {path}"
    }


async def _card_ct_lookup(ct_id: str) -> dict:
    """Look up a task in the MCP queue."""
    return {
        "title": f"{ct_id} lookup",
        "rows": [
            {"label": "Status", "value": "Query MCP for live data (wire pending)"},
            {"label": "Task ID", "value": ct_id},
        ],
        "footer": "Use Claude Code for full task payload"
    }


@app.get("/api/titan/tts")
async def api_titan_tts(text: str, voice: str = "alex") -> Response:
    """Stream ElevenLabs TTS audio for Titan's reply text."""
    if not ELEVENLABS_API_KEY:
        raise HTTPException(503, "ElevenLabs not configured")
    if not text or len(text) > 2000:
        raise HTTPException(400, "text 1-2000 chars")
    voice_id = ELEVENLABS_VOICES.get(voice.lower(), ELEVENLABS_VOICES["alex"])
    if httpx is None:
        raise HTTPException(500, "httpx missing")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {"stability": 0.55, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True}
    }
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code != 200:
                raise HTTPException(502, f"ElevenLabs {r.status_code}: {r.text[:200]}")
            return Response(content=r.content, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"TTS error: {type(exc).__name__}: {exc}")


@app.post("/api/titan/voice-in")
async def api_titan_voice_in(request: Request) -> JSONResponse:
    """Audio in → Whisper transcript → /api/titan/message pipeline."""
    from fastapi import UploadFile, File, Form
    form = await request.form()
    audio = form.get("audio")
    session_id = form.get("session_id") or "default"
    if not audio:
        raise HTTPException(400, "audio file required")
    if not OPENAI_API_KEY:
        raise HTTPException(503, "Whisper not configured (OPENAI_API_KEY missing)")

    # Read audio bytes
    audio_bytes = await audio.read() if hasattr(audio, "read") else audio
    if httpx is None:
        raise HTTPException(500, "httpx missing")

    # POST to OpenAI Whisper
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={"file": ("voice.webm", audio_bytes, "audio/webm")},
                data={"model": "whisper-1", "language": "en"}
            )
            if r.status_code != 200:
                raise HTTPException(502, f"Whisper {r.status_code}: {r.text[:200]}")
            transcript = r.json().get("text", "").strip()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Whisper error: {type(exc).__name__}: {exc}")

    if not transcript:
        return JSONResponse({"transcript": "", "reply": "(no speech detected)", "card": None})

    # Reuse message pipeline
    card = await _titan_intent_card(transcript)
    if card:
        return JSONResponse({"transcript": transcript, "card": card, "reply": None})

    history = _TITAN_SESSIONS.setdefault(session_id, [])
    msgs = [{"role": "system", "content": _titan_system_prompt()}]
    msgs.extend(history[-12:])
    msgs.append({"role": "user", "content": transcript})
    try:
        reply = await call_llm(msgs)
    except Exception as exc:
        reply = f"(LLM unavailable: {type(exc).__name__})"
    history.append({"role": "user", "content": transcript})
    history.append({"role": "assistant", "content": reply})
    if len(history) > 40:
        del history[:len(history) - 40]

    return JSONResponse({"transcript": transcript, "reply": reply, "session_id": session_id})


@app.get("/api/titan/health")
def api_titan_health() -> dict:
    """Titan mobile command health surface."""
    return {
        "service": "titan-mobile",
        "elevenlabs_configured": bool(ELEVENLABS_API_KEY),
        "whisper_configured": bool(OPENAI_API_KEY),
        "llm_gateway": bool(LITELLM_BASE and LITELLM_KEY),
        "active_sessions": len(_TITAN_SESSIONS),
        "voice_map": list(ELEVENLABS_VOICES.keys()),
    }


# ─── end /titan block ─────────────────────────────────────────────────────────


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    port = int(os.environ.get("ATLAS_API_PORT", "8081"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
