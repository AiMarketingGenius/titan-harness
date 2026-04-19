#!/bin/zsh
# stop_hook_restart_gate.sh — TitanControl Restart Handler v1.0
# Path 1 (self-restart): Claude Code Stop hook.
# Increments exchange counter + fires request_restart.sh at N=25.
#
# Coexists with CT-0419-07's stop_hook_drift_snapshot.sh (different concern,
# chains as two entries in the Stop hook list).

set -euo pipefail

APP_DIR="$HOME/Library/Application Support/TitanControl"
STATE_DIR="$APP_DIR/state"
HANDLER="$APP_DIR/request_restart.sh"
THRESHOLD=25
mkdir -p "$STATE_DIR"

INPUT="$(cat)"
export INPUT STATE_DIR HANDLER THRESHOLD

python3 <<'PY'
import json, os, pathlib, subprocess

inp = json.loads(os.environ["INPUT"])
# Prevent Stop-hook infinite-loop per Claude Code hook docs
if inp.get("stop_hook_active") is True:
    raise SystemExit(0)

state_dir = pathlib.Path(os.environ["STATE_DIR"])
counter_file = state_dir / "exchange_count"
count = 0
if counter_file.exists():
    try: count = int(counter_file.read_text().strip() or "0")
    except: count = 0
count += 1
counter_file.write_text(str(count))

threshold = int(os.environ["THRESHOLD"])
if count >= threshold:
    subprocess.Popen([
        "/bin/zsh", os.environ["HANDLER"],
        "--source", "self:stop-hook",
        "--reason", f"exchange_{count}",
        "--exchange-count", str(count),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
PY
