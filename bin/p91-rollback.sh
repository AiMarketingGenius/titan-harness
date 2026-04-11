#!/usr/bin/env bash
# bin/p91-rollback.sh — P9.1 Blue/Green cutover rollback helper.
#
# Usage:
#   p91-rollback.sh partial   # re-enable blue, keep green running
#   p91-rollback.sh full      # blue only, wipe green stack
#   p91-rollback.sh status    # show current state of blue + green
set -euo pipefail

MODE="${1:-status}"

blue_state() {
    systemctl is-active titan-queue-watcher.service 2>/dev/null || echo "inactive"
}

green_state() {
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^titan-worker-'; then
        echo "running"
    else
        echo "stopped"
    fi
}

case "$MODE" in
    status)
        echo "blue  (systemd titan-queue-watcher): $(blue_state)"
        echo "green (docker titan-compose pool):   $(green_state)"
        ;;
    partial)
        echo "[p91-rollback] partial — re-enabling blue, keeping green"
        systemctl start titan-queue-watcher.service
        sleep 2
        echo "  blue  -> $(blue_state)"
        echo "  green -> $(green_state) (unchanged)"
        ;;
    full)
        echo "[p91-rollback] full — blue only, wiping green"
        systemctl start titan-queue-watcher.service
        sleep 2
        docker compose -f /opt/titan-compose/docker-compose.yaml -p titan-compose down 2>/dev/null || true
        echo "  blue  -> $(blue_state)"
        echo "  green -> $(green_state)"
        ;;
    *)
        echo "usage: $0 {status|partial|full}" >&2
        exit 1
        ;;
esac
