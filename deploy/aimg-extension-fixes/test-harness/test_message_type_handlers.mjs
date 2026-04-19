/**
 * Service-worker message-type handler parity test.
 *
 * Found 2026-04-19 during Item 2 scope investigation of the revised
 * Sunday runway sequence: service-worker.js handled only NEW_RESPONSE
 * despite three content scripts (gemini.js, chatgpt.js, copilot.js)
 * dispatching CAPTURE_MESSAGE with a nested payload shape. Three of
 * six platforms were silently dropping captures at the boundary.
 *
 * This test loads service-worker.js into a node vm sandbox with stubbed
 * chrome APIs, captures the registered onMessage listener, fires both
 * NEW_RESPONSE (perplexity/claude/grok shape) and CAPTURE_MESSAGE
 * (gemini/chatgpt/copilot shape) with equivalent content, and asserts
 * BOTH land in pendingExtractions with consistent flat shape.
 *
 * Exit 0 = parity verified. Exit 1 = any assertion fires.
 */

import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SW_PATH = path.resolve(__dirname, '..', 'service-worker.js');

if (!fs.existsSync(SW_PATH)) {
  console.error(`FAIL: service-worker.js not at ${SW_PATH}`);
  process.exit(1);
}

const source = fs.readFileSync(SW_PATH, 'utf8');

// Stub browser/chrome surface. We only need the onMessage listener
// registration + just enough storage/fetch noise so the module parses
// and executes the top-level setup without throwing.
let registeredListener = null;
const pendingWrites = [];

const chromeStub = {
  runtime: {
    onMessage: {
      addListener: (fn) => { registeredListener = fn; },
    },
    lastError: null,
    sendMessage: () => {},
    getManifest: () => ({ version: '0.1.7' }),
    id: 'test-extension-id',
  },
  storage: {
    local: {
      get: (keys, cb) => { (typeof cb === 'function') && cb({}); return Promise.resolve({}); },
      set: (obj, cb) => { pendingWrites.push(obj); (typeof cb === 'function') && cb(); return Promise.resolve(); },
      remove: (keys, cb) => { (typeof cb === 'function') && cb(); return Promise.resolve(); },
    },
    session: {
      get: (keys, cb) => { (typeof cb === 'function') && cb({}); return Promise.resolve({}); },
      set: (obj, cb) => { (typeof cb === 'function') && cb(); return Promise.resolve(); },
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

const context = {
  chrome: chromeStub,
  console: {
    log: () => {},
    warn: () => {},
    error: () => {},
  },
  fetch: () => Promise.resolve({ ok: true, status: 200, json: async () => ({}), text: async () => '' }),
  setTimeout,
  clearTimeout,
  setInterval: () => 0,
  clearInterval: () => {},
  globalThis: null,
  // pendingExtractions lives in module scope; we'll reach into it below
  // after the module runs by re-evaluating a small probe.
};
context.globalThis = context;

vm.createContext(context);
vm.runInContext(source, context, { filename: 'service-worker.js' });

if (typeof registeredListener !== 'function') {
  console.error('FAIL: service-worker did not register a chrome.runtime.onMessage listener');
  process.exit(1);
}

// Probe the internal pendingExtractions after each dispatch. We re-evaluate
// a tiny snippet that returns pendingExtractions.slice() — this runs in the
// same vm context so it sees the module-local binding.
function getPendingExtractions() {
  return vm.runInContext(
    'typeof pendingExtractions === "undefined" ? [] : pendingExtractions.slice()',
    context,
  );
}

function assertEq(label, actual, expected) {
  if (actual !== expected) {
    console.error(`FAIL ${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    process.exit(1);
  }
}
function assertTrue(label, cond) {
  if (!cond) {
    console.error(`FAIL ${label}`);
    process.exit(1);
  }
}

console.log('=== service-worker message-type handler parity test ===');
console.log(`Source: ${SW_PATH} (${source.length} bytes)`);
console.log('');

// ─── Cycle 1: NEW_RESPONSE shape (perplexity/claude/grok) ──────────────
const newResponsePayload = {
  type: 'NEW_RESPONSE',
  platform: 'perplexity',
  content: 'Perplexity answer text. This is the flat NEW_RESPONSE shape.',
  contentLength: 62,
  provenance: {
    platform: 'perplexity',
    thread_id: 'pplx-thread-abc',
    thread_url: 'https://perplexity.ai/search/abc',
    exchange_number: 1,
    timestamp: '2026-04-19T03:15:00Z',
  },
};
const beforeLen1 = getPendingExtractions().length;
registeredListener(newResponsePayload, { tab: { id: 42 } }, () => {});
const afterLen1 = getPendingExtractions().length;
assertEq('NEW_RESPONSE appended row', afterLen1 - beforeLen1, 1);
const row1 = getPendingExtractions().at(-1);
assertEq('NEW_RESPONSE.platform', row1.platform, 'perplexity');
assertEq('NEW_RESPONSE.content', row1.content, newResponsePayload.content);
assertEq('NEW_RESPONSE.provenance.thread_id', row1.provenance.thread_id, 'pplx-thread-abc');
console.log('  [1/3] NEW_RESPONSE → pendingExtractions:  PASS');

// ─── Cycle 2: CAPTURE_MESSAGE shape (gemini) ───────────────────────────
const captureMessageGemini = {
  type: 'CAPTURE_MESSAGE',
  payload: {
    platform: 'gemini',
    platform_name: 'Gemini',
    thread_id: 'gem-thread-xyz',
    thread_url: 'https://gemini.google.com/app/xyz',
    exchange_number: 2,
    role: 'assistant',
    content: 'Gemini answer text. This is the nested CAPTURE_MESSAGE shape.',
    model_used: 'Gemini 2.5 Flash',
    source_timestamp: '2026-04-19T03:15:05Z',
    message_id: 'gem-msg-001',
  },
};
const beforeLen2 = getPendingExtractions().length;
registeredListener(captureMessageGemini, { tab: { id: 43 } }, () => {});
const afterLen2 = getPendingExtractions().length;
assertEq('CAPTURE_MESSAGE(gemini) appended row', afterLen2 - beforeLen2, 1);
const row2 = getPendingExtractions().at(-1);
assertEq('CAPTURE_MESSAGE.platform', row2.platform, 'gemini');
assertEq('CAPTURE_MESSAGE.content', row2.content, captureMessageGemini.payload.content);
assertEq('CAPTURE_MESSAGE.provenance.thread_id', row2.provenance.thread_id, 'gem-thread-xyz');
assertEq('CAPTURE_MESSAGE.provenance.model_used', row2.provenance.model_used, 'Gemini 2.5 Flash');
assertEq('CAPTURE_MESSAGE.provenance.message_id', row2.provenance.message_id, 'gem-msg-001');
assertEq('CAPTURE_MESSAGE.provenance.role', row2.provenance.role, 'assistant');
assertEq('CAPTURE_MESSAGE.provenance.platform_name', row2.provenance.platform_name, 'Gemini');
console.log('  [2/3] CAPTURE_MESSAGE(gemini) → pendingExtractions:  PASS');

// ─── Cycle 3: CAPTURE_MESSAGE shape (chatgpt) ──────────────────────────
const captureMessageChatgpt = {
  type: 'CAPTURE_MESSAGE',
  payload: {
    platform: 'chatgpt',
    platform_name: 'ChatGPT',
    thread_id: 'cgpt-thread-123',
    thread_url: 'https://chatgpt.com/c/cgpt-thread-123',
    exchange_number: 3,
    role: 'assistant',
    content: 'ChatGPT answer text.',
    model_used: 'GPT-4o',
    source_timestamp: '2026-04-19T03:15:10Z',
    message_id: 'cgpt-msg-789',
  },
};
const beforeLen3 = getPendingExtractions().length;
registeredListener(captureMessageChatgpt, { tab: { id: 44 } }, () => {});
const afterLen3 = getPendingExtractions().length;
assertEq('CAPTURE_MESSAGE(chatgpt) appended row', afterLen3 - beforeLen3, 1);
const row3 = getPendingExtractions().at(-1);
assertEq('CAPTURE_MESSAGE(chatgpt).platform', row3.platform, 'chatgpt');
assertEq('CAPTURE_MESSAGE(chatgpt).content', row3.content, captureMessageChatgpt.payload.content);
assertEq('CAPTURE_MESSAGE(chatgpt).provenance.model_used', row3.provenance.model_used, 'GPT-4o');
console.log('  [3/3] CAPTURE_MESSAGE(chatgpt) → pendingExtractions:  PASS');

console.log('');
console.log('=== SUMMARY ===');
console.log(`  Total pending extractions after 3 dispatches: ${getPendingExtractions().length}`);
console.log('  Shape parity verified across NEW_RESPONSE + CAPTURE_MESSAGE');
console.log('  Gemini/ChatGPT/Copilot capture-loss defect structurally fixed');
console.log('');
console.log('PASS: service-worker message-type handler parity (3/3)');
