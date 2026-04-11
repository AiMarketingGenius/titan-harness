#!/usr/bin/env python3
"""
titan-harness/bin/baseline_report.py - Phase P1 (war-room graded A)

Computes performance baselines from actual Supabase data sources:
  - mp_runs       : phase-level duration, API spend, war-room grades
  - tasks         : task wall-clock (updated_at - created_at), tokens used
  - war_room_exchanges : per-exchange cost & grade distribution
  - tool_log      : tool-call frequency per session

Writes the aggregated snapshot to baseline_snapshots.
"""
import os
import sys
import json
import argparse
import subprocess
from datetime import datetime, timezone, timedelta
from urllib import request, error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SB_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF", "egoazyasyrhslluossli")
BASELINES_DIR = os.environ.get("TITAN_BASELINES_DIR", "/opt/titan-harness/baselines")


def _fail(msg):
    print(f"baseline_report: FATAL: {msg}", file=sys.stderr)
    sys.exit(2)


def _supa_get(path):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    req = request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    })
    try:
        with request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except error.HTTPError as e:
        _fail(f"GET {path}: {e.code} {e.read().decode()[:200]}")


def _mgmt_sql(query):
    if not SB_ACCESS_TOKEN:
        _fail("SUPABASE_ACCESS_TOKEN required for aggregate queries")
    url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
    body = json.dumps({"query": query}).encode()
    req = request.Request(url, data=body, headers={
        "Authorization": f"Bearer {SB_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "titan-harness/1.0 (baseline_report)",
    }, method="POST")
    try:
        with request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except error.HTTPError as e:
        _fail(f"mgmt SQL: {e.code} {e.read().decode()[:500]}")


def _num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _percentile(values, p):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * (p / 100)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def compute_metrics(window_days=14):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()

    metrics = {"window_days": window_days, "cutoff": cutoff}
    counts = {}

    # ---- mp_runs aggregates ----
    mp_rows = _mgmt_sql(
        f"SELECT duration_ms, api_spend_cents, war_room_grade, war_room_cost_cents, "
        f"bytes, words, megaprompt, phase_name, status "
        f"FROM mp_runs WHERE created_at >= '{cutoff}'"
    )
    counts["mp_runs"] = len(mp_rows)
    durations = [_num(r["duration_ms"]) for r in mp_rows if _num(r.get("duration_ms")) is not None]
    spends = [_num(r["api_spend_cents"]) for r in mp_rows if _num(r.get("api_spend_cents")) is not None]
    grades = [r["war_room_grade"] for r in mp_rows if r.get("war_room_grade")]
    wr_costs = [_num(r["war_room_cost_cents"]) for r in mp_rows if _num(r.get("war_room_cost_cents")) is not None]
    statuses = [r["status"] for r in mp_rows if r.get("status")]

    metrics["mp_runs"] = {
        "count": len(mp_rows),
        "duration_ms_p50": _percentile(durations, 50),
        "duration_ms_p95": _percentile(durations, 95),
        "duration_ms_p99": _percentile(durations, 99),
        "duration_ms_avg": sum(durations) / len(durations) if durations else None,
        "api_spend_cents_total": sum(spends) if spends else 0,
        "api_spend_cents_avg": sum(spends) / len(spends) if spends else None,
        "war_room_cost_cents_total": sum(wr_costs) if wr_costs else 0,
        "grades_distribution": _dist(grades),
        "status_distribution": _dist(statuses),
        "success_rate": round(statuses.count("done") / len(statuses), 4) if statuses else None,
    }

    # ---- tasks wall-clock ----
    task_rows = _mgmt_sql(
        "SELECT task_type, status, api_tokens_used, "
        "EXTRACT(EPOCH FROM (updated_at - created_at)) * 1000 AS elapsed_ms "
        f"FROM tasks WHERE created_at >= '{cutoff}'"
    )
    counts["tasks"] = len(task_rows)
    t_elapsed = [float(r["elapsed_ms"]) for r in task_rows if r.get("elapsed_ms") is not None]
    t_tokens = [_num(r["api_tokens_used"]) for r in task_rows if _num(r.get("api_tokens_used")) is not None]
    t_statuses = [r["status"] for r in task_rows if r.get("status")]
    t_types = [r["task_type"] for r in task_rows if r.get("task_type")]

    metrics["tasks"] = {
        "count": len(task_rows),
        "elapsed_ms_p50": _percentile(t_elapsed, 50),
        "elapsed_ms_p95": _percentile(t_elapsed, 95),
        "elapsed_ms_avg": sum(t_elapsed) / len(t_elapsed) if t_elapsed else None,
        "api_tokens_used_total": sum(t_tokens) if t_tokens else 0,
        "api_tokens_used_avg": sum(t_tokens) / len(t_tokens) if t_tokens else None,
        "status_distribution": _dist(t_statuses),
        "type_distribution": _dist(t_types),
        "success_rate": round(
            sum(1 for s in t_statuses if s in ("done", "completed")) / len(t_statuses), 4
        ) if t_statuses else None,
    }

    # ---- war_room_exchanges ----
    wr_rows = _mgmt_sql(
        "SELECT grade, cost_cents, input_tokens, output_tokens, round_number "
        f"FROM war_room_exchanges WHERE created_at >= '{cutoff}'"
    )
    counts["war_room_exchanges"] = len(wr_rows)
    wr_grades = [r["grade"] for r in wr_rows if r.get("grade")]
    wr_costs2 = [_num(r["cost_cents"]) for r in wr_rows if _num(r.get("cost_cents")) is not None]
    wr_tok = [(_num(r.get("input_tokens")) or 0) + (_num(r.get("output_tokens")) or 0) for r in wr_rows]

    metrics["war_room_exchanges"] = {
        "count": len(wr_rows),
        "grade_distribution": _dist(wr_grades),
        "cost_cents_total": sum(wr_costs2) if wr_costs2 else 0,
        "cost_cents_avg": sum(wr_costs2) / len(wr_costs2) if wr_costs2 else None,
        "tokens_total_p50": _percentile(wr_tok, 50),
        "tokens_total_p95": _percentile(wr_tok, 95),
        "tokens_total_sum": sum(wr_tok) if wr_tok else 0,
    }

    # ---- tool_log frequency ----
    tl_rows = _mgmt_sql(
        "SELECT tool_name, COUNT(*) AS n "
        f"FROM tool_log WHERE ts >= '{cutoff}' GROUP BY tool_name ORDER BY n DESC"
    )
    counts["tool_log"] = sum(int(r["n"]) for r in tl_rows)
    metrics["tool_log"] = {
        "total_calls": counts["tool_log"],
        "top_tools": {r["tool_name"]: int(r["n"]) for r in tl_rows[:20]},
    }

    return metrics, counts


def _dist(items):
    out = {}
    for v in items:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def capture_policy_capacity():
    keys = [
        "POLICY_CAPACITY_MAX_CLAUDE_SESSIONS",
        "POLICY_CAPACITY_MAX_HEAVY_TASKS",
        "POLICY_CAPACITY_MAX_N8N_BRANCHES",
        "POLICY_CAPACITY_MAX_HEAVY_WORKFLOWS",
        "POLICY_CAPACITY_MAX_WORKERS_GENERAL",
        "POLICY_CAPACITY_MAX_WORKERS_CPU_HEAVY",
        "POLICY_CAPACITY_MAX_LLM_BATCH_SIZE",
        "POLICY_CAPACITY_MAX_LLM_CONCURRENT_BATCHES",
        "POLICY_CAPACITY_CPU_SOFT_PCT",
        "POLICY_CAPACITY_CPU_HARD_PCT",
        "POLICY_CAPACITY_RAM_SOFT_GIB",
        "POLICY_CAPACITY_RAM_HARD_GIB",
    ]
    return {k: os.environ.get(k) for k in keys}


def write_snapshot(snapshot_name, window_days, metrics, counts, freeze=False, notes=""):
    payload = {
        "snapshot_name": snapshot_name,
        "window_days": window_days,
        "is_frozen": freeze,
        "policy_capacity": capture_policy_capacity(),
        "metrics": metrics,
        "source_counts": counts,
        "notes": notes,
    }
    url = f"{SUPABASE_URL}/rest/v1/baseline_snapshots"
    body = json.dumps(payload).encode()
    req = request.Request(url, data=body, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }, method="POST")
    try:
        with request.urlopen(req, timeout=30) as r:
            rows = json.loads(r.read().decode())
            return rows[0] if rows else None
    except error.HTTPError as e:
        _fail(f"write_snapshot: {e.code} {e.read().decode()[:500]}")


def write_markdown(snapshot, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    m = snapshot["metrics"]
    lines = []
    lines.append(f"# Baseline Snapshot: {snapshot['snapshot_name']}")
    lines.append("")
    lines.append(f"**Run at:** {snapshot['run_at']}")
    lines.append(f"**Window:** last {snapshot['window_days']} days (cutoff: {m.get('cutoff','?')})")
    lines.append(f"**Frozen:** {snapshot['is_frozen']}")
    lines.append("")
    lines.append("## Policy Capacity at Snapshot")
    for k, v in (snapshot.get("policy_capacity") or {}).items():
        lines.append(f"- {k} = `{v}`")
    lines.append("")
    lines.append("## Source Row Counts")
    for k, v in (snapshot.get("source_counts") or {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## mp_runs (phase-level)")
    mr = m.get("mp_runs", {})
    for k, v in mr.items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")
    lines.append("## tasks (task wall-clock)")
    for k, v in m.get("tasks", {}).items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")
    lines.append("## war_room_exchanges")
    for k, v in m.get("war_room_exchanges", {}).items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")
    lines.append("## tool_log frequency")
    for k, v in m.get("tool_log", {}).items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")
    lines.append("---")
    lines.append("*Generated by baseline_report.py (Phase P1)*")
    open(path, "w").write("\n".join(lines))
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-days", type=int, default=14)
    parser.add_argument("--name", default=None, help="Snapshot name (e.g. 'P0' or 'weekly_YYYY-MM-DD')")
    parser.add_argument("--freeze", action="store_true", help="Mark snapshot as frozen (P0 reference)")
    parser.add_argument("--weekly", action="store_true", help="Weekly cron mode: auto-name + no freeze")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        _fail("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")

    # Capacity gate preflight
    cap = subprocess.run(["/opt/titan-harness/bin/check-capacity.sh"], capture_output=True)
    if cap.returncode == 2:
        _fail("capacity HARD block — refusing to run baseline report")

    if args.weekly:
        name = f"weekly_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        freeze = False
    else:
        name = args.name or f"snapshot_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')}"
        freeze = args.freeze

    print(f"baseline_report: computing metrics for '{name}' (window={args.window_days}d, freeze={freeze})")
    metrics, counts = compute_metrics(args.window_days)
    print(f"baseline_report: row counts = {counts}")

    snap = write_snapshot(name, args.window_days, metrics, counts, freeze=freeze, notes=args.notes)
    print(f"baseline_report: snapshot id = {snap['id']}")

    md_path = os.path.join(BASELINES_DIR, f"{name}_baseline.md")
    write_markdown(snap, md_path)
    print(f"baseline_report: markdown report -> {md_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
