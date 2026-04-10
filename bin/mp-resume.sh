#!/bin/bash
# bin/mp-resume.sh
#
# Phase G.4 — Resume the next unblocked MP phase under the harness runner.
#
# Looks at the latest run per phase in public.mp_runs, identifies the next
# phase that is NOT complete and NOT blocked (or is pending/failed and
# needs retry), and invokes mp-runner.sh on it.
#
# Usage:
#   mp-resume.sh                           # resume MP-1, then MP-2
#   mp-resume.sh --only mp1                # resume only MP-1 phases
#   mp-resume.sh --only mp2                # resume only MP-2 phases
#   mp-resume.sh --project ACME            # resume for tenant ACME
#   mp-resume.sh --dry-run                 # show what would run, don't execute
#
# Safety: will not run more than one phase per invocation. To chain, call
# mp-resume.sh repeatedly or wrap it in a loop.

set -u

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_HARNESS_DIR="$(cd "$_SCRIPT_DIR/.." && pwd)"

PROJECT="EOM"
ONLY=""
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --only)    ONLY="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '3,20p' "$0"; exit 0 ;;
    *) echo "mp-resume: unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Load env
if [ -f "$_HARNESS_DIR/lib/titan-env.sh" ]; then . "$_HARNESS_DIR/lib/titan-env.sh"; fi
if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  for _f in /opt/titan-processor/.env /opt/amg-titan/.env /opt/amg-mcp-server/.env.local; do
    [ -f "$_f" ] && { set -a; . "$_f" 2>/dev/null; set +a; }
  done
  : "${SUPABASE_SERVICE_ROLE_KEY:=${SUPABASE_SERVICE_KEY:-}}"
fi

# Pull latest run per phase
FETCH_URL="$SUPABASE_URL/rest/v1/mp_runs?project_id=eq.$PROJECT&select=megaprompt,phase_number,status,blocker_reason&order=created_at.desc&limit=500"
RUNS_JSON=$(curl -sS -m 10 "$FETCH_URL" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" 2>/dev/null || echo "[]")

# Decide next phase
NEXT=$(python3 - "$RUNS_JSON" "$ONLY" <<'PYEOF'
import sys, json
from collections import OrderedDict

runs = json.loads(sys.argv[1])
only = sys.argv[2]

# Collapse to latest per phase
latest = {}
for r in runs:
    key = (r.get("megaprompt"), r.get("phase_number"))
    if key not in latest:
        latest[key] = r.get("status")

# Walk in canonical order
order = [
    ("mp1", 1), ("mp1", 2), ("mp1", 3), ("mp1", 4), ("mp1", 5),
    ("mp1", 6), ("mp1", 7), ("mp1", 8),
    ("mp2", 1), ("mp2", 2), ("mp2", 3), ("mp2", 4), ("mp2", 5),
    ("mp2", 6), ("mp2", 7),
]
if only in ("mp1", "mp2"):
    order = [(m,p) for m,p in order if m == only]

# Find first phase that is not 'complete' and not 'blocked'
# Pending, failed, or never-run → candidate to (re)run.
for mp, pn in order:
    st = latest.get((mp, pn))
    if st in ("complete", "blocked", "running"):
        continue
    print(f"{mp} {pn}")
    sys.exit(0)

# All complete or blocked
print("")
PYEOF
)

if [ -z "$NEXT" ]; then
  echo "mp-resume: no runnable phase found for project=$PROJECT" \
       "${ONLY:+ (filter: $ONLY)}"
  echo "  everything is either complete, blocked, or already running."
  echo "  run mp-status.sh to see what's going on."
  exit 0
fi

MP=$(echo "$NEXT" | awk '{print $1}')
PN=$(echo "$NEXT" | awk '{print $2}')

if [ "$DRY_RUN" -eq 1 ]; then
  echo "mp-resume: next phase to run: $MP.$PN (project=$PROJECT)"
  echo "  (dry-run — not executing)"
  exit 0
fi

echo "mp-resume: launching $MP phase $PN for project $PROJECT"
exec "$_HARNESS_DIR/bin/mp-runner.sh" "$MP" "$PN" --project "$PROJECT"
