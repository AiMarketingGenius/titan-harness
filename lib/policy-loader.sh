#!/bin/bash
# titan-harness/lib/policy-loader.sh
#
# Phase G.2: Policy-as-code loader. Parses policy.yaml and exports
# relevant keys as env vars so hooks and helper scripts can read config
# at runtime without hardcoding values.
#
# Sourced by titan-env.sh, so every hook gets policy-driven config
# automatically.
#
# Design:
#   - Uses python3 (already a dependency) + PyYAML OR a tiny inline parser
#   - Fails safe: if policy.yaml is missing/malformed, emits warning and
#     falls back to existing env vars / defaults. Never blocks a hook.
#   - Exports only the keys hooks need. Does NOT pollute env with everything.
#
# Env vars exported:
#   POLICY_FILE                       — absolute path to loaded policy.yaml
#   POLICY_VERSION                    — policy.version string
#   POLICY_PROJECT_ID                 — harness.project_id
#   POLICY_PRE_TOOL_BLOCKED           — pre_tool_gate.blocked_tools (comma-joined)
#   POLICY_PRE_TOOL_REQUIRE_TASK      — pre_tool_gate.require_active_task (1/0)
#   POLICY_PRE_TOOL_BYPASS_FILE       — pre_tool_gate.bypass_file
#   POLICY_IDEA_ENABLED               — idea_capture.enabled (1/0)
#   POLICY_IDEA_TRIGGER               — idea_capture.trigger_phrase
#   POLICY_IDEA_EMOJI                 — idea_capture.emoji_trigger
#   POLICY_IDEA_PROJECT               — idea_capture.default_project
#   POLICY_IDEA_EMPTY_BEHAVIOR        — idea_capture.empty_behavior
#   POLICY_IDEA_DEDUP_LOOKBACK        — idea_capture.dedup.local_queue_lookback
#   POLICY_DRAIN_INTERVAL             — idea_drain.interval_seconds
#   POLICY_DRAIN_HTTP_TIMEOUT         — idea_drain.http_timeout_seconds
#   POLICY_DRAIN_DEDUP_CODE           — idea_drain.dedup_http_code
#   POLICY_DRAIN_SLACK_ENABLED        — idea_drain.slack.enabled (1/0)
#   POLICY_DRAIN_SLACK_WEBHOOK_ENV    — idea_drain.slack.webhook_env
#   POLICY_DRAIN_SLACK_TIMEOUT        — idea_drain.slack.timeout_seconds
#   POLICY_WAR_ROOM_ENABLED           — war_room.enabled (1/0)
#   POLICY_WAR_ROOM_MODEL             — war_room.model
#   POLICY_WAR_ROOM_MIN_GRADE         — war_room.min_acceptable_grade
#   POLICY_WAR_ROOM_MAX_ROUNDS        — war_room.max_refinement_rounds
#   POLICY_WAR_ROOM_TABLE             — war_room.log_table
#   POLICY_WAR_ROOM_COST_CEILING      — war_room.cost_ceiling_cents_per_exchange
#   POLICY_WAR_ROOM_SLACK_CHANNEL     — war_room.slack_channel
#   POLICY_WAR_ROOM_REQUIRE_PASSING   — war_room.require_passing_grade_before_lock (1/0)

# Locate policy.yaml
_policy_candidates=(
  "${TITAN_POLICY_FILE:-}"
  "$(dirname "${BASH_SOURCE[0]}")/../policy.yaml"
  "/opt/titan-harness/policy.yaml"
  "$HOME/titan-harness/policy.yaml"
)

POLICY_FILE=""
for _p in "${_policy_candidates[@]}"; do
  if [ -n "$_p" ] && [ -f "$_p" ]; then
    POLICY_FILE=$(cd "$(dirname "$_p")" && pwd)/$(basename "$_p")
    break
  fi
done

if [ -z "$POLICY_FILE" ]; then
  # No policy file found — fall through silently. Hooks will use their defaults.
  return 0 2>/dev/null || exit 0
fi

# Parse policy.yaml using python3 and export keys.
# Uses a tiny YAML parser written inline because PyYAML may not be installed.
# For our flat-ish config this is sufficient — we do NOT try to be general.
_policy_exports=$(python3 - "$POLICY_FILE" <<'PYEOF' 2>/dev/null
import sys, re, os

def parse_yaml(path):
    """Minimal YAML parser for our policy.yaml shape.
    Handles: nested mappings, scalars (str/int/bool), inline lists,
    and quoted strings. Does NOT handle: anchors, multi-line strings,
    block lists with nested maps (redact_patterns uses those — we
    emit the redact list separately).
    """
    with open(path) as f:
        lines = f.read().splitlines()

    result = {}
    stack = [(0, result)]  # (indent, dict)

    def _strip_inline_comment(s):
        # Only treat '#' as a comment if preceded by whitespace or at BOL.
        # Keeps quoted values like "#amg-war-room" intact.
        out_chars = []
        in_s = in_d = False
        prev = ''
        for ch in s:
            if ch == "'" and not in_d:
                in_s = not in_s
            elif ch == '"' and not in_s:
                in_d = not in_d
            elif ch == '#' and not in_s and not in_d and (prev == '' or prev.isspace()):
                break
            out_chars.append(ch)
            prev = ch
        return ''.join(out_chars).rstrip()

    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = _strip_inline_comment(raw)
        if not stripped.strip():
            i += 1
            continue

        indent = len(raw) - len(raw.lstrip(' '))
        # Pop stack to current level
        while stack and stack[-1][0] > indent:
            stack.pop()

        line = stripped.strip()

        # List item under a key (we skip these; handled separately if needed)
        if line.startswith('- '):
            i += 1
            continue

        # key: value  OR  key:
        m = re.match(r'^([A-Za-z0-9_.\-]+)\s*:\s*(.*)$', line)
        if not m:
            i += 1
            continue
        key = m.group(1)
        val = m.group(2).strip()

        parent = stack[-1][1]

        if val == '':
            # Nested mapping opens here
            new_map = {}
            parent[key] = new_map
            stack.append((indent + 2, new_map))
        else:
            # Scalar value — strip quotes, coerce bool/int
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            elif val.lower() in ('true', 'false'):
                val = val.lower() == 'true'
            elif val.startswith('[') and val.endswith(']'):
                # Simple inline list
                inner = val[1:-1].strip()
                if inner:
                    parts = [p.strip().strip('"').strip("'") for p in inner.split(',')]
                    val = parts
                else:
                    val = []
            else:
                try:
                    val = int(val)
                except ValueError:
                    pass  # leave as string
            parent[key] = val

        i += 1

    return result

def get(d, path, default=None):
    cur = d
    for p in path.split('.'):
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur

def b(v):
    """Bool → 1/0 string"""
    return '1' if v else '0'

def esc(v):
    """Shell-escape string for export"""
    if v is None:
        return ''
    if isinstance(v, list):
        v = ','.join(str(x) for x in v)
    s = str(v)
    # Replace single quotes
    s = s.replace("'", "'\\''")
    return s

try:
    cfg = parse_yaml(sys.argv[1])
except Exception as e:
    sys.stderr.write(f"policy-loader: parse failed: {e}\n")
    sys.exit(1)

exports = {
    'POLICY_VERSION':             get(cfg, 'version', '1.0'),
    'POLICY_PROJECT_ID':          get(cfg, 'harness.project_id', 'EOM'),
    # pre_tool_gate
    'POLICY_PRE_TOOL_BLOCKED':    get(cfg, 'pre_tool_gate.blocked_tools', ['Write','Edit','NotebookEdit']),
    'POLICY_PRE_TOOL_REQUIRE_TASK': b(get(cfg, 'pre_tool_gate.require_active_task', True)),
    'POLICY_PRE_TOOL_BYPASS_FILE': get(cfg, 'pre_tool_gate.bypass_file', '.gate_bypass'),
    # idea_capture
    'POLICY_IDEA_ENABLED':        b(get(cfg, 'idea_capture.enabled', True)),
    'POLICY_IDEA_TRIGGER':        get(cfg, 'idea_capture.trigger_phrase', 'lock it'),
    'POLICY_IDEA_EMOJI':          get(cfg, 'idea_capture.emoji_trigger', '🔒'),
    'POLICY_IDEA_PROJECT':        get(cfg, 'idea_capture.default_project', 'EOM'),
    'POLICY_IDEA_EMPTY_BEHAVIOR': get(cfg, 'idea_capture.empty_behavior', 'warn-and-skip'),
    'POLICY_IDEA_DEDUP_LOOKBACK': get(cfg, 'idea_capture.dedup.local_queue_lookback', 10),
    # idea_drain
    'POLICY_DRAIN_INTERVAL':      get(cfg, 'idea_drain.interval_seconds', 60),
    'POLICY_DRAIN_HTTP_TIMEOUT':  get(cfg, 'idea_drain.http_timeout_seconds', 8),
    'POLICY_DRAIN_DEDUP_CODE':    get(cfg, 'idea_drain.dedup_http_code', 409),
    'POLICY_DRAIN_SLACK_ENABLED': b(get(cfg, 'idea_drain.slack.enabled', True)),
    'POLICY_DRAIN_SLACK_WEBHOOK_ENV': get(cfg, 'idea_drain.slack.webhook_env', 'SLACK_WEBHOOK_URL'),
    'POLICY_DRAIN_SLACK_TIMEOUT': get(cfg, 'idea_drain.slack.timeout_seconds', 4),
    # war_room (Phase G.3)
    'POLICY_WAR_ROOM_ENABLED':        b(get(cfg, 'war_room.enabled', False)),
    'POLICY_WAR_ROOM_MODEL':          get(cfg, 'war_room.model', 'sonar-pro'),
    'POLICY_WAR_ROOM_MIN_GRADE':      get(cfg, 'war_room.min_acceptable_grade', 'B'),
    'POLICY_WAR_ROOM_MAX_ROUNDS':     get(cfg, 'war_room.max_refinement_rounds', 3),
    'POLICY_WAR_ROOM_TABLE':          get(cfg, 'war_room.log_table', 'war_room_exchanges'),
    'POLICY_WAR_ROOM_COST_CEILING':   get(cfg, 'war_room.cost_ceiling_cents_per_exchange', 25),
    'POLICY_WAR_ROOM_SLACK_CHANNEL':  get(cfg, 'war_room.slack_channel', '#amg-war-room'),
    'POLICY_WAR_ROOM_REQUIRE_PASSING': b(get(cfg, 'war_room.require_passing_grade_before_lock', True)),
}

for k, v in exports.items():
    print(f"export {k}='{esc(v)}'")
PYEOF
)

if [ -n "$_policy_exports" ]; then
  eval "$_policy_exports"
  export POLICY_FILE
else
  # Parser failed — log once per shell, don't block
  if [ -z "${_POLICY_WARNED:-}" ]; then
    echo "policy-loader: failed to parse $POLICY_FILE, using hook defaults" >&2
    export _POLICY_WARNED=1
  fi
fi

unset _policy_candidates _policy_exports _p
