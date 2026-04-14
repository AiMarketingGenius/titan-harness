#!/usr/bin/env bash
# bin/hypothesis-timer-tick.sh
# Gate #2 v1.1 — systemd-invoked tick. Runs every 5min.
# Checks HMAC state validity + alert thresholds + max-attempts + audit-chain.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
STATE_DIR="${REPO}/.harness-state"
LOCK="${STATE_DIR}/.hypothesis.lock"
mkdir -p "$STATE_DIR"

# Portable advisory lock: flock on Linux, mkdir-based fallback for macOS.
if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK"
  flock -w 5 9 || exit 0
else
  LOCKDIR="${STATE_DIR}/.hypothesis.lock.d"
  for _ in 1 2 3 4 5; do
    if mkdir "$LOCKDIR" 2>/dev/null; then
      trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT
      break
    fi
    sleep 1
  done
  [[ -d "$LOCKDIR" ]] || exit 0
fi

export PYTHONPATH="${REPO}/lib:${PYTHONPATH:-}"
export REPO

python3 - <<'PY'
import json, os, sys, time, calendar

REPO = os.environ["REPO"]
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, "lib"))

try:
    from hmac_state import load_state, write_state, audit_append, verify_audit_chain
except Exception as e:
    print(f"[gate2-tick] cannot import hmac_state: {e}", file=sys.stderr)
    sys.exit(0)

STATE = os.path.join(REPO, ".harness-state/active-hypothesis.json")
AUDIT = os.path.join(REPO, ".harness-state/hypothesis-audit.jsonl")
FLAG  = os.path.join(REPO, ".harness-state/baseline-restart-required.flag")

def post_slack(msg: str) -> None:
    try:
        sys.path.insert(0, os.path.join(REPO, "lib"))
        from aristotle_slack import post_to_channel  # type: ignore
        post_to_channel("#titan-aristotle", msg)
    except Exception as e:
        print(f"[gate2-tick] slack post failed: {e}", file=sys.stderr)

# Missing secret → exit silently (install-gate2 hasn't run here yet)
try:
    chain_ok, chain_msg = verify_audit_chain(AUDIT)
except Exception as e:
    print(f"[gate2-tick] audit verify failed (probably missing secret): {e}", file=sys.stderr)
    sys.exit(0)

if not chain_ok:
    print(f"[gate2-tick] AUDIT CHAIN TAMPERED: {chain_msg}", file=sys.stderr)
    post_slack(f":rotating_light: Gate #2 audit chain BROKEN: {chain_msg}")
    sys.exit(0)

s, status = load_state(STATE)
if status == "missing":
    sys.exit(0)
if status == "tampered":
    print("[gate2-tick] state file tampered — clearing + alerting", file=sys.stderr)
    try: os.unlink(STATE)
    except OSError: pass
    audit_append(AUDIT, {"event":"tamper-detected",
                         "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                         "ts_epoch": int(time.time())})
    post_slack(":rotating_light: Gate #2 state file tampered; cleared and flagged.")
    sys.exit(0)
if status != "ok" or not s:
    sys.exit(0)

now = int(time.time())
started_struct = time.strptime(s["started_utc"], "%Y-%m-%dT%H:%M:%SZ")
started_epoch = calendar.timegm(started_struct)  # proper UTC epoch
elapsed = now - started_epoch
incident = s["incident_id"]
ac = s.get("alert_count", 0)

def ts():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

# Max attempts reached → force baseline
if s.get("attempt_n", 1) >= s.get("max_attempts", 3):
    if not os.path.exists(FLAG):
        with open(FLAG, "w") as f: f.write(incident)
        audit_append(AUDIT, {"event":"force-baseline","incident_id":incident,
                             "reason":"max_attempts_reached","ts_utc":ts(),"ts_epoch":now})
        post_slack(f":warning: Gate #2 FORCE BASELINE: incident {incident} hit max_attempts. "
                   f"Re-run bin/ssh-audit-firstpass.sh + bin/hypothesis-track.sh ack-baseline.")
    sys.exit(0)

def alert(n: int, msg: str) -> None:
    s["alert_count"] = n
    s["last_alert_utc"] = ts()
    write_state(STATE, s)
    audit_append(AUDIT, {"event":"alert","incident_id":incident,"alert_count":n,
                         "ts_utc":s["last_alert_utc"],"ts_epoch":now})
    post_slack(msg)

# T >= 90min → force baseline restart
if elapsed >= 5400:
    if not os.path.exists(FLAG):
        with open(FLAG, "w") as f: f.write(incident)
        audit_append(AUDIT, {"event":"force-baseline","incident_id":incident,
                             "reason":"90min_timeout","ts_utc":ts(),"ts_epoch":now})
        post_slack(f":rotating_light: Gate #2 T+90min on {incident}. FORCING BASELINE RESTART. "
                   f"Current hypothesis: {s['hypothesis'][:200]}")
    sys.exit(0)

# T >= 60min → escalate (ping Solon)
if elapsed >= 3600 and ac < 2:
    alert(2, f":warning: Gate #2 T+60min on {incident}. Hypothesis: {s['hypothesis'][:200]}. "
             f"Solon, please review. Auto-baseline-restart in 30min.")
    sys.exit(0)

# T >= 30min → first alert
if elapsed >= 1800 and ac < 1:
    alert(1, f":bell: Gate #2 T+30min on {incident}. Hypothesis: {s['hypothesis'][:200]}. "
             f"Aristotle, please weigh in.")
    sys.exit(0)

# below 30min → silent
PY
