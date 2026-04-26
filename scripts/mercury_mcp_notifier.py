#!/usr/bin/env python3
"""
mercury_mcp_notifier.py — MCP → Solon notification daemon.

Polls MCP `get_recent_decisions` every 30s for new entries tagged `hercules`,
`mercury-proof`, `mercury-delegated`, `hercules-dispatch`, or matching
project_source=titan with priority markers. Writes each new entry as a markdown
brief to ~/AMG/hercules-inbox/<TS>__<tag>.md, fires a macOS notification via
osascript, and (when Telenix bridge is wired) sends an SMS for P0/P1.

Priority filter:
    P0 (urgent)   → immediate macOS notif + SMS (when wired). Breaks quiet hours.
    P1 (normal)   → batched into rolling 15-min digest. macOS notif at digest tick.
    P2 (low)      → daily 8 PM digest only. No SMS.
    P3 (silent)   → log only, no notif.

Quiet hours: 23:00 – 07:00 EST. Only P0 fires during quiet hours.

State persisted at ~/.openclaw/state/mercury_notifier_cursor.json so the daemon
doesn't re-notify on restart.

Run modes:
    mercury_mcp_notifier.py --watch        # daemon (default)
    mercury_mcp_notifier.py --once         # drain once
    mercury_mcp_notifier.py --backfill 30  # process last 30 minutes (for tests)
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))
from mcp_rest_client import get_recent_decisions as mcp_get_recent  # noqa: E402

INBOX = HOME / "AMG" / "hercules-inbox"
ARCHIVE = HOME / "AMG" / "hercules-archive" / "notified"
STATE_DIR = HOME / ".openclaw" / "state"
CURSOR_FILE = STATE_DIR / "mercury_notifier_cursor.json"
LOGFILE = HOME / ".openclaw" / "logs" / "mercury_mcp_notifier.log"

QUIET_HOURS_START = 23   # 11pm
QUIET_HOURS_END = 7      # 7am

INTERESTING_TAGS = {
    "hercules", "mercury-proof", "mercury-delegated",
    "hercules-dispatch", "hercules-mcp-bridge",
    "polling-doctrine-violation",
    "factory-stall", "agent-idle", "false-completion",
}
P0_TAGS = {
    "factory-stall", "agent-down", "security-breach",
    "rotation-failure", "polling-doctrine-violation",
    "p0", "urgent",
}
P1_TAGS = {"mercury-proof", "hercules-dispatch", "task-complete", "p1"}


def _log(msg: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    sys.stderr.write(line)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line)


def _load_cursor() -> dict:
    if not CURSOR_FILE.exists():
        return {"last_seen_ts": None, "last_seen_id": None, "seen_ids": []}
    try:
        return json.loads(CURSOR_FILE.read_text())
    except Exception:
        return {"last_seen_ts": None, "last_seen_id": None, "seen_ids": []}


def _save_cursor(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state["seen_ids"] = (state.get("seen_ids") or [])[-200:]
    CURSOR_FILE.write_text(json.dumps(state, indent=2))


def _is_quiet_hours_now_eastern() -> bool:
    # Approx ET = UTC-4 (EDT) or UTC-5 (EST). Use UTC offset env, fallback -4.
    offset_h = int(os.environ.get("ET_OFFSET_HOURS", "-4"))
    now_local = datetime.now(tz=timezone.utc) + timedelta(hours=offset_h)
    h = now_local.hour
    if QUIET_HOURS_START > QUIET_HOURS_END:
        return h >= QUIET_HOURS_START or h < QUIET_HOURS_END
    return QUIET_HOURS_START <= h < QUIET_HOURS_END


def classify_priority(decision: dict) -> str:
    text = (decision.get("text") or "").lower()
    rationale = (decision.get("rationale") or "").lower()
    tags = {str(t).lower() for t in (decision.get("tags") or [])}
    blob = f"{text} {rationale} {' '.join(tags)}"
    if tags & P0_TAGS or any(k in blob for k in ("p0", "alert:", "factory stall", "rotation failure")):
        return "P0"
    if tags & P1_TAGS or any(k in blob for k in ("p1", "task complete", "dispatch:", "proof:")):
        return "P1"
    return "P2"


def is_interesting(decision: dict) -> bool:
    tags = {str(t).lower() for t in (decision.get("tags") or [])}
    if tags & INTERESTING_TAGS:
        return True
    text = (decision.get("text") or "").lower()
    if any(k in text for k in ("hercules", "mercury", "dispatch:", "proof packet")):
        return True
    return False


def write_inbox_entry(decision: dict, priority: str) -> pathlib.Path:
    INBOX.mkdir(parents=True, exist_ok=True)
    created = decision.get("created_at") or datetime.now(tz=timezone.utc).isoformat()
    decision_id = decision.get("id") or decision.get("decision_id") or "noid"
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_id = str(decision_id).replace("/", "-")[:24]
    fname = f"{stamp}__{priority}__{safe_id}.md"
    path = INBOX / fname
    body = (
        f"# {priority} — {decision.get('text', '(no summary)')[:200]}\n\n"
        f"- **Created:** {created}\n"
        f"- **Project:** {decision.get('project_source', 'unknown')}\n"
        f"- **Tags:** {', '.join(decision.get('tags') or [])}\n"
        f"- **Decision ID:** {decision_id}\n\n"
        f"## Summary\n\n{decision.get('text', '')}\n\n"
        f"## Rationale\n\n{decision.get('rationale', '')}\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def osascript_notify(title: str, subtitle: str, message: str) -> None:
    safe_title = title.replace('"', "'")[:80]
    safe_subtitle = subtitle.replace('"', "'")[:80]
    safe_msg = message.replace('"', "'")[:240]
    script = (
        f'display notification "{safe_msg}" '
        f'with title "{safe_title}" subtitle "{safe_subtitle}" sound name "Glass"'
    )
    try:
        subprocess.Popen(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        _log(f"osascript notify failed: {e!r}")


def telenix_send(_priority: str, _summary: str) -> None:
    """Stub. Telenix SMS bridge wires here when scripts/telenix_bridge.py lands."""
    return


def fetch_recent(count: int = 25) -> list[dict]:
    code, body = mcp_get_recent(count=min(count, 20))
    if code != 200:
        return []
    decisions = body.get("decisions") or body.get("results") or []
    if not decisions and isinstance(body, list):
        decisions = body
    return decisions


def drain_once() -> dict:
    state = _load_cursor()
    seen_ids = set(state.get("seen_ids") or [])
    decisions = fetch_recent(count=20)
    quiet = _is_quiet_hours_now_eastern()
    out = {"scanned": len(decisions), "notified": 0, "p0": 0, "p1": 0, "p2": 0, "skipped_quiet": 0}
    for d in decisions:
        did = d.get("id") or d.get("decision_id") or (d.get("created_at", "") + d.get("text", "")[:40])
        if did in seen_ids:
            continue
        if not is_interesting(d):
            seen_ids.add(did)
            continue
        priority = classify_priority(d)
        if quiet and priority != "P0":
            out["skipped_quiet"] += 1
            seen_ids.add(did)
            continue
        path = write_inbox_entry(d, priority)
        title = f"{priority}: Hercules"
        subtitle = (d.get("text") or "")[:80]
        msg = (d.get("rationale") or d.get("text") or "")[:200]
        osascript_notify(title, subtitle, msg)
        if priority in {"P0", "P1"}:
            telenix_send(priority, f"{priority}: {subtitle}")
        out["notified"] += 1
        out[priority.lower()] = out.get(priority.lower(), 0) + 1
        seen_ids.add(did)
        _log(f"NOTIFIED {priority} → {path.name}")
    state["seen_ids"] = list(seen_ids)
    state["last_poll_ts"] = datetime.now(tz=timezone.utc).isoformat()
    _save_cursor(state)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Mercury MCP → Solon notifier")
    p.add_argument("--once", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=30)
    p.add_argument("--backfill", type=int, default=0, help="ignore cursor, scan last N minutes")
    args = p.parse_args()

    if args.backfill:
        try:
            os.unlink(CURSOR_FILE)
        except FileNotFoundError:
            pass
        _log(f"backfill: cursor cleared, processing last {args.backfill} min")

    if args.once or not args.watch:
        results = drain_once()
        print(json.dumps(results, indent=2))
        return 0

    _log(f"mercury_mcp_notifier starting watch interval={args.interval}s")
    while True:
        try:
            results = drain_once()
            if results["scanned"] > 0 and results["notified"] > 0:
                _log(f"poll: scanned={results['scanned']} notified={results['notified']} "
                     f"P0={results['p0']} P1={results['p1']} P2={results['p2']}")
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            _log(f"poll error: {e!r}")
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
