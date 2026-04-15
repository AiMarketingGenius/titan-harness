/**
 * Unit tests — tier-router-client.js
 * Runner: node --test tests/tier-router-client.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { makeTierRouterClient, AimgTierRouterError } from "../src/tier-router-client.js";
import { installMockSupabase, teardownMockSupabase, setScenario, getMockCallLog } from "./mock-supabase.js";

test("200 ok — returns {status:'ok', data} with usage", async () => {
  installMockSupabase({ scenario: "ok" });
  const call = makeTierRouterClient({ supabaseUrl: "https://x.supabase.co", jwt: "jwt" });
  const resp = await call({ user_id: "u1", memory_content: "hi", operation: "verify" });
  assert.equal(resp.status, "ok");
  assert.equal(resp.data.result.verified, true);
  assert.equal(resp.data.usage.daily_cap, 20);
  assert.ok(resp.data.usage.remaining < 20);
  teardownMockSupabase();
});

test("402 cap_exceeded — returns {status:'cap_exceeded', data:{upsell}}", async () => {
  installMockSupabase({ scenario: "cap_exceeded" });
  const call = makeTierRouterClient({ supabaseUrl: "https://x.supabase.co", jwt: "jwt" });
  const resp = await call({ user_id: "u1", memory_content: "hi" });
  assert.equal(resp.status, "cap_exceeded");
  assert.equal(resp.data.upsell.suggested_tier, "basic");
  teardownMockSupabase();
});

test("429 platform_paused — returns {status:'platform_paused', data:{retry_after_utc}}", async () => {
  installMockSupabase({ scenario: "platform_paused" });
  const call = makeTierRouterClient({ supabaseUrl: "https://x.supabase.co", jwt: "jwt" });
  const resp = await call({ user_id: "u1", memory_content: "hi" });
  assert.equal(resp.status, "platform_paused");
  assert.ok(resp.data.retry_after_utc);
  teardownMockSupabase();
});

test("non-JSON 502 — throws AimgTierRouterError", async () => {
  installMockSupabase({ scenario: "non_json" });
  const call = makeTierRouterClient({ supabaseUrl: "https://x.supabase.co", jwt: "jwt" });
  await assert.rejects(() => call({ user_id: "u1", memory_content: "hi" }), AimgTierRouterError);
  teardownMockSupabase();
});

test("provider_error JSON 502 — throws AimgTierRouterError with payload", async () => {
  installMockSupabase({ scenario: "provider_error" });
  const call = makeTierRouterClient({ supabaseUrl: "https://x.supabase.co", jwt: "jwt" });
  await assert.rejects(
    () => call({ user_id: "u1", memory_content: "hi" }),
    (e) => e instanceof AimgTierRouterError && e.status === 502,
  );
  teardownMockSupabase();
});

test("constructor throws when supabaseUrl or jwt missing", () => {
  assert.throws(() => makeTierRouterClient({ supabaseUrl: "", jwt: "" }), AimgTierRouterError);
  assert.throws(() => makeTierRouterClient({ supabaseUrl: "x", jwt: "" }), AimgTierRouterError);
});

test("endpoint uses /functions/v1/aimg-qe-call and strips trailing slash", async () => {
  installMockSupabase({ scenario: "ok" });
  const call = makeTierRouterClient({ supabaseUrl: "https://x.supabase.co/", jwt: "jwt" });
  await call({ user_id: "u1", memory_content: "hi" });
  const log = getMockCallLog();
  assert.equal(log.length, 1);
  assert.equal(log[0].url, "https://x.supabase.co/functions/v1/aimg-qe-call");
  assert.equal(log[0].method, "POST");
  teardownMockSupabase();
});
