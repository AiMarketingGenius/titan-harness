#!/usr/bin/env python3
"""DR-AMG-GOVERNANCE-01 Phase 3 Task 3.4 — Governance Health Score

Weekly composite 0-100:
GHS = (0.20 * (1 - violation_rate))
    + (0.15 * hash_chain_integrity_pct)
    + (0.15 * auditor_uptime_pct)
    + (0.15 * (1 - rubber_stamp_rate))
    + (0.10 * (1 - mirror_drift_hours))
    + (0.10 * (1 - stale_state_rate))
    + (0.10 * (1 - hard_stop_recurrence_rate))
    + (0.05 * alert_budget_compliance)
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone, date

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    sys.exit("psycopg2 required")

DB_URL = os.environ.get("SUPABASE_DB_URL", "")
GHS_THRESHOLD = 85  # Below this triggers operator review


def get_db():
    if not DB_URL:
        raise RuntimeError("SUPABASE_DB_URL not set")
    return psycopg2.connect(DB_URL)


def compute_ghs(week_start: date = None):
    """Compute Governance Health Score for the given week."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    now = datetime.now(timezone.utc)
    if week_start is None:
        # Current week (Monday to Sunday)
        today = now.date()
        week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)

    ws = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc)
    we = datetime.combine(week_end, datetime.min.time()).replace(tzinfo=timezone.utc)

    # 1. Violation rate (governance_audit violations / total events)
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE action_type LIKE 'violation%%' OR action_type = 'hard_stop') AS violations
        FROM public.governance_audit
        WHERE timestamp_utc >= %s AND timestamp_utc < %s
    """, (ws, we))
    vr = cur.fetchone()
    total_events = max(vr["total"] or 1, 1)
    violation_rate = (vr["violations"] or 0) / total_events
    violation_score = round(1 - violation_rate, 4)

    # 2. Hash chain integrity
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE action_payload->>'hash_valid' = 'true') AS valid
        FROM public.governance_audit
        WHERE action_type = 'hash_chain_check'
          AND timestamp_utc >= %s AND timestamp_utc < %s
    """, (ws, we))
    hc = cur.fetchone()
    hash_total = max(hc["total"] or 1, 1)
    hash_chain_score = round((hc["valid"] or hash_total) / hash_total, 4)

    # 3. Auditor uptime (heartbeats received / expected)
    cur.execute("""
        SELECT COUNT(*) AS heartbeats
        FROM public.governance_audit
        WHERE action_type = 'auditor_heartbeat'
          AND timestamp_utc >= %s AND timestamp_utc < %s
    """, (ws, we))
    hb = cur.fetchone()
    # Expect 1 heartbeat per minute = ~10080 per week
    expected_heartbeats = 10080
    auditor_uptime = round(min((hb["heartbeats"] or 0) / expected_heartbeats, 1.0), 4)

    # 4. Rubber stamp rate (reviews with minimal content / total reviews)
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE
                LENGTH(COALESCE(action_payload->>'rationale', '')) < 20
            ) AS rubber_stamps
        FROM public.governance_audit
        WHERE action_type = 'reviewer_grade'
          AND timestamp_utc >= %s AND timestamp_utc < %s
    """, (ws, we))
    rs = cur.fetchone()
    rs_total = max(rs["total"] or 1, 1)
    rubber_stamp_rate = (rs["rubber_stamps"] or 0) / rs_total
    rubber_stamp_score = round(1 - rubber_stamp_rate, 4)

    # 5. Mirror drift (count of drift events, normalized)
    cur.execute("""
        SELECT COUNT(*) AS drift_events
        FROM public.governance_audit
        WHERE action_type = 'mirror_drift'
          AND timestamp_utc >= %s AND timestamp_utc < %s
    """, (ws, we))
    md = cur.fetchone()
    drift_events = md["drift_events"] or 0
    # Normalize: 0 drifts = 0, 10+ = 1.0
    drift_hours = min(drift_events / 10.0, 1.0) * 168  # Scale to hours equivalent
    mirror_drift_normalized = min(drift_hours / 168, 1.0)  # 168 hours in a week
    mirror_drift_score = round(1 - mirror_drift_normalized, 4)

    # 6. Stale state rate
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE action_type = 'stale_state_error') AS stale
        FROM public.governance_audit
        WHERE action_type IN ('state_access', 'stale_state_error')
          AND timestamp_utc >= %s AND timestamp_utc < %s
    """, (ws, we))
    ss = cur.fetchone()
    ss_total = max(ss["total"] or 1, 1)
    stale_state_rate = (ss["stale"] or 0) / ss_total
    stale_state_score = round(1 - stale_state_rate, 4)

    # 7. Hard stop recurrence
    cur.execute("""
        SELECT
            COUNT(DISTINCT action_payload->>'trigger_type') AS unique_triggers,
            COUNT(*) AS total_stops
        FROM public.governance_audit
        WHERE action_type = 'hard_stop'
          AND timestamp_utc >= %s AND timestamp_utc < %s
    """, (ws, we))
    hs = cur.fetchone()
    total_stops = hs["total_stops"] or 0
    unique_triggers = hs["unique_triggers"] or 0
    recurrence = max(total_stops - unique_triggers, 0) / max(total_stops, 1)
    hard_stop_score = round(1 - recurrence, 4)

    # 8. Alert budget compliance
    cur.execute("""
        SELECT COUNT(*) AS alerts_today
        FROM public.governance_audit
        WHERE action_type LIKE 'alert%%'
          AND timestamp_utc >= %s AND timestamp_utc < %s
    """, (ws, we))
    ab = cur.fetchone()
    weekly_alerts = ab["alerts_today"] or 0
    # Budget: max 3 actionable per day = 21 per week
    alert_compliance = round(min(1.0, 1 - max(weekly_alerts - 21, 0) / 21), 4)

    # Composite GHS
    ghs = round((
        0.20 * violation_score +
        0.15 * hash_chain_score +
        0.15 * auditor_uptime +
        0.15 * rubber_stamp_score +
        0.10 * mirror_drift_score +
        0.10 * stale_state_score +
        0.10 * hard_stop_score +
        0.05 * alert_compliance
    ) * 100, 2)

    review_triggered = ghs < GHS_THRESHOLD

    # Store
    cur.execute("""
        INSERT INTO public.governance_health_scores (
            week_start, week_end,
            violation_rate_score, hash_chain_score, auditor_uptime_score,
            rubber_stamp_score, mirror_drift_score, stale_state_score,
            hard_stop_recurrence_score, alert_budget_score,
            ghs_composite, review_triggered
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        week_start, week_end,
        violation_score, hash_chain_score, auditor_uptime,
        rubber_stamp_score, mirror_drift_score, stale_state_score,
        hard_stop_score, alert_compliance,
        ghs, review_triggered
    ))
    row_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()

    return {
        "id": row_id,
        "week": f"{week_start} → {week_end}",
        "ghs": ghs,
        "review_triggered": review_triggered,
        "components": {
            "violation_rate": violation_score,
            "hash_chain": hash_chain_score,
            "auditor_uptime": auditor_uptime,
            "rubber_stamp": rubber_stamp_score,
            "mirror_drift": mirror_drift_score,
            "stale_state": stale_state_score,
            "hard_stop_recurrence": hard_stop_score,
            "alert_budget": alert_compliance
        }
    }


if __name__ == "__main__":
    result = compute_ghs()
    print(json.dumps(result, indent=2, default=str))
    if result["review_triggered"]:
        print(f"\n⚠️  GHS {result['ghs']} < {GHS_THRESHOLD} — operator review triggered")
    else:
        print(f"\n✅ GHS {result['ghs']} — healthy")
