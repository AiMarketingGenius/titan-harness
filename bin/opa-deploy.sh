#!/usr/bin/env bash
# bin/opa-deploy.sh
# Gate #4 v1.2 — mode flipper with all pre-flight gates.
#
# Phases:
#   --phase1-audit            Install audit mode (24h window begins)
#   --generate-observe-report Emit 24h summary to stdout/path
#   --consume-ack             Validate signed+nonced ack + escape-hatch + chrony
#                             → flip to enforce for 7d
#   --revert                  Manual revert to audit

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE_FILE="/etc/amg/opa-mode"
AUDIT_START="/etc/amg/opa-audit-start.ts"
ENFORCE_START="/etc/amg/opa-enforce-start.ts"
SOLON_ACK="/etc/amg/gate4-solon-ack.json"
NONCES_USED="/etc/amg/gate4-ack-nonces.used"
SECRET_FILE="/etc/amg/gate4.secret"
DECISIONS_LOG="/var/log/amg/opa-decisions.jsonl"
MODE_CHANGES_LOG="/var/log/amg/opa-mode-changes.jsonl"

mode_write() {
    local target="$1" reason="$2"
    mkdir -p /etc/amg /var/log/amg 2>/dev/null || true
    echo -n "$target" > "$MODE_FILE"
    chmod 0444 "$MODE_FILE" 2>/dev/null || true
    python3 -c "
import json, sys, time
print(json.dumps({'ts':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  'new_mode':sys.argv[1],'reason':sys.argv[2]}))
" "$target" "$reason" >> "$MODE_CHANGES_LOG" 2>/dev/null || true
}

case "${1:-}" in
    --phase1-audit)
        "${REPO}/bin/test-policies.sh" || { echo "opa-deploy: rego tests failed — refusing to deploy" >&2; exit 4; }
        mode_write "audit" "phase1-audit"
        date +%s > "$AUDIT_START"
        echo "opa-deploy: AUDIT mode active. Observe for 24h then run --generate-observe-report."
        ;;

    --generate-observe-report)
        OUT="${2:-/tmp/opa-observe-report-$(date +%Y%m%d-%H%M).json}"
        python3 - > "$OUT" <<PY
import json, os, collections
log = "$DECISIONS_LOG"
by_mode = collections.Counter()
would_deny = 0
total = 0
samples = []
if os.path.exists(log):
    with open(log) as f:
        for raw in f:
            try: d = json.loads(raw)
            except Exception: continue
            total += 1
            by_mode[d.get("mode","?")] += 1
            if str(d.get("allow")).strip().lower() != "true":
                would_deny += 1
                if len(samples) < 20: samples.append(d)
print(json.dumps({
  "total_decisions": total,
  "by_mode": dict(by_mode),
  "would_deny_count": would_deny,
  "would_deny_samples": samples,
}, indent=2))
PY
        echo "opa-deploy: report at $OUT"
        ;;

    --consume-ack)
        [[ -f "$SOLON_ACK" ]] || { echo "opa-deploy: no ack at $SOLON_ACK — run bin/opa-confirm-enforce.sh first" >&2; exit 5; }
        [[ -f "$SECRET_FILE" ]] || { echo "opa-deploy: missing $SECRET_FILE" >&2; exit 5; }

        # Validate HMAC
        python3 - <<PY || { echo "opa-deploy: ack HMAC invalid" >&2; exit 6; }
import hmac, hashlib, json, sys
ack = json.load(open("$SOLON_ACK"))
sec = open("$SECRET_FILE","rb").read().strip()
msg = f"{ack['report_sha256']}|{ack['ts_utc']}|{ack['operator']}|{ack['nonce']}|{ack['target_mode']}".encode()
expected = hmac.new(sec, msg, hashlib.sha256).hexdigest()
sys.exit(0 if hmac.compare_digest(expected, ack['hmac']) else 1)
PY

        # Replay check
        NONCE="$(python3 -c "import json; print(json.load(open('$SOLON_ACK'))['nonce'])")"
        if [[ -f "$NONCES_USED" ]] && grep -qxF "$NONCE" "$NONCES_USED"; then
            echo "opa-deploy: REPLAY DETECTED — nonce already consumed" >&2
            exit 7
        fi

        # Freshness (<1h old)
        ACK_EPOCH="$(python3 -c "import json;print(json.load(open('$SOLON_ACK'))['ts_epoch'])")"
        AGE=$(( $(date +%s) - ACK_EPOCH ))
        (( AGE > 3600 )) && { echo "opa-deploy: ack stale (age=${AGE}s)" >&2; exit 8; }

        # Pre-enforce gates
        "${REPO}/bin/escape-hatch-verify.sh" --json > /tmp/eh.json || true
        GREEN="$(python3 -c "import json;print(json.load(open('/tmp/eh.json')).get('all_green', False))")"
        [[ "$GREEN" == "True" ]] || { echo "opa-deploy: escape-hatch RED — refusing to flip" >&2; exit 9; }

        "${REPO}/bin/opa-chrony-check.sh" || { echo "opa-deploy: chrony RED — refusing to flip" >&2; exit 10; }

        # Consume nonce + flip
        mkdir -p /etc/amg
        echo "$NONCE" >> "$NONCES_USED"
        date +%s > "$ENFORCE_START"
        TARGET="$(python3 -c "import json;print(json.load(open('$SOLON_ACK'))['target_mode'])")"
        mode_write "$TARGET" "consume-ack-nonce-${NONCE}"
        echo "opa-deploy: flipped to $TARGET (7d observe-tail armed; auto-revert timer active)"
        ;;

    --revert)
        mode_write "audit" "manual-revert"
        rm -f "$ENFORCE_START"
        echo "opa-deploy: reverted to AUDIT"
        ;;

    *)
        sed -n '2,14p' "$0"
        exit 2
        ;;
esac
