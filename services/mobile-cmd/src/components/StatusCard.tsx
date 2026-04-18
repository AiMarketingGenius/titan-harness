/**
 * Live status card — polls /api/mobile/claude/status every 5s, surfaces
 * the active/idle/unknown state + last heartbeat excerpt.
 *
 * Graceful-degrade rules:
 * - 503 AuthContextMissing → card shows "Backend awaiting config" state
 *   with the hint inlined. Not an error the operator can fix from the PWA.
 * - Network error → "Connection lost" state + retry button.
 * - 401 before sign-in → card shows "Sign in to see live state".
 */
import { useEffect, useState } from "react";

import { lifecycleApi, AuthContextMissing, NetworkError, ServerError, type ClaudeStatusResp } from "../lib/api";


type LoadState =
  | { kind: "initial" }
  | { kind: "loading" }
  | { kind: "ok"; data: ClaudeStatusResp }
  | { kind: "auth-missing"; hint?: string }
  | { kind: "signed-out" }
  | { kind: "network" }
  | { kind: "server"; status: number; detail?: string };


export function StatusCard() {
  const [state, setState] = useState<LoadState>({ kind: "initial" });

  useEffect(() => {
    let active = true;
    async function load() {
      if (!active) return;
      setState((prev) => (prev.kind === "ok" ? prev : { kind: "loading" }));
      try {
        const data = await lifecycleApi.status();
        if (active) setState({ kind: "ok", data });
      } catch (exc) {
        if (!active) return;
        if (exc instanceof AuthContextMissing) {
          setState({ kind: "auth-missing", hint: exc.hint });
        } else if (exc instanceof NetworkError) {
          setState({ kind: "network" });
        } else if (exc instanceof ServerError) {
          if (exc.status === 401) setState({ kind: "signed-out" });
          else setState({ kind: "server", status: exc.status, detail: exc.detail });
        } else {
          setState({ kind: "server", status: 0, detail: String(exc) });
        }
      }
    }
    load();
    const t = setInterval(load, 5000);
    return () => { active = false; clearInterval(t); };
  }, []);

  return (
    <section className="card status-card" aria-live="polite">
      <header className="card-head">
        <h2>Session</h2>
        <StatusChip state={state} />
      </header>
      <div className="card-body">
        <StatusBody state={state} />
      </div>
    </section>
  );
}


function StatusChip({ state }: { state: LoadState }) {
  if (state.kind === "ok") {
    const cls =
      state.data.status === "active" ? "chip-ok" :
      state.data.status === "idle"   ? "chip-warn" :
      "chip-muted";
    return <span className={`chip ${cls}`}>{state.data.status}</span>;
  }
  if (state.kind === "loading" || state.kind === "initial") return <span className="chip chip-muted">loading</span>;
  if (state.kind === "auth-missing") return <span className="chip chip-warn">config pending</span>;
  if (state.kind === "signed-out") return <span className="chip chip-muted">signed out</span>;
  if (state.kind === "network") return <span className="chip chip-warn">offline</span>;
  return <span className="chip chip-danger">error</span>;
}


function StatusBody({ state }: { state: LoadState }) {
  switch (state.kind) {
    case "initial":
    case "loading":
      return <p className="muted">Reading heartbeat…</p>;
    case "ok": {
      const d = state.data;
      return (
        <>
          <Metric k="Status" v={d.status} />
          <Metric k="MCP" v={d.mcp_reachable ? "connected" : "unreachable"} />
          <Metric k="Queried" v={formatTs(d.queried_at)} />
          {d.last_heartbeat ? (
            <details className="details">
              <summary>Last heartbeat</summary>
              <pre className="json">{JSON.stringify(d.last_heartbeat, null, 2)}</pre>
            </details>
          ) : (
            <p className="muted">No heartbeat yet.</p>
          )}
        </>
      );
    }
    case "auth-missing":
      return (
        <>
          <p>Backend auth context isn’t configured yet.</p>
          {state.hint && <p className="muted hint">{state.hint}</p>}
        </>
      );
    case "signed-out":
      return <p className="muted">Sign in to see the live session state.</p>;
    case "network":
      return <p className="muted">Can’t reach the backend. Will retry.</p>;
    case "server":
      return <p className="muted">Server error {state.status}. {state.detail}</p>;
  }
}


function Metric({ k, v }: { k: string; v: string }) {
  return (
    <div className="metric">
      <span className="metric-k">{k}</span>
      <span className="metric-v">{v}</span>
    </div>
  );
}


function formatTs(iso: string): string {
  try {
    const dt = new Date(iso);
    return dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return iso;
  }
}
