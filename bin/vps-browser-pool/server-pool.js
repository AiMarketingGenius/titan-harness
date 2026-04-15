// Production Optimization Pass — Vector 2 (Stagehand browser pool)
// Parallel-context Playwright API, additive to existing single-context server.js on port 3200.
// Ships on port 3201; POOL_SIZE env controls context count (default 3).
//
// Key differences vs server.js:
//   - N contexts, each with own user-data directory `/opt/persistent-browser/user-data-<i>`
//   - Per-context busy-flag mutex; acquire() returns least-busy slot
//   - Endpoints take optional `ctx` in body/query to target a specific slot
//   - /pool/stats for observability; /pool/acquire + /pool/release for explicit slot management
//
// Deploy:
//   1. Copy this file to /opt/persistent-browser/server-pool.js
//   2. Install new systemd unit persistent-browser-pool.service
//   3. Start: systemctl start persistent-browser-pool
//   4. Verify: curl http://127.0.0.1:3201/status + /pool/stats
//
// Rollback: systemctl stop persistent-browser-pool; existing single-context on 3200 unaffected.

const { chromium } = require("playwright");
const express = require("express");
const app = express();
app.use(express.json({ limit: "10mb" }));

const POOL_SIZE = parseInt(process.env.POOL_SIZE || "3", 10);
const LISTEN_PORT = parseInt(process.env.LISTEN_PORT || "3201", 10);
const BASE_USER_DATA = process.env.BASE_USER_DATA || "/opt/persistent-browser/user-data";

const STEALTH_INIT = `
  Object.defineProperty(navigator, 'webdriver', { get: () => false });
  Object.defineProperty(navigator, 'plugins', {
    get: () => [
      { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
      { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
      { name: 'Native Client', filename: 'internal-nacl-plugin' }
    ]
  });
  window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {} };
  if (window.Permissions && window.Permissions.prototype.query) {
    const origQuery = window.Permissions.prototype.query;
    window.Permissions.prototype.query = (parameters) => (
      parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        origQuery(parameters)
    );
  }
`;

// Pool state: array of { id, context, page, busy, acquiredAt, totalRuns, lastError }
const pool = [];

async function launchContext(id) {
  const userDataDir = `${BASE_USER_DATA}-${id}`;
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--disable-blink-features=AutomationControlled",
      "--disable-features=IsolateOrigins,site-per-process"
    ],
    userAgent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    viewport: { width: 1920, height: 1080 },
    locale: "en-US",
    timezoneId: "America/New_York"
  });
  await context.addInitScript(STEALTH_INIT);
  const page = context.pages()[0] || await context.newPage();
  console.log(`[pool] context ${id} launched, user-data=${userDataDir}`);
  return { id, context, page, busy: false, acquiredAt: null, totalRuns: 0, lastError: null };
}

async function launchAll() {
  for (let i = 1; i <= POOL_SIZE; i++) {
    const ctx = await launchContext(i);
    pool.push(ctx);
  }
  console.log(`[pool] all ${POOL_SIZE} contexts up`);
}

// acquire: return the least-busy context (idle first, else least-recently-acquired)
function acquireSlot() {
  const idle = pool.find(s => !s.busy);
  if (idle) {
    idle.busy = true;
    idle.acquiredAt = Date.now();
    return idle;
  }
  // All busy — return least-recently-acquired (oldest lock)
  const oldest = pool.reduce((a, b) => (a.acquiredAt < b.acquiredAt ? a : b));
  return oldest; // caller must handle contention
}

function releaseSlot(id) {
  const slot = pool.find(s => s.id === parseInt(id, 10));
  if (slot) {
    slot.busy = false;
    slot.acquiredAt = null;
    slot.totalRuns += 1;
    return true;
  }
  return false;
}

function findSlot(id) {
  return pool.find(s => s.id === parseInt(id, 10));
}

// ---------------------------------------------------------------------------
// Pool management endpoints
// ---------------------------------------------------------------------------

app.get("/pool/stats", (req, res) => {
  res.json({
    pool_size: POOL_SIZE,
    listen_port: LISTEN_PORT,
    slots: pool.map(s => ({
      id: s.id,
      busy: s.busy,
      acquired_at_ms_ago: s.acquiredAt ? Date.now() - s.acquiredAt : null,
      total_runs: s.totalRuns,
      last_error: s.lastError,
      current_url: s.page ? s.page.url() : null
    })),
    uptime: process.uptime()
  });
});

app.post("/pool/acquire", (req, res) => {
  const slot = acquireSlot();
  if (!slot) return res.status(503).json({ error: "pool_empty" });
  res.json({ ctx: slot.id, already_busy: pool.every(s => s.busy) });
});

app.post("/pool/release/:id", (req, res) => {
  const ok = releaseSlot(req.params.id);
  if (!ok) return res.status(404).json({ error: "slot_not_found" });
  res.json({ released: parseInt(req.params.id, 10) });
});

// ---------------------------------------------------------------------------
// Per-context endpoints (ctx param in body or ?ctx= query)
// ---------------------------------------------------------------------------

function ctxParam(req) {
  return parseInt(req.body?.ctx || req.query?.ctx || "1", 10);
}

app.get("/status", (req, res) => {
  res.json({
    running: true,
    pool_size: POOL_SIZE,
    busy_count: pool.filter(s => s.busy).length,
    idle_count: pool.filter(s => !s.busy).length,
    uptime: process.uptime()
  });
});

app.post("/navigate", async (req, res) => {
  const ctx = ctxParam(req);
  const slot = findSlot(ctx);
  if (!slot) return res.status(404).json({ error: "slot_not_found" });
  try {
    const { url, newTab } = req.body;
    if (!url) return res.status(400).json({ error: "url is required" });
    if (newTab) {
      slot.page = await slot.context.newPage();
    }
    await slot.page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
    res.json({ success: true, ctx: slot.id, url: slot.page.url(), title: await slot.page.title() });
  } catch (err) {
    slot.lastError = err.message;
    res.status(500).json({ error: err.message, ctx: slot.id });
  }
});

app.get("/screenshot", async (req, res) => {
  const ctx = parseInt(req.query.ctx || "1", 10);
  const slot = findSlot(ctx);
  if (!slot) return res.status(404).json({ error: "slot_not_found" });
  try {
    const buffer = await slot.page.screenshot({ type: "png", fullPage: false });
    res.set("Content-Type", "image/png");
    res.send(buffer);
  } catch (err) {
    res.status(500).json({ error: err.message, ctx: slot.id });
  }
});

app.post("/execute", async (req, res) => {
  const ctx = ctxParam(req);
  const slot = findSlot(ctx);
  if (!slot) return res.status(404).json({ error: "slot_not_found" });
  try {
    const { script } = req.body;
    if (!script) return res.status(400).json({ error: "script is required" });
    const result = await slot.page.evaluate(script);
    res.json({ success: true, ctx: slot.id, result });
  } catch (err) {
    slot.lastError = err.message;
    res.status(500).json({ error: err.message, ctx: slot.id });
  }
});

app.get("/pages", async (req, res) => {
  const ctx = parseInt(req.query.ctx || "1", 10);
  const slot = findSlot(ctx);
  if (!slot) return res.status(404).json({ error: "slot_not_found" });
  try {
    const pages = slot.context.pages();
    const info = [];
    for (let i = 0; i < pages.length; i++) {
      try {
        info.push({ index: i, url: pages[i].url(), title: await pages[i].title() });
      } catch (e) {
        info.push({ index: i, url: "error", title: "error" });
      }
    }
    res.json({ ctx: slot.id, pages: info });
  } catch (err) {
    res.status(500).json({ error: err.message, ctx: slot.id });
  }
});

// ---------------------------------------------------------------------------
// Graceful shutdown
// ---------------------------------------------------------------------------

async function shutdown(signal) {
  console.log(`[pool] received ${signal}, closing all contexts...`);
  for (const slot of pool) {
    try { await slot.context.close(); } catch (e) { console.error(`[pool] ctx ${slot.id} close failed:`, e.message); }
  }
  process.exit(0);
}
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));

// ---------------------------------------------------------------------------
// Startup
// ---------------------------------------------------------------------------

app.listen(LISTEN_PORT, "0.0.0.0", () => {
  console.log(`[pool] server listening on 0.0.0.0:${LISTEN_PORT}, pool_size=${POOL_SIZE}`);
});

launchAll().catch(err => {
  console.error("[pool] Failed to launch all contexts:", err);
  process.exit(1);
});
