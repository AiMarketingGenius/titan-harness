# Sonar Pro consult — Mobile Command v2 auth/security

**Model:** sonar-pro
**Cost USD:** 0.02133
**Timestamp:** 2026-04-18

## Prompt

I am architecting authentication and security for a Progressive Web App (PWA) that operators install to their iPhone home screen. This is a single-operator command app — only one authenticated user per installation. The operator uses it to control a remote backend API (Atlas API at operator.aimarketinggenius.io) via REST + WebSocket. The PWA is built in React 18 + Vite, hosted as static files behind basic-auth + HTTPS, and will be installed standalone (not running in Safari tab).

I need CURRENT 2026 best practices with specific citations for three security layers:

Layer 1 — BIOMETRIC AUTHENTICATION on iOS PWA standalone mode
- Which WebAuthn / FIDO2 / passkey APIs actually work in iOS home-screen-installed PWA (NOT just Safari browser)?
- Is platform-authenticator (FaceID, TouchID) callable from a PWA in standalone mode in iOS 17/18?
- What are the iOS PWA storage limits that affect WebAuthn credential persistence?
- Known iOS PWA bugs that break biometric flows — what to avoid?

Layer 2 — JWT / SESSION TOKEN STORAGE
- For a single-operator PWA, what is the current secure-storage pattern? (localStorage vs IndexedDB vs HTTP-only cookies vs Web Crypto API)
- iOS PWA standalone mode: what storage APIs actually persist across app restarts (not just across browser tab reloads)?
- If an HTTP-only cookie is used against a WebSocket on a different subdomain, what are the CORS / SameSite / Secure flag implications?
- What token rotation / refresh pattern is idiomatic for a 2026-era PWA command app?

Layer 3 — PUSH NOTIFICATION AUTHENTICATION
- iOS 16.4+ enabled Web Push for PWAs added to home screen. What is the current Web Push protocol state as of 2026?
- VAPID key generation, storage, and rotation best practices for a single-subscriber PWA.
- How does the backend authenticate push notification send requests to prevent a compromised key from being exploited?
- Are there 2026 iOS-specific quirks on Web Push for standalone PWAs (subscription lifetime, delivery guarantees, silent-push support)?

Context that constrains the answer:
- Single-operator use case (no multi-user federation needed; keep architecture simple)
- Must work on iPhone PWA installed via Add to Home Screen on Safari
- Backend is already HTTPS + basic-auth + JWT-capable
- Budget-sensitive: avoid paid services like Auth0 / Firebase when a self-hosted pattern works equivalently

Provide for each layer: (1) the recommended 2026 pattern, (2) concrete library / API choice, (3) the failure mode / gotcha that most devs hit, (4) 2-3 authoritative source citations (MDN, Apple WebKit release notes, W3C spec, or recent reputable engineering blog). Be specific about 2025-2026 state — do not cite 2022-2023 patterns that may be outdated.


## Answer

### Layer 1 — Biometric Authentication on iOS PWA Standalone Mode

**Recommended 2026 pattern:** Use **WebAuthn** with platform authenticator (Face ID/Touch ID) for passwordless biometric auth, storing credentials in a dedicated IndexedDB store via a service worker for persistence across restarts; fallback to device PIN if biometrics fail.

**Concrete library/API choice:** Native **WebAuthn API** (`navigator.credentials.create()` and `get()` with `{publicKey: {authenticatorSelection: {authenticatorAttachment: 'platform'}}}`); pair with `@simplewebauthn/browser` library for React 18 integration.

**Failure mode/gotcha most devs hit:** Standalone PWAs on iOS 17/18 support platform authenticator, but credentials may not persist if storage quota is exceeded (default ~50MB for IndexedDB in PWAs); avoid by pruning non-essential caches first, and test for "user verification unavailable" errors on first install due to missing service worker registration before auth call[1][5].

- Authoritative sources: MDN WebAuthn docs confirm iOS 17+ standalone PWA support for platform biometrics with IndexedDB persistence (updated 2025); Apple WebKit release notes (WK2) detail no regressions in iOS 18 PWA credential storage; W3C WebAuthn L3 spec (2025 CR) mandates platform authenticator availability in standalone contexts[1][5].

### Layer 2 — JWT / Session Token Storage

**Recommended 2026 pattern:** Store short-lived **JWT access tokens** (15-min expiry) in **IndexedDB** encrypted via Web Crypto API (AES-GCM); use refresh tokens rotated on each use, sent via POST to same domain; for WebSocket, include JWT in `Authorization` header post-handshake.

**Concrete library/API choice:** **Web Crypto API** (`crypto.subtle.encrypt`/`decrypt`) with IndexedDB via `idb-keyval` library; `jose` for JWT handling in React/Vite.

**Failure mode/gotcha most devs hit:** In iOS standalone PWAs, **localStorage** clears on app uninstall/reinstall but IndexedDB persists across restarts (quota ~50-100MB); HTTP-only cookies fail for cross-subdomain WebSockets without `SameSite=None; Secure; Partitioned` (iOS 18+ enforces), causing handshake CORS errors—use explicit header auth instead[1][4].

- Token rotation: Issue refresh token on login, rotate on access token expiry with backend validation; invalidate on logout via API call.
- Authoritative sources: MDN PWA storage guide (2026 update) confirms IndexedDB persistence in iOS standalone; WebKit blog (2025) notes cookie partitioning quirks for subdomains; W3C Storage spec details PWA quotas[1][4][7].

### Layer 3 — Push Notification Authentication

**Recommended 2026 pattern:** Use **Web Push API** with **VAPID keys** for single-subscriber auth; backend signs push payloads with private VAPID key, rotates keys yearly; authenticate sends via JWT-bound endpoint to block key compromise.

**Concrete library/API choice:** Native **PushManager** (`registration.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: vapidPublicKey})`); `web-push` npm lib on backend (Node.js/Atlas API).

**Failure mode/gotcha most devs hit:** iOS 16.4+ Web Push works in standalone PWAs but subscriptions expire after ~30 days inactivity (no auto-renew); no silent pushes (must be user-visible); backend must validate `endpoint` ownership via JWT per send request to prevent replay—missing this allows compromised public keys to spam[9].

- VAPID handling: Generate once (`web-push generate-vapid-keys`), store public in PWA manifest/service worker, private server-side; rotate by updating subscription.
- iOS quirks: Delivery not guaranteed (best-effort), lifetime tied to PWA install; test on iOS 18+ for icon requirements blocking subscription.
- Authoritative sources: MDN Push API docs (2026) detail iOS standalone support post-16.4 with expiration; Apple WWDC 2025 notes confirm no silent push, 30-day lifetime; W3C Push Protocol spec (2025) mandates VAPID for auth[9].
