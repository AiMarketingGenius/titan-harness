/**
 * Einstein origin-tab routing test.
 *
 * Verifies that EINSTEIN_VERIFIED_SUMMARY + EINSTEIN_CONTRADICTION
 * dispatches prefer the exact tab whose content script captured the
 * message, NOT whichever tab happens to be active when the async Haiku
 * call returns (which may differ if user switched tabs during the
 * 1-2s fact-check round-trip).
 *
 * Scenario: Monday Don demo Beat 2b captures a Revere Chamber claim on
 * tab 42, Einstein demo-mock runs. Before the fix, the badge would
 * route to chrome.tabs.query({active:true, currentWindow:true}) which
 * returns whichever tab is now focused — could be the demo browser's
 * note window, not the Chamber page. With sender.tab.id propagation,
 * the badge lands on tab 42 reliably.
 *
 * Three cycles verified:
 *   1. NEW_RESPONSE with sender.tab.id=42 → dispatch target tab 42
 *   2. CAPTURE_MESSAGE with sender.tab.id=77 → dispatch target tab 77
 *   3. NEW_RESPONSE with NO sender.tab → dispatch falls back to active-tab
 *
 * Exit 0 = all 3 cycles PASS. Exit 1 = any assertion fires.
 */

import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SW_PATH = path.resolve(__dirname, '..', 'service-worker.js');
const CLAIMS_PATH = path.resolve(__dirname, '..', 'einstein-demo-claims.json');

const source = fs.readFileSync(SW_PATH, 'utf8');
// Load the bundled demo claims so the mock fetch can serve them verbatim
// when runEinsteinDemoCheck requests einstein-demo-claims.json.
const demoClaimsText = fs.readFileSync(CLAIMS_PATH, 'utf8');
const demoClaims = JSON.parse(demoClaimsText);

let registeredListener = null;
const tabSendMessageCalls = []; // { tabId, payload }
const tabQueryCalls = [];

// Stub chrome.* + fetch. Track chrome.tabs.sendMessage calls so we can
// assert correct tab targeting. chrome.tabs.query returns a fixed "active
// tab" (tab 99) so if routing falls back to query, we see tab 99 in the
// call list — easy to distinguish from origin routing (tab 42 / 77).
const ACTIVE_TAB_ID = 99;

const chromeStub = {
  runtime: {
    onMessage: { addListener: (fn) => { registeredListener = fn; } },
    lastError: null,
    sendMessage: () => {},
    getManifest: () => ({ version: '0.1.7' }),
    getURL: (p) => `chrome-extension://test-ext-id/${p}`,
    id: 'test-extension-id',
  },
  storage: {
    local: {
      get: (keys, cb) => {
        // settings: disableDemoMock not set → demo-mock runs
        // token: set so fact-check wouldn't bail, but we won't fire fact-check in this test
        const out = { settings: {}, token: null };
        if (typeof cb === 'function') cb(out);
        return Promise.resolve(out);
      },
      set: (obj, cb) => { (typeof cb === 'function') && cb(); return Promise.resolve(); },
      remove: (keys, cb) => { (typeof cb === 'function') && cb(); return Promise.resolve(); },
    },
    session: {
      get: (keys, cb) => { (typeof cb === 'function') && cb({}); return Promise.resolve({}); },
      set: (obj, cb) => { (typeof cb === 'function') && cb(); return Promise.resolve(); },
    },
  },
  tabs: {
    sendMessage: (tabId, payload) => {
      tabSendMessageCalls.push({ tabId, payload });
      return Promise.resolve();
    },
    query: (criteria) => {
      tabQueryCalls.push(criteria);
      return Promise.resolve([{ id: ACTIVE_TAB_ID }]);
    },
  },
  alarms: {
    create: () => {},
    onAlarm: { addListener: () => {} },
    clear: () => {},
  },
  action: { setBadgeText: () => {}, setBadgeBackgroundColor: () => {} },
  notifications: { create: () => {} },
};

// Serve the bundled einstein-demo-claims.json when the SW requests it.
const fetchStub = async (url) => {
  if (typeof url === 'string' && url.includes('einstein-demo-claims.json')) {
    return {
      ok: true,
      status: 200,
      json: async () => demoClaims,
      text: async () => demoClaimsText,
    };
  }
  // Other fetches (Supabase calls) — bail with non-ok so runEinsteinFactCheck returns early.
  return { ok: false, status: 401, json: async () => ({}), text: async () => '' };
};

const context = {
  chrome: chromeStub,
  console: { log: () => {}, warn: () => {}, error: () => {} },
  fetch: fetchStub,
  setTimeout,
  clearTimeout,
  setInterval: () => 0,
  clearInterval: () => {},
  globalThis: null,
};
context.globalThis = context;

vm.createContext(context);
vm.runInContext(source, context, { filename: 'service-worker.js' });

if (typeof registeredListener !== 'function') {
  console.error('FAIL: service-worker did not register onMessage listener');
  process.exit(1);
}

// Find a demo claim we can trigger. The bundled claims target Chamber /
// Revere / Don content with specific keywords. Build a content string
// that matches at least one claim's require_any groups.
function buildMatchingContent() {
  const claim = (demoClaims.claims || [])[0];
  if (!claim) {
    console.error('FAIL: einstein-demo-claims.json has no claims to test against');
    process.exit(1);
  }
  // Concatenate one keyword from each require_any group → guaranteed match.
  const keywords = (claim.require_any || []).map(group => (group[0] || '')).join(' ');
  return `Test content: ${keywords}. This should match claim ${claim.id} verbatim in the mock interceptor.`;
}

function assertEq(label, actual, expected) {
  if (actual !== expected) {
    console.error(`FAIL ${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    process.exit(1);
  }
}

// Utility — wait for the async runEinsteinDemoCheck pipeline to drain.
// handleNewResponse fires runEinsteinDemoCheck with .catch(); we have
// no direct promise handle, so we poll tabSendMessageCalls up to N ms.
async function waitForDispatch(prevLen, timeoutMs = 2000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (tabSendMessageCalls.length > prevLen) return true;
    await new Promise(r => setTimeout(r, 50));
  }
  return false;
}

console.log('=== Einstein origin-tab routing test ===');
console.log(`Source: ${SW_PATH}`);
console.log(`Claims: ${demoClaims.claims?.length || 0} loaded from ${CLAIMS_PATH}`);
console.log(`Active-tab fallback id: ${ACTIVE_TAB_ID}`);
console.log('');

// ─── Cycle 1: NEW_RESPONSE with sender.tab.id=42 ──────────────────────
const matchingContent = buildMatchingContent();
const beforeLen1 = tabSendMessageCalls.length;
registeredListener(
  {
    type: 'NEW_RESPONSE',
    platform: 'claude',
    content: matchingContent,
    contentLength: matchingContent.length,
    provenance: { platform: 'claude', thread_id: 'claude-thread-1' },
  },
  { tab: { id: 42 } },
  () => {},
);
const got1 = await waitForDispatch(beforeLen1);
if (!got1) {
  console.error('FAIL cycle 1: no chrome.tabs.sendMessage call within 2s (Einstein pipeline may be gated)');
  process.exit(1);
}
const call1 = tabSendMessageCalls.at(-1);
assertEq('cycle 1 target tabId', call1.tabId, 42);
assertEq('cycle 1 payload type', call1.payload.type, 'EINSTEIN_VERIFIED_SUMMARY');
assertEq('cycle 1 payload platform', call1.payload.platform, 'claude');
console.log('  [1/3] NEW_RESPONSE sender.tab.id=42 → dispatch tab 42:  PASS');

// ─── Cycle 2: CAPTURE_MESSAGE with sender.tab.id=77 ───────────────────
const beforeLen2 = tabSendMessageCalls.length;
registeredListener(
  {
    type: 'CAPTURE_MESSAGE',
    payload: {
      platform: 'gemini',
      platform_name: 'Gemini',
      content: matchingContent,
      thread_id: 'gem-thread-2',
      model_used: 'Gemini 2.5 Flash',
    },
  },
  { tab: { id: 77 } },
  () => {},
);
const got2 = await waitForDispatch(beforeLen2);
if (!got2) {
  console.error('FAIL cycle 2: no dispatch within 2s for CAPTURE_MESSAGE path');
  process.exit(1);
}
const call2 = tabSendMessageCalls.at(-1);
assertEq('cycle 2 target tabId', call2.tabId, 77);
assertEq('cycle 2 payload type', call2.payload.type, 'EINSTEIN_VERIFIED_SUMMARY');
assertEq('cycle 2 payload platform', call2.payload.platform, 'gemini');
console.log('  [2/3] CAPTURE_MESSAGE sender.tab.id=77 → dispatch tab 77:  PASS');

// ─── Cycle 3: NEW_RESPONSE with no sender.tab → active-tab fallback ──
const beforeLen3 = tabSendMessageCalls.length;
const queryCallsBefore = tabQueryCalls.length;
registeredListener(
  {
    type: 'NEW_RESPONSE',
    platform: 'perplexity',
    content: matchingContent,
    contentLength: matchingContent.length,
    provenance: { platform: 'perplexity', thread_id: 'pplx-thread-3' },
  },
  { /* no tab field → sender.tab is undefined */ },
  () => {},
);
const got3 = await waitForDispatch(beforeLen3);
if (!got3) {
  console.error('FAIL cycle 3: no dispatch within 2s for missing-sender.tab path');
  process.exit(1);
}
const call3 = tabSendMessageCalls.at(-1);
assertEq('cycle 3 target tabId (active-tab fallback)', call3.tabId, ACTIVE_TAB_ID);
const queriedAfter = tabQueryCalls.length > queryCallsBefore;
if (!queriedAfter) {
  console.error('FAIL cycle 3: expected chrome.tabs.query fallback to fire; it did not');
  process.exit(1);
}
console.log('  [3/3] NEW_RESPONSE no sender.tab → active-tab fallback (99):  PASS');

console.log('');
console.log('=== SUMMARY ===');
console.log(`  tabSendMessage calls: ${tabSendMessageCalls.length}`);
console.log(`  tabQuery calls: ${tabQueryCalls.length} (fallback used only when origin tab absent)`);
console.log('  Origin-tab routing verified across NEW_RESPONSE + CAPTURE_MESSAGE + missing-sender');
console.log('');
console.log('PASS: Einstein origin-tab routing (3/3)');
