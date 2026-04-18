"""Supabase-backed storage adapters + in-memory ChallengeStore for Mobile Command v2.

Step 6.3-b — provides the production storage backends that
`lib/mobile_cmd_auth.py` consumes via its abstract `RefreshTokenStore` /
credential_store / challenge_store interfaces. Step 6.1 shipped the auth
module + an InMemoryRefreshStore reference implementation; this module
adds the Supabase psycopg2 adapters that atlas_api wires into the live
auth handlers.

Schema dependency: `sql/008_mobile_cmd_auth.sql` (Step 6.2). Three tables:
- `public.refresh_tokens`         — JWT pair rotation + family reuse detection
- `public.webauthn_credentials`   — platform-authenticator public keys
- `public.push_subscriptions`     — VAPID Web Push subscriptions

Connection: takes a `conn_factory` callable that returns a fresh psycopg2
connection. atlas_api wires this from DATABASE_URL at startup. Each backend
method opens a short-lived connection / cursor scoped to that one query, so
this module is safe to share across gunicorn workers without connection-pool
state contamination.

ChallengeStore is in-memory (per Step 6 architecture spec — single-operator
scope; multi-operator scale-out moves it to Redis at Step 7). Includes a
TTL sweep that runs on every `set()` to keep the dict bounded.
"""
from __future__ import annotations

import datetime as _dt
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    psycopg2 = None  # type: ignore
    HAS_PSYCOPG2 = False

# Avoid a hard-import cycle by referencing the dataclass via fully-qualified path
# in type hints only. For the runtime construction we import it inside the methods.


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class StoreError(Exception):
    """Base error for storage adapter operations."""


class StoreUnavailable(StoreError):
    """Raised when psycopg2 is missing or DB is unreachable."""


def _require_psycopg2() -> None:
    if not HAS_PSYCOPG2:
        raise StoreUnavailable("psycopg2 not installed — pip install psycopg2-binary")


# ---------------------------------------------------------------------------
# Refresh token backend
# ---------------------------------------------------------------------------

class SupabaseRefreshTokenBackend:
    """psycopg2-backed implementation of the RefreshTokenStore backend interface.

    Methods match the abstract surface that mobile_cmd_auth.RefreshTokenStore
    wraps: insert(), find_by_hash(), mark_used(), revoke_family().
    """

    def __init__(self, conn_factory: Callable[[], Any]):
        self._conn_factory = conn_factory

    def insert(self, row: dict) -> None:
        _require_psycopg2()
        sql = """
            INSERT INTO public.refresh_tokens
                (id, operator_id, token_hash, family_id,
                 issued_at, expires_at, used_at, revoked_at, replaced_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            row["id"],
            row["operator_id"],
            psycopg2.Binary(row["token_hash"]) if HAS_PSYCOPG2 else row["token_hash"],
            row["family_id"],
            row["issued_at"],
            row["expires_at"],
            row.get("used_at"),
            row.get("revoked_at"),
            row.get("replaced_by"),
        )
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()

    def find_by_hash(self, token_hash: bytes):
        _require_psycopg2()
        from lib.mobile_cmd_models import RefreshTokenRecord

        sql = """
            SELECT id, operator_id, token_hash, family_id,
                   issued_at, expires_at, used_at, revoked_at
              FROM public.refresh_tokens
             WHERE token_hash = %s
             LIMIT 1
        """
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (psycopg2.Binary(token_hash),))
                row = cur.fetchone()
        if not row:
            return None
        return RefreshTokenRecord(
            id=uuid.UUID(str(row[0])),
            operator_id=uuid.UUID(str(row[1])),
            token_hash=bytes(row[2]),
            family_id=uuid.UUID(str(row[3])),
            issued_at=_as_dt(row[4]),
            expires_at=_as_dt(row[5]),
            used_at=_as_dt(row[6]) if row[6] else None,
            revoked_at=_as_dt(row[7]) if row[7] else None,
        )

    def mark_used(self, token_id: uuid.UUID, replaced_by: uuid.UUID | None) -> None:
        _require_psycopg2()
        sql = """
            UPDATE public.refresh_tokens
               SET used_at = now(),
                   replaced_by = %s
             WHERE id = %s
        """
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(replaced_by) if replaced_by else None, str(token_id)))
            conn.commit()

    def revoke_family(self, family_id: uuid.UUID, reason: str) -> int:
        _require_psycopg2()
        # Calls the PG function shipped in sql/008 (atomic + returns count).
        sql = "SELECT public.revoke_refresh_family(%s::uuid, %s)"
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(family_id), reason))
                affected = cur.fetchone()[0]
            conn.commit()
        return int(affected or 0)


# ---------------------------------------------------------------------------
# WebAuthn credential backend
# ---------------------------------------------------------------------------

class SupabaseWebAuthnCredentialBackend:
    """psycopg2-backed credential_store the mobile_cmd_auth WebAuthn flows use.

    Surface (per mobile_cmd_auth callsites):
        insert(row: dict)
        find_by_credential_id(cred_id: bytes | str) -> dict | None
        update_sign_count(id, new_sign_count) -> None
        list_active_for_operator(operator_id) -> list[dict]
    """

    def __init__(self, conn_factory: Callable[[], Any]):
        self._conn_factory = conn_factory

    def insert(self, row: dict) -> None:
        _require_psycopg2()
        sql = """
            INSERT INTO public.webauthn_credentials
                (id, operator_id, credential_id, public_key,
                 sign_count, transports, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            row["id"],
            row["operator_id"],
            psycopg2.Binary(_to_bytes(row["credential_id"])),
            psycopg2.Binary(_to_bytes(row["public_key"])),
            int(row.get("sign_count", 0)),
            row.get("transports") or ["internal"],
            row.get("user_agent"),
        )
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()

    def find_by_credential_id(self, cred_id) -> dict | None:
        _require_psycopg2()
        sql = """
            SELECT id, operator_id, credential_id, public_key,
                   sign_count, transports, user_agent, revoked_at
              FROM public.webauthn_credentials
             WHERE credential_id = %s
             LIMIT 1
        """
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (psycopg2.Binary(_to_bytes(cred_id)),))
                row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "operator_id": str(row[1]),
            "credential_id": bytes(row[2]),
            "public_key": bytes(row[3]),
            "sign_count": int(row[4]),
            "transports": list(row[5] or []),
            "user_agent": row[6],
            "revoked_at": row[7],
        }

    def update_sign_count(self, cred_pk_id, new_sign_count: int) -> None:
        _require_psycopg2()
        sql = """
            UPDATE public.webauthn_credentials
               SET sign_count = %s, last_used_at = now()
             WHERE id = %s
        """
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (int(new_sign_count), str(cred_pk_id)))
            conn.commit()

    def list_active_for_operator(self, operator_id) -> list[dict]:
        _require_psycopg2()
        sql = """
            SELECT id, credential_id, public_key, sign_count, transports
              FROM public.webauthn_credentials
             WHERE operator_id = %s AND revoked_at IS NULL
             ORDER BY created_at
        """
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(operator_id),))
                rows = cur.fetchall()
        return [
            {
                "id": str(r[0]),
                "credential_id": bytes(r[1]),
                "public_key": bytes(r[2]),
                "sign_count": int(r[3]),
                "transports": list(r[4] or []),
            }
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Push subscription backend
# ---------------------------------------------------------------------------

class SupabasePushSubscriptionBackend:
    """psycopg2-backed push_subscriptions store.

    Surface:
        insert(row) — re-subscribe-friendly (ON CONFLICT (endpoint) DO UPDATE)
        find_by_id(sub_id) -> dict | None
        list_active_for_operator(operator_id) -> list[dict]
        mark_revoked(sub_id, reason) -> None
        record_send_success(sub_id) / record_send_failure(sub_id, reason)
    """

    def __init__(self, conn_factory: Callable[[], Any]):
        self._conn_factory = conn_factory

    def insert(self, row: dict) -> str:
        """Insert OR update on endpoint conflict (treat re-subscribe as update).
        Returns the row id."""
        _require_psycopg2()
        sql = """
            INSERT INTO public.push_subscriptions
                (id, operator_id, endpoint, p256dh_key, auth_key, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (endpoint) DO UPDATE
              SET p256dh_key = EXCLUDED.p256dh_key,
                  auth_key   = EXCLUDED.auth_key,
                  user_agent = EXCLUDED.user_agent,
                  revoked_at = NULL,
                  revocation_reason = NULL,
                  failure_count = 0
            RETURNING id
        """
        params = (
            row["id"],
            row["operator_id"],
            row["endpoint"],
            row["p256dh_key"],
            row["auth_key"],
            row.get("user_agent"),
        )
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                returned = cur.fetchone()[0]
            conn.commit()
        return str(returned)

    def find_by_id(self, sub_id) -> dict | None:
        _require_psycopg2()
        sql = """
            SELECT id, operator_id, endpoint, p256dh_key, auth_key,
                   user_agent, revoked_at, failure_count
              FROM public.push_subscriptions
             WHERE id = %s
             LIMIT 1
        """
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(sub_id),))
                row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "operator_id": str(row[1]),
            "endpoint": row[2],
            "p256dh_key": row[3],
            "auth_key": row[4],
            "user_agent": row[5],
            "revoked_at": row[6],
            "failure_count": int(row[7]),
        }

    def list_active_for_operator(self, operator_id) -> list[dict]:
        _require_psycopg2()
        sql = """
            SELECT id, endpoint, p256dh_key, auth_key, user_agent
              FROM public.push_subscriptions
             WHERE operator_id = %s AND revoked_at IS NULL
        """
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(operator_id),))
                rows = cur.fetchall()
        return [
            {
                "id": str(r[0]),
                "endpoint": r[1],
                "p256dh_key": r[2],
                "auth_key": r[3],
                "user_agent": r[4],
            }
            for r in rows
        ]

    def mark_revoked(self, sub_id, reason: str) -> None:
        _require_psycopg2()
        sql = """
            UPDATE public.push_subscriptions
               SET revoked_at = now(), revocation_reason = %s
             WHERE id = %s
        """
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (reason, str(sub_id)))
            conn.commit()

    def record_send_success(self, sub_id) -> None:
        _require_psycopg2()
        sql = """
            UPDATE public.push_subscriptions
               SET last_success_at = now(), failure_count = 0
             WHERE id = %s
        """
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(sub_id),))
            conn.commit()

    def record_send_failure(self, sub_id, reason: str) -> None:
        _require_psycopg2()
        sql = """
            UPDATE public.push_subscriptions
               SET last_failure_at = now(),
                   failure_count = failure_count + 1
             WHERE id = %s
        """
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(sub_id),))
            conn.commit()


# ---------------------------------------------------------------------------
# In-memory ChallengeStore — TTL-aware
# ---------------------------------------------------------------------------

@dataclass
class _ChallengeEntry:
    value: Any
    expires_at: float  # monotonic-clock seconds


class InMemoryChallengeStore:
    """Thread-safe in-memory challenge store with on-write TTL sweep.

    Used for short-lived (2-min default) WebAuthn challenges. Single-operator
    scope — fine to keep in-process. Multi-operator scale-out moves this to
    Redis at Step 7 (CRM multi-tenant).

    Sweep happens on every set() so the dict can't grow unbounded. With a
    2-minute TTL + single operator, the dict size stays trivially small.
    """

    def __init__(self) -> None:
        self._data: dict[str, _ChallengeEntry] = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        now = time.monotonic()
        expires_at = now + max(1, int(ttl_seconds))
        with self._lock:
            # Sweep expired entries opportunistically.
            self._sweep_locked(now)
            self._data[key] = _ChallengeEntry(value=value, expires_at=expires_at)

    def pop(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            entry = self._data.pop(key, None)
        if entry is None:
            return None
        if entry.expires_at < now:
            return None  # expired in flight
        return entry.value

    def peek(self, key: str) -> Any | None:
        """Read without removing — for diagnostics / status endpoints. None if expired or missing."""
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
        if entry is None or entry.expires_at < now:
            return None
        return entry.value

    def size(self) -> int:
        with self._lock:
            return len(self._data)

    def _sweep_locked(self, now: float) -> int:
        """Caller must hold self._lock. Removes expired entries; returns count."""
        expired_keys = [k for k, v in self._data.items() if v.expires_at < now]
        for k in expired_keys:
            del self._data[k]
        return len(expired_keys)

    def sweep(self) -> int:
        with self._lock:
            return self._sweep_locked(time.monotonic())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_bytes(value) -> bytes:
    """Coerce string / memoryview / bytearray / bytes → bytes."""
    if isinstance(value, bytes):
        return value
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    raise TypeError(f"cannot coerce {type(value).__name__} to bytes")


def _as_dt(value) -> _dt.datetime:
    if isinstance(value, _dt.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=_dt.timezone.utc)
        return value
    if isinstance(value, str):
        return _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError(f"cannot coerce {type(value).__name__} to datetime")


# ---------------------------------------------------------------------------
# DATABASE_URL connection factory
# ---------------------------------------------------------------------------

def make_supabase_conn_factory(database_url: str | None = None) -> Callable[[], Any]:
    """Return a no-arg callable that opens a fresh psycopg2 connection.

    Reads DATABASE_URL from env if not passed explicitly. Raises StoreUnavailable
    at first call if psycopg2 is missing or DATABASE_URL is unset.
    """
    import os
    url = database_url or os.environ.get("DATABASE_URL")

    def factory() -> Any:
        _require_psycopg2()
        if not url:
            raise StoreUnavailable(
                "DATABASE_URL not set — required for Supabase storage adapters"
            )
        return psycopg2.connect(url)

    return factory


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

class _FakeCursor:
    """Minimal psycopg2 cursor stand-in for self-tests. Records exec calls."""

    def __init__(self, fetchone_returns=None, fetchall_returns=None):
        self.executed: list[tuple[str, tuple]] = []
        self._fetchone = fetchone_returns
        self._fetchall = fetchall_returns or []

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def execute(self, sql: str, params: tuple = ()):
        self.executed.append((sql, params))

    def fetchone(self):
        if callable(self._fetchone):
            return self._fetchone()
        return self._fetchone

    def fetchall(self):
        if callable(self._fetchall):
            return self._fetchall()
        return self._fetchall

    def close(self):
        pass


class _FakeConn:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1


def _self_test() -> int:
    passed = 0
    failed = 0

    def check(name: str, cond: bool) -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  ok  {name}")
        else:
            failed += 1
            print(f"  FAIL {name}")

    if not HAS_PSYCOPG2:
        print("  SKIP psycopg2 not installed — adapter SQL-shape tests will skip")
        # still run the ChallengeStore + helper tests
        skip_psycopg2 = True
    else:
        skip_psycopg2 = False

    # --- ChallengeStore ----------------------------------------------------
    cs = InMemoryChallengeStore()
    cs.set("k1", b"value1", ttl_seconds=10)
    check("ChallengeStore set+pop returns value", cs.pop("k1") == b"value1")
    check("ChallengeStore pop after pop returns None", cs.pop("k1") is None)

    cs.set("k2", "value2", ttl_seconds=1)
    check("ChallengeStore peek returns value", cs.peek("k2") == "value2")
    check("ChallengeStore peek does not consume", cs.peek("k2") == "value2")
    check("ChallengeStore size reflects entries", cs.size() == 1)

    cs.set("k3", "value3", ttl_seconds=10)
    cs.set("k4", "value4", ttl_seconds=10)
    check("ChallengeStore size reflects multiple", cs.size() == 3)

    # Force expiry via monkey-patched monotonic (simulate time advance)
    import time as _t
    real_monotonic = _t.monotonic
    fake_now = real_monotonic() + 100
    _t.monotonic = lambda: fake_now  # type: ignore
    try:
        check("ChallengeStore peek returns None when expired", cs.peek("k3") is None)
        check("ChallengeStore pop returns None when expired", cs.pop("k4") is None)
        # set() triggers sweep — verify k2/k3/k4 cleared
        cs.set("k5", "fresh", ttl_seconds=10)
        check("ChallengeStore size after sweep is 1 (only fresh)", cs.size() == 1)
    finally:
        _t.monotonic = real_monotonic  # type: ignore

    # --- _to_bytes / _as_dt helpers ----------------------------------------
    check("_to_bytes from bytes", _to_bytes(b"x") == b"x")
    check("_to_bytes from str", _to_bytes("x") == b"x")
    check("_to_bytes from bytearray", _to_bytes(bytearray(b"x")) == b"x")
    type_caught = False
    try:
        _to_bytes(123)
    except TypeError:
        type_caught = True
    check("_to_bytes raises TypeError on int", type_caught)

    dt_now = _dt.datetime.now(_dt.timezone.utc)
    check("_as_dt from datetime", _as_dt(dt_now) == dt_now)
    check("_as_dt from naive datetime adds UTC tz",
          _as_dt(_dt.datetime(2026, 4, 18, 12, 0, 0)).tzinfo is _dt.timezone.utc)
    check("_as_dt from ISO string", _as_dt("2026-04-18T12:00:00+00:00").year == 2026)

    if skip_psycopg2:
        print()
        print(f"TOTAL: {passed} passed, {failed} failed (psycopg2 skipped)")
        return 0 if failed == 0 else 1

    # --- SupabaseRefreshTokenBackend SQL-shape verification -----------------
    insert_cur = _FakeCursor()
    insert_conn = _FakeConn(insert_cur)
    rt = SupabaseRefreshTokenBackend(conn_factory=lambda: insert_conn)
    rt.insert({
        "id": str(uuid.uuid4()),
        "operator_id": str(uuid.uuid4()),
        "token_hash": b"\x00" * 32,
        "family_id": str(uuid.uuid4()),
        "issued_at": dt_now.isoformat(),
        "expires_at": (dt_now + _dt.timedelta(days=30)).isoformat(),
    })
    check("RefreshToken insert ran 1 SQL",
          len(insert_cur.executed) == 1 and "INSERT INTO public.refresh_tokens" in insert_cur.executed[0][0])
    check("RefreshToken insert committed", insert_conn.commits == 1)

    # find_by_hash → returns RefreshTokenRecord
    find_row = (
        str(uuid.uuid4()),               # id
        str(uuid.uuid4()),               # operator_id
        memoryview(b"\x00" * 32),        # token_hash (psycopg2 returns memoryview for BYTEA)
        str(uuid.uuid4()),               # family_id
        dt_now,                          # issued_at
        dt_now + _dt.timedelta(days=30), # expires_at
        None,                            # used_at
        None,                            # revoked_at
    )
    find_cur = _FakeCursor(fetchone_returns=find_row)
    find_conn = _FakeConn(find_cur)
    rt2 = SupabaseRefreshTokenBackend(conn_factory=lambda: find_conn)
    rec = rt2.find_by_hash(b"\x00" * 32)
    check("RefreshToken find_by_hash returns record", rec is not None)
    check("RefreshToken find_by_hash record has correct id", str(rec.id) == find_row[0])

    # find_by_hash → None when no row
    none_cur = _FakeCursor(fetchone_returns=None)
    none_conn = _FakeConn(none_cur)
    rt3 = SupabaseRefreshTokenBackend(conn_factory=lambda: none_conn)
    check("RefreshToken find_by_hash None when missing", rt3.find_by_hash(b"x") is None)

    # mark_used
    mark_cur = _FakeCursor()
    mark_conn = _FakeConn(mark_cur)
    rt4 = SupabaseRefreshTokenBackend(conn_factory=lambda: mark_conn)
    rt4.mark_used(uuid.uuid4(), replaced_by=None)
    check("RefreshToken mark_used SQL has UPDATE",
          "UPDATE public.refresh_tokens" in mark_cur.executed[0][0])
    check("RefreshToken mark_used commits", mark_conn.commits == 1)

    # revoke_family — returns int from PG function
    revoke_cur = _FakeCursor(fetchone_returns=(3,))
    revoke_conn = _FakeConn(revoke_cur)
    rt5 = SupabaseRefreshTokenBackend(conn_factory=lambda: revoke_conn)
    affected = rt5.revoke_family(uuid.uuid4(), reason="test-revoke")
    check("RefreshToken revoke_family returns int count", affected == 3)
    check("RefreshToken revoke_family calls PG function",
          "revoke_refresh_family" in revoke_cur.executed[0][0])

    # --- SupabaseWebAuthnCredentialBackend ---------------------------------
    wa_insert_cur = _FakeCursor()
    wa_insert_conn = _FakeConn(wa_insert_cur)
    wa = SupabaseWebAuthnCredentialBackend(conn_factory=lambda: wa_insert_conn)
    wa.insert({
        "id": str(uuid.uuid4()),
        "operator_id": str(uuid.uuid4()),
        "credential_id": b"\x42" * 32,
        "public_key": b"\x99" * 65,
        "sign_count": 0,
        "transports": ["internal"],
        "user_agent": "test-agent",
    })
    check("WebAuthn insert ran INSERT",
          "INSERT INTO public.webauthn_credentials" in wa_insert_cur.executed[0][0])

    # find_by_credential_id with row found
    wa_find_row = (
        str(uuid.uuid4()), str(uuid.uuid4()),
        memoryview(b"\x42" * 32), memoryview(b"\x99" * 65),
        5, ["internal"], "agent", None,
    )
    wa_find_cur = _FakeCursor(fetchone_returns=wa_find_row)
    wa_find_conn = _FakeConn(wa_find_cur)
    wa2 = SupabaseWebAuthnCredentialBackend(conn_factory=lambda: wa_find_conn)
    found = wa2.find_by_credential_id(b"\x42" * 32)
    check("WebAuthn find_by_credential_id returns dict", isinstance(found, dict))
    check("WebAuthn find returns sign_count int", found["sign_count"] == 5)

    # update_sign_count
    wa_upd_cur = _FakeCursor()
    wa_upd_conn = _FakeConn(wa_upd_cur)
    wa3 = SupabaseWebAuthnCredentialBackend(conn_factory=lambda: wa_upd_conn)
    wa3.update_sign_count(uuid.uuid4(), 7)
    check("WebAuthn update_sign_count runs UPDATE",
          "UPDATE public.webauthn_credentials" in wa_upd_cur.executed[0][0])

    # list_active_for_operator
    wa_list_rows = [
        (str(uuid.uuid4()), memoryview(b"a" * 32), memoryview(b"b" * 65), 1, ["internal"]),
        (str(uuid.uuid4()), memoryview(b"c" * 32), memoryview(b"d" * 65), 2, ["hybrid"]),
    ]
    wa_list_cur = _FakeCursor(fetchall_returns=wa_list_rows)
    wa_list_conn = _FakeConn(wa_list_cur)
    wa4 = SupabaseWebAuthnCredentialBackend(conn_factory=lambda: wa_list_conn)
    actives = wa4.list_active_for_operator(uuid.uuid4())
    check("WebAuthn list_active returns 2 entries", len(actives) == 2)
    check("WebAuthn list entry has credential_id bytes",
          isinstance(actives[0]["credential_id"], bytes))

    # --- SupabasePushSubscriptionBackend -----------------------------------
    new_id = str(uuid.uuid4())
    push_ins_cur = _FakeCursor(fetchone_returns=(new_id,))
    push_ins_conn = _FakeConn(push_ins_cur)
    push = SupabasePushSubscriptionBackend(conn_factory=lambda: push_ins_conn)
    returned_id = push.insert({
        "id": new_id,
        "operator_id": str(uuid.uuid4()),
        "endpoint": "https://push.example.com/v1/abc",
        "p256dh_key": "p256dh-key",
        "auth_key": "auth-key",
        "user_agent": "test-pwa",
    })
    check("Push insert returns id", returned_id == new_id)
    check("Push insert SQL uses ON CONFLICT",
          "ON CONFLICT" in push_ins_cur.executed[0][0])

    # mark_revoked
    push_rev_cur = _FakeCursor()
    push_rev_conn = _FakeConn(push_rev_cur)
    push2 = SupabasePushSubscriptionBackend(conn_factory=lambda: push_rev_conn)
    push2.mark_revoked(new_id, reason="test-410")
    check("Push mark_revoked runs UPDATE",
          "UPDATE public.push_subscriptions" in push_rev_cur.executed[0][0])

    # find_by_id missing
    push_miss_cur = _FakeCursor(fetchone_returns=None)
    push_miss_conn = _FakeConn(push_miss_cur)
    push3 = SupabasePushSubscriptionBackend(conn_factory=lambda: push_miss_conn)
    check("Push find_by_id None when missing", push3.find_by_id(new_id) is None)

    # --- end-to-end: backend wired into RefreshTokenStore + rotation logic --
    # InMemoryRefreshStore is the reference, and the Supabase backend is the
    # production implementation. Verify the Supabase backend, when injected
    # into mobile_cmd_auth.RefreshTokenStore, satisfies the duck-typed surface
    # the rotation logic expects (insert/find_by_hash/mark_used/revoke_family).
    # Soft-skip if pyjwt isn't installed on this host (dev Mac without crypto deps).
    try:
        from lib.mobile_cmd_auth import RefreshTokenStore
        rt_store = RefreshTokenStore(backend=SupabaseRefreshTokenBackend(
            conn_factory=lambda: _FakeConn(_FakeCursor(fetchone_returns=(1,)))
        ))
        affected_via_wrapper = rt_store.revoke_family(uuid.uuid4(), reason="wrapper-smoke")
        check("RefreshTokenStore wrapper proxies revoke_family count via backend",
              affected_via_wrapper == 1)
    except ImportError as exc:
        print(f"  SKIP RefreshTokenStore wrapper test (pyjwt/webauthn missing on this host): {exc}")

    print()
    print(f"TOTAL: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_self_test())
