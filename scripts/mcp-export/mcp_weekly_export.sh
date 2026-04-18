#!/bin/bash
# scripts/mcp-export/mcp_weekly_export.sh
#
# Weekly MCP → R2 export with verify-first, per Solon autonomous-queue
# interstitial directive 2026-04-18. Pulls public.op_decisions + op_sprints
# + op_blockers from Supabase via REST, writes NDJSON.gz, uploads to R2,
# verifies readback by checksum + row count.
#
# Runs on VPS (where /etc/amg/supabase.env + rclone r2 config live).
# Invoked weekly via systemd timer mcp-weekly-export.timer (installed
# separately; see companion .service / .timer files).
#
# Usage:
#   bash mcp_weekly_export.sh [--dry-run] [--since YYYY-MM-DD]
#
# Exit codes:
#   0 = export complete + verified
#   1 = transient Supabase / rclone error (retry recommended)
#   2 = verification mismatch — DO NOT ROTATE older backups
#   3 = missing env or config

set -euo pipefail

# ----- config -----
load_env_safe() {
  local f="$1"
  [ -f "$f" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|'#'*) continue ;;
      *=*)
        local key="${line%%=*}"
        local value="${line#*=}"
        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"
        [ -z "$key" ] && continue
        case "$value" in
          '"'*'"') value="${value#\"}"; value="${value%\"}" ;;
          "'"*"'") value="${value#\'}"; value="${value%\'}" ;;
        esac
        export "$key=$value"
        ;;
    esac
  done < "$f"
}

load_env_safe /etc/amg/supabase.env
load_env_safe /root/.titan-env

SUPABASE_URL="${SUPABASE_URL:-}"
SUPABASE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-}"
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
  echo "[mcp-export] FATAL: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing" >&2
  exit 3
fi

R2_BUCKET="${R2_BUCKET:-amg-storage}"
EXPORT_DIR="${EXPORT_DIR:-/opt/amg-backups/mcp-decisions}"
LOG="${LOG:-/var/log/mcp-weekly-export.log}"
TABLE="${TABLE:-op_decisions}"
PAGE_SIZE=1000
DATE_UTC=$(date -u +%Y-%m-%d)
DATE_COMPACT=$(date -u +%Y%m%dT%H%M%SZ)

DRY_RUN=0
SINCE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --since) SINCE="$2"; shift ;;
    *) echo "unknown arg: $1" >&2; exit 3 ;;
  esac
  shift
done

mkdir -p "$EXPORT_DIR"
OUT="$EXPORT_DIR/${TABLE}-${DATE_COMPACT}.ndjson"
OUT_GZ="${OUT}.gz"

log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

log "=== mcp-export start table=$TABLE date=$DATE_UTC dry_run=$DRY_RUN since=${SINCE:-all} ==="

# ----- paginated fetch -----
offset=0
total=0
> "$OUT"
while :; do
  url="$SUPABASE_URL/rest/v1/$TABLE?select=*&order=created_at.asc&limit=$PAGE_SIZE&offset=$offset"
  if [ -n "$SINCE" ]; then
    url="$url&created_at=gte.${SINCE}"
  fi
  batch=$(curl -sS "$url" \
    -H "apikey: $SUPABASE_KEY" \
    -H "Authorization: Bearer $SUPABASE_KEY" \
    -H "Accept: application/json") || {
      log "ERROR fetching offset=$offset"
      exit 1
    }
  # rows-per-batch (compact; each row on one line)
  n=$(printf '%s' "$batch" | python3 -c 'import json,sys
data=json.load(sys.stdin)
if not isinstance(data, list):
    print(0); sys.exit(0)
print(len(data))' 2>/dev/null || echo 0)
  if [ "$n" = "0" ]; then
    break
  fi
  printf '%s' "$batch" | python3 -c 'import json,sys
for row in json.load(sys.stdin):
    print(json.dumps(row, separators=(",",":")))' >> "$OUT"
  total=$((total + n))
  log "fetched batch offset=$offset n=$n total=$total"
  if [ "$n" -lt "$PAGE_SIZE" ]; then
    break
  fi
  offset=$((offset + PAGE_SIZE))
done

log "fetch complete total_rows=$total file=$OUT size=$(wc -c < "$OUT")"

if [ "$total" = "0" ]; then
  log "WARN: zero rows exported — check SINCE filter. Aborting upload."
  rm -f "$OUT"
  exit 1
fi

# ----- compress + checksum -----
gzip -9 -f "$OUT"
LOCAL_SHA=$(sha256sum "$OUT_GZ" | awk '{print $1}')
LOCAL_SIZE=$(wc -c < "$OUT_GZ")
log "compressed size=$LOCAL_SIZE sha256=$LOCAL_SHA"

if [ "$DRY_RUN" = "1" ]; then
  log "dry-run — skipping upload + verify"
  exit 0
fi

# ----- upload to R2 -----
R2_PATH="r2:${R2_BUCKET}/mcp-decisions/${DATE_UTC}/$(basename "$OUT_GZ")"
rclone copyto "$OUT_GZ" "$R2_PATH" --log-file "$LOG" --log-level INFO 2>&1 || {
  log "ERROR rclone upload failed"
  exit 1
}
log "uploaded to $R2_PATH"

# ----- verify by redownload + sha256 -----
VERIFY_DIR=$(mktemp -d)
trap 'rm -rf "$VERIFY_DIR"' EXIT
rclone copyto "$R2_PATH" "$VERIFY_DIR/verify.gz" --log-file "$LOG" --log-level INFO 2>&1 || {
  log "ERROR rclone re-download for verify failed"
  exit 1
}
REMOTE_SHA=$(sha256sum "$VERIFY_DIR/verify.gz" | awk '{print $1}')
REMOTE_SIZE=$(wc -c < "$VERIFY_DIR/verify.gz")
if [ "$LOCAL_SHA" != "$REMOTE_SHA" ] || [ "$LOCAL_SIZE" != "$REMOTE_SIZE" ]; then
  log "VERIFY FAILED: local ${LOCAL_SHA} (${LOCAL_SIZE}) != remote ${REMOTE_SHA} (${REMOTE_SIZE})"
  exit 2
fi
log "verify OK — local/remote sha256 + size match"

# ----- row-count sanity (gunzip + count lines) -----
gunzip -c "$VERIFY_DIR/verify.gz" > "$VERIFY_DIR/decoded.ndjson"
REMOTE_ROWS=$(wc -l < "$VERIFY_DIR/decoded.ndjson")
if [ "$REMOTE_ROWS" != "$total" ]; then
  log "VERIFY FAILED: local $total rows != remote $REMOTE_ROWS rows"
  exit 2
fi
log "row-count verify OK — $total rows readback confirmed"

# ----- retention: keep last 8 local files; R2 has its own versioning -----
ls -1t "$EXPORT_DIR"/${TABLE}-*.ndjson.gz 2>/dev/null | tail -n +9 | xargs -I {} rm -f {} || true

log "=== mcp-export complete total_rows=$total sha=$LOCAL_SHA size=$LOCAL_SIZE r2_path=$R2_PATH ==="
exit 0
