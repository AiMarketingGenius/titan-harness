/**
 * Minimal DOM shim for Node test runner.
 *
 * The widget + modal rely on document + window + AudioContext. Node does
 * not provide these. This shim gives us just enough to exercise the code
 * paths without jsdom. Zero-dep — matches extension-client's own stance.
 *
 * Limitations:
 *   - Layout properties (getBoundingClientRect, getComputedStyle) are stubs.
 *   - Events are synchronous and only fire for listeners added with
 *     addEventListener (no bubbling).
 *   - AudioContext nodes are no-ops (chime is fire-and-forget — tests assert
 *     on the construction, not the audio output).
 */

class FakeElement {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.parent = null;
    this.style = {};
    this.attributes = {};
    this.listeners = {};
    this._textContent = "";
    this._innerHTML = "";
    this.id = "";
  }
  appendChild(child) {
    if (child.parent) child.parent.removeChild(child);
    this.children.push(child);
    child.parent = this;
    return child;
  }
  append(...kids) { kids.forEach((k) => this.appendChild(k)); }
  removeChild(child) {
    const idx = this.children.indexOf(child);
    if (idx >= 0) { this.children.splice(idx, 1); child.parent = null; }
    return child;
  }
  remove() { if (this.parent) this.parent.removeChild(this); }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return this.attributes[k] ?? null; }
  addEventListener(ev, fn) {
    (this.listeners[ev] ||= []).push(fn);
  }
  removeEventListener(ev, fn) {
    const arr = this.listeners[ev];
    if (!arr) return;
    const idx = arr.indexOf(fn);
    if (idx >= 0) arr.splice(idx, 1);
  }
  dispatch(ev) {
    (this.listeners[ev] || []).forEach((fn) => fn({ type: ev, target: this }));
  }
  get textContent() { return this._textContent; }
  set textContent(v) { this._textContent = String(v ?? ""); this.children = []; }
  get innerHTML() { return this._innerHTML; }
  set innerHTML(v) { this._innerHTML = String(v ?? ""); }
  click() { this.dispatch("click"); }
}

class FakeDocument {
  constructor() {
    this.body = new FakeElement("body");
    this.documentElement = new FakeElement("html");
  }
  createElement(tag) { return new FakeElement(tag); }
  getElementById(id) { return findById(this.body, id); }
}

function findById(root, id) {
  if (root.id === id) return root;
  for (const c of root.children) {
    const hit = findById(c, id);
    if (hit) return hit;
  }
  return null;
}

class FakeAudioContext {
  constructor() {
    this.state = "running";
    this.currentTime = 0;
    this.destination = { __node: "destination" };
    this._graph = [];
  }
  createOscillator() {
    const n = {
      type: "sine",
      frequency: { value: 0 },
      connect(t) { return t; },
      start() {},
      stop() {},
    };
    this._graph.push({ kind: "osc", node: n });
    return n;
  }
  createGain() {
    const n = {
      gain: {
        setValueAtTime() {},
        linearRampToValueAtTime() {},
        exponentialRampToValueAtTime() {},
      },
      connect(t) { return t; },
    };
    this._graph.push({ kind: "gain", node: n });
    return n;
  }
  async resume() { this.state = "running"; }
  async close() { this.state = "closed"; }
}

let _doc = null;
let _win = null;
let _originals = null;

export function installFakeDom() {
  if (_originals) return;
  _originals = {
    document: globalThis.document,
    window: globalThis.window,
    AudioContext: globalThis.AudioContext,
  };
  _doc = new FakeDocument();
  _win = {
    AudioContext: FakeAudioContext,
    webkitAudioContext: FakeAudioContext,
    // setTimeout already exists on globalThis in Node.
  };
  globalThis.document = _doc;
  globalThis.window = _win;
  globalThis.AudioContext = FakeAudioContext;
}

export function teardownFakeDom() {
  if (!_originals) return;
  globalThis.document = _originals.document;
  globalThis.window = _originals.window;
  globalThis.AudioContext = _originals.AudioContext;
  _originals = null;
  _doc = null;
  _win = null;
}

export function getDom() { return _doc; }
export function findByText(root, substring) {
  const hits = [];
  (function walk(n) {
    if (!n) return;
    if (typeof n.textContent === "string" && n.textContent.includes(substring)) hits.push(n);
    if (n.children) for (const c of n.children) walk(c);
  })(root || _doc?.body);
  return hits;
}
