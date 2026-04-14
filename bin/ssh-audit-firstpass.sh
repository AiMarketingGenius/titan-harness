#!/usr/bin/env bash
# bin/ssh-audit-firstpass.sh
# Gate #3 of DR-AMG-ENFORCEMENT-01 — SSH forensic first-pass.
#
# Runs the 9-step baseline non-destructively on the VPS and emits a completed
# copy of templates/ssh-forensic-first-pass.md to stdout (or to --out <path>).
#
# This is the ONLY sanctioned way to open an SSH/firewall proposal or SSH-adjacent
# hypothesis chain. Pre-proposal-gate.sh (Gate #1) will reject proposals whose
# commit/message does not reference an output file produced by this script.
#
# Exit codes:
#   0  — all 9 baseline steps captured cleanly
#   10 — SSH access failure (escape-hatch issue — STOP and escalate)
#   11 — one or more baseline steps returned empty/error (partial capture)
#   12 — template file missing
#
# Usage:
#   bin/ssh-audit-firstpass.sh --host root@170.205.37.148 --port 2222 \
#       --key ~/.ssh/id_ed25519_amg --incident INC-2026-04-14-02 \
#       --out plans/review_bundles/STEP_<ID>/ssh-firstpass.md

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${REPO_ROOT}/templates/ssh-forensic-first-pass.md"

HOST=""
PORT="22"
KEY=""
INCIDENT=""
OUT=""
OPERATOR="${USER:-titan}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)      HOST="$2";       shift 2 ;;
    --port)      PORT="$2";       shift 2 ;;
    --key)       KEY="$2";        shift 2 ;;
    --incident)  INCIDENT="$2";   shift 2 ;;
    --operator)  OPERATOR="$2";   shift 2 ;;
    --out)       OUT="$2";        shift 2 ;;
    -h|--help)
      sed -n '2,25p' "$0" ; exit 0 ;;
    *) echo "ssh-audit-firstpass: unknown arg: $1" >&2 ; exit 2 ;;
  esac
done

[[ -z "$HOST"     ]] && { echo "ssh-audit-firstpass: --host required" >&2; exit 2; }
[[ -z "$INCIDENT" ]] && { echo "ssh-audit-firstpass: --incident required" >&2; exit 2; }
[[ -f "$TEMPLATE" ]] || { echo "ssh-audit-firstpass: template missing at $TEMPLATE" >&2; exit 12; }

SSH_OPTS=(-4 -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -p "$PORT")
[[ -n "$KEY" ]] && SSH_OPTS+=(-i "$KEY")

# Escape-hatch liveness probe (Q2 of lockout-risk gate)
if ! ssh "${SSH_OPTS[@]}" "$HOST" 'echo alive' >/dev/null 2>&1; then
  echo "ssh-audit-firstpass: escape hatch DEAD — $HOST:$PORT not responding" >&2
  echo "                    STOP. Do not propose any SSH/firewall change." >&2
  echo "                    Next action: HostHatch console + root password (cred doc §15C)." >&2
  exit 10
fi

START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
WORK="$(mktemp -d -t ssh-firstpass.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

PARTIAL=0
run_remote() {
  local label="$1" ; shift
  local outfile="${WORK}/${label}.txt"
  if ssh "${SSH_OPTS[@]}" "$HOST" "$*" >"$outfile" 2>&1; then
    :
  else
    PARTIAL=1
    echo "[PARTIAL] step '$label' exited non-zero" >>"$outfile"
  fi
  [[ -s "$outfile" ]] || { echo "(empty output)" >"$outfile"; PARTIAL=1; }
  echo "$outfile"
}

F1=$(run_remote  "01-sshd-T"             "sshd -T 2>&1 | head -400")
F2=$(run_remote  "02-sshd_config"        "cat /etc/ssh/sshd_config")
F3=$(run_remote  "03-access-blocks"      "grep -inE '^\s*(AllowUsers|DenyUsers|AllowGroups|DenyGroups|Match)' /etc/ssh/sshd_config || true")
F4=$(run_remote  "04-iptables"           "iptables -L -n -v 2>&1 ; echo '---' ; ip6tables -L -n -v 2>&1")
F5=$(run_remote  "05-ufw"                "ufw status verbose 2>&1")
F6=$(run_remote  "06-fail2ban"           "fail2ban-client status 2>&1 ; echo '---' ; fail2ban-client status sshd 2>&1 || true")
F7=$(run_remote  "07-authlog-24h"        "journalctl -u ssh --since '24 hours ago' --no-pager 2>&1 | tail -200 ; echo '---' ; tail -200 /var/log/auth.log 2>/dev/null || true")
F8=$(run_remote  "08-who-last"           "who ; echo '---' ; last -a | head -30")
F9=$(run_remote  "09-systemctl"          "systemctl status ssh sshd fail2ban --no-pager 2>&1 | head -80")

BLOCKS="$(cat "$F3")"
[[ -z "$BLOCKS" || "$BLOCKS" == "(empty output)" ]] && BLOCKS="(none found — no AllowUsers/DenyUsers/Match blocks in sshd_config)"

# Assemble filled template
TMP_OUT="$(mktemp -t ssh-firstpass-out.XXXXXX)"
{
  # Copy template up to the "## 3." extraction block
  awk '/^## 3\. AllowUsers/{exit} {print}' "$TEMPLATE"
  cat <<EOF
## 3. AllowUsers / DenyUsers / Match extracted lines

\`\`\`text
${BLOCKS}
\`\`\`

## Attachments (9-step baseline)

### Step 1 — sshd -T
\`\`\`
$(cat "$F1")
\`\`\`

### Step 2 — /etc/ssh/sshd_config
\`\`\`
$(cat "$F2")
\`\`\`

### Step 4 — iptables / ip6tables
\`\`\`
$(cat "$F4")
\`\`\`

### Step 5 — ufw status verbose
\`\`\`
$(cat "$F5")
\`\`\`

### Step 6 — fail2ban
\`\`\`
$(cat "$F6")
\`\`\`

### Step 7 — auth log (24h)
\`\`\`
$(cat "$F7")
\`\`\`

### Step 8 — who / last
\`\`\`
$(cat "$F8")
\`\`\`

### Step 9 — systemctl status
\`\`\`
$(cat "$F9")
\`\`\`

---

## Run metadata (machine-parseable)

\`\`\`yaml
ssh_audit_firstpass:
  incident:  "${INCIDENT}"
  operator:  "${OPERATOR}"
  host:      "${HOST}"
  port:      ${PORT}
  started_utc:  "${START_UTC}"
  finished_utc: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  baseline_all_9_present: $([[ $PARTIAL -eq 0 ]] && echo true || echo false)
  partial_capture: $([[ $PARTIAL -eq 1 ]] && echo true || echo false)
  template_version: "1.0"
\`\`\`
EOF
} >"$TMP_OUT"

if [[ -n "$OUT" ]]; then
  mkdir -p "$(dirname "$OUT")"
  mv "$TMP_OUT" "$OUT"
  echo "ssh-audit-firstpass: wrote $OUT"
else
  cat "$TMP_OUT"
  rm -f "$TMP_OUT"
fi

[[ $PARTIAL -eq 1 ]] && exit 11
exit 0
