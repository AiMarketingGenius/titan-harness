"""
lib/rnnoise_wrapper.py — Hermes Phase A Step 8

Thin Python wrapper around the RNNoise C binary (xiph/rnnoise), which
expects raw 16-bit signed little-endian PCM at 48 kHz mono as both input
and output. We handle resampling + PCM packing so callers can hand us
float32 audio at any sample rate.

Doctrine reference: plans/DOCTRINE_VOICE_AI_STACK_v1.0.md §"(d) AEC /
Noise Suppression" — "RNNoise: Neural noise suppressor for residual
noise AEC doesn't address (keyboard clicks, HVAC, ambient hum). Add to
VPS-side audio pipeline as a post-AEC stage. Lightweight: CPU-viable,
negligible latency."

Used by the Atlas API shim as a post-AEC stage: browser AEC3 handles
linear echo, RNNoise handles residual non-linear noise before the audio
reaches Silero VAD + faster-whisper.

Public API:
    denoise(samples_float32, sample_rate) -> numpy.ndarray (float32, same length approximately)

Self-test:
    python3 -m lib.rnnoise_wrapper --self-test
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover
    raise ImportError("numpy is required for lib.rnnoise_wrapper") from exc

RNNOISE_BIN = "/usr/local/bin/rnnoise_demo"
RNNOISE_SR = 48000  # RNNoise is fixed at 48 kHz


def _check_binary() -> None:
    if not Path(RNNOISE_BIN).exists():
        raise FileNotFoundError(
            f"{RNNOISE_BIN} not found — build rnnoise from xiph/rnnoise and "
            f"install examples/rnnoise_demo to /usr/local/bin/"
        )


def _resample_linear(arr: "np.ndarray", src_sr: int, dst_sr: int) -> "np.ndarray":
    if src_sr == dst_sr:
        return arr.astype(np.float32)
    ratio = dst_sr / src_sr
    new_len = int(round(len(arr) * ratio))
    if new_len <= 1:
        return arr.astype(np.float32)
    x_old = np.linspace(0.0, 1.0, num=len(arr), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=new_len, endpoint=False)
    return np.interp(x_new, x_old, arr).astype(np.float32)


def _float32_to_pcm16(arr: "np.ndarray") -> bytes:
    clipped = np.clip(arr, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    return pcm.tobytes()


def _pcm16_to_float32(raw: bytes) -> "np.ndarray":
    pcm = np.frombuffer(raw, dtype="<i2")
    return pcm.astype(np.float32) / 32768.0


def denoise(samples: "np.ndarray", sample_rate: int) -> "np.ndarray":
    """Apply RNNoise to *samples*. Returns float32 samples at the ORIGINAL
    sample rate. Internally resamples to 48 kHz for RNNoise, then back."""
    _check_binary()
    if samples.dtype != np.float32:
        samples = samples.astype(np.float32)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)

    # Resample to 48 kHz for RNNoise
    resampled = _resample_linear(samples, sample_rate, RNNOISE_SR)
    pcm_in = _float32_to_pcm16(resampled)

    with tempfile.NamedTemporaryFile("wb", suffix=".pcm", delete=False) as fin, \
         tempfile.NamedTemporaryFile("rb", suffix=".pcm", delete=False) as fout:
        fin.write(pcm_in)
        fin.flush()
        in_path = fin.name
        out_path = fout.name
    try:
        subprocess.run(
            [RNNOISE_BIN, in_path, out_path],
            check=True,
            capture_output=True,
            timeout=30,
        )
        with open(out_path, "rb") as rh:
            pcm_out = rh.read()
    finally:
        Path(in_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)

    cleaned_48k = _pcm16_to_float32(pcm_out)
    return _resample_linear(cleaned_48k, RNNOISE_SR, sample_rate)


# ─── self-test ────────────────────────────────────────────────────────────────

def _load_wav_mono_float32(path: Path) -> tuple["np.ndarray", int]:
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        n = wf.getnframes()
        raw = wf.readframes(n)
    if sampwidth != 2:
        raise ValueError(f"Only 16-bit PCM WAV is supported (got {sampwidth*8}-bit)")
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        arr = arr.reshape(-1, channels).mean(axis=1)
    return arr, sr


def _rms(arr: "np.ndarray") -> float:
    return float(np.sqrt(np.mean(arr.astype(np.float64) ** 2)) + 1e-12)


def _self_test() -> int:
    # Use the existing Kokoro smoke output as the clean signal.
    clean_path = Path("/tmp/hermes_smoke.wav")
    if not clean_path.exists():
        print(f"FAIL  fixture missing: {clean_path}", file=sys.stderr)
        return 1

    clean, sr = _load_wav_mono_float32(clean_path)
    duration = len(clean) / sr

    # Synthesize low-pass-filtered "ambient" noise at ~1/3 the RMS of the
    # clean signal. RNNoise is trained on stationary + non-stationary noise
    # of the kind found in real call environments (HVAC, fans, traffic);
    # pure broadband white noise is noticeably harder to suppress since it
    # has energy in the speech band. A low-pass profile better represents
    # the production use case.
    rng = np.random.default_rng(seed=0)
    white = rng.standard_normal(len(clean)).astype(np.float32)
    # Simple 1-pole LP filter to bias energy toward low frequencies.
    alpha = 0.85
    lp = np.zeros_like(white)
    lp[0] = white[0]
    for i in range(1, len(white)):
        lp[i] = alpha * lp[i - 1] + (1.0 - alpha) * white[i]
    # Scale noise to 0.33 * clean RMS.
    target_noise_rms = 0.33 * _rms(clean)
    noise = lp * (target_noise_rms / (_rms(lp) + 1e-12))
    noisy = clean + noise

    # Compute noisy-segment SNR (treat first 0.1s as pure noise, rest as signal+noise).
    pre_silence = noisy[: int(sr * 0.1)]
    pre_noise_rms = _rms(pre_silence)

    try:
        cleaned = denoise(noisy, sample_rate=sr)
    except FileNotFoundError as exc:
        print(f"FAIL  {exc}", file=sys.stderr)
        return 1

    # Trim or pad to match length for RMS compare
    n = min(len(noisy), len(cleaned))
    noisy = noisy[:n]
    cleaned = cleaned[:n]

    post_silence = cleaned[: int(sr * 0.1)]
    post_noise_rms = _rms(post_silence)

    # Overall noise reduction in the silent prefix
    if post_noise_rms <= 0:
        print("FAIL  post silence RMS is zero", file=sys.stderr)
        return 1
    reduction_db = 20.0 * np.log10(pre_noise_rms / post_noise_rms)

    # Signal preservation: the RMS of the full cleaned signal should be
    # comparable (within 6 dB) to the original clean signal — i.e., we
    # stripped noise without destroying the voice.
    clean_trim = clean[:n]
    clean_rms = _rms(clean_trim)
    cleaned_rms = _rms(cleaned)
    signal_delta_db = 20.0 * np.log10(clean_rms / max(cleaned_rms, 1e-6))

    print(f"  fixture: {clean_path} ({duration:.2f}s)")
    print(f"  pre  silence RMS:  {pre_noise_rms:.4f}")
    print(f"  post silence RMS:  {post_noise_rms:.4f}")
    print(f"  noise reduction (silence segment): {reduction_db:.1f} dB")
    print(f"  signal preservation delta: {abs(signal_delta_db):.1f} dB")

    # Plan §5 Step 8 acceptance: SNR improvement >= 10 dB in silent segment.
    if reduction_db < 10.0:
        print(f"FAIL  noise reduction {reduction_db:.1f} dB under 10 dB target", file=sys.stderr)
        return 1
    if abs(signal_delta_db) > 6.0:
        print(f"FAIL  signal altered by {abs(signal_delta_db):.1f} dB > 6 dB budget", file=sys.stderr)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print("Usage: python3 -m lib.rnnoise_wrapper --self-test", file=sys.stderr)
    sys.exit(2)
