"""
titan-harness/lib/context_builder.py - Phase P4 (war-room graded A in spec)

Builds trimmed, relevance-ranked LLM prompt context from harness memory.
Sources (priority order): standing_rules -> mem_ground_truth_facts ->
agent_config.kb_context -> tool_log recent -> auto-memory markdown.

Public API:
    build_context(task, caller, max_tokens=8000) -> (context_text, metadata)
    embed(text) -> list[float]   (uses LiteLLM gateway + nomic-embed-text)

CORE CONTRACT: capacity-gates via lib/capacity.py; logs every build to
Supabase context_builds for observability.
"""
from __future__ import annotations

import os
import sys
import time
import json
import hashlib
import uuid
from typing import Optional
from urllib import request, error

# Ensure lib is on path for capacity import
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

# Per-source token caps (percent of max_tokens)
SOURCE_CAPS = {
    "rules":    0.15,
    "facts":    0.30,
    "kb":       0.35,
    "tool_log": 0.15,
    "slack":    0.05,
}


# ---------------------------------------------------------------------------
# Embedding helper (LiteLLM gateway -> ollama/nomic-embed-text)
# ---------------------------------------------------------------------------
def embed(text: str, model: str = "nomic-embed-text") -> list[float]:
    """Return an embedding vector for the given text via the LLM gateway."""
    if not LITELLM_MASTER_KEY:
        return []
    body = json.dumps({"model": model, "input": text}).encode()
    req = request.Request(
        LITELLM_BASE_URL + "/v1/embeddings",
        data=body,
        headers={
            "Authorization": "Bearer " + LITELLM_MASTER_KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
            if d.get("data"):
                return d["data"][0].get("embedding", [])
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Supabase fetchers (one per source, fail-open on error)
# ---------------------------------------------------------------------------
def _supa_get(path: str) -> list:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        req = request.Request(
            SUPABASE_URL + "/rest/v1/" + path,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": "Bearer " + SUPABASE_KEY,
                "Accept": "application/json",
            },
        )
        with request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        return []


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


def _get_standing_rules(scope: str = "both", limit: int = 15) -> list[dict]:
    rows = _supa_get("standing_rules?active=eq.true&order=priority.desc&limit=" + str(limit))
    return [r for r in rows if r.get("scope") in (scope, "both") or scope == "both"]


def _get_facts(task_project: Optional[str] = None, limit: int = 20) -> list[dict]:
    q = "mem_ground_truth_facts?select=*&limit=" + str(limit)
    if task_project:
        q += "&project=eq." + task_project
    return _supa_get(q)


def _get_agent_kb(agent_id: Optional[str]) -> str:
    if not agent_id:
        return ""
    rows = _supa_get("agent_config?agent_id=eq." + agent_id + "&select=kb_context&limit=1")
    if rows and rows[0].get("kb_context"):
        return str(rows[0]["kb_context"])
    return ""


def _get_recent_tool_log(session_id: Optional[str] = None, limit: int = 5) -> list[dict]:
    q = "tool_log?order=ts.desc&limit=" + str(limit)
    if session_id:
        q += "&session_id=eq." + session_id
    return _supa_get(q)


# ---------------------------------------------------------------------------
# Token estimation (cheap — 1 token ~= 4 chars)
# ---------------------------------------------------------------------------
def _est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _fit_to_budget(items: list[tuple[str, float]], budget_tokens: int) -> list[str]:
    """Greedy-fill: sort by relevance descending, take until budget exhausted."""
    items = sorted(items, key=lambda x: -x[1])
    out = []
    used = 0
    for text, _score in items:
        t = _est_tokens(text)
        if used + t > budget_tokens:
            continue
        out.append(text)
        used += t
    return out


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def build_context(task: dict, caller: str, max_tokens: int = 8000) -> tuple[str, dict]:
    """Assemble trimmed context for a task. Returns (context_text, metadata)."""
    start = time.time()

    # Capacity gate (soft-warn, not block — resolution is cheap)
    cap = check_capacity()

    task_id = task.get("id") or task.get("task_id")
    task_type = task.get("task_type") or task.get("type")
    task_project = task.get("project") or task.get("project_id") or "EOM"
    agent_id = task.get("agent_id")
    session_id = task.get("session_id")
    task_prompt = task.get("prompt") or task.get("summary") or ""

    # ---- Gather from sources ----
    rules = _get_standing_rules(scope="both", limit=15)
    facts = _get_facts(task_project=task_project, limit=20)
    kb_text = _get_agent_kb(agent_id)
    tool_log = _get_recent_tool_log(session_id=session_id, limit=5)

    # ---- Convert to scored text items ----
    # Simple keyword-based relevance scoring (pgvector backfill is follow-on).
    def _score(text: str, task_words: set) -> float:
        tw = set(text.lower().split()) & task_words
        return len(tw) / max(1, len(task_words))

    task_words = set(task_prompt.lower().split())

    rule_items = [(f"[RULE] {r.get('rule_text','')}", 1.0) for r in rules if r.get("rule_text")]
    fact_items = [(f"[FACT] {f.get('fact_text','')}", _score(f.get("fact_text",""), task_words))
                  for f in facts if f.get("fact_text")]
    kb_items = []
    if kb_text:
        kb_items = [(f"[KB:{agent_id}] " + kb_text[:2000], 1.0)]
    tl_items = [(f"[TOOL] {t.get('tool_name','')} task={t.get('task_id','')}", 0.5)
                for t in tool_log]

    # ---- Per-source token caps ----
    caps = {k: int(max_tokens * v) for k, v in SOURCE_CAPS.items()}

    rules_text = _fit_to_budget(rule_items, caps["rules"])
    facts_text = _fit_to_budget(fact_items, caps["facts"])
    kb_text_list = _fit_to_budget(kb_items, caps["kb"])
    tl_text = _fit_to_budget(tl_items, caps["tool_log"])

    # ---- Assemble ----
    parts = []
    if rules_text:
        parts.append("[STANDING RULES — binding]\n" + "\n".join(rules_text))
    if facts_text:
        parts.append("[RELEVANT FACTS]\n" + "\n".join(facts_text))
    if kb_text_list:
        parts.append("[AGENT KB]\n" + "\n".join(kb_text_list))
    if tl_text:
        parts.append("[RECENT TOOL LOG]\n" + "\n".join(tl_text))
    parts.append("[TASK]\n" + task_prompt)

    context = "\n\n".join(parts)
    final_tokens = _est_tokens(context)
    duration_ms = int((time.time() - start) * 1000)

    # ---- Dedup long content across sources (hash-based) ----
    seen_hashes = set()
    deduped_parts = []
    for p in parts:
        h = hashlib.sha1(p.encode()).hexdigest()
        if h not in seen_hashes:
            seen_hashes.add(h)
            deduped_parts.append(p)
    context = "\n\n".join(deduped_parts)

    metadata = {
        "caller": caller,
        "task_id": task_id,
        "task_type": task_type,
        "max_tokens": max_tokens,
        "final_tokens": final_tokens,
        "sources_used": {
            "rules": len(rules_text),
            "facts": len(facts_text),
            "kb":    len(kb_text_list),
            "tool_log": len(tl_text),
        },
        "build_duration_ms": duration_ms,
        "cache_hit": False,
        "capacity_status": {0: "ok", 1: "soft_block", 2: "hard_block"}.get(cap, "ok"),
    }

    # ---- Log observability (fail-open) ----
    _supa_post("context_builds", {
        "caller": caller,
        "task_id": str(task_id) if task_id else None,
        "task_type": task_type,
        "max_tokens": max_tokens,
        "final_tokens": final_tokens,
        "sources_used": metadata["sources_used"],
        "relevance_scores": {},
        "build_duration_ms": duration_ms,
        "cache_hit": False,
    })

    return context, metadata


# ---------------------------------------------------------------------------
# Bypass violation logger — callers that skip the builder MUST call this
# ---------------------------------------------------------------------------
def report_bypass(caller: str, task_id: Optional[str], reason: str) -> bool:
    return _supa_post("context_builder_bypasses", {
        "caller": caller,
        "task_id": str(task_id) if task_id else None,
        "reason": reason,
    })


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Smoke-test embed
    print("embed('hello world') ->", end=" ")
    v = embed("hello world")
    print("dim=" + str(len(v)) if v else "EMPTY")

    # Smoke-test build_context
    ctx, meta = build_context(
        {"id": "smoke-test", "task_type": "synthesis", "project": "EOM",
         "prompt": "Summarize the AMG pricing source of truth"},
        caller="smoke_test",
        max_tokens=4000,
    )
    print("context tokens:", meta["final_tokens"])
    print("sources_used:", meta["sources_used"])
    print("capacity_status:", meta["capacity_status"])
    print("first 500 chars:\n" + ctx[:500])
