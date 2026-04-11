#!/usr/bin/env python3
"""
titan-harness/bin/baseline_compare.py - Phase P1 (war-room graded A)

Compares a recent baseline snapshot against a reference (default: P0 frozen).
Prints a delta table. Writes regressions >5% to baseline_regressions.
"""
import os
import sys
import json
import argparse
from urllib import request, error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _fail(msg):
    print(f"baseline_compare: FATAL: {msg}", file=sys.stderr)
    sys.exit(2)


def _supa(path, method="GET", body=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    }
    if body:
        headers["Content-Type"] = "application/json"
        headers["Prefer"] = "return=representation"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except error.HTTPError as e:
        _fail(f"{method} {path}: {e.code} {e.read().decode()[:200]}")


def get_snapshot(name):
    rows = _supa(f"baseline_snapshots?snapshot_name=eq.{name}&order=run_at.desc&limit=1")
    if not rows:
        _fail(f"snapshot '{name}' not found")
    return rows[0]


def flatten(metrics, prefix=""):
    out = {}
    for k, v in (metrics or {}).items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        elif isinstance(v, (int, float)):
            out[key] = float(v)
    return out


def delta_pct(before, after):
    if before is None or after is None:
        return None
    if before == 0:
        return None
    return round((after - before) / before * 100, 2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--since", default="P0", help="Baseline snapshot name (default: P0)")
    p.add_argument("--until", default=None, help="Snapshot name to compare (default: most recent)")
    p.add_argument("--threshold", type=float, default=5.0, help="Regression threshold percent")
    p.add_argument("--write-regressions", action="store_true")
    p.add_argument("--json", action="store_true", help="Output JSON instead of table")
    args = p.parse_args()

    base = get_snapshot(args.since)
    if args.until:
        curr = get_snapshot(args.until)
    else:
        rows = _supa("baseline_snapshots?order=run_at.desc&limit=1")
        if not rows:
            _fail("no snapshots available")
        curr = rows[0]

    base_flat = flatten(base["metrics"])
    curr_flat = flatten(curr["metrics"])

    keys = sorted(set(base_flat.keys()) | set(curr_flat.keys()))

    results = []
    for k in keys:
        b = base_flat.get(k)
        c = curr_flat.get(k)
        d = delta_pct(b, c)
        results.append({"metric": k, "baseline": b, "current": c, "delta_pct": d})

    if args.json:
        print(json.dumps({
            "baseline_snapshot": base["snapshot_name"],
            "current_snapshot": curr["snapshot_name"],
            "results": results,
        }, indent=2, default=str))
    else:
        print(f"Comparing {curr['snapshot_name']} vs {base['snapshot_name']}")
        print(f"{'METRIC':60} {'BASELINE':>15} {'CURRENT':>15} {'DELTA%':>10}")
        print("-" * 105)
        for r in results:
            b = f"{r['baseline']:.2f}" if r['baseline'] is not None else "-"
            c = f"{r['current']:.2f}" if r['current'] is not None else "-"
            d = f"{r['delta_pct']:+.2f}" if r['delta_pct'] is not None else "-"
            print(f"{r['metric'][:60]:60} {b:>15} {c:>15} {d:>10}")

    # Regression detection
    regressions = []
    higher_is_worse_prefixes = ("mp_runs.duration_ms_", "tasks.elapsed_ms_", "war_room_exchanges.cost_cents_",
                                "war_room_exchanges.latency_ms_", "mp_runs.api_spend_cents_")
    lower_is_worse_prefixes = ("mp_runs.success_rate", "tasks.success_rate")

    for r in results:
        if r['delta_pct'] is None:
            continue
        metric = r['metric']
        if any(metric.startswith(p) for p in higher_is_worse_prefixes):
            if r['delta_pct'] > args.threshold:
                regressions.append({**r, "severity": "regression"})
        elif any(metric.startswith(p) for p in lower_is_worse_prefixes):
            if r['delta_pct'] < -args.threshold:
                regressions.append({**r, "severity": "regression"})

    if regressions:
        print(f"\n{len(regressions)} REGRESSIONS DETECTED (threshold ±{args.threshold}%)")
        for r in regressions:
            print(f"  {r['metric']}: {r['delta_pct']:+.2f}% (baseline={r['baseline']}, current={r['current']})")
        if args.write_regressions:
            for r in regressions:
                _supa("baseline_regressions", method="POST", body={
                    "snapshot_id": curr["id"],
                    "metric_path": r["metric"],
                    "baseline_value": r["baseline"],
                    "current_value": r["current"],
                    "delta_pct": r["delta_pct"],
                    "severity": "regression",
                })
            print(f"  wrote {len(regressions)} regressions to baseline_regressions")
    else:
        print(f"\nNo regressions beyond ±{args.threshold}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
