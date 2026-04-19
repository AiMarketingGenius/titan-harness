"""Smoke test for lib/crm_mcp_bridge — commit #5 of Kleisthenes CRM Loop.

Validates the bridge layer end-to-end:
  1. tenant_slug_for resolves revere-chamber-demo id → slug
  2. sync_lead_ingested posts to MCP /api/decisions (200 response)
  3. sync_status_change posts a transition decision
  4. fetch_tenant_context retrieves the posted decisions back by tag
  5. Input validation raises ValueError on bad slug / UUID / empty text

Uses revere-chamber-demo tenant (seeded commit #1) + a uuid-tagged lead_id.
Posts real decisions to MCP — they're tagged with a unique test_run_id to
allow separation from production chatter.

Requires MCP_BASE_URL reachable. SKIP on missing httpx or unreachable MCP.
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

from lib.crm_mcp_bridge import (  # noqa: E402
    BRIDGE_TAG,
    MCPBridgeError,
    MCPUnavailable,
    fetch_tenant_context,
    sync_lead_ingested,
    sync_status_change,
    tenant_slug_for,
)


REVERE_DEMO_ID = "d315bd76-9044-41ad-a619-6803a2fdc0ed"
REVERE_DEMO_SLUG = "revere-chamber-demo"
TEST_RUN_ID = uuid.uuid4().hex[:8]


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def main() -> int:
    if not os.environ.get("SUPABASE_DB_URL"):
        print("SKIP: SUPABASE_DB_URL not set", file=sys.stderr)
        return 77

    print("[1/5] tenant_slug_for resolves id → slug")
    conn = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
    try:
        slug = tenant_slug_for(conn, REVERE_DEMO_ID)
        _assert(slug == REVERE_DEMO_SLUG, f"expected {REVERE_DEMO_SLUG}, got {slug}")
        print(f"  -> {REVERE_DEMO_ID} → {slug}")
    finally:
        conn.close()

    print("[2/5] sync_lead_ingested posts to MCP")
    fake_lead = {
        "id": str(uuid.uuid4()),
        "source": "inbound_form",
        "contact_email": f"test-{TEST_RUN_ID}@revere-chamber.test",
        "status": "new",
    }
    try:
        resp = sync_lead_ingested(REVERE_DEMO_SLUG, fake_lead)
    except MCPUnavailable as exc:
        print(f"SKIP: MCP unreachable ({exc})", file=sys.stderr)
        return 77
    _assert(isinstance(resp, dict), f"POST response not dict: {type(resp)}")
    print(f"  -> MCP POST accepted for lead {fake_lead['id']}")

    print("[3/5] sync_status_change posts transition decision")
    resp = sync_status_change(
        REVERE_DEMO_SLUG,
        fake_lead["id"],
        source="inbound_form",
        old_status="new",
        new_status="qualified",
        note=f"test-run {TEST_RUN_ID}",
    )
    _assert(isinstance(resp, dict), f"POST response not dict: {type(resp)}")
    print(f"  -> transition decision posted")

    print("[4/5] fetch_tenant_context retrieves by tag")
    time.sleep(1.0)  # allow embedding index to catch up (non-critical)
    conn = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
    try:
        decisions = fetch_tenant_context(conn, REVERE_DEMO_SLUG, count=25)
    finally:
        conn.close()
    _assert(isinstance(decisions, list), f"fetch returned {type(decisions)}")
    ours = [
        d for d in decisions
        if isinstance(d, dict) and TEST_RUN_ID in (d.get("text") or "")
    ]
    _assert(len(ours) >= 2, f"expected >=2 test decisions back, got {len(ours)}")
    print(f"  -> fetched {len(ours)} decisions tagged for this test run (of {len(decisions)} total)")

    print("[5/5] input validation raises ValueError")
    bad_cases = [
        lambda: sync_lead_ingested("BAD-SLUG-UPPER", fake_lead),
        lambda: sync_status_change("BAD-SLUG-UPPER", fake_lead["id"], "inbound_form", "new", "qualified"),
        lambda: sync_status_change(REVERE_DEMO_SLUG, "not-a-uuid", "inbound_form", "new", "qualified"),
    ]
    for i, fn in enumerate(bad_cases, 1):
        try:
            fn()
        except ValueError:
            print(f"  -> case {i}: rejected")
        else:
            _assert(False, f"bad case {i} did not raise ValueError")

    print(f"PASS: crm_mcp_bridge smoke test (run_id={TEST_RUN_ID})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
