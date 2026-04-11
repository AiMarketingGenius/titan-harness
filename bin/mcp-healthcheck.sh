#!/usr/bin/env bash
# titan-harness/bin/mcp-healthcheck.sh
#
# Unified healthcheck primitive covering the entire MCP + harness surface.
# Exit 0 = all green, non-zero = failure with description on stderr.
#
# Probes:
#   1. Capacity gate (check-capacity.sh) — must not be hard_block
#   2. harness-preflight.sh — policy validation
#   3. LiteLLM gateway /health/liveliness (127.0.0.1:4000)
#   4. MCP server /health (127.0.0.1:3000)
#   5. MCP public URL /health (https://memory.aimarketinggenius.io)
#   6. PM2 process amg-mcp-server online
#   7. n8n /healthz (https://n8n.aimarketinggenius.io)
#   8. Supabase REST reachable
#   9. Ollama /api/tags (127.0.0.1:11434)
#  10. titan-queue-watcher.service active
#
# Usage:
#   mcp-healthcheck.sh              # human-readable
#   mcp-healthcheck.sh --json       # single JSON line for parsers
#   mcp-healthcheck.sh --crit-only  # only check CRIT services (faster)
set -euo pipefail

_HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "$_HARNESS_DIR/lib/titan-env.sh" ]; then
    . "$_HARNESS_DIR/lib/titan-env.sh" >/dev/null 2>&1 || true
fi
if [ -f "$HOME/.titan-env" ]; then
    . "$HOME/.titan-env" >/dev/null 2>&1 || true
fi

FORMAT="text"
CRIT_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --json) FORMAT="json" ;;
        --crit-only) CRIT_ONLY=1 ;;
    esac
done

declare -a _PROBE_NAMES _PROBE_STATUS _PROBE_DETAIL

_probe() {
    local name="$1" status="$2" detail="$3"
    _PROBE_NAMES+=("$name")
    _PROBE_STATUS+=("$status")
    _PROBE_DETAIL+=("$detail")
}

# ---- 1. Capacity gate ------------------------------------------------------
if cap_line=$("$_HARNESS_DIR/bin/check-capacity.sh" 2>&1); then
    _probe "capacity_gate" "ok" "$cap_line"
else
    ec=$?
    if [ "$ec" -eq 1 ]; then
        _probe "capacity_gate" "warn" "soft_block: $cap_line"
    else
        _probe "capacity_gate" "crit" "hard_block: $cap_line"
    fi
fi

# ---- 2. Harness preflight --------------------------------------------------
if pf_line=$("$_HARNESS_DIR/bin/harness-preflight.sh" 2>&1 | tail -1); then
    _probe "harness_preflight" "ok" "$pf_line"
else
    _probe "harness_preflight" "crit" "${pf_line:-exit non-zero}"
fi

# ---- 3. LiteLLM gateway ----------------------------------------------------
if code=$(curl -sS -o /dev/null -w "%{http_code}" -m 5 http://127.0.0.1:4000/health/liveliness 2>/dev/null); then
    if [ "$code" = "200" ]; then
        _probe "litellm_gateway" "ok" "http 200 on :4000/health/liveliness"
    else
        _probe "litellm_gateway" "crit" "http $code on :4000/health/liveliness"
    fi
else
    _probe "litellm_gateway" "crit" "unreachable"
fi

# ---- 4. MCP server /health (local) -----------------------------------------
if body=$(curl -sS -m 5 http://127.0.0.1:3000/health 2>/dev/null); then
    case "$body" in
        *'"status":"ok"'*) _probe "mcp_local" "ok" "$(echo "$body" | head -c 120)" ;;
        *) _probe "mcp_local" "crit" "unexpected body: $(echo "$body" | head -c 80)" ;;
    esac
else
    _probe "mcp_local" "crit" "unreachable on :3000/health"
fi

# ---- 5. MCP public URL -----------------------------------------------------
if [ "$CRIT_ONLY" -eq 0 ]; then
    if body=$(curl -sS -m 5 https://memory.aimarketinggenius.io/health 2>/dev/null); then
        case "$body" in
            *'"status":"ok"'*) _probe "mcp_public" "ok" "$(echo "$body" | head -c 120)" ;;
            *) _probe "mcp_public" "warn" "unexpected body: $(echo "$body" | head -c 80)" ;;
        esac
    else
        _probe "mcp_public" "warn" "unreachable via DNS (may be local-only)"
    fi
fi

# ---- 6. PM2 amg-mcp-server -------------------------------------------------
if pm2_status=$(pm2 jlist 2>/dev/null | python3 -c "
import sys, json
try:
    procs = json.load(sys.stdin)
    for p in procs:
        if p.get('name') == 'amg-mcp-server':
            pm2_env = p.get('pm2_env', {})
            print(pm2_env.get('status','unknown'))
            break
    else:
        print('not_found')
except Exception:
    print('parse_error')
" 2>/dev/null); then
    if [ "$pm2_status" = "online" ]; then
        _probe "pm2_amg_mcp_server" "ok" "pm2 status online"
    else
        _probe "pm2_amg_mcp_server" "crit" "pm2 status $pm2_status"
    fi
else
    _probe "pm2_amg_mcp_server" "warn" "pm2 jlist unavailable"
fi

# ---- 7. n8n /healthz -------------------------------------------------------
if [ "$CRIT_ONLY" -eq 0 ]; then
    if code=$(curl -sS -o /dev/null -w "%{http_code}" -m 5 https://n8n.aimarketinggenius.io/healthz 2>/dev/null); then
        if [ "$code" = "200" ]; then
            _probe "n8n_public" "ok" "http 200 /healthz"
        else
            _probe "n8n_public" "warn" "http $code /healthz"
        fi
    else
        _probe "n8n_public" "warn" "unreachable"
    fi
fi

# ---- 8. Supabase REST reachable --------------------------------------------
if [ -n "${SUPABASE_URL:-}" ] && [ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
    if code=$(curl -sS -o /dev/null -w "%{http_code}" -m 5 \
        -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
        "$SUPABASE_URL/rest/v1/" 2>/dev/null); then
        if [ "$code" = "200" ] || [ "$code" = "401" ]; then
            _probe "supabase_rest" "ok" "http $code"
        else
            _probe "supabase_rest" "crit" "http $code"
        fi
    else
        _probe "supabase_rest" "crit" "unreachable"
    fi
else
    _probe "supabase_rest" "warn" "env missing"
fi

# ---- 9. Ollama -------------------------------------------------------------
if [ "$CRIT_ONLY" -eq 0 ]; then
    if code=$(curl -sS -o /dev/null -w "%{http_code}" -m 5 http://127.0.0.1:11434/api/tags 2>/dev/null); then
        if [ "$code" = "200" ]; then
            _probe "ollama" "ok" "http 200 /api/tags"
        else
            _probe "ollama" "warn" "http $code"
        fi
    else
        _probe "ollama" "warn" "unreachable"
    fi
fi

# ---- 10. titan-queue-watcher -----------------------------------------------
if qstatus=$(systemctl is-active titan-queue-watcher.service 2>/dev/null); then
    if [ "$qstatus" = "active" ]; then
        _probe "titan_queue_watcher" "ok" "systemd active"
    else
        _probe "titan_queue_watcher" "crit" "systemd $qstatus"
    fi
else
    _probe "titan_queue_watcher" "warn" "systemctl unavailable"
fi

# ---- Render ----------------------------------------------------------------
overall="ok"
for s in "${_PROBE_STATUS[@]}"; do
    if [ "$s" = "crit" ]; then overall="crit"; break; fi
    if [ "$s" = "warn" ] && [ "$overall" = "ok" ]; then overall="warn"; fi
done

if [ "$FORMAT" = "json" ]; then
    printf '{"overall":"%s","probes":[' "$overall"
    for i in "${!_PROBE_NAMES[@]}"; do
        [ "$i" -gt 0 ] && printf ','
        printf '{"name":"%s","status":"%s","detail":"%s"}' \
            "${_PROBE_NAMES[$i]}" "${_PROBE_STATUS[$i]}" \
            "$(echo "${_PROBE_DETAIL[$i]}" | sed 's/"/\\"/g' | tr -d '\n' | head -c 300)"
    done
    printf ']}\n'
else
    printf '%-24s %-6s %s\n' "PROBE" "STATUS" "DETAIL"
    printf '%-24s %-6s %s\n' "------" "------" "------"
    for i in "${!_PROBE_NAMES[@]}"; do
        printf '%-24s %-6s %s\n' "${_PROBE_NAMES[$i]}" "${_PROBE_STATUS[$i]}" \
            "$(echo "${_PROBE_DETAIL[$i]}" | head -c 200)"
    done
    echo ""
    echo "OVERALL: $overall"
fi

case "$overall" in
    ok)   exit 0 ;;
    warn) exit 1 ;;
    crit) exit 2 ;;
esac
