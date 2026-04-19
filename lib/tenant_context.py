"""Tenant + operator context wiring for RLS — Kleisthenes layer.

Sets the per-transaction GUCs that sql/009_multi_tenant.sql RLS policies
read via `current_setting('amg.tenant_id', TRUE)` and
`current_setting('amg.operator_id', TRUE)`.

Usage pattern (consumer-side wiring for JWT-authenticated requests):

    from lib.tenant_context import tenant_tx, tenant_id_from_jwt

    claims = verify_access_token(token, public_key)
    tenant_id = tenant_id_from_jwt(claims)

    with tenant_tx(conn_factory, tenant_id, operator_id=claims["sub"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ... FROM tenant_scoped_table ...")

`tenant_tx` opens a connection from `conn_factory()`, begins a transaction,
issues `SET LOCAL amg.tenant_id = <uuid>` + optional `amg.operator_id`,
yields the conn, then commits / rolls back. GUCs revert at tx end because
SET LOCAL is transaction-scoped.

Step 7.2 Multi-Tenant wiring pairs with lib/mobile_cmd_auth.py JWT issuance
which packs `tenant_id` into every access token (defaults to amg-internal
UUID for back-compat with single-operator Step 6.x paths).
"""

from __future__ import annotations

import contextlib
import re
import uuid
from typing import Any, Callable, Iterator


AMG_INTERNAL_TENANT_ID = "00000000-0000-0000-0000-000000000001"


_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _coerce_uuid(value: Any, field: str) -> str:
    """Normalize to canonical lowercase UUID string. Raises ValueError on malformed."""
    if isinstance(value, uuid.UUID):
        return str(value)
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UUID string or uuid.UUID, got {type(value).__name__}")
    s = value.strip().lower()
    if not _UUID_RE.match(s):
        raise ValueError(f"{field} is not a valid UUID: {value!r}")
    return s


def set_tenant_context(conn: Any, tenant_id: Any) -> None:
    """Issue `SET LOCAL amg.tenant_id = <uuid>` on the active transaction.

    Requires an already-open transaction (psycopg2 default-mode is autocommit=False,
    so any cursor op begins a tx). Safe to call multiple times per tx — last wins.
    """
    coerced = _coerce_uuid(tenant_id, "tenant_id")
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('amg.tenant_id', %s, true);", (coerced,))


def set_operator_context(conn: Any, operator_id: Any) -> None:
    """Issue `SET LOCAL amg.operator_id = <uuid>` on the active transaction."""
    coerced = _coerce_uuid(operator_id, "operator_id")
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('amg.operator_id', %s, true);", (coerced,))


def tenant_id_from_jwt(claims: dict[str, Any]) -> str:
    """Extract tenant_id from verified JWT claims, defaulting to amg-internal.

    lib/mobile_cmd_auth.py:issue_access_token() always sets tenant_id claim
    (defaults to amg-internal UUID if not provided at issuance), so this
    should never need the fallback in practice — but defensive default
    preserves back-compat with any legacy tokens issued before Step 7.2.
    """
    raw = claims.get("tenant_id", AMG_INTERNAL_TENANT_ID)
    return _coerce_uuid(raw, "claims.tenant_id")


def operator_id_from_jwt(claims: dict[str, Any]) -> str:
    """Extract operator_id (`sub` claim) as canonical UUID string."""
    raw = claims.get("sub")
    if raw is None:
        raise ValueError("JWT claims missing 'sub' (operator_id)")
    return _coerce_uuid(raw, "claims.sub")


@contextlib.contextmanager
def tenant_tx(
    conn_factory: Callable[[], Any],
    tenant_id: Any,
    operator_id: Any | None = None,
) -> Iterator[Any]:
    """Open a connection, BEGIN a tx, set GUCs, yield conn, commit or rollback.

    On exception: rollback + re-raise. On clean exit: commit. Always closes conn.
    """
    conn = conn_factory()
    try:
        if getattr(conn, "autocommit", False):
            conn.autocommit = False
        set_tenant_context(conn, tenant_id)
        if operator_id is not None:
            set_operator_context(conn, operator_id)
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass
