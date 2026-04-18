/**
 * Home — the 4 lifecycle buttons Solon's mobile UI surfaces.
 *
 * Each button calls the matching /api/mobile/claude/* endpoint + surfaces
 * a last-action toast. The status card beside it polls /status every 5s
 * so the operator sees the aftermath of any action in near-real-time.
 */
import { useState } from "react";

import { StatusCard } from "../components/StatusCard";
import { lifecycleApi, AuthContextMissing, NetworkError, ServerError, type ClaudeActionResp } from "../lib/api";
import { getOperator } from "../lib/auth";


type Toast =
  | null
  | { kind: "ok"; action: string; detail: string }
  | { kind: "warn"; action: string; detail: string }
  | { kind: "err"; action: string; detail: string };


export function Home() {
  const [toast, setToast] = useState<Toast>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function runAction(
    action: "start" | "stop" | "reset",
    fn: (operatorId: string) => Promise<ClaudeActionResp>,
  ) {
    setBusy(action);
    try {
      const op = await getOperator();
      const operatorId = op?.operatorId ?? "solon";
      const result = await fn(operatorId);
      const processAction = result.process?.action ?? "ok";
      const kind = processAction.startsWith("ctl_") || processAction === "no_live_process"
        ? "warn"
        : "ok";
      setToast({
        kind,
        action,
        detail: `${processAction}${result.process?.error ? `: ${result.process.error}` : ""}`,
      });
    } catch (exc) {
      if (exc instanceof AuthContextMissing) {
        setToast({ kind: "warn", action, detail: "backend auth context not configured" });
      } else if (exc instanceof NetworkError) {
        setToast({ kind: "err", action, detail: "network error" });
      } else if (exc instanceof ServerError) {
        setToast({ kind: "err", action, detail: `server ${exc.status}: ${exc.detail ?? ""}` });
      } else {
        setToast({ kind: "err", action, detail: String(exc) });
      }
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="page page-home">
      <StatusCard />

      <section className="card action-card">
        <header className="card-head"><h2>Lifecycle</h2></header>
        <div className="action-grid">
          <ActionButton label="Start" intent="primary" busy={busy === "start"}
            onClick={() => runAction("start", (op) => lifecycleApi.start(op))} />
          <ActionButton label="Stop" intent="danger" busy={busy === "stop"}
            onClick={() => runAction("stop", (op) => lifecycleApi.stop(op, "mobile_stop_button"))} />
          <ActionButton label="Reset" intent="warn" busy={busy === "reset"}
            onClick={() => runAction("reset", (op) => lifecycleApi.reset(op))} />
          <ActionButton label="Status" intent="ghost" busy={false}
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} />
        </div>
        {toast && (
          <div className={`toast toast-${toast.kind}`} role="status">
            <strong>{toast.action}</strong> — {toast.detail}
          </div>
        )}
      </section>
    </div>
  );
}


interface ActionButtonProps {
  label: string;
  intent: "primary" | "danger" | "warn" | "ghost";
  busy: boolean;
  onClick: () => void;
}

function ActionButton({ label, intent, busy, onClick }: ActionButtonProps) {
  return (
    <button
      className={`action-btn intent-${intent}`}
      onClick={onClick}
      disabled={busy}
      type="button"
    >
      {busy ? "…" : label}
    </button>
  );
}
