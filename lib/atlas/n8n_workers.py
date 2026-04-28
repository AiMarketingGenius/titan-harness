#!/usr/bin/env python3
"""Atlas Factory governance workers — pg_cron + Python implementations of the
5 n8n workflows specified in CT-0427-99 work pack §6:

  heartbeat-stale-lock-alert    every 5 min  -> alert on stale active locks
  cost-sentinel                 every 5 min  -> alert at 80%, suspend at 100%
  reaper                        every 5 min  -> belt-and-suspenders for atlas-reaper pg_cron
  false-completion-kill-switch  every 5 min  -> P0 on reviewer=builder shipped row
  morning-digest                cron 10 UTC  -> daily summary

Slack alerts disabled per 2026-04-26 doctrine — alerts written to
amg_blocker_register + emitted as op_decisions tagged atlas-alert.

Each worker is a separate CLI:
    n8n_workers.py heartbeat-stale-lock-alert
    n8n_workers.py cost-sentinel
    n8n_workers.py reaper
    n8n_workers.py false-completion-kill-switch
    n8n_workers.py morning-digest

The n8n equivalents live in /opt/amg-titan/n8n/workflows/*.json for future
import; this Python path is what pg_cron actually invokes today via:
    SELECT cron.schedule('atlas-heartbeat', '*/5 * * * *',
      $$SELECT atlas_run_worker('heartbeat-stale-lock-alert')$$);
... where atlas_run_worker is a SQL wrapper that COPYs to a fifo, OR via the
simpler path: pg_cron + a `psql -c "SELECT pg_notify(...)"` + a Python listener.
For pragmatic v1 we ship via systemd timer instead of pg_cron-driven Python.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras

ATLAS_ENV = os.environ.get("IRIS_ENV_PATH", "/etc/amg-agents/atlas.env")
LOG_PATH = "/var/log/n8n-workers.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler(sys.stdout)],
)


def load_dsn() -> str:
    p = pathlib.Path(ATLAS_ENV)
    if p.is_file():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line.startswith("SUPABASE_DB_URL="):
                return line.split("=", 1)[1].strip().strip('"')
    return os.environ.get("SUPABASE_DB_URL", "")


def shell_log(conn, agent: str, command: str, stdout: str = "", task_id=None, exit_code: int = 0) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO amg_shell_logs(task_id, agent, command, stdout_excerpt, exit_code) VALUES (%s,%s,%s,%s,%s);",
            (task_id, agent, command, stdout[:500], exit_code),
        )


def heartbeat_stale_lock_alert(conn) -> int:
    """Find active locks whose updated_at < NOW() - 5 min. Log + register P1 blocker for each."""
    log = logging.getLogger("heartbeat")
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            """
            SELECT task_id, assigned_to, locked_by, locked_at, last_heartbeat
            FROM op_task_queue
            WHERE status IN ('locked','active')
              AND COALESCE(last_heartbeat, locked_at) < NOW() - INTERVAL '5 minutes'
            ORDER BY locked_at ASC LIMIT 25;
            """
        )
        rows = cur.fetchall()
        for r in rows:
            msg = (
                f"stale lock task={r['task_id']} agent={r['locked_by']} "
                f"locked_at={r['locked_at']} last_heartbeat={r['last_heartbeat']}"
            )
            log.warning(msg)
            cur.execute(
                """
                INSERT INTO amg_blocker_register(task_id, agent, severity, description)
                SELECT %s, %s, 'P1', %s
                WHERE NOT EXISTS (
                  SELECT 1 FROM amg_blocker_register
                  WHERE task_id=%s AND severity='P1' AND resolved_at IS NULL
                    AND description LIKE 'stale lock%%'
                );
                """,
                (r["task_id"], r["locked_by"], msg, r["task_id"]),
            )
        shell_log(conn, "n8n-heartbeat", "scan", f"stale_count={len(rows)}", exit_code=0)
        conn.commit()
        log.info("heartbeat run complete; stale_count=%d", len(rows))
        return len(rows)


def cost_sentinel(conn) -> int:
    """Scan today's spend per agent vs daily ceiling. >=80% -> alert; >=100% -> suspend."""
    log = logging.getLogger("cost")
    suspensions = 0
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            """
            SELECT b.agent, b.daily_ceiling_usd, b.is_suspended,
              COALESCE((SELECT SUM(cost_usd) FROM amg_cost_ledger WHERE agent=b.agent AND ts::date=CURRENT_DATE),0) AS spent
            FROM amg_agent_budget_config b
            ORDER BY b.agent;
            """
        )
        rows = cur.fetchall()
        for r in rows:
            spent = float(r["spent"] or 0)
            ceiling = float(r["daily_ceiling_usd"])
            if ceiling <= 0:
                continue
            pct = spent / ceiling * 100
            if pct >= 100 and not r["is_suspended"]:
                cur.execute(
                    "UPDATE amg_agent_budget_config SET is_suspended=true, suspension_reason=%s WHERE agent=%s;",
                    (f"daily ceiling breached at {datetime.now(timezone.utc).isoformat()} ({spent:.4f}/{ceiling:.4f})", r["agent"]),
                )
                cur.execute(
                    "INSERT INTO amg_blocker_register(task_id, agent, severity, description) VALUES (NULL, %s, 'P0', %s);",
                    (r["agent"], f"AUTO-SUSPENDED: {spent:.4f}/{ceiling:.4f} USD today"),
                )
                log.error("SUSPENDED %s spent=%.4f ceiling=%.4f", r["agent"], spent, ceiling)
                suspensions += 1
            elif pct >= 80:
                cur.execute(
                    """
                    INSERT INTO amg_blocker_register(task_id, agent, severity, description)
                    SELECT NULL, %s, 'P2', %s
                    WHERE NOT EXISTS (
                      SELECT 1 FROM amg_blocker_register
                      WHERE agent=%s AND severity='P2' AND ts > NOW() - INTERVAL '30 minutes'
                        AND description LIKE 'cost 80%%%%'
                    );
                    """,
                    (r["agent"], f"cost 80%: spent {spent:.4f} / {ceiling:.4f} USD ({pct:.1f}%)", r["agent"]),
                )
                log.warning("80%% threshold %s spent=%.4f ceiling=%.4f", r["agent"], spent, ceiling)
        shell_log(conn, "n8n-cost", "scan", f"agents={len(rows)} suspensions={suspensions}", exit_code=0)
        conn.commit()
        log.info("cost-sentinel run complete; agents=%d suspensions=%d", len(rows), suspensions)
        return suspensions


def reaper(conn) -> int:
    """Belt-and-suspenders for atlas-reaper pg_cron; releases stale-active locks."""
    log = logging.getLogger("reaper")
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE op_task_queue
            SET status='approved', locked_by=NULL, locked_at=NULL, claimed_at=NULL,
                notes = COALESCE(notes,'') || E'\n[n8n-reaper ' || NOW()::TEXT || '] released stale lock.'
            WHERE status IN ('locked','active')
              AND claimed_at IS NOT NULL
              AND claimed_at + COALESCE(claim_timeout, INTERVAL '2 hours') < NOW()
            RETURNING task_id;
            """
        )
        released = cur.fetchall()
        shell_log(conn, "n8n-reaper", "release", f"count={len(released)}", exit_code=0)
        conn.commit()
        log.info("reaper run complete; released=%d", len(released))
        return len(released)


def false_completion_kill_switch(conn) -> int:
    """If a row has reviewer_agent==builder_agent shipped, raise P0 + suspend agent."""
    log = logging.getLogger("kill-switch")
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            """
            SELECT q.task_id, q.builder_agent, q.reviewer_agent
            FROM op_task_queue q
            WHERE q.status='shipped'
              AND q.builder_agent IS NOT NULL
              AND q.reviewer_agent IS NOT NULL
              AND q.builder_agent = q.reviewer_agent;
            """
        )
        violations = cur.fetchall()
        for v in violations:
            cur.execute(
                "UPDATE op_task_queue SET status='blocked' WHERE task_id=%s;",
                (v["task_id"],),
            )
            cur.execute(
                "INSERT INTO amg_blocker_register(task_id, agent, severity, description) VALUES (%s, %s, 'P0', %s);",
                (v["task_id"], v["builder_agent"], f"FALSE-COMPLETION: builder=reviewer={v['builder_agent']}"),
            )
            cur.execute(
                "UPDATE amg_agent_budget_config SET is_suspended=true, suspension_reason=%s WHERE agent=%s;",
                (f"false-completion auto-suspend at {datetime.now(timezone.utc).isoformat()}", v["builder_agent"]),
            )
            log.error("FALSE-COMPLETION KILL task=%s agent=%s", v["task_id"], v["builder_agent"])
        shell_log(conn, "n8n-kill-switch", "scan", f"violations={len(violations)}", exit_code=0)
        conn.commit()
        log.info("false-completion-kill-switch run complete; violations=%d", len(violations))
        return len(violations)


def morning_digest(conn) -> int:
    """Build digest for today; INSERT into amg_morning_digest; archive copy to /opt/amg-docs/digests/."""
    log = logging.getLogger("digest")
    today = datetime.now(timezone.utc).date()
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT count(*) AS n_shipped FROM op_task_queue WHERE status='shipped' AND completed_at::date = %s;", (today,))
        n_shipped = cur.fetchone()["n_shipped"]

        cur.execute("SELECT COALESCE(SUM(cost_usd),0) AS spent FROM amg_cost_ledger WHERE ts::date = %s;", (today,))
        spent = float(cur.fetchone()["spent"] or 0)

        cur.execute("SELECT count(*) AS n_blockers FROM amg_blocker_register WHERE ts::date=%s AND resolved_at IS NULL;", (today,))
        n_blockers = cur.fetchone()["n_blockers"]

        cur.execute("SELECT count(*) AS n_pass FROM amg_reviews WHERE reviewed_at::date=%s AND verdict='PASS';", (today,))
        n_pass = cur.fetchone()["n_pass"]

        cur.execute("SELECT agent, level, consecutive_clean FROM amg_graduation_counters ORDER BY level DESC, agent;")
        grads = cur.fetchall()

        content = (
            f"== ATLAS FACTORY DIGEST {today} ==\n"
            f"Shipped: {n_shipped}\n"
            f"Total spend: ${spent:.4f}\n"
            f"Open blockers: {n_blockers}\n"
            f"Reviews PASS today: {n_pass}\n"
            f"Graduation counters:\n"
            + "".join(f"  {g['agent']}: L{g['level']} ({g['consecutive_clean']}/threshold)\n" for g in grads)
        )
        cur.execute(
            """
            INSERT INTO amg_morning_digest(digest_date, content)
            VALUES (%s, %s)
            ON CONFLICT (digest_date) DO UPDATE SET content=EXCLUDED.content, ts=NOW()
            RETURNING id;
            """,
            (today, content),
        )
        rid = cur.fetchone()["id"]

        # Local archive (R2 mirror via /opt/amg-security/amg-docs-mirror.sh per §19).
        archive_dir = pathlib.Path("/opt/amg-docs/digests")
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"digest_{today.isoformat()}.md"
        archive_path.write_text(content)

        cur.execute("UPDATE amg_morning_digest SET r2_archive_path=%s WHERE id=%s;", (str(archive_path), rid))
        shell_log(conn, "n8n-digest", "build", content[:500], exit_code=0)
        conn.commit()
        log.info("morning-digest written id=%s archive=%s", rid, archive_path)
        print(content)
        return n_shipped


WORKERS = {
    "heartbeat-stale-lock-alert": heartbeat_stale_lock_alert,
    "cost-sentinel": cost_sentinel,
    "reaper": reaper,
    "false-completion-kill-switch": false_completion_kill_switch,
    "morning-digest": morning_digest,
}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in WORKERS:
        print(f"usage: {argv[0]} {{{' | '.join(WORKERS)}}}", file=sys.stderr)
        return 2
    name = argv[1]
    dsn = load_dsn()
    if not dsn:
        logging.error("no SUPABASE_DB_URL")
        return 2
    conn = psycopg2.connect(dsn, connect_timeout=10)
    try:
        WORKERS[name](conn)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
