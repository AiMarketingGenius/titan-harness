#!/usr/bin/env bash
# bin/titan-restart-capture.sh
# Pre-exit state capture. Runs when:
#   (a) exchange counter reaches threshold (via post-tool-log or manual)
#   (b) SessionEnd hook fires with reason=context-flush
#   (c) user runs `bin/titan-restart-capture.sh --now`
#
# Captures: sprint state (MCP), recent decisions (MCP), active hypothesis
# (Gate #2), blockers, open RADAR loops, last 5 handovers, HEAD commit.
# Writes: ~/.claude/titan-resume-state.json + ~/.claude/titan-restart.flag
# Notifies: Slack via bin/titan-notify.sh
#
# Exit 0 always — never block the session from ending.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESUME_FILE="$HOME/.claude/titan-resume-state.json"
FLAG_FILE="$HOME/.claude/titan-restart.flag"
REASON="${1:-context-flush}"
[[ "${1:-}" == "--now" ]] && REASON="manual"

mkdir -p "$HOME/.claude"

# Best-effort MCP state capture. If MCP unreachable, fall back to local files.
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
HEAD="$(cd "$REPO" && git rev-parse HEAD 2>/dev/null || echo unknown)"
BRANCH="$(cd "$REPO" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"

RADAR_SNAPSHOT=""
if [[ -f "$REPO/RADAR.md" ]]; then
    RADAR_SNAPSHOT="$(grep -E '^## |^- \[ \]' "$REPO/RADAR.md" 2>/dev/null | head -40 || true)"
fi

ACTIVE_HYP=""
if [[ -f "$REPO/.harness-state/active-hypothesis.json" ]]; then
    ACTIVE_HYP="$(cat "$REPO/.harness-state/active-hypothesis.json" 2>/dev/null || echo '{}')"
fi

# Build resume-state JSON (atomic tmp+rename; HMAC-signed when gate2.secret present).
export PYTHONPATH="${REPO}/lib:${PYTHONPATH:-}"
TMP_RESUME="$(mktemp "${RESUME_FILE}.XXXXXX.tmp")"
trap 'rm -f "$TMP_RESUME" 2>/dev/null || true' EXIT

if ! python3 - <<PY > "$TMP_RESUME" 2>/dev/null
import json, os, subprocess, sys

sys.path.insert(0, "${REPO}/lib")

def tail(path, n=20):
    try:
        with open(path) as f:
            return f.read().splitlines()[-n:]
    except Exception:
        return []

repo = "${REPO}"
hyp_raw = """${ACTIVE_HYP}""".strip()
try:
    active_hyp = json.loads(hyp_raw) if hyp_raw and hyp_raw != "{}" else None
except Exception:
    active_hyp = None

state = {
    "ts_utc": "${TS}",
    "reason": "${REASON}",
    "git": {
        "head": "${HEAD}",
        "branch": "${BRANCH}",
    },
    "radar_snapshot": """${RADAR_SNAPSHOT}""".splitlines()[:40],
    "active_hypothesis": active_hyp,
    "recent_commits": [],
    "handover_tail": tail(os.path.expanduser("~/titan-session/audit.log"), 20),
    "mcp_bootstrap_hint": {
        "call_on_resume": [
            {"tool": "get_sprint_state", "args": {"project_id": "EOM"}},
            {"tool": "get_recent_decisions", "args": {"count": 5}},
            {"tool": "get_bootstrap_context", "args": {"scope": "eom", "refresh_only": False}},
        ],
        "read_files": [
            "RADAR.md",
            "NEXT_TASK.md",
            os.path.expanduser("~/.claude/titan-resume-state.json"),
        ],
    },
}

try:
    out = subprocess.check_output(["git","-C",repo,"log","--oneline","-10"], text=True, timeout=5)
    state["recent_commits"] = out.strip().splitlines()
except Exception as e:
    state["recent_commits"] = [f"(git log failed: {e})"]

# HMAC sign using gate2.secret (same key class — ambient integrity).
try:
    from hmac_state import sign_state
    state = sign_state(state)
except Exception:
    # Secret not installed — fall through unsigned. Resume code tolerates both.
    pass

print(json.dumps(state, indent=2, sort_keys=True))
PY
then
    echo "{\"error\":\"capture_failed\",\"ts_utc\":\"${TS}\"}" > "$TMP_RESUME"
fi

# Atomic rename
if [[ -s "$TMP_RESUME" ]] && python3 -c "import json,sys;json.load(open(sys.argv[1]))" "$TMP_RESUME" 2>/dev/null; then
    mv "$TMP_RESUME" "$RESUME_FILE"
    chmod 0600 "$RESUME_FILE"
    trap - EXIT
else
    echo "titan-restart-capture: resume file write failed (tmp=$TMP_RESUME)" >&2
fi

# Best-effort: log a restart-captured decision to MCP via the Python/CLI bridge
# if available. We don't block on MCP — the resume file is the ground truth.
# The next session's bootstrap will call the MCP tools directly.

# Touch the restart flag (launchd plist watches this path)
# Skipped in silent-capture mode (session-end ran us without a threshold hit).
if [[ "${SILENT_CAPTURE:-0}" != "1" ]]; then
    touch "$FLAG_FILE"
fi

# Slack notify
bash "${REPO}/bin/titan-notify.sh" \
  --title "Titan restart captured" \
  "Reason: ${REASON}. HEAD: ${HEAD:0:12}. Resume state at ~/.claude/titan-resume-state.json. Launchd will spin a fresh session; new Titan will bootstrap from MCP + resume file." \
  >/dev/null 2>&1 || true

echo "titan-restart-capture: reason=${REASON} head=${HEAD:0:12} flag=${FLAG_FILE}"
exit 0
