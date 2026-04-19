"""Smoke test for lib/crm_lead_intake — commit #4 of Kleisthenes CRM Loop.

Exercises:
  1. ingest_lead for each of the 5 sources → 5 rows for revere-chamber-demo
  2. Re-ingest with same (tenant, source, email) → upsert, was_existing=True
  3. Re-ingest merges source_metadata into existing row
  4. list_leads returns 5 rows ordered by created_at DESC
  5. list_leads filter by status='new' returns 5
  6. list_leads filter by source='voicebot' returns 1
  7. update_lead_status transitions lead to 'qualified'
  8. Invalid source / status / email / agent / tenant all raise ValueError

Requires SUPABASE_DB_URL + sql/012_crm_leads.sql applied. Cleans up its own
test rows at the end (best effort).
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 required")

from lib.crm_lead_intake import (  # noqa: E402
    VALID_SOURCES,
    ingest_lead,
    list_leads,
    update_lead_status,
)


REVERE_DEMO_ID = "d315bd76-9044-41ad-a619-6803a2fdc0ed"
TEST_RUN_ID = uuid.uuid4().hex[:8]  # namespace emails + cleanup tag


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def _test_emails() -> dict[str, str]:
    return {
        src: f"test-{TEST_RUN_ID}-{src}@revere-chamber.test"
        for src in VALID_SOURCES
    }


def main() -> int:
    if not os.environ.get("SUPABASE_DB_URL"):
        print("SKIP: SUPABASE_DB_URL not set", file=sys.stderr)
        return 77

    emails = _test_emails()
    conn = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
    conn.autocommit = False
    try:
        print(f"[1/8] ingest_lead for 5 sources (test-run={TEST_RUN_ID})")
        created = {}
        for src in sorted(VALID_SOURCES):
            r = ingest_lead(
                conn, REVERE_DEMO_ID, src,
                contact_email=emails[src],
                contact_name=f"Test Contact {src}",
                contact_company="Revere Chamber (test)",
                source_metadata={"utm_source": "smoke-test", "run_id": TEST_RUN_ID},
                raw_payload={"src": src, "bucket": "smoke"},
                assigned_agent="nadia" if src == "inbound_form" else None,
                nadia_offset_seconds=60,
            )
            created[src] = r
            _assert(r["was_existing"] is False, f"{src}: expected new row, got was_existing={r['was_existing']}")
            _assert(r["status"] == "new", f"{src}: status={r['status']}")
            _assert(r["nadia_entry_scheduled_at"] is not None, f"{src}: nadia schedule missing")
            print(f"  -> {src}: id={r['id']} scheduled={r['nadia_entry_scheduled_at']}")

        print("[2/8] Re-ingest same (tenant, source, email) upserts")
        again = ingest_lead(
            conn, REVERE_DEMO_ID, "voicebot",
            contact_email=emails["voicebot"],
            source_metadata={"call_sid": "tw-test-sid-v2", "run_id": TEST_RUN_ID},
            raw_payload={"src": "voicebot", "bucket": "smoke", "v2": True},
        )
        _assert(again["was_existing"] is True, f"expected was_existing=True on re-ingest")
        _assert(again["id"] == created["voicebot"]["id"], "id changed on upsert")
        print(f"  -> voicebot upsert preserved id {again['id']}")

        print("[3/8] source_metadata merged, not replaced")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source_metadata, raw_payload FROM public.crm_lead_intake WHERE id = %s;",
                (created["voicebot"]["id"],),
            )
            meta, payload = cur.fetchone()
        _assert(meta.get("utm_source") == "smoke-test", f"utm_source lost: {meta}")
        _assert(meta.get("call_sid") == "tw-test-sid-v2", f"call_sid not merged: {meta}")
        _assert(payload.get("v2") is True, f"v2 not merged into raw_payload: {payload}")
        print("  -> JSONB || merge preserved first-write + added second-write keys")

        print("[4/8] list_leads for tenant returns 5 test rows")
        feed = list_leads(conn, REVERE_DEMO_ID, limit=50)
        ours = [r for r in feed if TEST_RUN_ID in (r.get("contact_email") or "")]
        _assert(len(ours) == 5, f"expected 5 test rows, got {len(ours)}: {[r['contact_email'] for r in ours]}")
        timestamps = [r["created_at"] for r in ours]
        _assert(timestamps == sorted(timestamps, reverse=True), "feed not DESC by created_at")
        print(f"  -> 5 rows, DESC-ordered")

        print("[5/8] list_leads status=new filter")
        new_feed = list_leads(conn, REVERE_DEMO_ID, status="new", limit=50)
        ours_new = [r for r in new_feed if TEST_RUN_ID in (r.get("contact_email") or "")]
        _assert(len(ours_new) == 5, f"status=new ours={len(ours_new)}")

        print("[6/8] list_leads source=voicebot filter")
        vb_feed = list_leads(conn, REVERE_DEMO_ID, source="voicebot", limit=50)
        ours_vb = [r for r in vb_feed if TEST_RUN_ID in (r.get("contact_email") or "")]
        _assert(len(ours_vb) == 1, f"source=voicebot ours={len(ours_vb)}")

        print("[7/8] update_lead_status new → qualified")
        ok = update_lead_status(conn, REVERE_DEMO_ID, created["inbound_form"]["id"], "qualified")
        _assert(ok, "update_lead_status returned False")
        qualified = list_leads(conn, REVERE_DEMO_ID, status="qualified", limit=50)
        ours_q = [r for r in qualified if TEST_RUN_ID in (r.get("contact_email") or "")]
        _assert(len(ours_q) == 1, f"expected 1 qualified, got {len(ours_q)}")

        print("[8/8] Invalid inputs raise ValueError")
        bad_cases = [
            lambda: ingest_lead(conn, REVERE_DEMO_ID, "bogus-source", contact_email="x@y.com"),
            lambda: ingest_lead(conn, REVERE_DEMO_ID, "inbound_form", contact_email="not-an-email"),
            lambda: ingest_lead(conn, REVERE_DEMO_ID, "inbound_form", assigned_agent="not-an-agent"),
            lambda: ingest_lead(conn, "not-a-uuid", "inbound_form"),
            lambda: update_lead_status(conn, REVERE_DEMO_ID, created["inbound_form"]["id"], "bogus-status"),
            lambda: list_leads(conn, REVERE_DEMO_ID, status="bogus"),
        ]
        for i, fn in enumerate(bad_cases, 1):
            try:
                fn()
            except ValueError:
                print(f"  -> case {i}: rejected")
            else:
                _assert(False, f"bad case {i} did not raise ValueError")

    except Exception:
        conn.rollback()
        raise
    else:
        # Cleanup: delete the 5 test rows we created.
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM public.crm_lead_intake WHERE tenant_id = %s AND contact_email LIKE %s;",
                (REVERE_DEMO_ID, f"test-{TEST_RUN_ID}-%"),
            )
            print(f"[cleanup] deleted {cur.rowcount} test rows")
        conn.commit()
    finally:
        conn.close()

    print("PASS: crm_lead_intake smoke test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
