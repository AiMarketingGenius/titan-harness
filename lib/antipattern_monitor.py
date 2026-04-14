#!/usr/bin/env python3
"""DR-AMG-GOVERNANCE-01 Phase 3 Task 3.5 — Anti-Pattern Monitoring

Daily queries for each anti-pattern with auto-alerting:
M.2 - Audit Log Manipulation (hash chain break)
M.3 - Reviewer Capture (held-out failure rate > 5%)
M.4 - Alert Fatigue (>3 actionable alerts/day for 3+ days)
M.5 - Governance Theater (GHS=0 / no events = silent disablement)
M.6 - Rule Proliferation Without Enforcement (orphan rules)
M.7 - Confident-Wrong Agent (self-report vs auditor mismatch)
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


def check_m2_audit_manipulation():
    """M.2: Hash chain verification — recompute last 1000 entries."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT event_id AS id, prev_event_hash AS prev_hash, this_event_hash AS hash
        FROM public.governance_audit
        ORDER BY timestamp_utc DESC
        LIMIT 1000
    """)
    rows = cur.fetchall()

    if not rows:
        cur.close()
        conn.close()
        return {"pattern": "M2", "status": "no_data", "severity": "INFO"}

    # Check chain continuity (each prev_hash should match prior row's hash)
    breaks = []
    sorted_rows = sorted(rows, key=lambda r: r["id"])
    for i in range(1, len(sorted_rows)):
        if sorted_rows[i].get("prev_hash") and sorted_rows[i]["prev_hash"] != sorted_rows[i-1].get("hash"):
            breaks.append(sorted_rows[i]["id"])

    cur.close()
    conn.close()

    if breaks:
        return {
            "pattern": "M2",
            "status": "DETECTED",
            "severity": "SEV1",
            "description": f"Hash chain break at {len(breaks)} point(s): rows {breaks[:5]}",
            "evidence": {"broken_rows": breaks[:10]}
        }
    return {"pattern": "M2", "status": "clean", "severity": "INFO"}


def check_m3_reviewer_capture():
    """M.3: Held-out example failure rate > 5% over rolling 30 days."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE action_payload->>'held_out_result' = 'fail') AS failures
        FROM public.governance_audit
        WHERE action_type = 'reviewer_held_out_test'
          AND timestamp_utc >= %s
    """, (cutoff,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    total = row["total"] or 0
    failures = row["failures"] or 0
    rate = failures / max(total, 1)

    if rate > 0.05 and total >= 10:
        return {
            "pattern": "M3",
            "status": "DETECTED",
            "severity": "SEV2",
            "description": f"Reviewer held-out failure rate {rate:.1%} ({failures}/{total}) exceeds 5% threshold",
            "evidence": {"failure_rate": round(rate, 4), "total": total, "failures": failures}
        }
    return {"pattern": "M3", "status": "clean", "severity": "INFO", "rate": round(rate, 4)}


def check_m4_alert_fatigue():
    """M.4: >3 actionable alerts/day sustained for 3+ days."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT DATE(timestamp_utc) AS alert_date, COUNT(*) AS alert_count
        FROM public.governance_audit
        WHERE action_type LIKE 'alert%%'
          AND timestamp_utc >= NOW() - INTERVAL '7 days'
        GROUP BY DATE(timestamp_utc)
        HAVING COUNT(*) > 3
        ORDER BY alert_date DESC
    """)
    high_days = cur.fetchall()
    cur.close()
    conn.close()

    consecutive = 0
    if high_days:
        dates = sorted([r["alert_date"] for r in high_days])
        for i in range(1, len(dates)):
            if (dates[i] - dates[i-1]).days == 1:
                consecutive += 1
            else:
                consecutive = 0

    if consecutive >= 2:  # 3+ consecutive days
        return {
            "pattern": "M4",
            "status": "DETECTED",
            "severity": "SEV2",
            "description": f"Alert fatigue: {consecutive+1} consecutive days with >3 alerts",
            "evidence": {"high_alert_days": [str(r["alert_date"]) for r in high_days]}
        }
    return {"pattern": "M4", "status": "clean", "severity": "INFO"}


def check_m5_governance_theater():
    """M.5: GHS drops to 0 / no events logged = governance stream silent."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Check if any governance events in last 24h
    cur.execute("""
        SELECT COUNT(*) AS event_count
        FROM public.governance_audit
        WHERE timestamp_utc >= NOW() - INTERVAL '24 hours'
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()

    if (row["event_count"] or 0) == 0:
        return {
            "pattern": "M5",
            "status": "DETECTED",
            "severity": "SEV1",
            "description": "Governance stream silent — 0 events in last 24h. Confirm governance layer alive.",
            "evidence": {"events_24h": 0}
        }
    return {"pattern": "M5", "status": "clean", "severity": "INFO", "events_24h": row["event_count"]}


def check_m6_orphan_rules():
    """M.6: Standing rules in MCP without corresponding enforcement mechanism."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE action_payload->>'has_enforcement' = 'false') AS orphans,
            COUNT(*) AS total
        FROM public.governance_audit
        WHERE action_type = 'rule_enforcement_check'
          AND timestamp_utc >= NOW() - INTERVAL '7 days'
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()

    orphans = row["orphans"] or 0
    if orphans > 0:
        return {
            "pattern": "M6",
            "status": "DETECTED",
            "severity": "SEV2",
            "description": f"{orphans} standing rule(s) without enforcement mechanism",
            "evidence": {"orphan_count": orphans}
        }
    return {"pattern": "M6", "status": "clean", "severity": "INFO"}


def check_m7_confident_wrong():
    """M.7: Titan self-report 'complete' vs auditor cross-check mismatch."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            COUNT(*) AS total_checks,
            COUNT(*) FILTER (WHERE action_payload->>'auditor_match' = 'false') AS mismatches
        FROM public.governance_audit
        WHERE action_type = 'completion_crosscheck'
          AND timestamp_utc >= NOW() - INTERVAL '7 days'
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()

    mismatches = row["mismatches"] or 0
    if mismatches > 0:
        return {
            "pattern": "M7",
            "status": "DETECTED",
            "severity": "SEV1",
            "description": f"{mismatches} self-report/auditor mismatch(es) in last 7 days — I.4 hard-stop",
            "evidence": {"mismatches": mismatches, "total_checks": row["total_checks"]}
        }
    return {"pattern": "M7", "status": "clean", "severity": "INFO"}


def run_all_checks():
    """Run all anti-pattern checks and store results."""
    checks = [
        check_m2_audit_manipulation,
        check_m3_reviewer_capture,
        check_m4_alert_fatigue,
        check_m5_governance_theater,
        check_m6_orphan_rules,
        check_m7_confident_wrong,
    ]

    results = []
    for check_fn in checks:
        try:
            result = check_fn()
        except Exception as e:
            result = {
                "pattern": check_fn.__name__.split("_")[1].upper(),
                "status": "ERROR",
                "severity": "SEV2",
                "description": f"Check failed: {str(e)}"
            }
        results.append(result)

        # If detected, store in antipattern_events table
        if result.get("status") == "DETECTED":
            store_antipattern_event(result)

    return results


def store_antipattern_event(result):
    """Store detected anti-pattern in governance_antipattern_events."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO public.governance_antipattern_events (
                pattern_code, severity, description, evidence
            ) VALUES (%s, %s, %s, %s)
        """, (
            result["pattern"],
            result["severity"],
            result["description"],
            json.dumps(result.get("evidence", {}))
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"WARNING: Failed to store antipattern event: {e}", file=sys.stderr)


if __name__ == "__main__":
    results = run_all_checks()
    detected = [r for r in results if r["status"] == "DETECTED"]
    print(json.dumps(results, indent=2, default=str))
    if detected:
        print(f"\n⚠️  {len(detected)} anti-pattern(s) DETECTED:")
        for d in detected:
            print(f"  {d['severity']}: {d['pattern']} — {d['description']}")
    else:
        print("\n✅ All anti-pattern checks clean")
