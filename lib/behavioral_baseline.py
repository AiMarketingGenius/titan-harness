#!/usr/bin/env python3
"""DR-AMG-GOVERNANCE-01 Phase 3 Task 3.1 — Behavioral Baseline Capture

Captures per-session distributions of action types, timing, reviewer grades,
and tool selection ratios. Stores in governance_baseline table.
14-day rolling window, refreshed weekly.
"""

import json
import os
import sys
import hashlib
from datetime import datetime, timedelta, timezone

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)


DB_URL = os.environ.get("SUPABASE_DB_URL", "")

DIMENSIONS = [
    "bash_actions", "git_actions", "mcp_read_actions", "mcp_write_actions",
    "api_call_actions", "time_to_first_action_s", "avg_diff_size_lines",
    "reviewer_grade_a_pct", "reviewer_grade_b_pct", "reviewer_grade_fail_pct",
    "override_count", "cli_actions", "stagehand_actions"
]


def get_db():
    if not DB_URL:
        raise RuntimeError("SUPABASE_DB_URL not set")
    return psycopg2.connect(DB_URL)


def capture_session_baseline(session_id: str, window_hours: int = 1):
    """Capture behavioral metrics from governance_audit for a given session window."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=window_hours)

    # Query governance_audit for action counts in window
    # Schema: action_type, timestamp_utc, action_payload, this_event_hash, prev_event_hash
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE action_type LIKE 'bash%%') AS bash_actions,
            COUNT(*) FILTER (WHERE action_type LIKE 'git%%') AS git_actions,
            COUNT(*) FILTER (WHERE action_type LIKE 'mcp_read%%') AS mcp_read_actions,
            COUNT(*) FILTER (WHERE action_type LIKE 'mcp_write%%') AS mcp_write_actions,
            COUNT(*) FILTER (WHERE action_type LIKE 'api%%') AS api_call_actions,
            COUNT(*) FILTER (WHERE action_type LIKE 'cli%%') AS cli_actions,
            COUNT(*) FILTER (WHERE action_type LIKE 'stagehand%%' OR action_type LIKE 'browser%%') AS stagehand_actions,
            COUNT(*) FILTER (WHERE operator_override = true) AS override_count
        FROM public.governance_audit
        WHERE timestamp_utc >= %s AND timestamp_utc <= %s
    """, (window_start, now))
    counts = cur.fetchone()

    # Get reviewer grade distribution
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE action_payload->>'grade' IN ('A', 'A+', 'A-')) AS grade_a,
            COUNT(*) FILTER (WHERE action_payload->>'grade' IN ('B', 'B+', 'B-')) AS grade_b,
            COUNT(*) FILTER (WHERE action_payload->>'grade' IN ('F', 'D', 'D+', 'D-')) AS grade_fail,
            COUNT(*) AS total_reviews
        FROM public.governance_audit
        WHERE action_type = 'reviewer_grade'
          AND timestamp_utc >= %s AND timestamp_utc <= %s
    """, (window_start, now))
    grades = cur.fetchone()

    total_reviews = grades["total_reviews"] or 1
    grade_a_pct = round((grades["grade_a"] or 0) / total_reviews * 100, 2)
    grade_b_pct = round((grades["grade_b"] or 0) / total_reviews * 100, 2)
    grade_fail_pct = round((grades["grade_fail"] or 0) / total_reviews * 100, 2)

    # Get time-to-first-action (avg seconds from session start to first event)
    cur.execute("""
        SELECT AVG(EXTRACT(EPOCH FROM (first_action - session_start))) AS avg_ttfa
        FROM (
            SELECT
                MIN(timestamp_utc) AS first_action,
                MIN(timestamp_utc) - INTERVAL '1 second' AS session_start
            FROM public.governance_audit
            WHERE timestamp_utc >= %s AND timestamp_utc <= %s
            GROUP BY session_id
        ) sub
    """, (window_start, now))
    ttfa_row = cur.fetchone()
    time_to_first_action = round(ttfa_row["avg_ttfa"] or 0, 2)

    # Get average diff size
    cur.execute("""
        SELECT AVG((action_payload->>'diff_lines')::numeric) AS avg_diff
        FROM public.governance_audit
        WHERE action_type = 'git_commit'
          AND timestamp_utc >= %s AND timestamp_utc <= %s
          AND action_payload->>'diff_lines' IS NOT NULL
    """, (window_start, now))
    diff_row = cur.fetchone()
    avg_diff = round(diff_row["avg_diff"] or 0, 2)

    # Insert baseline record
    cur.execute("""
        INSERT INTO public.governance_baseline (
            session_id, window_start, window_end,
            bash_actions, git_actions, mcp_read_actions, mcp_write_actions,
            api_call_actions, time_to_first_action_s, avg_diff_size_lines,
            reviewer_grade_a_pct, reviewer_grade_b_pct, reviewer_grade_fail_pct,
            override_count, cli_actions, stagehand_actions, is_rolling_baseline
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, false)
        RETURNING id
    """, (
        session_id, window_start, now,
        counts["bash_actions"] or 0, counts["git_actions"] or 0,
        counts["mcp_read_actions"] or 0, counts["mcp_write_actions"] or 0,
        counts["api_call_actions"] or 0, time_to_first_action,
        avg_diff, grade_a_pct, grade_b_pct, grade_fail_pct,
        counts["override_count"] or 0, counts["cli_actions"] or 0,
        counts["stagehand_actions"] or 0
    ))
    row_id = cur.fetchone()["id"]
    conn.commit()

    # Refresh rolling baseline (mark last 14 days as rolling)
    refresh_rolling_baseline(cur, conn)

    cur.close()
    conn.close()
    return row_id


def refresh_rolling_baseline(cur, conn):
    """Mark records within 14-day window as rolling baseline."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)

    cur.execute("""
        UPDATE public.governance_baseline
        SET is_rolling_baseline = (window_start >= %s)
    """, (cutoff,))
    conn.commit()


def get_rolling_baseline_stats():
    """Get mean and stddev for each dimension from the rolling baseline."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    stats = {}
    for dim in DIMENSIONS:
        cur.execute(f"""
            SELECT
                AVG({dim}) AS mean,
                STDDEV_POP({dim}) AS stddev,
                COUNT(*) AS n
            FROM public.governance_baseline
            WHERE is_rolling_baseline = true
        """)
        row = cur.fetchone()
        stats[dim] = {
            "mean": float(row["mean"] or 0),
            "stddev": float(row["stddev"] or 0),
            "n": int(row["n"] or 0)
        }

    cur.close()
    conn.close()
    return stats


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Behavioral baseline capture")
    parser.add_argument("--capture", action="store_true", help="Capture current session baseline")
    parser.add_argument("--session-id", default="manual", help="Session identifier")
    parser.add_argument("--window-hours", type=int, default=1, help="Window size in hours")
    parser.add_argument("--stats", action="store_true", help="Print rolling baseline stats")
    parser.add_argument("--refresh", action="store_true", help="Refresh rolling window markers")
    args = parser.parse_args()

    if args.capture:
        row_id = capture_session_baseline(args.session_id, args.window_hours)
        print(f"Baseline captured: row {row_id}")
    elif args.stats:
        stats = get_rolling_baseline_stats()
        print(json.dumps(stats, indent=2))
    elif args.refresh:
        conn = get_db()
        cur = conn.cursor()
        refresh_rolling_baseline(cur, conn)
        cur.close()
        conn.close()
        print("Rolling baseline refreshed")
    else:
        parser.print_help()
