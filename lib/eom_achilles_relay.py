#!/usr/bin/env python3
"""EOM → Achilles relay daemon.

Polls Supabase op_decisions every POLL_INTERVAL seconds for decisions tagged
`relay:eom-to-achilles`. For each new one: append the verbatim decision_text to
Achilles' inbox, log a `relay-delivered` decision back to MCP referencing the
source UUID, record state locally. Exits on HALT_RELAY tag OR no new messages
for IDLE_TIMEOUT seconds.

Env:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (sourced from titan-env.sh)

Paths:
  STATE_FILE  = .harness-state/relay/relay_state.json  (last_seen_ts, delivered_ids)
  INBOX_FILE  = achilles-harness/inbox/eom-relay.md    (append-only)
  LOG_FILE    = logs/eom_achilles_relay.log            (rotating-ish, append)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

POLL_INTERVAL = int(os.environ.get("RELAY_POLL_INTERVAL", "60"))
IDLE_TIMEOUT = int(os.environ.get("RELAY_IDLE_TIMEOUT", "7200"))  # 2h
RELAY_TAG = "relay:eom-to-achilles"
HALT_TAG = "HALT_RELAY"

TITAN_ROOT = Path("/Users/solonzafiropoulos1/titan-harness")
ACHILLES_ROOT = Path("/Users/solonzafiropoulos1/achilles-harness")
STATE_FILE = TITAN_ROOT / ".harness-state" / "relay" / "relay_state.json"
INBOX_FILE = ACHILLES_ROOT / "inbox" / "eom-relay.md"
LOG_FILE = TITAN_ROOT / "logs" / "eom_achilles_relay.log"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts} | {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(line + "\n")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"delivered_ids": [], "last_activity_ts": int(time.time())}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def supabase_headers() -> dict:
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def supabase_get(path: str, params: list) -> list:
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/" + path
    if params:
        url = url + "?" + urllib.parse.urlencode(params, safe="{},.:")
    req = urllib.request.Request(url, headers=supabase_headers())
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def supabase_post(path: str, body: dict) -> None:
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/" + path
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={**supabase_headers(), "Prefer": "return=minimal"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()


def fetch_pending(last_delivered_ids: set) -> list:
    params = [
        ("tags", f"cs.{{{RELAY_TAG}}}"),
        ("order", "created_at.asc"),
        ("limit", "50"),
    ]
    rows = supabase_get("op_decisions", params)
    return [r for r in rows if r["id"] not in last_delivered_ids]


def check_halt() -> bool:
    params = [
        ("tags", f"cs.{{{HALT_TAG}}}"),
        ("order", "created_at.desc"),
        ("limit", "1"),
    ]
    try:
        rows = supabase_get("op_decisions", params)
    except Exception as e:
        log(f"halt_check_error: {e!r}")
        return False
    if not rows:
        return False
    row = rows[0]
    # Only honor HALT issued after daemon start time (anti-staleness).
    created = row.get("created_at", "")
    return bool(created)


def deliver(row: dict) -> None:
    uuid = row["id"]
    created = row.get("created_at", "")
    text = row.get("decision_text") or ""
    tags = row.get("tags") or []
    project_source = row.get("project_source", "?")

    INBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"\n\n---\n## INCOMING EOM DIRECTIVE — {created}\n"
        f"source_uuid: {uuid}\n"
        f"project_source: {project_source}\n"
        f"tags: {', '.join(tags)}\n"
        f"relayed_by: titan-eom-achilles-relay\n"
        f"relayed_at: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n\n"
    )
    with INBOX_FILE.open("a") as f:
        f.write(header + text.rstrip() + "\n")

    log(f"delivered uuid={uuid} created={created} len={len(text)}")

    ack_text = (
        f"RELAY DELIVERED — EOM → Achilles\n"
        f"source_uuid: {uuid}\n"
        f"source_created_at: {created}\n"
        f"delivered_to: {INBOX_FILE}\n"
        f"method: file (tmux/slack unavailable on this Mac)\n"
        f"relayed_by: titan-eom-achilles-relay"
    )
    try:
        supabase_post("op_decisions", {
            "decision_text": ack_text,
            "project_source": "titan",
            "tags": ["relay-delivered", f"source-uuid:{uuid}", "eom-to-achilles"],
            "rationale": "Automated relay per standing Titan relay job. Achilles also reads MCP directly; file is belt+suspenders.",
        })
    except Exception as e:
        log(f"ack_post_error uuid={uuid} err={e!r}")


def main() -> int:
    log(f"relay_start poll={POLL_INTERVAL}s idle_timeout={IDLE_TIMEOUT}s")
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        log("FATAL env missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        return 2

    state = load_state()
    delivered = set(state.get("delivered_ids", []))
    last_activity = time.time()
    start_ts = datetime.now(timezone.utc).isoformat()
    state["started_at"] = start_ts
    save_state(state)

    while True:
        try:
            if check_halt():
                # Only halt if HALT was issued after daemon start.
                params = [("tags", f"cs.{{{HALT_TAG}}}"), ("order", "created_at.desc"), ("limit", "1")]
                rows = supabase_get("op_decisions", params)
                if rows and rows[0].get("created_at", "") >= start_ts:
                    log(f"HALT_RELAY detected uuid={rows[0]['id']}. Exiting.")
                    return 0

            pending = fetch_pending(delivered)
            if pending:
                for row in pending:
                    deliver(row)
                    delivered.add(row["id"])
                    last_activity = time.time()
                state["delivered_ids"] = sorted(delivered)
                state["last_activity_ts"] = int(last_activity)
                save_state(state)
            else:
                idle = time.time() - last_activity
                if idle >= IDLE_TIMEOUT:
                    log(f"idle_timeout reached ({int(idle)}s). Exiting.")
                    return 0
        except urllib.error.HTTPError as e:
            log(f"http_error status={e.code} body={e.read()[:200]!r}")
        except Exception as e:
            log(f"loop_error {e!r}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
