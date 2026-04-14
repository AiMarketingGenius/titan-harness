#!/bin/bash
# DR-AMG-SECURITY-01 Phase 3 Task 3.2 — Automated Credential Rotation
# Usage: rotate-credential.sh --key-id <id> | --check-ages
set -euo pipefail

REGISTRY="/opt/amg-security/credential-registry.json"
LOG="/var/log/amg-security/rotations.jsonl"

log() { echo "{\"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"action\": \"$1\", \"key_id\": \"${2:-}\", \"result\": \"$3\"}" | tee -a "$LOG"; }

rotate_key() {
    local KEY_ID="$1"

    # Validate key exists and is auto_rotate_allowed
    if ! python3 -c "
import json, sys
with open('$REGISTRY') as f:
    reg = json.load(f)
for c in reg.get('credentials', []):
    if c['id'] == '$KEY_ID':
        if not c.get('auto_rotate_allowed', False):
            print('NOT_ALLOWED', file=sys.stderr)
            sys.exit(1)
        print(c.get('provider', 'unknown'))
        sys.exit(0)
print('NOT_FOUND', file=sys.stderr)
sys.exit(1)
" 2>/dev/null; then
        log "rotate" "$KEY_ID" "DENIED: not found or auto_rotate_allowed=false"
        exit 1
    fi

    log "rotate_start" "$KEY_ID" "starting"

    # Provider-specific rotation would go here
    # For now, log the intent and defer actual API calls to operator
    log "rotate" "$KEY_ID" "DEFERRED: manual rotation required — run provider API manually"
    echo "Rotation for $KEY_ID: generate new key via provider, smoke-test, update n8n, wait 60s, re-test, revoke old."
}

check_ages() {
    if [ ! -f "$REGISTRY" ]; then
        echo "Registry not found at $REGISTRY"
        exit 1
    fi

    python3 -c "
import json
from datetime import datetime, timezone

with open('$REGISTRY') as f:
    reg = json.load(f)

now = datetime.now(timezone.utc)
overdue = []
for c in reg.get('credentials', []):
    created = datetime.fromisoformat(c.get('created', '2026-01-01'))
    max_days = c.get('max_age_days', 90)
    age = (now - created).days
    status = 'OVERDUE' if age > max_days else 'OK'
    if age > max_days:
        overdue.append(c['id'])
    print(f\"{status}: {c['id']} — {age}d / {max_days}d max (auto_rotate: {c.get('auto_rotate_allowed', False)})\")

if overdue:
    print(f'\n⚠️  {len(overdue)} credential(s) overdue for rotation')
else:
    print('\n✅ All credentials within age policy')
"
}

case "${1:-}" in
    --key-id) rotate_key "${2:?key-id required}" ;;
    --check-ages) check_ages ;;
    *) echo "Usage: $0 --key-id <id> | --check-ages"; exit 1 ;;
esac
