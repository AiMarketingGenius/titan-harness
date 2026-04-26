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
import hashlib
import json
import os
import pathlib
import re
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

# Fix 3 (CT-0426 2026-04-26): notifier was flooding inbox with 12 copies of the
# same Mercury fake-completion in 5 min. Cursor seen_ids worked at decision_id
# level but Mercury was emitting the same TEXT under fresh decision_ids each
# poll. New dedupe layer:
#   1. content_hash dedupe (sha256 of text+first-3-tags) — same content = drop
#   2. per-(agent, task_id) cooldown — only one notification per pair per 5 min
#   3. global rate limit — max 6 notifications per 60s across all sources
COOLDOWN_SECONDS = 5 * 60  # 5 min per (agent, task_id)
GLOBAL_RATE_WINDOW_S = 60
GLOBAL_RATE_MAX = 6
TASK_ID_RE = re.compile(r"\bCT-\d{4}-\d{2,3}\b")

INTERESTING_TAGS = {
    "hercules", "mercury-proof",
    "hercules-mcp-bridge",
    "polling-doctrine-violation",
    "factory-stall", "false-completion",
    "aletheia-violation", "cerberus-incident",
    "ploutos-signoff", "hephaestus-signoff",
    "rotation-failure", "secret-rotation-slack",
    "secret-rotation-supabase", "telnyx-bridge-live",
    "aimg-track-a-complete", "aimg-track-b-complete",
    "aimg-track-c-complete", "aimg-track-d-complete",
    "aimg-track-e-complete", "aimg-track-f-complete",
    "aimg-finalization-2026-04-26-complete",
}
# Operational telemetry — never notify, just log
NOISE_TAGS = {
    "agent-dispatch-bridge",  # routine cron dispatches
    "warden-violation",        # warden runs every 10min on 100+ stale tasks
    "mercury-delegated",       # internal Mercury sub-task spawn
    "hercules-dispatch",       # bridge ingest log (firehose when many dispatches)
    "heartbeat",               # hourly heartbeat from Dr SEO
    "hercules-shared-file",    # folder sync indexing
    "auto-approve",
    "tcc-auto-approve",
}
P0_TAGS = {
    "factory-stall", "agent-down", "security-breach",
    "rotation-failure", "polling-doctrine-violation",
    "cerberus-incident", "aletheia-violation",
    "p0", "urgent",
}
P1_TAGS = {"mercury-proof", "task-complete", "p1",
           "secret-rotation-slack", "secret-rotation-supabase",
           "telnyx-bridge-live", "aimg-track-a-complete",
           "aimg-track-b-complete", "aimg-track-c-complete",
           "aimg-track-d-complete", "aimg-track-e-complete",
           "aimg-track-f-complete"}


def _log(msg: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    sys.stderr.write(line)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line)


def _load_cursor() -> dict:
    if not CURSOR_FILE.exists():
        return {
            "last_seen_ts": None,
            "last_seen_id": None,
            "seen_ids": [],
            "seen_content_hashes": {},   # {hash: ts_iso} — Fix 3 dedupe layer 1
            "task_cooldown": {},         # {"agent::task_id": ts_iso} — Fix 3 layer 2
            "rate_window": [],           # [ts_iso, ...] — Fix 3 layer 3
        }
    try:
        s = json.loads(CURSOR_FILE.read_text())
        s.setdefault("seen_content_hashes", {})
        s.setdefault("task_cooldown", {})
        s.setdefault("rate_window", [])
        return s
    except Exception:
        return {
            "last_seen_ts": None, "last_seen_id": None, "seen_ids": [],
            "seen_content_hashes": {}, "task_cooldown": {}, "rate_window": [],
        }


def _save_cursor(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state["seen_ids"] = (state.get("seen_ids") or [])[-200:]
    # Prune content hashes older than 1 hour
    now = datetime.now(tz=timezone.utc)
    cutoff_iso = (now - timedelta(hours=1)).isoformat()
    state["seen_content_hashes"] = {
        h: ts for h, ts in (state.get("seen_content_hashes") or {}).items()
        if ts > cutoff_iso
    }
    # Prune cooldowns older than 1 hour
    state["task_cooldown"] = {
        k: ts for k, ts in (state.get("task_cooldown") or {}).items()
        if ts > cutoff_iso
    }
    # Prune rate window to last 60s
    rate_cutoff_iso = (now - timedelta(seconds=GLOBAL_RATE_WINDOW_S)).isoformat()
    state["rate_window"] = [ts for ts in (state.get("rate_window") or []) if ts > rate_cutoff_iso]
    # Atomic write with fsync
    tmp = CURSOR_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    fd = os.open(str(tmp), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, CURSOR_FILE)


def _content_hash(decision: dict) -> str:
    """Stable hash of decision content (text + first 3 tags + project_source).
    Catches the case where Mercury emits the same fake completion under fresh
    decision_ids every poll."""
    text = (decision.get("text") or "").strip()[:500]
    tags = sorted(str(t) for t in (decision.get("tags") or []))[:3]
    src = decision.get("project_source") or ""
    blob = f"{src}::{text}::{'|'.join(tags)}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _extract_task_id(decision: dict) -> str | None:
    """Pull a CT-XXXX-XX from decision text or tags for cooldown bucketing."""
    text = (decision.get("text") or "") + " " + (decision.get("rationale") or "")
    m = TASK_ID_RE.search(text)
    if m:
        return m.group(0)
    for t in (decision.get("tags") or []):
        ts = str(t)
        if ts.startswith("task:"):
            tid = ts.split(":", 1)[1].upper()
            if TASK_ID_RE.fullmatch(tid):
                return tid
    return None


def _under_cooldown(state: dict, agent: str, task_id: str) -> bool:
    if not task_id:
        return False
    key = f"{agent}::{task_id}"
    last_ts = (state.get("task_cooldown") or {}).get(key)
    if not last_ts:
        return False
    try:
        last = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
    except Exception:
        return False
    return (datetime.now(tz=timezone.utc) - last).total_seconds() < COOLDOWN_SECONDS


def _record_cooldown(state: dict, agent: str, task_id: str) -> None:
    if not task_id:
        return
    state.setdefault("task_cooldown", {})[f"{agent}::{task_id}"] = (
        datetime.now(tz=timezone.utc).isoformat()
    )


def _rate_limited(state: dict) -> bool:
    """Global last-line defense: max 6 notifications per 60s window."""
    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(seconds=GLOBAL_RATE_WINDOW_S)
    cutoff_iso = cutoff.isoformat()
    recent = [ts for ts in (state.get("rate_window") or []) if ts > cutoff_iso]
    state["rate_window"] = recent
    return len(recent) >= GLOBAL_RATE_MAX


def _record_rate(state: dict) -> None:
    state.setdefault("rate_window", []).append(datetime.now(tz=timezone.utc).isoformat())


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
    # NOISE filter wins — never notify on operational telemetry even if the
    # text contains common keywords. This stops the cron firehose from
    # flooding Solon's iPhone with agent-dispatch-bridge entries.
    if tags & NOISE_TAGS:
        return False
    if tags & INTERESTING_TAGS:
        return True
    # Conservative text fallback — only fire if text mentions a HUMAN-action
    # keyword (alert, escalate, blocked, decision needed, hard limit), NOT
    # routine ops like "dispatch:" or "proof packet" which fire too often.
    text = (decision.get("text") or "").lower()
    if any(k in text for k in (
        "alert:", "escalat", "hard limit", "decision needed",
        "p0:", "urgent:", "blocked on solon",
    )):
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


def telenix_send(priority: str, summary: str) -> None:
    """Telnyx SMS via scripts/telnyx_send.py (added 2026-04-26).
    Honors quiet hours upstream — only invoked for P0 always, P1 batched, P2 not at all.
    Best-effort + non-blocking — failure to SMS does not stop the notifier loop."""
    sender = HOME / "titan-harness" / "scripts" / "telnyx_send.py"
    if not sender.exists():
        return
    try:
        subprocess.Popen(
            ["python3", str(sender), summary, "--priority", priority],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        _log(f"telnyx_send spawn failed: {e!r}")


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
    seen_hashes = state.get("seen_content_hashes") or {}
    decisions = fetch_recent(count=20)
    quiet = _is_quiet_hours_now_eastern()
    out = {
        "scanned": len(decisions), "notified": 0,
        "p0": 0, "p1": 0, "p2": 0,
        "skipped_quiet": 0, "skipped_dup_id": 0, "skipped_dup_content": 0,
        "skipped_cooldown": 0, "skipped_rate_limit": 0,
    }
    for d in decisions:
        did = d.get("id") or d.get("decision_id") or (d.get("created_at", "") + d.get("text", "")[:40])
        # Layer 0: decision_id seen
        if did in seen_ids:
            out["skipped_dup_id"] += 1
            continue
        if not is_interesting(d):
            seen_ids.add(did)
            continue
        # Fix 3 Layer 1: content-hash dedupe (catches Mercury re-emitting same
        # text under fresh decision_ids every poll)
        chash = _content_hash(d)
        if chash in seen_hashes:
            out["skipped_dup_content"] += 1
            seen_ids.add(did)
            _log(f"DEDUPE_CONTENT did={str(did)[:20]} hash={chash} (already notified for same content)")
            continue
        # Fix 3 Layer 2: per-(agent, task_id) cooldown
        agent = d.get("project_source") or "unknown"
        task_id = _extract_task_id(d) or ""
        if _under_cooldown(state, agent, task_id):
            out["skipped_cooldown"] += 1
            seen_ids.add(did)
            seen_hashes[chash] = datetime.now(tz=timezone.utc).isoformat()
            _log(f"COOLDOWN agent={agent} task={task_id} did={str(did)[:20]} (5-min window)")
            continue
        priority = classify_priority(d)
        if quiet and priority != "P0":
            out["skipped_quiet"] += 1
            seen_ids.add(did)
            seen_hashes[chash] = datetime.now(tz=timezone.utc).isoformat()
            continue
        # Fix 3 Layer 3: global rate limit (last-line defense)
        if _rate_limited(state):
            out["skipped_rate_limit"] += 1
            _log(f"RATE_LIMITED did={str(did)[:20]} ({GLOBAL_RATE_MAX}/{GLOBAL_RATE_WINDOW_S}s exceeded)")
            # Don't mark seen — try again next poll when window clears
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
        seen_hashes[chash] = datetime.now(tz=timezone.utc).isoformat()
        _record_cooldown(state, agent, task_id)
        _record_rate(state)
        _log(f"NOTIFIED {priority} → {path.name}")
    state["seen_ids"] = list(seen_ids)
    state["seen_content_hashes"] = seen_hashes
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
