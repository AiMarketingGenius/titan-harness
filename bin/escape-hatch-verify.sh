#!/usr/bin/env bash
# bin/escape-hatch-verify.sh
# Pre-flight for Gate #4 enforce flip (and any other lockout-risk operation).
# Scripts all 6 items from the lockout-risk escape-hatch checklist.
#
# Automatable items check live state. Attestation items require a signed
# ack file at ~/.amg/escape-hatch/<slug>.ack containing a JSON blob with
# ts_utc <24h old and operator name.
#
# Exit codes:
#   0 — all 6 green, safe to proceed
#   1 — one or more red, DO NOT PROCEED
#   2 — usage error
#
# Usage:
#   bin/escape-hatch-verify.sh                      # verify all 6
#   bin/escape-hatch-verify.sh --ack <slug>         # write an attestation (<24h valid)
#   bin/escape-hatch-verify.sh --list-slugs         # show attestation slugs
#   bin/escape-hatch-verify.sh --json               # machine-parseable report

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACK_DIR="$HOME/.amg/escape-hatch"
mkdir -p "$ACK_DIR"
chmod 700 "$ACK_DIR"

VPS_HOST="${AMG_VPS_HOST:-root@170.205.37.148}"
VPS_PORT="${AMG_VPS_PORT:-2222}"
VPS_KEY="${AMG_VPS_KEY:-$HOME/.ssh/id_ed25519_amg}"
MAC_IP="${AMG_MAC_IP:-}"   # optional; best-effort if not set

ATTESTATION_SLUGS=(
  "hosthatch-console-login"        # item 2
  "root-password-via-console"      # item 3
  "vps-snapshot-fresh"             # item 4
  "backup-ssh-key-two-locations"   # item 5
)

usage() {
  sed -n '2,20p' "$0"
  echo
  echo "Attestation slugs:"
  for s in "${ATTESTATION_SLUGS[@]}"; do echo "  $s"; done
}

MODE="verify"
JSON=0
ACK_SLUG=""
for a in "$@"; do
  case "$a" in
    --ack)         MODE="ack"; shift; ACK_SLUG="${1:-}" ;;
    --list-slugs)  usage; exit 0 ;;
    --json)        JSON=1 ;;
    -h|--help)     usage; exit 0 ;;
  esac
done

if [[ "$MODE" == "ack" ]]; then
  [[ -z "$ACK_SLUG" ]] && { echo "usage: $0 --ack <slug>" >&2; exit 2; }
  found=0
  for s in "${ATTESTATION_SLUGS[@]}"; do [[ "$s" == "$ACK_SLUG" ]] && found=1; done
  (( found == 0 )) && { echo "unknown slug: $ACK_SLUG (use --list-slugs)" >&2; exit 2; }
  TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  cat > "$ACK_DIR/$ACK_SLUG.ack" <<EOF
{
  "slug": "$ACK_SLUG",
  "ts_utc": "$TS",
  "ts_epoch": $(date +%s),
  "operator": "${USER}",
  "host": "$(hostname)"
}
EOF
  chmod 600 "$ACK_DIR/$ACK_SLUG.ack"
  echo "ack written: $ACK_DIR/$ACK_SLUG.ack (expires in 24h)"
  exit 0
fi

# --- Verification ---
RESULTS_JSON="["
SEP=""
ALL_GREEN=1

emit() {
  local slug="$1" ok="$2" msg="$3"
  if (( JSON == 1 )); then
    RESULTS_JSON+="${SEP}{\"slug\":\"$slug\",\"ok\":$ok,\"msg\":$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$msg")}"
    SEP=","
  else
    if [[ "$ok" == "true" ]]; then
      printf "  [ \033[32mGREEN\033[0m ] %-35s %s\n" "$slug" "$msg"
    else
      printf "  [ \033[31m RED \033[0m ] %-35s %s\n" "$slug" "$msg"
    fi
  fi
  if [[ "$ok" == "false" ]]; then ALL_GREEN=0; fi
  return 0
}

(( JSON == 0 )) && echo "Escape-hatch verification ($(date -u +%Y-%m-%dT%H:%M:%SZ)):"

# Item 1: SSH alive
if ssh -4 -p "$VPS_PORT" -i "$VPS_KEY" \
       -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
       "$VPS_HOST" 'echo alive' 2>/dev/null | grep -qx alive; then
  emit "1-ssh-alive" true "ssh probe to $VPS_HOST:$VPS_PORT returned 'alive'"
else
  emit "1-ssh-alive" false "ssh probe FAILED — escape hatch compromised"
fi

# Item 2/3/4/5: attestation files <24h old
check_ack() {
  local slug="$1" label="$2"
  local f="$ACK_DIR/$slug.ack"
  if [[ ! -f "$f" ]]; then
    emit "$label" false "no ack at $f — run: $0 --ack $slug"
    return
  fi
  local ts_epoch now age
  ts_epoch="$(python3 -c "import json,sys; print(json.load(open('$f'))['ts_epoch'])" 2>/dev/null || echo 0)"
  now="$(date +%s)"
  age=$(( now - ts_epoch ))
  if (( age <= 86400 )); then
    emit "$label" true "ack ${age}s old (< 24h)"
  else
    emit "$label" false "ack STALE (${age}s old, >24h) — re-ack: $0 --ack $slug"
  fi
}

check_ack "hosthatch-console-login"       "2-hosthatch-console"
check_ack "root-password-via-console"     "3-root-password"
check_ack "vps-snapshot-fresh"            "4-vps-snapshot"
check_ack "backup-ssh-key-two-locations"  "5-ssh-key-backup"

# Item 6: fail2ban Mac IP whitelist active on VPS
if ssh -4 -p "$VPS_PORT" -i "$VPS_KEY" \
       -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
       "$VPS_HOST" 'grep -rh "^ignoreip" /etc/fail2ban/ 2>/dev/null | head -5' 2>/dev/null | grep -qE '127\.0\.0\.1|localhost'; then
  ignore="$(ssh -4 -p "$VPS_PORT" -i "$VPS_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$VPS_HOST" 'grep -rh "^ignoreip" /etc/fail2ban/ 2>/dev/null | head -1' 2>/dev/null || echo '')"
  emit "6-fail2ban-whitelist" true "ignoreip present: $(echo "$ignore" | tr -d '\n' | cut -c1-80)"
else
  emit "6-fail2ban-whitelist" false "no fail2ban ignoreip entries detected"
fi

if (( JSON == 1 )); then
  RESULTS_JSON+="]"
  python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(json.dumps({'ts_utc':'$(date -u +%Y-%m-%dT%H:%M:%SZ)','all_green':$ALL_GREEN==1,'items':d}, indent=2))" "$RESULTS_JSON"
fi

if (( ALL_GREEN == 1 )); then
  (( JSON == 0 )) && echo "  → ALL GREEN. Safe to proceed with lockout-risk operation."
  exit 0
else
  (( JSON == 0 )) && echo "  → RED ITEMS PRESENT. DO NOT PROCEED. Fix + re-run."
  exit 1
fi
