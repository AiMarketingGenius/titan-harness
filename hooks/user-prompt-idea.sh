#!/bin/bash
# titan-harness/hooks/user-prompt-idea.sh
#
# UserPromptSubmit hook: "lock it" / 🔒 trigger auto-captures an idea.
#
# Design (matches ARCHITECTURE.md in this repo):
#   1. Parse stdin JSON, extract .prompt field (Claude Code hooks get JSON, not raw prompt)
#   2. Detect trigger via POSIX regex (simpler-recommended path; no PCRE lookahead)
#   3. Extract explicit idea text AFTER "lock it:" or "🔒" — warn+skip on empty
#   4. Sanitize idea_text for secrets before any Slack mention
#   5. Hash + local dedup against last 10 queue lines
#   6. Append ONE line to $TITAN_SESSION_DIR/ideas-queue.jsonl (atomic)
#   7. Exit 0 — let prompt through unchanged
#
# IMPORTANT: This hook does NOT talk to Supabase or Slack directly.
# The sole Supabase writer is bin/idea-drain.sh, invoked by the systemd
# timer / launchd plist. This keeps the hook fast (<50ms) and eliminates
# the double-write bug from earlier drafts.

set -u
LC_ALL=C.UTF-8 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/titan-env.sh
source "$SCRIPT_DIR/../lib/titan-env.sh"

QUEUE_FILE="$TITAN_SESSION_DIR/ideas-queue.jsonl"
AUDIT_LOG="$TITAN_SESSION_DIR/audit.log"
touch "$QUEUE_FILE"

# --- Load config from ~/.titan-env or defaults ---
IDEA_TRIGGER="${IDEA_TRIGGER:-lock it}"
IDEA_EMOJI="${IDEA_EMOJI:-🔒}"
IDEA_PROJECT="${IDEA_PROJECT:-EOM}"

# --- Read stdin (Claude Code passes a JSON envelope) ---
INPUT=$(cat)

# Extract prompt + session_id via python (already a dependency for other hooks)
PROMPT=$(printf '%s' "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('prompt', ''), end='')
except Exception:
    pass
" 2>/dev/null)

SESSION_ID=$(printf '%s' "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('session_id', ''), end='')
except Exception:
    pass
" 2>/dev/null)

# If the hook gets called without a prompt field, do nothing
if [ -z "$PROMPT" ]; then
  exit 0
fi

# --- Detect trigger ---
# POSIX-safe pattern: "lock it" must be preceded by whitespace/punct OR start of string,
# AND followed by ":", whitespace, punctuation, or end of string.
# Case-insensitive match via tr-to-lower.
PROMPT_LOWER=$(printf '%s' "$PROMPT" | tr '[:upper:]' '[:lower:]')
TRIGGER_LOWER=$(printf '%s' "$IDEA_TRIGGER" | tr '[:upper:]' '[:lower:]')

TRIGGER_FOUND=0
TRIGGER_TYPE=""

# Phrase trigger: "lock it" with word boundaries
if printf '%s' "$PROMPT_LOWER" | grep -qE "(^|[[:space:][:punct:]])${TRIGGER_LOWER}([[:space:][:punct:]]|$)"; then
  TRIGGER_FOUND=1
  TRIGGER_TYPE="phrase"
fi

# Emoji trigger: locale-proof fixed-string match
if [ "$TRIGGER_FOUND" -eq 0 ] && printf '%s' "$PROMPT" | grep -qF "$IDEA_EMOJI"; then
  TRIGGER_FOUND=1
  TRIGGER_TYPE="emoji"
fi

if [ "$TRIGGER_FOUND" -eq 0 ]; then
  exit 0  # no trigger, pass prompt through
fi

# --- Extract idea text ---
# For phrase trigger: everything after the FIRST occurrence of "lock it"
# For emoji trigger: everything after the first emoji occurrence
IDEA_TEXT=""
if [ "$TRIGGER_TYPE" = "phrase" ]; then
  IDEA_TEXT=$(printf '%s' "$PROMPT" | python3 -c "
import sys, re
text = sys.stdin.read()
m = re.search(r'(?i)lock it[\s:]*(.*)', text, re.DOTALL)
print(m.group(1).strip() if m else '', end='')
")
else
  IDEA_TEXT=$(printf '%s' "$PROMPT" | python3 -c "
import sys
text = sys.stdin.read()
emoji = '$IDEA_EMOJI'
idx = text.find(emoji)
if idx == -1:
    print('', end='')
else:
    print(text[idx+len(emoji):].strip(), end='')
")
fi

# Warn + skip on empty
if [ -z "$IDEA_TEXT" ]; then
  titan_local_audit "IDEA_HOOK trigger=$TRIGGER_TYPE result=empty-skip session=${SESSION_ID:0:12}"
  exit 0
fi

# --- Sanitize idea_text for secrets before anything ---
# Strip obvious secret patterns so Slack + DB don't get a leaked key.
IDEA_TEXT_SANITIZED=$(printf '%s' "$IDEA_TEXT" | python3 -c "
import sys, re
t = sys.stdin.read()
patterns = [
    (r'sk-[A-Za-z0-9_-]{20,}', '[REDACTED_SK]'),
    (r'shpss_[A-Za-z0-9_-]{20,}', '[REDACTED_SHOPIFY]'),
    (r'shpat_[A-Za-z0-9_-]{20,}', '[REDACTED_SHOPIFY]'),
    (r'shpca_[A-Za-z0-9_-]{20,}', '[REDACTED_SHOPIFY]'),
    (r'eyJ[A-Za-z0-9_=\-]{40,}\.[A-Za-z0-9_=\-]+\.[A-Za-z0-9_=\-]+', '[REDACTED_JWT]'),
    (r'AKIA[0-9A-Z]{16}', '[REDACTED_AWS]'),
    (r'ghp_[A-Za-z0-9]{30,}', '[REDACTED_GH]'),
    (r'AIza[0-9A-Za-z_-]{30,}', '[REDACTED_GOOGLE]'),
    (r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[REDACTED_EMAIL]'),
]
for pat, repl in patterns:
    t = re.sub(pat, repl, t)
print(t, end='')
")

# --- Compute hash for dedup ---
IDEA_HASH=$(printf '%s' "$IDEA_TEXT_SANITIZED" | python3 -c "
import sys, re, hashlib
text = sys.stdin.read()
# normalize: lowercase, strip whitespace, strip punctuation
norm = re.sub(r'[\W_]+', '', text.lower())
print(hashlib.sha256(norm.encode('utf-8')).hexdigest(), end='')
")

# --- Local dedup check against last 10 queue lines ---
if [ -s "$QUEUE_FILE" ]; then
  if tail -n 10 "$QUEUE_FILE" | grep -qF "\"idea_hash\":\"$IDEA_HASH\""; then
    titan_local_audit "IDEA_HOOK hash=$IDEA_HASH result=dedup-skip session=${SESSION_ID:0:12}"
    exit 0
  fi
fi

# --- Build title (first 80 chars of sanitized text) ---
IDEA_TITLE=$(printf '%s' "$IDEA_TEXT_SANITIZED" | python3 -c "
import sys
t = sys.stdin.read().strip().replace('\n', ' ')
print(t[:80], end='')
")

# --- Build JSONL record ---
# NOTE: env vars must be set BEFORE `python3` (bash prefix-assignment syntax).
RECORD=$(
  IDEA_TEXT_SANITIZED="$IDEA_TEXT_SANITIZED" \
  IDEA_TITLE="$IDEA_TITLE" \
  IDEA_HASH="$IDEA_HASH" \
  IDEA_TRIGGER_USED="${TRIGGER_TYPE}:${IDEA_TRIGGER}" \
  TITAN_INSTANCE_VAR="$TITAN_INSTANCE" \
  SESSION_ID_VAR="$SESSION_ID" \
  IDEA_PROJECT="$IDEA_PROJECT" \
  python3 -c "
import json, os, sys
from datetime import datetime, timezone
rec = {
    'idea_text':    os.environ['IDEA_TEXT_SANITIZED'],
    'idea_title':   os.environ['IDEA_TITLE'],
    'idea_hash':    os.environ['IDEA_HASH'],
    'trigger_used': os.environ['IDEA_TRIGGER_USED'],
    'source':       'prompt-explicit',
    'instance_id':  os.environ['TITAN_INSTANCE_VAR'],
    'session_id':   os.environ.get('SESSION_ID_VAR', ''),
    'project_id':   os.environ['IDEA_PROJECT'],
    'status':       'captured',
    'created_at':   datetime.now(timezone.utc).isoformat(),
}
sys.stdout.write(json.dumps(rec, ensure_ascii=False))
")

# --- Atomic append to queue (single newline-terminated line) ---
printf '%s\n' "$RECORD" >> "$QUEUE_FILE"

titan_local_audit "IDEA_HOOK trigger=$TRIGGER_TYPE hash=$IDEA_HASH title=\"${IDEA_TITLE:0:40}\" session=${SESSION_ID:0:12}"

# Pass the prompt through to Claude unchanged
exit 0
