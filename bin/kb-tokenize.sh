#!/usr/bin/env bash
# bin/kb-tokenize.sh — validate per-agent KB size stays under the 30K-token cap.
#
# Usage:
#   bin/kb-tokenize.sh plans/agents/kb/alex
#   bin/kb-tokenize.sh --all
#
# Tokenization: rough 4-chars-per-token approximation (conservative).
# Target: <= 30,000 tokens per agent (configurable via KB_TOKEN_CAP env).
#
# Exit codes:
#   0 = all KBs under cap
#   1 = one or more KBs over cap
#   2 = usage error

set -u
KB_TOKEN_CAP="${KB_TOKEN_CAP:-30000}"
KB_ROOT_DEFAULT="plans/agents/kb"

token_estimate() {
  # char count / 4 = rough token count
  local chars
  chars=$(wc -c < "$1" 2>/dev/null || echo 0)
  echo $(( chars / 4 ))
}

validate_agent_kb() {
  local agent_dir="$1"
  local agent_name
  agent_name=$(basename "$agent_dir")
  local total_chars=0
  local file_count=0

  while IFS= read -r -d '' md; do
    local chars
    chars=$(wc -c < "$md")
    total_chars=$(( total_chars + chars ))
    file_count=$(( file_count + 1 ))
  done < <(find "$agent_dir" -maxdepth 3 -type f -name "*.md" -print0)

  local total_tokens=$(( total_chars / 4 ))
  if [ "$total_tokens" -gt "$KB_TOKEN_CAP" ]; then
    printf "FAIL: %s  %d files  %d chars  ~%d tokens  (cap %d)\n" \
      "$agent_name" "$file_count" "$total_chars" "$total_tokens" "$KB_TOKEN_CAP"
    return 1
  else
    printf "OK:   %s  %d files  %d chars  ~%d tokens  (cap %d)\n" \
      "$agent_name" "$file_count" "$total_chars" "$total_tokens" "$KB_TOKEN_CAP"
    return 0
  fi
}

main() {
  if [ $# -eq 0 ]; then
    echo "Usage: $0 <agent_kb_dir> | --all" >&2
    exit 2
  fi

  if [ "$1" = "--all" ]; then
    local root="${2:-$KB_ROOT_DEFAULT}"
    if [ ! -d "$root" ]; then
      echo "No KB root at $root" >&2
      exit 2
    fi
    local any_fail=0
    while IFS= read -r -d '' agent_dir; do
      validate_agent_kb "$agent_dir" || any_fail=1
    done < <(find "$root" -mindepth 1 -maxdepth 1 -type d -print0)
    exit $any_fail
  fi

  local dir="$1"
  if [ ! -d "$dir" ]; then
    echo "Not a directory: $dir" >&2
    exit 2
  fi
  validate_agent_kb "$dir"
  exit $?
}

main "$@"
