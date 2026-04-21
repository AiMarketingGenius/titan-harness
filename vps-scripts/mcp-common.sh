#!/bin/bash
# mcp-common.sh — CT-0419-07 shared helpers for VPS MCP integrity scripts.
# Source-only: expects callers to `source /opt/amg/scripts/mcp-common.sh`.
#
# Provides:
#   mcp_env_load                — loads SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY + SLACK_WEBHOOK_URL
#   mcp_log_decision TEXT TAGS  — POST op_decisions row (space-separated tags)
#   mcp_log_conversation_snapshot BODY PROJECT THREAD TURN_WINDOW ACTOR EXTRA_TAGS
#   mcp_flag_blocker TEXT SEV   — POST op_blockers row (sev: critical/high/medium/low)
#   mcp_slack_or_log MSG        — Slack webhook if defined, else mcp_log_decision fallback
#   mcp_search_nonce NONCE      — GET op_decisions LIKE heartbeat:NONCE, return matching count

set -u

mcp_env_load() {
  # /etc/amg/mcp-heartbeat.env is the canonical source for CT-0419-07. It's
  # populated by bin/install-mcp-integrity.sh with the correct SUPABASE_URL,
  # SUPABASE_SERVICE_ROLE_KEY, and SLACK_WEBHOOK_URL.
  #
  # Fallbacks are NOT auto-sourced because /etc/amg/slack-dispatcher.env has
  # empty-quoted SUPABASE_URL="" and SUPABASE_SERVICE_ROLE_KEY="" placeholders
  # that overwrite real values when loaded after other env files (discovered
  # 2026-04-19 during CT-0419-07 build-out).
  local primary=/etc/amg/mcp-heartbeat.env
  if [ -f "$primary" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$primary" 2>/dev/null || true
    set +a
  fi

  # Fallback: mcp-server.env has a real SUPABASE_SERVICE_ROLE_KEY if heartbeat
  # env is somehow missing it. Only consume when heartbeat env didn't supply.
  if [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ] && [ -f /etc/amg/mcp-server.env ]; then
    set -a
    # shellcheck disable=SC1091
    . /etc/amg/mcp-server.env 2>/dev/null || true
    set +a
  fi

  SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_KEY:-}}"
  SUPABASE_URL="${SUPABASE_URL:-}"
  SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-${SLACK_WEBHOOK_OPS:-}}"

  export SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY SLACK_WEBHOOK_URL
}

mcp_require_env() {
  if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
    echo "FATAL: missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY (tried /etc/amg/mcp-heartbeat.env /etc/amg/mcp-server.env /etc/amg/slack-dispatcher.env)" >&2
    return 1
  fi
}

# POST op_decisions — returns HTTP code via $?
mcp_log_decision() {
  local text="$1"
  local tags_csv="${2:-}"      # comma-separated
  local rationale="${3:-automated}"
  local project="${4:-titan}"
  mcp_require_env || return 1

  python3 - "$SUPABASE_URL" "$SUPABASE_SERVICE_ROLE_KEY" "$project" "$text" "$tags_csv" "$rationale" <<'PY'
import json, os, sys, urllib.request
url, key, project, text, tags_csv, rationale = sys.argv[1:]
tags = [t.strip() for t in tags_csv.split(",") if t.strip()]
# Column is `decision_text` (not `text`). Schema requires operator_id too.
body = json.dumps({
    "project_source": project,
    "decision_text": text,
    "rationale": rationale,
    "tags": tags,
    "operator_id": "OPERATOR_AMG",
    "decision_type": "automation",
}).encode()
req = urllib.request.Request(
    f"{url}/rest/v1/op_decisions",
    data=body,
    method="POST",
    headers={
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    },
)
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        sys.exit(0 if 200 <= r.status < 300 else 1)
except urllib.error.HTTPError as e:
    body = e.read().decode(errors="ignore")[:500]
    print(f"log_decision_fail: HTTP {e.code} {body}", file=sys.stderr)
    sys.exit(2)
except Exception as e:
    print(f"log_decision_fail: {e}", file=sys.stderr)
    sys.exit(2)
PY
}

mcp_format_conversation_snapshot() {
  local snapshot_text="$1"
  local thread_ref="${2:-unlabeled-thread}"
  local turn_window="${3:-unspecified-turn-window}"
  local actor="${4:-Achilles}"

  if [ -z "${snapshot_text//[[:space:]]/}" ]; then
    echo "FATAL: snapshot_text is empty" >&2
    return 1
  fi

  cat <<EOF
CONVERSATION SNAPSHOT
Actor: $actor
Thread: $thread_ref
Turn window: $turn_window

$snapshot_text
EOF
}

mcp_log_conversation_snapshot() {
  local snapshot_text="$1"
  local project="${2:-EOM}"
  local thread_ref="${3:-unlabeled-thread}"
  local turn_window="${4:-unspecified-turn-window}"
  local actor="${5:-Achilles}"
  local extra_tags_csv="${6:-}"
  local formatted tags_csv

  formatted="$(mcp_format_conversation_snapshot "$snapshot_text" "$thread_ref" "$turn_window" "$actor")" || return 1
  tags_csv="conversation_snapshot"
  if [ -n "$extra_tags_csv" ]; then
    tags_csv="$tags_csv,$extra_tags_csv"
  fi
  mcp_log_decision "$formatted" "$tags_csv" "10-turn conversation snapshot" "$project"
}

# Search for decisions matching a nonce substring — returns count via stdout
mcp_search_nonce() {
  local nonce="$1"
  mcp_require_env || { echo 0; return 1; }
  python3 - "$SUPABASE_URL" "$SUPABASE_SERVICE_ROLE_KEY" "$nonce" <<'PY'
import json, sys, urllib.parse, urllib.request
url, key, nonce = sys.argv[1:]
# ilike '%heartbeat:NONCE%' on decision_text column
q = urllib.parse.urlencode({
    "select": "id,decision_text,created_at",
    "decision_text": f"ilike.*heartbeat:{nonce}*",
    "order": "created_at.desc",
    "limit": "5",
})
req = urllib.request.Request(
    f"{url}/rest/v1/op_decisions?{q}",
    headers={
        "apikey": key,
        "Authorization": f"Bearer {key}",
    },
)
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        rows = json.loads(r.read())
    print(len(rows))
except Exception as e:
    print(0)
    print(f"search_fail: {e}", file=sys.stderr)
PY
}

mcp_flag_blocker() {
  local text="$1"
  local severity="${2:-high}"
  local project="${3:-EOM}"
  mcp_require_env || return 1
  python3 - "$SUPABASE_URL" "$SUPABASE_SERVICE_ROLE_KEY" "$project" "$text" "$severity" <<'PY'
import json, sys, urllib.request
url, key, project, text, severity = sys.argv[1:]
# op_blockers schema: blocker_text (not text), operator_id required
body = json.dumps({
    "project_source": project,
    "blocker_text": text,
    "severity": severity,
    "status": "open",
    "operator_id": "OPERATOR_AMG",
}).encode()
req = urllib.request.Request(
    f"{url}/rest/v1/op_blockers",
    data=body,
    method="POST",
    headers={
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    },
)
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        sys.exit(0 if 200 <= r.status < 300 else 1)
except urllib.error.HTTPError as e:
    body = e.read().decode(errors="ignore")[:500]
    print(f"flag_blocker_fail: HTTP {e.code} {body}", file=sys.stderr)
    sys.exit(2)
except Exception as e:
    print(f"flag_blocker_fail: {e}", file=sys.stderr)
    sys.exit(2)
PY
}

mcp_slack_or_log() {
  local msg="$1"
  local tags_csv="${2:-mcp-integrity,alert}"
  if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
    curl -sS -m 3 -X POST "$SLACK_WEBHOOK_URL" \
      -H 'Content-Type: application/json' \
      -d "$(python3 -c "import json,sys; print(json.dumps({'text': sys.argv[1]}))" "$msg")" \
      >/dev/null 2>&1 || true
  fi
  # MCP log is canonical regardless
  mcp_log_decision "$msg" "$tags_csv" "auto-alert from mcp-common.sh" "titan" || true
}

# Read past N log lines from a file, filter for "FAIL" count — used by heartbeat escalation.
mcp_count_recent_fails() {
  local logfile="$1"
  local lines="${2:-3}"
  [ -f "$logfile" ] || { echo 0; return; }
  tail -n "$lines" "$logfile" | grep -c "FAIL" || echo 0
}
