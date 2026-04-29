#!/usr/bin/env python3
"""queue_requery.py — atomic MCP get_task_queue refresh + NEXT_TASK.md rewrite.

DIR-009 Phase 1 / CT-0428-40. Universal queue-requery hook helper. Used by
hooks/session-start.sh and hooks/post-ship.sh on titan-harness; mirrored to
achilles-harness with --agent achilles.

Reads:
- SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (env, via lib/titan-env.sh)
- operator_task_queue table

Writes:
- $TITAN_SESSION_DIR/NEXT_TASK.md (default: $HOME/<agent>-session/NEXT_TASK.md)

Sort: priority urgent > high > normal > low; within priority, oldest queued
first. Filters: assigned_to=<agent>, status in (queued, locked) AND
approval=pre_approved (so the file shows what is claim-ready right now).

Stdlib only. No third-party deps.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PRIORITY_RANK = {"urgent": 0, "high": 1, "normal": 2, "low": 3}


def _env(key: str, default: str = "") -> str:
    val = os.environ.get(key, default)
    return val.strip() if val else default


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_queue(agent: str, supabase_url: str, supabase_key: str, timeout: int = 8):
    """Pull claim-ready tasks for the agent from op_task_queue.

    Note: MCP exposes this as `operator_task_queue` logically; the underlying
    Supabase table is `op_task_queue`.
    """
    params = {
        "select": (
            "task_id,objective,priority,status,approval,project_id,"
            "tags,locked_by,created_at,assigned_to,context"
        ),
        "assigned_to": f"eq.{agent}",
        "status": "in.(queued,locked)",
        "order": "created_at.desc",
        "limit": "40",
    }
    url = f"{supabase_url.rstrip('/')}/rest/v1/op_task_queue?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        return None, f"fetch_failed: {exc}"
    if not isinstance(data, list):
        return None, f"unexpected_payload_shape: {type(data).__name__}"
    return data, None


def rank_tasks(rows):
    """Sort by priority (urgent → low) then newest-first within priority.

    Reverse-iso8601 means lexicographic descending == chronological descending,
    so we negate by sorting ascending on (-priority_rank-flip, created_at) is
    awkward; instead sort with priority asc + created_at desc directly.
    """
    def keyer(row):
        priority_rank = PRIORITY_RANK.get((row.get("priority") or "normal").lower(), 9)
        # Negate ISO timestamp by sorting on the negated unicode-codepoint trick:
        # simpler — use a tuple of (priority_rank, NEGATIVE-sortable-created_at).
        # `created_at` reversed comparison: pad to fixed length then character-flip.
        ts = row.get("created_at") or ""
        return (priority_rank, _ts_neg_key(ts))
    return sorted(rows, key=keyer)


def _ts_neg_key(ts: str) -> str:
    """Return a string that sorts in reverse-chronological order."""
    # Replace each digit/char so newer timestamps sort earlier.
    # ISO timestamps are zero-padded fixed-width; we can flip char-by-char.
    return "".join(chr(255 - ord(c)) if c.isdigit() else c for c in ts)


def build_markdown(agent: str, rows, fetch_error: str | None) -> str:
    head = (
        f"# NEXT_TASK — {agent}\n\n"
        f"**Refreshed:** {_now()} (queue_requery.py)\n"
        f"**Source:** MCP operator_task_queue\n\n"
    )
    if fetch_error:
        head += f"> **WARN:** queue fetch failed — {fetch_error}\n"
        head += "> Treat this file as STALE; re-run on next session start or claim cycle.\n\n"
        return head
    claim_ready = [
        r for r in rows
        if (r.get("approval") or "").lower() == "pre_approved"
        and (r.get("status") or "").lower() in {"queued", "locked"}
    ]
    if not claim_ready:
        head += "_No claim-ready (`status in queued|locked` AND `approval=pre_approved`) tasks._\n\n"
    else:
        top = claim_ready[0]
        head += "## TOP — claim this next\n\n"
        head += _format_row(top, primary=True)
        head += "\n## Full claim-ready queue\n\n"
        for row in claim_ready:
            head += _format_row(row, primary=False)
    head += "\n## All assigned (any status)\n\n"
    if not rows:
        head += "_No tasks assigned to this agent._\n"
    else:
        for row in rows:
            head += (
                f"- `{row.get('task_id', '?')}` "
                f"[{(row.get('priority') or 'normal')}] "
                f"status={row.get('status', '?')}/{row.get('approval', '?')} — "
                f"{(row.get('objective') or '')[:120]}\n"
            )
    return head


def _format_row(row, primary: bool) -> str:
    task_id = row.get("task_id", "?")
    priority = row.get("priority", "normal")
    objective = (row.get("objective") or "(no objective)").strip()
    status = row.get("status", "?")
    approval = row.get("approval", "?")
    locked_by = row.get("locked_by") or "(unlocked)"
    tags = row.get("tags") or []
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = [tags]
    bullet = "###" if primary else "-"
    if primary:
        return (
            f"### `{task_id}` — priority={priority}\n\n"
            f"- status: `{status}` / approval: `{approval}` / locked_by: `{locked_by}`\n"
            f"- tags: {', '.join(tags) if tags else '(none)'}\n\n"
            f"**Objective:** {objective}\n\n"
        )
    return (
        f"- `{task_id}` [{priority}] {status}/{approval} — {objective[:140]}\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default=os.environ.get("AGENT_NAME", "titan"))
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    supabase_url = _env("SUPABASE_URL")
    supabase_key = _env("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        body = (
            f"# NEXT_TASK — {args.agent}\n\n"
            f"**Refreshed:** {_now()}\n\n"
            "> **ERROR:** SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set in env.\n"
            "> Cannot refresh queue. File stale; will retry next hook fire.\n"
        )
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(body)
        return 1

    rows, err = fetch_queue(args.agent, supabase_url, supabase_key)
    rows = rank_tasks(rows or [])
    body = build_markdown(args.agent, rows, err)
    tmp = args.output + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(body)
    os.replace(tmp, args.output)
    return 0 if not err else 2


if __name__ == "__main__":
    sys.exit(main())
