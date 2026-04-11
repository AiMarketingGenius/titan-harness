"""
lib/whisper_cpu.py — Hermes Phase A Step 5

CPU-only wrapper around `faster_whisper` using the `medium.en` int8 model.
Runs ~2× real-time on modern x86, which covers the ≤1s transcription target
for 2-second chunks. English-only; do NOT use for phone-call streaming
(per doctrine red line — that path uses Deepgram Flux in Phase B).

Doctrine reference: plans/DOCTRINE_VOICE_AI_STACK_v1.0.md §"(b) STT" —
faster-whisper for app/desktop, Silero VAD gating against hallucinations,
1-2s chunks, overlap-and-dedupe on chunk boundaries.

Downscope rationale (plan §3 decision log): large-v3-turbo on CPU is
~0.5× real-time, unusable for streaming; medium.en at int8 hits ~2× real
time while staying within the English-demo scope.

Public API:
    transcribe(audio_path_or_samples, sample_rate=16000) -> str

Self-test:
    python3 -m lib.whisper_cpu --self-test [PATH_TO_WAV]
"""

from __future__ import annotations

import sys
import time
import wave
from pathlib import Path

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover
    raise ImportError("numpy is required for lib.whisper_cpu") from exc

try:
    from faster_whisper import WhisperModel
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "faster-whisper is not installed; run `pip install faster-whisper`"
    ) from exc

_MODEL: "WhisperModel | None" = None
_MODEL_NAME = "medium.en"
_COMPUTE_TYPE = "int8"


def _model() -> "WhisperModel":
    global _MODEL
    if _MODEL is None:
        _MODEL = WhisperModel(_MODEL_NAME, device="cpu", compute_type=_COMPUTE_TYPE)
    return _MODEL


def transcribe(audio, *, language: str = "en", beam_size: int = 1) -> str:
    """Transcribe *audio* (path str/Path or float32 numpy array) to a plain
    string. Uses beam_size=1 for latency; callers that want higher accuracy
    at the cost of wall time can pass beam_size=5.

    Silence gating should be done UPSTREAM by lib.silero_vad — this function
    assumes the caller has already confirmed speech presence, to avoid the
    documented silence-hallucination failure mode.
    """
    model = _model()
    segments, _info = model.transcribe(
        audio,
        language=language,
        beam_size=beam_size,
        vad_filter=False,  # Silero handles this upstream
        word_timestamps=False,
        condition_on_previous_text=False,
    )
    return " ".join(seg.text.strip() for seg in segments).strip()


# ─── self-test ────────────────────────────────────────────────────────────────

def _load_wav_as_mono_16k(path: Path) -> "np.ndarray":
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        n = wf.getnframes()
        raw = wf.readframes(n)
    if sampwidth != 2:
        raise ValueError(f"Only 16-bit PCM WAV is supported in the self-test (got {sampwidth*8}-bit)")
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        arr = arr.reshape(-1, channels).mean(axis=1)
    if sr != 16000:
        ratio = 16000 / sr
        new_len = int(len(arr) * ratio)
        x_old = np.linspace(0.0, 1.0, num=len(arr), endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=new_len, endpoint=False)
        arr = np.interp(x_new, x_old, arr).astype(np.float32)
    return arr


def _self_test(argv: list[str]) -> int:
    wav_path = Path(argv[0]) if argv else Path("/tmp/hermes_smoke.wav")
    if not wav_path.exists():
        print(f"FAIL  fixture missing: {wav_path}", file=sys.stderr)
        return 1

    samples = _load_wav_as_mono_16k(wav_path)
    duration = len(samples) / 16000

    # Warmup: first invocation pays model-load cost (~5s). Production callers
    # hold a persistent WhisperModel singleton, so the warm-run latency is the
    # representative measurement — not cold start. We time the second call.
    print(f"  fixture: {wav_path} ({duration:.2f}s of audio)")
    t_cold = time.perf_counter()
    warmup_text = transcribe(samples)
    cold = time.perf_counter() - t_cold
    print(f"  cold (incl. model load): {cold*1000:.0f}ms ({cold/duration:.2f}x RTF)")

    t_warm = time.perf_counter()
    text = transcribe(samples)
    warm = time.perf_counter() - t_warm
    print(f"  warm: {warm*1000:.0f}ms ({warm/duration:.2f}x RTF)")
    print(f"  transcript: {text!r}")

    # Acceptance: non-empty transcription on the warm run, warm RTF <= 2.5
    # (plan §3 Step 5 decision: medium.en int8 targets ~2x RTF on CPU; 2.5
    # is the ceiling before the model is unusable for streaming).
    if not text:
        print("FAIL  empty transcription", file=sys.stderr)
        return 1
    warm_rtf = warm / duration
    max_warm_rtf = 2.5
    if warm_rtf > max_warm_rtf:
        print(f"FAIL  warm RTF {warm_rtf:.2f}x exceeds ceiling {max_warm_rtf}x", file=sys.stderr)
        return 1
    # Soft check: fixture is "Hello, this is Hermes..." — expect 'hermes' in output.
    if "hermes" not in text.lower():
        print(f"WARN  expected 'hermes' token in transcript; got: {text!r}", file=sys.stderr)
    print("PASS")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test([a for a in sys.argv[1:] if a != "--self-test"]))
    print("Usage: python3 -m lib.whisper_cpu --self-test [PATH_TO_WAV]", file=sys.stderr)
    sys.exit(2)
