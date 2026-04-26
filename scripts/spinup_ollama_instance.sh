#!/usr/bin/env bash
# spinup_ollama_instance.sh — placeholder scaffold for multi-node Ollama scaling.
#
# Purpose: when monitor_and_scale.py detects sustained queue overload that API
# fallback alone can't absorb, this script can spin up an additional Ollama
# container alongside the primary on the VPS to add lane capacity.
#
# Status: NOT WIRED INTO RUNTIME. This is a documented placeholder so the
# scaling-architecture intent is captured + a future operator can flesh it out
# without re-deriving the design.

set -euo pipefail

# ─── Config (env-overridable) ────────────────────────────────────────────────
VPS_HOST="${VPS_HOST:-amg-staging}"
INSTANCE_NUM="${INSTANCE_NUM:-2}"  # which secondary; primary = 1 implicit
INSTANCE_PORT="$((11434 + INSTANCE_NUM - 1))"
INSTANCE_NAME="ollama-${INSTANCE_NUM}"
MODEL_TO_PULL="${MODEL_TO_PULL:-qwen2.5:32b}"

usage() {
    cat <<EOF
Usage: $0 [start|stop|status|pull-model]

Subcommands:
  start        Launch a new Ollama container on $VPS_HOST at port $INSTANCE_PORT
  stop         Stop + remove the container
  status       Show container state + model list
  pull-model   Pull \$MODEL_TO_PULL into the container

Environment:
  VPS_HOST          (default: amg-staging)
  INSTANCE_NUM      (default: 2)
  MODEL_TO_PULL     (default: qwen2.5:32b)

NOTE: This is a placeholder. Production scaling needs:
  - Docker installed on the VPS (verify before launch)
  - Persistent model volume mount across restarts
  - Reverse proxy / load balancer entry per instance (currently absent)
  - aliases.json updated with the new endpoint after each spinup
EOF
}

require_ssh() {
    if ! ssh -o ConnectTimeout=5 "$VPS_HOST" 'true' >/dev/null 2>&1; then
        echo "ERROR: cannot reach $VPS_HOST via ssh" >&2
        exit 1
    fi
}

cmd_start() {
    require_ssh
    echo "[spinup] launching $INSTANCE_NAME at port $INSTANCE_PORT on $VPS_HOST"
    ssh "$VPS_HOST" "docker run -d \
        --name $INSTANCE_NAME \
        --restart unless-stopped \
        -p $INSTANCE_PORT:11434 \
        -v ${INSTANCE_NAME}-models:/root/.ollama \
        ollama/ollama:latest"
    echo "[spinup] $INSTANCE_NAME started; pull model with: $0 pull-model"
}

cmd_stop() {
    require_ssh
    echo "[spinup] stopping $INSTANCE_NAME"
    ssh "$VPS_HOST" "docker stop $INSTANCE_NAME 2>/dev/null || true; \
                     docker rm $INSTANCE_NAME 2>/dev/null || true"
    echo "[spinup] $INSTANCE_NAME stopped + removed (volume preserved)"
}

cmd_status() {
    require_ssh
    ssh "$VPS_HOST" "docker ps -f name=^${INSTANCE_NAME}\$ --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
    echo "---"
    ssh "$VPS_HOST" "curl -sS http://127.0.0.1:$INSTANCE_PORT/api/tags 2>/dev/null | head -200"
}

cmd_pull_model() {
    require_ssh
    echo "[spinup] pulling $MODEL_TO_PULL into $INSTANCE_NAME (port $INSTANCE_PORT)"
    ssh "$VPS_HOST" "curl -sS http://127.0.0.1:$INSTANCE_PORT/api/pull -d '{\"name\":\"$MODEL_TO_PULL\"}' | tail -10"
}

case "${1:-help}" in
    start)      cmd_start ;;
    stop)       cmd_stop ;;
    status)     cmd_status ;;
    pull-model) cmd_pull_model ;;
    help|*)     usage; exit 0 ;;
esac
