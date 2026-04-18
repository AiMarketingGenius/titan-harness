#!/bin/bash
# bin/titan-steroids-start.sh — start Titan Steroids C1 via PM2 with all env
# sources loaded. Source of truth for prod lifecycle.

set -e

# Safe env loader — tolerates values containing (), spaces, special chars that
# would confuse `set -a; source`. Exports key=value verbatim without shell
# re-evaluation.
load_env_safe() {
  local f="$1"
  [ -f "$f" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|'#'*) continue ;;
      *=*)
        local key="${line%%=*}"
        local value="${line#*=}"
        # Trim surrounding whitespace on key
        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"
        [ -z "$key" ] && continue
        # Strip surrounding quotes on value if present
        case "$value" in
          '"'*'"') value="${value#\"}"; value="${value%\"}" ;;
          "'"*"'") value="${value#\'}"; value="${value%\'}" ;;
        esac
        export "$key=$value"
        ;;
    esac
  done < "$f"
}

load_env_safe /root/.titan-env
load_env_safe /etc/amg/redis-shared.env
load_env_safe /etc/amg/supabase.env

mkdir -p /var/log/titan-steroids
cd /opt/titan-steroids

case "${1:-start}" in
  start)
    pm2 start ecosystem.config.js --update-env
    pm2 save
    ;;
  stop)
    pm2 stop titan-steroids-scheduler || true
    ;;
  restart)
    pm2 restart titan-steroids-scheduler --update-env
    ;;
  once)
    node scheduler.js --once
    ;;
  enqueue)
    node scheduler.js --enqueue "$2"
    ;;
  logs)
    pm2 logs titan-steroids-scheduler --lines 50
    ;;
  status)
    pm2 describe titan-steroids-scheduler || true
    ;;
  *)
    echo "usage: $0 {start|stop|restart|once|enqueue <class_name>|logs|status}"
    exit 2
    ;;
esac
