#!/usr/bin/env bash
# bin/pre-proposal-gate.sh
# Gate #1 of DR-AMG-ENFORCEMENT-01 v1.1 — pre-proposal gate.
#
# Rejects commits touching SSH-adjacent paths unless they carry a verified
# SSH-Baseline trailer (hash-pinned to a recent ssh-audit-firstpass.sh output).
#
# Hash-pin logic closes the v1.0 bypass vectors Perplexity flagged:
#   - forged timestamps die: we hash file content, not filename/mtime
#   - stale baselines die: we require YAML metadata <24h AND file mtime <24h
#   - --no-verify on commit: post-commit logger catches (separate script)
#   - server-side: VPS pre-receive runs this same gate on push
#
# Usage:
#   bin/pre-proposal-gate.sh pre-commit
#       → checks staged files; uses commit-msg file if pre-commit-msg env hook supplies it,
#         else reads message from $GIT_COMMIT_MSG_FILE if set, else falls back to `git log -1`.
#   bin/pre-proposal-gate.sh commit-msg <path-to-COMMIT_EDITMSG>
#       → checks staged files + parses the given message file (this is the robust mode)
#   bin/pre-proposal-gate.sh pre-receive <oldsha> <newsha> <refname>
#       → walks commits in range, validates each
#
# Exit 0 pass, 1 fail (block), 2 usage error.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${REPO_ROOT}/.harness-state"
mkdir -p "$STATE_DIR"

MODE="${1:-}"
[[ -z "$MODE" ]] && { echo "usage: $0 {pre-commit|commit-msg <file>|pre-receive <old> <new> <ref>}" >&2; exit 2; }

# --- SSH-adjacent scope matcher ---
is_ssh_adjacent() {
  local f="$1"
  shopt -s nocasematch
  case "$f" in
    # exempted self-edits (the gate + template + audit script)
    templates/ssh-forensic-first-pass.md) return 1 ;;
    bin/ssh-audit-firstpass.sh)            return 1 ;;
    bin/pre-proposal-gate.sh)              return 1 ;;
    bin/post-commit-bypass-logger.sh)      return 1 ;;
    hooks/git/pre-receive)                 return 1 ;;
    bin/install-gate1-hooks.sh)            return 1 ;;
    # in-scope patterns
    *sshd_config*|*ssh_config*)            return 0 ;;
    *iptables*|*ufw*|*fail2ban*)           return 0 ;;
    */etc/ssh/*)                           return 0 ;;
    bin/ssh-*|bin/*-ssh-*)                 return 0 ;;
    bin/*firewall*|bin/*-ufw-*)            return 0 ;;
  esac
  return 1
}

parse_trailer() {
  # Reads stdin; echoes value for the given key, or empty.
  local key="$1"
  awk -v key="$key" 'BEGIN{IGNORECASE=1} $0 ~ "^"key":" {sub("^"key":[[:space:]]*",""); print; exit}'
}

validate_baseline() {
  # $1 = sha256-claimed  $2 = repo-relative path  $3 = commit-iso-ts (for age calc)
  local claim="$1" path="$2" commit_ts="${3:-}"
  local full="${REPO_ROOT}/${path}"

  if [[ ! -f "$full" ]]; then
    echo "[GATE-1] baseline path not found in repo: $path" >&2
    return 1
  fi

  # Content hash must match claim
  local actual
  actual="$(shasum -a 256 "$full" 2>/dev/null | awk '{print $1}' || sha256sum "$full" | awk '{print $1}')"
  if [[ "$actual" != "$claim" ]]; then
    echo "[GATE-1] baseline hash mismatch — forged trailer or stale file" >&2
    echo "         claimed: $claim" >&2
    echo "         actual:  $actual" >&2
    return 1
  fi

  # Dual timestamp check: file mtime AND YAML metadata must both be <24h old.
  local now_epoch mtime_epoch
  now_epoch="$(date +%s)"
  mtime_epoch="$(stat -f %m "$full" 2>/dev/null || stat -c %Y "$full")"
  local age=$(( now_epoch - mtime_epoch ))
  if (( age > 86400 )); then
    echo "[GATE-1] baseline file mtime >24h old (age=${age}s); re-run bin/ssh-audit-firstpass.sh" >&2
    return 1
  fi

  # Parse YAML finished_utc: from the baseline's own metadata block
  local yaml_fin
  yaml_fin="$(awk '/finished_utc:/ {gsub(/"/, ""); print $2; exit}' "$full" || true)"
  if [[ -n "$yaml_fin" ]]; then
    local yaml_epoch
    yaml_epoch="$(date -u -j -f '%Y-%m-%dT%H:%M:%SZ' "$yaml_fin" +%s 2>/dev/null \
                  || date -u -d "$yaml_fin" +%s 2>/dev/null || echo 0)"
    if (( yaml_epoch > 0 )); then
      local yaml_age=$(( now_epoch - yaml_epoch ))
      if (( yaml_age > 86400 )); then
        echo "[GATE-1] baseline YAML finished_utc >24h old (age=${yaml_age}s)" >&2
        return 1
      fi
    fi
  fi

  return 0
}

scan_shell_for_unguarded_ssh() {
  # Gate #4 v1.2 integration: flag SSH-scope shell invocations in staged
  # shell files that don't go through bin/opa-guard.sh.
  # Recognized exemptions:
  #   - Line prefixed with '# opa-guard-exempt:' comment above OR same line trailing
  #   - Lines already invoking opa-guard.sh
  #   - The opa-guard.sh script itself + escape-hatch-verify.sh + ssh-audit-firstpass.sh
  #     + bin/harness-* drift/install/heal scripts (read-only probes)
  local f="$1"
  case "$f" in
    bin/opa-guard.sh|bin/escape-hatch-verify.sh|bin/ssh-audit-firstpass.sh) return 0 ;;
    bin/harness-*|bin/install-*|bin/titan-*|bin/trigger-*|bin/update-*) return 0 ;;
    bin/pre-proposal-gate.sh|bin/post-commit-bypass-logger.sh|bin/refresh-policy-checksums.sh) return 0 ;;
    bin/opa-*|bin/hypothesis-*) return 0 ;;
  esac
  [[ "$f" == *.sh ]] || return 0
  [[ -f "${REPO_ROOT}/$f" ]] || return 0

  local hits
  hits="$(grep -nE '^[[:space:]]*(ssh|ufw|iptables|ip6tables|fail2ban-client)([[:space:]]|$)' "${REPO_ROOT}/$f" | \
          grep -vE '(opa-guard\.sh|# opa-guard-exempt:)' || true)"
  if [[ -n "$hits" ]]; then
    echo "[GATE-1] Gate #4 integration: $f has SSH-scope invocation(s) NOT routed through opa-guard.sh:" >&2
    echo "$hits" | sed 's/^/    /' >&2
    echo "    Fix: wrap with bin/opa-guard.sh --baseline <path> --incident <ID> -- <cmd>" >&2
    echo "    Or add trailing '# opa-guard-exempt: <reason>' comment for read-only probes" >&2
    return 1
  fi
  return 0
}

check_commit() {
  # $1 = commit sha (or empty = staged index)
  # $2 = optional explicit commit-message file (commit-msg mode)
  local sha="${1:-}" msgfile="${2:-}"
  local files msg

  if [[ -n "$sha" ]]; then
    files="$(git diff --name-only "${sha}^!" 2>/dev/null || true)"
    msg="$(git log -1 --format=%B "$sha")"
  elif [[ -n "$msgfile" && -f "$msgfile" ]]; then
    files="$(git diff --cached --name-only)"
    msg="$(cat "$msgfile")"
  else
    files="$(git diff --cached --name-only)"
    msg="${GIT_COMMIT_MSG:-$(cat "${GIT_COMMIT_MSG_FILE:-/dev/null}" 2>/dev/null || true)}"
  fi

  # Scope check
  local in_scope=0 f
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    if is_ssh_adjacent "$f"; then in_scope=1; break; fi
  done <<<"$files"

  if (( in_scope == 0 )); then
    return 0  # nothing to enforce
  fi

  # Trailer extraction
  local claim_sha claim_path claim_inc
  claim_sha="$(printf '%s\n' "$msg" | parse_trailer 'SSH-Baseline')"
  claim_path="$(printf '%s\n' "$msg" | parse_trailer 'SSH-Baseline-Path')"
  claim_inc="$(printf '%s\n' "$msg" | parse_trailer 'SSH-Baseline-Incident')"

  if [[ -z "$claim_sha" || -z "$claim_path" || -z "$claim_inc" ]]; then
    cat >&2 <<EOF
[GATE-1] SSH-scope commit blocked — missing required trailers.

  This commit touches SSH/firewall paths. It must carry:
    SSH-Baseline: <sha256>
    SSH-Baseline-Path: <repo-relative path to ssh-firstpass.md output>
    SSH-Baseline-Incident: <INC-ID or PROPOSAL-ID>

  Produce a baseline via:
    bin/ssh-audit-firstpass.sh --host <> --port <> --key <> \\
        --incident <INC-ID> --out plans/review_bundles/STEP_<ID>/ssh-firstpass.md

  Then recompute hash and add trailers to the commit message.

  Staged files that triggered scope:
EOF
    while IFS= read -r f; do is_ssh_adjacent "$f" && echo "    $f" >&2; done <<<"$files"
    return 1
  fi

  # Validate
  validate_baseline "$claim_sha" "$claim_path" || return 1

  # Gate #4 v1.2 integration: shell files with unguarded SSH-scope invocations
  local unguarded_fail=0
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    scan_shell_for_unguarded_ssh "$f" || unguarded_fail=1
  done <<<"$files"
  (( unguarded_fail == 1 )) && return 1

  echo "[GATE-1] SSH-scope trailer validated — path=$claim_path incident=$claim_inc"
  return 0
}

case "$MODE" in
  pre-commit)
    check_commit ""
    ;;
  commit-msg)
    shift
    MSGFILE="${1:-}"
    [[ -z "$MSGFILE" || ! -f "$MSGFILE" ]] && { echo "commit-msg: message file required" >&2; exit 2; }
    check_commit "" "$MSGFILE"
    ;;
  pre-receive)
    shift
    OLD="${1:-}"; NEW="${2:-}"; REF="${3:-}"
    [[ -z "$OLD" || -z "$NEW" || -z "$REF" ]] && { echo "pre-receive: need old new ref" >&2; exit 2; }
    # Walk new commits
    FAIL=0
    for C in $(git rev-list "${OLD}..${NEW}" 2>/dev/null); do
      if ! check_commit "$C"; then
        echo "[GATE-1] rejecting push: commit $C fails SSH-scope validation" >&2
        FAIL=1
      fi
    done
    exit $FAIL
    ;;
  *)
    echo "usage: $0 {pre-commit|commit-msg <file>|pre-receive <old> <new> <ref>}" >&2
    exit 2
    ;;
esac
