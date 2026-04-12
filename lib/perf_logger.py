#!/usr/bin/env python3
"""
lib/perf_logger.py
MP-4 §6 — Per-Call Performance Logging + Daily Digest

Logs every Hermes pipeline and Reviewer Loop call to perf-calls.jsonl.
Compiles daily digest at 6:00 AM ET for Slack #titan-ops.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(os.environ.get("TITAN_HEALTH_LOG_DIR", "/var/log/titan"))
PERF_LOG = LOG_DIR / "perf-calls.jsonl"


def log_call(
    call_type: str,  # "reviewer_loop" or "hermes_pipeline"
    model: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_input_tokens: int = 0,
    latency_ms: int = 0,
    cost_usd: float = 0.0,
    phase: str = "",
    status: str = "completed",
) -> dict:
    """Log a per-call performance entry per MP-4 §6.1."""
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "call_type": call_type,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_input_tokens,
        "latency_ms": latency_ms,
        "cost_usd": round(cost_usd, 6),
        "phase": phase,
        "status": status,
    }

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(PERF_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

    return entry


def compile_daily_digest(date_str: str | None = None) -> str:
    """Compile daily performance digest per MP-4 §6.2."""
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    reviewer_calls = 0
    reviewer_latency_total = 0
    reviewer_cached = 0
    reviewer_total_tokens = 0
    hermes_jobs = 0
    hermes_latency_total = 0
    hermes_failures = 0

    try:
        with open(PERF_LOG) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if not entry.get("ts", "").startswith(date_str):
                        continue
                    if entry["call_type"] == "reviewer_loop":
                        reviewer_calls += 1
                        reviewer_latency_total += entry.get("latency_ms", 0)
                        reviewer_cached += entry.get("cached_input_tokens", 0)
                        reviewer_total_tokens += entry.get("input_tokens", 0)
                    elif entry["call_type"] == "hermes_pipeline":
                        hermes_jobs += 1
                        hermes_latency_total += entry.get("latency_ms", 0)
                        if entry.get("status") != "completed":
                            hermes_failures += 1
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass

    cache_rate = (reviewer_cached / reviewer_total_tokens * 100) if reviewer_total_tokens > 0 else 0
    avg_reviewer_latency = (reviewer_latency_total / reviewer_calls) if reviewer_calls > 0 else 0
    avg_hermes_latency = (hermes_latency_total / hermes_jobs) if hermes_jobs > 0 else 0

    return f"""Daily Perf Digest — {date_str}
Reviewer Loop
  • Calls: {reviewer_calls}
  • Cache hit rate: {cache_rate:.0f}%
  • Avg latency: {avg_reviewer_latency:.0f}ms
Hermes Pipeline
  • Jobs processed: {hermes_jobs}
  • Avg end-to-end: {avg_hermes_latency:.0f}ms
  • Failures: {hermes_failures}"""
