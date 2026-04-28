#!/usr/bin/env python3
"""Iris daemon v0.4 — Atlas Factory CT-0428-22 (mail idempotency + install-packet routing).

Changes vs v0.3 (CT-0428-RECOVERY):
  - Mail-only delivery is now IDEMPOTENT: every successful operator-class
    delivery records a row in iris_mail_log keyed by task_id. The poll
    SELECT excludes any task already in iris_mail_log so each task is
    mailed exactly once per its lifetime in op_task_queue. Kills the
    re-delivery loop blocker iris_mail_loop_ct-0428-12 (active P10 since
    2026-04-28).
  - Install-packet detection added: when objective/instructions match
    install-packet keywords (e.g., "wire X into Y harness", references
    to scripts/, bin/, lib/, tests/, configs/ paths), Iris auto-creates
    a follow-up queue_operator_task assigned to the receiving harness
    owner with the standard verify+test+commit protocol embedded in
    instructions. Replaces the "files dumped in worktree without an
    install task" anti-pattern that surfaced via CT-0428-04.
  - SELECT now also pulls instructions + queued_by so install-packet
    detection has the full text. Self-recursion guard: tasks queued_by
    'iris' (the install-followup tasks themselves) bypass install-packet
    detection.

Changes vs v0.2 (CT-0428-08):
  - Operator-class tasks (titan / manual / n8n / achilles) MAIL-ONLY:
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
# achilles_courier added 2026-04-28 per tier1_gate_phase1 spec §12.3 — Achilles's
# Mac courier subscribes to op_decisions tagged iris-mail recipient:achilles_courier
# via Supabase Realtime (PATCH-01 pattern) and runs Stagehand against the
# corresponding eom_judgments row.
OPERATORS_MAIL_ONLY = {"titan", "manual", "n8n", "achilles", "achilles_courier"}
# Claimable: each has a tmux supervisor that consumes wake flags.
BUILDER_AGENTS = {"codex", "hercules", "nestor", "alexander", "kimi_code"}
ALL_KNOWN = OPERATORS_MAIL_ONLY | BUILDER_AGENTS

# CT-0428-22: install-packet detection. When an operator-class objective text
# matches one of these patterns, Iris routes via queue_install_followup() in
# addition to mail-only, creating a structured verify+test+commit sub-task on
# the receiving harness owner instead of relying on the recipient to
# materialize and verify files themselves.
#
# Conservative keyword set — false positives prefer mail-only over false-
# negative routing. Add new keywords as new install patterns surface.
INSTALL_PACKET_KEYWORDS = (
    "wire ",
    "install ",
    "deploy ",
    "scaffold ",
    "drop into",
    "copy to ",
    "scripts/",
    "tests/",
    " bin/",
    " lib/",
    "configs/",
    "into achilles harness",
    "into titan harness",
    "into the achilles harness",
    "into the titan harness",
)

# Boilerplate the install-packet follow-up task carries — receiving harness
# session reads the source mail referenced via parent_task_id, materializes
# any files the source describes, runs associated tests, then commits or
# named-stashes per the result.
INSTALL_PROTOCOL_TEMPLATE = """\
INSTALL PROTOCOL (auto-routed from CT-0428-22 iris install-packet detection)

Source mail: parent_task_id={source_task_id}
Original recipient: {recipient}
Source objective (verbatim): {objective_excerpt}

Receiving harness session, run in this order:
  (1) Read the source task referenced via parent_task_id (op_task_queue.task_id={source_task_id}).
      Pull objective + instructions in full so file paths and test references are exact.
  (2) Materialize any files the source describes. If files were embedded in the
      objective/instructions text (heredocs, code blocks), write them to the
      paths exactly as specified. If the source references a remote artifact
      (URL / git ref / other harness path), fetch it.
  (3) Verify content against the original spec. If a verification command is
      named in the source (lint / type-check / smoke harness), run it.
  (4) Run associated tests:
        - pytest path/ if tests/ dir referenced
        - the explicit test command if the source named one
        - bash bin/<harness>-preflight.sh if no tests but harness preflight exists
  (5) Commit on green:
        - git add <paths>; git commit with message tagged the source task_id
        - Mac sessions: also confirm post-commit auto-mirror landed (3-leg green)
      OR named-stash on red:
        - git stash push -u -m "iris-install-packet-{source_task_id}-FAILED"
        - then log a blocker in MCP describing why
  (6) log_decision tag iris_install_completed_{source_task_id} with diff link
      OR iris_install_failed_{source_task_id} with rationale.

Acceptance: the source task's intent is realized in working code in the receiving
harness, with tests green and a committed (or named-stashed) artifact + a
log_decision entry that links source + result.
"""

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


def mail_only(cur, task: dict, *, install_followup_id: Optional[str] = None) -> None:
    """Operator-class delivery: log + decision-tag, never lock the row.

    CT-0428-22: also records to iris_mail_log so subsequent polls skip
    this task (idempotency). When called as part of install-packet routing,
    install_followup_id is the queued sub-task's task_id and gets recorded
    in iris_mail_log.install_packet_followup_task_id for traceability.
    """
    task_id = task["task_id"]
    recipient = task["assigned_to"]
    objective = (task.get("objective") or "")[:200]
    summary = f"recipient={recipient} obj={objective}"
    cur.execute(
        "INSERT INTO amg_shell_logs(task_id, agent, command, stdout_excerpt, exit_code) VALUES (%s,%s,%s,%s,0);",
        (task_id, "iris", "mail_delivered (mail-only operator)", summary[:500]),
    )
    cur.execute(
        """
        INSERT INTO iris_mail_log(task_id, recipient, install_packet_routed, install_packet_followup_task_id, meta)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (task_id) DO NOTHING;
        """,
        (
            task_id,
            recipient,
            install_followup_id is not None,
            install_followup_id,
            json.dumps({"objective_excerpt": objective[:200]}),
        ),
    )
    decision_tags = ["iris-mail", "mail_delivered", task_id, f"recipient:{recipient}", "claim_cycle_deadlock_fix"]
    if install_followup_id:
        decision_tags.extend(["install_packet_routed", f"followup:{install_followup_id}"])
    body = json.dumps({
        "text": f"Mail delivered: {task_id} → {recipient}. Objective: {objective}"
                + (f" (install-packet routed: followup_task_id={install_followup_id})" if install_followup_id else ""),
        "project_source": "titan",
        "tags": decision_tags,
    }).encode("utf-8")
    try:
        req = urlreq.Request(f"{MCP_BASE}/api/decisions", data=body, method="POST",
                             headers={"Content-Type": "application/json"})
        with urlreq.urlopen(req, timeout=4) as resp:
            resp.read(64)
    except (URLError, Exception) as exc:
        log.warning("mail_only MCP post failed (non-fatal): %s", exc)


def is_install_packet(task: dict) -> bool:
    """Detect if an operator-class mail describes installing files into a
    receiving harness. False if the task was queued by Iris itself (anti-
    recursion guard) or if no install keywords appear in objective/instructions.
    """
    if (task.get("queued_by") or "").lower() == "iris":
        return False
    text = (
        ((task.get("objective") or "") + " " + (task.get("instructions") or ""))
        .lower()
    )
    return any(kw in text for kw in INSTALL_PACKET_KEYWORDS)


def queue_install_followup(cur, task: dict) -> Optional[str]:
    """Insert a structured verify+test+commit follow-up task assigned to the
    receiving harness owner. Returns the new task_id on success, None on
    conflict (already routed) or insert failure.
    """
    source_task_id = task["task_id"]
    recipient = task["assigned_to"]
    follow_id = f"{source_task_id}-install"
    objective_excerpt = (task.get("objective") or "")[:300]
    instructions = INSTALL_PROTOCOL_TEMPLATE.format(
        source_task_id=source_task_id,
        recipient=recipient,
        objective_excerpt=objective_excerpt,
    )
    follow_objective = f"INSTALL: {objective_excerpt[:150]}"
    acceptance = (
        "(1) Files referenced in source mail materialized at the paths the source describes. "
        "(2) Tests/preflight green (or named-stashed on red with a logged blocker). "
        "(3) Commit landed in receiving harness with message tagged the source task_id; "
        "3-leg mirror green for Mac sessions. "
        "(4) log_decision tag iris_install_completed_{src} OR iris_install_failed_{src}."
    ).format(src=source_task_id)
    try:
        cur.execute(
            """
            INSERT INTO op_task_queue(
              task_id, priority, agent, objective, instructions, acceptance_criteria,
              assigned_to, status, approval, queued_by, parent_task_id, tags
            )
            VALUES (%s, %s, 'ops', %s, %s, %s, %s, 'queued', 'pre_approved', 'iris',
                    (SELECT id FROM op_task_queue WHERE task_id=%s LIMIT 1),
                    ARRAY['iris_install_followup', %s, %s])
            ON CONFLICT (task_id) DO NOTHING
            RETURNING task_id;
            """,
            (
                follow_id,
                task.get("priority") or "normal",
                follow_objective,
                instructions,
                acceptance,
                recipient,
                source_task_id,
                f"source:{source_task_id}",
                f"recipient:{recipient}",
            ),
        )
        row = cur.fetchone()
        if row:
            return row[0]
        return None
    except Exception as exc:
        log.warning("queue_install_followup insert failed task=%s: %s", source_task_id, exc)
        return None


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
                SELECT q.task_id, q.assigned_to, q.objective, q.instructions, q.proof_spec,
                       q.priority, q.task_risk_tier, q.expires_at, q.created_at, q.queued_by
                FROM op_task_queue q
                WHERE q.status IN ('queued','approved') AND q.approval='pre_approved'
                  AND q.created_at > NOW() - (%s || ' hours')::INTERVAL
                  AND NOT EXISTS (
                    SELECT 1 FROM iris_mail_log m WHERE m.task_id = q.task_id
                  )
                ORDER BY q.priority='urgent' DESC, q.created_at ASC
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
                # CT-0428-22: also detect install-packet objectives + auto-route
                # to a structured verify+test+commit follow-up task on the
                # recipient harness owner.
                if task["assigned_to"] in OPERATORS_MAIL_ONLY:
                    follow_id = None
                    if is_install_packet(task):
                        follow_id = queue_install_followup(cur, task)
                        if follow_id:
                            log.info("INSTALL-PACKET routed task=%s -> followup=%s recipient=%s",
                                     task["task_id"], follow_id, task["assigned_to"])
                            shell_log(cur, task_id=task["task_id"], agent="iris",
                                      command="install_packet_routed",
                                      stdout=f"followup={follow_id}", exit_code=0)
                    mail_only(cur, task, install_followup_id=follow_id)
                    log.info("MAIL-ONLY task=%s recipient=%s install_followup=%s (no auto-claim)",
                             task["task_id"], task["assigned_to"], follow_id or "no")
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

    log.info("Iris v0.4 starting; poll_interval=%ss; max_age_h=%s; mail_only=%s; claimable=%s; "
             "idempotency=iris_mail_log; install_packet_routing=enabled",
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
    log.info("Iris v0.4 clean exit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
