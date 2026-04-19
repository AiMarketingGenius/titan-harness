#!/bin/bash
# install-titan-control-settings.sh — patches ~/.claude/settings.json for TitanControl
#
# Adds to the existing hook chain:
#   SessionStart: …hydrate_gate → sessionstart_mark_ready → session-start.sh (inserts mark_ready)
#   Stop: stop_hook_drift_snapshot → stop_hook_restart_gate (adds restart_gate to chain)
#   StopFailure: stopfailure_hook_restart (new)
#
# Idempotent. Backs up settings.json before editing.

set -eu

SETTINGS="$HOME/.claude/settings.json"
[ -f "$SETTINGS" ] || { echo "ERR: $SETTINGS missing" >&2; exit 1; }

BACKUP="$SETTINGS.bak.titan-control.$(date -u +%Y%m%dT%H%M%SZ)"
cp "$SETTINGS" "$BACKUP"
echo "backup: $BACKUP"

python3 - "$SETTINGS" <<'PY'
import json, os, sys

path = sys.argv[1]
home = os.path.expanduser("~")
tc = f"{home}/Library/Application Support/TitanControl"

with open(path) as f:
    data = json.load(f)

hooks = data.setdefault("hooks", {})

# Helper: ensure a hook entry exists in a chain (match by command suffix)
def ensure_hook_in_chain(hook_list, cmd_suffix, new_entry, insert_idx=None):
    """hook_list is list of {'hooks': [...]}; find first group and check each entry."""
    if not hook_list:
        hook_list.append({"hooks": []})
    group = hook_list[0].setdefault("hooks", [])
    for h in group:
        if h.get("command", "").endswith(cmd_suffix):
            return False  # already present
    if insert_idx is None:
        group.append(new_entry)
    else:
        group.insert(insert_idx, new_entry)
    return True

# --- SessionStart: insert sessionstart_mark_ready between hydrate_gate and session-start ---
session_start = hooks.setdefault("SessionStart", [])
mark_ready_entry = {
    "type": "command",
    "command": f"{tc}/sessionstart_mark_ready.sh",
    "timeout": 5,
}
# Position: after hydrate_gate, before session-start.sh
if session_start:
    group = session_start[0].setdefault("hooks", [])
    # Already present?
    already = any(h.get("command", "").endswith("sessionstart_mark_ready.sh") for h in group)
    if not already:
        # Find insertion index: after last 'hydrate_gate', before 'session-start.sh'
        insert_at = len(group)  # default end
        for i, h in enumerate(group):
            if h.get("command", "").endswith("session-start.sh"):
                insert_at = i
                break
        group.insert(insert_at, mark_ready_entry)
        print(f"SessionStart: inserted mark_ready at idx {insert_at}")
    else:
        print("SessionStart: mark_ready already present")
else:
    session_start.append({"hooks": [mark_ready_entry]})
    print("SessionStart: new chain created")

# --- Stop: append stop_hook_restart_gate (chains after existing drift_snapshot) ---
stop_chain = hooks.setdefault("Stop", [])
restart_gate_entry = {
    "type": "command",
    "async": True,
    "command": f"{tc}/stop_hook_restart_gate.sh",
}
added = ensure_hook_in_chain(stop_chain, "stop_hook_restart_gate.sh", restart_gate_entry)
print(f"Stop: restart_gate {'added' if added else 'already present'}")

# --- StopFailure: new chain with matcher + async hook ---
sf_chain = hooks.setdefault("StopFailure", [])
sf_entry = {
    "type": "command",
    "async": True,
    "command": f"{tc}/stopfailure_hook_restart.sh",
}
# StopFailure uses a matcher for error types
if not sf_chain:
    sf_chain.append({
        "matcher": "rate_limit|authentication_failed|server_error|max_output_tokens|unknown",
        "hooks": [sf_entry],
    })
    print("StopFailure: new chain created")
else:
    group = sf_chain[0].setdefault("hooks", [])
    already = any(h.get("command", "").endswith("stopfailure_hook_restart.sh") for h in group)
    if not already:
        group.append(sf_entry)
        print("StopFailure: entry added to existing chain")
    else:
        print("StopFailure: entry already present")

with open(path, "w") as f:
    json.dump(data, f, indent=2)

print("settings.json written")
PY

echo ""
echo "validation:"
python3 -c "import json; d=json.load(open('$SETTINGS')); print('SessionStart hooks:', len(d['hooks']['SessionStart'][0]['hooks'])); print('Stop hooks:', len(d['hooks']['Stop'][0]['hooks'])); print('StopFailure hooks:', len(d['hooks']['StopFailure'][0]['hooks']))"
