#!/bin/zsh
# stopfailure_hook_restart.sh — TitanControl Restart Handler v1.0
# Path 1 (self-restart): Claude Code StopFailure hook.
# Fires request_restart.sh on rate_limit / authentication_failed / server_error / etc.

set -euo pipefail

APP_DIR="$HOME/Library/Application Support/TitanControl"
HANDLER="$APP_DIR/request_restart.sh"
STATE_DIR="$APP_DIR/state"
mkdir -p "$STATE_DIR"

INPUT="$(cat)"
export INPUT HANDLER STATE_DIR

python3 <<'PY'
import json, os, pathlib, subprocess
inp = json.loads(os.environ["INPUT"])
reason = inp.get("error_type", "unknown")
count_path = pathlib.Path(os.environ["STATE_DIR"]) / "exchange_count"
count = count_path.read_text().strip() if count_path.exists() else ""
subprocess.Popen([
    "/bin/zsh", os.environ["HANDLER"],
    "--source", "self:error-signal",
    "--reason", reason,
    "--exchange-count", count,
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
PY
