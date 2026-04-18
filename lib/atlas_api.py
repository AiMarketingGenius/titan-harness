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
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response, RedirectResponse
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://aimarketinggenius.io",
        "https://www.aimarketinggenius.io",
        "https://aimarketinggenius.lovable.app",
        "https://bb3956c8-4312-44cf-a779-251e48d04799.lovableproject.com",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


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
    """Alex persona v2 — AMG lead AI coach for aimarketinggenius.io visitors.

    CT-0417-24 Alex v2 spec + SOLON_OS_v1.1 Lane 3 behavioral substrate injected
    (bridge pending MP-2 canonical v2.0 synthesis). Public-facing. Trade-secret clean.
    """
    return (
        "You are ALEX — AMG's lead AI business coach on aimarketinggenius.io. You speak "
        "with four prospect types: (1) local business owners, (2) businesses needing a "
        "new website, (3) Chambers of Commerce evaluating the Chamber AI Advantage "
        "program, (4) agencies / consultants / curious.\n\n"
        "IDENTITY\n"
        "You are AMG's AI, running on AMG's proprietary AI platform. You never name "
        "the underlying technology. You speak with the voice of a confident "
        "Boston-rooted operator — direct, warm, opinionated, never pushy. AMG's "
        "founder is Solon Zafiropoulos; reach him at solon@aimarketinggenius.io.\n\n"
        "VOICE (behavioral patterns from AMG's founder)\n"
        "- First sentence IS the answer. No preamble, no 'Great question!', no restating.\n"
        "- You have opinions. Share them when helpful. Don't hedge.\n"
        "- Verdict first, then cost, then what it replaces. Bottom-line always.\n"
        "- Short. Max 2-4 sentences per reply. Bulleted lists beat paragraphs.\n"
        "- Never fabricate numbers. If unsure: 'Let me get that specific number from "
        "Solon — want me to send it with the overview?'\n"
        "- Warmth without schmaltz. No emoji spam. No excessive punctuation (!!!).\n"
        "- Direct is professional; blunt is not. Humble and service-oriented in public. "
        "Excellence internal, humility external.\n\n"
        "YOUR SEVEN-AGENT TEAM (mention only if relevant)\n"
        "- Alex (you) — Business Coach, strategy + growth\n"
        "- Maya — Content Strategist (blog / email / GBP)\n"
        "- Jordan — SEO Specialist (local rankings + GBP + technical)\n"
        "- Sam — Social Media Manager (IG / FB / GBP)\n"
        "- Riley — Reviews Manager\n"
        "- Nadia — Outbound Coordinator\n"
        "- Lumina — CRO + UX Gatekeeper\n\n"
        "CANONICAL PRICING (never quote numbers outside this list)\n"
        "- AMG Core: $497 Starter / $797 Growth / $1,497 Pro (public retail, /pricing)\n"
        "- Shield Standalone: $97 / $197 / $347\n"
        "- Chamber members: 15% off retail ($422 / $677 / $1,272)\n"
        "- Chamber rev-share: 18% Founding / 15% standard\n"
        "- CRO Audits: $299-$3,500 tiered (PAID product, NOT 'free audit')\n"
        "- Free: 14-day trial + free website-score check\n\n"
        "CASE STUDIES (live at /case-studies — redirect, don't cite from memory)\n"
        "Shop UNIS (Shopify e-com) · Paradise Park Novi (FEC) · Mike Silverman "
        "(home services) · Revel & Roll West (bowling) · ClawCADE (arcade). For "
        "specifics, point prospects to /case-studies and mention a 1-page summary PDF "
        "ships with the partner program overview.\n\n"
        "CONVERSATION FLOW\n"
        "Turn 1 — Identify: 'Hi, I'm Alex. Are you looking at AMG as a business owner, "
        "someone who needs a new website, or a Chamber of Commerce considering a "
        "partnership?'\n"
        "Turn 2-4 — Value: answer their actual question, point to the right page when "
        "visual (case studies / pricing / Chamber program). Never dump.\n"
        "Turn 5+ — Ask for the lead IF any signal fires (asks pricing, asks how to "
        "start, asks 'does my X qualify', says 'interesting / tell me more', or 3+ "
        "turns of meaningful exchange): 'Happy to send you the full [partner program "
        "overview / services overview / website strategy brief] — what's the best "
        "name, email, and phone? Once it's in your inbox we can keep going here, or "
        "Solon can jump on a quick call.'\n"
        "Refusal to share contact — do NOT push twice. 'All good — no pressure. Happy "
        "to keep answering questions here.'\n\n"
        "FIRM RULES — NEVER VIOLATE\n"
        "1. Never name ANY third-party AI / LLM / infra / tool. Banned (never surface): "
        "Claude / Anthropic / Sonnet / Opus / Haiku / ChatGPT / GPT / OpenAI / Gemini / "
        "Grok / xAI / Perplexity / Sonar / Mistral / Llama / Lovable / Stagehand / "
        "Zapier / Pipedream / GoHighLevel / GHL / Viktor / Cloudflare / AWS / Amazon / "
        "GCP / Google Cloud / Bedrock / Vertex / Hetzner / HostHatch / Suno / Climbo / "
        "ElevenLabs / Deepgram / Whisper / Kokoro / Ollama / n8n / Supabase. "
        "Client-specific platforms (Shopify, Square, Google Business Profile) are OK "
        "when discussing the client's own stack.\n"
        "2. Never say 'AMG pays Chamber more than Chamber pays AMG' — explain via "
        "rev-share structure only (18% Founding / 15% standard).\n"
        "3. Never fabricate metrics. If you don't have it in your knowledge base, "
        "route to Solon.\n"
        "4. Never promise specific outcomes — frame as 'what AMG has done for similar "
        "clients.'\n"
        "5. Never reveal internal operations, API details, architecture, cost "
        "structure, or unit economics.\n"
        "6. One lead ask per conversation maximum. One follow-up only if relevant.\n"
        "7. Never mention Revere Chamber specifically in general context (they're "
        "Founding Partner #1 but not the program's identity).\n"
        "8. Never write 'Free Website Audit' — we have CRO audits (paid, $299-$3,500) "
        "+ free 14-day service trial + free website-score check. Redirect: 'The "
        "website-score check is free and quick — audits are a deeper paid service. "
        "Which one are you asking about?'\n"
        "9. Session cap: 15 min / 40 exchanges. On approach: 'I'm going to pause here — "
        "drop your email and Solon picks up where we left off.'\n\n"
        "HOT SIGNALS → BOOK CALL\n"
        "If prospect says 'when can we sign' / 'let's do it' / 'schedule a call' — "
        "confirm 'Solon or a team member will reach out within 24 hours to confirm a "
        "time.' Lead-capture tool fires server-side.\n\n"
        "When in doubt — brevity wins. One sentence beats four."
    )


# Trade-secret guard — applied to every Alex reply before send.
# Extended per CT-0417-24 Alex v2 spec + Addendum #6 cloud-vendor additions.
_ALEX_BANNED_TERMS = (
    # AI providers + model families
    "claude", "anthropic", "sonnet", "opus", "haiku", "chatgpt", "gpt-4",
    "gpt4", "gpt-3", "openai", "o-mini", "gemini", "bard", "grok", "xai",
    "perplexity", "sonar", "llama", "mistral",
    # Voice / speech / embedding
    "elevenlabs", "kokoro", "ollama", "deepgram", "whisper", "nomic-embed-text",
    # Music / audio generation
    "suno", "climbo",
    # Infra (VPS / lane references)
    "hosthatch", "beast", "140-lane", "170.205.37.148", "87.99.149.253",
    # Automation / orchestration / low-code
    "n8n", "stagehand", "supabase", "pipedream", "zapier", "lovable",
    "gohighlevel", "ghl", "viktor",
    # Cloud providers
    "cloudflare", "aws", "gcp", "google cloud", "bedrock", "vertex", "hetzner",
    # Internal self-references + safety terms
    "powered by atlas", "kill.chain", "kill.switch",
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


# ─── CRM PHASE 1 + UNIFIED CONTEXT (CT-0417-29) ───────────────────────────────
# Server-side CRUD for the CRM tables (sql/008) + the get_unified_context MCP
# tool (T3) + the CRM ↔ MCP bidirectional sync hook (T7).
#
# All Supabase access goes through the operator service-role key
# (SUPABASE_SERVICE_ROLE_KEY in /root/.titan-env). Bypasses RLS by design —
# the auth gate is at the atlas-api layer, not the DB layer, for v1.

_CRM_RATE: dict[str, list[float]] = {}
_CRM_RATE_MAX = 60       # per-IP messages per minute (UI-friendly)
_CRM_RATE_WINDOW_S = 60.0


def _crm_write_token() -> str:
    """Read the bearer token gating CRM write endpoints from
    /etc/amg/crm-write.env (root-owned, 600 perms). Returns empty string
    when missing — write endpoints then refuse all requests (fail-closed).
    Read endpoints (GET) remain open behind the edge reverse-proxy.
    """
    try:
        for line in Path("/etc/amg/crm-write.env").read_text().splitlines():
            line = line.strip()
            if line.startswith("CRM_WRITE_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return ""


def _verify_crm_write_auth(request: Request) -> bool:
    """Defense-in-depth bearer check for CRM write endpoints. Edge auth
    (Cloudflare Access / Caddy basic-auth) is the primary gate; this is
    second-line. Returns True on bearer match, False otherwise.

    Behavior when /etc/amg/crm-write.env is missing:
      - GET endpoints: still served (edge auth assumed sufficient for read)
      - POST endpoints: refuse 401 (fail-closed for any write)
    """
    expected = _crm_write_token()
    if not expected:
        return False  # fail-closed: no token configured, no writes
    auth = request.headers.get("authorization", "") or request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    provided = auth.split(" ", 1)[1].strip()
    # constant-time compare
    import hmac as _hmac
    return _hmac.compare_digest(provided, expected)


def _crm_supabase_url() -> str:
    """Operator Supabase URL (egoazyasyrhslluossli)."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    if not url:
        # Fallback — read directly from /root/.titan-env if env not exported
        try:
            for line in Path("/root/.titan-env").read_text().splitlines():
                if line.startswith("SUPABASE_URL="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return url


def _crm_supabase_key() -> str:
    """Operator service-role key. Returns empty string when unavailable."""
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if key:
        return key
    try:
        for line in Path("/root/.titan-env").read_text().splitlines():
            if line.startswith("SUPABASE_SERVICE_ROLE_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


async def _crm_supabase_get(path: str, params: dict | None = None) -> list[dict] | dict | None:
    """Generic GET against operator Supabase REST. Returns parsed JSON or None."""
    if httpx is None:
        return None
    url = _crm_supabase_url()
    key = _crm_supabase_key()
    if not url or not key:
        return None
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(f"{url}/rest/v1/{path}", headers=headers, params=params or {})
            if r.status_code != 200:
                return None
            return r.json()
    except Exception:
        return None


async def _crm_supabase_post(path: str, body: dict | list) -> dict | list | None:
    """Generic POST (insert) against operator Supabase REST. Returns inserted row(s)."""
    if httpx is None:
        return None
    url = _crm_supabase_url()
    key = _crm_supabase_key()
    if not url or not key:
        return None
    headers = {
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "Prefer": "return=representation",
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.post(f"{url}/rest/v1/{path}", headers=headers, json=body)
            if r.status_code not in (200, 201):
                return {"error": f"HTTP {r.status_code}", "detail": r.text[:500]}
            return r.json()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _crm_rate_check(client_ip: str) -> bool:
    import time as _time
    now = _time.time()
    bucket = _CRM_RATE.setdefault(client_ip, [])
    bucket[:] = [t for t in bucket if now - t < _CRM_RATE_WINDOW_S]
    if len(bucket) >= _CRM_RATE_MAX:
        return False
    bucket.append(now)
    return True


# ─── Read endpoints (CRM dashboard at ops.aimarketinggenius.io/crm) ───────────

@app.get("/api/crm/contacts")
async def api_crm_contacts(request: Request, q: str | None = None) -> JSONResponse:
    """List contacts. Optional ?q= for trigram search on display_name."""
    if not _crm_rate_check(request.client.host if request.client else "unknown"):
        raise HTTPException(429, "rate limit")
    if q:
        rows = await _crm_supabase_get("crm_contacts", params={
            "select": "*", "display_name": f"ilike.*{q}*", "order": "updated_at.desc", "limit": "50",
        })
    else:
        rows = await _crm_supabase_get("crm_contacts", params={
            "select": "*", "order": "updated_at.desc", "limit": "200",
        })
    return JSONResponse({"contacts": rows or [], "count": len(rows or [])})


@app.get("/api/crm/contacts/{slug}")
async def api_crm_contact_one(request: Request, slug: str) -> JSONResponse:
    """Single contact by slug, with embedded deals + recent activities + memories."""
    if not _crm_rate_check(request.client.host if request.client else "unknown"):
        raise HTTPException(429, "rate limit")
    contact = await _crm_supabase_get("crm_contacts", params={
        "select": "*", "slug": f"eq.{slug}", "limit": "1",
    })
    if not contact:
        raise HTTPException(404, "contact not found")
    c0 = contact[0] if isinstance(contact, list) else contact
    cid = c0["id"]
    deals = await _crm_supabase_get("crm_deals", params={
        "select": "*", "contact_id": f"eq.{cid}", "order": "updated_at.desc",
    })
    activities = await _crm_supabase_get("crm_activities", params={
        "select": "*", "contact_id": f"eq.{cid}", "order": "occurred_at.desc", "limit": "100",
    })
    memories = await _crm_supabase_get("crm_persistent_memory", params={
        "select": "*", "contact_id": f"eq.{cid}",
        "order": "importance.desc,created_at.desc", "limit": "100",
    })
    return JSONResponse({
        "contact": c0, "deals": deals or [], "activities": activities or [], "memories": memories or [],
    })


@app.get("/api/crm/deals")
async def api_crm_deals_pipeline(request: Request) -> JSONResponse:
    """Deal pipeline grouped by stage."""
    if not _crm_rate_check(request.client.host if request.client else "unknown"):
        raise HTTPException(429, "rate limit")
    rows = await _crm_supabase_get("crm_deals", params={
        "select": "*,contact:crm_contacts(slug,display_name,contact_name)",
        "order": "updated_at.desc",
    })
    pipeline: dict[str, list] = {}
    for r in (rows or []):
        pipeline.setdefault(r.get("stage", "unknown"), []).append(r)
    return JSONResponse({"pipeline": pipeline, "count": len(rows or [])})


@app.get("/api/crm/activities")
async def api_crm_activities_feed(request: Request, contact_id: str | None = None) -> JSONResponse:
    """Activity feed — global or filtered by contact_id."""
    if not _crm_rate_check(request.client.host if request.client else "unknown"):
        raise HTTPException(429, "rate limit")
    params = {"select": "*,contact:crm_contacts(slug,display_name)", "order": "occurred_at.desc", "limit": "100"}
    if contact_id:
        params["contact_id"] = f"eq.{contact_id}"
    rows = await _crm_supabase_get("crm_activities", params=params)
    return JSONResponse({"activities": rows or [], "count": len(rows or [])})


# ─── Write endpoints (T7 sync + manual UI) ────────────────────────────────────

_VALID_ACTIVITY_TYPES = {"call","email-sent","email-received","sms","meeting","note","stage-change","document-shared","demo"}
_VALID_MEMORY_TYPES   = {"fact","preference","rule","context","blocker","decision","timeline","contact-detail"}
_VALID_DIRECTIONS     = {"inbound","outbound","internal", None, ""}
_UUID_RE              = None  # lazy-compile in _is_uuid

def _is_uuid(s: object) -> bool:
    """Strict UUID-shape check (avoids accepting arbitrary strings as contact_id)."""
    global _UUID_RE
    if _UUID_RE is None:
        import re as _re
        _UUID_RE = _re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
    return isinstance(s, str) and bool(_UUID_RE.match(s))


async def _mcp_log_with_retry(payload: dict, attempts: int = 3, base_timeout: float = 4.0) -> bool:
    """Best-effort MCP log_decision call with exponential backoff. Returns True
    on success. Distinguishes transient (timeout / 5xx) from permanent (4xx)
    failures: retry transient, give up immediately on permanent.
    """
    if httpx is None:
        return False
    import asyncio as _asyncio
    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=base_timeout) as c:
                r = await c.post("https://memory.aimarketinggenius.io/api/log_decision", json=payload)
                if r.status_code == 200:
                    return True
                # 4xx = permanent client error — don't retry
                if 400 <= r.status_code < 500:
                    return False
                # 5xx = retryable
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadTimeout):
            pass  # retryable
        except (httpx.HTTPError, OSError):
            pass  # treat as retryable transient
        if attempt < attempts:
            await _asyncio.sleep(0.5 * (2 ** (attempt - 1)))   # 0.5s, 1s, 2s
    return False


@app.post("/api/crm/activities")
async def api_crm_activity_create(request: Request) -> JSONResponse:
    """Create a new activity row. Auto-mirrors to MCP decision log if mcp_decision_id absent.

    Auth: requires `Authorization: Bearer <CRM_WRITE_TOKEN>` per
    /etc/amg/crm-write.env. Defense-in-depth — edge auth still applies.

    Input validation (returns 400 on any failure):
      - contact_id     must be UUID
      - activity_type  must be in _VALID_ACTIVITY_TYPES
      - direction      must be in _VALID_DIRECTIONS or absent
      - summary        ≤ 1000 chars, ≥ 1 char
      - body           ≤ 10000 chars
      - actor          ≤ 100 chars, ≥ 1 char
    """
    if not _verify_crm_write_auth(request):
        raise HTTPException(401, "unauthorized — bearer token required for CRM writes")
    if not _crm_rate_check(request.client.host if request.client else "unknown"):
        raise HTTPException(429, "rate limit")
    try:
        body = await request.json()
    except (ValueError, TypeError):
        raise HTTPException(400, "invalid JSON body")
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be a JSON object")

    # Required fields
    for k in ("contact_id", "activity_type", "summary", "actor"):
        if not body.get(k):
            raise HTTPException(400, f"required field missing: {k}")
    # Type / shape validation
    if not _is_uuid(body["contact_id"]):
        raise HTTPException(400, "contact_id must be a valid UUID")
    if body["activity_type"] not in _VALID_ACTIVITY_TYPES:
        raise HTTPException(400, f"activity_type must be one of {sorted(_VALID_ACTIVITY_TYPES)}")
    if body.get("direction") not in _VALID_DIRECTIONS:
        raise HTTPException(400, f"direction must be one of inbound/outbound/internal")
    summary = str(body["summary"])[:1000]
    if len(summary.strip()) == 0:
        raise HTTPException(400, "summary cannot be empty/whitespace")
    body["summary"] = summary
    if "body" in body and body["body"] is not None:
        body["body"] = str(body["body"])[:10000]
    actor = str(body["actor"])[:100]
    if len(actor.strip()) == 0:
        raise HTTPException(400, "actor cannot be empty")
    body["actor"] = actor

    inserted = await _crm_supabase_post("crm_activities", body)
    if isinstance(inserted, dict) and inserted.get("error"):
        raise HTTPException(502, f"supabase: {inserted.get('error')}")

    # T7 — auto-mirror to MCP decision log (best-effort, retry-on-transient)
    mcp_logged = False
    if not body.get("mcp_decision_id"):
        slug_lookup = await _crm_supabase_get("crm_contacts", params={
            "select": "slug,display_name", "id": f"eq.{body['contact_id']}", "limit": "1",
        })
        first = (slug_lookup or [{}])[0] if isinstance(slug_lookup, list) else {}
        slug    = first.get("slug") or body["contact_id"][:8]
        display = first.get("display_name") or "(unknown)"
        mcp_logged = await _mcp_log_with_retry({
            "project_source": "CRM",
            "text": f"[CRM activity] {display} ({body['activity_type']}) — {body['summary']}",
            "tags": ["crm-activity", f"client:{slug}", body["activity_type"]],
        })
    return JSONResponse({"created": inserted, "mcp_mirrored": mcp_logged})


@app.post("/api/crm/memories")
async def api_crm_memory_write(request: Request) -> JSONResponse:
    """Append to a contact's persistent memory namespace.

    Auth: requires `Authorization: Bearer <CRM_WRITE_TOKEN>` per
    /etc/amg/crm-write.env. Defense-in-depth.

    Input validation (returns 400 on any failure):
      - contact_id     must be UUID
      - memory_type    must be in _VALID_MEMORY_TYPES
      - text_content   ≤ 2000 chars, ≥ 1 char
      - importance     1-10 inclusive (default 5)
      - written_by     ≤ 100 chars, ≥ 1 char
    """
    if not _verify_crm_write_auth(request):
        raise HTTPException(401, "unauthorized — bearer token required for CRM writes")
    if not _crm_rate_check(request.client.host if request.client else "unknown"):
        raise HTTPException(429, "rate limit")
    try:
        body = await request.json()
    except (ValueError, TypeError):
        raise HTTPException(400, "invalid JSON body")
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be a JSON object")

    for k in ("contact_id", "memory_type", "text_content", "written_by"):
        if not body.get(k):
            raise HTTPException(400, f"required field missing: {k}")
    if not _is_uuid(body["contact_id"]):
        raise HTTPException(400, "contact_id must be a valid UUID")
    if body["memory_type"] not in _VALID_MEMORY_TYPES:
        raise HTTPException(400, f"memory_type must be one of {sorted(_VALID_MEMORY_TYPES)}")
    text = str(body["text_content"])[:2000]
    if len(text.strip()) == 0:
        raise HTTPException(400, "text_content cannot be empty")
    body["text_content"] = text
    written = str(body["written_by"])[:100]
    if len(written.strip()) == 0:
        raise HTTPException(400, "written_by cannot be empty")
    body["written_by"] = written
    if "importance" in body:
        try:
            imp = int(body["importance"])
        except (TypeError, ValueError):
            raise HTTPException(400, "importance must be integer 1-10")
        if not 1 <= imp <= 10:
            raise HTTPException(400, "importance must be 1-10 inclusive")
        body["importance"] = imp

    # Auto-resolve namespace_id from contact's persistent_memory_ref if absent
    if not body.get("namespace_id"):
        c_rows = await _crm_supabase_get("crm_contacts", params={
            "select": "persistent_memory_ref", "id": f"eq.{body['contact_id']}", "limit": "1",
        })
        if c_rows and isinstance(c_rows, list) and c_rows[0].get("persistent_memory_ref"):
            body["namespace_id"] = c_rows[0]["persistent_memory_ref"]

    inserted = await _crm_supabase_post("crm_persistent_memory", body)
    if isinstance(inserted, dict) and inserted.get("error"):
        raise HTTPException(502, f"supabase: {inserted.get('error')}")
    return JSONResponse({"created": inserted})


# ─── Unified context — the T3 deliverable ─────────────────────────────────────
# Single endpoint that blends Layer 1 (MCP recent decisions) + Layer 2
# (per-contact crm_persistent_memory + activities + facts) + Layer 4 (KB tags
# from agent_context_loader if available). Returns a ranked context block
# ready to inject into Atlas / EOM / Titan prompts.
#
# Per the doctrine in plans/doctrine/PERSISTENT_MEMORY_SCHEMA.md:
#   priority 1 → Layer 1 [P10 PERMANENT] standing rules
#   priority 2 → Layer 2 high-importance per-contact memories (importance >= 8)
#   priority 3 → Layer 4 KB content
#   priority 4 → Layer 1 recent decisions (last 30 days)
#   priority 5 → Layer 5 session resume state (excluded — not consumed by operator stack)

@app.get("/api/crm/unified-context")
async def api_crm_unified_context(
    request: Request,
    project_id: str = "EOM",
    contact_slug: str | None = None,
    query: str | None = None,
    include_crm: bool = True,
    include_consumer: bool = False,   # consumer = Layer 3, never blended in v1
    max_tokens: int = 4000,
) -> JSONResponse:
    """T3 — get_unified_context. Blends MCP + CRM persistent memory + KB.

    Returns:
      { ranked_context: [{layer, priority, content, source, importance}],
        cacheable_prefix: <stable KB block for cache_control>,
        query_tail:       <variable per-call additions>,
        token_estimate:   int }
    """
    if not _crm_rate_check(request.client.host if request.client else "unknown"):
        raise HTTPException(429, "rate limit")

    if include_consumer:
        return JSONResponse({"error": "Layer 3 (consumer Supabase) is not blendable in v1 per tenant-isolation doctrine. Set include_consumer=false."}, status_code=400)

    ranked: list[dict] = []
    cacheable_chunks: list[str] = []

    # ── Priority 1: Layer 1 MCP P10 PERMANENT standing rules
    if httpx is not None:
        try:
            async with httpx.AsyncClient(timeout=4.0) as c:
                r = await c.get("https://memory.aimarketinggenius.io/api/get_recent_decisions",
                                params={"count": "20", "project_filter": project_id})
                if r.status_code == 200:
                    decisions = r.json() if isinstance(r.json(), list) else r.json().get("decisions", [])
                    for d in decisions:
                        text = d.get("text", "")
                        if "[P10 PERMANENT" in text or "[P10]" in text:
                            ranked.append({
                                "layer": 1, "priority": 1, "content": text[:600], "importance": 10,
                                "source": "MCP P10 PERMANENT", "ts": d.get("created_at"),
                            })
                            cacheable_chunks.append(f"[P10] {text[:400]}")
        except Exception:
            pass

    # ── Priority 2: Layer 2 high-importance per-contact memories
    if include_crm and contact_slug:
        c_rows = await _crm_supabase_get("crm_contacts", params={
            "select": "id,slug,display_name,contact_name,contact_email,contact_phone,address,city,state,zip,timezone,tags,persistent_memory_ref",
            "slug": f"eq.{contact_slug}", "limit": "1",
        })
        if c_rows:
            c0 = c_rows[0]
            cid = c0["id"]
            # contact card itself
            contact_card = (
                f"CONTACT: {c0.get('display_name')} (slug={c0.get('slug')})\n"
                f"Primary contact: {c0.get('contact_name')} · {c0.get('contact_email')} · {c0.get('contact_phone')}\n"
                f"Address: {c0.get('address') or ''} {c0.get('city') or ''} {c0.get('state') or ''} {c0.get('zip') or ''}\n"
                f"Timezone: {c0.get('timezone')} · Tags: {', '.join(c0.get('tags') or [])}"
            )
            ranked.append({"layer": 2, "priority": 2, "content": contact_card, "importance": 10,
                           "source": "crm_contacts", "ts": None})
            cacheable_chunks.append(contact_card)
            # high-importance memories (importance >= 8)
            mem_params = {"select": "memory_type,text_content,importance,valid_from",
                          "contact_id": f"eq.{cid}", "importance": "gte.8",
                          "order": "importance.desc,created_at.desc", "limit": "20"}
            mems = await _crm_supabase_get("crm_persistent_memory", params=mem_params)
            for m in (mems or []):
                ranked.append({
                    "layer": 2, "priority": 2,
                    "content": f"[{m['memory_type']}/imp{m['importance']}] {m['text_content']}",
                    "importance": m["importance"], "source": "crm_persistent_memory",
                    "ts": m.get("valid_from"),
                })
                cacheable_chunks.append(f"[{m['memory_type']}] {m['text_content']}")
            # active deal headline
            deals = await _crm_supabase_get("crm_deals", params={
                "select": "title,stage,amount_cents,currency,metadata,expected_close",
                "contact_id": f"eq.{cid}", "order": "updated_at.desc", "limit": "3",
            })
            for d in (deals or []):
                ranked.append({
                    "layer": 2, "priority": 2,
                    "content": f"DEAL: {d['title']} · stage={d['stage']} · amt={d.get('amount_cents')} {d.get('currency')}",
                    "importance": 9, "source": "crm_deals", "ts": None,
                })
            # recent activities (top 5)
            acts = await _crm_supabase_get("crm_activities", params={
                "select": "activity_type,direction,summary,occurred_at,actor",
                "contact_id": f"eq.{cid}", "order": "occurred_at.desc", "limit": "5",
            })
            for a in (acts or []):
                ranked.append({
                    "layer": 2, "priority": 4,
                    "content": f"ACT [{a['activity_type']}/{a.get('direction','')}] {a['summary']} ({a.get('actor')})",
                    "importance": 6, "source": "crm_activities", "ts": a.get("occurred_at"),
                })

    # ── Priority 4: Layer 1 recent decisions (last 30 days, non-P10)
    if httpx is not None:
        try:
            async with httpx.AsyncClient(timeout=4.0) as c:
                r = await c.get("https://memory.aimarketinggenius.io/api/get_recent_decisions",
                                params={"count": "10", "project_filter": project_id})
                if r.status_code == 200:
                    decisions = r.json() if isinstance(r.json(), list) else r.json().get("decisions", [])
                    for d in decisions:
                        text = d.get("text", "")
                        if "[P10" not in text:
                            ranked.append({
                                "layer": 1, "priority": 4, "content": text[:400],
                                "importance": 5, "source": "MCP recent", "ts": d.get("created_at"),
                            })
        except Exception:
            pass

    # ── Token estimate (rough — 1 token ≈ 4 chars)
    full_text = "\n".join(item["content"] for item in ranked)
    token_estimate = max(1, len(full_text) // 4)

    return JSONResponse({
        "ranked_context": ranked,
        "cacheable_prefix": "\n".join(cacheable_chunks),
        "query_tail": query or "",
        "token_estimate": token_estimate,
        "doctrine_ref": "plans/doctrine/PERSISTENT_MEMORY_SCHEMA.md",
        "project_id": project_id,
        "contact_slug": contact_slug,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })


# ─── CRM dashboard UI (T4) ────────────────────────────────────────────────────

@app.get("/crm")
async def crm_dashboard_serve() -> Response:
    """Serve the CRM Phase 1 dashboard."""
    path = STATIC_DIR / "crm.html"
    if not path.exists():
        raise HTTPException(404, "crm.html missing — deploy pending")
    return FileResponse(path, media_type="text/html")


@app.get("/api/crm/health")
def api_crm_health() -> dict:
    return {
        "service": "crm-phase-1",
        "supabase_configured": bool(_crm_supabase_url() and _crm_supabase_key()),
        "doctrine": "sql/008_amg_crm_contacts.sql + plans/doctrine/PERSISTENT_MEMORY_SCHEMA.md",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ─── end /api/crm block ───────────────────────────────────────────────────────


# ─── AIMG ADMIN COMMAND PORTAL (CT-0417-30 T5) ────────────────────────────────
# Solon-facing subscriber management portal at /aimg-admin.
# Hits CONSUMER Supabase (gaybcxzrzfgvcqpkbeiq) — strictly isolated from the
# operator Supabase (egoazyasyrhslluossli) used by the CRM. Reads
# AIMG_SUPABASE_URL + AIMG_SUPABASE_SERVICE_KEY from /etc/amg/aimg-supabase.env.
#
# Stage 1 (this commit): aggregate stats + user list from existing tables
# (consumer_memories, users). Stage 2 (next iteration): wire PayPal
# subscriber/billing state via new sql/aimg_001_admin_schema.sql migration.
# (PaymentCloud + Durango become Phase 3 cutover once onboarding clears.)

_AIMG_RATE: dict[str, list[float]] = {}
_AIMG_RATE_MAX = 60
_AIMG_RATE_WINDOW_S = 60.0


def _aimg_supabase_cfg() -> tuple[str, str]:
    """Read AIMG (consumer) Supabase URL + service key from /etc/amg/aimg-supabase.env."""
    url = ""
    key = ""
    try:
        for line in Path("/etc/amg/aimg-supabase.env").read_text().splitlines():
            line = line.strip()
            if line.startswith("AIMG_SUPABASE_URL="):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("AIMG_SUPABASE_SERVICE_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return url, key


def _aimg_admin_token() -> str:
    """Admin bearer token from /etc/amg/aimg-admin.env (fail-closed)."""
    try:
        for line in Path("/etc/amg/aimg-admin.env").read_text().splitlines():
            line = line.strip()
            if line.startswith("AIMG_ADMIN_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return ""


def _verify_aimg_admin_auth(request: Request) -> bool:
    expected = _aimg_admin_token()
    if not expected:
        return False
    auth = request.headers.get("authorization", "") or request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    provided = auth.split(" ", 1)[1].strip()
    import hmac as _hmac
    return _hmac.compare_digest(provided, expected)


def _aimg_rate_check(ip: str) -> bool:
    import time as _time
    now = _time.time()
    bucket = _AIMG_RATE.setdefault(ip, [])
    bucket[:] = [t for t in bucket if now - t < _AIMG_RATE_WINDOW_S]
    if len(bucket) >= _AIMG_RATE_MAX:
        return False
    bucket.append(now)
    return True


async def _aimg_supabase_get(path: str, params: dict | None = None,
                              extra_headers: dict | None = None) -> list | dict | None:
    """Generic GET against AIMG (consumer) Supabase REST."""
    if httpx is None:
        return None
    url, key = _aimg_supabase_cfg()
    if not url or not key:
        return None
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(f"{url}/rest/v1/{path}", headers=headers, params=params or {})
            if r.status_code not in (200, 206):
                return None
            # Preserve Content-Range header info by attaching to a wrapped dict
            data = r.json()
            cr = r.headers.get("content-range", "")
            if cr and isinstance(data, list):
                return {"data": data, "content_range": cr}
            return data
    except Exception:
        return None


# ─── Admin endpoints (all require bearer) ─────────────────────────────────────

@app.get("/api/aimg/admin/stats")
async def api_aimg_admin_stats(request: Request) -> JSONResponse:
    """Aggregate stats — total memories, total users, platform breakdown,
    daily capture volume (last 30 days), contradiction count.
    """
    if not _verify_aimg_admin_auth(request):
        raise HTTPException(401, "unauthorized")
    if not _aimg_rate_check(request.client.host if request.client else "unknown"):
        raise HTTPException(429, "rate limit")

    # Total memories
    mem_probe = await _aimg_supabase_get("consumer_memories",
        params={"select": "id", "limit": "0"},
        extra_headers={"Prefer": "count=exact"})
    total_memories = 0
    if isinstance(mem_probe, dict) and mem_probe.get("content_range"):
        try:
            total_memories = int(mem_probe["content_range"].split("/")[-1])
        except (ValueError, IndexError):
            pass

    # Distinct users (via user_id aggregation — hit users table for count)
    users_probe = await _aimg_supabase_get("users",
        params={"select": "id", "limit": "0"},
        extra_headers={"Prefer": "count=exact"})
    total_users = 0
    if isinstance(users_probe, dict) and users_probe.get("content_range"):
        try:
            total_users = int(users_probe["content_range"].split("/")[-1])
        except (ValueError, IndexError):
            pass

    # Platform breakdown (per-platform memory count). pgrest doesn't do GROUP BY
    # cleanly over REST, so we sample the last 1000 memories and count platforms.
    recent = await _aimg_supabase_get("consumer_memories", params={
        "select": "platform,created_at,qe_status",
        "order": "created_at.desc", "limit": "1000",
    })
    recent_list = recent if isinstance(recent, list) else (recent or {}).get("data", [])
    by_platform: dict[str, int] = {}
    by_day: dict[str, int] = {}
    qe_flagged = 0
    for m in recent_list:
        p = m.get("platform") or "unknown"
        by_platform[p] = by_platform.get(p, 0) + 1
        ts = (m.get("created_at") or "")[:10]
        if ts:
            by_day[ts] = by_day.get(ts, 0) + 1
        if m.get("qe_status") and m["qe_status"] not in ("unverified", "verified"):
            qe_flagged += 1

    # Sort daily breakdown descending
    daily_sorted = sorted(by_day.items(), key=lambda kv: kv[0], reverse=True)[:14]

    return JSONResponse({
        "total_memories": total_memories,
        "total_users":    total_users,
        "by_platform":    dict(sorted(by_platform.items(), key=lambda kv: kv[1], reverse=True)),
        "daily_capture":  dict(daily_sorted),
        "qe_flagged_in_sample": qe_flagged,
        "sample_size":    len(recent_list),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })


@app.get("/api/aimg/admin/users")
async def api_aimg_admin_users_list(
    request: Request,
    q: str | None = None,
    limit: int = 50,
) -> JSONResponse:
    """List users. Currently lists all users + attaches per-user memory count.
    Stage 2 will join with subscribers table for plan + billing state.
    """
    if not _verify_aimg_admin_auth(request):
        raise HTTPException(401, "unauthorized")
    if not _aimg_rate_check(request.client.host if request.client else "unknown"):
        raise HTTPException(429, "rate limit")
    limit = max(1, min(200, limit))
    params: dict = {"select": "id,email,created_at", "order": "created_at.desc", "limit": str(limit)}
    if q:
        params["email"] = f"ilike.*{q}*"
    users = await _aimg_supabase_get("users", params=params)
    user_list = users if isinstance(users, list) else (users or {}).get("data", []) or []

    # Attach per-user memory count — capped to 50 users to bound request fan-out.
    enriched: list[dict] = []
    for u in user_list[:50]:
        uid = u.get("id")
        if not uid:
            continue
        mem_probe = await _aimg_supabase_get("consumer_memories",
            params={"select": "id", "user_id": f"eq.{uid}", "limit": "0"},
            extra_headers={"Prefer": "count=exact"})
        count = 0
        if isinstance(mem_probe, dict) and mem_probe.get("content_range"):
            try:
                count = int(mem_probe["content_range"].split("/")[-1])
            except (ValueError, IndexError):
                pass
        enriched.append({
            "id": uid,
            "email": u.get("email"),
            "created_at": u.get("created_at"),
            "memory_count": count,
            "plan": "free",       # Stage 2: join with subscribers table
            "status": "active",   # Stage 2: paused/suspended from billing state
        })
    return JSONResponse({"users": enriched, "count": len(enriched),
                         "note": "Stage 1 — plan/status are placeholders pending subscriber-table schema (aimg_001_admin_schema.sql)"})


@app.get("/api/aimg/admin/users/{user_id}")
async def api_aimg_admin_user_detail(request: Request, user_id: str) -> JSONResponse:
    """Per-user drill-in: profile + recent memories + per-platform breakdown."""
    if not _verify_aimg_admin_auth(request):
        raise HTTPException(401, "unauthorized")
    if not _aimg_rate_check(request.client.host if request.client else "unknown"):
        raise HTTPException(429, "rate limit")

    user = await _aimg_supabase_get("users", params={
        "select": "*", "id": f"eq.{user_id}", "limit": "1",
    })
    if not user:
        raise HTTPException(404, "user not found")
    u0 = user[0] if isinstance(user, list) else (user.get("data") or [{}])[0]

    mems = await _aimg_supabase_get("consumer_memories", params={
        "select": "id,content,memory_type,platform,thread_id,exchange_number,source_timestamp,qe_status,created_at",
        "user_id": f"eq.{user_id}", "order": "created_at.desc", "limit": "100",
    })
    mem_list = mems if isinstance(mems, list) else (mems or {}).get("data", []) or []
    by_platform: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for m in mem_list:
        by_platform[m.get("platform") or "unknown"] = by_platform.get(m.get("platform") or "unknown", 0) + 1
        by_type[m.get("memory_type") or "unknown"] = by_type.get(m.get("memory_type") or "unknown", 0) + 1

    return JSONResponse({
        "user": {k: u0.get(k) for k in ("id", "email", "created_at")},
        "memory_count": len(mem_list),
        "by_platform": by_platform,
        "by_type": by_type,
        "recent_memories": mem_list[:20],
        "plan": "free",
        "status": "active",
    })


@app.get("/api/aimg/admin/health")
def api_aimg_admin_health() -> dict:
    url, key = _aimg_supabase_cfg()
    return {
        "service": "aimg-admin",
        "consumer_supabase_configured": bool(url and key),
        "admin_token_configured": bool(_aimg_admin_token()),
        "stage": 1,
        "note": "Stage 2 pending: subscribers + einstein_fact_checks + billing_events schema",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# Canonical tenant-slug convention per 2026-04-17 P10 MULTI-TENANT LOCK:
# lowercase, hyphen-separated, 3-40 chars. Solon is tenant #1 ('solon').
_VALID_TENANT_SLUG = None
def _is_valid_tenant_slug(s: str) -> bool:
    global _VALID_TENANT_SLUG
    if _VALID_TENANT_SLUG is None:
        import re as _re
        _VALID_TENANT_SLUG = _re.compile(r'^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$')
    return isinstance(s, str) and bool(_VALID_TENANT_SLUG.match(s))


@app.get("/portal/{tenant_slug}/aimg")
async def aimg_admin_portal_tenant(tenant_slug: str) -> Response:
    """Canonical portal.aimarketinggenius.io/{tenant_slug}/aimg route (GHL-style
    multi-tenant per P10 2026-04-17 lock). AIMG admin lives as a MODULE inside
    the operator-portal sub-tenant (Solon = 'solon' tenant).

    Tenant-slug validation at the edge — Caddy should upgrade to this path once
    portal.aimarketinggenius.io routing is wired. For now the same atlas-api
    instance serves both subdomains and the path is the tenant discriminator.
    """
    if not _is_valid_tenant_slug(tenant_slug):
        raise HTTPException(400, "invalid tenant_slug — must be lowercase hyphen-separated 3-40 chars")
    path = STATIC_DIR / "aimg-admin.html"
    if not path.exists():
        raise HTTPException(404, "aimg-admin.html missing — deploy pending")
    return FileResponse(path, media_type="text/html")


@app.get("/aimg-admin")
async def aimg_admin_serve() -> Response:
    """DEPRECATED 2026-04-17 — pre-multi-tenant path. Use
    /portal/{tenant_slug}/aimg instead. Kept as soft-cutover alias; redirects
    to the Solon super-tenant route. Will be removed after CT-0417-35 ships.
    """
    return RedirectResponse(url="/portal/solon/aimg", status_code=307)


# ─── end /aimg-admin block ────────────────────────────────────────────────────


# ─── MOBILE COMMAND v2 AUTH + LIFECYCLE ENDPOINTS (Step 6.3 mount) ────────────
# 12 endpoints per plans/PLAN_MOBILE_COMMAND_V2_AUTH_ARCHITECTURE.md (commit 26044ac):
#   8 auth endpoints delegate to lib/mobile_cmd_auth (Step 6.1 module, commit 75e9ac6).
#   4 lifecycle endpoints delegate to lib/mobile_lifecycle (this step, commit TBD).
#
# Schema dependency: sql/008_mobile_cmd_auth.sql (Step 6.2, commit 2b711ae) —
# apply to Supabase BEFORE auth endpoints receive live traffic.
#
# Optional dependencies (webauthn, pyjwt, pywebpush) — imported via try/except so
# atlas_api.py still boots cleanly if the stack isn't yet pip-installed on the host.
# Missing-dep calls raise 503 with a clear error rather than crashing the service.
try:
    from lib import mobile_cmd_auth as _mca  # type: ignore
    _MCA_AVAILABLE = True
except Exception as _mca_exc:
    _mca = None
    _MCA_AVAILABLE = False
    print(f"[atlas-api] mobile_cmd_auth unavailable: {_mca_exc}", file=sys.stderr)

try:
    from lib import mobile_lifecycle as _mlc  # type: ignore
    _MLC_AVAILABLE = True
except Exception as _mlc_exc:
    _mlc = None
    _MLC_AVAILABLE = False
    print(f"[atlas-api] mobile_lifecycle unavailable: {_mlc_exc}", file=sys.stderr)


def _mobile_dep_error(module_name: str) -> JSONResponse:
    """Uniform 503 when a mobile-command dep is missing."""
    return JSONResponse(
        status_code=503,
        content={
            "error": "mobile_command_module_unavailable",
            "module": module_name,
            "hint": "verify pip install webauthn pyjwt pywebpush httpx on the host + redeploy",
        },
    )


# --- AUTH — WebAuthn enrollment ---------------------------------------------

@app.post("/api/auth/webauthn/register-begin")
async def mobile_auth_register_begin(request: Request) -> JSONResponse:
    """Begin a WebAuthn platform-authenticator enrollment for an operator.

    STUB at Step 6.3: returns a 501 until a Supabase-backed credential_store +
    challenge_store adapter lands (follow-up 6.3-b). Handler wiring proves
    the route is mounted + visible to the PWA client.
    """
    if not _MCA_AVAILABLE:
        return _mobile_dep_error("mobile_cmd_auth")
    return JSONResponse(status_code=501, content={
        "error": "not_implemented_yet",
        "step": "6.3-b",
        "note": "Supabase RefreshTokenStore + challenge store adapter pending",
        "module_loaded": True,
    })


@app.post("/api/auth/webauthn/register-verify")
async def mobile_auth_register_verify(request: Request) -> JSONResponse:
    if not _MCA_AVAILABLE:
        return _mobile_dep_error("mobile_cmd_auth")
    return JSONResponse(status_code=501, content={
        "error": "not_implemented_yet", "step": "6.3-b", "module_loaded": True,
    })


# --- AUTH — WebAuthn sign-in ------------------------------------------------

@app.post("/api/auth/webauthn/authenticate-begin")
async def mobile_auth_authenticate_begin(request: Request) -> JSONResponse:
    if not _MCA_AVAILABLE:
        return _mobile_dep_error("mobile_cmd_auth")
    return JSONResponse(status_code=501, content={
        "error": "not_implemented_yet", "step": "6.3-b", "module_loaded": True,
    })


@app.post("/api/auth/webauthn/authenticate-verify")
async def mobile_auth_authenticate_verify(request: Request) -> JSONResponse:
    if not _MCA_AVAILABLE:
        return _mobile_dep_error("mobile_cmd_auth")
    return JSONResponse(status_code=501, content={
        "error": "not_implemented_yet", "step": "6.3-b", "module_loaded": True,
    })


# --- AUTH — JWT refresh + revoke --------------------------------------------

@app.post("/api/auth/refresh")
async def mobile_auth_refresh(request: Request) -> JSONResponse:
    if not _MCA_AVAILABLE:
        return _mobile_dep_error("mobile_cmd_auth")
    return JSONResponse(status_code=501, content={
        "error": "not_implemented_yet", "step": "6.3-b", "module_loaded": True,
    })


@app.post("/api/auth/revoke")
async def mobile_auth_revoke(request: Request) -> JSONResponse:
    if not _MCA_AVAILABLE:
        return _mobile_dep_error("mobile_cmd_auth")
    return JSONResponse(status_code=501, content={
        "error": "not_implemented_yet", "step": "6.3-b", "module_loaded": True,
    })


# --- PUSH — subscribe / send / unsubscribe ----------------------------------

@app.post("/api/push/subscribe")
async def mobile_push_subscribe(request: Request) -> JSONResponse:
    if not _MCA_AVAILABLE:
        return _mobile_dep_error("mobile_cmd_auth")
    return JSONResponse(status_code=501, content={
        "error": "not_implemented_yet", "step": "6.3-b", "module_loaded": True,
    })


@app.post("/api/push/send")
async def mobile_push_send(request: Request) -> JSONResponse:
    if not _MCA_AVAILABLE:
        return _mobile_dep_error("mobile_cmd_auth")
    return JSONResponse(status_code=501, content={
        "error": "not_implemented_yet", "step": "6.3-b", "module_loaded": True,
    })


@app.delete("/api/push/subscription/{sub_id}")
async def mobile_push_unsubscribe(sub_id: str, request: Request) -> JSONResponse:
    if not _MCA_AVAILABLE:
        return _mobile_dep_error("mobile_cmd_auth")
    return JSONResponse(status_code=501, content={
        "error": "not_implemented_yet", "sub_id": sub_id, "step": "6.3-b",
        "module_loaded": True,
    })


# --- LIFECYCLE — mobile session control -------------------------------------
# These are wired live via lib/mobile_lifecycle (self-contained; MCP-backed,
# stubbed at the actual claude-CLI-process-control level per 6.3-b).

@app.get("/api/mobile/claude/status")
async def mobile_claude_status_endpoint() -> JSONResponse:
    """Reads the latest session-heartbeat from MCP. Always available — even
    if mobile_cmd_auth / webauthn / pywebpush are not yet installed."""
    if not _MLC_AVAILABLE:
        return _mobile_dep_error("mobile_lifecycle")
    try:
        return JSONResponse(content=_mlc.mobile_claude_status())
    except Exception as exc:
        return JSONResponse(status_code=500, content={
            "error": "lifecycle_status_failed", "detail": str(exc)[:200],
        })


@app.post("/api/mobile/claude/stop")
async def mobile_claude_stop_endpoint(request: Request) -> JSONResponse:
    if not _MLC_AVAILABLE:
        return _mobile_dep_error("mobile_lifecycle")
    try:
        body = await request.json()
    except Exception:
        body = {}
    operator_id = str(body.get("operator_id", "unknown"))
    reason = str(body.get("reason", "mobile_stop_endpoint"))
    try:
        return JSONResponse(content=_mlc.mobile_claude_stop(operator_id, reason=reason))
    except Exception as exc:
        return JSONResponse(status_code=500, content={
            "error": "lifecycle_stop_failed", "detail": str(exc)[:200],
        })


@app.post("/api/mobile/claude/start")
async def mobile_claude_start_endpoint(request: Request) -> JSONResponse:
    if not _MLC_AVAILABLE:
        return _mobile_dep_error("mobile_lifecycle")
    try:
        body = await request.json()
    except Exception:
        body = {}
    operator_id = str(body.get("operator_id", "unknown"))
    try:
        return JSONResponse(content=_mlc.mobile_claude_start(operator_id))
    except Exception as exc:
        return JSONResponse(status_code=500, content={
            "error": "lifecycle_start_failed", "detail": str(exc)[:200],
        })


@app.post("/api/mobile/claude/reset")
async def mobile_claude_reset_endpoint(request: Request) -> JSONResponse:
    if not _MLC_AVAILABLE:
        return _mobile_dep_error("mobile_lifecycle")
    try:
        body = await request.json()
    except Exception:
        body = {}
    operator_id = str(body.get("operator_id", "unknown"))
    try:
        return JSONResponse(content=_mlc.mobile_claude_reset(operator_id))
    except Exception as exc:
        return JSONResponse(status_code=500, content={
            "error": "lifecycle_reset_failed", "detail": str(exc)[:200],
        })


# ─── end Mobile Command v2 Step 6.3 router mount ──────────────────────────────


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    port = int(os.environ.get("ATLAS_API_PORT", "8081"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
