#!/usr/bin/env bash
# hooks/pre-commit-lumina-gate.sh
# CT-0417-10b: block commits of visual / client-facing artifacts that lack a
# Lumina approval record. Source rule: plans/agents/kb/titan/05_lumina_dependency.md
#
# Gate logic:
#   IF staged file matches CLIENT_FACING_VISUAL_RE
#   AND no approval record exists at /opt/amg-docs/lumina/approvals/*.yaml with sha256 match
#   → BLOCK
#
# Exit codes:
#   0 = clean (either non-gated file, or approval found)
#   3 = gated file without approval, commit blocked

set -u

CLIENT_FACING_VISUAL_RE='^(deploy/|portal/|site/|marketing/|.*revere-|.*chamber-).+\.(html|css|jsx?|tsx?|svg|png|webp|avif)$'

# Exempt paths: Chrome-extension source code (capture logic, not client-facing
# visual), brand-assets source archives.
EXEMPT_VISUAL_RE='^deploy/aimg-extension-fixes/|/brand-assets/.*(original|src)'

APPROVAL_DIR="${LUMINA_APPROVAL_DIR:-/opt/amg-docs/lumina/approvals}"

# Environment flags
# LUMINA_GATE_BYPASS=1 → skip the gate entirely (emergency only; every bypass logged)
# LUMINA_GATE_DRAFT=1 → warn instead of block (for rapid local iteration pre-Lumina)

if [ "${LUMINA_GATE_BYPASS:-}" = "1" ]; then
  echo "[lumina-gate] BYPASSED — logged to /opt/amg-docs/lumina/bypass.log" >&2
  mkdir -p /opt/amg-docs/lumina 2>/dev/null || true
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) BYPASS by $(whoami) on $(git rev-parse HEAD 2>/dev/null || echo 'no-HEAD')" \
    >> /opt/amg-docs/lumina/bypass.log 2>/dev/null || true
  exit 0
fi

staged=$(git diff --cached --name-only --diff-filter=ACMR)
blocked=0
blocked_report=""

for f in $staged; do
  if ! echo "$f" | grep -qE "$CLIENT_FACING_VISUAL_RE"; then continue; fi
  if echo "$f" | grep -qE "$EXEMPT_VISUAL_RE"; then continue; fi
  if ! [ -f "$f" ]; then continue; fi

  # Compute sha256 of staged content
  sha=$(git show ":$f" 2>/dev/null | shasum -a 256 2>/dev/null | awk '{print $1}')
  if [ -z "$sha" ]; then continue; fi

  # Look for matching approval YAML
  matched=""
  if [ -d "$APPROVAL_DIR" ]; then
    matched=$(grep -l "artifact_sha256: $sha" "$APPROVAL_DIR"/*.yaml 2>/dev/null | head -1)
  fi

  if [ -z "$matched" ]; then
    # Also check if an approval mentions this artifact_path + score≥9.3 (path-based fallback)
    if [ -d "$APPROVAL_DIR" ]; then
      path_match=$(grep -l "artifact_path: $f" "$APPROVAL_DIR"/*.yaml 2>/dev/null | xargs -I{} awk '/lumina_score:/ {if ($2+0 >= 9.3) print FILENAME}' {} 2>/dev/null | head -1)
      if [ -n "$path_match" ]; then
        echo "[lumina-gate] $f — path match via $path_match (sha mismatch; iterative edit assumed — re-review recommended)" >&2
        continue
      fi
    fi
    blocked=$((blocked + 1))
    blocked_report="${blocked_report}
  $f (sha256: ${sha:0:16}…)"
  else
    echo "[lumina-gate] $f — approval: $(basename "$matched")"
  fi
done

if [ "$blocked" -gt 0 ]; then
  cat >&2 <<EOF

[BLOCK] Lumina-gate: $blocked visual artifact(s) lack a Lumina approval record.

Blocked files:
$blocked_report

Required before commit:
  1. Run Lumina review (agent_context_loader agent_name=lumina)
  2. Iterate until score >= 9.3 with no dimension below 8.5
  3. Log approval at $APPROVAL_DIR/YYYY-MM-DD_<hash>.yaml with artifact_sha256 matching the staged file
  4. Re-commit

Emergency bypass: LUMINA_GATE_BYPASS=1 git commit (logged to /opt/amg-docs/lumina/bypass.log)
Draft iteration: LUMINA_GATE_DRAFT=1 → (not yet implemented — use bypass for now, review next cycle)

Rule source: plans/agents/kb/titan/05_lumina_dependency.md
EOF
  exit 3
fi

echo "[lumina-gate] clean"
exit 0
