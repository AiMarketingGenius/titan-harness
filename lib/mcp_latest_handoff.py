#!/usr/bin/env python3
"""Fetch the latest Titan RESTART_HANDOFF / safe-restart-eligible decision from MCP.

TLA v1.0 bug #2 fix — supports cold-boot resume priority-order enforcement
per CLAUDE.md §7 / §13.1 / §13.4. The boot audit calls this before emitting
the greeting so `RESUME_SOURCE` can be determined: MCP handoff wins over
`~/titan-session/NEXT_TASK.md` when the MCP record is newer than the file
mtime.

Data path: direct PostgREST query against Supabase `op_decisions` table
(the MCP server's storage backend). Pure stdlib (urllib) — no httpx or
third-party deps so this can run during cold-boot on any machine.

Env requirements:
  SUPABASE_URL                Supabase project REST base URL
  SUPABASE_SERVICE_ROLE_KEY   Service-role key (read-only usage here)

Output: single-line JSON to stdout on success.
  {
    "found": true,
    "ts_unix": <int>,
    "iso_ts": "2026-04-18T15:53:29Z",
    "commit_hash": "d5e538c",
    "project_source": "titan",
    "tags": [...],
    "text_excerpt": "...",
    "resume_source_hint": "mcp-handoff" | "mcp-trigger-ready"
  }
If no matching decision found:
  {"found": false, "reason": "no matching RESTART_HANDOFF within limit"}
If transport / config error:
  {"found": false, "reason": "<error>"} on stderr + exit 2

Exit codes: 0 = found, 1 = not found, 2 = error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone


DEFAULT_TAGS = ["RESTART_HANDOFF", "safe-restart-eligible", "tla-trigger-ready"]


def _parse_iso(ts: str) -> int:
    if not ts:
        return 0
    ts = ts.replace("Z", "+00:00")
    # Normalize fractional seconds: Python <3.11 datetime.fromisoformat is strict
    # about digit count (needs exactly 3 or 6). PostgREST returns variable-length
    # microseconds like ".96514". Trim to microsecond precision.
    m = re.match(r"^(.*?\.\d{0,6})\d*(.*)$", ts)
    if m and m.group(1).count(".") == 1:
        ts = m.group(1) + m.group(2)
    for parse in (datetime.fromisoformat,):
        try:
            return int(parse(ts).astimezone(timezone.utc).timestamp())
        except Exception:
            pass
    # Last-resort: strip fractional entirely
    bare = re.sub(r"\.\d+", "", ts)
    try:
        return int(datetime.fromisoformat(bare).astimezone(timezone.utc).timestamp())
    except Exception:
        return 0


def _extract_commit_hash(tags, text):
    for t in tags or []:
        m = re.match(r"^commit-([0-9a-f]{7,40})$", t)
        if m:
            return m.group(1)[:7]
    m = re.search(r"\bcommit[-: ]?([0-9a-f]{7,40})\b", text or "", re.IGNORECASE)
    if m:
        return m.group(1)[:7]
    return None


def _infer_source_hint(tags):
    tags_lower = {t.lower() for t in tags or []}
    if "restart_handoff" in tags_lower or any("restart_handoff" in t.lower() for t in tags or []):
        return "mcp-handoff"
    if any("safe-restart-eligible" in t.lower() for t in tags or []):
        return "mcp-handoff"
    if any("tla-trigger-ready" in t.lower() for t in tags or []):
        return "mcp-trigger-ready"
    return "mcp-handoff"


def query_decisions(tag_filters, limit=20):
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")

    or_parts = [f"tags.cs.{{{t}}}" for t in tag_filters]
    or_filter = f"or=({','.join(or_parts)})"
    params = f"select=id,decision_text,tags,created_at,project_source&order=created_at.desc&limit={limit}&{or_filter}"
    url = f"{base}/rest/v1/op_decisions?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="+", default=DEFAULT_TAGS)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--require-tag", action="append", default=[],
                    help="Only accept a decision whose tag list contains ALL of these (repeatable).")
    args = ap.parse_args()

    try:
        rows = query_decisions(args.tags, args.limit)
    except Exception as exc:
        print(json.dumps({"found": False, "reason": f"transport: {exc}"}), file=sys.stderr)
        sys.exit(2)

    if not rows:
        print(json.dumps({"found": False, "reason": "no matching decisions"}))
        sys.exit(1)

    for row in rows:
        tags = row.get("tags") or []
        tagset = set(tags)
        if args.require_tag and not set(args.require_tag).issubset(tagset):
            continue
        text = row.get("decision_text") or ""
        ts_iso = row.get("created_at") or ""
        ts_unix = _parse_iso(ts_iso)
        out = {
            "found": True,
            "ts_unix": ts_unix,
            "iso_ts": ts_iso,
            "commit_hash": _extract_commit_hash(tags, text),
            "project_source": row.get("project_source"),
            "tags": tags,
            "text_excerpt": text[:400],
            "resume_source_hint": _infer_source_hint(tags),
        }
        print(json.dumps(out))
        sys.exit(0)

    print(json.dumps({"found": False, "reason": "no row matched require-tag filters"}))
    sys.exit(1)


if __name__ == "__main__":
    main()
