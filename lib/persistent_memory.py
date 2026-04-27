#!/usr/bin/env python3
"""persistent_memory.py — Hercules's session-memory layer.

Phase 1.1 of Hercules's MASTER BUILD ORDER 2026-04-26: rolling 24h
context summary that survives restart, hydrates new Kimi tabs, and
pushes to a public gist Hercules can WebFetch on demand.

Two-tier persistence (Redis is NOT installed locally; sqlite + file is
the equivalent in our stack):

  Tier 1: rolling-summary.md (~/.openclaw/state/hercules_memory_summary.md)
    Compressed markdown of the last 24h of MCP op_decisions, refreshed
    every 5 min. ~3-5KB total. Hercules reads this on every startup.

  Tier 2: rolling-summary.sqlite (~/.openclaw/state/hercules_memory.db)
    Append-only history of every summary the daemon has ever produced
    (one row per 5-min cycle). Survives crashes. Replays on startup.

Compression: uses Artisan (DeepSeek V4 Flash, ~$0.001/cycle) to
distill 50 MCP decisions + queue snapshot + sprint into a single
markdown digest. Falls back to template-only digest if DeepSeek is
unreachable so the loop never stalls.

Public gist mirror: Hercules WebFetches mid-session for fresh context.

Run modes:
    persistent_memory.py --once        # one-shot regen + exit
    persistent_memory.py --watch       # daemon, every --interval seconds
    persistent_memory.py --hydrate     # print current summary (startup hydration)
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
from datetime import datetime, timedelta, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))

from mcp_rest_client import (  # noqa: E402
    get_recent_decisions as mcp_get_recent,
    get_sprint_state as mcp_get_sprint,
    get_task_queue as mcp_get_task_queue,
)

STATE_DIR = HOME / ".openclaw" / "state"
SUMMARY_FILE = STATE_DIR / "hercules_memory_summary.md"
HISTORY_DB = STATE_DIR / "hercules_memory.db"
LOG_FILE = HOME / ".openclaw" / "logs" / "persistent_memory.log"
WINDOW_HOURS = 24
SUMMARY_GIST_ID = os.environ.get("HERCULES_MEMORY_GIST_ID", "")
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
COMPRESSOR_MODEL = "deepseek-v4-flash"
SSH_HOST = "amg-staging"


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with LOG_FILE.open("a") as f:
        f.write(f"[{ts}] {msg}\n")


def _resolve_deepseek_key() -> str | None:
    for v in ("DEEPSEEK_API_KEY",):
        x = os.environ.get(v)
        if x:
            return x
    try:
        out = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=8", SSH_HOST,
             "grep '^DEEPSEEK_API_KEY=' /etc/amg/deepseek.env | cut -d= -f2-"],
            capture_output=True, text=True, timeout=15,
        )
        return (out.stdout or "").strip() or None
    except Exception:
        return None


def _init_db() -> None:
    HISTORY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(HISTORY_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts TEXT NOT NULL,
          window_start TEXT NOT NULL,
          window_end TEXT NOT NULL,
          decision_count INTEGER,
          summary_md TEXT,
          model TEXT,
          tokens_in INTEGER,
          tokens_out INTEGER,
          cost_usd REAL
        )
    """)
    conn.commit()
    conn.close()


def _gather_window() -> dict:
    code_d, body_d = mcp_get_recent(count=50)
    decisions = body_d.get("decisions") or [] if code_d == 200 else []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    in_window = []
    for d in decisions:
        ts = d.get("created_at") or ""
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if t >= cutoff:
                in_window.append(d)
        except Exception:
            in_window.append(d)
    code_s, sprint = mcp_get_sprint(project_id="EOM")
    sprint = sprint if code_s == 200 else {}
    code_q1, body_q1 = mcp_get_task_queue(status="approved", limit=20)
    approved = body_q1.get("tasks") or [] if code_q1 == 200 else []
    code_q2, body_q2 = mcp_get_task_queue(status="locked", limit=20)
    locked = body_q2.get("tasks") or [] if code_q2 == 200 else []
    code_q3, body_q3 = mcp_get_task_queue(status="completed", include_completed=True, limit=15)
    completions = body_q3.get("tasks") or [] if code_q3 == 200 else []
    return {
        "decisions": in_window,
        "sprint": sprint,
        "approved_tasks": approved,
        "locked_tasks": locked,
        "recent_completions": completions,
    }


def _template_digest(window: dict) -> tuple[str, dict]:
    now = datetime.now(timezone.utc)
    decisions = window["decisions"]
    chunks = [
        f"# Hercules persistent memory — rolling {WINDOW_HOURS}h summary (template fallback)",
        f"**Generated:** {now.isoformat()}",
        f"**Window start:** {(now - timedelta(hours=WINDOW_HOURS)).isoformat()}",
        f"**Mode:** template (DeepSeek compressor unavailable)",
        "",
        f"## Headline counts",
        f"- decisions in last {WINDOW_HOURS}h: {len(decisions)}",
        f"- approved-queue depth: {len(window['approved_tasks'])}",
        f"- locked-in-flight: {len(window['locked_tasks'])}",
        f"- recent completions: {len(window['recent_completions'])}",
        "",
        f"## Sprint",
        f"- name: {window['sprint'].get('sprint','?')}",
        f"- completion: {window['sprint'].get('completion','?')}",
        f"- blockers: {window['sprint'].get('blockers') or 'none'}",
        "",
        f"## Recent decisions (top 10)",
    ]
    for d in decisions[:10]:
        ts = (d.get("created_at") or "")[:19]
        proj = d.get("project_source") or "?"
        text = (d.get("text") or "")[:140].replace("\n", " ")
        tags = ", ".join((d.get("tags") or [])[:4])
        chunks.append(f"- [{ts}] [{proj}] {text}  (tags: {tags})")
    chunks.append("")
    chunks.append("## Recent completions (top 5)")
    for t in window["recent_completions"][:5]:
        chunks.append(f"- {t.get('task_id')} | {t.get('assigned_to') or '?'} | {(t.get('objective') or '')[:90]}")
    return "\n".join(chunks), {"model": "template", "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}


def _llm_digest(window: dict, api_key: str) -> tuple[str, dict]:
    decisions = window["decisions"]
    raw_blob = json.dumps({
        "decisions": [
            {
                "ts": d.get("created_at"),
                "project": d.get("project_source"),
                "text": (d.get("text") or "")[:400],
                "tags": (d.get("tags") or [])[:6],
            } for d in decisions[:50]
        ],
        "sprint": {
            "name": window["sprint"].get("sprint"),
            "completion": window["sprint"].get("completion"),
            "blockers": window["sprint"].get("blockers"),
            "kill_chain": (window["sprint"].get("kill_chain") or [])[-8:],
        },
        "queue_depth": {
            "approved": len(window["approved_tasks"]),
            "locked": len(window["locked_tasks"]),
        },
        "recent_completions": [
            {"task_id": t.get("task_id"), "assigned_to": t.get("assigned_to"),
             "objective": (t.get("objective") or "")[:120]}
            for t in window["recent_completions"][:10]
        ],
    }, separators=(",", ":"))[:24000]
    prompt = (
        f"Compress the last {WINDOW_HOURS} hours of AMG factory state below into a "
        "Hercules-readable rolling-memory digest. Markdown only, ~600-800 words. "
        "Sections: (1) what changed since last summary [bullets], (2) current sprint + "
        "blockers, (3) queue health (approved + locked + recent completions), (4) "
        "open questions or incidents Hercules should know about, (5) one-line "
        "recommended next dispatch. Be terse. No fluff. Plain markdown.\n\nFACTORY STATE JSON:\n"
        + raw_blob
    )
    body = {
        "model": COMPRESSOR_MODEL,
        "messages": [
            {"role": "system",
             "content": "You are Hercules's memory compressor. Your output is read by Hercules at session start to hydrate context. Be terse, accurate, and structural."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 2048,
    }
    req = urllib.request.Request(
        DEEPSEEK_ENDPOINT,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    msg = (resp.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    usage = resp.get("usage") or {}
    cost = (usage.get("prompt_tokens", 0) * 0.07 + usage.get("completion_tokens", 0) * 0.28) / 1_000_000
    return msg, {
        "model": COMPRESSOR_MODEL,
        "tokens_in": usage.get("prompt_tokens", 0),
        "tokens_out": usage.get("completion_tokens", 0),
        "cost_usd": round(cost, 5),
    }


def _push_gist(summary_md: str) -> None:
    if not SUMMARY_GIST_ID:
        return
    SUMMARY_FILE.write_text(summary_md)
    try:
        subprocess.run(
            ["gh", "gist", "edit", SUMMARY_GIST_ID, "-f", "hercules_memory_summary.md", str(SUMMARY_FILE)],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except Exception as e:
        _log(f"gist push exception: {e!r}")


def _persist_history(window_start: str, summary_md: str, meta: dict) -> None:
    _init_db()
    conn = sqlite3.connect(HISTORY_DB)
    conn.execute(
        "INSERT INTO summaries (ts, window_start, window_end, decision_count, summary_md, model, tokens_in, tokens_out, cost_usd) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            datetime.now(timezone.utc).isoformat(),
            window_start,
            datetime.now(timezone.utc).isoformat(),
            meta.get("decision_count", 0),
            summary_md,
            meta.get("model"),
            meta.get("tokens_in", 0),
            meta.get("tokens_out", 0),
            meta.get("cost_usd", 0.0),
        ),
    )
    conn.commit()
    conn.close()


def regenerate(force_template: bool = False) -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        window = _gather_window()
    except Exception as e:
        _log(f"gather window FAIL: {e!r}")
        return {"ok": False, "error": f"gather: {e!r}"}
    window_start = (datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)).isoformat()
    api_key = None if force_template else _resolve_deepseek_key()
    if api_key:
        try:
            summary_md, meta = _llm_digest(window, api_key)
            meta["decision_count"] = len(window["decisions"])
        except Exception as e:
            _log(f"llm digest FAIL: {e!r} → falling back to template")
            summary_md, meta = _template_digest(window)
            meta["decision_count"] = len(window["decisions"])
            meta["fallback_reason"] = repr(e)[:200]
    else:
        summary_md, meta = _template_digest(window)
        meta["decision_count"] = len(window["decisions"])
    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_FILE.write_text(summary_md)
    try:
        _persist_history(window_start, summary_md, meta)
    except Exception as e:
        _log(f"sqlite persist FAIL: {e!r}")
    _push_gist(summary_md)
    _log(f"regen ok decisions={meta.get('decision_count',0)} model={meta.get('model')} cost=${meta.get('cost_usd',0):.4f}")
    return {"ok": True, "summary_path": str(SUMMARY_FILE), **meta}


def hydrate() -> str:
    if SUMMARY_FILE.exists():
        return SUMMARY_FILE.read_text()
    if HISTORY_DB.exists():
        conn = sqlite3.connect(HISTORY_DB)
        row = conn.execute("SELECT summary_md FROM summaries ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        if row:
            return row[0]
    return "(no persistent memory yet — run with --once first)"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=300)
    p.add_argument("--hydrate", action="store_true")
    p.add_argument("--template-only", action="store_true")
    args = p.parse_args()

    if args.hydrate:
        print(hydrate())
        return 0

    if args.once or not args.watch:
        result = regenerate(force_template=args.template_only)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    _log(f"persistent_memory starting watch interval={args.interval}s window={WINDOW_HOURS}h")
    while True:
        try:
            regenerate(force_template=args.template_only)
        except Exception as e:
            _log(f"watch ERROR: {e!r}")
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
