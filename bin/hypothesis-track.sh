#!/usr/bin/env bash
# bin/hypothesis-track.sh
# Gate #2 v1.1 mandatory write path for hypothesis state.
#
# Subcommands:
#   start    --incident ID --hypothesis STR --baseline PATH
#   attempt  --incident ID --new-hypothesis STR
#   end      --incident ID --resolution STR
#   status   [--incident ID]
#   ack-baseline --incident ID --baseline PATH    (after forced restart)
#
# Enforces:
#   - HMAC signing on every mutation
#   - Sequential attempt_n (1 → 2 → 3, no skips)
#   - 4h dedup on hypothesis text per incident
#   - Max 3 attempts per incident (beyond → force baseline restart)
#   - Baseline freshness check (<24h, valid ssh-firstpass.md)
#   - flock on state file for concurrency safety

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${REPO}/.harness-state"
STATE_FILE="${STATE_DIR}/active-hypothesis.json"
AUDIT_LOG="${STATE_DIR}/hypothesis-audit.jsonl"
BASELINE_FLAG="${STATE_DIR}/baseline-restart-required.flag"
LOCK="${STATE_DIR}/.hypothesis.lock"
DEDUP_WINDOW_SEC=14400    # 4h
MAX_ATTEMPTS=3

mkdir -p "$STATE_DIR"

SUB="${1:-}"
[[ -z "$SUB" ]] && { echo "usage: $0 {start|attempt|end|status|ack-baseline} [opts]" >&2; exit 2; }
shift

INCIDENT=""
HYPOTHESIS=""
NEW_HYPOTHESIS=""
BASELINE=""
RESOLUTION=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --incident)        INCIDENT="$2"; shift 2 ;;
    --hypothesis)      HYPOTHESIS="$2"; shift 2 ;;
    --new-hypothesis)  NEW_HYPOTHESIS="$2"; shift 2 ;;
    --baseline)        BASELINE="$2"; shift 2 ;;
    --resolution)      RESOLUTION="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# --- acquire lock (portable: flock on Linux, mkdir fallback on macOS) ---
if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK"
  if ! flock -w 10 9; then
    echo "hypothesis-track: could not acquire lock within 10s" >&2
    exit 3
  fi
else
  LOCKDIR="${STATE_DIR}/.hypothesis.lock.d"
  acquired=0
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if mkdir "$LOCKDIR" 2>/dev/null; then acquired=1; break; fi
    sleep 1
  done
  if (( acquired == 0 )); then
    echo "hypothesis-track: could not acquire lock within 10s" >&2
    exit 3
  fi
  trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT
fi

PY="${REPO}/lib"
export PYTHONPATH="${PY}:${PYTHONPATH:-}"

runpy() {
  python3 - "$@"
}

sha_of() {
  shasum -a 256 "$1" 2>/dev/null | awk '{print $1}' || sha256sum "$1" | awk '{print $1}'
}

now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
now_epoch() { date +%s; }

verify_baseline_path() {
  local path="$1"
  [[ -f "$path" ]] || { echo "baseline path missing: $path" >&2; return 1; }
  grep -q 'ssh_audit_firstpass:' "$path" || {
    echo "baseline does not look like ssh-firstpass.md output: $path" >&2
    return 1
  }
  # mtime <24h
  local mt now age
  mt="$(stat -f %m "$path" 2>/dev/null || stat -c %Y "$path")"
  now="$(now_epoch)"; age=$(( now - mt ))
  (( age <= 86400 )) || { echo "baseline >24h old (age=${age}s)" >&2; return 1; }
}

case "$SUB" in
  start)
    [[ -z "$INCIDENT" || -z "$HYPOTHESIS" || -z "$BASELINE" ]] && {
      echo "start: --incident, --hypothesis, --baseline required" >&2; exit 2
    }
    if [[ -f "$BASELINE_FLAG" ]]; then
      echo "start REJECTED: baseline-restart-required.flag present — run ack-baseline first" >&2
      exit 4
    fi
    verify_baseline_path "$BASELINE" || exit 5
    BSHA="$(sha_of "$BASELINE")"

    # Dedup: any audit entry in last 4h for same incident with same hypothesis?
    runpy <<PY
import json, os, sys, time, hashlib, hmac
sys.path.insert(0, "${PY}")
from hmac_state import audit_append, write_state, load_state, verify_audit_chain

log = "${AUDIT_LOG}"
incident = """${INCIDENT}"""
hyp = """${HYPOTHESIS}"""
now = int(time.time())
win = ${DEDUP_WINDOW_SEC}

dup = False
if os.path.exists(log):
    with open(log) as f:
        for raw in f:
            try: d = json.loads(raw)
            except Exception: continue
            if d.get("incident_id") != incident: continue
            if d.get("hypothesis") != hyp and d.get("new_hypothesis") != hyp: continue
            t = d.get("ts_epoch", 0)
            if now - t <= win:
                dup = True; break

if dup:
    print("hypothesis-track: DEDUP — same hypothesis for this incident within 4h; pick a different one", file=sys.stderr)
    sys.exit(6)

existing, status = load_state("${STATE_FILE}")
if existing and status == "ok" and existing.get("incident_id") != incident:
    print(f"hypothesis-track: another active hypothesis exists for incident {existing.get('incident_id')}; end it first", file=sys.stderr)
    sys.exit(7)
if status == "tampered":
    print("hypothesis-track: state file tampered; refusing to overwrite without explicit ack-baseline", file=sys.stderr)
    sys.exit(8)

state = {
  "incident_id": incident,
  "hypothesis": hyp,
  "started_utc": "${START_UTC:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}",
  "attempt_n": 1,
  "max_attempts": ${MAX_ATTEMPTS},
  "last_alert_utc": None,
  "alert_count": 0,
  "baseline_ref": "${BASELINE}",
  "baseline_sha256": "${BSHA}"
}
write_state("${STATE_FILE}", state)
audit_append(log, {
  "event": "start", "incident_id": incident, "hypothesis": hyp,
  "attempt_n": 1, "baseline_sha256": "${BSHA}",
  "ts_utc": state["started_utc"], "ts_epoch": now
})
print("hypothesis-track: started incident={} attempt=1".format(incident))
PY
    ;;

  attempt)
    [[ -z "$INCIDENT" || -z "$NEW_HYPOTHESIS" ]] && {
      echo "attempt: --incident, --new-hypothesis required" >&2; exit 2
    }
    runpy <<PY
import json, sys, time, os
sys.path.insert(0, "${PY}")
from hmac_state import load_state, write_state, audit_append

s, status = load_state("${STATE_FILE}")
if status != "ok" or not s:
    print(f"attempt: no valid state (status={status})", file=sys.stderr); sys.exit(9)
if s["incident_id"] != "${INCIDENT}":
    print(f"attempt: state belongs to different incident ({s['incident_id']})", file=sys.stderr); sys.exit(10)

# Sequential attempt_n
new_n = s["attempt_n"] + 1
if new_n > s["max_attempts"]:
    print(f"attempt: max_attempts reached — write baseline-restart-required.flag", file=sys.stderr)
    open("${BASELINE_FLAG}", "w").write(s["incident_id"])
    sys.exit(11)

# Dedup across audit log (4h window)
now = int(time.time()); win = ${DEDUP_WINDOW_SEC}
with open("${AUDIT_LOG}") as f:
    for raw in f:
        try: d = json.loads(raw)
        except Exception: continue
        if d.get("incident_id") != "${INCIDENT}": continue
        if d.get("hypothesis") != """${NEW_HYPOTHESIS}""" and d.get("new_hypothesis") != """${NEW_HYPOTHESIS}""": continue
        if now - d.get("ts_epoch", 0) <= win:
            print("attempt: DEDUP — already tried this hypothesis <4h ago", file=sys.stderr); sys.exit(6)

s["hypothesis"] = """${NEW_HYPOTHESIS}"""
s["attempt_n"] = new_n
write_state("${STATE_FILE}", s)
audit_append("${AUDIT_LOG}", {
  "event":"attempt","incident_id":"${INCIDENT}",
  "new_hypothesis":"""${NEW_HYPOTHESIS}""","attempt_n":new_n,
  "ts_utc":"$(now_iso)","ts_epoch":now
})
print(f"hypothesis-track: attempt_n={new_n}")
PY
    ;;

  end)
    [[ -z "$INCIDENT" || -z "$RESOLUTION" ]] && {
      echo "end: --incident, --resolution required" >&2; exit 2
    }
    runpy <<PY
import os, sys, time, json
sys.path.insert(0, "${PY}")
from hmac_state import load_state, audit_append

s, status = load_state("${STATE_FILE}")
if s and s.get("incident_id") == "${INCIDENT}":
    os.unlink("${STATE_FILE}")
audit_append("${AUDIT_LOG}", {
  "event":"end","incident_id":"${INCIDENT}",
  "resolution":"""${RESOLUTION}""",
  "ts_utc":"$(now_iso)","ts_epoch":int(time.time())
})
print("hypothesis-track: ended")
PY
    ;;

  ack-baseline)
    [[ -z "$INCIDENT" || -z "$BASELINE" ]] && {
      echo "ack-baseline: --incident, --baseline required" >&2; exit 2
    }
    verify_baseline_path "$BASELINE" || exit 5
    BSHA="$(sha_of "$BASELINE")"
    runpy <<PY
import os, sys, time, json
sys.path.insert(0, "${PY}")
from hmac_state import audit_append
if os.path.exists("${BASELINE_FLAG}"):
    os.unlink("${BASELINE_FLAG}")
audit_append("${AUDIT_LOG}", {
  "event":"ack-baseline","incident_id":"${INCIDENT}",
  "baseline_sha256":"${BSHA}","baseline_ref":"${BASELINE}",
  "ts_utc":"$(now_iso)","ts_epoch":int(time.time())
})
print("hypothesis-track: baseline re-acked; hypothesis chases unblocked")
PY
    ;;

  status)
    runpy <<PY
import sys, json
sys.path.insert(0, "${PY}")
from hmac_state import load_state, verify_audit_chain

s, status = load_state("${STATE_FILE}")
chain_ok, msg = verify_audit_chain("${AUDIT_LOG}")
print("state:", status)
if s: print(json.dumps(s, indent=2))
print("audit_chain:", "OK" if chain_ok else "TAMPERED", "-", msg)
PY
    ;;

  *)
    echo "unknown subcommand: $SUB" >&2; exit 2 ;;
esac
