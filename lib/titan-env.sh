#!/bin/bash
# titan-env.sh — shared env + OS detection for titan-harness hooks
# Sourced by every hook script.

# OS detection
case "$(uname -s)" in
  Darwin*) TITAN_OS=macos ;;
  Linux*)  TITAN_OS=linux ;;
  *)       TITAN_OS=unknown ;;
esac

# Instance name — override via TITAN_INSTANCE env var, else derive from hostname
TITAN_INSTANCE="${TITAN_INSTANCE:-$(hostname -s 2>/dev/null || hostname)}"

# Session dir (local cache only — source of truth is Supabase)
if [ -z "${TITAN_SESSION_DIR:-}" ]; then
  if [ "$TITAN_OS" = "linux" ] && [ -d /opt/titan-session ]; then
    TITAN_SESSION_DIR=/opt/titan-session
  else
    TITAN_SESSION_DIR="$HOME/titan-session"
  fi
fi
mkdir -p "$TITAN_SESSION_DIR"

# Supabase creds — try multiple locations in order
_load_env_file() {
  local f="$1"
  [ -f "$f" ] && set -a && source "$f" 2>/dev/null && set +a
}
_load_env_file "$HOME/.titan-env"
_load_env_file "/opt/amg-titan/.env"
_load_env_file "$HOME/.config/titan/env"

# Normalize the key variable name
SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_KEY:-}}"
export SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY TITAN_INSTANCE TITAN_SESSION_DIR TITAN_OS

# Utility: write to local audit log
titan_local_audit() {
  local msg="$1"
  local ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  echo "$ts | $TITAN_INSTANCE | $msg" >> "$TITAN_SESSION_DIR/audit.log"
}

# Utility: POST to Supabase (fail-safe async)
titan_supabase_post() {
  local table="$1"
  local body="$2"
  if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    (
      curl -s -m 3 -X POST "$SUPABASE_URL/rest/v1/$table" \
        -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
        -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
        -H "Content-Type: application/json" \
        -H "Prefer: return=minimal" \
        -d "$body" > /dev/null 2>&1
    ) &
  fi
}
