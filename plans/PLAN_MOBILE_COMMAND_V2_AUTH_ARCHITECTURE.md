# PLAN — Mobile Command v2 auth/security architecture

**Status:** ARCHITECTURE LOCKED 2026-04-18 per Sonar Pro consult + Solon directive. Implementation (Step 6.1) queued.
**Grounding:** `plans/research/SONAR_PRO_CONSULT_MOBILE_COMMAND_v2_AUTH_2026-04-18.md` (commit `d7d2329`) + `plans/DOCTRINE_SOLON_OS_PRODUCT_BLUEPRINT_v2.md`.
**Supersedes:** any prior Mobile Command v2 auth guidance. Auth0 / Firebase / LocalStorage-JWT patterns are REJECTED.

---

## 1. Scope

Mobile Command v2 is a single-operator PWA installed to Solon's iPhone home screen. Authenticated access to the Atlas API at `operator.aimarketinggenius.io` for remote backend control via REST + WebSocket. Three security layers lock here:

1. **Biometric auth** — FaceID / TouchID via WebAuthn
2. **Token storage + transport** — JWT in encrypted IndexedDB + Authorization-header-on-WebSocket
3. **Push notifications** — VAPID Web Push + JWT-bound send endpoint

Voice pipeline (Deepgram + ElevenLabs + LLM) is OUT of scope for this plan — covered in the product blueprint separately. This plan is auth/security only.

---

## 2. Layer 1 — Biometric authentication (WebAuthn)

### 2.1 Flow

**Enrollment (first install):**
1. Operator adds PWA to Home Screen via Safari "Add to Home Screen."
2. First launch from Home Screen: service worker registers (MUST complete before any WebAuthn call — iOS quirk).
3. PWA calls `navigator.credentials.create({publicKey: {authenticatorSelection: {authenticatorAttachment: "platform", userVerification: "required", residentKey: "required"}, ...}})`
4. iOS prompts for FaceID / TouchID to create the platform-bound credential.
5. Backend receives attestation; stores public key in `webauthn_credentials` table keyed on operator_id.
6. Backend issues first JWT access + refresh token pair.

**Sign-in (subsequent launches):**
1. PWA retrieves credential allowCredentials from IndexedDB (service-worker-registered store).
2. `navigator.credentials.get({publicKey: {allowCredentials: [...], userVerification: "required"}})` — iOS prompts FaceID.
3. Backend verifies signed challenge against stored public key.
4. Backend issues new JWT access + refresh pair; PWA stores encrypted in IndexedDB.

**Fallback:**
- If WebAuthn unavailable (rare on current iOS), fall back to device-PIN-gated JWT refresh via operator password (stored encrypted, never persisted in plaintext).

### 2.2 Library / API choices

- **Frontend:** `@simplewebauthn/browser` (npm, actively maintained 2025-2026). Exposes `startRegistration()` / `startAuthentication()` helpers so React 18 components don't touch raw WebAuthn types.
- **Backend:** `@simplewebauthn/server` (Node.js) OR Python equivalent (`py_webauthn`). Challenge generation, attestation parsing, signature verification.
- **Storage:** IndexedDB via `idb-keyval` npm wrapper. Service worker registered FIRST (`sw.js` from `/mobile-cmd/` root scope).

### 2.3 Database schema (Atlas API side)

```sql
-- Supabase / Postgres table for operator WebAuthn credentials
CREATE TABLE webauthn_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    credential_id BYTEA NOT NULL UNIQUE,
    public_key BYTEA NOT NULL,
    sign_count BIGINT NOT NULL DEFAULT 0,
    transports TEXT[] NOT NULL DEFAULT ARRAY['internal'],
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX idx_webauthn_operator ON webauthn_credentials(operator_id) WHERE revoked_at IS NULL;
```

### 2.4 Atlas API endpoints (new, add to `lib/atlas_api.py`)

- `POST /api/auth/webauthn/register-begin` → returns attestation options (challenge, rp, user, pubKeyCredParams, ...). Rate-limited to 3 enrollment attempts per operator per 24h.
- `POST /api/auth/webauthn/register-verify` → verifies attestation response; stores public key; returns success + JWT pair.
- `POST /api/auth/webauthn/authenticate-begin` → returns assertion options (challenge, allowCredentials, ...).
- `POST /api/auth/webauthn/authenticate-verify` → verifies assertion response; rotates sign_count; returns JWT pair.

### 2.5 Gotcha guard (from consult)

- **iOS 50MB IndexedDB quota:** the PWA MUST NOT accumulate chat history / voice transcripts in the same IndexedDB as credentials. Separate stores, with a quota-monitor + LRU cache eviction on non-essential stores.
- **Service worker registration ordering:** PWA entrypoint `index.html` registers SW before any `credentials.create` call fires. React mount gates on `navigator.serviceWorker.ready`.

---

## 3. Layer 2 — Token storage + transport

### 3.1 JWT pair architecture

**Access token:**
- Lifetime 15 min (consult-recommended).
- Payload: `{sub: operator_id, exp, iat, aud: "atlas-api", scope: "command"}`.
- Signed with backend-held RS256 key (keypair in `/etc/amg/jwt.env` — already exists).
- Sent on every REST + WebSocket call via `Authorization: Bearer <token>`.

**Refresh token:**
- Lifetime 30 days.
- One-time-use, rotated on each refresh.
- Stored in IndexedDB encrypted via Web Crypto AES-GCM (key derived from WebAuthn-gated challenge or operator-PIN; never the default WebCrypto ephemeral key).
- On use, backend invalidates the prior refresh token and issues a new pair. Token-reuse detection revokes the entire chain (security incident — operator must re-enroll via WebAuthn).

### 3.2 Storage pattern

**Wrong (rejected):**
- `localStorage` — clears on PWA uninstall/reinstall, plaintext, XSS-vulnerable.
- HTTP-only cookies — iOS 18+ `SameSite=None + Partitioned` enforcement breaks cross-subdomain WebSocket handshakes (consult cites this as a common failure).

**Right (adopted):**
- `IndexedDB` via `idb-keyval` wrapper.
- Payload encrypted via Web Crypto `crypto.subtle.encrypt({name: "AES-GCM", iv}, key, plaintext)`.
- Encryption key never persisted in plaintext — derived from a WebAuthn-bound session seed each app-launch, OR from a PBKDF2-stretched operator PIN.

### 3.3 WebSocket auth pattern

iOS 18+ SameSite+Partitioned cookie rules make cookie-auth fragile across subdomains. Consult-recommended fix:

```
// Client (after fetch refresh token):
const ws = new WebSocket("wss://memory.aimarketinggenius.io/ws/command");
ws.addEventListener("open", () => {
    ws.send(JSON.stringify({type: "auth", token: accessToken}));  // post-handshake auth message
});
```

Backend: first server-received message on a WebSocket must be an `auth` payload with a valid JWT; otherwise close with code 4401. Validate every 60s; refresh window is server-pushed if access token expiring.

### 3.4 Atlas API endpoints (new)

- `POST /api/auth/refresh` → accepts refresh token, returns new JWT pair, invalidates prior refresh. Rate-limited 10/hr per operator. Detects reuse → revoke chain.
- `POST /api/auth/revoke` → operator-initiated full-chain revocation (logout). Invalidates all active JWT pairs for the operator.
- WebSocket: `/ws/command` — post-handshake auth gate as above.

### 3.5 Schema additions

```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    token_hash BYTEA NOT NULL UNIQUE,
    family_id UUID NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    replaced_by UUID REFERENCES refresh_tokens(id)
);

CREATE INDEX idx_refresh_operator_active ON refresh_tokens(operator_id, family_id)
    WHERE revoked_at IS NULL AND used_at IS NULL;
```

Reuse-detection algorithm: on refresh, if the presented token is already `used_at` (but not yet expired), revoke the entire `family_id` chain + force WebAuthn re-auth.

### 3.6 Gotcha guard

- **Key-derivation lifetime:** the AES-GCM key used to encrypt tokens is derived per-session, not persisted. If the PWA closes, the encrypted ciphertext is useless until WebAuthn re-authenticates the session. Acceptable trade-off: operator gets a FaceID prompt each app-launch; in exchange, stolen PWA-device loss doesn't leak tokens.

---

## 4. Layer 3 — Push notification authentication (VAPID + Web Push)

### 4.1 VAPID key management

- `web-push generate-vapid-keys` produces `publicKey` + `privateKey` pair (ECDH P-256).
- Public key stored in PWA manifest + bundled JS for `pushManager.subscribe` call.
- Private key stored server-side in `/etc/amg/vapid.env` (mode 0600, root:root).
- Rotation: yearly OR on suspected compromise. On rotation, backend signs push payloads with NEW private key; existing subscriptions continue working because subscription endpoint is independent of VAPID key (VAPID just authenticates sends to the push service — FCM/APN).
- Subject URI: `mailto:solon@aimarketinggenius.io` (consult-compliant required field).

### 4.2 Subscription flow

**PWA side:**
```javascript
const registration = await navigator.serviceWorker.ready;
const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,  // iOS requires true
    applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
});
await fetch("/api/push/subscribe", {
    method: "POST",
    headers: {Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json"},
    body: JSON.stringify(subscription),
});
```

**Backend side (new endpoints):**
- `POST /api/push/subscribe` → JWT-authenticated; stores subscription endpoint + keys (p256dh, auth) in `push_subscriptions` table keyed to operator_id.
- `POST /api/push/send` → **JWT-bound**: the send request must come from an authenticated internal caller (Titan operator) with a JWT specifying `scope: push.send`. The consult specifically calls this out to prevent VAPID-public-key-compromise replay: even if the VAPID public key leaks, external attackers can't send because they lack the JWT-bound send endpoint.
- `DELETE /api/push/subscription/{id}` → operator-initiated unsubscribe.

### 4.3 Send pipeline

Use `web-push` npm on backend (Atlas API side). For Python backend, equivalent is `pywebpush`. Pseudocode:

```python
from pywebpush import webpush, WebPushException

def send_push(subscription, payload, vapid_private_key, vapid_subject):
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=vapid_private_key,
            vapid_claims={"sub": vapid_subject},
            ttl=3600,
        )
    except WebPushException as e:
        if e.response.status_code == 410:
            # Subscription expired (iOS 30-day rule) — mark revoked, PWA must re-subscribe
            mark_subscription_revoked(subscription["id"])
        else:
            raise
```

### 4.4 Schema additions

```sql
CREATE TABLE push_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh_key TEXT NOT NULL,
    auth_key TEXT NOT NULL,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revocation_reason TEXT
);

CREATE INDEX idx_push_operator_active ON push_subscriptions(operator_id)
    WHERE revoked_at IS NULL;
```

### 4.5 Gotcha guard (from consult)

- **30-day iOS expiry:** no auto-renew. PWA must detect `revocation_reason = 'expired_410'` on next launch and re-prompt subscription. Service worker can't do this silently — user-initiated action required.
- **No silent push on iOS:** every push notification must have `userVisibleOnly: true` and display a visible UI element. Cannot use push for background sync alone.
- **Delivery not guaranteed:** push is best-effort. Critical commands must still poll over HTTPS — push is a nudge, not a guarantee.
- **PWA icon requirement:** iOS 18+ requires proper PWA icon set (180x180 apple-touch-icon minimum) for subscription to succeed. PWA manifest + icon assets MUST be present.

---

## 5. Implementation sequence (Step 6.1-6.5)

Step 6 architectural gate (this plan) closes → implementation queues as sequential sub-steps:

**6.1 Backend auth module** (`lib/mobile_cmd_auth.py`):
- New file, not edits to `atlas_api.py` until the module imports cleanly.
- Implements WebAuthn register/verify, JWT refresh rotation with reuse detection, VAPID subscribe/send endpoints.
- `py_webauthn` + `pyjwt` + `pywebpush` dependencies.
- Unit tests: challenge generation, signature verification, refresh rotation, reuse detection, VAPID signing.
- Dual-grade ≥9.3 before mounting into atlas_api.py.

**6.2 Database migrations:**
- `sql/008_mobile_cmd_auth.sql`: three tables (webauthn_credentials, refresh_tokens, push_subscriptions) + indices + RLS policies.
- Apply to Supabase prod after migration review.

**6.3 atlas_api.py mount:**
- Import `mobile_cmd_auth` module. Expose 8 endpoints behind new FastAPI router at `/api/auth/*` and `/api/push/*`.
- Systemd restart atlas-api. Smoke test each endpoint.

**6.4 PWA scaffold** (`services/mobile-cmd/`):
- React 18 + Vite + TailwindCSS.
- Service worker at `sw.js` with scope `/mobile-cmd/`.
- WebAuthn + IndexedDB + idb-keyval + jose libraries.
- Minimal UI: login screen, command composer, response feed, push-permission prompt.

**6.5 Lumina + dual-grade pass:**
- Lumina 6-dim visual review on PWA screens.
- Dual-grade the implementation artifacts (mobile_cmd_auth.py + PWA code) at ≥9.3 both engines.
- Commit + mirror + MCP log.

---

## 6. Deferred (post-Monday pitch scope)

- Voice pipeline integration (Deepgram Nova-3 + ElevenLabs Flash v2.5) — covered in separate product blueprint follow-up.
- Multi-tenant operator support — current scope is single-operator (Solon). Multi-operator adds a separate tenant table + row-level scoping.
- Advanced push features (scheduled pushes, grouped notifications, action buttons) — minimal pass first.

---

## 7. Trade-secret discipline

This plan will NOT leak internal vendor names to client-facing surfaces. Third-party dependencies named here (`@simplewebauthn/browser`, `idb-keyval`, `jose`, `pywebpush`) are internal implementation details. PWA user-facing copy never mentions them. Plan is INTERNAL classification.

---

## 8. Rollback

If Step 6.1 implementation destabilizes production atlas-api:
1. Revert the mount commit in `lib/atlas_api.py` (leave `lib/mobile_cmd_auth.py` intact as dormant module).
2. `sudo systemctl restart atlas-api`.
3. Rollback schema migration via `sql/008_mobile_cmd_auth_rollback.sql` (drops the 3 new tables — no impact on existing `/api/revere`, `/api/alex`, `/api/titan` surfaces).

---

## Version

- v1.0 — 2026-04-18, locked post Sonar Pro consult. Implementation sub-steps 6.1-6.5 queued.
