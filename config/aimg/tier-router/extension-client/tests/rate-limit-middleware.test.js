/**
 * Unit tests — rate-limit-middleware.js
 * Runner: node --test tests/rate-limit-middleware.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { makeTierRouterClient } from "../src/tier-router-client.js";
import { makeRateLimitMiddleware } from "../src/rate-limit-middleware.js";
import { installMockSupabase, teardownMockSupabase, setScenario, getMockCallLog, resetMockState } from "./mock-supabase.js";

function makeStack(scenario, { opts } = {}) {
  installMockSupabase({ scenario });
  const inner = makeTierRouterClient({ supabaseUrl: "https://x.supabase.co", jwt: "jwt" });
  return makeRateLimitMiddleware(inner, opts);
}

test("local cap precheck — after cap_exceeded, next call short-circuits (no edge-fn hit)", async () => {
  const wrap = makeStack("ok_then_cap", { opts: {} });
  // first call 200 (used_today=1, remaining=1)
  let r = await wrap({ user_id: "u1", memory_id: "m1", memory_content: "a" });
  assert.equal(r.status, "ok");
  // second call 200 (used_today=2, remaining=0)
  r = await wrap({ user_id: "u1", memory_id: "m2", memory_content: "b" });
  assert.equal(r.status, "ok");
  // third call 402 (capAt=3 → cap_exceeded)
  r = await wrap({ user_id: "u1", memory_id: "m3", memory_content: "c" });
  assert.equal(r.status, "cap_exceeded");
  const edgeFnHits = getMockCallLog().length;
  // fourth call — should short-circuit WITHOUT hitting edge fn
  r = await wrap({ user_id: "u1", memory_id: "m4", memory_content: "d" });
  assert.equal(r.status, "cap_exceeded");
  assert.equal(getMockCallLog().length, edgeFnHits, "expected no additional edge-fn hit");
  teardownMockSupabase();
});

test("platform pause — short-circuits without network round-trip on subsequent calls", async () => {
  const wrap = makeStack("platform_paused");
  const r1 = await wrap({ user_id: "u1", memory_id: "m1", memory_content: "a" });
  assert.equal(r1.status, "platform_paused");
  const hitsAfterFirst = getMockCallLog().length;
  const r2 = await wrap({ user_id: "u1", memory_id: "m2", memory_content: "b" });
  assert.equal(r2.status, "platform_paused");
  assert.equal(getMockCallLog().length, hitsAfterFirst, "paused state must suppress further calls");
  teardownMockSupabase();
});

test("shape normalization — adds usage.cap alongside usage.daily_cap", async () => {
  const wrap = makeStack("ok");
  const r = await wrap({ user_id: "u1", memory_id: "m1", memory_content: "a" });
  assert.equal(r.status, "ok");
  assert.equal(r.data.usage.daily_cap, 20);
  assert.equal(r.data.usage.cap, 20, "middleware must expose usage.cap for widget countdown");
  teardownMockSupabase();
});

test("in-flight dedup — two concurrent identical (user_id, memory_id) collapse to one edge-fn hit", async () => {
  const wrap = makeStack("ok");
  const p1 = wrap({ user_id: "u1", memory_id: "m1", memory_content: "a" });
  const p2 = wrap({ user_id: "u1", memory_id: "m1", memory_content: "a" });
  const [r1, r2] = await Promise.all([p1, p2]);
  assert.equal(r1.status, "ok");
  assert.equal(r2.status, "ok");
  assert.equal(getMockCallLog().length, 1, "expected one edge-fn hit from dedup");
  teardownMockSupabase();
});

test("different memory_id — NOT deduped", async () => {
  const wrap = makeStack("ok");
  const p1 = wrap({ user_id: "u1", memory_id: "m1", memory_content: "a" });
  const p2 = wrap({ user_id: "u1", memory_id: "m2", memory_content: "b" });
  await Promise.all([p1, p2]);
  assert.equal(getMockCallLog().length, 2, "different memory_id must result in two edge-fn hits");
  teardownMockSupabase();
});

test("token bucket — 6 concurrent calls with bucket=3 refill=5/1s get paced, not all fired instantly", async () => {
  // Use a fast bucket so test stays quick.
  const wrap = makeStack("ok", { opts: {
    bucketCapacity: 3,
    bucketRefillTokens: 3,
    bucketRefillMs: 100,
    dedupTtlMs: 1,  // effectively disable dedup for this test
  }});
  const t0 = Date.now();
  await Promise.all(Array.from({ length: 6 }, (_, i) =>
    wrap({ user_id: "u1", memory_id: `m${i}`, memory_content: `c${i}` })
  ));
  const elapsed = Date.now() - t0;
  assert.ok(elapsed >= 90, `expected pacing delay, got ${elapsed}ms`);
  assert.equal(getMockCallLog().length, 6);
  teardownMockSupabase();
});

test("reset() — clears cached cap + pause state, subsequent call hits edge fn", async () => {
  const wrap = makeStack("cap_exceeded");
  await wrap({ user_id: "u1", memory_id: "m1", memory_content: "a" });
  const hitsBefore = getMockCallLog().length;
  // Second call with same user would short-circuit
  await wrap({ user_id: "u1", memory_id: "m2", memory_content: "b" });
  assert.equal(getMockCallLog().length, hitsBefore, "must short-circuit before reset");

  wrap.reset();
  // Switch scenario to ok to verify edge fn is actually contacted again
  setScenario("ok"); resetMockState();
  const r = await wrap({ user_id: "u1", memory_id: "m3", memory_content: "c" });
  assert.equal(r.status, "ok");
  assert.ok(getMockCallLog().length >= 1, "reset() must allow the next call to reach edge fn");
  teardownMockSupabase();
});

test("getState() — exposes internal counters for observability", async () => {
  const wrap = makeStack("ok");
  await wrap({ user_id: "u1", memory_id: "m1", memory_content: "a" });
  const state = wrap.getState();
  assert.ok(typeof state.tokens === "number");
  assert.ok(state.lastUsage, "lastUsage must be populated after first 200");
  assert.equal(state.lastUsage.cap, state.lastUsage.daily_cap);
  teardownMockSupabase();
});
