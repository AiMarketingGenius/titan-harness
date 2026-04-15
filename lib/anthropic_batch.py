"""
titan-harness/lib/anthropic_batch.py

Production Optimization Pass — Vector 1 (LLM inference batching via Anthropic
Message Batch API). NOT to be confused with lib/llm_batch.py which handles
Phase-P5 QC batch scoring with multi-item-in-one-prompt semantics.

This module submits N independent requests as a single Anthropic batch, polls
until completion, and returns per-request results. 50% cost reduction on
Anthropic vs. realtime; parallelism via Anthropic's backend scheduler.

Falls back to LiteLLM fan-out for non-Anthropic providers (Perplexity sonar
when batched grading is requested for grok_review / idea_to_dr workloads).

Honors EOM 2026-04-15 dispatch P10 — Sonar Pro = DR only; grading uses
regular sonar. Non-Anthropic path routes through LiteLLM gateway.

Public API:
    batch_chat_completions(requests, *, provider="auto", timeout_minutes=60,
                           poll_interval_sec=5.0) -> list[dict]
    batch_grok_review_outbox(outbox_dir, inbox_dir, *, min_batch_size=3,
                             reviewer_model="sonar", provider="auto",
                             timeout_minutes=30) -> dict

Per-request shape:
    {"id": str, "model": str, "messages": list[{role, content}],
     "system": optional str, "max_tokens": optional int, "temperature": optional float}

Integration hook for lib/grok_review.py:
    mailbox_worker_once() can batch-drain the outbox when depth >= 3
    artifacts, cutting N round-trips to 1 Anthropic batch (or 1 fan-out).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "").strip()
ANTHROPIC_BATCH_MAX_REQUESTS = 100_000
ANTHROPIC_BATCH_URL = "https://api.anthropic.com/v1/messages/batches"
DEFAULT_USER_AGENT = "AMG-Titan-Batch/1.0 (+https://aimarketinggenius.io)"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _anthropic_post(url: str, payload: dict[str, Any], *, timeout: int = 60) -> dict[str, Any]:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "message-batches-2024-09-24",
            "content-type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _anthropic_get(url: str, *, timeout: int = 60) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "message-batches-2024-09-24",
            "User-Agent": DEFAULT_USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _anthropic_get_raw(url: str, *, timeout: int = 120) -> bytes:
    """Results endpoint returns JSONL, not JSON."""
    req = urllib.request.Request(
        url,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "message-batches-2024-09-24",
            "User-Agent": DEFAULT_USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def _anthropic_batch_submit(requests: list[dict[str, Any]]) -> str:
    if len(requests) > ANTHROPIC_BATCH_MAX_REQUESTS:
        raise ValueError(
            f"batch size {len(requests)} exceeds Anthropic limit of {ANTHROPIC_BATCH_MAX_REQUESTS}"
        )
    resp = _anthropic_post(ANTHROPIC_BATCH_URL, {"requests": requests})
    return resp["id"]


def _anthropic_batch_poll(batch_id: str, timeout_minutes: int, poll_interval_sec: float) -> dict[str, Any]:
    deadline = time.monotonic() + (timeout_minutes * 60)
    interval = poll_interval_sec
    while time.monotonic() < deadline:
        batch = _anthropic_get(f"{ANTHROPIC_BATCH_URL}/{batch_id}")
        if batch.get("processing_status") == "ended":
            return batch
        time.sleep(interval)
        interval = min(interval * 1.5, 60.0)
    raise TimeoutError(f"batch {batch_id} did not complete within {timeout_minutes} min")


def _anthropic_batch_results(batch_id: str, batch_meta: dict[str, Any]) -> list[dict[str, Any]]:
    results_url = batch_meta.get("results_url")
    if not results_url:
        raise RuntimeError(f"batch {batch_id} has no results_url yet")
    raw = _anthropic_get_raw(results_url)
    out: list[dict[str, Any]] = []
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def _anthropic_batch_run(
    requests: list[dict[str, Any]],
    timeout_minutes: int,
    poll_interval_sec: float,
) -> list[dict[str, Any]]:
    anthropic_requests = []
    id_mapping: dict[str, dict[str, Any]] = {}
    for r in requests:
        cid = str(r.get("id"))
        if not cid:
            raise ValueError("every request must include an 'id'")
        id_mapping[cid] = r
        params = {
            "model": r["model"],
            "max_tokens": r.get("max_tokens", 2000),
            "messages": r["messages"],
        }
        if "system" in r:
            params["system"] = r["system"]
        if "temperature" in r:
            params["temperature"] = r["temperature"]
        anthropic_requests.append({"custom_id": cid, "params": params})

    batch_id = _anthropic_batch_submit(anthropic_requests)
    final_meta = _anthropic_batch_poll(batch_id, timeout_minutes, poll_interval_sec)
    raw_results = _anthropic_batch_results(batch_id, final_meta)

    out: list[dict[str, Any]] = []
    for entry in raw_results:
        cid = entry.get("custom_id", "")
        result = entry.get("result", {})
        if result.get("type") == "succeeded":
            msg = result.get("message", {})
            text = "".join(
                b.get("text", "") for b in msg.get("content", []) if b.get("type") == "text"
            )
            out.append({
                "id": cid,
                "response": text,
                "batch_id": batch_id,
                "provider": "anthropic",
                "ts_utc": _now_iso(),
            })
        else:
            out.append({
                "id": cid,
                "error": json.dumps(result, default=str),
                "batch_id": batch_id,
                "provider": "anthropic",
                "ts_utc": _now_iso(),
            })

    returned_ids = {r["id"] for r in out}
    for cid in id_mapping:
        if cid not in returned_ids:
            out.append({
                "id": cid,
                "error": "missing_from_batch_results",
                "batch_id": batch_id,
                "provider": "anthropic",
                "ts_utc": _now_iso(),
            })
    return out


def _litellm_single_call(model: str, messages: list[dict], max_tokens: int, system: Optional[str]) -> str:
    if not LITELLM_MASTER_KEY:
        raise RuntimeError("LITELLM_MASTER_KEY not set")
    msgs = messages[:]
    if system:
        msgs = [{"role": "system", "content": system}] + msgs
    payload = json.dumps({
        "model": model,
        "messages": msgs,
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{LITELLM_BASE_URL}/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {LITELLM_MASTER_KEY}",
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def _litellm_fanout_run(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in requests:
        cid = str(r.get("id"))
        try:
            text = _litellm_single_call(
                model=r["model"],
                messages=r["messages"],
                max_tokens=r.get("max_tokens", 2000),
                system=r.get("system"),
            )
            out.append({
                "id": cid,
                "response": text,
                "provider": "litellm",
                "model": r["model"],
                "ts_utc": _now_iso(),
            })
        except Exception as exc:
            out.append({
                "id": cid,
                "error": str(exc),
                "provider": "litellm",
                "model": r.get("model"),
                "ts_utc": _now_iso(),
            })
    return out


def batch_chat_completions(
    requests: list[dict[str, Any]],
    *,
    provider: str = "auto",
    timeout_minutes: int = 60,
    poll_interval_sec: float = 5.0,
) -> list[dict[str, Any]]:
    """
    Batch chat completions across N requests, returning per-id results.

    provider:
        - "anthropic": Message Batch API (50% cost reduction, ≤24h async)
        - "litellm" / "perplexity": LiteLLM gateway fan-out (realtime)
        - "auto": picks Anthropic when all requests target claude-* models
                  and ANTHROPIC_API_KEY is set; else LiteLLM

    Every request must include: id, model, messages.
    Optional: system, max_tokens (default 2000), temperature.
    """
    if not requests:
        return []

    if provider == "auto":
        all_anthropic = all(str(r.get("model", "")).startswith("claude-") for r in requests)
        provider = "anthropic" if (all_anthropic and ANTHROPIC_API_KEY) else "litellm"

    if provider == "anthropic":
        return _anthropic_batch_run(requests, timeout_minutes, poll_interval_sec)
    if provider in ("litellm", "perplexity"):
        return _litellm_fanout_run(requests)
    raise ValueError(f"unknown provider: {provider}")


def batch_grok_review_outbox(
    outbox_dir: str | os.PathLike[str],
    inbox_dir: str | os.PathLike[str],
    *,
    min_batch_size: int = 3,
    reviewer_model: str = "sonar",
    provider: str = "auto",
    timeout_minutes: int = 30,
) -> dict[str, Any]:
    """
    Drain lib/grok_review mailbox outbox with batched calls. Returns
    {"batched": n, "errors": m, "batch_id": "..."} or explains why skipped.
    """
    outbox = Path(outbox_dir)
    inbox = Path(inbox_dir)
    pending = sorted(outbox.glob("req-*.json"))
    if len(pending) < min_batch_size:
        return {"batched": 0, "skipped": len(pending), "reason": "below min_batch_size"}

    requests = []
    for req_file in pending:
        try:
            payload = json.loads(req_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        req_id = payload.get("request_id") or req_file.stem
        artifact_path = Path(payload.get("artifact_path", ""))
        if not artifact_path.is_file():
            continue
        artifact_text = artifact_path.read_text(encoding="utf-8", errors="replace")
        user_prompt = (
            "Grade this artifact against the war-room 10-dimension rubric. "
            "Return JSON only: grade, dimension_scores, risk_tags, rationale, remediation.\n\n"
            f"ARTIFACT ({artifact_path.name}):\n\n{artifact_text[:30_000]}"
        )
        requests.append({
            "id": req_id,
            "model": reviewer_model,
            "system": "You are a senior adversarial AI reviewer. Output JSON only.",
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": 2000,
        })

    if not requests:
        return {"batched": 0, "skipped": len(pending), "reason": "no_valid_payloads"}

    results = batch_chat_completions(
        requests,
        provider=provider,
        timeout_minutes=timeout_minutes,
    )

    batched = 0
    errors = 0
    for r in results:
        inbox_file = inbox / f"{r['id']}.json"
        try:
            if "response" in r:
                inbox_file.write_text(json.dumps({
                    "request_id": r["id"],
                    "response_raw": r["response"],
                    "provider": r.get("provider"),
                    "ts_utc": r["ts_utc"],
                    "batched": True,
                }, indent=2), encoding="utf-8")
                batched += 1
            else:
                inbox_file.write_text(json.dumps({
                    "request_id": r["id"],
                    "error": r.get("error"),
                    "ts_utc": r["ts_utc"],
                    "batched": True,
                }, indent=2), encoding="utf-8")
                errors += 1
        except OSError as exc:
            errors += 1
            print(f"[anthropic_batch] write error for {r['id']}: {exc}", file=sys.stderr)

    batch_id = results[0].get("batch_id") if results else None
    return {"batched": batched, "errors": errors, "batch_id": batch_id, "provider": provider}


def _selftest() -> int:
    demo = [
        {"id": f"test-{i}", "model": "claude-haiku-4-5",
         "messages": [{"role": "user", "content": f"Say 'ok-{i}' and nothing else."}],
         "max_tokens": 20}
        for i in range(3)
    ]
    print(f"[anthropic_batch selftest] prepared {len(demo)} demo requests")
    try:
        reshaped = [
            {"custom_id": str(r["id"]),
             "params": {"model": r["model"], "max_tokens": r.get("max_tokens", 2000), "messages": r["messages"]}}
            for r in demo
        ]
        print(f"[anthropic_batch selftest] reshape OK: {json.dumps(reshaped[0])[:160]}")
    except Exception as exc:
        print(f"[anthropic_batch selftest] FAIL reshape: {exc}")
        return 1
    all_claude = all(str(r.get("model", "")).startswith("claude-") for r in demo)
    detected = "anthropic" if (all_claude and os.environ.get("ANTHROPIC_API_KEY")) else "litellm"
    print(f"[anthropic_batch selftest] auto-provider would route to: {detected}")
    print("[anthropic_batch selftest] PASS (dry-run). Live batch requires VPS env.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
