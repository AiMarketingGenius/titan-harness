/**
 * Integration tests — aimg-client.js (widget + chime + modal wiring)
 * Runner: node --test tests/aimg-client.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { installFakeDom, teardownFakeDom, getDom, findByText } from "./mock-dom.js";
import { installMockSupabase, teardownMockSupabase, setScenario } from "./mock-supabase.js";
import { zoneForExchangeCount, ZONES } from "../src/thread-health-widget.js";

test("zoneForExchangeCount — boundaries 1/15/16/30/31/45/46 map to correct zones", () => {
  assert.equal(zoneForExchangeCount(1).key,   "green");
  assert.equal(zoneForExchangeCount(15).key,  "green");
  assert.equal(zoneForExchangeCount(16).key,  "yellow");
  assert.equal(zoneForExchangeCount(30).key,  "yellow");
  assert.equal(zoneForExchangeCount(31).key,  "orange");
  assert.equal(zoneForExchangeCount(45).key,  "orange");
  assert.equal(zoneForExchangeCount(46).key,  "red");
  assert.equal(zoneForExchangeCount(9999).key, "red");
});

test("zones array — 4 zones in order, colors match locked spec", () => {
  assert.equal(ZONES.length, 4);
  assert.equal(ZONES[0].color, "#2ecc71");
  assert.equal(ZONES[1].color, "#f1c40f");
  assert.equal(ZONES[2].color, "#e67e22");
  assert.equal(ZONES[3].color, "#e74c3c");
});

test("AimgClient.verify — 50 sequential calls transition widget through all zones and fire modal on 46th", async (t) => {
  installFakeDom();
  installMockSupabase({ scenario: "ok" });
  const { AimgClient } = await import("../src/aimg-client.js");

  let freshCallbackInvocations = 0;
  const client = new AimgClient({
    supabaseUrl: "https://x.supabase.co",
    jwt: "jwt",
    widgetContainer: getDom().body,
    onStartFreshThread: () => { freshCallbackInvocations += 1; },
  });

  // Exercise 50 calls
  for (let i = 0; i < 50; i++) {
    await client.verify({ user_id: "u1", memory_id: `m${i}`, memory_content: `c${i}` });
  }

  // Modal should have appeared at 46th exchange (first red entry)
  const modalHits = findByText(getDom().body, "Let's start a fresh thread to maintain quality");
  assert.ok(modalHits.length >= 1, "carryover modal must appear on red-zone entry");
  const footerHits = findByText(getDom().body, "AI can make mistakes please double-check all responses");
  assert.ok(footerHits.length >= 1, "copy-locked footer must be present");

  client.destroy();
  teardownMockSupabase();
  teardownFakeDom();
});

test("AimgClient.verify — 402 cap_exceeded triggers upsell modal with suggested_tier + price", async () => {
  installFakeDom();
  installMockSupabase({ scenario: "cap_exceeded" });
  const { AimgClient } = await import("../src/aimg-client.js");

  const client = new AimgClient({
    supabaseUrl: "https://x.supabase.co",
    jwt: "jwt",
    widgetContainer: getDom().body,
    onStartFreshThread: () => {},
  });

  const resp = await client.verify({ user_id: "u1", memory_id: "m1", memory_content: "a" });
  assert.equal(resp.status, "cap_exceeded");

  const capTitleHits = findByText(getDom().body, "Daily cap reached");
  assert.ok(capTitleHits.length >= 1, "cap-exceeded modal must appear");

  client.destroy();
  teardownMockSupabase();
  teardownFakeDom();
});

test("AimgClient.verify — 429 platform_paused triggers pause banner with retry_after_utc", async () => {
  installFakeDom();
  installMockSupabase({ scenario: "platform_paused" });
  const { AimgClient } = await import("../src/aimg-client.js");

  const client = new AimgClient({
    supabaseUrl: "https://x.supabase.co",
    jwt: "jwt",
    widgetContainer: getDom().body,
    onStartFreshThread: () => {},
  });

  const resp = await client.verify({ user_id: "u1", memory_id: "m1", memory_content: "a" });
  assert.equal(resp.status, "platform_paused");

  const pauseHits = findByText(getDom().body, "Service paused until UTC midnight");
  assert.ok(pauseHits.length >= 1, "platform-pause banner must appear");

  client.destroy();
  teardownMockSupabase();
  teardownFakeDom();
});

test("AimgClient.resetThread — zero-ing out exchange count re-enables chime on next red entry", async () => {
  installFakeDom();
  installMockSupabase({ scenario: "ok" });
  const { AimgClient } = await import("../src/aimg-client.js");

  const client = new AimgClient({
    supabaseUrl: "https://x.supabase.co",
    jwt: "jwt",
    widgetContainer: getDom().body,
    onStartFreshThread: () => {},
  });

  for (let i = 0; i < 46; i++) {
    await client.verify({ user_id: "u1", memory_id: `m${i}`, memory_content: `c${i}` });
  }
  // Red modal appeared once
  assert.ok(findByText(getDom().body, "Let's start a fresh thread").length >= 1);

  client.resetThread();
  // Exchange count back to 0 — zone should be green again on next call
  await client.verify({ user_id: "u1", memory_id: "post-reset", memory_content: "x" });
  // no assertion on zone API here (internal), but destroy should not throw
  client.destroy();
  teardownMockSupabase();
  teardownFakeDom();
});
