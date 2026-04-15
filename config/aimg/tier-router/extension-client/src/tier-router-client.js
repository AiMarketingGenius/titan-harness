/**
 * AIMG tier-router client.
 *
 * Thin fetch wrapper around the `aimg-qe-call` Supabase edge function.
 * Handles 200 (verify succeeded), 402 (per-user daily cap exceeded + upsell
 * payload), and 429 (platform cost ceiling breached, all tiers paused).
 *
 * Contract matches config/aimg/tier-router/README.md and
 * plans/DOCTRINE_AIMG_TIER_MATRIX.md (FINAL LOCK 2026-04-14).
 *
 * Caller is responsible for rendering:
 *   - countdown UI (usage.remaining / usage.cap)
 *   - upsell prompt (402 response → json.upsell)
 *   - platform pause banner (429 response → json.retry_after_utc)
 */

export class AimgTierRouterError extends Error {
  constructor(message, { status, payload } = {}) {
    super(message);
    this.name = "AimgTierRouterError";
    this.status = status;
    this.payload = payload;
  }
}

/**
 * @param {object} opts
 * @param {string} opts.supabaseUrl  e.g. https://<ref>.supabase.co
 * @param {string} opts.jwt          Supabase anon+user JWT
 * @param {AbortSignal=} opts.signal Optional abort signal for the fetch.
 * @returns {function(payload): Promise<{status:'ok'|'cap_exceeded'|'platform_paused', data:object}>}
 */
export function makeTierRouterClient({ supabaseUrl, jwt, signal }) {
  if (!supabaseUrl || !jwt) {
    throw new AimgTierRouterError("supabaseUrl and jwt are required");
  }
  const endpoint = `${supabaseUrl.replace(/\/$/, "")}/functions/v1/aimg-qe-call`;

  return async function callTierRouter(payload) {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${jwt}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      signal,
    });

    let json = null;
    try {
      json = await res.json();
    } catch (_) {
      throw new AimgTierRouterError(
        `aimg-qe-call returned non-JSON (status=${res.status})`,
        { status: res.status },
      );
    }

    if (res.status === 200) {
      return { status: "ok", data: json };
    }
    if (res.status === 402) {
      return { status: "cap_exceeded", data: json };
    }
    if (res.status === 429) {
      return { status: "platform_paused", data: json };
    }
    throw new AimgTierRouterError(
      json?.error || `aimg-qe-call failed (status=${res.status})`,
      { status: res.status, payload: json },
    );
  };
}
