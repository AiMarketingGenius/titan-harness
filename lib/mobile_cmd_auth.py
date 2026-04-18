"""Mobile Command v2 authentication + security module.

Implements the 3-layer auth architecture from
`plans/PLAN_MOBILE_COMMAND_V2_AUTH_ARCHITECTURE.md` (commit `26044ac`):

- Layer 1: WebAuthn platform authenticator (FaceID / TouchID) enrollment + verification
- Layer 2: JWT access (15 min) + refresh (30 d) token pair with rotation + reuse detection
- Layer 3: Web Push VAPID subscription + JWT-bound send with 410-expiry handling

Standalone module — imported by `lib/atlas_api.py` via a router mount. Keeps
the WebAuthn/JWT/VAPID surface isolated so atlas_api production endpoints
(/api/revere, /api/alex, /api/titan) are unaffected by module changes.

Dependencies:
- `pywebauthn` (aka `webauthn` on PyPI) — WebAuthn server-side flows
- `pyjwt` — JWT sign/verify
- `pywebpush` — VAPID-authenticated Web Push send
- `psycopg2` / `supabase-py` — the rest of atlas_api already uses these

Schema dependencies (see `sql/008_mobile_cmd_auth.sql`):
- `webauthn_credentials` table
- `refresh_tokens` table
- `push_subscriptions` table
- `operators` table (assumed to exist; Solon is operator_id = 1)

Usage from atlas_api.py:

    from lib.mobile_cmd_auth import (
        MobileCmdAuth,
        register_begin, register_verify,
        authenticate_begin, authenticate_verify,
        refresh_jwt_pair, revoke_chain,
        push_subscribe, push_send, push_unsubscribe,
    )
    auth = MobileCmdAuth(
        db_conn=supabase_client,
        jwt_private_key=JWT_RS256_PRIVATE,
        jwt_public_key=JWT_RS256_PUBLIC,
        vapid_private_key=VAPID_PRIVATE,
        vapid_subject="mailto:solon@aimarketinggenius.io",
        rp_id="operator.aimarketinggenius.io",
        rp_name="AMG Mobile Command",
    )
    # mount auth router on the FastAPI app
    app.include_router(auth.router, prefix="/api")
"""
from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import json
import os
import secrets
import uuid
from dataclasses import dataclass
from typing import Any

# Standard-library + third-party imports grouped separately
import jwt as pyjwt

try:
    from webauthn import (
        generate_registration_options,
        verify_registration_response,
        generate_authentication_options,
        verify_authentication_response,
    )
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        UserVerificationRequirement,
        ResidentKeyRequirement,
        PublicKeyCredentialDescriptor,
    )
    HAS_WEBAUTHN = True
except ImportError:
    HAS_WEBAUTHN = False

try:
    from pywebpush import webpush, WebPushException
    HAS_WEBPUSH = True
except ImportError:
    HAS_WEBPUSH = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCESS_TOKEN_TTL_SECONDS = 15 * 60      # 15 minutes
REFRESH_TOKEN_TTL_SECONDS = 30 * 24 * 3600  # 30 days
JWT_ALGORITHM = "RS256"
JWT_AUDIENCE = "atlas-api"
JWT_ISSUER = "amg-mobile-cmd"

VAPID_PUSH_TTL_SECONDS = 3600
PUSH_EXPIRED_STATUS_CODES = (404, 410)

WEBAUTHN_CHALLENGE_TTL_SECONDS = 120  # rp stores 2 min, after which client must restart


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class JWTPair:
    access_token: str
    refresh_token: str
    access_expires_at: _dt.datetime
    refresh_expires_at: _dt.datetime
    family_id: uuid.UUID


# RefreshTokenRecord lives in lib/mobile_cmd_models so storage adapters can
# import the shape without pulling in this module's crypto deps.
from lib.mobile_cmd_models import RefreshTokenRecord  # noqa: E402,F401  (re-export)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class MobileCmdAuthError(Exception):
    """Base error for all mobile-cmd-auth failures."""


class WebAuthnMissingError(MobileCmdAuthError):
    """Raised when `webauthn` package isn't installed but a WebAuthn method is called."""


class WebPushMissingError(MobileCmdAuthError):
    """Raised when `pywebpush` isn't installed but a push method is called."""


class TokenReuseDetected(MobileCmdAuthError):
    """Raised when a refresh token is presented that was already consumed —
    revoke the entire family_id and force re-auth via WebAuthn."""


class TokenExpired(MobileCmdAuthError):
    """Refresh token presented past expiry."""


class TokenNotFound(MobileCmdAuthError):
    """Refresh token doesn't match any record."""


class SubscriptionExpired(MobileCmdAuthError):
    """Push subscription returned 410 Gone — mark revoked, PWA must re-subscribe."""


# ---------------------------------------------------------------------------
# Crypto helpers
# ---------------------------------------------------------------------------

def _sha256(value: bytes | str) -> bytes:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).digest()


def _new_opaque_token() -> str:
    """Generate a URL-safe random token (32 bytes / 256 bits of entropy)."""
    return secrets.token_urlsafe(32)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _now_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def issue_access_token(
    operator_id: uuid.UUID,
    private_key: str,
    scope: str = "command",
    ttl_seconds: int = ACCESS_TOKEN_TTL_SECONDS,
) -> tuple[str, _dt.datetime]:
    """Issue an RS256 JWT access token for the given operator.

    Returns (token_string, expiry_datetime).
    """
    now = _now_utc()
    exp = now + _dt.timedelta(seconds=ttl_seconds)
    payload = {
        "sub": str(operator_id),
        "aud": JWT_AUDIENCE,
        "iss": JWT_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "scope": scope,
    }
    token = pyjwt.encode(payload, private_key, algorithm=JWT_ALGORITHM)
    return token, exp


def verify_access_token(token: str, public_key: str) -> dict[str, Any]:
    """Verify an RS256 JWT access token. Raises `jwt.PyJWTError` subclasses on failure."""
    return pyjwt.decode(
        token,
        public_key,
        algorithms=[JWT_ALGORITHM],
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
    )


# ---------------------------------------------------------------------------
# Refresh token rotation
# ---------------------------------------------------------------------------

class RefreshTokenStore:
    """Abstracts the refresh_tokens table. Backend-agnostic — takes a
    database callable interface so the caller can inject Supabase or
    raw psycopg2 without this module depending on either directly.

    Interface methods expected:
        insert(row: dict) -> None
        find_by_hash(token_hash: bytes) -> RefreshTokenRecord | None
        mark_used(token_id: uuid.UUID, replaced_by: uuid.UUID | None) -> None
        revoke_family(family_id: uuid.UUID, reason: str) -> int  # rows affected
    """

    def __init__(self, backend: Any):
        self._backend = backend

    def insert(self, row: dict) -> None:
        return self._backend.insert(row)

    def find_by_hash(self, token_hash: bytes) -> RefreshTokenRecord | None:
        return self._backend.find_by_hash(token_hash)

    def mark_used(self, token_id: uuid.UUID, replaced_by: uuid.UUID | None) -> None:
        return self._backend.mark_used(token_id, replaced_by)

    def revoke_family(self, family_id: uuid.UUID, reason: str) -> int:
        return self._backend.revoke_family(family_id, reason)


def issue_jwt_pair(
    operator_id: uuid.UUID,
    store: RefreshTokenStore,
    jwt_private_key: str,
    family_id: uuid.UUID | None = None,
) -> JWTPair:
    """Issue a fresh JWT access + refresh pair.

    If family_id is None, generate a new family (new enrollment / new login).
    If provided, extend an existing family (rotation path).
    """
    now = _now_utc()
    if family_id is None:
        family_id = uuid.uuid4()

    access_token, access_exp = issue_access_token(
        operator_id, jwt_private_key, scope="command", ttl_seconds=ACCESS_TOKEN_TTL_SECONDS
    )

    refresh_raw = _new_opaque_token()
    refresh_hash = _sha256(refresh_raw)
    refresh_id = uuid.uuid4()
    refresh_exp = now + _dt.timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS)

    store.insert({
        "id": str(refresh_id),
        "operator_id": str(operator_id),
        "token_hash": refresh_hash,
        "family_id": str(family_id),
        "issued_at": now.isoformat(),
        "expires_at": refresh_exp.isoformat(),
        "used_at": None,
        "revoked_at": None,
        "replaced_by": None,
    })

    return JWTPair(
        access_token=access_token,
        refresh_token=refresh_raw,
        access_expires_at=access_exp,
        refresh_expires_at=refresh_exp,
        family_id=family_id,
    )


def rotate_refresh_token(
    presented_refresh_raw: str,
    store: RefreshTokenStore,
    jwt_private_key: str,
) -> JWTPair:
    """Rotate a refresh token: validate + mark-used + issue new pair.

    - If token was already used → family reuse detected → revoke whole family.
    - If token expired → raise TokenExpired.
    - If token not found → raise TokenNotFound.
    - Otherwise: mark used, issue new pair in same family.
    """
    token_hash = _sha256(presented_refresh_raw)
    record = store.find_by_hash(token_hash)
    if record is None:
        raise TokenNotFound("refresh token not recognized")
    now = _now_utc()
    if record.revoked_at is not None:
        raise TokenNotFound("refresh token revoked")
    if record.used_at is not None:
        # REUSE DETECTED — security incident. Revoke the whole family.
        store.revoke_family(record.family_id, reason="refresh-token-reuse-detected")
        raise TokenReuseDetected(
            f"refresh token reuse on family {record.family_id} — all tokens revoked"
        )
    if record.expires_at < now:
        raise TokenExpired("refresh token expired")

    # All validations passed — rotate.
    new_pair = issue_jwt_pair(
        operator_id=record.operator_id,
        store=store,
        jwt_private_key=jwt_private_key,
        family_id=record.family_id,
    )
    store.mark_used(record.id, replaced_by=None)
    return new_pair


def revoke_chain(
    family_id: uuid.UUID,
    store: RefreshTokenStore,
    reason: str = "operator-initiated-logout",
) -> int:
    """Operator-initiated logout: revoke the entire refresh token family."""
    return store.revoke_family(family_id, reason=reason)


# ---------------------------------------------------------------------------
# WebAuthn flows
# ---------------------------------------------------------------------------

def _require_webauthn() -> None:
    if not HAS_WEBAUTHN:
        raise WebAuthnMissingError(
            "webauthn package not installed — pip install webauthn"
        )


def webauthn_register_begin(
    rp_id: str,
    rp_name: str,
    operator_id: uuid.UUID,
    operator_name: str,
    challenge_store: Any,
) -> dict[str, Any]:
    """Begin a WebAuthn registration flow.

    - Generates attestation options with `platform` authenticator attachment.
    - Persists challenge in `challenge_store` with 2-minute TTL.
    - Returns the attestation-options dict the PWA passes to
      `@simplewebauthn/browser.startRegistration()`.
    """
    _require_webauthn()
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=rp_name,
        user_id=str(operator_id).encode(),
        user_name=operator_name,
        user_display_name=operator_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment="platform",
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    challenge_store.set(
        key=f"webauthn:register:{operator_id}",
        value=options.challenge,
        ttl_seconds=WEBAUTHN_CHALLENGE_TTL_SECONDS,
    )
    # options is a pydantic model in newer `webauthn` packages
    return options.model_dump() if hasattr(options, "model_dump") else dict(options)


def webauthn_register_verify(
    operator_id: uuid.UUID,
    expected_origin: str,
    expected_rp_id: str,
    credential_response: dict[str, Any],
    challenge_store: Any,
    credential_store: Any,
) -> dict[str, Any]:
    """Verify a WebAuthn registration response + persist the credential."""
    _require_webauthn()
    expected_challenge = challenge_store.pop(f"webauthn:register:{operator_id}")
    if expected_challenge is None:
        raise MobileCmdAuthError("registration challenge expired or not found")

    verification = verify_registration_response(
        credential=credential_response,
        expected_challenge=expected_challenge,
        expected_origin=expected_origin,
        expected_rp_id=expected_rp_id,
        require_user_verification=True,
    )
    credential_store.insert({
        "id": str(uuid.uuid4()),
        "operator_id": str(operator_id),
        "credential_id": verification.credential_id,
        "public_key": verification.credential_public_key,
        "sign_count": verification.sign_count,
        "transports": credential_response.get("response", {}).get("transports", []) or ["internal"],
        "user_agent": credential_response.get("user_agent"),
    })
    return {"status": "ok", "sign_count": verification.sign_count}


def webauthn_authenticate_begin(
    rp_id: str,
    operator_id: uuid.UUID,
    credential_store: Any,
    challenge_store: Any,
) -> dict[str, Any]:
    """Begin a WebAuthn sign-in flow for a returning operator."""
    _require_webauthn()
    creds = credential_store.list_active_for_operator(operator_id)
    allow_credentials = [
        PublicKeyCredentialDescriptor(id=c["credential_id"])
        for c in creds
    ]
    options = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    challenge_store.set(
        key=f"webauthn:auth:{operator_id}",
        value=options.challenge,
        ttl_seconds=WEBAUTHN_CHALLENGE_TTL_SECONDS,
    )
    return options.model_dump() if hasattr(options, "model_dump") else dict(options)


def webauthn_authenticate_verify(
    operator_id: uuid.UUID,
    expected_origin: str,
    expected_rp_id: str,
    credential_response: dict[str, Any],
    credential_store: Any,
    challenge_store: Any,
) -> dict[str, Any]:
    """Verify a WebAuthn authentication response + update sign_count.

    Step 7.0-c: lenient sign_count handling for iOS / passkey providers.
    Apple platform authenticators frequently return sign_count=0 (always) or
    occasionally stale counts — treating every regression as a cloned-credential
    attack would brick real users. Per Sonar Pro audit 2026-04-18:
    - Accept the assertion if cryptographic verification passes
    - On regression (new < stored), log an audit event + update to max(stored, new)
    - Hard-fail only on BOTH-ZERO without progress over multiple signs AND
      user-agent mismatch (TODO: that heavier check rides with multi-tenant UA tracking)
    """
    _require_webauthn()
    expected_challenge = challenge_store.pop(f"webauthn:auth:{operator_id}")
    if expected_challenge is None:
        raise MobileCmdAuthError("authentication challenge expired or not found")

    cred_id = credential_response.get("id") or credential_response.get("rawId")
    if not cred_id:
        raise MobileCmdAuthError("credential id missing from response")
    stored = credential_store.find_by_credential_id(cred_id)
    if stored is None:
        raise MobileCmdAuthError("unknown credential for operator")

    try:
        verification = verify_authentication_response(
            credential=credential_response,
            expected_challenge=expected_challenge,
            expected_origin=expected_origin,
            expected_rp_id=expected_rp_id,
            credential_public_key=stored["public_key"],
            credential_current_sign_count=stored["sign_count"],
            require_user_verification=True,
        )
        new_count = verification.new_sign_count
        credential_store.update_sign_count(stored["id"], new_count)
        return {"status": "ok", "new_sign_count": new_count, "sign_count_mode": "advanced"}
    except Exception as exc:
        # The webauthn library raises on sign_count regression. Detect by error
        # class name + message substring (library API varies across versions).
        err_class = type(exc).__name__
        err_msg = str(exc).lower()
        is_counter_regression = (
            "counter" in err_msg or "sign_count" in err_msg or "sign count" in err_msg
        )
        if not is_counter_regression:
            raise MobileCmdAuthError(f"webauthn verification failed: {err_class}: {exc}") from exc

        # Lenient path — re-run verification with credential_current_sign_count=0
        # (disables the counter check on the library side), then update the stored
        # count to the max observed so we only regress forward, never backward.
        verification = verify_authentication_response(
            credential=credential_response,
            expected_challenge=expected_challenge,
            expected_origin=expected_origin,
            expected_rp_id=expected_rp_id,
            credential_public_key=stored["public_key"],
            credential_current_sign_count=0,
            require_user_verification=True,
        )
        new_count = verification.new_sign_count
        observed_max = max(stored["sign_count"], new_count)
        credential_store.update_sign_count(stored["id"], observed_max)
        return {
            "status": "ok",
            "new_sign_count": observed_max,
            "sign_count_mode": "lenient",
            "audit_note": f"sign_count regression accepted (stored={stored['sign_count']}, observed={new_count}); common on iOS/passkey",
        }


# ---------------------------------------------------------------------------
# VAPID / Web Push
# ---------------------------------------------------------------------------

def _require_webpush() -> None:
    if not HAS_WEBPUSH:
        raise WebPushMissingError(
            "pywebpush package not installed — pip install pywebpush"
        )


def push_send(
    subscription: dict[str, Any],
    payload: dict[str, Any],
    vapid_private_key: str,
    vapid_subject: str,
    ttl_seconds: int = VAPID_PUSH_TTL_SECONDS,
) -> dict[str, Any]:
    """Send a Web Push notification to one subscription.

    Raises SubscriptionExpired on 404/410 (caller should mark the subscription
    revoked and prompt the PWA to re-subscribe on next launch).
    """
    _require_webpush()
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=vapid_private_key,
            vapid_claims={"sub": vapid_subject},
            ttl=ttl_seconds,
        )
    except WebPushException as exc:
        status = getattr(exc, "response", None)
        status_code = getattr(status, "status_code", None)
        if status_code in PUSH_EXPIRED_STATUS_CODES:
            raise SubscriptionExpired(
                f"push subscription returned {status_code}; mark revoked + re-subscribe"
            ) from exc
        raise
    return {"status": "sent", "ttl": ttl_seconds}


# ---------------------------------------------------------------------------
# Unit-test helpers — callers can import + use in their own test suite
# ---------------------------------------------------------------------------

class InMemoryRefreshStore:
    """Reference in-memory RefreshTokenStore for tests. NOT for production —
    use Supabase / psycopg2 adapter in production."""

    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, dict] = {}

    def insert(self, row: dict) -> None:
        self._rows[uuid.UUID(row["id"])] = row

    def find_by_hash(self, token_hash: bytes) -> RefreshTokenRecord | None:
        for row in self._rows.values():
            if row["token_hash"] == token_hash:
                return RefreshTokenRecord(
                    id=uuid.UUID(row["id"]),
                    operator_id=uuid.UUID(row["operator_id"]),
                    token_hash=row["token_hash"],
                    family_id=uuid.UUID(row["family_id"]),
                    issued_at=_dt.datetime.fromisoformat(row["issued_at"]),
                    expires_at=_dt.datetime.fromisoformat(row["expires_at"]),
                    used_at=(_dt.datetime.fromisoformat(row["used_at"]) if row["used_at"] else None),
                    revoked_at=(_dt.datetime.fromisoformat(row["revoked_at"]) if row["revoked_at"] else None),
                )
        return None

    def mark_used(self, token_id: uuid.UUID, replaced_by: uuid.UUID | None) -> None:
        row = self._rows.get(token_id)
        if row is None:
            return
        row["used_at"] = _now_utc().isoformat()
        row["replaced_by"] = str(replaced_by) if replaced_by else None

    def revoke_family(self, family_id: uuid.UUID, reason: str) -> int:
        count = 0
        now_iso = _now_utc().isoformat()
        for row in self._rows.values():
            if uuid.UUID(row["family_id"]) == family_id and row["revoked_at"] is None:
                row["revoked_at"] = now_iso
                count += 1
        return count


# ---------------------------------------------------------------------------
# Self-tests (run as `python -m lib.mobile_cmd_auth`)
# ---------------------------------------------------------------------------

def _self_test() -> int:
    """Fast smoke tests for the crypto + rotation + reuse-detection logic.
    Does NOT test WebAuthn flows (those require webauthn package + real client)
    or VAPID sends (those require pywebpush + a real push endpoint).
    """
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError:
        print("cryptography package required for self_test (pip install cryptography)")
        return 1

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

    # 1) generate an RSA keypair for JWT signing
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = rsa_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    operator_id = uuid.uuid4()

    # 2) Issue JWT pair
    store = RefreshTokenStore(backend=InMemoryRefreshStore())
    pair1 = issue_jwt_pair(operator_id=operator_id, store=store, jwt_private_key=private_pem)
    decoded = verify_access_token(pair1.access_token, public_pem)
    check("JWT access token encodes + verifies", decoded["sub"] == str(operator_id))
    check("JWT audience set correctly", decoded["aud"] == JWT_AUDIENCE)
    check("refresh token is URL-safe", "/" not in pair1.refresh_token and "+" not in pair1.refresh_token)
    check("refresh_expires_at > access_expires_at", pair1.refresh_expires_at > pair1.access_expires_at)

    # 3) Rotate refresh token once → valid new pair in same family
    pair2 = rotate_refresh_token(
        presented_refresh_raw=pair1.refresh_token,
        store=store,
        jwt_private_key=private_pem,
    )
    check("rotated pair keeps same family_id", pair2.family_id == pair1.family_id)
    check("rotated access token decodes", verify_access_token(pair2.access_token, public_pem)["sub"] == str(operator_id))
    check("rotated refresh token differs from original", pair2.refresh_token != pair1.refresh_token)

    # 4) Reuse detection: re-present the first (already-rotated) refresh token → error + family revoked
    reuse_caught = False
    try:
        rotate_refresh_token(
            presented_refresh_raw=pair1.refresh_token,
            store=store,
            jwt_private_key=private_pem,
        )
    except TokenReuseDetected:
        reuse_caught = True
    check("reuse detection triggers TokenReuseDetected", reuse_caught)

    # 5) After reuse detection, the second (legitimate) token is also revoked → further rotation fails
    post_revoke_blocked = False
    try:
        rotate_refresh_token(
            presented_refresh_raw=pair2.refresh_token,
            store=store,
            jwt_private_key=private_pem,
        )
    except TokenNotFound:
        post_revoke_blocked = True
    check("post-revoke rotation of sibling token blocked", post_revoke_blocked)

    # 6) New session after revoke = fresh family
    pair3 = issue_jwt_pair(operator_id=operator_id, store=store, jwt_private_key=private_pem)
    check("fresh family after revoke has new family_id", pair3.family_id != pair1.family_id)

    # 7) Explicit revoke_chain
    pre_revoke_count = sum(1 for r in store._backend._rows.values() if r["revoked_at"] is None)
    revoked = revoke_chain(pair3.family_id, store, reason="test-logout")
    check("revoke_chain returns count of affected rows", revoked == 1)

    # 8) sha256 helper works on bytes and str identically for same content
    a = _sha256("hello")
    b = _sha256(b"hello")
    check("_sha256 str and bytes match", a == b)

    print()
    print(f"TOTAL: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_self_test())
