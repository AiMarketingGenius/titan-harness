/**
 * Login — first-time WebAuthn enrollment or returning-operator sign-in.
 *
 * Single-operator MVP: default operator_id is a deterministic UUID derived
 * from the literal "solon" namespace. Multi-operator support moves this
 * to a full operator-lookup step at Step 7 (CRM multi-tenant).
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { register, authenticate, isPlatformAuthenticatorAvailable } from "../lib/webauthn";
import { AuthContextMissing, NetworkError, ServerError } from "../lib/api";


const DEFAULT_OPERATOR_ID = "00000000-0000-0000-0000-000000000001";


export function Login() {
  const nav = useNavigate();
  const [busy, setBusy] = useState<"register" | "signin" | null>(null);
  const [operatorName, setOperatorName] = useState("solon");
  const [error, setError] = useState<string | null>(null);

  const webAuthnAvailable = isPlatformAuthenticatorAvailable();

  async function handleRegister() {
    setBusy("register");
    setError(null);
    try {
      await register({ operatorId: DEFAULT_OPERATOR_ID, operatorName });
      setError("Registered. Tap Sign in to authenticate.");
    } catch (exc) {
      setError(describeError(exc));
    } finally {
      setBusy(null);
    }
  }

  async function handleSignin() {
    setBusy("signin");
    setError(null);
    try {
      await authenticate(DEFAULT_OPERATOR_ID);
      nav("/", { replace: true });
    } catch (exc) {
      setError(describeError(exc));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="page page-login">
      <div className="login-hero">
        <div className="lock-mark" aria-hidden="true">⚡</div>
        <h1>Mobile Command</h1>
        <p className="muted">Operator-only access. WebAuthn required.</p>
      </div>

      {!webAuthnAvailable && (
        <div className="card warn-card">
          This device does not expose a platform authenticator. Use an iPhone
          (Face ID / Touch ID) or a compatible desktop biometric.
        </div>
      )}

      <section className="card">
        <label className="field">
          <span className="field-label">Operator name</span>
          <input
            className="field-input"
            value={operatorName}
            onChange={(e) => setOperatorName(e.target.value)}
            autoComplete="off"
          />
        </label>

        <div className="login-actions">
          <button
            className="action-btn intent-primary"
            onClick={handleSignin}
            disabled={busy !== null || !webAuthnAvailable}
            type="button"
          >
            {busy === "signin" ? "Authenticating…" : "Sign in"}
          </button>
          <button
            className="action-btn intent-ghost"
            onClick={handleRegister}
            disabled={busy !== null || !webAuthnAvailable}
            type="button"
          >
            {busy === "register" ? "Enrolling…" : "Enroll this device"}
          </button>
        </div>

        {error && <div className="toast toast-warn" role="status">{error}</div>}
      </section>
    </div>
  );
}


function describeError(exc: unknown): string {
  if (exc instanceof AuthContextMissing) {
    return "Backend auth context not configured yet. Solon must set DATABASE_URL + JWT keys + apply sql/008 before this flow can complete.";
  }
  if (exc instanceof NetworkError) return "Network error. Check connection and retry.";
  if (exc instanceof ServerError) return `Server ${exc.status}${exc.detail ? `: ${exc.detail}` : ""}`;
  if (exc instanceof Error) return exc.message;
  return String(exc);
}
