#!/usr/bin/env python3
"""atlas-agent.py — Mac-side liveness daemon.

Background: the original atlas-agent.py was lost in a refactor; the launchd
plist at ~/Library/LaunchAgents/io.aimg.atlas-agent.plist kept invoking a
non-existent file, producing exit 2 in an infinite keepalive loop. This file
restores a minimal but useful body so the plist runs clean and Argus has a
positive signal to monitor.

Today's job (intentionally narrow):
  - Heartbeat every POLL_INTERVAL_S to MCP /api/decisions tagged
    atlas-agent-heartbeat — gives queue-health monitor + Argus probe a
    fingerprint to detect death.
  - Tail MCP /api/recent-decisions for tags containing 'iris-mail' or
    'titan-assigned' (operator-class tasks Iris no longer auto-claims).
    Pretty-print one line per row to stdout for the Mac terminal log.

Out-of-scope today (handled by other services):
  - Builder execution: each builder agent has its own tmux supervisor on
    the VPS (CT-0427-97/98).
  - Iris claim loop: VPS iris-daemon.service.
  - Hercules outbox: com.amg.hercules-mcp-bridge launchd job.

Exit codes:
  0  clean signal-driven exit
  1  fatal config error (no MCP base, etc.)
  2  ENOENT-equivalent — should never appear once this file exists
"""
from __future__ import annotations

import json
import os
import signal
import socket
import sys
import time
from datetime import datetime, timezone
from urllib import request as urlreq
from urllib.error import HTTPError, URLError

MCP_BASE = os.environ.get("ATLAS_AGENT_MCP_BASE", "https://memory.aimarketinggenius.io")
POLL_INTERVAL_S = int(os.environ.get("ATLAS_AGENT_POLL_S", "60"))
TAIL_RECENT_LIMIT = int(os.environ.get("ATLAS_AGENT_TAIL_LIMIT", "5"))

_running = True
_seen_decision_ids: set[str] = set()


def _stop(signum: int, _frame) -> None:
    global _running
    log(f"signal {signum} — draining and exiting")
    _running = False


signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


def heartbeat(poll_count: int) -> str:
    body = json.dumps({
        "text": f"atlas-agent heartbeat poll={poll_count} host={socket.gethostname()} pid={os.getpid()}",
        "project_source": "titan",
        "tags": ["atlas-agent-heartbeat", "mac-side", "ct-0428-recovery"],
    }).encode("utf-8")
    req = urlreq.Request(
        f"{MCP_BASE}/api/decisions",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlreq.urlopen(req, timeout=8) as resp:
            return f"HTTP {resp.status}"
    except HTTPError as exc:
        return f"HTTP_ERR {exc.code}"
    except URLError as exc:
        return f"URL_ERR {exc.reason}"
    except Exception as exc:
        return f"UNEXPECTED {exc!r}"


def tail_recent_iris_mail() -> None:
    req = urlreq.Request(
        f"{MCP_BASE}/api/recent-decisions-json?limit={TAIL_RECENT_LIMIT}&q=iris-mail",
        method="GET",
    )
    try:
        with urlreq.urlopen(req, timeout=8) as resp:
            data = json.load(resp)
    except HTTPError as exc:
        if exc.code == 404:
            # Endpoint unavailable in this MCP build — degrade silently.
            return
        log(f"tail HTTPError: {exc}")
        return
    except (URLError, json.JSONDecodeError, Exception) as exc:
        log(f"tail err: {exc!r}")
        return

    rows = data if isinstance(data, list) else data.get("decisions") or data.get("data") or []
    for row in rows[-TAIL_RECENT_LIMIT:]:
        rid = str(row.get("id", ""))
        if rid in _seen_decision_ids:
            continue
        _seen_decision_ids.add(rid)
        text = (row.get("text") or row.get("decision_text") or "")[:140]
        tags = row.get("tags") or []
        log(f"IRIS-MAIL id={rid[:8]} tags={tags} text={text}")


def main() -> int:
    if not MCP_BASE:
        print("FATAL: ATLAS_AGENT_MCP_BASE unset", file=sys.stderr)
        return 1

    log(f"atlas-agent UP host={socket.gethostname()} pid={os.getpid()} mcp={MCP_BASE} interval={POLL_INTERVAL_S}s")
    poll = 0
    while _running:
        poll += 1
        status = heartbeat(poll)
        log(f"heartbeat poll={poll} -> {status}")
        try:
            tail_recent_iris_mail()
        except Exception as exc:  # never let tailing kill the loop
            log(f"tail crashed (recovered): {exc!r}")
        for _ in range(POLL_INTERVAL_S):
            if not _running:
                break
            time.sleep(1)
    log("atlas-agent EXIT clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
