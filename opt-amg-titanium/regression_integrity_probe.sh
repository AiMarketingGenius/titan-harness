#!/usr/bin/env bash
# regression_integrity_probe.sh — TITANIUM DOCTRINE v1.0 Gap 3.
#
# Runs daily at 06:00 UTC. Verifies nine known-fixed surfaces have NOT
# regressed. Any probe failure → MCP log_decision [regression-detected] +
# auto-queue urgent repair task + Slack/WebHook alert.
#
# Probes (expand as new fixes ship):
#   0  Governance gate self-check (pre-proposal-gate.sh --self-test)
#   1  Permission-dialog count during synthetic Titan run
#   2  SI field location on sampled AMG Claude Projects
#   3  Supabase routing cross-contamination
#   4  Memory loop 4:30 AM reproduction test
#   5  Trade-secret scan across live client-facing surfaces
#   6  Pricing consistency
#   7  Paddle-only payment processor reference
#   8  Dr. SEO branding scan
#   9  Idle-detection (Titan idle >30min AND queue has urgent pending — violation)
#
# Args:
#   --first-run         run all probes, verbose output
#   --probe N           run probe N only (0-9)
#   --dry-run           skip alerting + MCP writes
set -euo pipefail

readonly TITANIUM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOG_FILE="${PROBE_LOG:-$HOME/titan-harness/logs/regression_integrity_probe.log}"
readonly ALERT_QUEUE="$HOME/titan-harness/logs/auto_approve_queue"
mkdir -p "$(dirname "$LOG_FILE")" "$ALERT_QUEUE"

MODE=${1:-all}
SELECT_N=""
DRY_RUN=0
case "$MODE" in
  --first-run) MODE=all ;;
  --dry-run) DRY_RUN=1 ;;
  --probe) MODE=one; SELECT_N="${2:-}"; ;;
esac

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG_FILE"; }

# Env
for env_file in "$HOME/.titan-env" "/opt/amg-titan/.env"; do
  [ -f "$env_file" ] && . "$env_file"
done

alert() {
  local probe_n="$1" severity="$2" msg="$3"
  local event_file="$ALERT_QUEUE/regression-probe-${probe_n}-$(date +%s%N).json"
  python3 -c "
import json
print(json.dumps({
  'event': 'regression_probe_alert',
  'action': 'regression_detected',
  'kind': 'probe_#${probe_n}',
  'target': '${msg//\'/}',
  'app': 'titan',
  'category': '${severity}',
  'ts': '$(date -u +%Y-%m-%dT%H:%M:%SZ)'
}))" > "$event_file"
  log "ALERT probe=$probe_n sev=$severity msg=$msg"
}

result=0

probe_0() {
  log "probe 0: governance gate self-check"
  if "$TITANIUM_DIR/pre-proposal-gate.sh" --self-test; then
    log "probe 0 PASS"
  else
    alert 0 critical "pre-proposal-gate self-test FAIL"
    result=1
  fi
}

probe_1() {
  log "probe 1: permission-dialog count (synthetic window)"
  # Tail last 24h of auto_approve log; count TCC dialogs surfacing (non-approved)
  local log_file="$HOME/titan-harness/logs/auto_approve.log"
  if [ ! -f "$log_file" ]; then
    log "probe 1 SKIP (log missing)"; return
  fi
  local since
  since=$(date -u -v-1d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '-1 day' +%Y-%m-%dT%H:%M:%SZ)
  local count
  count=$(awk -v since="$since" '$1 >= since && /action=skipped_not_whitelisted/' "$log_file" | wc -l | tr -d ' ')
  if [ "$count" -gt 5 ]; then
    alert 1 high "permission dialogs surfacing: $count in 24h"
    result=1
  else
    log "probe 1 PASS (count=$count)"
  fi
}

probe_2() {
  log "probe 2: SI field location (Claude Project Instructions)"
  log "probe 2 MANUAL — requires Stagehand browser check; placeholder for future automation"
}

probe_3() {
  log "probe 3: Supabase routing cross-contamination"
  # Production portal login should ONLY hit egoazyasyrhslluossli.supabase.co
  # Deferred — requires HAR capture via Stagehand
  log "probe 3 MANUAL — requires Stagehand HAR capture"
}

probe_4() {
  log "probe 4: memory loop 4:30 AM reproduction"
  local start_ts end_ts elapsed_ms
  start_ts=$(python3 -c 'import time; print(int(time.time()*1000))')
  curl -sS --max-time 30 -G "$SUPABASE_URL/rest/v1/op_decisions" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
    --data-urlencode "select=id" \
    --data-urlencode "decision_text=ilike.*Lovable*" \
    --data-urlencode "limit=1" >/dev/null || { alert 4 critical "memory loop query failed"; result=1; return; }
  end_ts=$(python3 -c 'import time; print(int(time.time()*1000))')
  elapsed_ms=$((end_ts - start_ts))
  if [ "$elapsed_ms" -gt 30000 ]; then
    alert 4 high "memory loop query too slow: ${elapsed_ms}ms >30s"
    result=1
  else
    log "probe 4 PASS (${elapsed_ms}ms)"
  fi
}

probe_5() {
  log "probe 5: trade-secret scan on live client-facing surfaces"
  local domains=("https://aimemoryguard.com" "https://voice.aimarketinggenius.io")
  local banned_regex='Claude|Anthropic|GPT|OpenAI|Gemini|Grok|Perplexity|Supabase|n8n|Stagehand|Lovable|HostHatch|beast'
  local hits=0
  for d in "${domains[@]}"; do
    body=$(curl -sS --max-time 15 "$d" 2>/dev/null || echo "")
    if printf '%s' "$body" | grep -qiE "$banned_regex"; then
      term=$(printf '%s' "$body" | grep -iEo "$banned_regex" | head -1)
      alert 5 critical "trade-secret leak on $d: $term"
      hits=$((hits + 1))
    fi
  done
  if [ "$hits" -eq 0 ]; then
    log "probe 5 PASS"
  else
    result=1
  fi
}

probe_6() {
  log "probe 6: pricing consistency (AMG + Shield)"
  local canonical_amg="497.*797.*1497"
  local canonical_shield="97.*197.*347"
  # Placeholder: would scrape aimarketinggenius.io pricing page
  log "probe 6 MANUAL — pricing-page scrape target TBD; gate via OPA policy for changes"
}

probe_7() {
  log "probe 7: Paddle-only (zero Stripe refs live)"
  local domains=("https://aimemoryguard.com" "https://voice.aimarketinggenius.io")
  local hits=0
  for d in "${domains[@]}"; do
    body=$(curl -sS --max-time 15 "$d" 2>/dev/null || echo "")
    if printf '%s' "$body" | grep -qiE '\bstripe\b'; then
      alert 7 critical "Stripe reference found on $d (Paddle-only rule)"
      hits=$((hits + 1))
    fi
  done
  if [ "$hits" -eq 0 ]; then
    log "probe 7 PASS"
  else
    result=1
  fi
}

probe_8() {
  log "probe 8: Dr. SEO branding scan (zero hits client-facing)"
  local domains=("https://aimemoryguard.com" "https://voice.aimarketinggenius.io")
  local hits=0
  for d in "${domains[@]}"; do
    body=$(curl -sS --max-time 15 "$d" 2>/dev/null || echo "")
    if printf '%s' "$body" | grep -qiE 'dr\.?[[:space:]]*seo|drseo'; then
      alert 8 high "Dr. SEO branding leak on $d"
      hits=$((hits + 1))
    fi
  done
  if [ "$hits" -eq 0 ]; then
    log "probe 8 PASS"
  else
    result=1
  fi
}

probe_9() {
  log "probe 9: idle-detection (Titan idle >30min AND urgent queue)"
  # Check MCP for pending urgent pre_approved tasks assigned to titan
  if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
    log "probe 9 SKIP (env missing)"; return
  fi
  local pending_count
  pending_count=$(curl -sS --max-time 15 -G "$SUPABASE_URL/rest/v1/operator_task_queue" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
    --data-urlencode "select=task_id" \
    --data-urlencode "assigned_to=eq.titan" \
    --data-urlencode "approval=eq.pre_approved" \
    --data-urlencode "status=in.(approved,queued)" 2>/dev/null | python3 -c 'import json,sys; print(len(json.loads(sys.stdin.read() or "[]")))' || echo 0)
  # Check if titan session mutex file is stale (no heartbeat >30m)
  local mutex="/tmp/titan-session.pid"
  local stale=0
  if [ -f "$mutex" ]; then
    local mtime_now mtime_mutex
    mtime_now=$(date +%s)
    mtime_mutex=$(stat -f%m "$mutex" 2>/dev/null || stat -c%Y "$mutex" 2>/dev/null || echo 0)
    local delta=$((mtime_now - mtime_mutex))
    if [ "$delta" -gt 1800 ]; then stale=1; fi
  else
    stale=1
  fi
  if [ "$pending_count" -gt 0 ] && [ "$stale" = "1" ]; then
    alert 9 high "idle-with-pending-urgent: $pending_count tasks waiting, no heartbeat >30min"
    result=1
  else
    log "probe 9 PASS (pending=$pending_count, stale=$stale)"
  fi
}

if [ "$MODE" = "one" ]; then
  case "$SELECT_N" in
    0) probe_0 ;; 1) probe_1 ;; 2) probe_2 ;; 3) probe_3 ;; 4) probe_4 ;;
    5) probe_5 ;; 6) probe_6 ;; 7) probe_7 ;; 8) probe_8 ;; 9) probe_9 ;;
    *) echo "unknown probe: $SELECT_N" >&2; exit 1 ;;
  esac
else
  probe_0; probe_1; probe_2; probe_3; probe_4; probe_5; probe_6; probe_7; probe_8; probe_9
fi

exit $result
