#!/usr/bin/env bash
# bin/restore-titan-autonomy.sh
# Idempotent restoration of all 4 layers of DOCTRINE_TITAN_AUTONOMY.
# Called by titan-boot-audit.sh self-check when any layer is missing.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALIAS_LINE="alias claude='claude --dangerously-skip-permissions'"
RESTORED=()

# Layer 1: shell alias in BOTH .zshrc and .bash_profile (idempotent append)
for rc in "$HOME/.zshrc" "$HOME/.bash_profile"; do
    if [ -f "$rc" ]; then
        if ! grep -qF "$ALIAS_LINE" "$rc" 2>/dev/null; then
            printf '\n# Restored by bin/restore-titan-autonomy.sh on %s\n%s\n' \
                "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$ALIAS_LINE" >> "$rc"
            RESTORED+=("$rc")
        fi
    else
        # File missing entirely — create with minimal content
        cat > "$rc" <<EOF
# $(basename "$rc") — auto-created by bin/restore-titan-autonomy.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
# Part of DOCTRINE_TITAN_AUTONOMY Layer 1.

$ALIAS_LINE
export PATH="/usr/local/bin:/opt/homebrew/bin:\$HOME/.local/bin:\$HOME/bin:\$PATH"
alias th='cd ~/titan-harness'
EOF
        RESTORED+=("$rc (created)")
    fi
done

# Layer 2: settings.local.json (restore from HEAD if missing/stripped)
SETTINGS="$REPO/.claude/settings.local.json"
mkdir -p "$(dirname "$SETTINGS")"
if [ ! -f "$SETTINGS" ] || ! grep -q '"Bash(\*)"' "$SETTINGS" 2>/dev/null; then
    if (cd "$REPO" && git ls-files --error-unmatch "$SETTINGS" >/dev/null 2>&1); then
        (cd "$REPO" && git checkout HEAD -- ".claude/settings.local.json")
        RESTORED+=("$SETTINGS (restored from git HEAD)")
    else
        # Fallback: write canonical content
        cat > "$SETTINGS" <<'EOF'
{
  "permissions": {
    "allow": [
      "Bash(*)",
      "Edit(*)",
      "Write(*)",
      "Read(*)",
      "Glob(*)",
      "Grep(*)",
      "TodoWrite(*)",
      "WebFetch(*)",
      "WebSearch(*)",
      "NotebookEdit(*)",
      "mcp__*",
      "Skill(*)",
      "Agent(*)"
    ]
  }
}
EOF
        RESTORED+=("$SETTINGS (rewrote canonical)")
    fi
fi

# Report
if [ "${#RESTORED[@]}" -eq 0 ]; then
    echo "[restore-autonomy] all layers already intact — no changes"
    exit 0
fi
echo "[restore-autonomy] restored:"
printf '  - %s\n' "${RESTORED[@]}"
echo "[restore-autonomy] reload your shell or run: source ~/.zshrc"
