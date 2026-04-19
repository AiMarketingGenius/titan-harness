#!/bin/bash
# mcp-archive-github.sh — CT-0419-07 Step 4 (L3 GitHub archive)
#
# Nightly encrypt-in-place + commit + push of /opt/amg-mcp-archive/ to
# AiMarketingGenius/amg-mcp-archive private repo. age-encrypted so only
# holders of /etc/amg/mcp-archive-key.txt (private) + ~/.config/amg/mcp-archive-key.age
# (in Solon's keychain, deferred to first-surface moment) can decrypt.
#
# Schedule: 03:00 ET nightly via mcp-archive-github.timer.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./mcp-common.sh
. "$SCRIPT_DIR/mcp-common.sh"

ARCHIVE_SRC="/opt/amg-mcp-archive"
GIT_ROOT="/opt/amg-mcp-archive-git"
REPO_OWNER="AiMarketingGenius"
REPO_NAME="amg-mcp-archive"
AGE_PUB="/etc/amg/mcp-archive.age.pub"
LOG_FILE="/opt/amg/logs/mcp-archive-github.log"

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$LOG_FILE"; }

mcp_env_load

if [ ! -f "$AGE_PUB" ]; then
  log "FAIL missing_age_pub_key path=$AGE_PUB"
  exit 1
fi

AGE_PUB_RECIPIENT="$(cat "$AGE_PUB")"
if [ -z "$AGE_PUB_RECIPIENT" ]; then
  log "FAIL empty_age_pub_key"
  exit 1
fi

# Ensure git repo is set up
if [ ! -d "$GIT_ROOT/.git" ]; then
  log "INIT git repo at $GIT_ROOT"
  mkdir -p "$GIT_ROOT"
  cd "$GIT_ROOT"
  git init -q
  git branch -M main 2>/dev/null || git checkout -b main 2>/dev/null
  git config user.email "titan@aimarketinggenius.com"
  git config user.name "Titan MCP Archiver"

  # Auto-add remote if repo exists. Prefer HTTPS so gh's credential helper supplies auth;
  # SSH would require a separate key registration with the GitHub account.
  if ! git remote get-url origin >/dev/null 2>&1; then
    REPO_URL=$(gh repo view "${REPO_OWNER}/${REPO_NAME}" --json url --jq '.url+".git"' 2>/dev/null || true)
    if [ -n "$REPO_URL" ]; then
      git remote add origin "$REPO_URL"
    else
      log "FAIL no_remote_repo_url run install first"
      exit 2
    fi
  fi

  # Seed README + .gitignore
  cat > README.md <<'EOF'
# amg-mcp-archive

Encrypted nightly archive of MCP op_decisions from Supabase project
`egoazyasyrhslluossli`. Created by CT-0419-07 (memory loop closure) on
2026-04-19.

**Every `.md.age` file in this repo is age-encrypted.**
Decrypt with: `age -d -i /etc/amg/mcp-archive.age /path/to/file.md.age > out.md`

- Source: `/opt/amg-mcp-archive/decisions-YYYY-MM-DD.md`
- Cadence: Daily at 02:00 ET (L2 write) + 03:00 ET (L3 push)
- Retention on source VPS: 90 days rolling
- Retention on GitHub: unlimited (long-term store)
- Owner: AiMarketingGenius
- Visibility: private
EOF
  cat > .gitignore <<'EOF'
# Never commit plaintext decision dumps
decisions-*.md
# Only .age-encrypted files are tracked
!decisions-*.md.age
EOF
fi

cd "$GIT_ROOT"

# Encrypt all plaintext .md files that don't yet have .md.age counterparts
ENCRYPTED=0
for src in "$ARCHIVE_SRC"/decisions-*.md; do
  [ -f "$src" ] || continue
  base=$(basename "$src")
  target="$GIT_ROOT/${base}.age"
  # Skip if target already exists AND source hasn't changed mtime since encryption
  if [ -f "$target" ]; then
    src_m=$(stat -c %Y "$src" 2>/dev/null)
    tgt_m=$(stat -c %Y "$target" 2>/dev/null)
    [ "$src_m" -le "$tgt_m" ] && continue
  fi
  if age -r "$AGE_PUB_RECIPIENT" -o "$target" "$src"; then
    ENCRYPTED=$((ENCRYPTED+1))
  else
    log "FAIL age_encrypt src=$src"
  fi
done

# Stage + commit if any changes
cd "$GIT_ROOT"
git add -A
if git diff --cached --quiet; then
  log "OK no_changes encrypted=${ENCRYPTED}"
  exit 0
fi

TODAY=$(date -u +%Y-%m-%d)
if ! git commit -q -m "Nightly MCP archive — ${TODAY}" >/dev/null 2>&1; then
  log "FAIL git_commit"
  exit 3
fi

# Push
if ! git push -q origin main 2>&1 | tee -a "$LOG_FILE"; then
  log "FAIL git_push"
  # Best-effort Slack alert
  mcp_slack_or_log ":warning: MCP L3 GitHub archive push FAILED on $(hostname -s)" "mcp-integrity,archive-failure,ct-0419-07" || true
  exit 4
fi

SHA=$(git rev-parse --short HEAD)
log "OK encrypted=${ENCRYPTED} commit=${SHA}"

# Prune oldest plaintext .md on source (>90 days) — the L2 script does this
# too, but we do it here as a safety net since L3 push just landed.
find "$ARCHIVE_SRC" -maxdepth 1 -name 'decisions-*.md' -mtime +90 -delete 2>/dev/null || true

exit 0
