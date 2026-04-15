"""
titan-harness/lib/approval_broker.py

CT-0412-06 Titan Approval Broker — bidirectional middleman.

Polls MCP for pending operator-approvals, surfaces them to Solon's phone via
Slack DM + Ntfy push, and routes responses back to MCP update_task.

Runs as a systemd service. Primary deployment target: off-VPS Hetzner CX11
(resilience during VPS outage). Stopgap: runs on HostHatch VPS if Hetzner not
yet provisioned.

Polling logic:
    1. Every POLL_INTERVAL_SEC (default 300 = 5 min):
    2. Query MCP for tasks where status in {awaiting_operator_approval,
       confirmation_required} OR recent decisions tagged 'needs-solon' OR
       op_task_queue rows with 'BLOCKED: needs approval' in notes
    3. Dedup against SQLite /opt/amg-broker/surfaced.db
    4. For each new pending item:
        a. POST Slack DM via amg-approval-bot token
        b. Wait 60s for Slack confirmed delivery
        c. If unconfirmed, POST to Ntfy topic 'titan-approvals'
    5. Listen for responses via Slack events webhook + Ntfy webhook;
       route to MCP update_task

Response routing:
    - Button tap in Slack → webhook → classify action → MCP update_task
    - Natural-language DM reply → keyword match v1 (approve|deny|details) →
      MCP update_task (or reply with details for third)

Public API:
    BrokerConfig(...)
    Broker(config).run_forever()
    Broker(config).health() -> dict

CLI:
    python3 lib/approval_broker.py run       — run forever (systemd primary)
    python3 lib/approval_broker.py tick      — single poll cycle (for testing)
    python3 lib/approval_broker.py health    — print /broker/health payload
    python3 lib/approval_broker.py dedup-list — print SQLite surfaced rows
"""
from __future__ import annotations

import argparse
import dataclasses
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


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class BrokerConfig:
    broker_home: Path = Path(os.environ.get("AMG_BROKER_HOME", "/opt/amg-broker"))
    dedup_db: Path = dataclasses.field(init=False)
    activity_log: Path = dataclasses.field(init=False)
    mcp_endpoint: str = os.environ.get("MCP_ENDPOINT", "https://memory.aimarketinggenius.io")
    slack_bot_token: str = os.environ.get("SLACK_APPROVAL_BOT_TOKEN", "")
    slack_dm_channel: str = os.environ.get("SLACK_APPROVAL_DM_CHANNEL", "")  # Solon's DM channel ID
    ntfy_topic: str = os.environ.get("NTFY_APPROVAL_TOPIC", "titan-approvals")
    ntfy_host: str = os.environ.get("NTFY_HOST", "https://ntfy.sh")
    poll_interval_sec: int = int(os.environ.get("BROKER_POLL_INTERVAL_SEC", "300"))
    repush_after_hours: int = int(os.environ.get("BROKER_REPUSH_AFTER_HOURS", "1"))
    slack_delivery_timeout_sec: int = 60
    user_agent: str = "AMG-ApprovalBroker/1.0 (+https://aimarketinggenius.io)"

    def __post_init__(self):
        self.dedup_db = self.broker_home / "surfaced.db"
        self.activity_log = self.broker_home / "activity.jsonl"
        self.broker_home.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Dedup store
# ---------------------------------------------------------------------------

class DedupStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.db_path, timeout=10)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _init(self):
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS surfaced (
                    task_id TEXT NOT NULL,
                    surface_kind TEXT NOT NULL,
                    surfaced_ts TEXT NOT NULL,
                    responded_ts TEXT,
                    response TEXT,
                    slack_message_ts TEXT,
                    PRIMARY KEY (task_id, surface_kind)
                )
            """)
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_surfaced_responded_ts ON surfaced(responded_ts)
            """)

    def get(self, task_id: str, surface_kind: str) -> Optional[dict]:
        with self._conn() as c:
            r = c.execute(
                "SELECT task_id, surface_kind, surfaced_ts, responded_ts, response, slack_message_ts "
                "FROM surfaced WHERE task_id=? AND surface_kind=?",
                (task_id, surface_kind),
            ).fetchone()
        if not r:
            return None
        return {
            "task_id": r[0], "surface_kind": r[1],
            "surfaced_ts": r[2], "responded_ts": r[3],
            "response": r[4], "slack_message_ts": r[5],
        }

    def insert_surface(self, task_id: str, surface_kind: str, slack_message_ts: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        with self._conn() as c:
            c.execute("""
                INSERT OR REPLACE INTO surfaced (task_id, surface_kind, surfaced_ts, slack_message_ts)
                VALUES (?, ?, ?, ?)
            """, (task_id, surface_kind, now, slack_message_ts))

    def mark_responded(self, task_id: str, surface_kind: str, response: str) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        with self._conn() as c:
            c.execute("""
                UPDATE surfaced SET responded_ts=?, response=?
                WHERE task_id=? AND surface_kind=?
            """, (now, response, task_id, surface_kind))

    def should_repush(self, task_id: str, surface_kind: str, repush_after_hours: int) -> bool:
        """True if we already surfaced this, no response, and enough time has passed."""
        row = self.get(task_id, surface_kind)
        if row is None:
            return True  # never surfaced
        if row["responded_ts"]:
            return False  # already got a response
        # Has it been long enough?
        surfaced = datetime.fromisoformat(row["surfaced_ts"].rstrip("Z"))
        age = datetime.now(timezone.utc).replace(tzinfo=None) - surfaced
        return age > timedelta(hours=repush_after_hours)


# ---------------------------------------------------------------------------
# MCP queries
# ---------------------------------------------------------------------------

def _mcp_post(endpoint: str, action: str, data: dict[str, Any], *, timeout: int = 15) -> dict[str, Any]:
    payload = json.dumps({"action": action, "data": data}).encode("utf-8")
    req = urllib.request.Request(
        f"{endpoint}/{action}",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "AMG-ApprovalBroker/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def fetch_pending_approvals(cfg: BrokerConfig) -> list[dict[str, Any]]:
    """
    Query MCP for items that need Solon's phone attention.

    v1 strategy: query get_task_queue with status filter + limit, then client-side
    filter for awaiting_operator_approval / confirmation_required / needs-solon
    tagged notes.
    """
    try:
        r = _mcp_post(cfg.mcp_endpoint, "get_task_queue", {"limit": 50})
    except Exception as exc:
        logging.warning("fetch_pending_approvals: MCP query failed: %s", exc)
        return []
    tasks = r.get("tasks", [])
    pending: list[dict[str, Any]] = []
    for t in tasks:
        status = (t.get("status") or "").lower()
        notes = (t.get("notes") or "")
        approval = (t.get("approval") or "").lower()
        # Filter criteria per spec
        if (
            status in {"awaiting_operator_approval", "confirmation_required", "blocked"}
            or approval in {"awaiting_operator_approval", "confirmation_required"}
            or "BLOCKED: needs approval" in notes
            or "needs-solon" in (t.get("tags") or [])
            or "Tier B" in notes
            or "CONFIRM: EXECUTE" in notes
        ):
            pending.append(t)
    return pending


# ---------------------------------------------------------------------------
# Slack delivery
# ---------------------------------------------------------------------------

def slack_post_dm(cfg: BrokerConfig, text: str, blocks: Optional[list] = None) -> Optional[dict[str, Any]]:
    if not cfg.slack_bot_token or not cfg.slack_dm_channel:
        logging.info("slack_post_dm: missing token or channel; skipping")
        return None
    payload: dict[str, Any] = {
        "channel": cfg.slack_dm_channel,
        "text": text,
    }
    if blocks:
        payload["blocks"] = blocks
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {cfg.slack_bot_token}",
            "User-Agent": cfg.user_agent,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        return data
    except Exception as exc:
        logging.warning("slack_post_dm: post failed: %s", exc)
        return None


def ntfy_push(cfg: BrokerConfig, title: str, body: str, *, priority: str = "high") -> bool:
    url = f"{cfg.ntfy_host}/{cfg.ntfy_topic}"
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": priority,
            "Tags": "warning,bell",
            "User-Agent": cfg.user_agent,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):  # noqa: S310
            pass
        return True
    except Exception as exc:
        logging.warning("ntfy_push: failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Surface a single pending approval
# ---------------------------------------------------------------------------

def build_approval_blocks(task: dict[str, Any]) -> list[dict[str, Any]]:
    task_id = task.get("task_id", "?")
    objective = task.get("objective") or task.get("text") or "(no objective)"
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Approval needed: {task_id}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Objective:* {objective[:500]}"}},
        {
            "type": "actions",
            "block_id": f"approval-{task_id}",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "✅ Approve"},
                 "style": "primary", "value": f"approve|{task_id}", "action_id": "approve"},
                {"type": "button", "text": {"type": "plain_text", "text": "❌ Deny"},
                 "style": "danger", "value": f"deny|{task_id}", "action_id": "deny"},
                {"type": "button", "text": {"type": "plain_text", "text": "📋 Details"},
                 "value": f"details|{task_id}", "action_id": "details"},
            ],
        },
    ]
    return blocks


def log_activity(cfg: BrokerConfig, entry: dict[str, Any]) -> None:
    entry["ts_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        with open(cfg.activity_log, "a", encoding="utf-8") as fp:
            fp.write(json.dumps(entry) + "\n")
    except OSError as exc:
        logging.warning("log_activity: write failed: %s", exc)


def surface_one(cfg: BrokerConfig, dedup: DedupStore, task: dict[str, Any]) -> dict[str, Any]:
    task_id = task.get("task_id", "")
    if not task_id:
        return {"skipped": "no_task_id"}
    surface_kind = "pending_approval"
    if not dedup.should_repush(task_id, surface_kind, cfg.repush_after_hours):
        return {"skipped": "already_surfaced_recently", "task_id": task_id}
    blocks = build_approval_blocks(task)
    text = f"Approval needed: {task_id} — {(task.get('objective') or '')[:200]}"
    slack_resp = slack_post_dm(cfg, text, blocks=blocks)
    slack_ts = slack_resp.get("ts") if slack_resp and slack_resp.get("ok") else None
    dedup.insert_surface(task_id, surface_kind, slack_ts)
    slack_ok = bool(slack_ts)
    # If Slack unconfirmed, push Ntfy after timeout
    if not slack_ok:
        time.sleep(min(5, cfg.slack_delivery_timeout_sec))  # short probe; most Slack failures are immediate
        ntfy_ok = ntfy_push(cfg, f"Approval: {task_id}", text)
    else:
        ntfy_ok = None
    log_activity(cfg, {
        "kind": "broker_surface",
        "task_id": task_id,
        "slack_posted": slack_ok,
        "slack_ts": slack_ts,
        "ntfy_fallback": ntfy_ok,
    })
    return {
        "task_id": task_id,
        "slack_posted": slack_ok,
        "slack_ts": slack_ts,
        "ntfy_fallback": ntfy_ok,
    }


# ---------------------------------------------------------------------------
# Broker class
# ---------------------------------------------------------------------------

class Broker:
    def __init__(self, cfg: Optional[BrokerConfig] = None):
        self.cfg = cfg or BrokerConfig()
        self.dedup = DedupStore(self.cfg.dedup_db)
        self.last_poll_ts: Optional[str] = None
        self.last_pending_count = 0
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        self.log = logging.getLogger("approval-broker")

    def tick(self) -> dict[str, Any]:
        """Single poll + surface cycle. Returns summary."""
        self.last_poll_ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        pending = fetch_pending_approvals(self.cfg)
        self.last_pending_count = len(pending)
        self.log.info("tick: %d pending items", len(pending))
        results = [surface_one(self.cfg, self.dedup, t) for t in pending]
        pushed = sum(1 for r in results if r.get("slack_posted") or r.get("ntfy_fallback"))
        skipped = sum(1 for r in results if r.get("skipped"))
        return {"pending": len(pending), "pushed": pushed, "skipped": skipped, "ts": self.last_poll_ts}

    def run_forever(self) -> None:
        self.log.info("Broker starting run_forever (interval=%ds)", self.cfg.poll_interval_sec)
        while True:
            try:
                summary = self.tick()
                self.log.info("tick-summary: %s", json.dumps(summary))
            except Exception as exc:
                self.log.exception("tick failed: %s", exc)
            time.sleep(self.cfg.poll_interval_sec)

    def health(self) -> dict[str, Any]:
        # Count from dedup db
        with self.dedup._conn() as c:
            pushed_last_hour = c.execute(
                "SELECT COUNT(*) FROM surfaced WHERE surfaced_ts > ?",
                ((datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds").replace("+00:00", "Z"),),
            ).fetchone()[0]
            responses_last_hour = c.execute(
                "SELECT COUNT(*) FROM surfaced WHERE responded_ts IS NOT NULL AND responded_ts > ?",
                ((datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds").replace("+00:00", "Z"),),
            ).fetchone()[0]
        return {
            "last_poll_ts": self.last_poll_ts,
            "pending_count": self.last_pending_count,
            "pushed_last_hour": pushed_last_hour,
            "responses_last_hour": responses_last_hour,
            "broker_home": str(self.cfg.broker_home),
            "mcp_endpoint": self.cfg.mcp_endpoint,
            "slack_configured": bool(self.cfg.slack_bot_token and self.cfg.slack_dm_channel),
            "ntfy_topic": self.cfg.ntfy_topic,
        }


# ---------------------------------------------------------------------------
# Response routing (called from Slack interactive webhook + Ntfy webhook)
# ---------------------------------------------------------------------------

def route_response(cfg: BrokerConfig, dedup: DedupStore, task_id: str, action: str, actor: str = "solon-mobile") -> dict[str, Any]:
    """
    Called when Solon taps a button or sends a DM reply. Updates MCP task
    with the decision and records it in dedup.

    action: 'approve' | 'deny' | 'details'
    """
    action = action.lower()
    if action not in ("approve", "deny", "details"):
        return {"error": "unknown_action", "action": action}
    if action == "details":
        # Response flow: just look up and reply; no MCP update
        return {"action": "details", "task_id": task_id}

    # Approve or Deny → MCP update_task
    approval_value = "pre_approved" if action == "approve" else "denied"
    update_payload = {
        "task_id": task_id,
        "approval": approval_value,
        "notes": f"via approval broker (mobile), actor={actor}, ts={datetime.now(timezone.utc).isoformat(timespec='seconds')}Z",
        "last_heartbeat": True,
    }
    try:
        r = _mcp_post(cfg.mcp_endpoint, "update_task", update_payload)
        dedup.mark_responded(task_id, "pending_approval", action)
        log_activity(cfg, {
            "kind": "broker_response",
            "task_id": task_id,
            "action": action,
            "actor": actor,
            "mcp_result": r,
        })
        return {"action": action, "task_id": task_id, "mcp_result": r}
    except Exception as exc:
        return {"error": str(exc), "action": action, "task_id": task_id}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Titan Approval Broker (CT-0412-06)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", help="run forever (systemd)")
    sub.add_parser("tick", help="single poll cycle")
    sub.add_parser("health", help="print health payload")
    sub.add_parser("dedup-list", help="print SQLite surfaced rows")
    args = ap.parse_args()

    cfg = BrokerConfig()
    broker = Broker(cfg)

    if args.cmd == "run":
        broker.run_forever()
        return 0
    if args.cmd == "tick":
        print(json.dumps(broker.tick(), indent=2))
        return 0
    if args.cmd == "health":
        print(json.dumps(broker.health(), indent=2))
        return 0
    if args.cmd == "dedup-list":
        with broker.dedup._conn() as c:
            rows = c.execute(
                "SELECT task_id, surface_kind, surfaced_ts, responded_ts, response FROM surfaced ORDER BY surfaced_ts DESC LIMIT 50"
            ).fetchall()
        print(json.dumps([
            {"task_id": r[0], "surface_kind": r[1], "surfaced_ts": r[2],
             "responded_ts": r[3], "response": r[4]} for r in rows
        ], indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
