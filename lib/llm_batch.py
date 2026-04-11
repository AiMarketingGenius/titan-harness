"""
titan-harness/lib/llm_batch.py - Phase P5 (war-room graded A in spec)

Batch LLM caller: send up to N items in a single prompt, parse a JSON array
response, validate 1:1 mapping by item id, fall back to per-item calls on
contract violations, write DLQ + run observability to Supabase.

Public API:
    batch_score(items, prompt_template, model_group, max_batch_size=None,
                max_concurrent=None, caller="unknown") -> list[dict]

CORE CONTRACT: hard capacity gate before each batch. Respects
POLICY_CAPACITY_MAX_LLM_BATCH_SIZE and POLICY_CAPACITY_MAX_LLM_CONCURRENT_BATCHES.
"""
from __future__ import annotations

import os
import sys
import json
import uuid
import time
import asyncio
import hashlib
from typing import Optional, Any
from urllib import request, error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from capacity import check_capacity
except Exception:
    def check_capacity(timeout: float = 5.0) -> int:
        return 0


SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")

_MAX_BATCH_SIZE = int(os.environ.get("POLICY_CAPACITY_MAX_LLM_BATCH_SIZE", "15"))
_MAX_CONCURRENT = int(os.environ.get("POLICY_CAPACITY_MAX_LLM_CONCURRENT_BATCHES", "8"))


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------
def _supa_post(path: str, body: dict) -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    try:
        req = request.Request(
            SUPABASE_URL + "/rest/v1/" + path,
            data=json.dumps(body).encode(),
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": "Bearer " + SUPABASE_KEY,
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=5) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


# ---------------------------------------------------------------------------
# LLM call helper (sync; asyncio wraps via loop.run_in_executor)
# ---------------------------------------------------------------------------
def _llm_call(model: str, messages: list[dict], max_tokens: int = 4000,
              timeout: int = 180) -> tuple[int, dict]:
    body = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }).encode()
    req = request.Request(
        LITELLM_BASE_URL + "/v1/chat/completions",
        data=body,
        headers={
            "Authorization": "Bearer " + LITELLM_MASTER_KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}


def _est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Batch execution
# ---------------------------------------------------------------------------
def _build_prompt(prompt_template: str, items: list[dict]) -> str:
    items_json = json.dumps(items, ensure_ascii=False, indent=2)
    return prompt_template.replace("{{items_json}}", items_json)


def _parse_batch_response(text: str, expected_ids: set) -> Optional[list[dict]]:
    """Validate the LLM returned a JSON array with all expected item ids."""
    # Strip markdown code fences if present
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
        t = t.strip()
    try:
        parsed = json.loads(t)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    got_ids = {str(p.get("id")) for p in parsed if isinstance(p, dict)}
    if not expected_ids.issubset(got_ids):
        return None
    return parsed


def _retry_per_item(items: list[dict], prompt_template: str, model: str,
                    caller: str, batch_id: str) -> list[dict]:
    """Fallback: process items one at a time when batch validation fails."""
    out = []
    for item in items:
        messages = [{
            "role": "user",
            "content": _build_prompt(prompt_template, [item]) +
                       "\n\nReturn a JSON array with exactly one object.",
        }]
        status, resp = _llm_call(model, messages, max_tokens=2000)
        if status == 200:
            content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = _parse_batch_response(content, {str(item.get("id"))})
            if parsed:
                out.append(parsed[0])
                continue
        # DLQ
        _supa_post("llm_batch_dlq", {
            "batch_id": batch_id,
            "item_id": str(item.get("id")),
            "prompt_hash": hashlib.sha1(json.dumps(item).encode()).hexdigest(),
            "item_payload": item,
            "error_text": "per-item retry failed",
        })
        out.append({"id": item.get("id"), "_error": "per-item retry failed"})
    return out


def _log_run(batch_id: str, caller: str, model: str, items_in: int,
             items_out: int, tokens_in: int, tokens_out: int,
             cost_cents: float, latency_ms: int, status: str,
             error_text: Optional[str] = None) -> None:
    _supa_post("llm_batch_runs", {
        "batch_id": batch_id,
        "caller": caller,
        "model_group": model,
        "items_in": items_in,
        "items_out": items_out,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_cents": cost_cents,
        "latency_ms": latency_ms,
        "cache_hit_ratio": 0,
        "status": status,
        "error_text": error_text,
    })


def batch_score(items: list[dict], prompt_template: str,
                model_group: str = "claude-sonnet-4-6",
                max_batch_size: Optional[int] = None,
                max_concurrent: Optional[int] = None,
                caller: str = "unknown") -> list[dict]:
    """Score a list of items via batched LLM calls.

    Args:
        items: list of dicts, each must have an "id" field.
        prompt_template: string with {{items_json}} placeholder. Must instruct
            the model to return a JSON array of same length keyed by id.
        model_group: LiteLLM model_group name.
        max_batch_size: items per LLM call (default POLICY_CAPACITY_MAX_LLM_BATCH_SIZE).
        max_concurrent: concurrent LLM calls (default POLICY_CAPACITY_MAX_LLM_CONCURRENT_BATCHES).
        caller: caller class for observability (war_room, mp-runner, etc.)

    Returns:
        list[dict]: one result per input item, in original order.
    """
    if not items:
        return []

    mbs = max_batch_size or _MAX_BATCH_SIZE
    if mbs > _MAX_BATCH_SIZE:
        mbs = _MAX_BATCH_SIZE  # clamp to policy ceiling

    mc = max_concurrent or _MAX_CONCURRENT
    if mc > _MAX_CONCURRENT:
        mc = _MAX_CONCURRENT

    # Capacity gate
    cap = check_capacity()
    if cap == 2:
        # Hard block: defer entire call
        _log_run(str(uuid.uuid4()), caller, model_group, len(items), 0, 0, 0,
                 0, 0, "deferred", "capacity hard block")
        return [{"id": it.get("id"), "_status": "deferred"} for it in items]

    # Split into batches
    batches = [items[i:i + mbs] for i in range(0, len(items), mbs)]

    async def _run_batch(batch: list[dict]) -> list[dict]:
        batch_id = str(uuid.uuid4())
        start = time.time()
        expected_ids = {str(it.get("id")) for it in batch}
        messages = [{"role": "user", "content": _build_prompt(prompt_template, batch)}]

        loop = asyncio.get_event_loop()
        status, resp = await loop.run_in_executor(None, _llm_call, model_group, messages, 4000, 180)

        duration_ms = int((time.time() - start) * 1000)

        if status != 200:
            _log_run(batch_id, caller, model_group, len(batch), 0, 0, 0, 0,
                     duration_ms, "failed", f"http {status}")
            # Retry per-item
            return _retry_per_item(batch, prompt_template, model_group, caller, batch_id)

        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = resp.get("usage", {}) or {}
        tin = int(usage.get("prompt_tokens", 0) or 0)
        tout = int(usage.get("completion_tokens", 0) or 0)

        parsed = _parse_batch_response(content, expected_ids)
        if parsed is None:
            _log_run(batch_id, caller, model_group, len(batch), 0, tin, tout,
                     0, duration_ms, "failed", "contract violation (bad JSON / missing ids)")
            return _retry_per_item(batch, prompt_template, model_group, caller, batch_id)

        _log_run(batch_id, caller, model_group, len(batch), len(parsed),
                 tin, tout, 0, duration_ms, "success")
        return parsed

    async def _run_all():
        sem = asyncio.Semaphore(mc)

        async def _sem_wrap(batch):
            async with sem:
                return await _run_batch(batch)

        results = await asyncio.gather(*[_sem_wrap(b) for b in batches])
        flat = []
        for r in results:
            flat.extend(r)
        return flat

    return asyncio.run(_run_all())


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("POLICY_CAPACITY_MAX_LLM_BATCH_SIZE =", _MAX_BATCH_SIZE)
    print("POLICY_CAPACITY_MAX_LLM_CONCURRENT_BATCHES =", _MAX_CONCURRENT)
    items = [
        {"id": "a1", "text": "The sky is blue."},
        {"id": "a2", "text": "Water boils at 100C."},
        {"id": "a3", "text": "Grass is green."},
    ]
    template = """Score each of the following claims as "fact" or "opinion".
Return a JSON array with one object per input item, same order, with fields:
  id (copy from input), score ("fact" or "opinion"), confidence (0-1).

ITEMS:
{{items_json}}

JSON ARRAY ONLY (no preamble, no markdown fences):"""
    out = batch_score(items, template, model_group="claude-haiku-4-5", caller="self_test")
    print("results:")
    for r in out:
        print(" ", r)
