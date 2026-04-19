"""Smoke test for lib/onboarding_scheduler — commit #9 Kleisthenes.

Exercises:
  1. schedule_first_week_deliverables enqueues welcome email + logs MCP decision
  2. Re-invocation returns was_existing=True (idempotency by tenant_id + metadata.kind)
  3. outbound_email_queue row has expected shape (status='queued', scheduled_at
     ~15 min future, metadata.kind='onboarding_first_week')
  4. Invalid email / invalid tenant_id → ValueError
  5. Cleanup: delete test welcome rows

Requires SUPABASE_DB_URL + revere-chamber-demo tenant seeded.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 required")

from lib.onboarding_scheduler import (  # noqa: E402
    ONBOARDING_KIND,
    schedule_first_week_deliverables,
)


REVERE_ID = "d315bd76-9044-41ad-a619-6803a2fdc0ed"
REVERE_SLUG = "revere-chamber-demo"
TEST_RUN_ID = uuid.uuid4().hex[:8]
TEST_EMAIL = f"onboard-{TEST_RUN_ID}@revere-chamber.test"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def _cleanup_existing(conn):
    """Remove any prior onboarding_first_week row for revere-chamber-demo so
    we can test the fresh-enqueue path. Commit #1 didn't auto-schedule so
    this should be no-op on first ever run — but if a prior test run left
    residue, clear it."""
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM public.outbound_email_queue
             WHERE tenant_id = %s
               AND metadata->>'kind' = %s;
            """,
            (REVERE_ID, ONBOARDING_KIND),
        )
        return cur.rowcount


def main() -> int:
    if not os.environ.get("SUPABASE_DB_URL"):
        print("SKIP: SUPABASE_DB_URL not set", file=sys.stderr)
        return 77

    conn = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
    conn.autocommit = False
    try:
        print("[0/5] Clear any prior onboarding row so we test fresh-enqueue")
        cleaned = _cleanup_existing(conn)
        conn.commit()
        print(f"  -> cleared {cleaned} prior rows")

        print("[1/5] schedule_first_week_deliverables enqueues welcome email")
        first = schedule_first_week_deliverables(
            conn, REVERE_ID, REVERE_SLUG,
            tenant_name="Revere Chamber (Demo)",
            contact_email=TEST_EMAIL,
            contact_name=f"Test Contact {TEST_RUN_ID}",
            delay_seconds=900,  # 15 min
        )
        conn.commit()
        _assert(first["welcome_was_existing"] is False, f"expected fresh, got {first}")
        _assert(first["mcp_decision"] in ("posted", "skipped:MCPUnavailable"), f"mcp_decision={first['mcp_decision']}")
        print(f"  -> welcome id={first['welcome_email_id']} mcp={first['mcp_decision']}")

        print("[2/5] Re-invocation returns was_existing=True (idempotent)")
        second = schedule_first_week_deliverables(
            conn, REVERE_ID, REVERE_SLUG,
            tenant_name="Revere Chamber (Demo)",
            contact_email=TEST_EMAIL,
        )
        conn.commit()
        _assert(second["welcome_was_existing"] is True, f"expected re-existing, got {second}")
        _assert(second["welcome_email_id"] == first["welcome_email_id"], f"id changed on re-call")
        _assert(second["mcp_decision"] == "skipped", f"should not re-log on idempotent re-call")
        print(f"  -> re-call preserved id {second['welcome_email_id']}")

        print("[3/5] Queue row has expected shape")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT status, scheduled_at, metadata, subject, to_recipients
                  FROM public.outbound_email_queue
                 WHERE id = %s;
                """,
                (first["welcome_email_id"],),
            )
            row = cur.fetchone()
        status, scheduled_at, metadata, subject, to_recipients = row
        _assert(status == "queued", f"status={status}")
        _assert(metadata.get("kind") == ONBOARDING_KIND, f"metadata.kind={metadata.get('kind')}")
        _assert(metadata.get("tenant_slug") == REVERE_SLUG, f"metadata.tenant_slug={metadata.get('tenant_slug')}")
        _assert(TEST_EMAIL in (to_recipients or []), f"to_recipients missing test email: {to_recipients}")
        _assert(subject.startswith("Welcome"), f"subject={subject}")
        now = datetime.now(timezone.utc)
        expected_min = now + timedelta(seconds=60)
        expected_max = now + timedelta(seconds=20 * 60)
        _assert(expected_min < scheduled_at < expected_max,
                f"scheduled_at {scheduled_at} not in [{expected_min}, {expected_max}]")
        print(f"  -> subject={subject!r} scheduled_at={scheduled_at.isoformat()}")

        print("[4/5] Invalid inputs raise ValueError")
        try:
            schedule_first_week_deliverables(conn, "not-a-uuid", REVERE_SLUG, "X", "x@y.com")
        except ValueError:
            print("  -> rejected bad tenant_id")
        else:
            _assert(False, "bad tenant_id did not raise")
        try:
            schedule_first_week_deliverables(conn, REVERE_ID, REVERE_SLUG, "X", "no-at-sign")
        except ValueError:
            print("  -> rejected bad email")
        else:
            _assert(False, "bad email did not raise")

    except Exception:
        conn.rollback()
        raise
    else:
        # Cleanup: delete the test row.
        cleanup = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
        try:
            with cleanup.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM public.outbound_email_queue
                     WHERE tenant_id = %s
                       AND metadata->>'kind' = %s
                       AND %s = ANY(to_recipients);
                    """,
                    (REVERE_ID, ONBOARDING_KIND, TEST_EMAIL),
                )
                deleted = cur.rowcount
            cleanup.commit()
            print(f"[cleanup] deleted {deleted} test welcome rows")
        finally:
            cleanup.close()
    finally:
        conn.close()

    print("[5/5] all checks green")
    print(f"PASS: onboarding_scheduler smoke test (run_id={TEST_RUN_ID})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
