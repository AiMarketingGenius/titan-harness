#!/bin/bash
# bin/mp-status.sh
#
# Phase G.4 — Plain-English status query for MP-1 / MP-2 under a given
# project. Pulls from:
#   - public.mp_runs (most recent run per phase)
#   - /opt/amg-titan/solon-corpus/.checkpoint_mp1.json (if present)
#   - on-disk artifact counts (for checkpoint drift reconciliation)
#
# Usage:
#   mp-status.sh                           # default project EOM
#   mp-status.sh --project ACME
#   mp-status.sh --json                    # machine-readable
#   mp-status.sh --reconcile               # update checkpoint to match disk
#
# Output is designed for humans, not dashboards. Each phase gets a single
# line with status, artifacts, bytes, and last-run age.

set -u

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_HARNESS_DIR="$(cd "$_SCRIPT_DIR/.." && pwd)"

# ---- CLI parsing ------------------------------------------------------------
PROJECT="EOM"
FORMAT="text"
RECONCILE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --project)  PROJECT="$2"; shift 2 ;;
    --json)     FORMAT="json"; shift ;;
    --reconcile) RECONCILE=1; shift ;;
    -h|--help)
      sed -n '3,20p' "$0"
      exit 0
      ;;
    *) echo "mp-status: unknown arg: $1" >&2; exit 2 ;;
  esac
done

# ---- Load env ---------------------------------------------------------------
if [ -f "$_HARNESS_DIR/lib/titan-env.sh" ]; then . "$_HARNESS_DIR/lib/titan-env.sh"; fi
if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  for _f in /opt/titan-processor/.env /opt/amg-titan/.env /opt/amg-mcp-server/.env.local; do
    [ -f "$_f" ] && { set -a; . "$_f" 2>/dev/null; set +a; }
  done
  : "${SUPABASE_SERVICE_ROLE_KEY:=${SUPABASE_SERVICE_KEY:-}}"
fi

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  echo "mp-status: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY unset" >&2
  exit 2
fi

# ---- Reconcile MP-1 checkpoint against on-disk reality ---------------------
# The .checkpoint_mp1.json file drifts when phase scripts are run without
# updating it. Walk the corpus tree and count what's actually there.
CHECKPOINT_PATH="/opt/amg-titan/solon-corpus/.checkpoint_mp1.json"

_reconcile_mp1_checkpoint() {
  python3 - "$CHECKPOINT_PATH" "$RECONCILE" <<'PYEOF'
import json, sys, os, glob
from pathlib import Path

cp_path = sys.argv[1]
do_update = sys.argv[2] == "1"
CORPUS = Path("/opt/amg-titan/solon-corpus")

if not os.path.exists(cp_path):
    print(json.dumps({"exists": False, "drift": [], "updated": False}))
    sys.exit(0)

try:
    cp = json.loads(Path(cp_path).read_text())
except Exception as e:
    print(json.dumps({"exists": True, "error": f"parse: {e}"}))
    sys.exit(0)

# Phase → (subdir, file glob, min count to flip status)
sources = {
    "phase_1_claude_threads":  ("claude-threads", "*.json", 1),
    "phase_2_perplexity":      ("perplexity",      "*.json", 1),
    "phase_3_fireflies":       ("fireflies/transcripts", "*.json", 1),
    "phase_4_loom":            ("loom/videos",     "*.json", 1),
    "phase_5_gmail":           ("gmail",           "*.json", 1),
    "phase_6_slack":           ("slack/channels",  "*.jsonl", 1),
    "phase_7_mcp_decisions":   ("mcp-decisions",   "*.jsonl", 1),
}

drift = []
phases = cp.get("phases", {})
for phase_key, (subdir, pattern, min_count) in sources.items():
    base = CORPUS / subdir
    on_disk = len(list(base.rglob(pattern))) if base.exists() else 0
    recorded = phases.get(phase_key, {})
    recorded_status = recorded.get("status", "unknown")
    recorded_count = recorded.get("artifacts", 0)
    if on_disk >= min_count and recorded_status != "complete":
        drift.append({
            "phase": phase_key,
            "on_disk_count": on_disk,
            "recorded_status": recorded_status,
            "recorded_count": recorded_count,
        })
        if do_update:
            recorded["status"] = "reconciled_from_disk"
            recorded["artifacts"] = on_disk
            recorded["reconciled_at"] = "auto"
            phases[phase_key] = recorded

if do_update and drift:
    cp["phases"] = phases
    cp["last_reconciled"] = "auto"
    Path(cp_path).write_text(json.dumps(cp, indent=2))

print(json.dumps({
    "exists": True,
    "drift": drift,
    "updated": bool(do_update and drift),
    "percent_complete": cp.get("percent_complete", "?"),
    "status": cp.get("status", "?"),
}))
PYEOF
}

CHECKPOINT_REPORT=$(_reconcile_mp1_checkpoint)

# ---- Pull latest run per phase from Supabase -------------------------------
# We want "the most recent run per (project, megaprompt, phase_number)".
# PostgREST doesn't do window functions directly, so we fetch ordered and
# collapse in Python.
FETCH_URL="$SUPABASE_URL/rest/v1/mp_runs?project_id=eq.$PROJECT&select=megaprompt,phase_number,phase_name,status,artifacts_count,high_quality_count,bytes,war_room_grade,war_room_cost_cents,completed_at,blocker_reason,task_id&order=completed_at.desc.nullslast,created_at.desc&limit=500"

RUNS_JSON=$(curl -sS -m 10 "$FETCH_URL" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" 2>/dev/null)

if [ -z "$RUNS_JSON" ]; then
  RUNS_JSON="[]"
fi

# ---- Format output ---------------------------------------------------------
python3 - "$FORMAT" "$PROJECT" "$RUNS_JSON" "$CHECKPOINT_REPORT" <<'PYEOF'
import sys, json
from collections import defaultdict

fmt = sys.argv[1]
project = sys.argv[2]
runs = json.loads(sys.argv[3])
checkpoint = json.loads(sys.argv[4])

# Collapse to latest per phase
latest = {}
for r in runs:
    key = (r.get("megaprompt"), r.get("phase_number"))
    if key not in latest:
        latest[key] = r

# Known phase registry (same as mp-runner.sh)
PHASES = {
    ("mp1", 1): "claude_threads_harvest",
    ("mp1", 2): "perplexity_harvest",
    ("mp1", 3): "fireflies_harvest",
    ("mp1", 4): "loom_harvest",
    ("mp1", 5): "gmail_harvest",
    ("mp1", 6): "slack_harvest",
    ("mp1", 7): "mcp_decisions_harvest",
    ("mp1", 8): "manifest_consolidator",
    ("mp2", 1): "corpus_audit",
    ("mp2", 2): "voice_extraction",
    ("mp2", 3): "sales_patterns",
    ("mp2", 4): "decision_framework",
    ("mp2", 5): "operational_patterns",
    ("mp2", 6): "sop_codification",
    ("mp2", 7): "heldout_validation",
}

STATUS_EMOJI = {
    "complete":   "OK ",
    "running":    "RUN",
    "pending":    "...",
    "failed":     "FAIL",
    "blocked":    "BLK",
    "skipped":    "SKIP",
    "reconciled_from_disk": "RECN",
    "not_started": "   ",
}

if fmt == "json":
    out = {
        "project_id": project,
        "checkpoint": checkpoint,
        "latest_runs": {f"{k[0]}.{k[1]}": v for k,v in latest.items()},
    }
    print(json.dumps(out, indent=2))
    sys.exit(0)

# Text format
print(f"=== MP Status — project: {project} ===")
print()
print("MP-1 (Harvest)")
print("-" * 72)
for (mp, pn), name in [(k,v) for k,v in PHASES.items() if k[0] == "mp1"]:
    r = latest.get((mp, pn))
    if r:
        status = r.get("status", "?")
        arts = r.get("artifacts_count", 0) or 0
        bytes_ = r.get("bytes", 0) or 0
        grade = r.get("war_room_grade") or "-"
        line = f"  mp1.{pn} {name:<30} [{STATUS_EMOJI.get(status,'???')}] {arts:>5} arts  {bytes_:>10,} B  grade {grade}"
        if status == "blocked" and r.get("blocker_reason"):
            line += f"\n        ↳ {r['blocker_reason'][:80]}"
    else:
        line = f"  mp1.{pn} {name:<30} [   ] (no runs logged)"
    print(line)

print()
print("MP-2 (Synthesis)")
print("-" * 72)
for (mp, pn), name in [(k,v) for k,v in PHASES.items() if k[0] == "mp2"]:
    r = latest.get((mp, pn))
    if r:
        status = r.get("status", "?")
        arts = r.get("artifacts_count", 0) or 0
        grade = r.get("war_room_grade") or "-"
        cost = r.get("war_room_cost_cents", 0) or 0
        line = f"  mp2.{pn} {name:<30} [{STATUS_EMOJI.get(status,'???')}] {arts:>5} arts  grade {grade}  war-room {cost}¢"
        if status == "blocked" and r.get("blocker_reason"):
            line += f"\n        ↳ {r['blocker_reason'][:80]}"
    else:
        line = f"  mp2.{pn} {name:<30} [   ] (no runs logged)"
    print(line)

# Checkpoint drift
print()
print("MP-1 Checkpoint")
print("-" * 72)
if not checkpoint.get("exists"):
    print("  (no checkpoint file at /opt/amg-titan/solon-corpus/.checkpoint_mp1.json)")
else:
    print(f"  status:          {checkpoint.get('status','?')}")
    print(f"  percent_complete: {checkpoint.get('percent_complete','?')}")
    drift = checkpoint.get("drift", [])
    if drift:
        print(f"  drift detected:   {len(drift)} phase(s) have on-disk data but are not marked complete:")
        for d in drift:
            print(f"    - {d['phase']:<26} on_disk={d['on_disk_count']} recorded={d['recorded_status']}")
        if checkpoint.get("updated"):
            print("  ✓ checkpoint updated to reconcile with disk")
        else:
            print("  (run with --reconcile to auto-update the checkpoint)")
    else:
        print("  ✓ no drift — checkpoint matches disk")
PYEOF
