#!/usr/bin/env bash
# bin/titan-kokoro-healthcheck.sh
# Hermes Phase A Step 9 — minute-by-minute Kokoro health probe.
# Logs JSONL to /var/log/titan/kokoro-health.jsonl.
# Alerts via lib/war_room.py notification path if 3 consecutive probes fail.
# Invoked by titan-kokoro-health.timer.

set -euo pipefail

LOG_DIR=/var/log/titan
LOG_FILE="$LOG_DIR/kokoro-health.jsonl"
STATE_FILE=/run/titan-kokoro-health.state
ENDPOINT="http://127.0.0.1:8880/health"
ALERT_THRESHOLD=3

mkdir -p "$LOG_DIR"
touch "$LOG_FILE"

timestamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

http_code=0
time_total="n/a"
err=""
if response=$(curl -sf -o /dev/null -w '%{http_code} %{time_total}' \
              --connect-timeout 3 --max-time 8 "$ENDPOINT" 2>/dev/null); then
  http_code=$(awk '{print $1}' <<<"$response")
  time_total=$(awk '{print $2}' <<<"$response")
  status="ok"
else
  http_code=$(awk '{print $1}' <<<"${response:-0}" 2>/dev/null || echo 0)
  status="fail"
  err=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 3 --max-time 8 "$ENDPOINT" 2>&1 || true)
fi

# Track consecutive failures
consecutive_fail=0
if [[ -f "$STATE_FILE" ]]; then
  consecutive_fail=$(cat "$STATE_FILE" 2>/dev/null || echo 0)
fi
if [[ "$status" == "ok" ]]; then
  consecutive_fail=0
else
  consecutive_fail=$((consecutive_fail + 1))
fi
echo "$consecutive_fail" > "$STATE_FILE"

# Append JSONL line
printf '{"ts":"%s","service":"titan-kokoro","status":"%s","http_code":"%s","time_total_s":"%s","consecutive_fail":%d,"err":"%s"}\n' \
  "$(timestamp)" "$status" "$http_code" "$time_total" "$consecutive_fail" "$err" \
  >> "$LOG_FILE"

# Rotate if file exceeds 5 MB (keep last 1 MB)
if [[ -f "$LOG_FILE" ]] && (( $(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) > 5242880 )); then
  tail -c 1048576 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi

# Alert on threshold crossed
if (( consecutive_fail >= ALERT_THRESHOLD )); then
  alert_msg="titan-kokoro health probe failed ${consecutive_fail}x consecutively (http=${http_code}, err=${err})"
  # Best-effort notification path; do not fail the healthcheck if the alert path fails.
  python3 - <<PY 2>/dev/null || true
import sys
sys.path.insert(0, "/opt/titan-harness")
try:
    from lib.war_room import notify  # existing notification helper, if present
    notify("kokoro-health-alert", "${alert_msg}")
except Exception:
    pass
PY
  # Also write a sentinel line that a future poller can tail.
  printf '{"ts":"%s","service":"titan-kokoro","alert":"consecutive_fail_threshold","consecutive_fail":%d}\n' \
    "$(timestamp)" "$consecutive_fail" >> "$LOG_FILE"
fi

# Exit 0 on ok, 1 on fail (systemd timer will not retry — we just log)
[[ "$status" == "ok" ]]
