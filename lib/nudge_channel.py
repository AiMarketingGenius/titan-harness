"""
titan-harness/lib/nudge_channel.py

CT-0412-07 — #titan-nudge Slack channel (Viktor-persona conversational nudge).

Short, single-line, dry-tone soft-urgency nudges to Solon. Distinct from:
    - #titan-aristotle (strategy / grading)
    - Approval Broker (Hard Limits via DM + Ntfy + buttons, bidirectional)

Triggers (any of these fire a nudge):
    - Doctrine file stale > 14 days (last-research marker check)
    - RADAR item parked > 7 days
    - Governance Health Score drop > 5 points
    - n8n DLQ backlog > 50
    - SLO burn-rate > 5% in 24h window
    - log_decision with severity=medium tag
    - Custom caller via fire_nudge()

Rate-limit:
    - Max 6 nudges per rolling hour
    - Max 30 nudges per day
    - Excess messages roll into the daily SOLON_OS_CONTROL_LOOP digest
      (appended to /opt/amg/daily-digest/YYYY-MM-DD.md)

Persona:
    - Concise, dry, punctual
    - Single line (no bullet lists, no CTAs)
    - No @Solon tag unless severity=high
    - Signed "— Titan" at end

Public API:
    fire_nudge(reason, source=None, severity="medium", dry_run=False) -> dict
    check_and_fire_triggers() -> dict  # runs all trigger checks, fires eligible
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


NUDGE_DB = Path(os.environ.get("AMG_NUDGE_DB", "/var/lib/amg-nudge/rate_limit.db"))
DIGEST_DIR = Path(os.environ.get("AMG_NUDGE_DIGEST_DIR", "/opt/amg/daily-digest"))
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN_NUDGE", os.environ.get("SLACK_BOT_TOKEN", ""))
SLACK_NUDGE_CHANNEL = os.environ.get("SLACK_NUDGE_CHANNEL", "#titan-nudge")
MCP_ENDPOINT = os.environ.get("MCP_ENDPOINT", "https://memory.aimarketinggenius.io")

HOURLY_LIMIT = 6
DAILY_LIMIT = 30
DOCTRINE_STALE_DAYS = 14
RADAR_PARKED_DAYS = 7
GOVERNANCE_DROP_THRESHOLD = 5.0
DLQ_THRESHOLD = 50
SLO_BURN_THRESHOLD_PCT = 5.0


# ---------------------------------------------------------------------------
# Rate-limit store
# ---------------------------------------------------------------------------

class RateLimitStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.db_path, timeout=10)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _init(self):
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS nudges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_utc TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    source TEXT,
                    severity TEXT,
                    posted INTEGER NOT NULL DEFAULT 0
                )
            """)

    def record(self, reason: str, source: Optional[str], severity: str, posted: bool) -> int:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        with self._conn() as c:
            cursor = c.execute(
                "INSERT INTO nudges (ts_utc, reason, source, severity, posted) VALUES (?, ?, ?, ?, ?)",
                (now, reason, source, severity, 1 if posted else 0),
            )
            return cursor.lastrowid

    def recent_count(self, minutes_ago: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat(timespec="seconds").replace("+00:00", "Z")
        with self._conn() as c:
            r = c.execute(
                "SELECT COUNT(*) FROM nudges WHERE posted=1 AND ts_utc > ?", (cutoff,)
            ).fetchone()
        return int(r[0]) if r else 0

    def overflow_items(self, since_ts: str) -> list[dict[str, Any]]:
        """Items that hit rate-limit + got rolled to digest instead."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT ts_utc, reason, source, severity FROM nudges WHERE posted=0 AND ts_utc > ? ORDER BY ts_utc",
                (since_ts,),
            ).fetchall()
        return [{"ts_utc": r[0], "reason": r[1], "source": r[2], "severity": r[3]} for r in rows]


# ---------------------------------------------------------------------------
# Slack posting (Viktor-persona)
# ---------------------------------------------------------------------------

VIKTOR_PREFIXES = [
    "",  # no prefix most of the time
    "heads up — ",
    "noting — ",
    "fyi — ",
    "",
    "",
]


def _viktor_format(reason: str, severity: str) -> str:
    """Format a reason into a Viktor-persona single-line nudge."""
    # Severity=high gets @Solon tag prefix; medium/low no tag
    tag = "<@solon> " if severity == "high" else ""
    # Pick a random-but-deterministic prefix based on reason hash
    prefix = VIKTOR_PREFIXES[abs(hash(reason)) % len(VIKTOR_PREFIXES)]
    return f"{tag}{prefix}{reason}. — Titan"


def post_to_channel(text: str) -> dict[str, Any]:
    if not SLACK_BOT_TOKEN:
        logging.info("nudge_channel: SLACK_BOT_TOKEN missing; skipping post")
        return {"posted": False, "reason": "no_token"}
    payload = json.dumps({
        "channel": SLACK_NUDGE_CHANNEL,
        "text": text,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        return {"posted": bool(data.get("ok")), "slack_ts": data.get("ts"), "raw": data}
    except Exception as exc:
        logging.warning("post_to_channel failed: %s", exc)
        return {"posted": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Digest overflow
# ---------------------------------------------------------------------------

def _today_digest_path() -> Path:
    today = datetime.now(timezone.utc).date().isoformat()
    return DIGEST_DIR / f"{today}.md"


def append_to_daily_digest(reason: str, source: Optional[str], severity: str) -> None:
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    p = _today_digest_path()
    ts = datetime.now(timezone.utc).strftime("%H:%M UTC")
    line = f"- [{ts}] ({severity}) {reason}"
    if source:
        line += f" — source: {source}"
    line += "\n"
    try:
        with open(p, "a", encoding="utf-8") as fp:
            fp.write(line)
    except OSError as exc:
        logging.warning("append_to_daily_digest failed: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fire_nudge(reason: str, source: Optional[str] = None, severity: str = "medium", dry_run: bool = False) -> dict[str, Any]:
    """
    Fire a single nudge. Enforces rate-limit: beyond hourly/daily caps, rolls
    to daily digest instead.
    """
    store = RateLimitStore(NUDGE_DB)
    hourly_count = store.recent_count(60)
    daily_count = store.recent_count(60 * 24)

    if hourly_count >= HOURLY_LIMIT or daily_count >= DAILY_LIMIT:
        # Rate-limited — roll to digest
        store.record(reason, source, severity, posted=False)
        if not dry_run:
            append_to_daily_digest(reason, source, severity)
        return {
            "action": "digest_overflow",
            "reason": reason,
            "hourly_count": hourly_count,
            "daily_count": daily_count,
        }

    # Below rate limit — post
    text = _viktor_format(reason, severity)
    if dry_run:
        store.record(reason, source, severity, posted=False)
        return {"action": "dry_run", "would_post": text}
    post_result = post_to_channel(text)
    store.record(reason, source, severity, posted=post_result.get("posted", False))
    return {
        "action": "posted" if post_result.get("posted") else "post_failed",
        "text": text,
        "post_result": post_result,
    }


# ---------------------------------------------------------------------------
# Trigger checks
# ---------------------------------------------------------------------------

def _list_doctrine_files() -> list[Path]:
    repo = Path(os.environ.get("TITAN_HARNESS_DIR", "/opt/titan-harness-work"))
    patterns = ["plans/DOCTRINE_*.md", "plans/DR_*.md", "CLAUDE.md", "CORE_CONTRACT.md"]
    out: list[Path] = []
    for p in patterns:
        out.extend(repo.glob(p))
    return out


def _check_doctrine_freshness() -> list[dict[str, Any]]:
    """Return list of stale doctrine files (last-research marker > 14 days)."""
    stale = []
    marker = "last-research:"
    for path in _list_doctrine_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if marker in line:
                try:
                    raw = line.split(marker, 1)[1].strip().rstrip("-->").strip().split()[0]
                    last = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    age = (datetime.now(timezone.utc) - last).days
                    if age > DOCTRINE_STALE_DAYS:
                        stale.append({"file": str(path), "age_days": age, "last_research": raw})
                except (ValueError, IndexError):
                    pass
                break
    return stale


def check_and_fire_triggers(dry_run: bool = False) -> dict[str, Any]:
    """
    Run all trigger checks. Fire a nudge for each breach. Returns summary.

    v1 checks implemented:
        - Doctrine freshness > 14 days
    v1 stubs (to be implemented as integrations land):
        - RADAR parked > 7 days
        - Governance Health Score drop
        - n8n DLQ backlog
        - SLO burn-rate
    """
    fired: list[dict[str, Any]] = []

    # Doctrine freshness
    stale_doctrines = _check_doctrine_freshness()
    for s in stale_doctrines:
        name = Path(s["file"]).name
        r = fire_nudge(
            reason=f"doctrine stale {s['age_days']}d: {name}",
            source=s["file"],
            severity="medium",
            dry_run=dry_run,
        )
        fired.append({"trigger": "doctrine_stale", "reason": r})

    return {
        "fired_count": len(fired),
        "fired": fired,
        "checks_run": ["doctrine_freshness"],
        "checks_stubbed": ["radar_parked", "governance_health", "dlq_backlog", "slo_burn"],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Titan #titan-nudge channel (CT-0412-07)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    fire = sub.add_parser("fire", help="fire a single nudge")
    fire.add_argument("--reason", required=True)
    fire.add_argument("--source", default=None)
    fire.add_argument("--severity", default="medium", choices=["low", "medium", "high"])
    fire.add_argument("--dry-run", action="store_true")
    check = sub.add_parser("check", help="run all trigger checks + fire eligible")
    check.add_argument("--dry-run", action="store_true")
    sub.add_parser("status", help="print rate-limit + recent counts")
    args = ap.parse_args()

    if args.cmd == "fire":
        print(json.dumps(fire_nudge(args.reason, args.source, args.severity, args.dry_run), indent=2))
        return 0
    if args.cmd == "check":
        print(json.dumps(check_and_fire_triggers(dry_run=args.dry_run), indent=2))
        return 0
    if args.cmd == "status":
        store = RateLimitStore(NUDGE_DB)
        print(json.dumps({
            "nudge_db": str(NUDGE_DB),
            "slack_nudge_channel": SLACK_NUDGE_CHANNEL,
            "token_configured": bool(SLACK_BOT_TOKEN),
            "hourly_count_last_60min": store.recent_count(60),
            "daily_count_last_24h": store.recent_count(60 * 24),
            "hourly_limit": HOURLY_LIMIT,
            "daily_limit": DAILY_LIMIT,
        }, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
