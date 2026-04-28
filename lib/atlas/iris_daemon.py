#!/usr/bin/env python3
"""Iris daemon v0.3 — Atlas Factory CT-0428-RECOVERY (claim_cycle_deadlock_fix).

Changes vs v0.2 (CT-0428-08):
  - Operator-class tasks (titan / manual / n8n / achilles) now MAIL-ONLY:
    Iris logs delivery to amg_shell_logs + posts to MCP /api/decisions
    tagged iris-mail, but does NOT lock the row. There is no autonomous
    consumer for those operators on the VPS, so any auto-claim deadlocks.
    Builder agents (codex / hercules / nestor / alexander / kimi_code)
    still get the existing claim+flag-drop path because they HAVE tmux
    supervisors that consume.
  - MAX_TASK_AGE_HOURS default 168 -> 72 (matches doctrine §5.4 freshness
    floor; 8-day-old CT-0419/0420/0421 mail bursts triggered this fix).
  - SELECT pre-filters by created_at > NOW() - INTERVAL N hours so old
    rows aren't even pulled into the FOR UPDATE SKIP LOCKED window.

Slack alerts disabled per 2026-04-26 doctrine — alerts fire to amg_alerts.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import signal
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional, Tuple
from urllib import request as urlreq
from urllib.error import URLError

import psycopg2
import psycopg2.extras

POLL_INTERVAL_S = int(os.environ.get("IRIS_POLL_INTERVAL_S", "30"))
ATLAS_ENV_PATH = os.environ.get("IRIS_ENV_PATH", "/etc/amg-agents/atlas.env")
LOG_PATH = "/var/log/iris-daemon.log"
MAX_TASK_AGE_HOURS = int(os.environ.get("IRIS_MAX_TASK_AGE_HOURS", "72"))  # doctrine §5.4 freshness floor
MCP_HEARTBEAT_EVERY_N_POLLS = int(os.environ.get("IRIS_MCP_HEARTBEAT_EVERY_N_POLLS", "10"))
MCP_BASE = os.environ.get("IRIS_MCP_BASE", "https://memory.aimarketinggenius.io")

# Mail-only: Iris records delivery but does NOT lock — these have no autonomous
# consumer on the VPS, so locking causes claim_cycle_deadlock (CT-0428-recovery).
OPERATORS_MAIL_ONLY = {"titan", "manual", "n8n", "achilles"}
# Claimable: each has a tmux supervisor that consumes wake flags.
BUILDER_AGENTS = {"codex", "hercules", "nestor", "alexander", "kimi_code"}
ALL_KNOWN = OPERATORS_MAIL_ONLY | BUILDER_AGENTS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("iris")

_running = True
_poll_count = 0


def _signal_handler(signum: int, frame) -> None:
    global _running
    log.info("signal %d received; draining and exiting", signum)
    _running = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def load_env(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    p = pathlib.Path(path)
    if not p.is_file():
        log.warning("env file %s not present", path)
        return out
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"')
    return out


@contextmanager
def db_conn(dsn: str) -> Iterator[psycopg2.extensions.connection]:
    conn = psycopg2.connect(dsn, connect_timeout=10)
    try:
        yield conn
    finally:
        conn.close()


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def is_fresh(task: dict) -> Tuple[bool, str]:
    """Return (fresh, reason). False means skip with logged reason."""
    expires = task.get("expires_at")
    if expires is not None:
        if isinstance(expires, datetime):
            exp_dt = expires if expires.tzinfo else expires.replace(tzinfo=timezone.utc)
        else:
            exp_dt = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
        if exp_dt < now_utc():
            return False, f"expired_at={exp_dt.isoformat()}"
    created = task.get("created_at")
    if created is not None:
        if isinstance(created, datetime):
            cr_dt = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
        else:
            cr_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        age = now_utc() - cr_dt
        if age > timedelta(hours=MAX_TASK_AGE_HOURS):
            return False, f"stale age={age}"
    return True, "ok"


def shell_log(cur, *, task_id: Optional[str], agent: str, command: str, stdout: str = "", exit_code: int = 0) -> None:
    cur.execute(
        "INSERT INTO amg_shell_logs(task_id, agent, command, stdout_excerpt, exit_code) VALUES (%s, %s, %s, %s, %s);",
        (task_id, agent, command, stdout[:500], exit_code),
    )


def heartbeat_db(cur, *, host: str, pid: int, poll_count: int, status: str = "ok", meta: Optional[dict] = None) -> None:
    cur.execute(
        "INSERT INTO amg_daemon_heartbeats(daemon, host, pid, poll_count, status, meta) VALUES (%s,%s,%s,%s,%s,%s);",
        ("iris", host, pid, poll_count, status, json.dumps(meta or {})),
    )


def heartbeat_mcp(text: str) -> None:
    """Best-effort POST to MCP /api/decisions; never fail the daemon on this."""
    try:
        body = json.dumps({"text": text, "project_source": "titan", "tags": ["iris-heartbeat", "ct-0428-08"]}).encode("utf-8")
        req = urlreq.Request(f"{MCP_BASE}/api/decisions", data=body, method="POST", headers={"Content-Type": "application/json"})
        with urlreq.urlopen(req, timeout=4) as resp:  # noqa: S310
            resp.read(64)
    except URLError as exc:
        log.warning("MCP heartbeat POST failed: %s", exc)
    except Exception as exc:  # never let heartbeat kill the loop
        log.warning("MCP heartbeat unexpected: %s", exc)


def register_blocker(cur, *, task_id: Optional[str], agent: str, severity: str, description: str) -> None:
    cur.execute(
        "INSERT INTO amg_blocker_register(task_id, agent, severity, description) VALUES (%s, %s, %s, %s);",
        (task_id, agent, severity, description[:500]),
    )


def pre_claim_gate(cur, task: dict) -> Tuple[bool, str]:
    agent = task["assigned_to"]
    task_id = task["task_id"]

    if agent in ("titan", "manual", "n8n", "achilles"):
        # Operator-class tasks bypass per-builder gates (no budget config row, no
        # graduation level requirement). Still check swarm hard kill.
        cur.execute("SELECT hard_kill FROM amg_swarm_budget WHERE budget_date=CURRENT_DATE")
        row = cur.fetchone()
        if row and row[0]:
            return False, "G5 swarm_hard_kill: today budget breached"
        return True, "operator-class clear"

    cur.execute(
        "SELECT is_suspended, suspension_reason FROM amg_agent_budget_config WHERE agent=%s",
        (agent,),
    )
    row = cur.fetchone()
    if row and row[0]:
        return False, f"G1 suspended: agent={agent} reason={row[1] or 'unspecified'}"

    cur.execute(
        """
        SELECT
          (SELECT COALESCE(SUM(cost_usd),0) FROM amg_cost_ledger WHERE agent=%s AND ts::date = CURRENT_DATE),
          (SELECT daily_ceiling_usd FROM amg_agent_budget_config WHERE agent=%s)
        """,
        (agent, agent),
    )
    row = cur.fetchone()
    if row and row[0] is not None and row[1] is not None and float(row[0]) >= float(row[1]):
        return False, f"G2 daily_ceiling: spent={row[0]} ceiling={row[1]}"

    if agent not in ("titan", "manual") and task.get("proof_spec") is None:
        return False, f"G4 proof_spec missing: agent={agent} task={task_id}"

    cur.execute("SELECT hard_kill FROM amg_swarm_budget WHERE budget_date=CURRENT_DATE")
    row = cur.fetchone()
    if row and row[0]:
        return False, "G5 swarm_hard_kill: today budget breached"

    return True, "all gates clear"


def claim_and_drop_flag(cur, task: dict) -> bool:
    agent = task["assigned_to"]
    task_id = task["task_id"]

    cur.execute(
        """
        UPDATE op_task_queue
        SET status='locked', locked_by=%s, locked_at=NOW(), claimed_at=NOW(),
            started_at=NOW(), last_heartbeat=NOW()
        WHERE task_id=%s AND status IN ('queued','approved') AND approval='pre_approved'
        RETURNING task_id;
        """,
        (agent, task_id),
    )
    if not cur.fetchone():
        return False

    flag = pathlib.Path(f"/home/{agent}/.claude/{agent}-wake.flag")
    flag.parent.mkdir(parents=True, exist_ok=True)
    body = f"iris-claim task={task_id} ts={now_utc().isoformat()}\n"
    flag.write_text(body)
    try:
        subprocess.run(["chown", f"{agent}:{agent}", str(flag)], check=False, capture_output=True)
    except Exception as exc:
        log.warning("chown failed for %s: %s", flag, exc)
    return True


def mail_only(cur, task: dict) -> None:
    """Operator-class delivery: log + decision-tag, never lock the row."""
    task_id = task["task_id"]
    recipient = task["assigned_to"]
    objective = (task.get("objective") or "")[:200]
    summary = f"recipient={recipient} obj={objective}"
    cur.execute(
        "INSERT INTO amg_shell_logs(task_id, agent, command, stdout_excerpt, exit_code) VALUES (%s,%s,%s,%s,0);",
        (task_id, "iris", "mail_delivered (mail-only operator)", summary[:500]),
    )
    body = json.dumps({
        "text": f"Mail delivered: {task_id} → {recipient}. Objective: {objective}",
        "project_source": "titan",
        "tags": ["iris-mail", "mail_delivered", task_id, f"recipient:{recipient}", "claim_cycle_deadlock_fix"],
    }).encode("utf-8")
    try:
        req = urlreq.Request(f"{MCP_BASE}/api/decisions", data=body, method="POST",
                             headers={"Content-Type": "application/json"})
        with urlreq.urlopen(req, timeout=4) as resp:
            resp.read(64)
    except (URLError, Exception) as exc:
        log.warning("mail_only MCP post failed (non-fatal): %s", exc)


def poll_once(dsn: str) -> None:
    global _poll_count
    _poll_count += 1
    host = socket.gethostname()
    pid = os.getpid()

    with db_conn(dsn) as conn:
        conn.autocommit = False
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            heartbeat_db(cur, host=host, pid=pid, poll_count=_poll_count, status="poll_start")

            cur.execute(
                """
                SELECT task_id, assigned_to, objective, proof_spec, priority, task_risk_tier, expires_at, created_at
                FROM op_task_queue
                WHERE status IN ('queued','approved') AND approval='pre_approved'
                  AND created_at > NOW() - (%s || ' hours')::INTERVAL
                ORDER BY priority='urgent' DESC, created_at ASC
                LIMIT 25
                FOR UPDATE SKIP LOCKED;
                """,
                (str(MAX_TASK_AGE_HOURS),),
            )
            rows = cur.fetchall()
            claimed_count = 0
            mailed_count = 0
            skipped_count = 0
            for row in rows:
                task = dict(row)
                if task["assigned_to"] not in ALL_KNOWN:
                    log.info("SKIP task=%s reason=unknown_operator %s", task["task_id"], task["assigned_to"])
                    shell_log(cur, task_id=task["task_id"], agent="iris", command="SKIP unknown_operator", stdout=str(task["assigned_to"]), exit_code=1)
                    skipped_count += 1
                    continue
                # Application-level freshness as belt-and-suspenders behind the SQL filter.
                fresh, reason = is_fresh(task)
                if not fresh:
                    log.info("SKIP task=%s reason=%s", task["task_id"], reason)
                    shell_log(cur, task_id=task["task_id"], agent="iris", command="SKIP not_fresh", stdout=reason, exit_code=1)
                    skipped_count += 1
                    continue
                # Operator-class: mail-only, no lock (claim_cycle_deadlock_fix).
                if task["assigned_to"] in OPERATORS_MAIL_ONLY:
                    mail_only(cur, task)
                    log.info("MAIL-ONLY task=%s recipient=%s (no auto-claim)", task["task_id"], task["assigned_to"])
                    mailed_count += 1
                    continue
                allowed, gate_reason = pre_claim_gate(cur, task)
                if not allowed:
                    register_blocker(cur, task_id=task["task_id"], agent=task["assigned_to"], severity="P2", description=gate_reason)
                    log.info("SKIP task=%s reason=GATE %s", task["task_id"], gate_reason)
                    shell_log(cur, task_id=task["task_id"], agent="iris", command="SKIP gate_blocked", stdout=gate_reason, exit_code=1)
                    skipped_count += 1
                    continue
                ok = claim_and_drop_flag(cur, task)
                if ok:
                    log.info("CLAIMED+FLAGGED+GATED task=%s agent=%s", task["task_id"], task["assigned_to"])
                    shell_log(cur, task_id=task["task_id"], agent="iris", command="CLAIMED+FLAGGED+GATED", stdout=f"agent={task['assigned_to']}", exit_code=0)
                    claimed_count += 1
                else:
                    shell_log(cur, task_id=task["task_id"], agent="iris", command="claim_race_lost", stdout="another worker won", exit_code=0)

            heartbeat_db(cur, host=host, pid=pid, poll_count=_poll_count, status="ok",
                         meta={"scanned": len(rows), "claimed": claimed_count, "mailed": mailed_count, "skipped": skipped_count})
            conn.commit()

    if _poll_count % MCP_HEARTBEAT_EVERY_N_POLLS == 0:
        heartbeat_mcp(f"iris-heartbeat poll={_poll_count} host={host} pid={pid}")


def main() -> int:
    env = load_env(ATLAS_ENV_PATH)
    dsn = env.get("SUPABASE_DB_URL") or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        log.error("SUPABASE_DB_URL not in %s and not in environment; exiting", ATLAS_ENV_PATH)
        return 2

    log.info("Iris v0.3 starting; poll_interval=%ss; max_age_h=%s; mail_only=%s; claimable=%s",
             POLL_INTERVAL_S, MAX_TASK_AGE_HOURS, sorted(OPERATORS_MAIL_ONLY), sorted(BUILDER_AGENTS))
    while _running:
        try:
            poll_once(dsn)
        except Exception as exc:
            log.exception("poll_once raised: %s", exc)
        for _ in range(POLL_INTERVAL_S):
            if not _running:
                break
            time.sleep(1)
    log.info("Iris v0.3 clean exit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
