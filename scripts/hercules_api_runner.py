#!/usr/bin/env python3
"""hercules_api_runner.py — Phase 0 of Hercules Deployment Order v2.0
(Solon directive 2026-04-27).

Runs Hercules through the Kimi K2 API endpoint with **native function/tool
calling**, exactly the same pattern Anthropic uses for Claude EOM in
claude.ai. Eliminates the Titan-chat-scrape intermediary.

Architecture:
  user input → Kimi K2 API (with system prompt + tool schema)
            ← assistant response (may include tool_calls)
  if tool_calls present:
    for each call: execute via mcp_rest_client → append result as role=tool
    re-call API with updated convo
    loop until no more tool_calls
  ← final assistant text response → print to user

Same script powers Hercules, Nestor, and Alexander via `--persona <name>`
(reads scripts/personas/<name>_system_prompt.md). Per-persona convo history
in sqlite at ~/.openclaw/state/<persona>_convo.db.

Run modes:
    hercules_api_runner.py --persona hercules --message "your question"
    hercules_api_runner.py --persona hercules --interactive   # REPL
    hercules_api_runner.py --persona hercules --new-session   # wipe + start fresh
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))

from mcp_rest_client import (  # noqa: E402
    queue_task as mcp_queue_task,
    get_task_queue as mcp_get_task_queue,
    log_decision as mcp_log_decision_fn,
    get_recent_decisions as mcp_get_recent_decisions_fn,
    get_sprint_state as mcp_get_sprint_state_fn,
)

KIMI_ENDPOINT = "https://api.moonshot.ai/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("HERCULES_MODEL", "kimi-k2.6")
MAX_TOKENS = 4096
TOOL_LOOP_MAX = 8  # safety: max tool-call rounds before giving up
SSH_HOST = os.environ.get("AMG_VPS_SSH_HOST", "amg-staging")
PERSONAS_DIR = HOME / "titan-harness" / "scripts" / "personas"
STATE_DIR = HOME / ".openclaw" / "state"
LOG_DIR = HOME / ".openclaw" / "logs"
MCP_BASE = os.environ.get("MCP_BASE", "https://memory.aimarketinggenius.io")


def _log(persona: str, msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with (LOG_DIR / f"{persona}_api_runner.log").open("a") as f:
        f.write(f"[{ts}] {msg}\n")


# ─── Kimi API key resolver ──────────────────────────────────────────────────
def _resolve_kimi_key() -> str:
    for v in ("MOONSHOT_API_KEY", "KIMI_API_KEY"):
        x = os.environ.get(v)
        if x:
            return x
    out = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=8", SSH_HOST,
         "grep -E '^(MOONSHOT_API_KEY|KIMI_API_KEY)=' /etc/amg/moonshot.env 2>/dev/null | head -1 | cut -d= -f2-"],
        capture_output=True, text=True, timeout=15,
    )
    key = (out.stdout or "").strip()
    if key:
        return key
    local = HOME / ".config" / "amg" / "kimi.env"
    if local.exists():
        for line in local.read_text().splitlines():
            for prefix in ("MOONSHOT_API_KEY=", "KIMI_API_KEY="):
                if line.startswith(prefix):
                    return line.split("=", 1)[1].strip()
    raise RuntimeError("Kimi API key not found")


# ─── conversation history ───────────────────────────────────────────────────
def _convo_db(persona: str) -> pathlib.Path:
    return STATE_DIR / f"{persona}_convo.db"


def _init_convo_db(persona: str) -> None:
    path = _convo_db(persona)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts TEXT NOT NULL,
          session_id TEXT NOT NULL,
          role TEXT NOT NULL,
          content TEXT,
          tool_call_id TEXT,
          name TEXT,
          tool_calls_json TEXT,
          reasoning_content TEXT
        )
    """)
    # Migrate older schema
    cols = [r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()]
    if "reasoning_content" not in cols:
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN reasoning_content TEXT")
            conn.commit()
        except Exception:
            pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
          session_id TEXT PRIMARY KEY,
          started_at TEXT NOT NULL,
          last_activity TEXT
        )
    """)
    conn.commit()
    conn.close()


def _current_session(persona: str, new: bool = False) -> str:
    _init_convo_db(persona)
    conn = sqlite3.connect(_convo_db(persona))
    if new:
        sid = "session-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        conn.execute("INSERT INTO sessions (session_id, started_at) VALUES (?, ?)",
                     (sid, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
        return sid
    row = conn.execute("SELECT session_id FROM sessions ORDER BY started_at DESC LIMIT 1").fetchone()
    if row:
        sid = row[0]
    else:
        sid = "session-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        conn.execute("INSERT INTO sessions (session_id, started_at) VALUES (?, ?)",
                     (sid, datetime.now(timezone.utc).isoformat()))
        conn.commit()
    conn.close()
    return sid


def _load_convo(persona: str, session_id: str, max_messages: int = 40) -> list[dict]:
    """Load the last N messages of this session as Kimi-API-shaped dicts."""
    _init_convo_db(persona)
    conn = sqlite3.connect(_convo_db(persona))
    rows = conn.execute(
        "SELECT role, content, tool_call_id, name, tool_calls_json, reasoning_content FROM messages "
        "WHERE session_id=? ORDER BY id DESC LIMIT ?",
        (session_id, max_messages),
    ).fetchall()
    conn.close()
    rows.reverse()
    out = []
    for role, content, tcid, name, tc_json, rc in rows:
        msg = {"role": role}
        if content is not None:
            msg["content"] = content
        if tcid:
            msg["tool_call_id"] = tcid
        if name:
            msg["name"] = name
        if tc_json:
            try:
                msg["tool_calls"] = json.loads(tc_json)
            except Exception:
                pass
        if rc:
            msg["reasoning_content"] = rc
        out.append(msg)
    return out


def _save_msg(persona: str, session_id: str, msg: dict) -> None:
    _init_convo_db(persona)
    conn = sqlite3.connect(_convo_db(persona))
    conn.execute(
        "INSERT INTO messages (ts, session_id, role, content, tool_call_id, name, tool_calls_json, reasoning_content) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            datetime.now(timezone.utc).isoformat(),
            session_id,
            msg.get("role", "user"),
            msg.get("content"),
            msg.get("tool_call_id"),
            msg.get("name"),
            json.dumps(msg.get("tool_calls")) if msg.get("tool_calls") else None,
            msg.get("reasoning_content"),
        ),
    )
    conn.execute(
        "UPDATE sessions SET last_activity=? WHERE session_id=?",
        (datetime.now(timezone.utc).isoformat(), session_id),
    )
    conn.commit()
    conn.close()


def _load_recent_messages_across_sessions(persona: str, limit: int = 20) -> list[dict]:
    """Pull the last N messages for this persona across ALL sessions, newest
    first. Used by cold-start hydration so a fresh session can still see the
    most recent operational state. Returns the messages in reverse-chrono
    order with ts attached for human readability."""
    _init_convo_db(persona)
    conn = sqlite3.connect(_convo_db(persona))
    rows = conn.execute(
        "SELECT ts, session_id, role, content FROM messages "
        "WHERE role IN ('user','assistant') AND content IS NOT NULL "
        "ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [
        {"ts": ts, "session_id": sid, "role": role,
         "content_preview": (content or "")[:600]}
        for ts, sid, role, content in rows
    ]


def _count_assistant_turns(persona: str, session_id: str) -> int:
    """Count assistant messages in this session — used by the every-10-turn
    auto-snapshot trigger. Tool-call rounds DON'T count (those have role=
    'assistant' too but content=None or tool_calls set), only final
    assistant text replies do."""
    _init_convo_db(persona)
    conn = sqlite3.connect(_convo_db(persona))
    row = conn.execute(
        "SELECT COUNT(*) FROM messages "
        "WHERE session_id=? AND role='assistant' AND content IS NOT NULL "
        "AND content != '' AND tool_calls_json IS NULL",
        (session_id,),
    ).fetchone()
    conn.close()
    return int(row[0] if row else 0)


# ─── MCP tool schema (OpenAI-compatible function-calling format) ────────────
def _mcp_post(path: str, body: dict, timeout: int = 20) -> dict:
    url = f"{MCP_BASE.rstrip('/')}/{path.lstrip('/')}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return {"error": json.loads(e.read() or b"{}")}
        except Exception:
            return {"error": str(e)}


def _mcp_get(path: str, params: dict | None = None, timeout: int = 20) -> dict:
    import urllib.parse
    url = f"{MCP_BASE.rstrip('/')}/{path.lstrip('/')}"
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return {"error": json.loads(e.read() or b"{}")}
        except Exception:
            return {"error": str(e)}


# Tool implementations — each takes a dict of args and returns a JSON-serializable dict.
def tool_log_decision(args: dict) -> dict:
    code, body = mcp_log_decision_fn(
        text=args.get("text", ""),
        rationale=args.get("rationale"),
        tags=args.get("tags") or [],
        project_source=args.get("project_source", "hercules"),
    )
    return {"http_code": code, "result": body}


def tool_search_memory(args: dict) -> dict:
    return _mcp_post("/api/search-memory", {
        "query": args.get("query", ""),
        "count": args.get("count", 10),
        "project_filter": args.get("project_filter"),
    })


def tool_get_bootstrap_context(args: dict) -> dict:
    return _mcp_post("/api/bootstrap-context", {
        "scope": args.get("scope", "eom"),
        "project_id": args.get("project_id", "EOM"),
        "max_decisions": args.get("max_decisions", 10),
        "max_rules": args.get("max_rules", 15),
    })


def tool_queue_operator_task(args: dict) -> dict:
    payload = {
        "objective": args.get("objective", ""),
        "instructions": args.get("instructions", ""),
        "acceptance_criteria": args.get("acceptance_criteria", ""),
        "priority": args.get("priority", "normal"),
        "agent": args.get("agent", "ops"),
        "project_id": args.get("project_id", "AMG-ATLAS"),
        "queued_by": args.get("queued_by", "hercules"),
        "tags": args.get("tags") or [],
        "notes": args.get("notes"),
        "context": args.get("context"),
        "task_risk_tier": args.get("task_risk_tier", "exempt"),
    }
    code, body = mcp_queue_task(payload)
    return {"http_code": code, "result": body}


def tool_flag_blocker(args: dict) -> dict:
    return _mcp_post("/api/flag-blocker", {
        "description": args.get("description", ""),
        "severity": args.get("severity", "P2"),
        "blocking_what": args.get("blocking_what"),
        "owner": args.get("owner"),
        "project_id": args.get("project_id", "EOM"),
    })


def tool_update_sprint_state(args: dict) -> dict:
    return _mcp_post("/api/sprint-state", {
        "project_id": args.get("project_id", "EOM"),
        "sprint_name": args.get("sprint_name"),
        "kill_chain": args.get("kill_chain"),
        "blockers": args.get("blockers"),
        "completion_pct": args.get("completion_pct"),
        "infrastructure_status": args.get("infrastructure_status"),
    })


def tool_get_recent_decisions(args: dict) -> dict:
    code, body = mcp_get_recent_decisions_fn(
        count=args.get("count", 10),
        project_filter=args.get("project_filter"),
    )
    return {"http_code": code, "result": body}


def tool_get_sprint_state(args: dict) -> dict:
    code, body = mcp_get_sprint_state_fn(project_id=args.get("project_id", "EOM"))
    return {"http_code": code, "result": body}


TOOL_REGISTRY = {
    "log_decision": tool_log_decision,
    "search_memory": tool_search_memory,
    "get_bootstrap_context": tool_get_bootstrap_context,
    "queue_operator_task": tool_queue_operator_task,
    "flag_blocker": tool_flag_blocker,
    "update_sprint_state": tool_update_sprint_state,
    "get_recent_decisions": tool_get_recent_decisions,
    "get_sprint_state": tool_get_sprint_state,
}


TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "log_decision",
            "description": "Log a decision to AMG Memory (op_decisions table). Use this for every meaningful decision you make.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The decision text (1-3 sentences)."},
                    "rationale": {"type": "string", "description": "Why you made this decision."},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for searchability."},
                    "project_source": {"type": "string", "description": "Project tag, default 'hercules'."},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Semantic search across all AMG Memory decisions. Use before answering questions about prior work.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language query."},
                    "count": {"type": "integer", "description": "Max results (default 10)."},
                    "project_filter": {"type": "string", "description": "Optional project tag filter."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bootstrap_context",
            "description": "Pull standing rules + sprint state + recent decisions in one call. Use at session start on real work.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["eom", "titan", "both"], "description": "Rule scope."},
                    "project_id": {"type": "string", "description": "Default 'EOM'."},
                    "max_decisions": {"type": "integer"},
                    "max_rules": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "queue_operator_task",
            "description": "Issue an order to a builder via the Order Dispatcher. Use the lane-routing matrix in your system prompt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "objective": {"type": "string"},
                    "instructions": {"type": "string"},
                    "acceptance_criteria": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent", "blocker"]},
                    "agent": {"type": "string", "description": "Always 'ops' (MCP enum constraint)."},
                    "project_id": {"type": "string", "description": "Default 'AMG-ATLAS'."},
                    "queued_by": {"type": "string", "description": "Default 'hercules'."},
                    "tags": {"type": "array", "items": {"type": "string"},
                             "description": "Include agent:<name> tag to route (e.g. agent:daedalus, agent:nestor, agent:alexander, agent:athena, agent:hephaestus, agent:cerberus, agent:mercury)."},
                    "notes": {"type": "string"},
                    "context": {"type": "string"},
                },
                "required": ["objective", "instructions", "acceptance_criteria"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_blocker",
            "description": "Flag a new blocker that's preventing progress. Auto-escalates per severity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "severity": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
                    "blocking_what": {"type": "string"},
                    "owner": {"type": "string"},
                    "project_id": {"type": "string"},
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_sprint_state",
            "description": "Update sprint state (kill_chain, blockers, completion_pct, infrastructure_status).",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "sprint_name": {"type": "string"},
                    "kill_chain": {"type": "array", "items": {"type": "string"}},
                    "blockers": {"type": "array"},
                    "completion_pct": {"type": "number"},
                    "infrastructure_status": {"type": "object"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_decisions",
            "description": "Get the N most recent decisions across all projects.",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer"},
                    "project_filter": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sprint_state",
            "description": "Get current sprint state for a project.",
            "parameters": {
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
            },
        },
    },
]


# ─── persona prompt loader ──────────────────────────────────────────────────
def _load_system_prompt(persona: str) -> str:
    p = PERSONAS_DIR / f"{persona}_system_prompt.md"
    if not p.exists():
        raise FileNotFoundError(f"system prompt missing: {p}")
    return p.read_text(encoding="utf-8")


# ─── Kimi API call with tool-calling loop ──────────────────────────────────
def _call_kimi(api_key: str, messages: list[dict], tools: list[dict], temp: float = 0.7) -> dict:
    # Kimi K2.6 only accepts temperature=1 per their API spec (returns 400 otherwise).
    body = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 1,
        "max_tokens": MAX_TOKENS,
    }
    req = urllib.request.Request(
        KIMI_ENDPOINT,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:1500]
        raise RuntimeError(f"Kimi API HTTP {e.code}: {err_body}") from e


# ─── cold-start hydration + rolling memory hooks ────────────────────────────
HYDRATION_USER_PROMPT = (
    "[HYDRATION_BRIEF] You are resuming after a runner restart. Above is your "
    "operational state at the moment of resume — recent factory decisions, the "
    "last few RESTART_HANDOFFs, your most recent persona snapshot, your rolling "
    "24h summary (if any), and the last 20 messages across your past sessions. "
    "Briefly (3-6 sentences) summarize: where we are, what was open at last "
    "checkpoint, and what the next concrete action is. Do NOT call any tools — "
    "just synthesize from the context. After you reply, I'll send the real "
    "next message."
)


def _build_hydration_context(persona: str) -> str:
    """Assemble the cold-start system addendum: bootstrap_context + recent
    handoffs + persona-specific snapshots + rolling 24h summary + last 20
    cross-session messages. All four MCP calls are best-effort — if any fails
    we still return what we have so the runner doesn't block on a transient
    MCP outage."""
    parts: list[str] = [
        "===== HYDRATION CONTEXT =====",
        f"Persona: {persona}",
        f"Resume time (UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    # 1. Bootstrap context — overall factory + project state.
    try:
        boot = tool_get_bootstrap_context({"scope": "eom", "project_id": "EOM",
                                           "max_decisions": 10, "max_rules": 15})
        parts.append("--- bootstrap_context (EOM) ---")
        parts.append(json.dumps(boot, default=str)[:3000])
        parts.append("")
    except Exception as e:
        parts.append(f"--- bootstrap_context FAILED: {e!r} ---\n")
    # 2. Last 3 restart_handoff entries.
    try:
        hand = tool_search_memory({"query": "restart_handoff", "count": 3})
        parts.append("--- search_memory(restart_handoff, n=3) ---")
        parts.append(json.dumps(hand, default=str)[:3000])
        parts.append("")
    except Exception as e:
        parts.append(f"--- restart_handoff search FAILED: {e!r} ---\n")
    # 3. Most recent snapshot for THIS persona (auto + manual + powerdown).
    try:
        snap = tool_search_memory({"query": f"snapshot:{persona}", "count": 1})
        parts.append(f"--- search_memory(snapshot:{persona}, n=1) ---")
        parts.append(json.dumps(snap, default=str)[:3000])
        parts.append("")
    except Exception as e:
        parts.append(f"--- snapshot search FAILED: {e!r} ---\n")
    # 4. Rolling 24h summary (written by scripts/persona_summary_daemon.py).
    try:
        rolling = tool_search_memory({"query": f"summary:{persona}:rolling_24h", "count": 1})
        parts.append(f"--- search_memory(summary:{persona}:rolling_24h, n=1) ---")
        parts.append(json.dumps(rolling, default=str)[:3000])
        parts.append("")
    except Exception as e:
        parts.append(f"--- rolling 24h summary FAILED: {e!r} ---\n")
    # 5. Last 20 cross-session messages from sqlite.
    try:
        recent = _load_recent_messages_across_sessions(persona, limit=20)
        parts.append(f"--- last 20 sqlite messages (cross-session, newest first) ---")
        for m in recent:
            parts.append(f"[{m['ts'][:19]} {m['role']}] {m['content_preview']}")
        parts.append("")
    except Exception as e:
        parts.append(f"--- sqlite recent messages FAILED: {e!r} ---\n")
    parts.append("===== END HYDRATION CONTEXT =====")
    return "\n".join(parts)


def cold_start_hydrate(persona: str, session_id: str, verbose: bool = False) -> dict:
    """Run cold-start hydration once on persona launch. Builds a context bundle,
    saves it as a synthetic system addendum + user prompt in the convo db,
    runs ONE Kimi turn so the persona briefs themselves, returns the result.

    Idempotent within a session — re-running on the same session is a no-op
    after the first hydration (we mark the session row with hydrated=1)."""
    _init_convo_db(persona)
    conn = sqlite3.connect(_convo_db(persona))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()]
    if "hydrated" not in cols:
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN hydrated INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass
    row = conn.execute(
        "SELECT hydrated FROM sessions WHERE session_id=?", (session_id,)
    ).fetchone()
    if row and row[0]:
        conn.close()
        if verbose:
            print(f"[hydrate] session {session_id} already hydrated, skipping", file=sys.stderr)
        return {"skipped": True, "reason": "already_hydrated", "session_id": session_id}
    conn.close()

    if verbose:
        print(f"[hydrate] gathering context for persona={persona}...", file=sys.stderr)
    ctx = _build_hydration_context(persona)
    # Save the context as a system message so subsequent turns see it.
    sys_msg = {"role": "system", "content": ctx}
    _save_msg(persona, session_id, sys_msg)
    if verbose:
        print(f"[hydrate] context block: {len(ctx)} chars; running brief turn...", file=sys.stderr)

    result = run_turn(persona, HYDRATION_USER_PROMPT, session_id=session_id,
                      temp=0.5, verbose=verbose, _from_hydration=True)

    # Mark session as hydrated.
    conn = sqlite3.connect(_convo_db(persona))
    conn.execute("UPDATE sessions SET hydrated=1 WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()
    return {
        "skipped": False,
        "session_id": session_id,
        "brief": result.get("text", ""),
        "cost_usd": result.get("cost_usd", 0),
    }


def _generate_auto_snapshot(persona: str, session_id: str, turn_count: int,
                            recent_messages: list[dict]) -> None:
    """Every-10-turn auto-snapshot. Calls log_decision with a brief summary
    of where the conversation thread is, so a tab-close / context-overflow /
    crash mid-session doesn't lose state. Cheaper than a Kimi summary call —
    just dumps the last few message previews and tags them snapshot:<persona>:auto."""
    bullets = []
    for m in recent_messages[-8:]:
        role = m.get("role", "?")
        content = (m.get("content") or "")
        if not content:
            continue
        bullets.append(f"[{role}] {content[:240]}")
    snapshot_text = (
        f"AUTO-SNAPSHOT persona={persona} session={session_id} "
        f"turn_count={turn_count} ts={datetime.now(timezone.utc).isoformat()}\n\n"
        + "\n".join(bullets)
    )[:2500]
    try:
        mcp_log_decision_fn(
            text=snapshot_text,
            rationale=f"Auto-snapshot every 10th turn — preserves thread state mid-session.",
            tags=[f"snapshot:{persona}:auto", f"session:{session_id}",
                  f"turn:{turn_count}", "rolling-memory"],
            project_source=persona,
        )
        _log(persona, f"auto-snapshot session={session_id} turn={turn_count} OK")
    except Exception as e:
        _log(persona, f"auto-snapshot FAILED session={session_id} turn={turn_count}: {e!r}")


def run_turn(persona: str, user_message: str, session_id: str | None = None,
             temp: float = 0.7, verbose: bool = False, _from_hydration: bool = False) -> dict:
    """One full conversation turn — user message in, final assistant text out.
    Resolves all tool calls along the way. Returns dict with `text`, `tool_calls`,
    `usage`, `cost_usd`, `session_id`."""
    if session_id is None:
        session_id = _current_session(persona)
    api_key = _resolve_kimi_key()
    system_prompt = _load_system_prompt(persona)
    history = _load_convo(persona, session_id, max_messages=40)
    user_msg = {"role": "user", "content": user_message}
    _save_msg(persona, session_id, user_msg)
    messages = [{"role": "system", "content": system_prompt}] + history + [user_msg]

    total_tokens_in = 0
    total_tokens_out = 0
    tool_call_log = []

    for round_n in range(TOOL_LOOP_MAX):
        if verbose:
            print(f"[round {round_n + 1}] calling Kimi K2 with {len(messages)} messages...", file=sys.stderr)
        resp = _call_kimi(api_key, messages, TOOL_SCHEMA, temp=temp)
        choice = (resp.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        usage = resp.get("usage") or {}
        total_tokens_in += usage.get("prompt_tokens", 0)
        total_tokens_out += usage.get("completion_tokens", 0)
        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            # final assistant text
            text = msg.get("content") or ""
            asst_msg = {"role": "assistant", "content": text}
            _save_msg(persona, session_id, asst_msg)
            cost = (total_tokens_in * 0.55 + total_tokens_out * 2.20) / 1_000_000
            _log(persona, f"turn ok session={session_id} tokens_in={total_tokens_in} tokens_out={total_tokens_out} cost=${cost:.4f} tool_calls={len(tool_call_log)}")
            # Auto-snapshot every 10th completed turn — skip when called from
            # the hydration path so the very-first hydration brief doesn't
            # immediately trigger a snapshot of itself.
            if not _from_hydration:
                try:
                    turn_count = _count_assistant_turns(persona, session_id)
                    if turn_count > 0 and turn_count % 10 == 0:
                        recent = _load_convo(persona, session_id, max_messages=12)
                        _generate_auto_snapshot(persona, session_id, turn_count, recent)
                except Exception as e:
                    _log(persona, f"auto-snapshot trigger failed (non-fatal): {e!r}")
            return {
                "text": text,
                "tool_calls": tool_call_log,
                "usage": {"in": total_tokens_in, "out": total_tokens_out},
                "cost_usd": round(cost, 5),
                "session_id": session_id,
            }
        # tool call round — execute each, append results, loop.
        # Kimi K2 with `thinking` enabled REQUIRES reasoning_content on
        # assistant tool-call messages or it 400s the next round.
        asst_msg = {"role": "assistant", "content": msg.get("content"), "tool_calls": tool_calls}
        if msg.get("reasoning_content"):
            asst_msg["reasoning_content"] = msg.get("reasoning_content")
        _save_msg(persona, session_id, asst_msg)
        messages.append(asst_msg)
        for tc in tool_calls:
            fn_name = (tc.get("function") or {}).get("name") or ""
            fn_args_raw = (tc.get("function") or {}).get("arguments") or "{}"
            try:
                fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
            except Exception:
                fn_args = {}
            if verbose:
                print(f"  → tool: {fn_name}({json.dumps(fn_args)[:120]}...)", file=sys.stderr)
            handler = TOOL_REGISTRY.get(fn_name)
            if handler:
                try:
                    result = handler(fn_args)
                except Exception as e:
                    result = {"error": f"tool exception: {e!r}"}
            else:
                result = {"error": f"unknown tool: {fn_name}"}
            tool_call_log.append({"name": fn_name, "args": fn_args, "result_preview": str(result)[:200]})
            tool_msg = {
                "role": "tool",
                "tool_call_id": tc.get("id"),
                "name": fn_name,
                "content": json.dumps(result, default=str)[:8000],
            }
            _save_msg(persona, session_id, tool_msg)
            messages.append(tool_msg)
    # exceeded TOOL_LOOP_MAX
    _log(persona, f"turn FAIL session={session_id} exceeded {TOOL_LOOP_MAX} tool-call rounds")
    return {
        "text": f"(error: exceeded {TOOL_LOOP_MAX} tool-call rounds — possible infinite loop)",
        "tool_calls": tool_call_log,
        "usage": {"in": total_tokens_in, "out": total_tokens_out},
        "cost_usd": round((total_tokens_in * 0.55 + total_tokens_out * 2.20) / 1_000_000, 5),
        "session_id": session_id,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--persona", default="hercules", help="hercules, nestor, or alexander")
    p.add_argument("--message", "-m", help="single message to send (non-interactive mode)")
    p.add_argument("--interactive", "-i", action="store_true", help="REPL mode")
    p.add_argument("--new-session", action="store_true", help="start a fresh session")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--smoke-test", action="store_true",
                   help="run all 5 Hercules smoke tests from Phase 0.D-F")
    p.add_argument("--no-hydrate", action="store_true",
                   help="skip cold-start hydration (faster startup, no MCP context lookup)")
    args = p.parse_args()

    if args.smoke_test:
        return _smoke_test(args.persona, args.verbose)

    sid = _current_session(args.persona, new=args.new_session)

    # Cold-start hydration: persona briefs themselves on the operational state
    # at resume time before any user input. Idempotent within a session.
    # Skipped via --no-hydrate or when --smoke-test runs above.
    if not args.no_hydrate:
        try:
            hyd = cold_start_hydrate(args.persona, sid, verbose=args.verbose)
            if not hyd.get("skipped") and hyd.get("brief"):
                print(f"\n[{args.persona} resume brief]\n{hyd['brief']}\n", file=sys.stderr)
        except Exception as e:
            print(f"[hydrate] failed (non-fatal): {e!r}", file=sys.stderr)

    if args.interactive:
        print(f"[hercules-api-runner persona={args.persona} session={sid}] type ':quit' to exit", file=sys.stderr)
        while True:
            try:
                line = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not line:
                continue
            if line in {":quit", ":q", "exit"}:
                return 0
            if line == ":new":
                sid = _current_session(args.persona, new=True)
                print(f"[new session: {sid}]", file=sys.stderr)
                continue
            result = run_turn(args.persona, line, session_id=sid, temp=args.temperature, verbose=args.verbose)
            print(f"\n{result['text']}\n")
            if result["tool_calls"]:
                print(f"  [{len(result['tool_calls'])} tool call(s), cost=${result['cost_usd']:.4f}]\n", file=sys.stderr)
        return 0

    if not args.message:
        print("error: --message or --interactive required", file=sys.stderr)
        return 1

    result = run_turn(args.persona, args.message, session_id=sid, temp=args.temperature, verbose=args.verbose)
    print(json.dumps({
        "text": result["text"],
        "tool_calls": [{"name": tc["name"], "args": tc["args"]} for tc in result["tool_calls"]],
        "cost_usd": result["cost_usd"],
        "session_id": result["session_id"],
    }, indent=2, default=str))
    return 0


def _smoke_test(persona: str, verbose: bool) -> int:
    """Phase 0.D-F: run the 5 Hercules smoke tests from Solon's order."""
    tests = [
        ("memory_read", "Pull the last 5 decisions from AMG Memory and summarize them in 3-4 lines."),
        ("memory_write", "Log a test decision with text 'Hercules went live on 2026-04-27 via API runner Phase 0' and tags ['hercules-go-live', 'phase-0', 'api-runner']."),
        ("sprint_state", "What's our current sprint state? Pull it from MCP, do not fabricate."),
        ("operating_discipline", "Help me grow AMG."),
        ("order_issuance", "Issue a research order on home services pricing in Boston metro. Route to Athena."),
    ]
    sid = _current_session(persona, new=True)
    print(f"=== smoke test starting (session {sid}) ===\n", file=sys.stderr)
    results = []
    for name, msg in tests:
        print(f"\n--- {name} ---", file=sys.stderr)
        print(f"USER: {msg}", file=sys.stderr)
        try:
            r = run_turn(persona, msg, session_id=sid, verbose=verbose)
            print(f"\nASSISTANT: {r['text'][:600]}\n", file=sys.stderr)
            print(f"  cost=${r['cost_usd']:.4f}  tool_calls={[tc['name'] for tc in r['tool_calls']]}", file=sys.stderr)
            results.append({"test": name, "ok": True, "text_preview": r["text"][:200],
                            "tool_calls": [tc["name"] for tc in r["tool_calls"]],
                            "cost_usd": r["cost_usd"]})
        except Exception as e:
            print(f"  FAIL: {e!r}", file=sys.stderr)
            results.append({"test": name, "ok": False, "error": repr(e)})
    print("\n=== smoke test summary ===", file=sys.stderr)
    for r in results:
        if r.get("ok"):
            print(f"  ✅ {r['test']}: tool_calls={r['tool_calls']} cost=${r['cost_usd']:.4f}", file=sys.stderr)
        else:
            print(f"  ❌ {r['test']}: {r['error']}", file=sys.stderr)
    print(json.dumps(results, indent=2, default=str))
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
