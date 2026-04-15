/**
 * Mock Supabase edge-fn server for AIMG tier-router tests.
 *
 * No real network. Replaces `globalThis.fetch` with an inline handler that
 * imitates `/functions/v1/aimg-qe-call` — the 200/402/429 shapes matching
 * `config/aimg/tier-router/supabase/functions/aimg-qe-call/index.ts`.
 *
 * Usage:
 *   import { installMockSupabase, teardownMockSupabase, resetMockState } from "./mock-supabase.js";
 *   installMockSupabase({ scenario: "ok" });   // or "cap_exceeded", "platform_paused"
 *   ...run tests...
 *   teardownMockSupabase();
 */

let originalFetch = null;
let callLog = [];
let scenarioState = null;

function makeOkResponse({ tier = "free", used_today = 1, daily_cap = 20 } = {}) {
  return new Response(JSON.stringify({
    result: { verified: true, confidence: 0.9, result: "mock-ok" },
    usage: {
      tier,
      used_today,
      daily_cap,
      remaining: Math.max(0, daily_cap - used_today),
      actual_cost_usd: 0.00012,
    },
  }), { status: 200, headers: { "Content-Type": "application/json" } });
}

function makeCapExceededResponse({ tier = "free", daily_cap = 20, suggested = "basic", suggested_cap = 50, price = 4.99 } = {}) {
  return new Response(JSON.stringify({
    error: "tier_cap_exceeded",
    upsell: {
      current_tier: tier,
      current_cap: daily_cap,
      suggested_tier: suggested,
      suggested_cap,
      next_tier_price: price,
    },
  }), { status: 402, headers: { "Content-Type": "application/json" } });
}

function makePlatformPausedResponse({ retry_after_utc = "2099-01-01T00:00:00.000Z", platform_cost_usd = 5.01 } = {}) {
  return new Response(JSON.stringify({
    error: "platform_cost_ceiling",
    retry_after_utc,
    platform_cost_usd,
  }), { status: 429, headers: { "Content-Type": "application/json" } });
}

const SCENARIOS = {
  ok: (state) => {
    state.callCount = (state.callCount || 0) + 1;
    return makeOkResponse({ used_today: state.callCount, daily_cap: state.daily_cap ?? 20 });
  },
  cap_exceeded: () => makeCapExceededResponse(),
  platform_paused: () => makePlatformPausedResponse(),
  ok_then_cap: (state) => {
    state.callCount = (state.callCount || 0) + 1;
    if (state.callCount >= (state.capAt ?? 3)) return makeCapExceededResponse();
    return makeOkResponse({ used_today: state.callCount, daily_cap: state.capAt ?? 3 });
  },
  boundary_cap_one_left: (state) => {
    // First call: remaining=1. Second+: cap_exceeded.
    state.callCount = (state.callCount || 0) + 1;
    if (state.callCount === 1) return makeOkResponse({ used_today: 19, daily_cap: 20 });
    return makeCapExceededResponse();
  },
  non_json: () => new Response("<html>gateway</html>", { status: 502 }),
  provider_error: () => new Response(JSON.stringify({ error: "provider_error", detail: "mock" }), { status: 502, headers: { "Content-Type": "application/json" } }),
};

export function installMockSupabase({ scenario = "ok", ...init } = {}) {
  if (originalFetch) teardownMockSupabase();
  originalFetch = globalThis.fetch;
  callLog = [];
  scenarioState = { scenario, ...init };
  globalThis.fetch = async (url, opts = {}) => {
    callLog.push({ url: String(url), method: opts.method || "GET", body: opts.body ?? null });
    const handler = SCENARIOS[scenarioState.scenario];
    if (!handler) throw new Error(`mock-supabase: unknown scenario '${scenarioState.scenario}'`);
    return handler(scenarioState);
  };
}

export function teardownMockSupabase() {
  if (originalFetch) {
    globalThis.fetch = originalFetch;
    originalFetch = null;
  }
  callLog = [];
  scenarioState = null;
}

export function getMockCallLog() { return callLog.slice(); }
export function setScenario(scenario, patch = {}) {
  if (!scenarioState) throw new Error("mock-supabase not installed");
  scenarioState = { ...scenarioState, scenario, ...patch };
}
export function resetMockState() {
  if (scenarioState) scenarioState = { scenario: scenarioState.scenario };
  callLog = [];
}
