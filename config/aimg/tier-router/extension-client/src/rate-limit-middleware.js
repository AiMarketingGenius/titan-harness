/**
 * AIMG rate-limit middleware — API-side cap enforcement wrapper.
 *
 * Composes on top of makeTierRouterClient. Adds:
 *
 *   1. Local cap precheck (remaining <= 0 → short-circuit to cap_exceeded,
 *      no edge-fn round-trip, no wasted cost).
 *   2. Token-bucket pacing (defaults 5 requests / 1000ms, burst=3) to prevent
 *      accidental hammering when a UI loop fires verifies in quick succession.
 *   3. Exponential backoff on 429 platform-pause — honors retry_after_utc if
 *      present, otherwise doubles the wait on each retry up to ceiling.
 *   4. In-flight deduplication — two concurrent identical (user_id, memory_id)
 *      verifies collapse to a single edge-fn call; the second awaiter gets
 *      the same response.
 *   5. Shape normalization — edge fn returns usage.daily_cap, widgets expect
 *      usage.cap. The middleware adds `cap` alongside `daily_cap` without
 *      removing the original field (additive, backward-compatible).
 *
 * All state is in-memory per-instance. Caller owns lifecycle. Zero deps.
 *
 * Spec: CT-0414-09 Item 1 (Solon directive 2026-04-15) + DOCTRINE_AIMG_TIER_MATRIX.md.
 */

const DEFAULTS = {
  // Token bucket
  bucketCapacity: 3,
  bucketRefillTokens: 5,
  bucketRefillMs: 1000,
  // Backoff
  minBackoffMs: 250,
  maxBackoffMs: 30_000,
  // Deduplication TTL — identical inflight (user_id, memory_id) collapses
  // within this window. Beyond it, caller gets a fresh call.
  dedupTtlMs: 10_000,
};

/**
 * Returns a drop-in replacement for `callTierRouter` that wraps in the
 * middleware layer.
 *
 * @param {function} innerCall  the raw `callTierRouter` from makeTierRouterClient
 * @param {object} [opts]
 * @param {function=} opts.now  clock-injection for tests
 * @returns {function(payload): Promise<{status, data}>}
 */
export function makeRateLimitMiddleware(innerCall, opts = {}) {
  const cfg = { ...DEFAULTS, ...opts };
  const now = cfg.now || (() => Date.now());

  // Token bucket state
  let tokens = cfg.bucketCapacity;
  let lastRefillMs = now();

  function refillBucket() {
    const t = now();
    const elapsed = t - lastRefillMs;
    if (elapsed >= cfg.bucketRefillMs) {
      const periods = Math.floor(elapsed / cfg.bucketRefillMs);
      tokens = Math.min(cfg.bucketCapacity, tokens + periods * cfg.bucketRefillTokens);
      lastRefillMs += periods * cfg.bucketRefillMs;
    }
  }

  async function waitForToken() {
    for (;;) {
      refillBucket();
      if (tokens > 0) { tokens -= 1; return; }
      const wait = Math.max(1, cfg.bucketRefillMs - (now() - lastRefillMs));
      await new Promise((r) => setTimeout(r, wait));
    }
  }

  // Cap-exceeded / platform-pause cached state
  let cachedCapResponse = null;      // { data, expiresAtMs }
  let cachedPauseResponse = null;    // { data, expiresAtMs }
  let lastUsage = null;              // { tier, used_today, daily_cap, remaining }

  function normalizeUsage(usage) {
    if (!usage || typeof usage !== "object") return usage;
    // Additive shim: widgets expect .cap, edge fn returns .daily_cap.
    if (usage.cap === undefined && typeof usage.daily_cap === "number") {
      return { ...usage, cap: usage.daily_cap };
    }
    return usage;
  }

  function parseRetryAfter(data) {
    const iso = data?.retry_after_utc;
    if (!iso) return null;
    const t = Date.parse(iso);
    return Number.isFinite(t) ? t : null;
  }

  // In-flight dedup map — key: `${user_id}:${memory_id}`, value: { p, expiresAtMs }
  const inflight = new Map();

  function dedupKey(payload) {
    const u = payload?.user_id ?? "anon";
    const m = payload?.memory_id ?? payload?.memory_content?.slice?.(0, 64) ?? "";
    return `${u}:${m}`;
  }

  async function callWithMiddleware(payload) {
    // Short-circuit — platform pause still in effect?
    const tNow = now();
    if (cachedPauseResponse && cachedPauseResponse.expiresAtMs > tNow) {
      return { status: "platform_paused", data: cachedPauseResponse.data };
    }
    // Short-circuit — local cap precheck. Only if we have a fresh usage
    // snapshot AND remaining has actually gone to zero (not unknown).
    if (
      lastUsage &&
      typeof lastUsage.remaining === "number" &&
      lastUsage.remaining <= 0 &&
      cachedCapResponse &&
      cachedCapResponse.expiresAtMs > tNow
    ) {
      return { status: "cap_exceeded", data: cachedCapResponse.data };
    }

    // Dedup — if identical request in flight, piggy-back.
    // Register synchronously BEFORE any await so racing callers all see
    // the same entry and collapse into one edge-fn hit.
    const key = dedupKey(payload);
    const pending = inflight.get(key);
    if (pending && pending.expiresAtMs > tNow) {
      return pending.p;
    }

    const p = (async () => {
      // Pace via token bucket — inside the registered promise so dedup
      // sticks even while we wait for a token.
      await waitForToken();
      const resp = await innerCall(payload);
      if (resp.status === "ok" && resp.data) {
        resp.data.usage = normalizeUsage(resp.data.usage);
        lastUsage = resp.data.usage || null;
      }
      if (resp.status === "cap_exceeded") {
        // Cache until next UTC midnight — cap resets there.
        const midnight = new Date(); midnight.setUTCHours(24, 0, 0, 0);
        cachedCapResponse = { data: resp.data, expiresAtMs: midnight.getTime() };
        // Force remaining=0 so precheck short-circuits next call.
        lastUsage = { ...(lastUsage || {}), remaining: 0 };
      }
      if (resp.status === "platform_paused") {
        const retryAt = parseRetryAfter(resp.data);
        const expiresAtMs = retryAt ?? (now() + cfg.maxBackoffMs);
        cachedPauseResponse = { data: resp.data, expiresAtMs };
      }
      return resp;
    })();

    // Register BEFORE awaiting p so a parallel caller sees the entry.
    inflight.set(key, { p, expiresAtMs: tNow + cfg.dedupTtlMs });
    try {
      return await p;
    } finally {
      const e = inflight.get(key);
      if (e && e.p === p) inflight.delete(key);
    }
  }

  // Attach an escape hatch — caller can reset state on thread change.
  callWithMiddleware.reset = () => {
    cachedCapResponse = null;
    cachedPauseResponse = null;
    lastUsage = null;
    inflight.clear();
  };
  callWithMiddleware.getState = () => ({
    tokens,
    lastUsage,
    capCached: !!cachedCapResponse,
    pauseCached: !!cachedPauseResponse,
    inflight: inflight.size,
  });

  return callWithMiddleware;
}
