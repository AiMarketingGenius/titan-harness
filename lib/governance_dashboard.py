#!/usr/bin/env python3
"""DR-AMG-GOVERNANCE-01 Phase 3 Task 3.3 — Governance Dashboard API

Serves read-only JSON endpoints for the governance dashboard.
Deployed as a Cloudflare Worker or as a local Flask server for dev.
Dashboard panels:
1. Live audit stream (last 100 events)
2. Hash chain integrity status
3. Open hard-stops
4. Reviewer loop grade history + anomaly flags
5. Mirror sync status per repo
6. Alert budget consumption (current day, current week)
7. Drift scores per behavioral dimension
8. Auditor heartbeat status
9. Governance Health Score (weekly composite)
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    sys.exit("psycopg2 required")

DB_URL = os.environ.get("SUPABASE_DB_URL", "")


def get_db():
    if not DB_URL:
        raise RuntimeError("SUPABASE_DB_URL not set")
    return psycopg2.connect(DB_URL)


def panel_audit_stream(limit=100):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT event_id AS id, action_type, timestamp_utc, action_payload
        FROM public.governance_audit
        ORDER BY id DESC LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r["id"], "type": r["action_type"],
             "at": r["timestamp_utc"].isoformat(), "payload": r["action_payload"]} for r in rows]


def panel_hash_chain():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE prev_event_hash IS NOT NULL AND prev_event_hash != '') AS chained,
               (SELECT event_id FROM public.governance_audit ORDER BY timestamp_utc DESC LIMIT 1) AS latest_id,
               (SELECT this_event_hash FROM public.governance_audit ORDER BY timestamp_utc DESC LIMIT 1) AS latest_hash
        FROM public.governance_audit
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return {
        "total_events": row["total"],
        "chained_events": row["chained"],
        "latest_id": row["latest_id"],
        "latest_hash": row["latest_hash"],
        "status": "healthy" if row["chained"] == row["total"] - 1 or row["total"] <= 1 else "gaps_detected"
    }


def panel_open_hard_stops():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT event_id AS id, timestamp_utc, action_payload->>'trigger_type' AS trigger_type,
               action_payload->>'description' AS description
        FROM public.governance_audit
        WHERE action_type = 'hard_stop'
          AND (action_payload->>'resolved')::boolean IS NOT TRUE
        ORDER BY timestamp_utc DESC LIMIT 20
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r["id"], "at": r["timestamp_utc"].isoformat(),
             "trigger": r["trigger_type"], "desc": r["description"]} for r in rows]


def panel_reviewer_grades():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT DATE(timestamp_utc) AS day,
               action_payload->>'grade' AS grade,
               COUNT(*) AS cnt
        FROM public.governance_audit
        WHERE action_type = 'reviewer_grade'
          AND timestamp_utc >= NOW() - INTERVAL '30 days'
        GROUP BY DATE(timestamp_utc), action_payload->>'grade'
        ORDER BY day DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"day": str(r["day"]), "grade": r["grade"], "count": r["cnt"]} for r in rows]


def panel_mirror_status():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT action_payload->>'repo' AS repo,
               MAX(timestamp_utc) AS last_sync,
               action_payload->>'status' AS status
        FROM public.governance_audit
        WHERE action_type = 'mirror_sync'
        GROUP BY action_payload->>'repo', action_payload->>'status'
        ORDER BY MAX(timestamp_utc) DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"repo": r["repo"], "last_sync": r["last_sync"].isoformat(),
             "status": r["status"]} for r in rows]


def panel_alert_budget():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE timestamp_utc >= %s) AS today,
            COUNT(*) FILTER (WHERE timestamp_utc >= %s) AS this_week
        FROM public.governance_audit
        WHERE action_type LIKE 'alert%%'
    """, (today_start, week_start))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return {
        "today": row["today"] or 0, "budget_today": 3,
        "this_week": row["this_week"] or 0, "budget_week": 21
    }


def panel_drift_scores():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT DISTINCT ON (dimension)
            dimension, z_score, ks_statistic, drift_level, scored_at
        FROM public.governance_drift_scores
        ORDER BY dimension, scored_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"dim": r["dimension"], "z": float(r["z_score"]),
             "ks": float(r["ks_statistic"]), "level": r["drift_level"],
             "at": r["scored_at"].isoformat()} for r in rows]


def panel_auditor_heartbeat():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT MAX(timestamp_utc) AS last_heartbeat
        FROM public.governance_audit
        WHERE action_type = 'auditor_heartbeat'
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()

    last_hb = row["last_heartbeat"]
    if last_hb:
        age_s = (datetime.now(timezone.utc) - last_hb).total_seconds()
        status = "healthy" if age_s < 120 else "stale" if age_s < 600 else "dead"
    else:
        age_s = None
        status = "no_data"

    return {"last_heartbeat": last_hb.isoformat() if last_hb else None,
            "age_seconds": age_s, "status": status}


def panel_ghs():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM public.governance_health_scores
        ORDER BY scored_at DESC LIMIT 4
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{
        "week": f"{r['week_start']} → {r['week_end']}",
        "ghs": float(r["ghs_composite"]),
        "review_triggered": r["review_triggered"],
        "scored_at": r["scored_at"].isoformat()
    } for r in rows]


def get_full_dashboard():
    """Assemble all panels into a single dashboard payload."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "panels": {
            "audit_stream": panel_audit_stream(),
            "hash_chain": panel_hash_chain(),
            "open_hard_stops": panel_open_hard_stops(),
            "reviewer_grades": panel_reviewer_grades(),
            "mirror_status": panel_mirror_status(),
            "alert_budget": panel_alert_budget(),
            "drift_scores": panel_drift_scores(),
            "auditor_heartbeat": panel_auditor_heartbeat(),
            "ghs": panel_ghs()
        }
    }


if __name__ == "__main__":
    dashboard = get_full_dashboard()
    print(json.dumps(dashboard, indent=2, default=str))
