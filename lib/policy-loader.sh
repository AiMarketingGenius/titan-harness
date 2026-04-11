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
#   POLICY_WAR_ROOM_REVISER_MODEL     — war_room.reviser_model (Claude model name)
#   POLICY_MP_RUNS_ENABLED            — mp_runs.enabled (1/0)
#   POLICY_MP_RUNS_PROJECT            — mp_runs.default_project
#   POLICY_MP_RUNS_TABLE              — mp_runs.log_table
#   POLICY_MP_RUNS_LOG_DIR            — mp_runs.log_dir
#   POLICY_MP_RUNS_SLACK_CHANNEL      — mp_runs.slack_channel
#   POLICY_MP_RUNS_HARD_CAP_USD       — mp_runs.spend_hard_cap_usd
#   POLICY_MP_RUNS_SOFT_ALERT_USD     — mp_runs.spend_soft_alert_usd
#   POLICY_MP_RUNS_HARD_ALERT_USD     — mp_runs.spend_hard_alert_usd

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
    'POLICY_WAR_ROOM_REVISER_MODEL':  get(cfg, 'war_room.reviser_model', 'claude-sonnet-4-5-20250929'),
    # capacity (Phase G.5 — VPS ceilings)
    'POLICY_CAPACITY_MAX_CLAUDE_SESSIONS':       get(cfg, 'capacity.max_claude_sessions', 12),
    'POLICY_CAPACITY_MAX_HEAVY_TASKS':           get(cfg, 'capacity.max_heavy_tasks', 8),
    'POLICY_CAPACITY_MAX_N8N_BRANCHES':          get(cfg, 'capacity.max_n8n_branches_per_workflow', 20),
    'POLICY_CAPACITY_MAX_HEAVY_WORKFLOWS':       get(cfg, 'capacity.max_concurrent_heavy_workflows', 3),
    'POLICY_CAPACITY_MAX_WORKERS_GENERAL':       get(cfg, 'capacity.max_workers_general', 10),
    'POLICY_CAPACITY_MAX_WORKERS_CPU_HEAVY':     get(cfg, 'capacity.max_workers_cpu_heavy', 4),
    'POLICY_CAPACITY_MAX_LLM_BATCH_SIZE':        get(cfg, 'capacity.max_llm_batch_size', 15),
    'POLICY_CAPACITY_MAX_LLM_CONCURRENT_BATCHES':get(cfg, 'capacity.max_concurrent_llm_batches', 8),
    'POLICY_CAPACITY_CPU_SOFT_PCT':              get(cfg, 'capacity.cpu_soft_limit_percent', 80),
    'POLICY_CAPACITY_CPU_HARD_PCT':              get(cfg, 'capacity.cpu_hard_limit_percent', 90),
    'POLICY_CAPACITY_RAM_SOFT_GIB':              get(cfg, 'capacity.ram_soft_limit_gib', 50),
    'POLICY_CAPACITY_RAM_HARD_GIB':              get(cfg, 'capacity.ram_hard_limit_gib', 56),
    # mp_runs (Phase G.4)
    'POLICY_MP_RUNS_ENABLED':         b(get(cfg, 'mp_runs.enabled', False)),
    'POLICY_MP_RUNS_PROJECT':         get(cfg, 'mp_runs.default_project', 'EOM'),
    'POLICY_MP_RUNS_TABLE':           get(cfg, 'mp_runs.log_table', 'mp_runs'),
    'POLICY_MP_RUNS_LOG_DIR':         get(cfg, 'mp_runs.log_dir', '/var/log/mp-runs'),
    'POLICY_MP_RUNS_SLACK_CHANNEL':   get(cfg, 'mp_runs.slack_channel', '#amg-mp-runs'),
    'POLICY_MP_RUNS_HARD_CAP_USD':    get(cfg, 'mp_runs.spend_hard_cap_usd', 150),
    'POLICY_MP_RUNS_SOFT_ALERT_USD':  get(cfg, 'mp_runs.spend_soft_alert_usd', 75),
    'POLICY_MP_RUNS_HARD_ALERT_USD':  get(cfg, 'mp_runs.spend_hard_alert_usd', 135),
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



# --- P3 model router exports -------------------------------------------------
# Read the models: block directly from policy.yaml and emit POLICY_MODEL_*.
_model_exports=$(python3 - "$POLICY_FILE" <<'MEEOF' 2>/dev/null
import sys, json, re
try:
    lines = open(sys.argv[1]).read().splitlines()
except Exception:
    print("export POLICY_MODEL_DEFAULT='claude-sonnet-4-6'")
    print("export POLICY_MODEL_ROUTING_JSON='{}'")
    sys.exit(0)

default = "claude-sonnet-4-6"
routing = {}
in_models = False
in_routing = False
for raw in lines:
    stripped = raw.split("#", 1)[0].rstrip()
    if not stripped.strip():
        continue
    if re.match(r"^models:\s*$", stripped):
        in_models = True
        continue
    if in_models:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", stripped):
            break
        m = re.match(r'^\s+default:\s*"?([^"\s]+)"?\s*$', stripped)
        if m:
            default = m.group(1)
            continue
        if re.match(r"^\s+routing:\s*$", stripped):
            in_routing = True
            continue
        if in_routing:
            m = re.match(r'^\s+([a-z0-9_]+):\s*"([^"]+)"\s*$', stripped)
            if m:
                routing[m.group(1)] = m.group(2)

print("export POLICY_MODEL_DEFAULT='" + default + "'")
print("export POLICY_MODEL_ROUTING_JSON='" + json.dumps(routing).replace("'", "'\\''") + "'")
print("export POLICY_MODELS_CONFIGURED=1" if routing else "export POLICY_MODELS_CONFIGURED=0")
MEEOF
)
if [ -n "$_model_exports" ]; then
  eval "$_model_exports"
fi
unset _model_exports


# --- P11 fast_mode + blaze_mode exports --------------------------------------
_fastblaze=$(python3 - "$POLICY_FILE" <<'FBEOF' 2>/dev/null
import sys, re
try:
    lines = open(sys.argv[1]).read().splitlines()
except Exception:
    print("export POLICY_FAST_MODE_DEFAULT='on'")
    print("export POLICY_FAST_MODE_EXCEPTIONS='plan,architecture,war_room_revise,deep_debug'")
    print("export POLICY_BLAZE_MODE_ENABLED=1")
    sys.exit(0)

fast_default = "on"
fast_exc = []
blaze_enabled = False
in_fast = False
in_fast_exc = False
in_blaze = False
for raw in lines:
    stripped = raw.split("#", 1)[0].rstrip()
    if not stripped.strip():
        continue
    if re.match(r"^fast_mode:\s*$", stripped):
        in_fast = True
        in_blaze = False
        continue
    if re.match(r"^blaze_mode:\s*$", stripped):
        in_blaze = True
        in_fast = False
        in_fast_exc = False
        continue
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", stripped):
        in_fast = False
        in_blaze = False
        in_fast_exc = False
        continue
    if in_fast:
        m = re.match(r'^\s+default:\s*"?([^"\s]+)"?\s*$', stripped)
        if m:
            fast_default = m.group(1)
            continue
        if re.match(r"^\s+exception_task_types:\s*$", stripped):
            in_fast_exc = True
            continue
        if in_fast_exc:
            m = re.match(r"^\s+-\s*(\S+)", stripped)
            if m:
                fast_exc.append(m.group(1))
                continue
            in_fast_exc = False
    if in_blaze:
        m = re.match(r"^\s+enabled:\s*(true|false)", stripped)
        if m:
            blaze_enabled = (m.group(1) == "true")

print("export POLICY_FAST_MODE_DEFAULT='" + fast_default + "'")
print("export POLICY_FAST_MODE_EXCEPTIONS='" + ",".join(fast_exc) + "'")
print("export POLICY_BLAZE_MODE_ENABLED=" + ("1" if blaze_enabled else "0"))
FBEOF
)
if [ -n "$_fastblaze" ]; then
  eval "$_fastblaze"
fi
unset _fastblaze

# --- CORE CONTRACT: validate capacity block present (Phase G.5) --------------
# Non-bypassable. Inspects raw policy.yaml (not env vars, which have Python
# fallback defaults) for a populated capacity: block. Warns on stderr if
# missing. Does NOT block hook execution (fail-safe); harness-preflight.sh
# blocks runner startup when POLICY_CAPACITY_BLOCK_VALIDATED != 1.
_cap_validated=$(python3 - "$POLICY_FILE" <<'CAPVAL' 2>/dev/null
import sys, re
try:
    lines = open(sys.argv[1]).read().splitlines()
except Exception:
    print("0"); sys.exit(0)
in_cap = False
required = {
    "max_claude_sessions", "max_heavy_tasks",
    "max_n8n_branches_per_workflow", "max_concurrent_heavy_workflows",
    "max_workers_general", "max_workers_cpu_heavy",
    "max_llm_batch_size", "max_concurrent_llm_batches",
    "cpu_soft_limit_percent", "cpu_hard_limit_percent",
    "ram_soft_limit_gib", "ram_hard_limit_gib",
}
seen = set()
for raw in lines:
    stripped = raw.split("#", 1)[0].rstrip()
    if not stripped.strip():
        continue
    if re.match(r"^capacity:\s*$", stripped):
        in_cap = True
        continue
    if in_cap:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", stripped):
            break
        m = re.match(r"^\s+([a-z0-9_]+):\s*\S", stripped)
        if m:
            seen.add(m.group(1))
print("1" if required.issubset(seen) else "0")
CAPVAL
)
if [ "${_cap_validated:-0}" = "1" ]; then
  export POLICY_CAPACITY_BLOCK_VALIDATED=1
else
  echo "policy-loader: CORE CONTRACT VIOLATION - capacity block missing or incomplete in $POLICY_FILE" >&2
  export POLICY_CAPACITY_BLOCK_VALIDATED=0
fi
unset _cap_validated

unset _policy_candidates _policy_exports _p
