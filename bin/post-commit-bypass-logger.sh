#!/usr/bin/env bash
# bin/post-commit-bypass-logger.sh
# Gate #1 v1.1 companion — tamper logger for --no-verify bypass.
#
# Runs on every post-commit. If HEAD commit touches SSH-scope paths and does
# NOT carry the SSH-Baseline trailer, the pre-commit gate was bypassed
# (--no-verify or broken hook). Logs the event and alerts Slack.
#
# Does NOT block anything — the commit has already landed. The VPS pre-receive
# hook is the hard enforcement layer; this is the loud alarm for client-side.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${REPO_ROOT}/.harness-state"
BYPASS_LOG="${STATE_DIR}/bypass-log.jsonl"
GATE="${REPO_ROOT}/bin/pre-proposal-gate.sh"

mkdir -p "$STATE_DIR"

# Dry-invoke the gate on HEAD to detect bypass
HEAD_SHA="$(git rev-parse HEAD)"
HEAD_MSG="$(git log -1 --format=%B "$HEAD_SHA")"
STAGED_AT_HEAD="$(git diff-tree --no-commit-id --name-only -r "$HEAD_SHA")"

# Inline scope check (mirrors pre-proposal-gate.sh is_ssh_adjacent)
in_scope=0
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  case "$f" in
    templates/ssh-forensic-first-pass.md|bin/ssh-audit-firstpass.sh|bin/pre-proposal-gate.sh|bin/post-commit-bypass-logger.sh|hooks/git/pre-receive|bin/install-gate1-hooks.sh) continue ;;
    *sshd_config*|*ssh_config*|*iptables*|*ufw*|*fail2ban*|*/etc/ssh/*|bin/ssh-*|bin/*-ssh-*|bin/*firewall*|bin/*-ufw-*)
      in_scope=1 ; break ;;
  esac
done <<<"$STAGED_AT_HEAD"

(( in_scope == 0 )) && exit 0

if ! grep -qE '^SSH-Baseline:' <<<"$HEAD_MSG"; then
  TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  AUTHOR="$(git log -1 --format='%an <%ae>' "$HEAD_SHA")"
  FILES_JSON="$(printf '%s\n' "$STAGED_AT_HEAD" | python3 -c 'import sys,json; print(json.dumps([l for l in sys.stdin.read().splitlines() if l]))')"
  LINE="$(python3 -c "
import json
print(json.dumps({
  'ts': '$TS',
  'commit': '$HEAD_SHA',
  'author': '''$AUTHOR''',
  'files': $FILES_JSON,
  'reason': 'SSH-scope commit landed without SSH-Baseline trailer (pre-commit bypassed via --no-verify or broken hook)'
}))")"
  echo "$LINE" >> "$BYPASS_LOG"
  echo "[GATE-1 BYPASS DETECTED] logged to $BYPASS_LOG"

  # Best-effort Slack alert (non-blocking)
  if [[ -x "${REPO_ROOT}/lib/aristotle_slack.py" ]] || python3 -c "import sys; sys.path.insert(0,'${REPO_ROOT}/lib'); import aristotle_slack" 2>/dev/null; then
    python3 - <<PY 2>/dev/null || true
import sys
sys.path.insert(0, "${REPO_ROOT}/lib")
try:
    from aristotle_slack import post_to_channel
    post_to_channel("#titan-aristotle",
        f":warning: Gate #1 BYPASS — SSH-scope commit ${HEAD_SHA[:12]} landed without SSH-Baseline trailer. See .harness-state/bypass-log.jsonl.")
except Exception:
    pass
PY
  fi
fi

exit 0
