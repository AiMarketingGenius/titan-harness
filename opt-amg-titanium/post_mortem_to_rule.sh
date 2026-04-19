#!/usr/bin/env bash
# post_mortem_to_rule.sh — TITANIUM DOCTRINE v1.0 Gap 1.
#
# Scans MCP op_decisions from the past 7 days for [correction|burn|regression|mistake]
# tags. For each, proposes a structural rule (new pre-commit hook, new probe
# surface, new OPA policy fragment, new standing rule) and writes the
# proposal to /opt/amg-titanium/proposals/<yyyy-mm-dd>-<decision-id>.md.
#
# Acceptance: 100% of burn-tagged decisions from the past 30 days are either
# (a) promoted to a structural rule (decision tagged [structural-rule-added])
# or (b) explicitly rejected with rationale (decision tagged
# [structural-rule-rejected]). Zero unreviewed.
#
# Runs as systemd timer at 04:30 UTC daily.

set -euo pipefail

readonly TITANIUM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROPOSALS_DIR="$TITANIUM_DIR/proposals"
readonly LOG_FILE="${POSTMORTEM_LOG:-$HOME/titan-harness/logs/post_mortem_to_rule.log}"

mkdir -p "$PROPOSALS_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG_FILE"; }

# Load env for Supabase REST access
for env_file in "$HOME/.titan-env" "/opt/amg-titan/.env"; do
  [ -f "$env_file" ] && . "$env_file"
done
: "${SUPABASE_URL:?SUPABASE_URL not set}"
: "${SUPABASE_SERVICE_ROLE_KEY:?SUPABASE_SERVICE_ROLE_KEY not set}"

WINDOW_DAYS="${WINDOW_DAYS:-7}"
SINCE="$(python3 -c "import datetime as d; print((d.datetime.utcnow() - d.timedelta(days=${WINDOW_DAYS})).isoformat() + 'Z')")"

log "scanning op_decisions since $SINCE (window=${WINDOW_DAYS}d)"

# Query op_decisions with any of the target tags
curl_out=$(curl -sS -G "$SUPABASE_URL/rest/v1/op_decisions" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  --data-urlencode "select=id,created_at,decision_text,tags,project_source" \
  --data-urlencode "created_at=gte.$SINCE" \
  --data-urlencode "order=created_at.desc" \
  --data-urlencode "limit=500")

# jq filter to rows with target tags (adjust schema of tags column to your stored form)
targets=$(printf '%s' "$curl_out" | python3 -c '
import json, sys
rows = json.loads(sys.stdin.read() or "[]")
triggers = {"correction", "burn", "regression", "mistake", "confidence-miss", "protocol-gap"}
out = []
for r in rows:
    tags = r.get("tags") or []
    if isinstance(tags, str):
        try: tags = json.loads(tags)
        except Exception: tags = []
    if any(t in triggers for t in tags):
        out.append(r)
print(json.dumps(out))
')

count=$(printf '%s' "$targets" | python3 -c 'import json,sys; print(len(json.loads(sys.stdin.read() or "[]")))')
log "found $count trigger-tagged decisions in window"

if [ "$count" = "0" ]; then
  log "no action"
  exit 0
fi

# Write one proposal file per decision, flag as structural-rule-proposed
today=$(date -u +%Y-%m-%d)
printf '%s' "$targets" | python3 -c '
import json, os, sys, re
rows = json.loads(sys.stdin.read())
for r in rows:
    did = r.get("id", "unknown")
    ts = (r.get("created_at") or "")[:10]
    proj = r.get("project_source", "unknown")
    tags = r.get("tags") or []
    text = (r.get("decision_text") or "")[:1000].replace("\n", " ")
    fname = f"{os.environ[\"PROPOSALS_DIR\"]}/{ts}-{did[:8]}.md"
    if os.path.exists(fname):
        continue
    # Propose structural remediations heuristically
    proposals = []
    if re.search(r"pricing|price|\$[0-9]", text, re.I):
        proposals.append("Add pricing surface to regression_integrity_probe.sh (probe #6 expansion)")
    if re.search(r"dialog|permission|allow|deny", text, re.I):
        proposals.append("Re-check pre-proposal-gate.sh auto-approve allowlist and Hammerspoon Layer 3 loader")
    if re.search(r"token|secret|credential|api[-_]?key", text, re.I):
        proposals.append("Add OPA hard_limits.rego rule for the specific credential-file pattern")
    if re.search(r"trade[-_]?secret|claude|anthropic|grok|perplexity", text, re.I):
        proposals.append("Add term to opa_policies/trade_secrets.rego banned_terms set")
    if re.search(r"idle|wake|queue|claim", text, re.I):
        proposals.append("Tighten regression_integrity_probe.sh probe #9 (idle detection) thresholds")
    if not proposals:
        proposals.append("No automated rule proposal — EOM review required")

    with open(fname, "w") as f:
        f.write(f"# Proposal: structural rule for decision {did[:8]}\n\n")
        f.write(f"**Decision source:** {proj}\n")
        f.write(f"**Created:** {r.get(\"created_at\")}\n")
        f.write(f"**Tags:** {tags}\n\n")
        f.write(f"## Decision text\n\n> {text}\n\n")
        f.write(f"## Proposed structural remediations\n\n")
        for p in proposals:
            f.write(f"- {p}\n")
        f.write(f"\n## Review status\n\n- [ ] Promoted to structural rule (add tag [structural-rule-added] on original decision)\n")
        f.write(f"- [ ] Explicitly rejected (add tag [structural-rule-rejected] with rationale)\n")
    print(f"wrote {fname}")
'

log "post_mortem_to_rule complete"
