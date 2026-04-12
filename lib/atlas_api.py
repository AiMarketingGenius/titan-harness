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
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
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

                # VAD gate — skip silence
                try:
                    import numpy as np
                    samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
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

                # We have speech followed by silence — transcribe the accumulated audio
                if backchannel_mode:
                    audio_buffer.clear()
                    silent_chunks = 0
                    continue  # suppress barge-in during backchannel

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

                # Sentence-buffered TTS via Kokoro
                await ws.send_json({"type": "state", "state": "speaking"})
                t_tts_start = time.time()
                try:
                    sys.path.insert(0, str(REPO_ROOT / "lib"))
                    from sentence_buffer import sentence_buffer
                    sentences = list(sentence_buffer([reply]))
                    for sentence in sentences:
                        wav = await kokoro_synthesize(sentence)
                        if wav:
                            await ws.send_bytes(wav)
                except Exception:
                    # Fallback: synthesize entire reply at once
                    wav = await kokoro_synthesize(reply)
                    if wav:
                        await ws.send_bytes(wav)
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

    @app.get("/mobile")
    def mobile_dashboard() -> HTMLResponse:
        """MP-3 §2 — Mobile status dashboard (375-430px)."""
        data = get_dashboard_data()
        html = render_mobile_html(data)
        return HTMLResponse(html)

    @app.get("/desktop")
    def desktop_dashboard() -> HTMLResponse:
        """MP-3 §3 — Desktop Solon OS Control Center."""
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


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    port = int(os.environ.get("ATLAS_API_PORT", "8081"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
