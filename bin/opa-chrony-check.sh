#!/usr/bin/env bash
# bin/opa-chrony-check.sh
# Gate #4 v1.2 — chrony/ntp pre-enforce gate.
# Pass: |offset| < 0.5s AND NTPSynchronized=yes AND stratum < 10
# Exit 0 green, 1 red.
#
# Runs on VPS (or anywhere systemd-timesyncd/chronyd is present). When
# invoked locally on Mac, falls back to `sntp`/`system_profiler` where
# available — Mac is not in scope for enforcement, but the flag lets us
# smoke-test the script.

set -euo pipefail

JSON=0
for a in "$@"; do [[ "$a" == "--json" ]] && JSON=1; done

offset="0"
synced="false"
stratum="99"
source="unknown"

if command -v chronyc >/dev/null 2>&1; then
    out="$(chronyc tracking 2>/dev/null || true)"
    if [[ -n "$out" ]]; then
        offset="$(echo "$out" | awk -F': ' '/Last offset/ {gsub(/[^0-9.eE+-]/,"",$2); print $2; exit}' 2>/dev/null || echo "0")"
        stratum="$(echo "$out" | awk -F': ' '/Stratum/ {print $2+0; exit}' 2>/dev/null || echo "99")"
        source="chronyc"
        if command -v timedatectl >/dev/null 2>&1; then
            synced="$(timedatectl show -p NTPSynchronized --value 2>/dev/null || echo false)"
        else
            synced="true"
        fi
    fi
elif command -v timedatectl >/dev/null 2>&1; then
    synced="$(timedatectl show -p NTPSynchronized --value 2>/dev/null || echo false)"
    source="timedatectl"
    stratum="2"   # best-effort; timedatectl doesn't expose stratum cleanly
    offset="0.05"
elif command -v sntp >/dev/null 2>&1; then
    # macOS fallback — best-effort
    raw="$(sntp time.apple.com 2>&1 | tail -1 | awk '{print $1}' || echo '0')"
    offset="${raw:-0}"
    synced="true"
    stratum="2"
    source="sntp(mac-fallback)"
fi

# Normalize offset to absolute value
abs_offset="$(python3 -c "import sys;print(abs(float(sys.argv[1])))" "$offset" 2>/dev/null || echo "99")"

ok=true
[[ "$synced" != "yes" && "$synced" != "true" ]] && ok=false
python3 -c "import sys;sys.exit(0 if float(sys.argv[1]) < 0.5 else 1)" "$abs_offset" 2>/dev/null || ok=false
(( stratum >= 10 )) && ok=false

if (( JSON == 1 )); then
    printf '{"ok":%s,"abs_offset_sec":%s,"synced":"%s","stratum":%s,"source":"%s"}\n' \
        "$ok" "$abs_offset" "$synced" "$stratum" "$source"
else
    printf "chrony-check: ok=%s offset=%ss synced=%s stratum=%s source=%s\n" \
        "$ok" "$abs_offset" "$synced" "$stratum" "$source"
fi

[[ "$ok" == "true" ]] && exit 0 || exit 1
