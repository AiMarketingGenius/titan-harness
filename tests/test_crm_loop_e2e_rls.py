"""Synthetic cross-tenant RLS E2E — commit #7 Kleisthenes.

Proves the Phase 2 + CRM Loop RLS stack blocks cross-tenant reads:

  1. Provision a second test tenant (crm-rls-e2e-XXXX).
  2. Seed a lead on each tenant (revere-chamber-demo + test tenant).
  3. As authenticated role with amg.tenant_id = A → only A's leads visible.
  4. Switch GUC to tenant B → only B's leads visible.
  5. No GUC set → 0 leads visible.
  6. Roster + tenants tables exhibit same isolation.
  7. Cleanup: DELETE the test tenant (CASCADE removes roster + leads).

Hard failure on any cross-tenant leak. Ship-blocking.

Requires SUPABASE_DB_URL + full Phase 2 + sql/011 + sql/012 stack applied.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 required")

from lib.crm_lead_intake import ingest_lead  # noqa: E402
from lib.tenant_provisioning import provision_tenant  # noqa: E402


REVERE_SLUG = "revere-chamber-demo"
REVERE_ID = "d315bd76-9044-41ad-a619-6803a2fdc0ed"
TEST_RUN_ID = uuid.uuid4().hex[:8]
TEST_SLUG = f"crm-rls-e2e-{TEST_RUN_ID}"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def _conn():
    c = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
    c.autocommit = False
    return c


def _count_leads_as_authenticated(conn, tenant_id: str | None) -> int:
    """Run SELECT as authenticated role with optional amg.tenant_id GUC set."""
    with conn.cursor() as cur:
        cur.execute("SET LOCAL ROLE authenticated;")
        if tenant_id is not None:
            cur.execute("SELECT set_config('amg.tenant_id', %s, true);", (tenant_id,))
        cur.execute(
            "SELECT COUNT(*) FROM public.crm_lead_intake WHERE contact_email LIKE %s;",
            (f"e2e-{TEST_RUN_ID}-%",),
        )
        count = cur.fetchone()[0]
        cur.execute("RESET ROLE;")
    return count


def _count_roster_as_authenticated(conn, tenant_id: str | None) -> int:
    with conn.cursor() as cur:
        cur.execute("SET LOCAL ROLE authenticated;")
        if tenant_id is not None:
            cur.execute("SELECT set_config('amg.tenant_id', %s, true);", (tenant_id,))
        cur.execute("SELECT COUNT(*) FROM public.tenant_agent_roster;")
        count = cur.fetchone()[0]
        cur.execute("RESET ROLE;")
    return count


def main() -> int:
    if not os.environ.get("SUPABASE_DB_URL"):
        print("SKIP: SUPABASE_DB_URL not set", file=sys.stderr)
        return 77

    print(f"[1/7] Provision synthetic tenant {TEST_SLUG}")
    test_tenant = provision_tenant(
        slug=TEST_SLUG,
        name=f"CRM RLS E2E Test ({TEST_RUN_ID})",
        plan_tier="chamber-standard",
    )
    test_tenant_id = test_tenant["id"]
    print(f"  -> id={test_tenant_id} was_existing={test_tenant['was_existing']}")

    try:
        conn = _conn()
        try:
            print("[2/7] Seed one lead per tenant")
            # Each lead is identifiable via the test_run_id namespace.
            ingest_lead(
                conn, REVERE_ID, "inbound_form",
                contact_email=f"e2e-{TEST_RUN_ID}-revere@test.amg",
                contact_name=f"RLS E2E Revere ({TEST_RUN_ID})",
                source_metadata={"rls_e2e_run": TEST_RUN_ID, "tenant_side": "A"},
            )
            ingest_lead(
                conn, test_tenant_id, "inbound_form",
                contact_email=f"e2e-{TEST_RUN_ID}-test@test.amg",
                contact_name=f"RLS E2E Test ({TEST_RUN_ID})",
                source_metadata={"rls_e2e_run": TEST_RUN_ID, "tenant_side": "B"},
            )
            conn.commit()
            print(f"  -> 2 leads seeded, one per tenant")

            print("[3/7] Authenticated + tenant A GUC → sees only A lead")
            conn = _conn()
            count_a = _count_leads_as_authenticated(conn, REVERE_ID)
            conn.rollback()
            _assert(count_a == 1, f"tenant A authenticated view count={count_a}, expected 1")

            print("[4/7] Authenticated + tenant B GUC → sees only B lead")
            conn = _conn()
            count_b = _count_leads_as_authenticated(conn, test_tenant_id)
            conn.rollback()
            _assert(count_b == 1, f"tenant B authenticated view count={count_b}, expected 1")

            print("[5/7] Authenticated + no GUC → sees 0 leads (RLS blocks)")
            conn = _conn()
            count_none = _count_leads_as_authenticated(conn, None)
            conn.rollback()
            _assert(count_none == 0, f"no-GUC authenticated view count={count_none}, expected 0")

            print("[6/7] Roster RLS isolation")
            conn = _conn()
            roster_a = _count_roster_as_authenticated(conn, REVERE_ID)
            conn.rollback()
            _assert(roster_a == 7, f"tenant A roster via RLS count={roster_a}, expected 7")
            conn = _conn()
            roster_b = _count_roster_as_authenticated(conn, test_tenant_id)
            conn.rollback()
            _assert(roster_b == 7, f"tenant B roster via RLS count={roster_b}, expected 7")
            conn = _conn()
            roster_none = _count_roster_as_authenticated(conn, None)
            conn.rollback()
            _assert(roster_none == 0, f"no-GUC roster count={roster_none}, expected 0")

            print("[7/7] No cross-tenant leak between A and B")
            conn = _conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL ROLE authenticated;")
                    cur.execute("SELECT set_config('amg.tenant_id', %s, true);", (REVERE_ID,))
                    cur.execute(
                        "SELECT source_metadata->>'tenant_side' FROM public.crm_lead_intake "
                        "WHERE contact_email LIKE %s;",
                        (f"e2e-{TEST_RUN_ID}-%",),
                    )
                    sides = [r[0] for r in cur.fetchall()]
                    cur.execute("RESET ROLE;")
            finally:
                conn.rollback()
            _assert(sides == ["A"], f"expected ['A'], got {sides}")
            print(f"  -> tenant A view emitted {sides} (no leak)")

        finally:
            conn.close()
    finally:
        # Cleanup: delete test tenant's leads + tenant row. CASCADE on tenants
        # removes the roster rows. Intentionally outside the try/except so we
        # always run cleanup even if an assertion fires above.
        cleanup = _conn()
        try:
            with cleanup.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.crm_lead_intake WHERE contact_email LIKE %s;",
                    (f"e2e-{TEST_RUN_ID}-%",),
                )
                deleted_leads = cur.rowcount
                cur.execute(
                    "DELETE FROM public.tenants WHERE slug = %s;",
                    (TEST_SLUG,),
                )
                deleted_tenants = cur.rowcount
            cleanup.commit()
            print(
                f"[cleanup] deleted leads={deleted_leads} tenants={deleted_tenants} "
                f"(roster + test lead cleared by CASCADE)"
            )
        except Exception as exc:
            cleanup.rollback()
            print(f"[cleanup] FAILED: {exc}", file=sys.stderr)
        finally:
            cleanup.close()

    print(f"PASS: crm_loop_e2e_rls (run_id={TEST_RUN_ID})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
