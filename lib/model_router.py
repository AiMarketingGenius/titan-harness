"""
titan-harness/lib/model_router.py - Phase P3 (war-room graded A in spec)

Resolves a task_type (or task dict) to a concrete LiteLLM gateway model_group.
Reads POLICY_MODEL_DEFAULT and POLICY_MODEL_ROUTING_JSON populated by
lib/policy-loader.sh from policy.yaml `models:` block.

Public API:
    resolve_model(task_type, task=None) -> str
    resolve_with_fallback(task_type, task=None) -> list[str]  # primary + fallbacks
    log_choice(task_id, task_type, model, fallback_from=None, cost_cents=0, latency_ms=0)

Logging: writes to Supabase model_router_choices on every call; writes to
model_router_misses when task_type is unknown (falls back to default).

CORE CONTRACT: capacity-gates the call itself — resolution is cheap, so this
is mainly to surface hard_block as a pre-flight warning in the caller's path.
"""
from __future__ import annotations

import os
import json
import time
import uuid
from typing import Optional
from urllib import request, error


# ------------------------------------------------------------------ config
_DEFAULT_MODEL = os.environ.get("POLICY_MODEL_DEFAULT", "claude-sonnet-4-6")
_ROUTING_JSON = os.environ.get("POLICY_MODEL_ROUTING_JSON", "{}")
try:
    _ROUTING = json.loads(_ROUTING_JSON) if _ROUTING_JSON else {}
except json.JSONDecodeError:
    _ROUTING = {}

# Escape-hatch env overrides
_FORCE_MODEL = os.environ.get("FORCE_MODEL")

# Complexity-based bump: simple -> Haiku, medium -> Sonnet, hard -> Opus
# (only applies when task_type is ambiguous or task.complexity is set)
_COMPLEXITY_BUMP = {
    "simple": "claude-haiku-4-5",
    "medium": "claude-sonnet-4-6",
    "hard":   "claude-opus-4-6",
}

# Fallback chains per primary model (cheapest equivalent first)
_FALLBACK_CHAINS = {
    "claude-opus-4-6":   ["claude-sonnet-4-6", "claude-haiku-4-5"],
    "claude-sonnet-4-6": ["claude-haiku-4-5"],
    "claude-haiku-4-5":  [],
    "sonar-pro":         ["sonar"],
    "sonar":             [],
    "nomic-embed-text":  [],
}


# ------------------------------------------------------------------ supabase
_SUPA_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
_SUPA_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _supa_post(path: str, body: dict) -> bool:
    if not _SUPA_URL or not _SUPA_KEY:
        return False
    try:
        req = request.Request(
            _SUPA_URL + "/rest/v1/" + path,
            data=json.dumps(body).encode(),
            headers={
                "apikey": _SUPA_KEY,
                "Authorization": "Bearer " + _SUPA_KEY,
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=5) as r:
            return 200 <= r.status < 300
    except Exception:
        return False  # fail-open — router never blocks a caller on log failure


# ------------------------------------------------------------------ resolve
def resolve_model(task_type: Optional[str], task: Optional[dict] = None) -> str:
    """Return the canonical model_group for a task_type.

    Precedence:
        1. FORCE_MODEL env var (escape hatch)
        2. task["model_override"] if present
        3. task["complexity"] mapped via _COMPLEXITY_BUMP
        4. _ROUTING[task_type]
        5. _DEFAULT_MODEL
    """
    if _FORCE_MODEL:
        return _FORCE_MODEL

    if task:
        if task.get("model_override"):
            return str(task["model_override"])
        complexity = task.get("complexity")
        if complexity and complexity in _COMPLEXITY_BUMP:
            return _COMPLEXITY_BUMP[complexity]

    if task_type and task_type in _ROUTING:
        return _ROUTING[task_type]

    # Miss: log it for tuning
    if task_type:
        _supa_post("model_router_misses", {
            "task_type": task_type,
            "task_id": (task or {}).get("id"),
            "fallback_to": _DEFAULT_MODEL,
        })

    return _DEFAULT_MODEL


def resolve_with_fallback(task_type: Optional[str], task: Optional[dict] = None) -> list[str]:
    """Return primary + fallback models in priority order."""
    primary = resolve_model(task_type, task)
    return [primary] + _FALLBACK_CHAINS.get(primary, [])


# ------------------------------------------------------------------ observability
def log_choice(task_id: Optional[str], task_type: Optional[str], model: str,
               fallback_from: Optional[str] = None,
               cost_cents: float = 0.0, latency_ms: int = 0) -> bool:
    return _supa_post("model_router_choices", {
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "task_type": task_type,
        "chosen_model": model,
        "fallback_from": fallback_from,
        "cost_cents": cost_cents,
        "latency_ms": latency_ms,
        "chosen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })


# ------------------------------------------------------------------ self-test
if __name__ == "__main__":
    print("POLICY_MODEL_DEFAULT =", _DEFAULT_MODEL)
    print("POLICY_MODEL_ROUTING =", _ROUTING)
    tests = [
        ("transform", None),
        ("classify", None),
        ("plan", None),
        ("architecture", None),
        ("synthesis", None),
        ("war_room_grade", None),
        ("war_room_revise", None),
        ("research", None),
        ("unknown_task", None),
        (None, {"complexity": "hard"}),
        ("classify", {"complexity": "hard"}),  # complexity wins
        (None, {"model_override": "claude-opus-4-6"}),
    ]
    for tt, task in tests:
        m = resolve_model(tt, task)
        chain = resolve_with_fallback(tt, task)
        print(f"  {str(tt):20s} task={task} -> {m:25s} chain={chain}")
