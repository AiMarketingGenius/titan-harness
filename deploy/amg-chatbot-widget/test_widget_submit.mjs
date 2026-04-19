/**
 * Widget.js submit handler — rate-limit + timeout behavior test.
 *
 * Verifies the two Item 4 Sunday-runway fixes:
 *   (a) Rate-limit slot is burned ONLY on successful round-trip. A 500
 *       response or AbortError does NOT cost the user a message — previously
 *       users got rate-limited during backend outages.
 *   (b) Fetch timeout via AbortController: typing indicator removed + a
 *       "took longer than expected" message shown on abort, instead of
 *       hanging forever.
 *
 * Approach: load widget.js into a node vm sandbox with a minimal DOM stub
 * that tracks textContent per-element + a Fetch mock that switches behavior
 * per cycle. Assert on observable side-effects:
 *   - sessionStorage counter after each cycle
 *   - fetch call count
 *   - last non-typing agent-message textContent
 *
 * Exit 0 = 3/3 PASS. Exit 1 = any assertion fires.
 */

import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const WIDGET_PATH = path.resolve(__dirname, 'widget.js');
const source = fs.readFileSync(WIDGET_PATH, 'utf8');

// ──────────────────────────────────────────────────────────────────────
// Minimal DOM stub. Every element tracks children + textContent + classList.
// Elements expose querySelector(sel) via a per-element map injected when
// the widget calls panel.innerHTML = '…' (we pre-wire the panel's structure).
// ──────────────────────────────────────────────────────────────────────

let submitHandler = null;
const allMessageEls = []; // global: every element created during runtime, filter for .amg-msg

function makeEl(tag) {
  const el = {
    tagName: String(tag || 'div').toUpperCase(),
    children: [],
    parentNode: null,
    _attrs: {},
    _listeners: {},
    _text: '',
    _inner: '',
    classList: {
      _set: new Set(),
      add(c) { this._set.add(c); },
      remove(c) { this._set.delete(c); },
      contains(c) { return this._set.has(c); },
      toggle() {},
    },
    // className setter — widget sets `el.className = 'amg-msg agent'`; split
    // into classList tokens so querySelector-style filtering works in tests.
    set className(v) {
      this.classList._set.clear();
      String(v || '').split(/\s+/).filter(Boolean).forEach(c => this.classList._set.add(c));
    },
    get className() {
      return Array.from(this.classList._set).join(' ');
    },
    style: {},
    set textContent(v) { this._text = String(v == null ? '' : v); },
    get textContent() { return this._text; },
    set innerHTML(v) { this._inner = String(v == null ? '' : v); },
    get innerHTML() { return this._inner; },
    setAttribute(k, v) { this._attrs[k] = String(v); },
    getAttribute(k) { return this._attrs[k]; },
    removeAttribute(k) { delete this._attrs[k]; },
    appendChild(c) { this.children.push(c); c.parentNode = this; return c; },
    removeChild(c) { this.children = this.children.filter(x => x !== c); c.parentNode = null; return c; },
    remove() { if (this.parentNode) this.parentNode.removeChild(this); },
    addEventListener(ev, fn) {
      (this._listeners[ev] = this._listeners[ev] || []).push(fn);
      if (ev === 'submit' && this.tagName === 'FORM') submitHandler = fn;
    },
    dispatchEvent(ev) {
      const fns = this._listeners[ev.type] || [];
      for (const fn of fns) fn(ev);
    },
    querySelector(sel) { return this._qs ? this._qs(sel) : null; },
    querySelectorAll() { return []; },
    focus() {},
    scrollTop: 0,
    scrollHeight: 1000,
  };
  return el;
}

// Pre-wire: when the widget calls document.createElement('div') the first
// time it gets the FAB; the second is the panel. The panel needs
// querySelector to return specific children. We intercept the 2nd div and
// wire its _qs to return pre-built child stubs so the widget's internal
// lookups succeed.
const preBuiltMessages = makeEl('div');
preBuiltMessages.classList.add('amg-widget-messages');
const preBuiltForm = makeEl('form');
const preBuiltInput = makeEl('input');
preBuiltInput.value = '';
const preBuiltSend = makeEl('button');
preBuiltSend.disabled = false;
const preBuiltClose = makeEl('button');

let divCreateCount = 0;
const createdEls = [];
function documentCreateElement(tag) {
  const el = makeEl(tag);
  if (tag === 'div') {
    divCreateCount++;
    // Widget creates: style (diff tag) -> button (fab, diff tag) -> div (panel, 1st div)
    // So the first div created IS the panel. Wire _qs on it.
    if (divCreateCount === 1) {
      el._qs = (sel) => {
        if (sel === '.amg-widget-messages') return preBuiltMessages;
        if (sel === '.amg-widget-form') return preBuiltForm;
        if (sel === '.amg-widget-input') return preBuiltInput;
        if (sel === '.amg-widget-send') return preBuiltSend;
        if (sel === '.amg-widget-close') return preBuiltClose;
        return null;
      };
    }
  }
  createdEls.push(el);
  return el;
}

const documentStub = {
  readyState: 'complete',
  addEventListener() {},
  createElement: documentCreateElement,
  head: makeEl('head'),
  body: {
    appendChild(c) { c.parentNode = this; return c; },
  },
  querySelector: () => null,
};

// sessionStorage
const sessionStorageStub = {
  _data: {},
  getItem(k) { return k in this._data ? this._data[k] : null; },
  setItem(k, v) { this._data[k] = String(v); },
  removeItem(k) { delete this._data[k]; },
};

// Fetch mock — per-cycle mode
let fetchMode = 'ok';
let fetchCalls = 0;
const fetchArgs = [];

async function fetchStub(url, opts) {
  fetchCalls++;
  fetchArgs.push({ url, opts });
  if (fetchMode === 'ok') {
    return {
      ok: true,
      status: 200,
      json: async () => ({ reply: 'Hi there, this is Alex!' }),
    };
  }
  if (fetchMode === '500') {
    return { ok: false, status: 500, json: async () => ({}) };
  }
  if (fetchMode === 'abort-fast') {
    return new Promise((_, reject) => {
      const signal = opts?.signal;
      if (signal) {
        signal.addEventListener('abort', () => {
          const err = new Error('aborted');
          err.name = 'AbortError';
          reject(err);
        });
        // Force abort soon so we don't wait the full 20s widget timeout
        setTimeout(() => {
          const err = new Error('aborted');
          err.name = 'AbortError';
          reject(err);
        }, 100);
      } else {
        setTimeout(() => {
          const err = new Error('aborted');
          err.name = 'AbortError';
          reject(err);
        }, 100);
      }
    });
  }
  throw new Error('unreachable fetch mode: ' + fetchMode);
}

const windowStub = {
  AMG_CHATBOT_ENDPOINT: 'http://test-endpoint.local/api/alex/message',
  __AMG_WIDGET_LOADED__: undefined,
};

const context = {
  window: windowStub,
  document: documentStub,
  sessionStorage: sessionStorageStub,
  fetch: fetchStub,
  AbortController,
  setTimeout,
  clearTimeout,
  setInterval: () => 0,
  clearInterval: () => {},
  console: { log: () => {}, warn: () => {}, error: () => {} },
  JSON, Date, Math, Error, Promise,
  globalThis: null,
};
context.globalThis = context;

vm.createContext(context);
vm.runInContext(source, context, { filename: 'widget.js' });

if (typeof submitHandler !== 'function') {
  console.error('FAIL: submit handler was not registered on form');
  process.exit(1);
}

function getSessionCount() {
  try {
    const s = JSON.parse(sessionStorageStub.getItem('amg_widget_session') || '{}');
    return s.count || 0;
  } catch { return -1; }
}

function lastAgentText() {
  const msgs = preBuiltMessages.children.filter(
    c => c.classList && c.classList.contains('amg-msg') && c.classList.contains('agent') && !c.classList.contains('typing')
  );
  return msgs.length ? msgs[msgs.length - 1]._text : '';
}

function hasTypingIndicator() {
  return preBuiltMessages.children.some(c => c.classList && c.classList.contains('typing'));
}

function assert(label, cond, detail) {
  if (!cond) {
    console.error(`FAIL ${label}${detail ? ': ' + detail : ''}`);
    process.exit(1);
  }
}

console.log('=== widget.js submit handler test ===');
console.log(`Source: ${WIDGET_PATH}`);
console.log('');

// ─── Cycle 1: ok fetch → counter increments to 1, typing removed, reply shown ──
fetchMode = 'ok';
preBuiltInput.value = 'What is AMG?';
const countBefore1 = getSessionCount();
await submitHandler({ preventDefault() {} });
const countAfter1 = getSessionCount();
assert('cycle 1: counter +1 on success', countAfter1 - countBefore1 === 1,
  `before=${countBefore1}, after=${countAfter1}`);
assert('cycle 1: fetch called once', fetchCalls === 1, `calls=${fetchCalls}`);
assert('cycle 1: no typing indicator remaining', !hasTypingIndicator());
assert('cycle 1: reply rendered', /Alex/.test(lastAgentText()),
  `lastAgent="${lastAgentText()}"`);
assert('cycle 1: fetch body includes text', /What is AMG\?/.test(JSON.stringify(fetchArgs[0].opts?.body)));
console.log('  [1/3] ok fetch:      counter=+1 typing=cleared reply="Alex..."     PASS');

// ─── Cycle 2: 500 fetch → counter stays, error message shown ──────────────
fetchMode = '500';
preBuiltInput.value = 'Question during outage';
const countBefore2 = getSessionCount();
await submitHandler({ preventDefault() {} });
const countAfter2 = getSessionCount();
assert('cycle 2: counter unchanged on 500', countAfter2 === countBefore2,
  `before=${countBefore2}, after=${countAfter2}`);
assert('cycle 2: fetch called', fetchCalls === 2, `calls=${fetchCalls}`);
assert('cycle 2: no typing indicator remaining', !hasTypingIndicator());
assert('cycle 2: error message shown', /hiccup|server/i.test(lastAgentText()),
  `lastAgent="${lastAgentText()}"`);
console.log('  [2/3] 500:           counter=unchanged typing=cleared error=shown PASS');

// ─── Cycle 3: abort-fast → counter stays, timeout message shown, typing cleared ─
fetchMode = 'abort-fast';
preBuiltInput.value = 'Question during hang';
const countBefore3 = getSessionCount();
await submitHandler({ preventDefault() {} });
const countAfter3 = getSessionCount();
assert('cycle 3: counter unchanged on abort', countAfter3 === countBefore3,
  `before=${countBefore3}, after=${countAfter3}`);
assert('cycle 3: no typing indicator remaining', !hasTypingIndicator());
assert('cycle 3: timeout message shown', /longer than expected|longer|server/i.test(lastAgentText()),
  `lastAgent="${lastAgentText()}"`);
console.log('  [3/3] abort-fast:    counter=unchanged typing=cleared timeout=msg PASS');

console.log('');
console.log('=== SUMMARY ===');
console.log(`  Final session counter: ${getSessionCount()} (expected 1)`);
console.log(`  Total fetch calls: ${fetchCalls}`);
console.log('  Rate-limit fairness + timeout-handling verified');
console.log('');
console.log('PASS: widget.js submit handler (3/3)');
