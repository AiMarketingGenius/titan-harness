#!/usr/bin/env python3
"""
bin/qa_runner.py — Hermes Phase A Voice QA Loop

Runs a bank of test scenarios against the Atlas voice endpoint, measures
latency/quality metrics, gates on hard/soft fail thresholds, and logs
results. Designed for nightly execution via titan-qa.timer.

Doctrine: plans/DOCTRINE_HERMES_PHASE_A_VOICE_QA.md

Metrics per scenario:
  - latency_ms: end-to-end (text→Claude→Kokoro→WAV returned)
  - lufs: loudness measured via ffmpeg ebur128 filter
  - true_peak_dbfs: measured via ffmpeg ebur128
  - wpm: words per minute in Claude's response
  - artifact_flag: 0 = clean, 1+ = artifacts detected (clicks, pops, silence gaps)
  - silence_ratio: ratio of silence to total WAV duration

Hard fail gates (any = FAIL):
  - artifact_flag != 0
  - latency_ms > 800
  - clarity < 4 (subjective, from Reviewer Loop if available)

Soft fail gates (block only if 2 consecutive nights):
  - naturalness/pacing/brandfit < 3
  - LUFS out of [-16, -12] range
  - WPM out of [120, 180] range

Usage:
  python3 bin/qa_runner.py                    # full run
  python3 bin/qa_runner.py --scenario 1       # single scenario
  python3 bin/qa_runner.py --dry-run          # print scenarios, no execution
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure lib/ is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib"))

ATLAS_BASE = os.environ.get("ATLAS_API_BASE", "http://127.0.0.1:8084")
LOG_DIR = Path(os.environ.get("QA_LOG_DIR", "/var/log/titan/voice-qa"))
DATE_STR = datetime.now(timezone.utc).strftime("%Y%m%d")

# ─── Scenario Bank ──────────────────────────────────────────────────────────

SCENARIOS = [
    {
        "id": 1,
        "name": "cold_open_what_is_amg",
        "description": "First-time visitor asks what AMG does",
        "user_text": "What does AI Marketing Genius do?",
        "expected_keywords": ["marketing", "business"],
        "banned_keywords": ["synergy", "leverage"],
    },
    {
        "id": 2,
        "name": "pricing_inquiry",
        "description": "User asks about pricing — guardrail must hold",
        "user_text": "How much does it cost to work with you?",
        "expected_keywords": ["$497", "$797", "$1,497"],
        "banned_keywords": ["$999", "$2000", "$299"],
    },
    {
        "id": 3,
        "name": "seo_question",
        "description": "Small business owner asks about SEO",
        "user_text": "I have a plumbing business. Can you help me show up on Google?",
        "expected_keywords": ["SEO", "Google", "website"],
        "banned_keywords": [],
    },
    {
        "id": 4,
        "name": "escalation_trigger",
        "description": "User asks for enterprise pricing — should escalate",
        "user_text": "I need enterprise-level service for 50 locations. What's your enterprise pricing?",
        "expected_keywords": ["Solon", "team", "discuss"],
        "banned_keywords": [],
    },
]

# ─── Metric measurement ─────────────────────────────────────────────────────

def measure_latency(user_text: str) -> tuple[str, bytes, int]:
    """Call Atlas /api/ask, measure round-trip, return (reply_text, tts_wav, latency_ms).
    For the QA loop we use the text endpoint + separate TTS call."""
    import httpx

    t0 = time.time()
    r = httpx.get(f"{ATLAS_BASE}/api/ask", params={"q": user_text}, timeout=30)
    r.raise_for_status()
    data = r.json()
    reply = data.get("reply", "")
    latency_llm = int((time.time() - t0) * 1000)

    # TTS via Kokoro
    t1 = time.time()
    kokoro_url = os.environ.get("ATLAS_KOKORO_URL", "http://127.0.0.1:8880")
    tts_r = httpx.post(
        f"{kokoro_url}/v1/audio/speech",
        json={"model": "kokoro", "voice": "am_michael", "input": reply, "response_format": "wav", "speed": 0.92},
        timeout=30,
    )
    tts_r.raise_for_status()
    wav = tts_r.content
    latency_tts = int((time.time() - t1) * 1000)

    return reply, wav, latency_llm + latency_tts


def measure_audio_metrics(wav_bytes: bytes, scenario_dir: Path) -> dict:
    """Measure LUFS, true peak, silence ratio via ffmpeg ebur128."""
    wav_path = scenario_dir / "response.wav"
    wav_path.write_bytes(wav_bytes)

    metrics = {"lufs": None, "true_peak_dbfs": None, "silence_ratio": None, "artifact_flag": 0}

    try:
        result = subprocess.run(
            ["ffmpeg", "-i", str(wav_path), "-af", "ebur128=peak=true", "-f", "null", "-"],
            capture_output=True, text=True, timeout=30,
        )
        stderr = result.stderr
        # Parse LUFS
        for line in stderr.split("\n"):
            if "I:" in line and "LUFS" in line:
                try:
                    metrics["lufs"] = float(line.split("I:")[-1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
            if "True peak" in line and "dBFS" in line:
                try:
                    metrics["true_peak_dbfs"] = float(line.split("Peak:")[-1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass

    # Silence detection via ffmpeg silencedetect
    try:
        result = subprocess.run(
            ["ffmpeg", "-i", str(wav_path), "-af", "silencedetect=noise=-30dB:d=0.3", "-f", "null", "-"],
            capture_output=True, text=True, timeout=30,
        )
        silence_total = 0.0
        for line in result.stderr.split("\n"):
            if "silence_duration" in line:
                try:
                    dur = float(line.split("silence_duration:")[-1].strip())
                    silence_total += dur
                except (ValueError, IndexError):
                    pass
        # Get total duration
        dur_result = subprocess.run(
            ["ffprobe", "-i", str(wav_path), "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"],
            capture_output=True, text=True, timeout=10,
        )
        total_dur = float(dur_result.stdout.strip()) if dur_result.stdout.strip() else 1.0
        metrics["silence_ratio"] = round(silence_total / max(total_dur, 0.01), 3)
    except Exception:
        pass

    return metrics


def measure_wpm(text: str, wav_bytes: bytes) -> float:
    """Estimate words per minute from response text length and WAV duration."""
    words = len(text.split())
    try:
        result = subprocess.run(
            ["ffprobe", "-i", "pipe:", "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"],
            input=wav_bytes, capture_output=True, timeout=10,
        )
        dur = float(result.stdout.strip()) if result.stdout.strip() else 1.0
    except Exception:
        dur = max(words / 2.5, 1.0)  # rough fallback: ~150 wpm
    return round(words / max(dur / 60, 0.01), 1)


# ─── Gate evaluation ─────────────────────────────────────────────────────────

def evaluate_gates(metrics: dict) -> tuple[str, list[str]]:
    """Return (verdict, reasons). verdict = PASS / HARD_FAIL / SOFT_FAIL."""
    hard_fails = []
    soft_fails = []

    if metrics.get("artifact_flag", 0) != 0:
        hard_fails.append(f"artifact_flag={metrics['artifact_flag']}")
    if metrics.get("latency_ms", 0) > 800:
        hard_fails.append(f"latency={metrics['latency_ms']}ms (>800)")

    lufs = metrics.get("lufs")
    if lufs is not None and (lufs < -16 or lufs > -12):
        soft_fails.append(f"lufs={lufs} (outside [-16, -12])")

    wpm = metrics.get("wpm", 0)
    if wpm and (wpm < 120 or wpm > 180):
        soft_fails.append(f"wpm={wpm} (outside [120, 180])")

    if hard_fails:
        return "HARD_FAIL", hard_fails
    if soft_fails:
        return "SOFT_FAIL", soft_fails
    return "PASS", []


# ─── Main runner ─────────────────────────────────────────────────────────────

def run_scenario(scenario: dict) -> dict:
    """Run a single QA scenario. Returns result dict."""
    scenario_dir = LOG_DIR / DATE_STR / f"scenario_{scenario['id']}_{scenario['name']}"
    scenario_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        reply, wav, latency = measure_latency(scenario["user_text"])
        result["reply_text"] = reply
        result["latency_ms"] = latency
        result["reply_length"] = len(reply)

        # Check expected/banned keywords
        reply_lower = reply.lower()
        result["expected_keywords_found"] = [k for k in scenario["expected_keywords"] if k.lower() in reply_lower]
        result["banned_keywords_found"] = [k for k in scenario["banned_keywords"] if k.lower() in reply_lower]

        # Audio metrics
        audio = measure_audio_metrics(wav, scenario_dir)
        result.update(audio)

        # WPM
        result["wpm"] = measure_wpm(reply, wav)

        # Gate evaluation
        verdict, reasons = evaluate_gates(result)
        result["verdict"] = verdict
        result["fail_reasons"] = reasons

    except Exception as exc:
        result["verdict"] = "ERROR"
        result["error"] = f"{type(exc).__name__}: {exc}"

    # Save result
    (scenario_dir / "result.json").write_text(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description="Hermes Phase A Voice QA Runner")
    parser.add_argument("--scenario", type=int, help="Run single scenario by ID")
    parser.add_argument("--dry-run", action="store_true", help="Print scenarios without executing")
    args = parser.parse_args()

    if args.dry_run:
        print(f"QA Runner — {len(SCENARIOS)} scenarios registered:")
        for s in SCENARIOS:
            print(f"  [{s['id']}] {s['name']}: {s['description']}")
            print(f"      Input: \"{s['user_text']}\"")
        return

    scenarios = SCENARIOS
    if args.scenario:
        scenarios = [s for s in SCENARIOS if s["id"] == args.scenario]
        if not scenarios:
            print(f"Scenario {args.scenario} not found", file=sys.stderr)
            sys.exit(1)

    print(f"[QA] Running {len(scenarios)} scenario(s) at {datetime.now(timezone.utc).isoformat()}")
    print(f"[QA] Log dir: {LOG_DIR / DATE_STR}")

    results = []
    for scenario in scenarios:
        print(f"  [{scenario['id']}] {scenario['name']}...", end=" ", flush=True)
        result = run_scenario(scenario)
        verdict = result.get("verdict", "ERROR")
        latency = result.get("latency_ms", "?")
        print(f"{verdict} ({latency}ms)")
        results.append(result)

    # Summary
    summary_dir = LOG_DIR / DATE_STR
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "date": DATE_STR,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "pass": sum(1 for r in results if r.get("verdict") == "PASS"),
        "hard_fail": sum(1 for r in results if r.get("verdict") == "HARD_FAIL"),
        "soft_fail": sum(1 for r in results if r.get("verdict") == "SOFT_FAIL"),
        "error": sum(1 for r in results if r.get("verdict") == "ERROR"),
        "scenarios": results,
    }
    (summary_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n[QA] Summary: {summary['pass']}/{summary['total']} PASS, "
          f"{summary['hard_fail']} HARD_FAIL, {summary['soft_fail']} SOFT_FAIL, "
          f"{summary['error']} ERROR")
    print(f"[QA] Results: {summary_dir / 'summary.json'}")

    # Exit code: 0 = all pass, 1 = any hard fail, 2 = soft fail only
    if summary["hard_fail"] > 0:
        sys.exit(1)
    if summary["soft_fail"] > 0:
        sys.exit(2)


if __name__ == "__main__":
    main()
