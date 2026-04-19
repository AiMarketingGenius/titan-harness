"""Smoke test for lib/tenant_context — JWT tenant_id claim wiring (Kleisthenes).

Proves:
  1. set_tenant_context writes amg.tenant_id GUC inside an active tx, readable
     via current_setting('amg.tenant_id', TRUE).
  2. GUC is SET LOCAL — reverts at tx end.
  3. tenant_tx context manager sets + commits, re-raises on error + rolls back.
  4. tenant_id_from_jwt / operator_id_from_jwt extract + normalize claims.
  5. Malformed UUIDs raise ValueError at both the setter and the JWT helper.

Requires SUPABASE_DB_URL in env.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 required")

from lib.tenant_context import (  # noqa: E402
    AMG_INTERNAL_TENANT_ID,
    operator_id_from_jwt,
    set_tenant_context,
    tenant_id_from_jwt,
    tenant_tx,
)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def _conn_factory():
    return psycopg2.connect(os.environ["SUPABASE_DB_URL"])


def main() -> int:
    if not os.environ.get("SUPABASE_DB_URL"):
        print("SKIP: SUPABASE_DB_URL not set", file=sys.stderr)
        return 77

    tenant_a = AMG_INTERNAL_TENANT_ID
    tenant_b = "d315bd76-9044-41ad-a619-6803a2fdc0ed"  # revere-chamber-demo seeded 2026-04-19

    print("[1/5] set_tenant_context writes GUC inside tx")
    conn = _conn_factory()
    try:
        conn.autocommit = False
        set_tenant_context(conn, tenant_a)
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('amg.tenant_id', TRUE);")
            got = cur.fetchone()[0]
        _assert(got == tenant_a, f"expected {tenant_a}, got {got!r}")
        conn.rollback()
    finally:
        conn.close()
    print(f"  -> amg.tenant_id readable as {tenant_a}")

    print("[2/5] GUC reverts across tx boundary")
    conn = _conn_factory()
    try:
        conn.autocommit = False
        set_tenant_context(conn, tenant_a)
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('amg.tenant_id', TRUE);")
            got = cur.fetchone()[0]
        _assert(got in (None, ""), f"expected empty after rollback, got {got!r}")
    finally:
        conn.close()
    print("  -> empty after rollback")

    print("[3/5] tenant_tx context manager commits clean")
    with tenant_tx(_conn_factory, tenant_b) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('amg.tenant_id', TRUE);")
            got = cur.fetchone()[0]
        _assert(got == tenant_b, f"expected {tenant_b}, got {got!r}")
    print(f"  -> tenant_tx set {tenant_b} + committed")

    print("[4/5] tenant_id_from_jwt + operator_id_from_jwt")
    claims = {
        "sub": "11111111-2222-3333-4444-555555555555",
        "tenant_id": tenant_b,
        "aud": "atlas-api",
    }
    _assert(tenant_id_from_jwt(claims) == tenant_b, "tenant_id_from_jwt mismatch")
    _assert(operator_id_from_jwt(claims) == "11111111-2222-3333-4444-555555555555", "operator_id mismatch")
    empty_claims = {"sub": "11111111-2222-3333-4444-555555555555"}
    _assert(
        tenant_id_from_jwt(empty_claims) == AMG_INTERNAL_TENANT_ID,
        "missing tenant_id should default to amg-internal",
    )
    print("  -> claims extracted + defaulted correctly")

    print("[5/5] malformed UUID raises ValueError")
    bad = [
        ("not-a-uuid", "tenant_id"),
        ("12345", "tenant_id"),
        (12345, "tenant_id"),
    ]
    for val, field in bad:
        try:
            conn = _conn_factory()
            conn.autocommit = False
            set_tenant_context(conn, val)
        except ValueError:
            print(f"  -> rejected {val!r} as expected")
            conn.close()
            continue
        except Exception as exc:
            conn.close()
            _assert(False, f"{val!r} raised {type(exc).__name__} not ValueError")
        else:
            conn.close()
            _assert(False, f"{val!r} did not raise ValueError")

    print("PASS: tenant_context smoke test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
