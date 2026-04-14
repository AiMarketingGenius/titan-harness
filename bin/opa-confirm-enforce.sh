#!/usr/bin/env bash
# bin/opa-confirm-enforce.sh
# Gate #4 v1.2 — nonced Solon ack to flip audit → enforce.
#
# Generates a fresh 16-byte nonce per run, HMACs (report_sha + ts + operator
# + nonce + target_mode) with /etc/amg/gate4.secret, writes signed ack to
# /etc/amg/gate4-solon-ack.json. opa-deploy.sh validates + consumes.
#
# Nonce tracking: /etc/amg/gate4-ack-nonces.used (append-only).
# Replay rejected: opa-deploy.sh checks used-list before trusting ack.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRET_FILE="${GATE4_SECRET_OVERRIDE:-/etc/amg/gate4.secret}"
ACK_FILE="${GATE4_ACK_OVERRIDE:-/etc/amg/gate4-solon-ack.json}"
NONCES_USED="${GATE4_NONCES_OVERRIDE:-/etc/amg/gate4-ack-nonces.used}"

MODE_TARGET="enforce"
REPORT_PATH=""
for a in "$@"; do
    case "$a" in
        --target=audit)   MODE_TARGET="audit" ;;
        --report)         shift; REPORT_PATH="$1"; shift ;;
        -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    esac
done

[[ -f "$SECRET_FILE" ]] || { echo "opa-confirm: secret missing at $SECRET_FILE — run bin/install-gate4-opa.sh --rotate-secret" >&2; exit 2; }
[[ -z "$REPORT_PATH" || ! -f "$REPORT_PATH" ]] && { echo "opa-confirm: --report <24h-observe-report-path> required" >&2; exit 2; }

# Interactive typed confirmation
echo "========================================================================"
echo "Gate #4 enforce flip — typed confirmation required."
echo "Observe report: $REPORT_PATH"
echo "Target mode:    $MODE_TARGET"
echo "Type the following EXACTLY to proceed:"
CONFIRM_PHRASE="I have reviewed the 24h observe report and authorize Gate #4 $MODE_TARGET"
echo "    $CONFIRM_PHRASE"
read -rp "> " typed
if [[ "$typed" != "$CONFIRM_PHRASE" ]]; then
    echo "opa-confirm: confirmation phrase mismatch — ack not issued" >&2
    exit 3
fi

NONCE="$(openssl rand -hex 16)"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TS_EPOCH="$(date +%s)"
RPT_SHA="$(shasum -a 256 "$REPORT_PATH" 2>/dev/null | awk '{print $1}' || sha256sum "$REPORT_PATH" | awk '{print $1}')"

MSG="${RPT_SHA}|${TS}|solon|${NONCE}|${MODE_TARGET}"
SECRET="$(cat "$SECRET_FILE")"
MAC="$(printf '%s' "$MSG" | openssl dgst -sha256 -hmac "$SECRET" -hex | awk '{print $2}')"

python3 -c "
import json,sys
d={
  'report_sha256':sys.argv[1],
  'ts_utc':sys.argv[2],
  'ts_epoch':int(sys.argv[3]),
  'operator':'solon',
  'nonce':sys.argv[4],
  'target_mode':sys.argv[5],
  'hmac':sys.argv[6]
}
print(json.dumps(d, indent=2))
" "$RPT_SHA" "$TS" "$TS_EPOCH" "$NONCE" "$MODE_TARGET" "$MAC" > "$ACK_FILE"
chmod 0400 "$ACK_FILE" 2>/dev/null || true

# Append nonce to used-list only AFTER opa-deploy consumes it — deploy is the
# consumer that marks used. Here we just note issuance.
echo "opa-confirm: ack written to $ACK_FILE (nonce=${NONCE}, target=${MODE_TARGET})"
echo "            run bin/opa-deploy.sh --consume-ack to flip mode."
