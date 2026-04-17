#!/usr/bin/env bash
# hooks/pre-commit-tradesecret-scan.sh
# CT-0417-10b: block commits that leak internal codenames / underlying AI vendors
# into client-facing paths. Source-of-truth banned list: plans/agents/kb/titan/01_trade_secrets.md
#
# Install: symlink to .git/hooks/pre-commit (or chain from existing pre-commit)
#
# Exit codes:
#   0 = clean, commit proceeds
#   2 = leak detected in client-facing path, commit blocked
#
# Override: if a staged file has first line starting with `# LEAK_OVERRIDE: <reason>`
# AND the commit message (HEAD + staged) contains `[LEAK_OVERRIDE]`, the hook logs
# to /opt/amg-docs/leak-overrides.log and allows through. Default: deny.

set -u

# Client-facing path patterns — scoped to files that RENDER to end users.
# Rule: if the file's contents get rendered, quoted, or transmitted to an end user
# (Chamber Board, subscriber business, Board President, demo attendee), it's scanned.
# KB source files + extension files that legitimately name AI sites are exempt
# (they're source docs / system code, not end-user output).
CLIENT_FACING_RE='^(deploy/|portal/|site/|marketing/|.*revere-|.*chamber-)'

# Exempt paths: Chrome-extension source (legitimately names AI sites it captures
# from), brand-assets dirs (PNG/SVG binaries), backup files, original-archives.
EXEMPT_PATH_RE='^deploy/aimg-extension-fixes/|/brand-assets/|\.bak$|\.original\.'

# Scan only files whose contents render to end users. Code files OUTSIDE exempt
# paths still get scanned (e.g., a normal deploy/**/*.js bundle).
SCAN_EXTENSIONS_RE='\.(html|css|jsx?|tsx?|svg|md|pdf)$'

# Banned terms (exact match, case-insensitive, word-boundary where appropriate)
# Mirror of plans/agents/kb/titan/01_trade_secrets.md regex patterns section
read -r -d '' BANNED_RE <<'EOF' || true
\b(Claude|Anthropic|Sonnet|Opus|Haiku|ChatGPT|GPT-[0-9]|OpenAI|o[0-9]-mini|Gemini|Bard|Grok|xAI|Perplexity|Sonar|Llama|Mistral|ElevenLabs|Kokoro|Ollama|nomic-embed-text)\b|\b(HostHatch|beast-primary|beast VPS)\b|\b140[\s-]lane\b|\bn8n\b|\bStagehand\b|\bSupabase\b|\b(kill.chain|kill.switch)\b|170\.205\.37\.148|87\.99\.149\.253
EOF

LEAK_LOG="/opt/amg-docs/leak-overrides.log"

# Collect staged files
staged=$(git diff --cached --name-only --diff-filter=ACMR)
leaks_found=0
leak_report=""

for f in $staged; do
  # Skip non-text files
  if ! [ -f "$f" ]; then continue; fi
  # Only scan client-facing paths
  if ! echo "$f" | grep -qE "$CLIENT_FACING_RE"; then continue; fi
  # Skip exempt subpaths (extension source, brand-assets, backups, originals)
  if echo "$f" | grep -qE "$EXEMPT_PATH_RE"; then continue; fi
  # Only scan end-user-rendering file types
  if ! echo "$f" | grep -qE "$SCAN_EXTENSIONS_RE"; then continue; fi

  # Check for override marker on first line
  first_line=$(head -1 "$f" 2>/dev/null)
  if echo "$first_line" | grep -q '^# LEAK_OVERRIDE:'; then
    # Override claimed. Check that commit message also tags [LEAK_OVERRIDE]
    msg_file=".git/COMMIT_EDITMSG"
    if [ -f "$msg_file" ] && grep -q '\[LEAK_OVERRIDE\]' "$msg_file"; then
      echo "[tradesecret-scan] override honored for $f (reason: ${first_line#\# LEAK_OVERRIDE: })"
      mkdir -p "$(dirname "$LEAK_LOG")"
      echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) OVERRIDE $f :: ${first_line#\# LEAK_OVERRIDE: }" >> "$LEAK_LOG" 2>/dev/null || true
      continue
    fi
  fi

  # Scan staged contents (not working tree — handles partial staging)
  staged_content=$(git show ":$f" 2>/dev/null)
  if [ -z "$staged_content" ]; then continue; fi

  hits=$(echo "$staged_content" | grep -niE "$BANNED_RE" 2>/dev/null | head -5)
  if [ -n "$hits" ]; then
    leaks_found=$((leaks_found + 1))
    leak_report="${leak_report}
=== $f ===
$hits
"
  fi
done

if [ "$leaks_found" -gt 0 ]; then
  cat >&2 <<EOF

[BLOCK] Trade-secret scan failed — $leaks_found file(s) contain banned terms in client-facing paths.

${leak_report}

Banned terms source: plans/agents/kb/titan/01_trade_secrets.md
Preferred substitutions: see §"Preferred substitutions (client-facing)" in that file.

If the leak is genuinely required (rare, e.g. competitive press release):
  1. Add \`# LEAK_OVERRIDE: <reason>\` as the first line of the offending file
  2. Include \`[LEAK_OVERRIDE]\` in the commit message
Both conditions must be met. Override is logged to $LEAK_LOG.

Otherwise, fix the leaks and re-commit.
EOF
  exit 2
fi

echo "[tradesecret-scan] clean — $(echo "$staged" | wc -w) staged files scanned"
exit 0
