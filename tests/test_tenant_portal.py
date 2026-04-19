"""Smoke test for lib/tenant_portal — commit #8 Kleisthenes.

Exercises:
  1. portal_context returns tenant + enabled roster + lead counts
  2. portal_ingest_lead creates a lead + reports mcp_sync status
  3. Invalid slug raises ValueError; unknown slug raises LookupError
  4. Cleanup: delete test lead

Requires SUPABASE_DB_URL.
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

from lib.tenant_portal import portal_context, portal_ingest_lead  # noqa: E402


SLUG = "revere-chamber-demo"
TEST_RUN_ID = uuid.uuid4().hex[:8]
TEST_EMAIL = f"portal-{TEST_RUN_ID}@revere-chamber.test"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def main() -> int:
    if not os.environ.get("SUPABASE_DB_URL"):
        print("SKIP: SUPABASE_DB_URL not set", file=sys.stderr)
        return 77

    conn = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
    conn.autocommit = False
    try:
        print("[1/4] portal_context returns expected shape")
        ctx = portal_context(conn, SLUG)
        _assert(ctx["tenant"]["slug"] == SLUG, f"slug mismatch")
        _assert(isinstance(ctx["roster"], list), "roster not list")
        _assert(all(a["enabled"] for a in ctx["roster"]), "roster contains disabled agent")
        _assert(isinstance(ctx["lead_counts"], dict), "lead_counts not dict")
        _assert("total" in ctx["lead_counts"], "lead_counts missing 'total'")
        _assert(isinstance(ctx["recent_leads"], list), "recent_leads not list")
        print(f"  -> tenant={ctx['tenant']['name']}")
        print(f"  -> enabled_agents={len(ctx['roster'])}")
        print(f"  -> lead_counts={ctx['lead_counts']}")

        print("[2/4] portal_ingest_lead creates lead + posts to MCP")
        res = portal_ingest_lead(
            conn, SLUG,
            contact_email=TEST_EMAIL,
            contact_name=f"Portal Test {TEST_RUN_ID}",
            contact_company="Revere Chamber Web Form (test)",
            message="Looking for AI marketing help. Found you through the Chamber.",
            utm={"utm_source": "portal-smoke-test", "utm_medium": "organic"},
        )
        _assert(res["lead"]["was_existing"] is False, f"expected fresh lead")
        _assert(res["lead"]["source"] == "inbound_form", f"source={res['lead']['source']}")
        _assert(res["tenant_slug"] == SLUG, f"tenant_slug mismatch")
        _assert(
            res["mcp_sync"] in ("posted", "skipped:MCPUnavailable"),
            f"unexpected mcp_sync: {res['mcp_sync']}",
        )
        lead_id = res["lead"]["id"]
        print(f"  -> lead={lead_id} mcp_sync={res['mcp_sync']}")

        print("[3/4] invalid slug / unknown slug fail correctly")
        try:
            portal_context(conn, "BAD-SLUG-UPPER")
        except ValueError:
            print("  -> invalid slug rejected (ValueError)")
        else:
            _assert(False, "invalid slug did not raise")

        try:
            portal_ingest_lead(conn, "truly-nonexistent-slug-abc", contact_email="x@y.com")
        except LookupError:
            print("  -> unknown slug rejected (LookupError)")
        else:
            _assert(False, "unknown slug did not raise")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        # Cleanup: delete test lead
        cleanup = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
        try:
            with cleanup.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.crm_lead_intake WHERE contact_email = %s;",
                    (TEST_EMAIL,),
                )
                deleted = cur.rowcount
            cleanup.commit()
            print(f"[cleanup] deleted {deleted} test lead(s)")
        finally:
            cleanup.close()
        conn.close()

    print("[4/4] all checks green")
    print(f"PASS: tenant_portal smoke test (run_id={TEST_RUN_ID})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
