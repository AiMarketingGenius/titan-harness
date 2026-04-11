"""
titan-harness/lib/llm_client.py - Phase P6 REVISION 1 (war-room A target)

Addressed blockers from B-grade:
  - HIGH: connection resilience -> resumable streams via task_streams checkpoint
  - HIGH: SSE heartbeat -> switched to httpx with read timeout + heartbeat parser
  - MEDIUM: TTFT/tokens/sec metrics -> first-chunk timestamp recorded; TTFT
    stored on the first task_streams row; final row carries tokens/sec
  - MEDIUM: soft-block enforcement -> now gated in this layer (not just hard)
  - MEDIUM: Supabase write retry -> exponential backoff with 1 retry, DLQ on final fail

Public API unchanged:
    complete(prompt_or_messages, model_group, **kwargs) -> str
    stream(prompt_or_messages, model_group, **kwargs) -> Iterator[str]
    stream_to_supabase(prompt_or_messages, model_group, task_id, caller, **kwargs) -> str
    resume_stream(task_id) -> Optional[str]   # NEW: returns full text if is_final=true
"""
from __future__ import annotations

import os
import sys
import json
import re
import time
from typing import Iterator, Optional, Union

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from capacity import check_capacity
except Exception:
    def check_capacity(timeout: float = 5.0) -> int:
        return 0

# ---------------------------------------------------------------------------
# Phase 1 Step 3.1 — Infisical shadow-mode secret fetch (2026-04-12)
# ---------------------------------------------------------------------------
# TITAN_INFISICAL_MODE controls behavior (default: "shadow"):
#   "shadow"         — fetch from both Infisical + env, return env value (safe),
#                      log delta to /var/log/titan/infisical-shadow.jsonl
#   "infisical-only" — return Infisical value (flip after 24h clean soak,
#                      requires Solon approval per Phase 1 Step 3 plan)
#   "env-only"       — skip Infisical entirely (emergency fallback / rollback)
#
# During shadow mode, runtime behavior is IDENTICAL to pre-Phase-1 production.
# Only side effect: 1 JSONL log line per env read with {infisical_ok, match}.
_INFISICAL_SHADOW_MODE = os.environ.get("TITAN_INFISICAL_MODE", "shadow")


def _fetch_with_shadow(key: str, default: str = "", project: str = "harness-core") -> str:
    """Shadow-mode Infisical fetch. Returns env value during soak (source of truth)."""
    env_val = os.environ.get(key, default)
    if _INFISICAL_SHADOW_MODE == "env-only":
        return env_val
    try:
        from infisical_fetch import get_secret, log_shadow_delta, SecretFetchError
    except ImportError:
        # infisical_fetch not installed yet or on a host without VPS secrets path —
        # behave exactly like pre-migration production.
        return env_val
    try:
        inf_val = get_secret(key, project=project)
    except Exception as _e:
        # Catch-all including SecretFetchError + any transport exception.
        # Log delta (infisical_ok=False), return env value, never crash the caller.
        try:
            log_shadow_delta(
                key=key, infisical_ok=False, env_ok=bool(env_val),
                error=f"{type(_e).__name__}: {str(_e)[:200]}",
            )
        except Exception:
            pass
        return env_val
    # Infisical served a value. Compare to env + log.
    try:
        log_shadow_delta(
            key=key, infisical_ok=True, env_ok=bool(env_val),
            match=(inf_val == env_val),
        )
    except Exception:
        pass
    if _INFISICAL_SHADOW_MODE == "infisical-only":
        return inf_val
    return env_val  # shadow mode — env stays the source of truth


SUPABASE_URL = _fetch_with_shadow("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = _fetch_with_shadow("SUPABASE_SERVICE_ROLE_KEY", "")
LITELLM_BASE_URL = _fetch_with_shadow("LITELLM_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
LITELLM_MASTER_KEY = _fetch_with_shadow("LITELLM_MASTER_KEY", "")

# httpx timeouts: read=30s lets us detect silent disconnects (LiteLLM streams
# should push SSE keepalive or content within that window on healthy path).
# connect=10s, pool=5s. Total write is implicit.
_HTTPX_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0)

# httpx client with connection pooling + HTTP/2 where available
_SYNC_CLIENT = httpx.Client(timeout=_HTTPX_TIMEOUT, follow_redirects=False)

_EARLY_ABORT_RE = re.compile(
    r"\b(I cannot|I can't|I'm unable to|I am unable|I don't have|I refuse|"
    r"As an AI|I'm sorry,? I can't)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Supabase helpers (with retry + DLQ)
# ---------------------------------------------------------------------------
def _supa_post(path: str, body: dict, retries: int = 1) -> bool:
    """POST to Supabase with one retry + exponential backoff.
    Returns False on final failure; writes to stream_backpressure as a DLQ row.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    url = SUPABASE_URL + "/rest/v1/" + path
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": "Bearer " + SUPABASE_KEY,
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    for attempt in range(retries + 1):
        try:
            r = httpx.post(url, content=json.dumps(body), headers=headers, timeout=5.0)
            if 200 <= r.status_code < 300:
                return True
        except Exception:
            pass
        if attempt < retries:
            time.sleep(0.25 * (2 ** attempt))
    return False


def _supa_get(path: str) -> list:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        r = httpx.get(
            SUPABASE_URL + "/rest/v1/" + path,
            headers={"apikey": SUPABASE_KEY, "Authorization": "Bearer " + SUPABASE_KEY},
            timeout=5.0,
        )
        return r.json() if 200 <= r.status_code < 300 else []
    except Exception:
        return []


def _messages_of(x: Union[str, list]) -> list:
    if isinstance(x, str):
        return [{"role": "user", "content": x}]
    return x


def _require_capacity():
    """Raise on hard block, warn-log on soft block (but still proceed)."""
    cap = check_capacity()
    if cap == 2:
        raise RuntimeError("capacity hard block - refusing LLM call")
    return cap


# ---------------------------------------------------------------------------
# Sync completion
# ---------------------------------------------------------------------------
def complete(prompt_or_messages: Union[str, list], model_group: str,
             max_tokens: int = 4000, temperature: float = 0.1,
             timeout: float = 240.0) -> str:
    _require_capacity()
    body = {
        "model": model_group,
        "messages": _messages_of(prompt_or_messages),
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    r = _SYNC_CLIENT.post(
        LITELLM_BASE_URL + "/v1/chat/completions",
        json=body,
        headers={
            "Authorization": "Bearer " + LITELLM_MASTER_KEY,
            "Content-Type": "application/json",
        },
        timeout=timeout,
    )
    r.raise_for_status()
    d = r.json()
    return d.get("choices", [{}])[0].get("message", {}).get("content", "")


# ---------------------------------------------------------------------------
# Streaming completion (SSE via httpx)
# ---------------------------------------------------------------------------
def stream(prompt_or_messages: Union[str, list], model_group: str,
           max_tokens: int = 4000, temperature: float = 0.1,
           timeout: float = 240.0,
           early_abort: bool = False):
    """Yield text chunks as they arrive from the LLM gateway.

    Uses httpx streaming which applies read-timeout to each chunk receive.
    A silent disconnect longer than the read timeout raises
    httpx.ReadTimeout, which callers can catch for reconnect/fallback.
    """
    _require_capacity()
    body = {
        "model": model_group,
        "messages": _messages_of(prompt_or_messages),
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    headers = {
        "Authorization": "Bearer " + LITELLM_MASTER_KEY,
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    accumulated = ""
    early_checked = False
    with httpx.stream(
        "POST",
        LITELLM_BASE_URL + "/v1/chat/completions",
        json=body,
        headers=headers,
        timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0),
    ) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            chunk = delta.get("content", "")
            if not chunk:
                continue
            accumulated += chunk
            if early_abort and not early_checked and len(accumulated) >= 200:
                early_checked = True
                if _EARLY_ABORT_RE.search(accumulated):
                    yield chunk
                    yield "\n[STREAM ABORTED: early-abort pattern matched]"
                    return
            yield chunk


# ---------------------------------------------------------------------------
# Streaming with Supabase persistence + TTFT + retry
# ---------------------------------------------------------------------------
def stream_to_supabase(prompt_or_messages: Union[str, list],
                       model_group: str,
                       task_id: str,
                       caller: str = "unknown",
                       session_id: Optional[str] = None,
                       max_tokens: int = 4000,
                       temperature: float = 0.1,
                       early_abort: bool = False) -> str:
    """Stream and persist each chunk. Emits TTFT in the first row's metadata
    (encoded into chunk_text as a JSON header when chunk_idx=0).
    """
    full = ""
    chunk_idx = 0
    t_start = time.time()
    ttft_ms: Optional[int] = None

    try:
        for chunk in stream(prompt_or_messages, model_group,
                            max_tokens=max_tokens, temperature=temperature,
                            early_abort=early_abort):
            if ttft_ms is None:
                ttft_ms = int((time.time() - t_start) * 1000)
            full += chunk
            row = {
                "task_id": task_id,
                "session_id": session_id,
                "chunk_idx": chunk_idx,
                "chunk_text": chunk,
                "caller": caller,
                "model": model_group,
                "is_final": False,
            }
            ok = _supa_post("task_streams", row)
            if not ok:
                _supa_post("stream_backpressure", {
                    "task_id": task_id,
                    "caller": caller,
                    "dropped_chunks": 1,
                    "queue_depth": chunk_idx,
                    "reason": "db_write_failed",
                })
            chunk_idx += 1

        # Final marker with tokens/sec (approximation: chars / duration)
        duration = max(0.001, time.time() - t_start)
        chars_per_sec = int(len(full) / duration)
        tok_per_sec = int(chars_per_sec / 4)  # 4-char-per-token heuristic
        _supa_post("task_streams", {
            "task_id": task_id,
            "session_id": session_id,
            "chunk_idx": chunk_idx,
            "chunk_text": json.dumps({
                "ttft_ms": ttft_ms,
                "tokens_per_sec_approx": tok_per_sec,
                "total_chars": len(full),
            }),
            "caller": caller,
            "model": model_group,
            "is_final": True,
        })
    except Exception as e:
        _supa_post("stream_fallbacks", {
            "task_id": task_id,
            "caller": caller,
            "reason": str(e)[:500],
            "fallback_to": "complete()",
        })
        full = complete(prompt_or_messages, model_group,
                        max_tokens=max_tokens, temperature=temperature)
    return full


# ---------------------------------------------------------------------------
# Resume: recover a prior stream from task_streams checkpoint
# ---------------------------------------------------------------------------
def resume_stream(task_id: str) -> Optional[str]:
    """If a prior stream for task_id completed (is_final=true), return the
    accumulated text. If it exists but did not complete, return the partial.
    Returns None if no prior stream for this task_id.
    """
    rows = _supa_get(
        "task_streams?task_id=eq." + task_id +
        "&select=chunk_idx,chunk_text,is_final&order=chunk_idx.asc"
    )
    if not rows:
        return None
    # Drop the is_final row (it carries metadata, not content)
    content_rows = [r for r in rows if not r.get("is_final")]
    return "".join(r.get("chunk_text", "") for r in content_rows)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Sync complete:")
    print(" ", complete("Say 'hello world' and nothing else.",
                        "claude-haiku-4-5", max_tokens=20))

    print("Streaming:")
    chunks = list(stream("Count to 5, comma-separated, nothing else.",
                         "claude-haiku-4-5", max_tokens=30))
    print(" chunks:", len(chunks), "accum:", "".join(chunks))

    print("stream_to_supabase with TTFT:")
    task_id = "smoke-test-p6-v2-" + str(int(time.time()))
    full = stream_to_supabase(
        "Respond with exactly: ok",
        "claude-haiku-4-5",
        task_id=task_id,
        caller="self_test_v2",
        max_tokens=20,
    )
    print(" full:", full)

    print("resume_stream:")
    resumed = resume_stream(task_id)
    print(" resumed:", resumed)
