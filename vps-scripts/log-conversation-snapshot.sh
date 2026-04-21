#!/bin/bash
# Standardized MCP writer for the 10-turn conversation snapshot rule.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./mcp-common.sh
. "$SCRIPT_DIR/mcp-common.sh"

PROJECT="EOM"
ACTOR="Achilles"
THREAD_REF="unlabeled-thread"
TURN_WINDOW="unspecified-turn-window"
EXTRA_TAGS=""
INPUT_FILE=""
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage:
  log-conversation-snapshot.sh [options] [--file path]
  cat snapshot.md | log-conversation-snapshot.sh [options]

Options:
  --project <name>       project_source to write (default: EOM)
  --actor <name>         Achilles, EOM, or another lane label
  --thread <label>       human-readable thread label
  --turn-window <range>  e.g. 1-10 or 31-40
  --tags <csv>           extra MCP tags to append
  --file <path>          read snapshot body from file instead of stdin
  --dry-run              print normalized payload without posting
  -h, --help             show this help
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project)
      PROJECT="${2:?missing value for --project}"
      shift 2
      ;;
    --actor)
      ACTOR="${2:?missing value for --actor}"
      shift 2
      ;;
    --thread)
      THREAD_REF="${2:?missing value for --thread}"
      shift 2
      ;;
    --turn-window)
      TURN_WINDOW="${2:?missing value for --turn-window}"
      shift 2
      ;;
    --tags)
      EXTRA_TAGS="${2:?missing value for --tags}"
      shift 2
      ;;
    --file)
      INPUT_FILE="${2:?missing value for --file}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -n "$INPUT_FILE" ]; then
  SNAPSHOT_TEXT="$(cat "$INPUT_FILE")"
else
  if [ -t 0 ]; then
    echo "FATAL: no snapshot body supplied. Pass --file or pipe stdin." >&2
    exit 2
  fi
  SNAPSHOT_TEXT="$(cat)"
fi

FORMATTED="$(mcp_format_conversation_snapshot "$SNAPSHOT_TEXT" "$THREAD_REF" "$TURN_WINDOW" "$ACTOR")"
TAGS="conversation_snapshot"
if [ -n "$EXTRA_TAGS" ]; then
  TAGS="$TAGS,$EXTRA_TAGS"
fi

if [ "$DRY_RUN" = "1" ]; then
  printf 'PROJECT=%s\nTAGS=%s\n\n%s\n' "$PROJECT" "$TAGS" "$FORMATTED"
  exit 0
fi

mcp_env_load
mcp_log_conversation_snapshot "$SNAPSHOT_TEXT" "$PROJECT" "$THREAD_REF" "$TURN_WINDOW" "$ACTOR" "$EXTRA_TAGS"
