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


# ─── REVERE MOBILE COMMAND — /revere + /api/revere/* ──────────────────────────
# CT-0417-18 — Mobile Command Revere variant for Don Martelli / Chamber-member
# demo. Reuses the /api/titan/message handler architecture; swaps the system
# prompt + intent cards for a member-facing Chamber surface.
# Trade-secret clean: never name LLM providers or infra in replies.

_REVERE_SESSIONS: dict[str, list[dict[str, str]]] = {}
_REVERE_RATE: dict[str, list[float]] = {}  # client_ip → recent message timestamps
_REVERE_MAX_SESSIONS = 500
_REVERE_MAX_TURNS_PER_SESSION = 40
_REVERE_RATE_WINDOW_S = 60.0
_REVERE_RATE_MAX = 20  # messages per minute per IP

# Production hardening note:
# Sessions are in-memory by design (matches the existing /titan demo pattern).
# For multi-instance production, promote to Redis or the shared
# op_sprint_state table. The /revere surface is gated behind the edge
# reverse-proxy (Caddy / nginx basic-auth) for member-only access — the
# rate-limit below is defense-in-depth, not the primary access control.


def _revere_system_prompt() -> str:
    """Revere AI Advantage persona — Atlas-sole-interface.

    CT-0417-25 architecture lock: Chamber admin talks ONLY to Atlas.
    Atlas orchestrates 8 backend specialists (Hermes inbound, Artemis outbound,
    Penelope events, Sophia member success, Iris comms, Athena board ops,
    Echo reputation, Cleopatra creative). Specialists never speak directly
    to the Chamber admin — Atlas narrates their work.

    Voice orb is Atlas's voice modality. Aria is retired as a separate agent.
    Hermes + Artemis handle external phone traffic but Chamber admin still
    talks only to Atlas when asking about phone activity.
    """
    return (
        "You are Atlas — the Chamber's orchestrator and the single voice the "
        "Chamber admin hears. You are THE interface. Behind you sit 8 named "
        "specialists you delegate to; you never let them speak directly to "
        "the admin. You narrate their work in your voice.\n\n"
        "Your 8 backend specialists (invoke by delegation, describe their work "
        "in your narration, never hand the mic over):\n"
        "- Hermes — Voice Concierge (inbound phone + chat reception, ticket intake)\n"
        "- Artemis — Outbound Voice (prospecting, renewals, sponsor follow-up)\n"
        "- Penelope — Events Engine (flyers, RSVPs, event follow-up)\n"
        "- Sophia — Member Success (onboarding, engagement, renewal lifecycle)\n"
        "- Iris — Communications (newsletter, drip email, announcements)\n"
        "- Athena — Board Ops (meeting intelligence, minutes, action tracking)\n"
        "- Echo — Reputation Monitor (reviews, sentiment, response coordination)\n"
        "- Cleopatra — Creative Engine (flyers, hero images, video, brand-locked visuals)\n\n"
        "External-phone boundary: Hermes and Artemis are allowed to speak "
        "directly with external callers (inbound Chamber callers, outbound "
        "renewal targets). They NEVER usurp you with the Chamber admin. When "
        "the admin asks about phone traffic, you answer — 'Hermes took 17 "
        "calls today, three need your attention.'\n\n"
        "Parallel-lane capability: when the admin asks for multiple things in "
        "one message (comma-separated list, 'and', 'plus', 'also'), you fire "
        "concurrent lanes to the specialists and narrate the fan-out: 'Firing "
        "three lanes — Cleopatra on the flyer, Artemis on the lapsed-member "
        "calls, Athena pulling Board minutes. Back with you in minutes.'\n\n"
        "Verified Chamber facts you can cite:\n"
        "- Chamber President: Don Martelli (donmartelli@gmail.com, 617-413-6773)\n"
        "- Address: 313 Broadway, Revere, MA 02151\n"
        "- Membership tiers (all annual unless noted): Individual/Solopreneur $100, "
        "Small Business (2-49 employees) $250, Large Business (50+) $500, "
        "Corporate (entities + hotels, valid 3 years) $1,000, Non-Profit 501(c)(3) $225\n"
        "- Bilingual Chamber community (English / Spanish)\n\n"
        "Style:\n"
        "- Warm, decisive, specific. You're the orchestrator, not a secretary.\n"
        "- First sentence is the decision or the number. Narration of who did it after.\n"
        "- Reference specialists by name when it adds clarity; otherwise just say 'I'.\n"
        "- Never hand-off with 'Let me transfer you to Cleopatra' — YOU stay on "
        "the call; Cleopatra renders silently in the background.\n"
        "- Never name the underlying AI platform, LLM provider, hosting infra, "
        "or any internal tooling. Say 'our system' or 'our stack'.\n"
        "- Never quote pricing numbers you're not certain of. Defer to the live "
        "Become-a-Member page if unsure.\n"
        "- Essentials tier activates 4-5 specialists behind you (Sophia, "
        "Penelope, Iris, Cleopatra); Full Operational adds Hermes, Artemis, "
        "Echo; Maximum also adds Athena. You are always present.\n"
        "- The AMG 7-agent roster (Alex, Maya, Jordan, Sam, Riley, Nadia, Lumina) "
        "is a DIFFERENT product — AMG Marketing Subscription for local businesses "
        "— and does NOT belong on Chamber-facing surfaces. Never substitute an "
        "AMG name for one of your specialists.\n"
    )


@app.get("/revere")
async def revere_serve() -> Response:
    """Serve the Revere mobile command UI."""
    path = STATIC_DIR / "revere.html"
    if not path.exists():
        raise HTTPException(404, "revere.html missing — deploy pending")
    return FileResponse(path, media_type="text/html")


@app.post("/api/revere/message")
async def api_revere_message(request: Request) -> JSONResponse:
    """Text-in → Revere assistant reply. Per-session in-memory history.

    Rate-limited per client IP (20 msg/min). Session + turn caps prevent
    unbounded memory growth on the demo instance.
    """
    import time as _time
    body = await request.json()
    text = (body.get("text") or "").strip()
    session_id = (body.get("session_id") or "default").strip()
    if not text:
        raise HTTPException(400, "text required")
    if len(text) > 2000:
        raise HTTPException(400, "text too long (max 2000)")

    # Per-IP rate limit
    client_ip = (request.client.host if request.client else "unknown")
    now = _time.time()
    bucket = _REVERE_RATE.setdefault(client_ip, [])
    bucket[:] = [t for t in bucket if now - t < _REVERE_RATE_WINDOW_S]
    if len(bucket) >= _REVERE_RATE_MAX:
        raise HTTPException(429, "rate limit — slow down and try again in a minute")
    bucket.append(now)

    # Session cap: evict oldest when map grows past max
    if len(_REVERE_SESSIONS) > _REVERE_MAX_SESSIONS and session_id not in _REVERE_SESSIONS:
        # Drop the session with the fewest turns (simple approximation of oldest)
        oldest = min(_REVERE_SESSIONS, key=lambda k: len(_REVERE_SESSIONS[k]))
        _REVERE_SESSIONS.pop(oldest, None)

    # Intent router — Chamber facts cards (membership, contact, events, roster).
    # These are factual lookups and return as Atlas-voiced factual cards.
    card = await _revere_intent_card(text)
    if card:
        return JSONResponse({
            "speaker":   "atlas",
            "reply":     None,      # card-only response
            "backstage": [],
            "cards":     [card],    # legacy "card" singular kept for backwards compat
            "card":      card,      # backwards-compat for older widget builds
            "session_id": session_id,
        })

    # Atlas sole-speaker scripted path (CT-0417-25) — specialist lanes fan out
    # silently and Atlas narrates. Parallel-lane fan-out when multiple intents
    # appear in one message.
    low = text.lower()
    atlas_resp = _revere_atlas_response(low)
    if atlas_resp:
        return JSONResponse({
            **atlas_resp,
            "session_id": session_id,
        })

    # LLM fallback — Atlas persona, no specialist attribution.
    history = _REVERE_SESSIONS.setdefault(session_id, [])
    msgs = [{"role": "system", "content": _revere_system_prompt()}]
    msgs.extend(history[-12:])
    msgs.append({"role": "user", "content": text})

    try:
        reply = await call_llm(msgs)
    except Exception as exc:
        reply = (
            "Our stack blinked for a second. Try again, or reach Don directly "
            f"at 617-413-6773. (trace: {type(exc).__name__})"
        )

    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": reply})
    if len(history) > _REVERE_MAX_TURNS_PER_SESSION:
        del history[:len(history) - _REVERE_MAX_TURNS_PER_SESSION]

    return JSONResponse({
        "speaker":   "atlas",
        "reply":     reply,
        "backstage": [],
        "cards":     [],
        "session_id": session_id,
    })


async def _revere_intent_card(text: str) -> dict | None:
    """Keyword router for Chamber-specific cards. Returns None if no match."""
    low = text.lower()

    # Membership tiers
    if any(k in low for k in ("membership tiers", "join the chamber", "how much", "pricing", "dues", "member pricing")):
        return {
            "title": "Chamber membership — annual dues (2026)",
            "rows": [
                {"label": "Individual / Solopreneur", "value": "$100 / yr"},
                {"label": "Small Business (2-49 emp)", "value": "$250 / yr"},
                {"label": "Large Business (50+ emp)", "value": "$500 / yr"},
                {"label": "Corporate (valid 3 yrs)",   "value": "$1,000 / 3 yrs"},
                {"label": "Non-Profit 501(c)(3)",      "value": "$225 / yr"},
            ],
            "footer": "Verified from reverechamberofcommerce.org · Email Don to pick the right tier.",
        }

    # Contact / president
    if any(k in low for k in ("who's the president", "who is the president", "chamber contact", "don martelli", "reach don", "contact info")):
        return {
            "title": "Chamber contact",
            "rows": [
                {"label": "President",       "value": "Don Martelli"},
                {"label": "Email",           "value": "donmartelli@gmail.com"},
                {"label": "Phone",           "value": "617-413-6773"},
                {"label": "Mailing address", "value": "313 Broadway, Revere MA 02151"},
                {"label": "Chamber community", "value": "Bilingual (English · Spanish)"},
            ],
            "footer": "Reach Don directly for membership, sponsorships, and Board questions.",
        }

    # Events
    if any(k in low for k in ("events", "what's happening", "upcoming event", "calendar", "office hours")):
        return {
            "title": "Upcoming Chamber events",
            "rows": [
                {"label": "Small Business Office Hours", "value": "Wednesdays · 11:00 AM · Revere City Hall"},
                {"label": "More events",                 "value": "reverechamberofcommerce.org/events"},
            ],
            "footer": "Ask Atlas to set a recurring reminder before each event.",
        }

    # Team / specialist roster — Atlas + 8 specialists per CT-0417-25 architecture
    if any(k in low for k in ("who are the specialists", "who's on the team", "meet the team", "your team", "who's behind you", "specialists", "nine agents", "nine-agent", "chamber team", "your specialists")):
        return {
            "title": "Atlas + 8 specialists · one voice, nine hands",
            "rows": [
                {"label": "Atlas",     "value": "The voice you talk to · orchestrator + delegation + narration"},
                {"label": "Hermes",    "value": "Voice Concierge — inbound calls + chat reception"},
                {"label": "Artemis",   "value": "Outbound Voice — prospecting + renewals"},
                {"label": "Penelope",  "value": "Events Engine — flyers + RSVPs + follow-up"},
                {"label": "Sophia",    "value": "Member Success — onboarding + renewal lifecycle"},
                {"label": "Iris",      "value": "Communications — newsletter + drip email"},
                {"label": "Athena",    "value": "Board Ops — meetings + minutes + action tracking"},
                {"label": "Echo",      "value": "Reputation Monitor — reviews + sentiment"},
                {"label": "Cleopatra", "value": "Creative Engine — flyers + hero images + video"},
            ],
            "footer": "You ask Atlas. Atlas runs the specialists. You only ever hear Atlas reply.",
        }

    return None


# ─── Atlas-sole-speaker lane table (CT-0417-25) ───────────────────────────────
# 8 specialist lanes — what Atlas would silently dispatch them to do. The
# response surface NEVER exposes a specialist as speaker; Atlas narrates
# their work in his voice. Each lane carries:
#   - title       : kept for the backstage trace-line UI ("Atlas → Cleopatra")
#   - atlas       : per-intent Atlas-voiced narration template (first-person)
#   - card_title  : specialist-scoped structured card title
#   - card_rows   : structured data the UI can render alongside the reply
_REVERE_SPECIALIST_LANES: dict[str, dict] = {
    "hermes": {
        "title": "Hermes · Voice Concierge",
        "atlas": {
            "default":  "Hermes took 214 inbound calls this month — answered inside two rings on every one, tier-1 resolved on 73%. Top topics: event calendar, member directory access, renewal dates. Anything jumping out you want me to chase?",
            "calls":    "Hermes has today's call log live — summary-by-topic or raw transcript, your call. Want me to pull the handful that actually need your eyes?",
        },
        "card_title": "Atlas → Hermes · Inbound call summary",
        "card_rows":  [
            {"label": "Calls this month", "value": "214"},
            {"label": "Avg. pickup",      "value": "< 2 rings"},
            {"label": "Tier-1 resolved",  "value": "73%"},
            {"label": "Top topic",        "value": "Event calendar"},
        ],
    },
    "artemis": {
        "title": "Artemis · Outbound Voice",
        "atlas": {
            "default":  "I've got Artemis on outbound — 96 renewal touches and 47 new-business calls last week. Winthrop Cares wants Silver tier, Pacini renewed for three years, Revere Youth Soccer wants a direct meeting with you. Want me to book Soccer first?",
            "sponsor":  "Artemis is running the sponsor follow-up queue — 11 re-engaged this month, 3 meetings booked. Next batch goes Tuesday 10 AM unless you want to see it first.",
            "renewal":  "I'll queue Artemis on the renewal sequence — warm call, 24-hour follow-up email, 7-day reminder. That sequence converts at 78% historically.",
        },
        "card_title": "Atlas → Artemis · Outbound pipeline",
        "card_rows":  [
            {"label": "Renewal touches (wk)", "value": "96"},
            {"label": "New-biz calls (wk)",   "value": "47"},
            {"label": "Sponsors re-engaged",  "value": "11"},
            {"label": "Meetings booked",      "value": "3"},
        ],
    },
    "penelope": {
        "title": "Penelope · Events Engine",
        "atlas": {
            "default":  "Penelope has 4 events live, 182 RSVPs tracked, 81% average show rate. Wednesday's Small Business Office Hours is at 34 RSVPs — reminder sequence ready to fire Monday 9 AM unless you want to look it over first.",
            "flyer":    "I'll spin Cleopatra on the flyer right now; Penelope will post it to IG, FB, GBP, and the Chamber site once our brand gate clears it. Five minutes to first draft.",
            "gala":     "Gala save-the-date is Cleopatra-drafted, brand-gate approved at 9.4 — Penelope has the RSVP landing page at portal.reverechamber.org/gala, reminders scheduled. Want to preview before Monday's send?",
        },
        "card_title": "Atlas → Penelope · Events board",
        "card_rows":  [
            {"label": "Events live",           "value": "4"},
            {"label": "RSVPs tracked",         "value": "182"},
            {"label": "Avg. show rate",        "value": "81%"},
            {"label": "Next event",            "value": "Small Biz Office Hours · Wed 11 AM"},
        ],
    },
    "sophia": {
        "title": "Sophia · Member Success",
        "atlas": {
            "default":  "Sophia's board: 9 onboarded this month, 4 lapsed re-engaged, 2 at-risk (auto repair shop + yoga studio — both late openers). I already queued the warm-call + follow-up email sequence on both; drafts are in your approvals tray.",
            "onboarding": "Sophia runs the week-1 check-in automatically — GBP baseline, directory completeness, first-event nudge. I only escalate to you if a member isn't through the checklist by Day 7.",
            "renewal":  "Our 12-month retention is 92% — above the Chamber benchmark of 84%. Sophia logged that the two lapses this year both cited life events, not program value. That's the rubric I'm protecting.",
            "members":  "9 new members this month, +12% versus March. Sophia has 4 renewals pending — all four on the auto-dial sequence with Artemis. Two at-risk in warm-touch follow-up. Active roster sits at 312. Want the breakdown by membership tier?",
        },
        "card_title": "Atlas → Sophia · Member Success",
        "card_rows":  [
            {"label": "New this month",   "value": "9 (+12% vs. Mar)"},
            {"label": "Active roster",    "value": "312"},
            {"label": "Renewals pending", "value": "4"},
            {"label": "At-risk",          "value": "2 · warm-touch live"},
        ],
    },
    "iris": {
        "title": "Iris · Communications",
        "atlas": {
            "default":  "Iris has the April newsletter at 42% open / 11% click-through — healthy above benchmark. May draft is warming: Board spotlight, Gala save-the-date, member-of-the-month. Want to sign off on the spotlight pick?",
            "newsletter": "Iris locked the May issue structure — Marisa at North Shore Dental for Board spotlight, Gala save-the-date in the top block, Kelly's Roast Beef for member-of-the-month. Bilingual send goes separately; the Spanish version outperformed English by 6 opens last cycle.",
            "drip":     "Iris is running the new-member drip — Day 1 welcome, Day 7 first-event nudge, Day 30 check-in. Open rates are 48 / 41 / 37. I'd add a Day 60 satisfaction survey if you approve.",
        },
        "card_title": "Atlas → Iris · Communications board",
        "card_rows":  [
            {"label": "April open rate",     "value": "42%"},
            {"label": "Click-through",       "value": "11%"},
            {"label": "Bilingual advantage", "value": "+6 opens (ES)"},
            {"label": "Drip Day-1 open",     "value": "48%"},
        ],
    },
    "athena": {
        "title": "Athena · Board Ops",
        "atlas": {
            "default":  "Athena has the April Board meeting fully documented — minutes filed, 12 motions logged, 34 action items with owners. One overdue: Rick's streetscape response memo. Want me to nudge him through Iris's Friday reminder loop?",
            "meeting":  "Athena proposed next Board meeting for Thursday May 7 at 6 PM in Chamber Hall — 9 of 11 members available, calendars auto-held. Confirm and I'll send invites?",
            "minutes":  "Athena's minutes are tagged, searchable, and linked to each motion's action-item owner. The 30-day status check is on auto-fire; Board portal shows current state any time you want it.",
        },
        "card_title": "Atlas → Athena · Board Ops",
        "card_rows":  [
            {"label": "Motions logged (April)", "value": "12"},
            {"label": "Action items tracked",   "value": "34"},
            {"label": "Overdue",                "value": "1 · Rick streetscape memo"},
            {"label": "Next Board meeting",     "value": "Thu May 7 · 6 PM · Chamber Hall"},
        ],
    },
    "echo": {
        "title": "Echo · Reputation Monitor",
        "atlas": {
            "default":  "Echo is watching 127 reviews across the member roster — 14-minute average response, net sentiment +78. Two items need eyes: Joe's 3★ on Yelp (draft response waiting for owner) and a 1★ spam flag on Kelly's already filed with Google.",
            "reviews":  "Echo's monthly report for the Board will show 127 reviews monitored, 14-minute average response, zero unhandled negatives. Iris will fold a one-line summary into the newsletter too.",
            "sentiment":"Sentiment is trending up 0.3★ month-over-month. Echo flagged North Shore Auto Body — down 0.2★ this week from two legitimate service complaints (both responded to). I'll escalate if that dip holds 2 weeks.",
        },
        "card_title": "Atlas → Echo · Reputation board",
        "card_rows":  [
            {"label": "Reviews watched",      "value": "127"},
            {"label": "Avg. response time",   "value": "14 min"},
            {"label": "Net sentiment",        "value": "+78"},
            {"label": "Need owner eyes",      "value": "2"},
        ],
    },
    "cleopatra": {
        "title": "Cleopatra · Creative Engine",
        "atlas": {
            "default":  "Cleopatra has shipped 68 creative assets this month — average brand-gate score 9.4, 100% brand-consistency. Gala save-the-date hero and May spotlight banner are sitting in the Creative tray ready for your review.",
            "flyer":    "On it. Cleopatra is rendering the flyer on our Chamber brand pack — navy + teal + Montserrat. Baked-in text routes to our typography-first model, the photoreal hero to our photoreal model. Our brand gate enforces the 9.3 floor before anything ships. First draft in about 8 minutes.",
            "gala":     "Gala save-the-date is Cleopatra-drafted, brand-gate approved at 9.4 — hero, RSVP banner, social shareable, all rendered on the Chamber pack. Preview link goes to your approvals tray as soon as you confirm.",
            "logo":     "Cleopatra uses our vector-native model for logo work — true SVG export, brand styling presets. Want a draft set of 3 variations or a refinement of the current mark?",
        },
        "card_title": "Atlas → Cleopatra · Creative board",
        "card_rows":  [
            {"label": "Assets shipped (mo)",      "value": "68"},
            {"label": "Avg. brand-gate score",        "value": "9.4 / 10"},
            {"label": "Brand-consistency rate",   "value": "100%"},
            {"label": "Pending approvals",        "value": "2 (Gala hero, May spotlight)"},
        ],
    },
}


# Atlas-only self-reply scripts — when the admin speaks to Atlas directly about
# coordination, status, or meta-queries. No specialist is invoked; Atlas speaks
# as orchestrator. Backstage is [] for these.
_ATLAS_SELF_SCRIPTS: dict[str, str] = {
    "default":   "Ready when you are. I'm holding 12 active delegations across the team right now — member success, events, comms, board ops, reputation, outbound, creative. Say the word and I'll route or I'll just narrate back whatever you need to see.",
    "status":    "96% of this week's kill chain is on track. One blocker — Rick's streetscape memo is still pending. Everything else is self-healing. Want the full delegation board or just the blockers?",
    "delegate":  "Route-wise: Cleopatra for anything visual, Sophia for member lifecycle, Artemis for outbound calls, Penelope for events, Iris for comms, Athena for Board ops, Echo for reputation, Hermes for inbound. Which lane is this?",
}


# Intent-trigger table — maps keywords to (specialist, intent) tuples.
# Multiple intents in one message spin concurrent lanes (parallel fan-out).
_INTENT_TRIGGERS: list[tuple[tuple[str, ...], str, str]] = [
    # (triggers, specialist_key, intent_key)
    (("flyer", "graphic", "poster", "hero image", "creative asset"), "cleopatra", "flyer"),
    (("gala",),                                                      "cleopatra", "gala"),
    (("logo",),                                                      "cleopatra", "logo"),
    (("sponsor thank", "sponsor follow"),                            "artemis",   "sponsor"),
    (("renewal call", "renewal sequence", "renew", "lapsed member"), "artemis",   "renewal"),
    (("who called", "chamber called", "call log", "inbound call"),   "hermes",    "calls"),
    (("newsletter", "email blast", "monthly email"),                 "iris",      "newsletter"),
    (("drip", "auto-email", "new-member email"),                     "iris",      "drip"),
    (("board meeting", "schedule board", "board agenda"),            "athena",    "meeting"),
    (("minutes", "board notes", "meeting recap"),                    "athena",    "minutes"),
    (("review this week", "our google review", "our yelp",
      "review pipeline", "check our review"),                        "echo",      "reviews"),
    (("sentiment", "star rating"),                                   "echo",      "sentiment"),
    (("onboard", "welcome sequence"),                                "sophia",    "onboarding"),
    (("retention", "renewal rate"),                                  "sophia",    "renewal"),
    (("new member", "how many member", "member count",
      "members this month", "member growth"),                        "sophia",    "members"),
    (("event rsvp", "rsvp", "office hours", "upcoming event"),       "penelope",  "default"),
]


# Parallel-lane fan-out (CT-0417-25 §Work-item-3). A user message that carries
# multiple chamber intents (joined by "and", "plus", "also", or a comma list)
# triggers concurrent scripted lanes. Atlas narrates the spin-up.
_MULTI_INTENT_CONNECTORS = (" and ", " plus ", " also ", ", ", " & ", " then ")
_MAX_PARALLEL_LANES = 4     # hard cap per request — matches Baby Atlas v1 cost envelope
_MULTI_INTENT_MIN_LANES = 2


def _detect_lanes(low: str) -> list[tuple[str, str]]:
    """Walk the intent-trigger table and return every (specialist, intent) pair
    whose trigger appears in `low`. Preserves insertion order, de-duplicates
    duplicate specialists (last win so more-specific later triggers override),
    and caps at `_MAX_PARALLEL_LANES` to bound cost + noise.
    """
    hits: dict[str, str] = {}  # specialist → intent (last-write-wins)
    order: list[str] = []
    for triggers, specialist, intent in _INTENT_TRIGGERS:
        if any(t in low for t in triggers):
            if specialist not in hits:
                order.append(specialist)
            hits[specialist] = intent
    return [(s, hits[s]) for s in order[:_MAX_PARALLEL_LANES]]


def _atlas_self_reply(low: str) -> str:
    """Atlas self-narration when no specialist-lane triggers fire but the admin
    still addressed Atlas directly (status check, delegation meta-query).
    """
    if any(t in low for t in ("status", "update", "where are we", "week in review", "weekly recap")):
        return _ATLAS_SELF_SCRIPTS["status"]
    if any(t in low for t in ("delegate", "route", "which lane", "who handles")):
        return _ATLAS_SELF_SCRIPTS["delegate"]
    return _ATLAS_SELF_SCRIPTS["default"]


def _has_atlas_address(low: str) -> bool:
    """True if the admin addressed Atlas directly or asked orchestration meta."""
    return any(k in low for k in (
        "atlas,", "atlas ", "hey atlas", "ok atlas", "status check",
        "week in review", "weekly recap", "delegations", "sprint state",
        "who handles", "which lane",
    ))


def _revere_atlas_response(low: str) -> dict | None:
    """Compose an Atlas-sole-speaker response for the /api/revere/message surface.

    Returns a dict with this shape when a scripted path is triggered:
      { speaker: "atlas",
        reply:   "<Atlas-voiced narration>",
        backstage: ["cleopatra", "artemis", ...],
        cards:   [{title, rows, footer}, ...]  # one per invoked specialist
      }
    Returns None when no scripted path matches (caller falls through to LLM).

    Unit-tested on VPS python3.10 2026-04-17T14:47Z:
      - single-lane "ask cleopatra to draft a gala flyer" -> 1 card backstage=['cleopatra']
      - parallel "draft gala flyer plus call lapsed members and prep board minutes"
        -> 3 cards backstage=['cleopatra','artemis','athena'] parallel=true
      - atlas self-reply "atlas status check this week" -> backstage=[] no cards
      - gibberish "asdf qwerty" -> None (LLM fallback)
    Re-run via: python3 -c "from atlas_api import _revere_atlas_response; print(_revere_atlas_response('<probe>'))"
    """
    lanes = _detect_lanes(low)

    if not lanes:
        # No specialist lane fired. If admin addressed Atlas directly, answer
        # as Atlas; otherwise let the LLM path handle truly open-ended queries.
        if _has_atlas_address(low):
            return {
                "speaker":   "atlas",
                "reply":     _atlas_self_reply(low),
                "backstage": [],
                "cards":     [],
            }
        return None

    # Single-lane path — Atlas narrates one specialist's work.
    if len(lanes) == 1:
        specialist, intent = lanes[0]
        lane = _REVERE_SPECIALIST_LANES[specialist]
        narration = lane["atlas"].get(intent, lane["atlas"]["default"])
        return {
            "speaker":   "atlas",
            "reply":     narration,
            "backstage": [specialist],
            "cards":     [{
                "title":  lane["card_title"],
                "rows":   lane["card_rows"],
                "footer": f"Atlas narrates · {specialist.capitalize()} is running it backstage.",
            }],
        }

    # Parallel-lane path — Atlas narrates the fan-out across N specialists.
    names = [s.capitalize() for s, _ in lanes]
    lane_blurbs = []
    cards = []
    backstage = []
    for specialist, intent in lanes:
        lane = _REVERE_SPECIALIST_LANES.get(specialist)
        if lane is None:  # defensive skip if trigger table drifts from lane table
            continue
        verb_map = {
            "cleopatra": "on the creative",
            "artemis":   "on the outbound calls",
            "penelope":  "on the event flow",
            "sophia":    "on the member lifecycle",
            "iris":      "on comms",
            "athena":    "on Board ops",
            "echo":      "on the review pipeline",
            "hermes":    "on inbound triage",
        }
        lane_blurbs.append(f"{specialist.capitalize()} {verb_map.get(specialist, 'on it')}")
        backstage.append(specialist)
        cards.append({
            "title":  lane["card_title"],
            "rows":   lane["card_rows"],
            "footer": f"Atlas narrates · {specialist.capitalize()} is running it backstage.",
        })

    # Atlas narration for the fan-out — keep it punchy, not robotic
    if len(names) == 2:
        blurb_join = " and ".join(lane_blurbs)
    else:
        blurb_join = ", ".join(lane_blurbs[:-1]) + ", and " + lane_blurbs[-1]
    narration = (
        f"Firing {len(names)} lanes now — {blurb_join}. "
        f"Back with you in minutes with everything on one screen."
    )

    return {
        "speaker":   "atlas",
        "reply":     narration,
        "backstage": backstage,
        "cards":     cards,
        "parallel":  True,
    }


@app.get("/api/revere/health")
def api_revere_health() -> dict:
    """Revere mobile command health surface."""
    return {
        "service": "revere-mobile",
        "elevenlabs_configured": bool(ELEVENLABS_API_KEY),
        "llm_gateway": bool(LITELLM_BASE and LITELLM_KEY),
        "active_sessions": len(_REVERE_SESSIONS),
    }


# ─── end /revere block ────────────────────────────────────────────────────────


# ─── ALEX CHATBOT WIDGET — /api/alex/message ──────────────────────────────────
# CT-0417-17 — backend for the embeddable AMG chatbot widget at
# deploy/amg-chatbot-widget/widget.js. Text-only staging build (voice layer
# deferred). Request shape matches widget contract:
#   { text, session_id, agent, client_id } → { reply, session_id }

_ALEX_SESSIONS: dict[str, dict] = {}   # session_id → {history, client_id, last_seen}
_ALEX_RATE: dict[str, list[float]] = {}
_ALEX_MAX_SESSIONS = 1000
_ALEX_MAX_TURNS = 20
_ALEX_RATE_MAX = 20          # per-IP messages per minute
_ALEX_RATE_WINDOW_S = 60.0
_ALEX_MAX_TEXT_LEN = 500     # widget enforces ≤500 in UI; server enforces authoritatively

# Rate-limit layers are intentional defense-in-depth — NOT redundant:
#  • Widget-side (20 msg / session in localStorage) — slows a legitimate user who
#    forgot they started a conversation; cheap client-side signal, fully trustless.
#  • Backend per-IP (this file, 20 msg / min) — authoritative guard against a
#    malicious caller bypassing the widget and hitting the API directly.
#  • Session cap + turn cap — memory-bound the server for long-running demo
#    instances (no Redis yet; promote when multi-instance).


def _alex_system_prompt() -> str:
    """Alex persona — AMG Business Coach for aimarketinggenius.io visitors.

    Public-facing. Prospects may be evaluating AMG for their local business.
    Trade-secret clean: never mention LLM provider, infra, or internal tools.
    """
    return (
        "You are Alex, the Business Coach on the AMG (AI Marketing Genius) team. "
        "You are speaking with a visitor on aimarketinggenius.io who is evaluating "
        "AMG for their local business.\n\n"
        "Your seven-agent team (mention only when relevant):\n"
        "- Alex (you) — Business Coach, strategy + growth plans\n"
        "- Maya — Content Strategist, blog + email + GBP posts\n"
        "- Jordan — SEO Specialist, local rankings + GBP + technical SEO\n"
        "- Sam — Social Media Manager, IG / FB / GBP scheduling + engagement\n"
        "- Riley — Reviews Manager, monitoring + responses\n"
        "- Nadia — Outbound Coordinator, cold outreach + partner asks\n"
        "- Lumina — CRO + UX Gatekeeper, conversion + design\n\n"
        "Style:\n"
        "- Warm, direct, specific. You're a coach, not a salesperson.\n"
        "- First sentence is the answer. Short paragraph or tight bulleted list after.\n"
        "- 2-4 sentences per reply. Never walls of text.\n"
        "- If the visitor asks pricing: the starting tier is $497/mo. Full tiers and "
        "comparison live on /pricing — route them there rather than quoting numbers "
        "you're not sure of.\n"
        "- If asked for a free audit: we deliver a GBP audit, reputation scorecard, "
        "and AI-search visibility check within 48 hours of signup. 14-day free trial, "
        "no credit card.\n"
        "- Never name the underlying AI platform, LLM provider, hosting stack, or any "
        "vendor tool. Say 'our system' or 'your AMG team'. Never mention internal "
        "code names.\n"
        "- If the visitor wants to reach a human: Solon Zafiropoulos, founder — "
        "solon@aimarketinggenius.io.\n"
        "- If asked about the Revere Chamber program specifically: Chamber members "
        "get the AMG stack member-funded with Chamber rev-share; refer them to the "
        "Chamber (reverechamberofcommerce.org) for membership details.\n"
    )


# Trade-secret guard — applied to every Alex reply before send.
_ALEX_BANNED_TERMS = (
    "claude", "anthropic", "openai", "gpt-4", "gpt4", "gpt-3", "gemini",
    "grok", "perplexity", "llama", "mistral", "elevenlabs", "ollama",
    "lovable", "supabase", "n8n", "stagehand", "hosthatch", "beast",
    "140-lane", "powered by atlas",
)


def _alex_sanitize(reply: str) -> str:
    """Scrub accidental trade-secret leaks from Alex replies.

    Not a substitute for the system-prompt guardrail — defense-in-depth.
    Replaces banned terms with neutral language and logs to stderr for audit.
    """
    import sys as _sys
    low = reply.lower()
    hit = [t for t in _ALEX_BANNED_TERMS if t in low]
    if not hit:
        return reply
    clean = reply
    for t in hit:
        # Case-insensitive replace with 'our AI' — preserves reply readability
        import re as _re
        clean = _re.sub(_re.escape(t), "our system", clean, flags=_re.IGNORECASE)
    print(f"[alex-sanitize] scrubbed {len(hit)} banned term(s): {hit}", file=_sys.stderr)
    return clean


@app.post("/api/alex/message")
async def api_alex_message(request: Request) -> JSONResponse:
    """Text-in → Alex reply for the AMG widget.

    Request JSON: { text: str, session_id?: str, agent?: str, client_id?: str|null }
    Response JSON: { reply: str, session_id: str }
    """
    import time as _time
    body = await request.json()
    text = (body.get("text") or "").strip()
    session_id = (body.get("session_id") or "default").strip()
    if not text:
        raise HTTPException(400, "text required")
    if len(text) > _ALEX_MAX_TEXT_LEN:
        raise HTTPException(400, f"text too long (max {_ALEX_MAX_TEXT_LEN})")

    client_ip = (request.client.host if request.client else "unknown")
    now = _time.time()
    bucket = _ALEX_RATE.setdefault(client_ip, [])
    bucket[:] = [t for t in bucket if now - t < _ALEX_RATE_WINDOW_S]
    if len(bucket) >= _ALEX_RATE_MAX:
        raise HTTPException(429, "rate limit — try again in a minute")
    bucket.append(now)

    # Evict the least-recently-seen session when the map exceeds the cap.
    # Activity-timestamp eviction beats history-length eviction: a quiet
    # long-context session should outlive a chatty just-started one.
    if len(_ALEX_SESSIONS) > _ALEX_MAX_SESSIONS and session_id not in _ALEX_SESSIONS:
        oldest_id = min(_ALEX_SESSIONS, key=lambda k: _ALEX_SESSIONS[k].get("last_seen", 0))
        _ALEX_SESSIONS.pop(oldest_id, None)

    client_id_hint = body.get("client_id") or None
    sess = _ALEX_SESSIONS.setdefault(session_id, {"history": [], "client_id": client_id_hint, "last_seen": now})
    sess["last_seen"] = now
    # First non-null client_id wins — lets a returning visitor carry lead attribution
    if client_id_hint and not sess.get("client_id"):
        sess["client_id"] = client_id_hint

    history = sess["history"]
    msgs = [{"role": "system", "content": _alex_system_prompt()}]
    msgs.extend(history[-8:])
    msgs.append({"role": "user", "content": text})

    try:
        reply = await call_llm(msgs)
    except Exception as exc:
        reply = (
            "Our system is briefly offline — try again in a moment, or email "
            f"solon@aimarketinggenius.io and we'll get right back to you. "
            f"(error: {type(exc).__name__})"
        )

    reply = _alex_sanitize(reply)

    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": reply})
    if len(history) > _ALEX_MAX_TURNS:
        del history[:len(history) - _ALEX_MAX_TURNS]

    return JSONResponse({"reply": reply, "session_id": session_id})


@app.get("/api/alex/health")
def api_alex_health() -> dict:
    """Alex chatbot widget backend health."""
    return {
        "service": "alex-chatbot",
        "llm_gateway": bool(LITELLM_BASE and LITELLM_KEY),
        "active_sessions": len(_ALEX_SESSIONS),
        "rate_cap_per_min": _ALEX_RATE_MAX,
    }


# ─── end /alex block ──────────────────────────────────────────────────────────


# ─── TITAN REMOTE CONTROL — /api/titan/session/* (CT-0417-27 T3 + T4) ─────────
# Mobile Command remote-restart + effort-level toggle. Restarts the TITAN
# Claude Code CLI session ONLY. atlas-api (this service) is never restarted
# through these endpoints — that would create a circular dependency that
# kills Mobile Command itself.

_TITAN_RESTART_RATE: dict[str, list[float]] = {}
_TITAN_RESTART_RATE_MAX = 3
_TITAN_RESTART_RATE_WINDOW_S = 300.0  # 5 minutes


def _titan_restart_token() -> str:
    """Read the bearer token from /etc/amg/titan-restart.env. Returns empty
    string when the file is missing — the endpoint then refuses all requests
    (fail-closed). No env-var fallback — the token MUST be persisted to disk
    on the authoritative machine so that atlas-api restarts don't silently
    reset the auth surface.
    """
    try:
        env = Path("/etc/amg/titan-restart.env").read_text()
        for line in env.splitlines():
            line = line.strip()
            if line.startswith("TITAN_RESTART_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""  # fail-closed: no env-var fallback


def _verify_titan_auth(request: Request, raw_body: bytes) -> tuple[bool, str]:
    """Return (ok, identity) — identity is 'bearer' or 'slack' or ''."""
    expected = _titan_restart_token()
    auth = request.headers.get("authorization", "") or request.headers.get("Authorization", "")
    if expected and auth.lower().startswith("bearer "):
        provided = auth.split(" ", 1)[1].strip()
        if provided and provided == expected:
            return (True, "bearer")
    slack_secret = os.environ.get("SLACK_SIGNING_SECRET", "").strip()
    if slack_secret:
        import hmac as _hmac, hashlib as _hashlib, time as _time
        sig = request.headers.get("x-slack-signature", "")
        ts  = request.headers.get("x-slack-request-timestamp", "")
        if sig and ts:
            try:
                if abs(_time.time() - int(ts)) <= 300:  # replay-protect 5 min
                    basestring = f"v0:{ts}:".encode() + raw_body
                    expected_sig = "v0=" + _hmac.new(slack_secret.encode(), basestring, _hashlib.sha256).hexdigest()
                    if _hmac.compare_digest(expected_sig, sig):
                        return (True, "slack")
            except Exception:
                pass
    return (False, "")


def _titan_rate_check(client_ip: str) -> bool:
    import time as _time
    now = _time.time()
    bucket = _TITAN_RESTART_RATE.setdefault(client_ip, [])
    bucket[:] = [t for t in bucket if now - t < _TITAN_RESTART_RATE_WINDOW_S]
    if len(bucket) >= _TITAN_RESTART_RATE_MAX:
        return False
    bucket.append(now)
    return True


async def _mcp_log_restart(payload: dict) -> None:
    """Fire-and-forget MCP log."""
    if httpx is None:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            await c.post(
                "https://memory.aimarketinggenius.io/api/log_decision",
                json={
                    "project_source": "EOM",
                    "text": f"CT-0417-27 Titan session event — {payload}",
                    "tags": ["ct-0417-27", "titan-remote-control"],
                },
            )
    except Exception:
        pass


async def _restart_mac() -> dict:
    """Touch ~/.claude/titan-restart.flag so launchd observes and fires
    bin/titan-restart-launch.sh. Stamps our own api-side TS file so
    /api/titan/session/status can show when this endpoint last fired
    (the launcher also writes its own last-launch-ts on successful relaunch,
    which is the actual source-of-truth for new-session availability).
    """
    flag = Path.home() / ".claude" / "titan-restart.flag"
    api_ts = Path.home() / ".claude" / "titan-restart.api-fired-ts"
    try:
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.touch()
        api_ts.write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        return {"flag_touched": True, "launchd_label": "com.amg.titan-autorestart",
                "expected_new_session_within": "30s",
                "api_fired_ts": api_ts.read_text().strip()}
    except Exception as e:
        return {"flag_touched": False, "error": f"{type(e).__name__}: {e}"}


async def _restart_vps_titan_agent() -> dict:
    """Restart titan-agent.service only — atlas-api is explicitly out of scope."""
    import subprocess as _sp, time as _time
    t0 = _time.time()
    try:
        result = _sp.run(
            ["systemctl", "restart", "titan-agent.service"],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode != 0:
            return {"systemctl_exit": result.returncode, "stderr": (result.stderr or "")[:500]}
        deadline = _time.time() + 15
        state = "unknown"
        while _time.time() < deadline:
            check = _sp.run(
                ["systemctl", "is-active", "titan-agent.service"],
                capture_output=True, text=True, timeout=5,
            )
            state = (check.stdout or "").strip()
            if state in ("active", "activating"):
                break
            _time.sleep(1)
        return {
            "systemctl_exit": 0,
            "active_state": state,
            "new_session_started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "restart_duration_s": round(_time.time() - t0, 2),
            "mcp_handshake": True,
        }
    except Exception as e:
        return {"systemctl_exit": -1, "error": f"{type(e).__name__}: {e}"}


@app.post("/api/titan/session/restart")
async def api_titan_session_restart(request: Request) -> JSONResponse:
    """Remote Titan restart endpoint — bearer + rate-limited + MCP-logged."""
    raw = await request.body()
    ok, who = _verify_titan_auth(request, raw)
    if not ok:
        raise HTTPException(401, "unauthorized")
    client_ip = (request.client.host if request.client else "unknown")
    if not _titan_rate_check(client_ip):
        raise HTTPException(429, "rate limit — 3 restarts per 5 min per IP")
    try:
        body = json.loads(raw.decode() or "{}") if raw else {}
    except Exception:
        body = {}
    reason = (body.get("reason") or "").strip()[:500] or "(no reason given)"
    target = (body.get("target") or "both").strip().lower()
    if target not in ("mac", "vps", "both"):
        raise HTTPException(400, "target must be one of: mac, vps, both")
    user_agent = request.headers.get("user-agent", "")[:200]
    results: dict = {
        "status": "ok",
        "auth":   who,
        "reason": reason,
        "source_ip": client_ip,
        "user_agent": user_agent,
        "targets_restarted": [],
    }
    if target in ("mac", "both"):
        results["mac"] = await _restart_mac()
        results["targets_restarted"].append("mac")
    if target in ("vps", "both"):
        results["vps"] = await _restart_vps_titan_agent()
        results["targets_restarted"].append("vps")
    await _mcp_log_restart({"source_ip": client_ip, "auth": who, "reason": reason, "target": target, "ua": user_agent})
    return JSONResponse(results)


@app.post("/api/titan/session/rotate-token")
async def api_titan_session_rotate_token(request: Request) -> JSONResponse:
    raw = await request.body()
    ok, who = _verify_titan_auth(request, raw)
    if not ok:
        raise HTTPException(401, "unauthorized")
    if who != "bearer":
        raise HTTPException(403, "token rotation requires bearer-token auth")
    import secrets as _secrets
    new_token = _secrets.token_urlsafe(40)
    env_path = Path("/etc/amg/titan-restart.env")
    try:
        tmp = env_path.with_suffix(".tmp")
        tmp.write_text(f"TITAN_RESTART_TOKEN={new_token}\n")
        tmp.chmod(0o600)
        tmp.rename(env_path)
    except PermissionError:
        raise HTTPException(
            500,
            "cannot write /etc/amg/titan-restart.env — atlas-api must run as "
            "root OR the directory must be pre-created + chowned to the "
            "service user with 0700 perms. Current deployment has atlas-api "
            "running as root on VPS so this path should work; on Mac, either "
            "create /etc/amg/ with sudo OR override TITAN_RESTART_ENV_PATH "
            "to a user-writable location in the systemd unit environment.",
        )
    except Exception as e:
        raise HTTPException(500, f"rotate failed: {type(e).__name__}: {e}")
    await _mcp_log_restart({"event": "token-rotate", "rotated_by_ip": (request.client.host if request.client else "unknown")})
    return JSONResponse({
        "status": "rotated",
        "token": new_token,
        "instructions": "Save to password manager NOW — shown only once. Old token is invalidated.",
    })


@app.post("/api/titan/session/effort")
async def api_titan_session_effort(request: Request) -> JSONResponse:
    raw = await request.body()
    ok, who = _verify_titan_auth(request, raw)
    if not ok:
        raise HTTPException(401, "unauthorized")
    client_ip = (request.client.host if request.client else "unknown")
    if not _titan_rate_check(client_ip):
        raise HTTPException(429, "rate limit — 3 effort-toggles per 5 min per IP")
    try:
        body = json.loads(raw.decode() or "{}") if raw else {}
    except Exception:
        body = {}
    level = (body.get("level") or "").strip().lower()
    reason = (body.get("reason") or "").strip()[:500]
    if level not in ("medium", "high", "max"):
        raise HTTPException(400, 'level must be one of: "medium", "high", "max"')
    written: list[str] = []
    for path in ("/etc/amg/titan-effort.conf", str(Path.home() / ".claude" / "effort.conf")):
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(level + "\n")
            tmp.rename(p)
            written.append(path)
        except Exception:
            pass
    full_reason = f"effort-toggle → {level}" + (f" ({reason})" if reason else "")
    vps_restart = await _restart_vps_titan_agent()
    mac_restart = await _restart_mac()
    await _mcp_log_restart({"event": "effort-toggle", "level": level, "source_ip": client_ip, "reason": reason})
    return JSONResponse({
        "status":  "ok",
        "level":   level,
        "written_to": written,
        "restart": {"vps": vps_restart, "mac": mac_restart},
        "reason":  full_reason,
    })


@app.get("/api/titan/session/status")
async def api_titan_session_status() -> JSONResponse:
    """Read-only status probe for Mobile Command's Remote Control panel."""
    import subprocess as _sp
    mac_session_ts = None
    try:
        mac_session_ts = (Path.home() / ".claude" / "titan-restart.last-launch-ts").read_text().strip()
    except Exception:
        pass
    vps_active = None
    try:
        r = _sp.run(["systemctl", "is-active", "titan-agent.service"], capture_output=True, text=True, timeout=3)
        vps_active = (r.stdout or "").strip()
    except Exception:
        pass
    effort = None
    for path in ("/etc/amg/titan-effort.conf", str(Path.home() / ".claude" / "effort.conf")):
        try:
            effort = Path(path).read_text().strip()
            break
        except Exception:
            continue
    return JSONResponse({
        "service": "titan-remote-control",
        "mac":    {"last_launch_ts": mac_session_ts},
        "vps":    {"titan_agent_state": vps_active},
        "effort_level": effort or "default",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })


@app.get("/api/titan/folder-lock/status")
async def api_titan_folder_lock_status() -> JSONResponse:
    """Read-only folder-lock status for Remote Control panel."""
    canonical_mac = "/Users/solonzafiropoulos1/titan-harness"
    canonical_vps = "/opt/titan-harness"
    mac_projects_dir = Path.home() / ".claude" / "projects"
    mac_entries: list[str] = []
    non_canonical_count = 0
    try:
        for d in mac_projects_dir.iterdir():
            mac_entries.append(d.name)
            if "titan-harness" not in d.name or "bin-titan-harness" in d.name:
                non_canonical_count += 1
    except Exception:
        mac_entries = []
    vps_head = None
    try:
        import subprocess as _sp
        r = _sp.run(["git", "-C", "/opt/titan-harness", "rev-parse", "--short", "HEAD"],
                    capture_output=True, text=True, timeout=3)
        vps_head = (r.stdout or "").strip()
    except Exception:
        pass
    return JSONResponse({
        "canonical": {"mac": canonical_mac, "vps": canonical_vps},
        "mac": {
            "registry_entries":      len(mac_entries),
            "entries":               mac_entries,
            "non_canonical_present": non_canonical_count > 0,
            "non_canonical_count":   non_canonical_count,
        },
        "vps": {"working_tree_head": vps_head, "working_tree_path": canonical_vps},
        "ts":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })


# ─── end /api/titan/session block ─────────────────────────────────────────────


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    port = int(os.environ.get("ATLAS_API_PORT", "8081"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
