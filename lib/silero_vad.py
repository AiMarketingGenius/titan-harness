"""
lib/silero_vad.py — Hermes Phase A Step 4

Thin CPU-only wrapper around the `silero-vad` PyPI package. Loads the ONNX
Silero VAD v4 model once at import time and exposes two entry points:

    detect_speech(samples, sample_rate=16000) -> list[tuple[float, float]]
        Returns a list of (start_s, end_s) speech segments, AUC 0.91.

    is_speech(samples, sample_rate=16000) -> bool
        True if any speech was detected in the clip.

Doctrine reference: plans/DOCTRINE_VOICE_AI_STACK_v1.0.md §"(c) VAD: Full
Doctrine" — Silero VAD v4, ONNX, AUC 0.91, frame window 150-250ms.

Used by the Atlas API shim to (a) gate faster-whisper input against silence
hallucinations and (b) emit barge-in signals during Kokoro TTS playback.

Self-test:
    python3 -m lib.silero_vad --self-test [PATH_TO_WAV]
"""

from __future__ import annotations

import sys
import time
import wave
from pathlib import Path
from typing import Iterable

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover
    raise ImportError("numpy is required for lib.silero_vad") from exc

try:
    from silero_vad import get_speech_timestamps, load_silero_vad
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "silero-vad is not installed; run `pip install silero-vad onnxruntime`"
    ) from exc

_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        _MODEL = load_silero_vad(onnx=True)
    return _MODEL


def _to_float32(samples) -> "np.ndarray":
    if isinstance(samples, np.ndarray):
        arr = samples
    else:
        arr = np.asarray(samples)
    if arr.dtype == np.int16:
        arr = arr.astype(np.float32) / 32768.0
    elif arr.dtype != np.float32:
        arr = arr.astype(np.float32)
    if arr.ndim > 1:
        arr = arr.mean(axis=1)
    return arr


def detect_speech(samples, sample_rate: int = 16000, threshold: float = 0.5) -> list[tuple[float, float]]:
    """Return speech segments as [(start_s, end_s), ...]."""
    arr = _to_float32(samples)
    try:
        import torch
    except ImportError as exc:  # pragma: no cover
        raise ImportError("torch is required by silero_vad at runtime") from exc
    tensor = torch.from_numpy(arr)
    timestamps = get_speech_timestamps(
        tensor,
        _model(),
        sampling_rate=sample_rate,
        threshold=threshold,
        return_seconds=True,
    )
    return [(float(t["start"]), float(t["end"])) for t in timestamps]


def is_speech(samples, sample_rate: int = 16000, threshold: float = 0.5) -> bool:
    return bool(detect_speech(samples, sample_rate=sample_rate, threshold=threshold))


# ─── self-test ────────────────────────────────────────────────────────────────

def _load_wav(path: Path) -> tuple["np.ndarray", int]:
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        raw = wf.readframes(n)
    if sampwidth != 2:
        raise ValueError(f"Only 16-bit PCM WAV is supported in the self-test (got {sampwidth*8}-bit)")
    arr = np.frombuffer(raw, dtype=np.int16)
    if channels > 1:
        arr = arr.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return arr.astype(np.float32) / 32768.0, sr


def _resample_linear(arr: "np.ndarray", src_sr: int, dst_sr: int) -> "np.ndarray":
    if src_sr == dst_sr:
        return arr
    ratio = dst_sr / src_sr
    new_len = int(len(arr) * ratio)
    if new_len <= 1:
        return arr
    x_old = np.linspace(0.0, 1.0, num=len(arr), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=new_len, endpoint=False)
    return np.interp(x_new, x_old, arr).astype(np.float32)


def _self_test(argv: list[str]) -> int:
    wav_path = Path(argv[0]) if argv else Path("/tmp/hermes_smoke.wav")
    if not wav_path.exists():
        print(f"FAIL  fixture missing: {wav_path}", file=sys.stderr)
        return 1

    samples, sr = _load_wav(wav_path)
    if sr != 16000:
        samples = _resample_linear(samples, sr, 16000)
        sr = 16000

    t0 = time.perf_counter()
    segments = detect_speech(samples, sample_rate=sr)
    elapsed = time.perf_counter() - t0
    print(f"  fixture: {wav_path} ({len(samples)/sr:.2f}s)")
    print(f"  segments: {segments}")
    print(f"  wall: {elapsed*1000:.1f}ms")
    if not segments:
        print("FAIL  no speech detected in fixture", file=sys.stderr)
        return 1
    # Acceptance: detection under 200ms on fixture, at least one segment.
    budget_ms = 500  # CPU budget, more lenient than the 200ms GPU figure in doctrine
    if elapsed * 1000 > budget_ms:
        print(f"FAIL  wall {elapsed*1000:.1f}ms exceeds budget {budget_ms}ms", file=sys.stderr)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test([a for a in sys.argv[1:] if a != "--self-test"]))
    print("Usage: python3 -m lib.silero_vad --self-test [PATH_TO_WAV]", file=sys.stderr)
    sys.exit(2)
