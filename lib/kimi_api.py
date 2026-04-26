"""
kimi_api.py — Kimi K2.6 (Moonshot) API client wrapper.

Used by scripts/hercules_daemon.py to put Hercules's brain on a Python daemon
instead of a sleep-when-tab-closes web chat. Single-purpose client: build
context packet → send to Kimi K2.6 → parse JSON action response → return.

Key resolution: tries env MOONSHOT_API_KEY first, then KIMI_API_KEY, then
SSHs to VPS to read /etc/amg/moonshot.env (same pattern as
agent_dispatch_bridge.py:_key()).

Cost (kimi-k2.6 on Moonshot, 2026-04 pricing):
    Input:  ~$0.60 / 1M tokens
    Output: ~$2.50 / 1M tokens
A typical Hercules context packet is 1-3K input tokens + 300-800 output, so
each call costs ~$0.001-0.005. Daemon polls every 30s but only calls Kimi
when a trigger condition fires (new mercury-proof, new violation, etc.) —
practical spend ~$1-3/day under normal operation.

Public API:
    chat(system_prompt, user_message, model="kimi-k2.6", max_tokens=1500)
        → {ok: bool, text: str, raw: dict, latency_ms: int, tokens_in: int,
           tokens_out: int, cost_usd_est: float, error: str|None}
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOME = pathlib.Path.home()
SSH_HOST = os.environ.get("AMG_SSH_HOST", "amg-staging")
KIMI_ENDPOINT = "https://api.moonshot.ai/v1/chat/completions"
DEFAULT_MODEL = "kimi-k2.6"
DEFAULT_TIMEOUT_S = 120

# Pricing per 1M tokens (USD). Update if Moonshot changes pricing.
PRICING_USD_PER_M = {
    "kimi-k2.6": {"input": 0.60, "output": 2.50},
    "kimi-k2-1106": {"input": 0.60, "output": 2.50},  # alias variant
}


def _load_env_remote_one(file_hint: str) -> dict:
    """SSH to VPS, cat /etc/amg/<file_hint>.env, parse KEY=VAL lines.
    Mirrors the agent_dispatch_bridge._load_env_remote() pattern."""
    cmd = ["ssh", "-o", "ConnectTimeout=5", SSH_HOST,
           f"cat /etc/amg/{file_hint}.env 2>/dev/null"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if out.returncode != 0:
            return {}
        env = {}
        for line in out.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
        return env
    except Exception:
        return {}


def _resolve_api_key() -> str | None:
    """Env first, then VPS env file."""
    for env_var in ("MOONSHOT_API_KEY", "KIMI_API_KEY"):
        v = os.environ.get(env_var)
        if v:
            return v
    env = _load_env_remote_one("moonshot")
    return env.get("MOONSHOT_API_KEY") or env.get("KIMI_API_KEY")


def _estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    p = PRICING_USD_PER_M.get(model) or PRICING_USD_PER_M[DEFAULT_MODEL]
    return (tokens_in * p["input"] / 1_000_000) + (tokens_out * p["output"] / 1_000_000)


def chat(
    system_prompt: str,
    user_message: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1500,
    temperature: float = 1.0,  # Kimi K2.6 only accepts temperature=1
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> dict:
    """Single-turn Kimi K2.6 chat call. Returns dict with ok/text/raw/cost."""
    t0 = time.time()
    key = _resolve_api_key()
    if not key:
        return {
            "ok": False, "error": "no MOONSHOT_API_KEY in env or /etc/amg/moonshot.env on VPS",
            "text": "", "raw": {}, "latency_ms": 0,
            "tokens_in": 0, "tokens_out": 0, "cost_usd_est": 0.0,
        }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    req = urllib.request.Request(
        KIMI_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            data = json.loads(r.read())
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        usage = data.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens", 0))
        tokens_out = int(usage.get("completion_tokens", 0))
        cost = _estimate_cost_usd(model, tokens_in, tokens_out)
        return {
            "ok": True, "text": text, "raw": data,
            "latency_ms": int((time.time() - t0) * 1000),
            "tokens_in": tokens_in, "tokens_out": tokens_out,
            "cost_usd_est": round(cost, 6),
            "model": model,
            "error": None,
        }
    except urllib.error.HTTPError as e:
        return {
            "ok": False,
            "error": f"HTTP {e.code}: {e.read()[:300].decode('utf-8', errors='replace')}",
            "text": "", "raw": {},
            "latency_ms": int((time.time() - t0) * 1000),
            "tokens_in": 0, "tokens_out": 0, "cost_usd_est": 0.0,
        }
    except Exception as e:
        return {
            "ok": False, "error": repr(e), "text": "", "raw": {},
            "latency_ms": int((time.time() - t0) * 1000),
            "tokens_in": 0, "tokens_out": 0, "cost_usd_est": 0.0,
        }


def parse_action_json(text: str) -> dict:
    """Hercules's response should be a JSON action block. Be permissive about
    code-fenced JSON, leading/trailing text, etc.

    Expected schema:
        {
          "action": "dispatch_new" | "escalate_solon" | "silent" | "update_sprint",
          "priority": "P0" | "P1" | "P2",
          "summary": "<one-line>",
          "payload": { ... action-specific }
        }
    """
    # Try fenced ```json ... ``` first
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = m.group(1) if m else None
    # Then any top-level {...} block
    if not candidate:
        m = re.search(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})", text, re.DOTALL)
        candidate = m.group(1) if m else None
    if not candidate:
        return {"action": "silent", "priority": "P3", "summary": "(no JSON in response)", "payload": {}}
    try:
        obj = json.loads(candidate)
    except Exception:
        return {"action": "silent", "priority": "P3", "summary": "(unparseable JSON)", "payload": {}}
    obj.setdefault("action", "silent")
    obj.setdefault("priority", "P3")
    obj.setdefault("summary", "")
    obj.setdefault("payload", {})
    return obj


# Smoke test entrypoint
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--smoke":
        result = chat(
            system_prompt="You are a smoke-test responder. Reply with exactly the JSON: {\"ok\": true, \"msg\": \"kimi alive\"}",
            user_message="ping",
            max_tokens=50,
        )
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("ok") else 1)
    print("Usage: python3 kimi_api.py --smoke")
    sys.exit(1)
