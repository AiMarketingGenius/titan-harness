#!/usr/bin/env python3
"""DR-AMG-GOVERNANCE-01 Phase 3 Task 3.2 — Drift Scoring

Daily cron compares last 24h distributions against rolling baseline.
Deviation > 2σ → GOV-SEV2 alert "behavioral drift"
Deviation > 3σ → hard-stop trigger I.10
Uses Kolmogorov-Smirnov test for distribution comparison.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 not installed")
    sys.exit(1)

try:
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

DB_URL = os.environ.get("SUPABASE_DB_URL", "")

DIMENSIONS = [
    "bash_actions", "git_actions", "mcp_read_actions", "mcp_write_actions",
    "api_call_actions", "time_to_first_action_s", "avg_diff_size_lines",
    "reviewer_grade_a_pct", "reviewer_grade_b_pct", "reviewer_grade_fail_pct",
    "override_count", "cli_actions", "stagehand_actions"
]

# Thresholds
SIGMA_WARNING = 2.0   # GOV-SEV2
SIGMA_CRITICAL = 3.0  # hard-stop I.10
KS_P_THRESHOLD = 0.05  # reject null if p < 0.05


def get_db():
    if not DB_URL:
        raise RuntimeError("SUPABASE_DB_URL not set")
    return psycopg2.connect(DB_URL)


def score_drift():
    """Compare last 24h behavioral data against rolling baseline."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    now = datetime.now(timezone.utc)
    recent_start = now - timedelta(hours=24)

    results = []

    for dim in DIMENSIONS:
        # Get baseline distribution (rolling 14-day)
        cur.execute(f"""
            SELECT {dim} FROM public.governance_baseline
            WHERE is_rolling_baseline = true
            ORDER BY captured_at
        """)
        baseline_vals = [float(r[dim] or 0) for r in cur.fetchall()]

        # Get recent distribution (last 24h)
        cur.execute(f"""
            SELECT {dim} FROM public.governance_baseline
            WHERE captured_at >= %s
            ORDER BY captured_at
        """, (recent_start,))
        recent_vals = [float(r[dim] or 0) for r in cur.fetchall()]

        # Calculate z-score
        if baseline_vals:
            mean = sum(baseline_vals) / len(baseline_vals)
            variance = sum((x - mean) ** 2 for x in baseline_vals) / max(len(baseline_vals), 1)
            stddev = variance ** 0.5
        else:
            mean, stddev = 0, 0

        recent_mean = sum(recent_vals) / max(len(recent_vals), 1) if recent_vals else 0
        z_score = abs(recent_mean - mean) / stddev if stddev > 0 else 0

        # KS test if scipy available and enough data
        ks_stat, ks_p = 0.0, 1.0
        if HAS_SCIPY and len(baseline_vals) >= 5 and len(recent_vals) >= 2:
            ks_result = scipy_stats.ks_2samp(baseline_vals, recent_vals)
            ks_stat = float(ks_result.statistic)
            ks_p = float(ks_result.pvalue)

        # Determine drift level
        if z_score >= SIGMA_CRITICAL or (ks_p < KS_P_THRESHOLD and ks_stat > 0.5):
            drift_level = "critical"
            alert_fired = True
        elif z_score >= SIGMA_WARNING or (ks_p < KS_P_THRESHOLD and ks_stat > 0.3):
            drift_level = "warning"
            alert_fired = True
        else:
            drift_level = "normal"
            alert_fired = False

        # Insert drift score
        cur.execute("""
            INSERT INTO public.governance_drift_scores (
                dimension, baseline_mean, baseline_stddev,
                recent_value, z_score, ks_statistic, ks_p_value,
                drift_level, alert_fired
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            dim, round(mean, 4), round(stddev, 4),
            round(recent_mean, 4), round(z_score, 4),
            round(ks_stat, 6), round(ks_p, 6),
            drift_level, alert_fired
        ))
        row_id = cur.fetchone()["id"]

        results.append({
            "dimension": dim,
            "z_score": round(z_score, 4),
            "ks_stat": round(ks_stat, 6),
            "drift_level": drift_level,
            "alert_fired": alert_fired,
            "id": row_id
        })

    conn.commit()
    cur.close()
    conn.close()
    return results


def inject_artificial_drift(dimension: str, multiplier: float = 5.0):
    """For testing ONLY: inject an artificial drift spike. Marked as test data."""
    if os.environ.get("GOVERNANCE_TEST_MODE") != "true":
        print("ERROR: Set GOVERNANCE_TEST_MODE=true to use drift injection")
        sys.exit(1)

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    now = datetime.now(timezone.utc)
    # Get baseline mean for the dimension
    cur.execute(f"""
        SELECT AVG({dimension}) AS mean FROM public.governance_baseline
        WHERE is_rolling_baseline = true
    """)
    row = cur.fetchone()
    baseline_mean = float(row["mean"] or 10)
    injected_value = baseline_mean * multiplier

    # Insert a test record with inflated value (marked as test data)
    values = {d: 0 for d in DIMENSIONS}
    values[dimension] = injected_value

    cur.execute("""
        INSERT INTO public.governance_baseline (
            session_id, window_start, window_end,
            bash_actions, git_actions, mcp_read_actions, mcp_write_actions,
            api_call_actions, time_to_first_action_s, avg_diff_size_lines,
            reviewer_grade_a_pct, reviewer_grade_b_pct, reviewer_grade_fail_pct,
            override_count, cli_actions, stagehand_actions, is_rolling_baseline
        ) VALUES (
            'drift-test', %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, false
        )
    """, (
        now - timedelta(minutes=30), now,
        values["bash_actions"], values["git_actions"],
        values["mcp_read_actions"], values["mcp_write_actions"],
        values["api_call_actions"], values["time_to_first_action_s"],
        values["avg_diff_size_lines"], values["reviewer_grade_a_pct"],
        values["reviewer_grade_b_pct"], values["reviewer_grade_fail_pct"],
        values["override_count"], values["cli_actions"],
        values["stagehand_actions"]
    ))
    conn.commit()
    cur.close()
    conn.close()
    print(f"Injected drift: {dimension} = {injected_value} (baseline mean: {baseline_mean})")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Drift scoring")
    parser.add_argument("--score", action="store_true", help="Run drift scoring")
    parser.add_argument("--inject-drift", type=str, help="Inject artificial drift for testing")
    parser.add_argument("--multiplier", type=float, default=5.0, help="Drift multiplier")
    args = parser.parse_args()

    if args.score:
        results = score_drift()
        alerts = [r for r in results if r["alert_fired"]]
        print(json.dumps(results, indent=2))
        if alerts:
            print(f"\n⚠️  DRIFT ALERTS: {len(alerts)} dimensions flagged")
            for a in alerts:
                print(f"  {a['drift_level'].upper()}: {a['dimension']} z={a['z_score']}")
        else:
            print("\n✅ All dimensions within normal range")
    elif args.inject_drift:
        inject_artificial_drift(args.inject_drift, args.multiplier)
    else:
        parser.print_help()
