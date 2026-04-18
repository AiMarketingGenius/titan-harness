// lib/executor.js — class executor.
//
// Given a class definition and inputs, runs the class's probe and returns the
// result JSON. Acceptance criteria are evaluated by the caller (scheduler.js).

'use strict';

const https = require('https');
const { URL } = require('url');

async function httpsGetJson(url, headers, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const req = https.request({
      method: 'GET',
      hostname: u.hostname,
      port: u.port || 443,
      path: u.pathname + (u.search || ''),
      headers: Object.assign({ 'Accept': 'application/json' }, headers || {}),
      timeout: timeoutMs,
    }, (res) => {
      let buf = '';
      res.on('data', (c) => { buf += c; });
      res.on('end', () => {
        try { resolve({ status: res.statusCode, json: JSON.parse(buf || '{}') }); }
        catch (_) { resolve({ status: res.statusCode, raw: buf.slice(0, 500) }); }
      });
    });
    req.on('timeout', () => { req.destroy(new Error(`timeout ${timeoutMs}ms`)); });
    req.on('error', reject);
    req.end();
  });
}

// Built-in probes. New classes register their probe handler here.
const PROBES = {
  // MCP health ping — GET memory.aimarketinggenius.io/health
  async mcp_ping() {
    const res = await httpsGetJson('https://memory.aimarketinggenius.io/health', {}, 5000);
    if (res.status !== 200) {
      return { ok: false, status: res.status, raw: res.raw || '', server: null };
    }
    return { ok: true, status: 'ok', ...res.json };
  },

  // Placeholder for future class — weekly client metric pull, etc.
  async noop() {
    return { ok: true, status: 'ok', noop: true };
  },
};

async function runClass(cls) {
  const probeName = (cls.inputs || {}).probe || 'noop';
  const probe = PROBES[probeName];
  if (!probe) {
    return { ok: false, error: `unknown probe: ${probeName}`, probe_name: probeName };
  }
  const started = Date.now();
  try {
    const result = await probe();
    return { ok: true, probe_name: probeName, duration_ms: Date.now() - started, result };
  } catch (err) {
    return { ok: false, probe_name: probeName, duration_ms: Date.now() - started, error: err.message };
  }
}

module.exports = { runClass, PROBES };
