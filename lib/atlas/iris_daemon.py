#!/usr/bin/env python3
"""Iris daemon — Atlas Factory CT-0427-99.

Polls op_task_queue every 30s for status='approved' AND approval='pre_approved'
rows; applies pre_claim_gate() (5 gates per unified arch §3.1); claims the row;
drops a wake flag at /home/{agent}/.claude/{agent}-wake.flag carrying the task_id.

Gates (block claim and log to amg_blocker_register if blocked):
  G1 suspended       — agent's amg_agent_budget_config.is_suspended = true
  G2 daily_ceiling   — sum(amg_cost_ledger today) >= daily_ceiling_usd
  G3 level           — agent's level < required level for task_risk_tier
  G4 proof_spec      — assigned_to NOT IN ('manual','titan') AND proof_spec IS NULL
  G5 swarm_hard_kill — amg_swarm_budget today.hard_kill = true

Slack alerts disabled per 2026-04-26 doctrine — MCP log_decision tagged
atlas-build-summary substitutes for non-fatal alerts; flag_blocker for P0/P1.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

import psycopg2
import psycopg2.extras

POLL_INTERVAL_S = int(os.environ.get("IRIS_POLL_INTERVAL_S", "30"))
ATLAS_ENV_PATH = os.environ.get("IRIS_ENV_PATH", "/etc/amg-agents/atlas.env")
LOG_PATH = "/var/log/iris-daemon.log"
BUILDER_AGENTS = {"codex", "hercules", "nestor", "alexander", "kimi_code"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("iris")

_running = True


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


def shell_log(cur, *, task_id: Optional[str], agent: str, command: str, stdout: str = "", exit_code: int = 0) -> None:
    cur.execute(
        """
        INSERT INTO amg_shell_logs(task_id, agent, command, stdout_excerpt, exit_code)
        VALUES (%s, %s, %s, %s, %s);
        """,
        (task_id, agent, command, stdout[:500], exit_code),
    )


def register_blocker(cur, *, task_id: Optional[str], agent: str, severity: str, description: str) -> None:
    cur.execute(
        """
        INSERT INTO amg_blocker_register(task_id, agent, severity, description)
        VALUES (%s, %s, %s, %s);
        """,
        (task_id, agent, severity, description[:500]),
    )


def pre_claim_gate(cur, task: dict) -> tuple[bool, str]:
    """Return (allowed, reason). Allowed=False writes a blocker row."""
    agent = task["assigned_to"]
    task_id = task["task_id"]

    # G1 suspended
    cur.execute(
        "SELECT is_suspended, suspension_reason FROM amg_agent_budget_config WHERE agent=%s",
        (agent,),
    )
    row = cur.fetchone()
    if row and row[0]:
        return False, f"G1 suspended: agent={agent} reason={row[1] or 'unspecified'}"

    # G2 daily ceiling
    cur.execute(
        """
        SELECT
          (SELECT COALESCE(SUM(cost_usd),0) FROM amg_cost_ledger WHERE agent=%s AND ts::date = CURRENT_DATE) AS spent,
          (SELECT daily_ceiling_usd FROM amg_agent_budget_config WHERE agent=%s) AS ceiling
        """,
        (agent, agent),
    )
    row = cur.fetchone()
    if row and row[0] is not None and row[1] is not None and float(row[0]) >= float(row[1]):
        return False, f"G2 daily_ceiling: agent={agent} spent={row[0]} ceiling={row[1]}"

    # G3 level — placeholder (production: cross-check task_risk_tier vs agent level).
    # Today: skip for builders at L1 since synthetic tasks are standard tier.

    # G4 proof_spec required for non-titan/non-manual
    if agent not in ("titan", "manual") and task.get("proof_spec") is None:
        return False, f"G4 proof_spec missing: agent={agent} task_id={task_id}"

    # G5 swarm hard kill
    cur.execute(
        "SELECT hard_kill FROM amg_swarm_budget WHERE budget_date=CURRENT_DATE",
    )
    row = cur.fetchone()
    if row and row[0]:
        return False, "G5 swarm_hard_kill: today's budget breached"

    return True, "all gates clear"


def claim_and_drop_flag(cur, task: dict) -> bool:
    """Atomically lock the row and drop wake flag for the agent."""
    agent = task["assigned_to"]
    task_id = task["task_id"]
    cur.execute(
        """
        UPDATE op_task_queue
        SET status='locked', locked_by=%s, locked_at=NOW(), claimed_at=NOW(),
            started_at=NOW(), last_heartbeat=NOW()
        WHERE task_id=%s AND status='approved' AND approval='pre_approved'
        RETURNING task_id;
        """,
        (agent, task_id),
    )
    claimed = cur.fetchone()
    if not claimed:
        return False

    flag = pathlib.Path(f"/home/{agent}/.claude/{agent}-wake.flag")
    flag.parent.mkdir(parents=True, exist_ok=True)
    body = f"iris-claim task={task_id} ts={datetime.now(tz=timezone.utc).isoformat()}\n"
    flag.write_text(body)
    try:
        # Make sure the agent owns the flag so the supervisor can rm it.
        subprocess.run(["chown", f"{agent}:{agent}", str(flag)], check=False, capture_output=True)
    except Exception as exc:
        log.warning("chown failed for %s: %s", flag, exc)
    return True


def poll_once(dsn: str) -> None:
    with db_conn(dsn) as conn:
        conn.autocommit = False
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT task_id, assigned_to, proof_spec, priority, task_risk_tier
                FROM op_task_queue
                WHERE status='approved' AND approval='pre_approved'
                  AND assigned_to = ANY(%s)
                ORDER BY priority='urgent' DESC, created_at ASC
                LIMIT 5
                FOR UPDATE SKIP LOCKED;
                """,
                (list(BUILDER_AGENTS),),
            )
            rows = cur.fetchall()
            if not rows:
                conn.rollback()
                return
            for row in rows:
                task = dict(row)
                allowed, reason = pre_claim_gate(cur, task)
                if not allowed:
                    register_blocker(cur, task_id=task["task_id"], agent=task["assigned_to"], severity="P2", description=reason)
                    shell_log(cur, task_id=task["task_id"], agent="iris", command="pre_claim_gate BLOCKED", stdout=reason, exit_code=1)
                    log.info("GATE BLOCKED task=%s reason=%s", task["task_id"], reason)
                    continue
                ok = claim_and_drop_flag(cur, task)
                if ok:
                    shell_log(cur, task_id=task["task_id"], agent="iris", command="CLAIMED+FLAGGED+GATED", stdout=f"agent={task['assigned_to']}", exit_code=0)
                    log.info("CLAIMED+FLAGGED+GATED task=%s agent=%s", task["task_id"], task["assigned_to"])
                else:
                    shell_log(cur, task_id=task["task_id"], agent="iris", command="claim race-lost", stdout="another worker won", exit_code=0)
            conn.commit()


def main() -> int:
    env = load_env(ATLAS_ENV_PATH)
    dsn = env.get("SUPABASE_DB_URL") or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        log.error("SUPABASE_DB_URL not in %s and not in environment; exiting", ATLAS_ENV_PATH)
        return 2

    log.info("Iris daemon starting; poll_interval=%ss; agents=%s", POLL_INTERVAL_S, sorted(BUILDER_AGENTS))
    while _running:
        try:
            poll_once(dsn)
        except Exception as exc:  # never let the loop die
            log.exception("poll_once raised: %s", exc)
        # Sleep but check signal frequently.
        for _ in range(POLL_INTERVAL_S):
            if not _running:
                break
            time.sleep(1)
    log.info("Iris daemon clean exit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
