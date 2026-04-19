#!/bin/bash
# mcp-archive-daily.sh — CT-0419-07 Step 3 (L2 daily markdown export)
#
# Exports all MCP op_decisions from past 24h (or a --date override) to
# /opt/amg-mcp-archive/decisions-YYYY-MM-DD.md plus appends sprint_state snapshot.
# Cron: 02:00 ET daily via mcp-archive-daily.timer.
#
# Usage:
#   mcp-archive-daily.sh                 # export yesterday (00:00–23:59:59 UTC)
#   mcp-archive-daily.sh --date 2026-04-15
#   mcp-archive-daily.sh --backfill 90   # one-time: export last 90 daily files

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./mcp-common.sh
. "$SCRIPT_DIR/mcp-common.sh"

ARCHIVE_DIR="/opt/amg-mcp-archive"
LOG_FILE="/opt/amg/logs/mcp-archive-daily.log"
RETENTION_DAYS=90

mkdir -p "$ARCHIVE_DIR" "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$LOG_FILE"; }

mcp_env_load
mcp_require_env || { log "FAIL missing_env"; exit 1; }

DATE_ARG=""
BACKFILL_DAYS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --date) DATE_ARG="$2"; shift 2 ;;
    --backfill) BACKFILL_DAYS="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# Export a single day
export_day() {
  local day="$1"
  local outfile="$ARCHIVE_DIR/decisions-${day}.md"
  local after="${day}T00:00:00Z"
  local before
  before=$(python3 -c "import datetime; d=datetime.date.fromisoformat('$day'); print((d+datetime.timedelta(days=1)).isoformat())")T00:00:00Z

  log "BEGIN day=${day} file=${outfile}"

  # Paginated fetch (page_size=200)
  local page=0 page_size=200 total=0
  local tmp_all=$(mktemp)
  : >"$tmp_all"

  while :; do
    local off=$((page * page_size))
    local tmp_page=$(mktemp)
    local hc
    hc=$(curl -sS -m 15 -w '%{http_code}' -o "$tmp_page" \
      "${SUPABASE_URL}/rest/v1/op_decisions?select=*&created_at=gte.${after}&created_at=lt.${before}&order=created_at.asc&limit=${page_size}&offset=${off}" \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}")
    if [ "$hc" != "200" ]; then
      rm -f "$tmp_page" "$tmp_all"
      log "FAIL day=${day} page=${page} http=${hc}"
      return 2
    fi
    local got
    got=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))))' "$tmp_page")
    total=$((total + got))
    # Merge page into running JSON array
    python3 - "$tmp_all" "$tmp_page" <<'PY'
import json, sys
acc_path, page_path = sys.argv[1:]
try:
    with open(acc_path) as f: acc = json.load(f) if f.read(1) else []
except Exception: acc = []
with open(acc_path) as f:
    raw = f.read()
acc = json.loads(raw) if raw.strip() else []
with open(page_path) as f:
    page = json.load(f)
acc.extend(page)
with open(acc_path, "w") as f:
    json.dump(acc, f)
PY
    rm -f "$tmp_page"
    [ "$got" -lt "$page_size" ] && break
    page=$((page + 1))
  done

  # Sprint snapshot
  local sprint_tmp=$(mktemp)
  curl -sS -m 5 -o "$sprint_tmp" \
    "${SUPABASE_URL}/rest/v1/op_sprint_state?project_id=eq.EOM&select=*&limit=1" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" 2>/dev/null

  # Render markdown
  python3 - "$tmp_all" "$sprint_tmp" "$outfile" "$day" <<'PY'
import json, sys, datetime
decs_f, sprint_f, out_f, day = sys.argv[1:]
try:
    with open(decs_f) as f: decs = json.load(f)
except Exception: decs = []
try:
    with open(sprint_f) as f: sprint = json.load(f)
except Exception: sprint = []

sprint_row = sprint[0] if sprint else {}
now_iso = datetime.datetime.utcnow().isoformat() + "Z"

lines = []
lines.append("---")
lines.append(f"date: {day}")
lines.append(f"decision_count: {len(decs)}")
lines.append(f"sprint_completion_pct: {sprint_row.get('completion_pct', 'n/a')}")
lines.append(f"sprint_name: {json.dumps(sprint_row.get('sprint_name', ''))}")
lines.append(f"exported_at: {now_iso}")
lines.append(f"exporter: mcp-archive-daily.sh (CT-0419-07)")
lines.append("---")
lines.append("")
lines.append(f"# MCP decisions for {day}")
lines.append("")
if not decs:
    lines.append("_No decisions logged this day._")
    lines.append("")
else:
    for d in decs:
        did = d.get("id", "")
        ts = d.get("created_at", "")
        src = d.get("project_source", "")
        dtype = d.get("decision_type", "")
        tags = d.get("tags") or []
        tag_str = ", ".join(tags)
        text = d.get("decision_text", "") or ""
        rationale = d.get("rationale", "") or ""
        operator = d.get("operator_id", "")
        lines.append(f"## {ts} · {src}")
        lines.append("")
        lines.append(f"- **id:** `{did}`")
        lines.append(f"- **decision_type:** {dtype}")
        lines.append(f"- **operator:** {operator}")
        if tag_str:
            lines.append(f"- **tags:** {tag_str}")
        lines.append("")
        lines.append("**Decision:**")
        lines.append("")
        lines.append("```")
        lines.append(text)
        lines.append("```")
        if rationale:
            lines.append("")
            lines.append("**Rationale:**")
            lines.append("")
            lines.append("```")
            lines.append(rationale)
            lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

lines.append("## Sprint snapshot (end of day)")
lines.append("")
lines.append("```json")
lines.append(json.dumps(sprint_row, indent=2, default=str))
lines.append("```")

with open(out_f, "w") as f:
    f.write("\n".join(lines) + "\n")

print(f"OK count={len(decs)} out={out_f}")
PY
  local prc=$?
  rm -f "$tmp_all" "$sprint_tmp"
  if [ "$prc" -ne 0 ]; then
    log "FAIL day=${day} render_fail rc=${prc}"
    return 3
  fi
  log "OK day=${day} count=${total} file=${outfile}"
  return 0
}

# Retention prune
prune_old() {
  local cutoff_epoch
  cutoff_epoch=$(python3 -c "import time; print(int(time.time()) - ${RETENTION_DAYS}*86400)")
  local removed=0
  for f in "$ARCHIVE_DIR"/decisions-*.md; do
    [ -f "$f" ] || continue
    local m
    m=$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null)
    [ -z "$m" ] && continue
    if [ "$m" -lt "$cutoff_epoch" ]; then
      rm -f "$f"
      removed=$((removed+1))
    fi
  done
  [ "$removed" -gt 0 ] && log "PRUNE removed=${removed}"
}

if [ "$BACKFILL_DAYS" -gt 0 ]; then
  log "BACKFILL days=${BACKFILL_DAYS}"
  for i in $(seq 1 "$BACKFILL_DAYS"); do
    d=$(python3 -c "import datetime; print((datetime.date.today()-datetime.timedelta(days=$i)).isoformat())")
    # Skip if already present (idempotent)
    if [ -f "$ARCHIVE_DIR/decisions-${d}.md" ]; then
      log "SKIP day=${d} already_exists"
      continue
    fi
    export_day "$d" || log "WARN backfill_fail day=${d}"
  done
  log "BACKFILL done"
  prune_old
  exit 0
fi

# Default: export yesterday (cron at 02:00 ET runs for previous day)
if [ -z "$DATE_ARG" ]; then
  DATE_ARG=$(python3 -c "import datetime; print((datetime.date.today()-datetime.timedelta(days=1)).isoformat())")
fi

export_day "$DATE_ARG"
RC=$?
prune_old
exit $RC
