/**
 * Mobile Command v2 — backend client.
 *
 * Thin wrapper over fetch() that:
 * - prefixes API base URL (VITE_API_BASE_URL env at build, default operator.aimarketinggenius.io/api)
 * - attaches the JWT access token from IndexedDB (via getAccessToken() from auth.ts)
 * - refreshes the JWT pair on 401 via /api/auth/refresh (rotation)
 * - surfaces typed errors the UI can distinguish:
 *     AuthContextMissing — backend returned 503 mobile_auth_context_unavailable
 *     TokenReuseDetected — backend returned 401 TokenReuseDetected (forces WebAuthn re-auth)
 *     NetworkError       — fetch threw
 *     ServerError        — any non-2xx / non-handled response
 *
 * Keeps API surface explicit (named functions per endpoint) rather than a giant
 * generic client, so the PWA code reads clearly at each call site.
 */
import { getAccessToken, setTokenPair, clearTokens, type TokenPair } from "./auth";

const DEFAULT_API_BASE = "/api";
const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) || DEFAULT_API_BASE;


export class AuthContextMissing extends Error {
  hint?: string;
  constructor(hint?: string) {
    super("mobile auth context unavailable on backend");
    this.name = "AuthContextMissing";
    this.hint = hint;
  }
}

export class TokenReuseDetected extends Error {
  constructor() {
    super("refresh token reuse detected — re-auth required");
    this.name = "TokenReuseDetected";
  }
}

export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

export class ServerError extends Error {
  status: number;
  detail?: string;
  constructor(status: number, detail?: string) {
    super(`server error ${status}: ${detail ?? ""}`);
    this.name = "ServerError";
    this.status = status;
    this.detail = detail;
  }
}


interface RequestOpts {
  method?: "GET" | "POST" | "DELETE";
  body?: unknown;
  auth?: boolean;  // attach access token; default true
  retryOn401?: boolean;  // attempt refresh + retry once; default true
}


async function request<T>(path: string, opts: RequestOpts = {}): Promise<T> {
  const {
    method = "GET",
    body,
    auth = true,
    retryOn401 = true,
  } = opts;
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["content-type"] = "application/json";
  if (auth) {
    const tok = await getAccessToken();
    if (tok) headers["authorization"] = `Bearer ${tok}`;
  }

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: "same-origin",
    });
  } catch (exc) {
    throw new NetworkError((exc as Error).message);
  }

  if (res.status === 503) {
    const err = await res.json().catch(() => ({}));
    if (err?.error === "mobile_auth_context_unavailable") {
      throw new AuthContextMissing(err.hint);
    }
  }

  if (res.status === 401 && auth && retryOn401) {
    // Try refresh rotation once.
    const refreshed = await tryRefresh();
    if (refreshed) {
      return request<T>(path, { ...opts, retryOn401: false });
    }
    const err = await res.json().catch(() => ({}));
    if (err?.error === "TokenReuseDetected") {
      clearTokens();
      throw new TokenReuseDetected();
    }
    throw new ServerError(401, err?.detail);
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ServerError(res.status, err?.detail ?? err?.error);
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return (await res.json()) as T;
  }
  return (await res.text()) as T;
}


async function tryRefresh(): Promise<boolean> {
  const { getRefreshToken } = await import("./auth");
  const refreshToken = await getRefreshToken();
  if (!refreshToken) return false;
  try {
    const pair = await request<{
      access_token: string;
      refresh_token: string;
      access_expires_at: string;
      refresh_expires_at: string;
      family_id: string;
    }>("/auth/refresh", {
      method: "POST",
      body: { refresh_token: refreshToken },
      auth: false,
      retryOn401: false,
    });
    await setTokenPair({
      accessToken: pair.access_token,
      refreshToken: pair.refresh_token,
      accessExpiresAt: pair.access_expires_at,
      refreshExpiresAt: pair.refresh_expires_at,
      familyId: pair.family_id,
    } satisfies TokenPair);
    return true;
  } catch {
    return false;
  }
}


// ─── Auth endpoints ────────────────────────────────────────────────────────
export interface RegisterBeginReq { operator_id: string; operator_name: string }
export interface AuthenticateBeginReq { operator_id: string }

export const authApi = {
  registerBegin: (req: RegisterBeginReq) =>
    request<unknown>("/auth/webauthn/register-begin", { method: "POST", body: req, auth: false }),

  registerVerify: (operator_id: string, credential: unknown) =>
    request<{ status: string; sign_count: number }>("/auth/webauthn/register-verify", {
      method: "POST", body: { operator_id, credential }, auth: false,
    }),

  authenticateBegin: (req: AuthenticateBeginReq) =>
    request<unknown>("/auth/webauthn/authenticate-begin", { method: "POST", body: req, auth: false }),

  authenticateVerify: (operator_id: string, credential: unknown) =>
    request<{
      access_token: string; refresh_token: string;
      access_expires_at: string; refresh_expires_at: string;
      family_id: string; webauthn_sign_count: number;
    }>("/auth/webauthn/authenticate-verify", {
      method: "POST", body: { operator_id, credential }, auth: false,
    }),

  revoke: (family_id: string, reason?: string) =>
    request<{ action: string; rows_affected: number }>("/auth/revoke", {
      method: "POST", body: { family_id, reason }, auth: true,
    }),
};


// ─── Mobile lifecycle endpoints ────────────────────────────────────────────
export interface ClaudeStatusResp {
  status: "active" | "idle" | "unknown";
  last_heartbeat: unknown;
  last_handoff: unknown;
  mcp_reachable: boolean;
  queried_at: string;
}

export interface ClaudeActionResp {
  action: string;
  operator_id: string;
  process?: { action: string; pid: number | null; error: string | null };
  output?: string;
  mcp_logged?: boolean;
}

export const lifecycleApi = {
  status: () => request<ClaudeStatusResp>("/mobile/claude/status", { auth: true }),
  start: (operator_id: string) =>
    request<ClaudeActionResp>("/mobile/claude/start", {
      method: "POST", body: { operator_id }, auth: true,
    }),
  stop: (operator_id: string, reason?: string) =>
    request<ClaudeActionResp>("/mobile/claude/stop", {
      method: "POST", body: { operator_id, reason }, auth: true,
    }),
  reset: (operator_id: string) =>
    request<ClaudeActionResp>("/mobile/claude/reset", {
      method: "POST", body: { operator_id }, auth: true,
    }),
};


// ─── Push endpoints ────────────────────────────────────────────────────────
export interface SubscribeReq {
  operator_id: string;
  endpoint: string;
  keys: { p256dh: string; auth: string };
  user_agent?: string;
}

export const pushApi = {
  subscribe: (req: SubscribeReq) =>
    request<{ action: string; id: string }>("/push/subscribe", { method: "POST", body: req, auth: true }),

  send: (subscription_id: string, payload: unknown, ttl_seconds = 3600) =>
    request<{ status: string; ttl: number }>("/push/send", {
      method: "POST", body: { subscription_id, payload, ttl_seconds }, auth: true,
    }),

  unsubscribe: (sub_id: string) =>
    request<{ action: string; id: string }>(`/push/subscription/${encodeURIComponent(sub_id)}`, {
      method: "DELETE", auth: true,
    }),
};
