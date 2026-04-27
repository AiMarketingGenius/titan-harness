#!/usr/bin/env python3
"""titan_telnyx_watcher.py — Telnyx tollfree verification status poll (4hr cadence).

On approval (status != 'Waiting For Telnyx' / pending):
  1. log_decision tag telnyx_tollfree_approved
  2. Patch CT-57 SMS path automatically IF Watchdog v0.1 already deployed
     (check for /etc/systemd/system/amg-watchdog-disk.service presence)

State at /var/lib/amg-titan/telnyx_state.json prevents re-firing on already-approved.
Logs to /var/log/amg-titan-watch.log (shared with dep watcher).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

MCP_BASE = os.environ.get("MCP_BASE", "http://localhost:3000")
TELNYX_ENV = "/etc/amg/telnyx.env"
WATCHDOG_UNIT_PATH = "/etc/systemd/system/amg-watchdog-disk.service"
TELNYX_API = "https://api.telnyx.com/v2/messaging_tollfree/verification/requests"

STATE_PATH = "/var/lib/amg-titan/telnyx_state.json"
LOG_PATH = "/var/log/amg-titan-watch.log"

# Statuses that mean approval landed (case-insensitive partial match against verificationStatus).
# Anything containing "verified" or "approved" or "live" counts. "Waiting For Telnyx" /
# "pending" / "in review" do NOT.
APPROVAL_TOKENS = ("verified", "approved", "live", "active")
PENDING_TOKENS = ("waiting", "pending", "review", "submitted")


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"[{ts}] [telnyx-watcher] {msg}\n"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line)
    except OSError:
        pass
    sys.stderr.write(line)


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_PATH)


def read_telnyx_key() -> str | None:
    if not os.path.exists(TELNYX_ENV):
        return None
    try:
        with open(TELNYX_ENV) as f:
            for line in f:
                line = line.strip()
                if line.startswith("TELNYX_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def fetch_status(api_key: str) -> dict | None:
    req = urllib.request.Request(
        f"{TELNYX_API}?page=1&page_size=10",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        log(f"telnyx api error: {e}")
        return None


def mcp_post(path: str, payload: dict) -> tuple[bool, str]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{MCP_BASE}{path}", data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, r.read().decode()
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read()[:300].decode(errors='replace')}"
    except (urllib.error.URLError, TimeoutError) as e:
        return False, str(e)


def is_approved(status_str: str) -> bool:
    s = (status_str or "").lower()
    if any(p in s for p in PENDING_TOKENS):
        return False
    return any(t in s for t in APPROVAL_TOKENS)


def patch_telnyx_send_py() -> bool:
    """Stub: actual telnyx_send.py env-loading patch is folded into CT-57 build per dispatch.
    This watcher records the trigger but does NOT modify code. CT-57 build picks it up.
    """
    return os.path.exists(WATCHDOG_UNIT_PATH)


def main(argv: list[str]) -> int:
    log("=== telnyx watcher run start ===")
    api_key = read_telnyx_key()
    if not api_key:
        log("no TELNYX_API_KEY in env — skipping")
        return 1

    resp = fetch_status(api_key)
    if not resp:
        log("no telnyx response — skipping")
        return 1

    records = resp.get("records") or []
    if not records:
        log("no verification records found")
        return 0

    state = load_state()
    seen_status = state.get("verification_status", "")

    rec = records[0]  # primary tollfree (we only have one phone)
    status = rec.get("verificationStatus", "")
    phone = (rec.get("phoneNumbers") or [{}])[0].get("phoneNumber", "")
    log(f"current status: {status!r} for {phone}")

    if status == seen_status:
        log("status unchanged — no action")
        save_state({"verification_status": status, "phone": phone, "last_checked": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
        return 0

    # Status changed — log it
    state["previous_status"] = seen_status
    state["verification_status"] = status
    state["phone"] = phone
    state["last_changed"] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    if is_approved(status):
        watchdog_deployed = patch_telnyx_send_py()
        msg = (f"Telnyx tollfree APPROVED for {phone}. "
               f"Status changed: {seen_status!r} → {status!r}. "
               f"Watchdog v0.1 deployed: {watchdog_deployed}. "
               f"telnyx_send.py env-loading patch ownership: CT-57 build (folded per Solon dispatch).")
        ok, body = mcp_post("/api/decisions", {
            "text": msg,
            "project_source": "titan",
            "rationale": "Telnyx 4hr-cadence watcher detected verificationStatus change to approval state.",
            "tags": ["telnyx_tollfree_approved", "telnyx_watcher", "ct_57_sms_path_unblocked"],
        })
        log(f"approval logged ok={ok} body={body[:200]}")
        state["approved_at"] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    else:
        # Status changed but not yet approved
        msg = f"Telnyx tollfree status CHANGED but still pending: {seen_status!r} → {status!r} for {phone}."
        ok, body = mcp_post("/api/decisions", {
            "text": msg,
            "project_source": "titan",
            "rationale": "Telnyx watcher detected non-approval status transition.",
            "tags": ["telnyx_status_change", "telnyx_watcher", "still_pending"],
        })
        log(f"transition logged ok={ok} body={body[:200]}")

    save_state(state)
    log("=== telnyx watcher run end ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
