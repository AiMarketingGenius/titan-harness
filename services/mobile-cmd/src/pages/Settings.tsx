/**
 * Settings — operator identity, push opt-in, sign-out.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getOperator, signOut, type OperatorIdentity } from "../lib/auth";
import { canSubscribe, subscribePush, unsubscribePush, requestPermission } from "../lib/push";


export function Settings() {
  const nav = useNavigate();
  const [op, setOp] = useState<OperatorIdentity | null>(null);
  const [permission, setPermission] = useState<NotificationPermission>("default");
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    getOperator().then(setOp);
    if ("Notification" in window) setPermission(Notification.permission);
  }, []);

  async function handleEnablePush() {
    if (!op) { setToast("sign in first"); return; }
    setBusy("push-enable");
    try {
      const perm = await requestPermission();
      setPermission(perm);
      if (perm === "granted") {
        const res = await subscribePush(op.operatorId);
        setToast(`subscribed (id=${res.id.slice(0, 8)}…)`);
      } else {
        setToast(`permission ${perm}`);
      }
    } catch (exc) {
      setToast(`error: ${(exc as Error).message}`);
    } finally {
      setBusy(null);
    }
  }

  async function handleDisablePush() {
    setBusy("push-disable");
    try {
      await unsubscribePush();
      setToast("unsubscribed locally");
    } catch (exc) {
      setToast(`error: ${(exc as Error).message}`);
    } finally {
      setBusy(null);
    }
  }

  async function handleSignOut() {
    setBusy("signout");
    await signOut(true);
    nav("/login", { replace: true });
  }

  const pushOk = canSubscribe();

  return (
    <div className="page page-settings">
      <section className="card">
        <header className="card-head"><h2>Operator</h2></header>
        {op ? (
          <>
            <div className="metric"><span className="metric-k">ID</span><span className="metric-v mono">{op.operatorId}</span></div>
            <div className="metric"><span className="metric-k">Name</span><span className="metric-v">{op.operatorName}</span></div>
            <div className="metric"><span className="metric-k">Enrolled</span><span className="metric-v">{new Date(op.enrolledAt).toLocaleDateString()}</span></div>
          </>
        ) : (
          <p className="muted">No operator enrolled on this device.</p>
        )}
      </section>

      <section className="card">
        <header className="card-head"><h2>Push notifications</h2></header>
        <div className="metric"><span className="metric-k">Permission</span><span className="metric-v">{permission}</span></div>
        <div className="metric"><span className="metric-k">Capable</span><span className="metric-v">{pushOk ? "yes" : "no (install to home screen + set VAPID key)"}</span></div>
        <div className="login-actions">
          <button className="action-btn intent-primary" disabled={!pushOk || busy !== null}
                  onClick={handleEnablePush} type="button">
            {busy === "push-enable" ? "…" : "Enable"}
          </button>
          <button className="action-btn intent-ghost" disabled={busy !== null}
                  onClick={handleDisablePush} type="button">
            {busy === "push-disable" ? "…" : "Disable"}
          </button>
        </div>
      </section>

      <section className="card">
        <header className="card-head"><h2>Session</h2></header>
        <button className="action-btn intent-danger" disabled={busy !== null}
                onClick={handleSignOut} type="button">
          {busy === "signout" ? "Signing out…" : "Sign out"}
        </button>
      </section>

      {toast && <div className="toast toast-warn" role="status">{toast}</div>}
    </div>
  );
}
