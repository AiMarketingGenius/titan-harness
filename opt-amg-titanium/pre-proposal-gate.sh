#!/usr/bin/env bash
# pre-proposal-gate.sh — TITANIUM DOCTRINE v1.0 enforcement gate.
#
# Called from pre-commit as Layer 1.5 (between integrity + tradesecret).
# Enforces: pre-mortem file presence, material-claim confidence flags,
# OPA policy evaluation, ESCALATE.md hard-stop, emergency-halt state.
#
# Exits:
#   0  — gate passed (or open-fail on OPA tooling missing)
#   10 — policy violation (OPA eval deny)
#   11 — pre-mortem file missing on production-bound change
#   12 — material claim without confidence flag
#   13 — emergency halt active
#   14 — self-test passed (when --self-test)
#   99 — bypassed via GATE_OVERRIDE=1 (logs, exits 0)

set -euo pipefail

readonly REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd ../.. && pwd)"
readonly TITANIUM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly STATE_FILE="${GOVERNANCE_STATE_FILE:-$TITANIUM_DIR/governance_state.json}"
readonly POLICY_DIR="$TITANIUM_DIR/opa_policies"
readonly LOG_FILE="${GATE_LOG:-$HOME/titan-harness/logs/pre_proposal_gate.log}"

mkdir -p "$(dirname "$LOG_FILE")"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG_FILE"; }

slack_alert() {
  local msg="$1"
  if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
    curl -s -m 3 -X POST "$SLACK_WEBHOOK_URL" \
      -H 'Content-Type: application/json' \
      -d "$(printf '{"text":"[pre-proposal-gate] %s"}' "$msg")" >/dev/null 2>&1 &
  fi
  # Always log locally + MCP (degraded path). flag_blocker requires MCP client;
  # here we just append to an MCP-drain queue for the auto_approve_ingest sidecar
  # to pick up (reuse existing infra rather than new paths).
  local queue="$HOME/titan-harness/logs/auto_approve_queue"
  mkdir -p "$queue"
  printf '{"event":"gate_alert","action":"violation","target":"pre-proposal-gate","app":"titan","kind":"governance","category":null,"ts":"%s","message":%s}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(printf '%s' "$msg" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')" \
    > "$queue/gate-$(date +%s%N).json"
}

self_test() {
  log "self-test invoked"
  # Syntax-check every script in this dir
  local rc=0
  for f in "$TITANIUM_DIR"/*.sh; do
    if [ -f "$f" ]; then
      bash -n "$f" || { log "self-test syntax FAIL $f"; rc=1; }
    fi
  done
  # Check OPA policies exist if opa binary present
  if command -v opa >/dev/null 2>&1 && [ -d "$POLICY_DIR" ]; then
    opa eval --data "$POLICY_DIR" 'data' >/dev/null 2>&1 || { log "self-test opa eval FAIL"; rc=1; }
  fi
  # Check governance_state.json parses (if exists)
  if [ -f "$STATE_FILE" ]; then
    command -v jq >/dev/null 2>&1 && {
      jq -e . "$STATE_FILE" >/dev/null 2>&1 || { log "self-test state FAIL"; rc=1; }
    }
  fi
  if [ $rc -eq 0 ]; then log "self-test PASS"; else log "self-test FAIL"; fi
  return $rc
}

# Hard stop — emergency halt active
if [ -f "$REPO/ESCALATE.md" ]; then
  slack_alert "ESCALATE.md present — gate blocking all commits"
  log "BLOCK ESCALATE.md present"
  echo "[pre-proposal-gate] BLOCK: ESCALATE.md present at repo root. Ack with bin/harness-ack-escalation.sh." >&2
  exit 13
fi

# Governance state check (open-fail if state file or jq missing)
if [ -f "$STATE_FILE" ] && command -v jq >/dev/null 2>&1; then
  if jq -e '.emergency_halt == true' "$STATE_FILE" >/dev/null 2>&1; then
    slack_alert "governance_state.emergency_halt=true — gate blocking"
    log "BLOCK emergency_halt=true"
    echo "[pre-proposal-gate] BLOCK: governance_state.emergency_halt=true." >&2
    exit 13
  fi
fi

# Self-test subcommand
if [ "${1:-}" = "--self-test" ]; then
  self_test
  exit $?
fi

# GATE_OVERRIDE honor (logged)
if [ "${GATE_OVERRIDE:-0}" = "1" ]; then
  slack_alert "GATE_OVERRIDE=1 used — bypassing policy checks (user=$USER)"
  log "OVERRIDE GATE_OVERRIDE=1 user=$USER"
  echo "[pre-proposal-gate] OVERRIDE applied; gate skipped. Logged." >&2
  exit 0
fi

# Determine staged files (pre-commit context) — if none, this is a non-commit
# invocation and we just run self-test + exit.
STAGED=""
if git rev-parse --git-dir >/dev/null 2>&1; then
  STAGED=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || true)
fi
if [ -z "$STAGED" ]; then
  log "no staged files; gate run in non-commit mode — self-test only"
  self_test
  exit $?
fi

# Detect production-bound classes: deploys, schemas, external API wiring,
# client-facing artifacts. These trigger pre-mortem requirement.
PRODUCTION_BOUND=0
while IFS= read -r f; do
  case "$f" in
    deploy/*|sql/*|TitanControl/*|bin/deploy-*|scripts/deploy_*|opt-amg-titanium/*) PRODUCTION_BOUND=1 ;;
    portal/*|site/*|marketing/*|revere-*|chamber-*) PRODUCTION_BOUND=1 ;;
    hooks/*|.git/hooks/*) PRODUCTION_BOUND=1 ;;
    CLAUDE.md|CORE_CONTRACT.md|policy.yaml) PRODUCTION_BOUND=1 ;;
  esac
done <<< "$STAGED"

# Check 1: pre-mortem file requirement
if [ "$PRODUCTION_BOUND" = "1" ] && [ "${SKIP_PRE_MORTEM:-0}" != "1" ]; then
  HAS_PRE_MORTEM=0
  while IFS= read -r f; do
    case "$f" in
      PRE_MORTEM_*.md|**/PRE_MORTEM_*.md) HAS_PRE_MORTEM=1 ;;
    esac
  done <<< "$STAGED"
  if [ "$HAS_PRE_MORTEM" = "0" ]; then
    slack_alert "BLOCK: production-bound commit lacks PRE_MORTEM_*.md file"
    log "BLOCK pre-mortem missing; files: $(echo "$STAGED" | tr '\n' ' ')"
    cat <<EOF >&2
[pre-proposal-gate] BLOCK: production-bound commit has no PRE_MORTEM_*.md file.
Write a 3-question pre-mortem per /opt/amg-titanium/PRE_MORTEM_TEMPLATE.md:
  - Q1: Most likely failure mode in 48hr
  - Q2: Exact rollback procedure
  - Q3: Leading indicator visible before failure
Filename: PRE_MORTEM_<CT-ID>_<YYYY-MM-DD>.md at repo root.
Bypass for non-production fixes: SKIP_PRE_MORTEM=1 git commit ...
EOF
    exit 11
  fi
fi

# Check 2: material-claim confidence flag scan on staged .md files
# Scans for unflagged dollar amounts, credentials references, DNS assertions, etc.
# Only scans files under plans/ and opt-amg-titanium/ (doctrine + proposal docs)
# because those are where material-claim assertions typically land.
if [ "${SKIP_CONFIDENCE_SCAN:-0}" != "1" ]; then
  VIOLATIONS=""
  while IFS= read -r f; do
    case "$f" in
      plans/*.md|plans/**/*.md|opt-amg-titanium/*.md)
        # Skip if file has either a CONFIDENCE block or a "⚠️ CROSS-VALIDATED" tag.
        if [ -f "$f" ]; then
          if grep -qE "CONFIDENCE|CROSS-VALIDATED|perplexity_review|cross-check" "$f" 2>/dev/null; then
            continue
          fi
          # Scan for material-claim signals
          if grep -qE '\$[0-9]+' "$f" 2>/dev/null || \
             grep -qiE 'api[-_]?key|service[-_]?role|tailscale[-_]?key' "$f" 2>/dev/null; then
            VIOLATIONS="$VIOLATIONS $f"
          fi
        fi
        ;;
    esac
  done <<< "$STAGED"
  if [ -n "$VIOLATIONS" ]; then
    slack_alert "BLOCK: material claims without confidence flag in:$VIOLATIONS"
    log "BLOCK material claims unflagged:$VIOLATIONS"
    cat <<EOF >&2
[pre-proposal-gate] BLOCK: material-claim confidence flag missing in:
$VIOLATIONS

Material claims (dollar amounts, credentials, DNS assertions) in doctrine
or proposal docs need either:
  (a) inline ⚠️ CONFIDENCE <0.95 flag with reason
  (b) cross-validation tag (CROSS-VALIDATED via perplexity_review)
  (c) a top-level CONFIDENCE section stating ≥0.95

Bypass for acknowledged non-material content: SKIP_CONFIDENCE_SCAN=1 git commit ...
EOF
    exit 12
  fi
fi

# Check 3: OPA policy evaluation (open-fail if opa binary missing)
if command -v opa >/dev/null 2>&1 && [ -d "$POLICY_DIR" ]; then
  # Build input.json from staged files
  input_json="$(mktemp)"
  trap 'rm -f "$input_json"' EXIT
  files_json=$(printf '%s\n' "$STAGED" | jq -R . | jq -s .)
  printf '{"files": %s, "production_bound": %s}\n' "$files_json" "$PRODUCTION_BOUND" > "$input_json"

  # Query deny rules
  DECISION=$(opa eval --data "$POLICY_DIR" --input "$input_json" \
    --format pretty 'data.amg.titanium.deny' 2>&1 || echo '["opa-eval-error"]')
  if printf '%s' "$DECISION" | grep -q '"'; then
    slack_alert "BLOCK: OPA deny — $DECISION"
    log "BLOCK opa deny: $DECISION"
    echo "[pre-proposal-gate] BLOCK OPA policy deny:" >&2
    echo "$DECISION" >&2
    exit 10
  fi
else
  log "WARN opa binary or policy dir missing; open-fail"
fi

log "PASS files=$(echo "$STAGED" | wc -l | tr -d ' ')"
exit 0
