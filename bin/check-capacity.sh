#!/usr/bin/env bash
# titan-harness/bin/check-capacity.sh — Phase G.5
# CPU/RAM guardrail gate. Exit codes:
#   0 — ok, safe to launch heavy work
#   1 — soft block: no new heavy workflows, light tasks only
#   2 — hard block: do NOT start any new heavy work
#
# Reads POLICY_CAPACITY_* env vars; sources lib/titan-env.sh if they are unset.

_HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -z "${POLICY_CAPACITY_CPU_SOFT_PCT:-}" ] && [ -f "$_HARNESS_DIR/lib/titan-env.sh" ]; then
  # shellcheck source=../lib/titan-env.sh
  . "$_HARNESS_DIR/lib/titan-env.sh" >/dev/null 2>&1 || true
fi

soft_cpu="${POLICY_CAPACITY_CPU_SOFT_PCT:-80}"
hard_cpu="${POLICY_CAPACITY_CPU_HARD_PCT:-90}"
soft_ram="${POLICY_CAPACITY_RAM_SOFT_GIB:-50}"
hard_ram="${POLICY_CAPACITY_RAM_HARD_GIB:-56}"

# CPU: 1-minute loadavg as percent of total cores (capped at 999)
cores=$(nproc 2>/dev/null || echo 1)
load_1=$(awk '{print $1}' /proc/loadavg 2>/dev/null || echo 0)
cpu_percent=$(awk -v l="$load_1" -v c="$cores" 'BEGIN{ p=(l/c)*100; if(p>999)p=999; printf "%d", p }')

# RAM: used GiB from MemTotal-MemAvailable
total_kb=$(awk '/MemTotal/ {print $2; exit}' /proc/meminfo)
avail_kb=$(awk '/MemAvailable/ {print $2; exit}' /proc/meminfo)
used_gib=$(awk -v t="$total_kb" -v a="$avail_kb" 'BEGIN{ printf "%d", (t-a)/1024/1024 }')

status="ok"
reason=""
if [ "$cpu_percent" -ge "$hard_cpu" ] || [ "$used_gib" -ge "$hard_ram" ]; then
  status="hard_block"
  reason="CPU=${cpu_percent}%>=${hard_cpu}% OR RAM=${used_gib}GiB>=${hard_ram}GiB"
elif [ "$cpu_percent" -ge "$soft_cpu" ] || [ "$used_gib" -ge "$soft_ram" ]; then
  status="soft_block"
  reason="CPU=${cpu_percent}%>=${soft_cpu}% OR RAM=${used_gib}GiB>=${soft_ram}GiB"
fi

printf "status=%s cpu=%s%% ram=%sGiB cores=%s soft=%s/%s hard=%s/%s reason=%s\n" \
  "$status" "$cpu_percent" "$used_gib" "$cores" "$soft_cpu" "$soft_ram" "$hard_cpu" "$hard_ram" "$reason"

case "$status" in
  hard_block) exit 2 ;;
  soft_block) exit 1 ;;
  *)          exit 0 ;;
esac
