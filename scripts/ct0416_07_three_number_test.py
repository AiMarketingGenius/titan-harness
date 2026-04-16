#!/usr/bin/env python3
"""
titan-harness/scripts/ct0416_07_three_number_test.py

CT-0416-07 Gate 4 — the only test that catches false completion on AI Memory
Guard persistence.

The lie CT-0416-07 was queued to kill: popup says "Connected" while
`consumer_memories` in Supabase is empty. The only way to prove memories are
actually persisting is to align three numbers at the same moment in time:

    popup_counter_value   ==  SELECT COUNT(*) FROM consumer_memories WHERE user_id=<solon>
                          ==  freshness(MAX(created_at))  (must be < 5 min old)

All three must match. If any one is off, the product is still lying.

Usage (Solon triggers from Mac terminal or Slack → Titan runs):
    SUPABASE_URL_AIMG=https://gaybcxzrzfgvcqpkbeiq.supabase.co \\
    SUPABASE_SERVICE_ROLE_KEY_AIMG=eyJhbGc... \\
    SLACK_BOT_TOKEN=xoxb-... \\
    ARISTOTLE_CHANNEL_ID=C0XXXXXXXXX \\
    python3 scripts/ct0416_07_three_number_test.py \\
        --user-id <uuid-from-extension-login> \\
        --popup-counter 5

What it does:
  1. GET /rest/v1/consumer_memories?user_id=eq.<uid>&select=id,created_at
     via service-role key (service role bypasses RLS, which is what we want
     for an audit script — never ship this key to the client).
  2. Compute row_count + max_created_at + age_seconds.
  3. Render a 3-number alignment table.
  4. Post a structured Slack message (aristotle_slack.post_update) so Solon
     sees the three numbers in one glance, not scattered across tabs.
  5. Exit 0 if all three align, exit 1 otherwise. Caller (cron / pre-commit /
     Slack slash command) can branch on the exit code.

Design constraints:
  - stdlib-only (no requests, no supabase-py). Consistent with harness
    conventions.
  - Never logs the service role key. Redacts on trace.
  - Freshness window configurable via --max-age-seconds, default 300 (5 min).
  - Tolerates COUNT-only queries: if Supabase Prefer: count=exact header is
    honored, uses Content-Range; otherwise falls back to counting returned rows.
  - Slack post is best-effort — if aristotle_slack can't post (policy.yaml
    aristotle_enabled=false or token missing), still emits the table to stdout
    and stderr tells Solon why.
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Let the script import harness libs regardless of cwd
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib"))

try:
    import aristotle_slack  # type: ignore
except ImportError:
    aristotle_slack = None  # noqa — graceful degrade


# ---------------------------------------------------------------------------
# Supabase query
# ---------------------------------------------------------------------------

def _supabase_query(url: str, service_key: str, user_id: str,
                    timeout_s: int = 10) -> dict:
    """Hit /rest/v1/consumer_memories for rows matching user_id.

    Returns {'row_count': int, 'max_created_at': Optional[str],
             'sample_ids': [str, ...], 'http_status': int}.
    Raises RuntimeError on any non-2xx — caller turns into exit 2.
    """
    q = urllib.parse.urlencode({
        "user_id": f"eq.{user_id}",
        "select": "id,created_at",
        "order": "created_at.desc",
        "limit": "50",
    })
    endpoint = f"{url.rstrip('/')}/rest/v1/consumer_memories?{q}"

    req = urllib.request.Request(endpoint, method="GET")
    req.add_header("apikey", service_key)
    req.add_header("Authorization", f"Bearer {service_key}")
    req.add_header("Prefer", "count=exact")

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
            body = resp.read().decode("utf-8")
            content_range = resp.headers.get("Content-Range", "")
            status = resp.getcode()
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"Supabase HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:400]}"
        ) from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"Supabase connection failed: {e}") from e

    rows = json.loads(body) if body.strip() else []

    # Content-Range: '0-4/5' → total 5
    total = None
    if "/" in content_range:
        try:
            total = int(content_range.rsplit("/", 1)[1])
        except ValueError:
            total = None
    row_count = total if total is not None else len(rows)

    max_created_at = rows[0].get("created_at") if rows else None
    sample_ids = [r["id"] for r in rows[:5]]

    return {
        "row_count": row_count,
        "max_created_at": max_created_at,
        "sample_ids": sample_ids,
        "http_status": status,
    }


# ---------------------------------------------------------------------------
# Alignment math
# ---------------------------------------------------------------------------

def _age_seconds(iso_ts: Optional[str]) -> Optional[int]:
    if not iso_ts:
        return None
    # Supabase returns ISO 8601 with microseconds + timezone offset
    # Normalize to timezone-aware datetime.
    normalized = iso_ts.replace("Z", "+00:00")
    try:
        ts = datetime.fromisoformat(normalized)
    except ValueError:
        # Strip fractional seconds past 6 digits if Postgres returned them
        head, _, tail = normalized.partition(".")
        if tail:
            frac, _, tz = tail.partition("+")
            frac = frac[:6]
            normalized = f"{head}.{frac}+{tz}" if tz else f"{head}.{frac}"
        ts = datetime.fromisoformat(normalized)
    now = datetime.now(timezone.utc)
    return int((now - ts).total_seconds())


def _align(popup_counter: int, row_count: int,
           max_age_seconds: Optional[int], freshness_limit: int) -> dict:
    """Score the three-number alignment.

    Returns {'aligned': bool, 'reasons': [str, ...]}.
    """
    reasons = []
    aligned = True

    if popup_counter != row_count:
        aligned = False
        reasons.append(
            f"popup={popup_counter} ≠ supabase_rows={row_count}"
        )

    if max_age_seconds is None:
        aligned = False
        reasons.append("no max(created_at) — table empty or query failed")
    elif max_age_seconds > freshness_limit:
        aligned = False
        reasons.append(
            f"max(created_at) is {max_age_seconds}s old, freshness limit is {freshness_limit}s"
        )

    if row_count == 0:
        aligned = False
        reasons.append("zero rows in consumer_memories — persistence not firing")

    return {"aligned": aligned, "reasons": reasons}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_table(popup_counter: int, q: dict, alignment: dict,
                  user_id: str, project_ref: str) -> str:
    fresh_s = _age_seconds(q["max_created_at"])
    fresh_label = f"{fresh_s}s ago" if fresh_s is not None else "n/a"
    status = "✅ ALIGNED" if alignment["aligned"] else "🔴 MISMATCH"

    lines = [
        f"*CT-0416-07 Gate 4 — 3-Number Alignment Test*  →  {status}",
        "",
        f"• *Popup counter:*  `{popup_counter}`",
        f"• *Supabase row count:*  `{q['row_count']}`  (consumer_memories, project `{project_ref}`)",
        f"• *MAX(created_at):*  `{q['max_created_at'] or 'null'}`  ({fresh_label})",
        "",
        f"user_id: `{user_id}`",
    ]
    if q["sample_ids"]:
        lines.append(f"sample row ids: `{', '.join(q['sample_ids'])}`")
    if not alignment["aligned"]:
        lines.append("")
        lines.append("*Why this is a FAIL:*")
        for r in alignment["reasons"]:
            lines.append(f"  • {r}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        description="CT-0416-07 Gate 4 — three-number alignment audit for AI Memory Guard",
    )
    p.add_argument("--user-id", required=True,
                   help="Solon's auth.users.id UUID (from extension login — check popup or chrome.storage)")
    p.add_argument("--popup-counter", type=int, required=True,
                   help="Value currently shown in the extension popup — Solon reads it off screen")
    p.add_argument("--max-age-seconds", type=int, default=300,
                   help="Freshness window for MAX(created_at) — default 300s (5 min)")
    p.add_argument("--no-slack", action="store_true",
                   help="Skip Slack post, stdout only")
    args = p.parse_args()

    url = os.environ.get("SUPABASE_URL_AIMG", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY_AIMG", "").strip()

    if not url:
        sys.stderr.write("ERROR: SUPABASE_URL_AIMG env var required "
                         "(e.g. https://gaybcxzrzfgvcqpkbeiq.supabase.co)\n")
        return 2
    if not key:
        sys.stderr.write("ERROR: SUPABASE_SERVICE_ROLE_KEY_AIMG env var required — "
                         "pull from consumer project service_role key (NEVER commit this)\n")
        return 2

    project_ref = url.replace("https://", "").split(".")[0] or "unknown"

    try:
        q = _supabase_query(url, key, args.user_id)
    except RuntimeError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2

    alignment = _align(
        popup_counter=args.popup_counter,
        row_count=q["row_count"],
        max_age_seconds=_age_seconds(q["max_created_at"]),
        freshness_limit=args.max_age_seconds,
    )

    table = _render_table(args.popup_counter, q, alignment, args.user_id, project_ref)
    print(table)

    # Slack post — best-effort
    if not args.no_slack:
        if aristotle_slack is None:
            sys.stderr.write(
                "WARN: aristotle_slack not importable — skipped Slack post\n"
            )
        else:
            ready, reason = aristotle_slack.is_ready()
            if not ready:
                sys.stderr.write(f"WARN: Slack skipped — {reason}\n")
            else:
                ts = aristotle_slack.post_update(
                    title="CT-0416-07 Gate 4 — 3-Number Alignment",
                    body_md=table,
                )
                if ts:
                    print(f"\n[slack] posted ts={ts}", file=sys.stderr)

    return 0 if alignment["aligned"] else 1


if __name__ == "__main__":
    sys.exit(main())
