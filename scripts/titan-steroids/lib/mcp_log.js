// lib/mcp_log.js — write a decision to the MCP memory server via Supabase REST.
//
// Reads SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from env (inherited from
// /etc/amg/supabase.env + /root/.titan-env on VPS). No third-party deps.

'use strict';

const https = require('https');
const { URL } = require('url');

function postJson(url, headers, body) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const req = https.request({
      method: 'POST',
      hostname: u.hostname,
      port: u.port || 443,
      path: u.pathname + (u.search || ''),
      headers: Object.assign({ 'Content-Type': 'application/json' }, headers || {}),
    }, (res) => {
      let buf = '';
      res.on('data', (c) => { buf += c; });
      res.on('end', () => resolve({ status: res.statusCode, body: buf }));
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

async function logDecision({ text, tags, project_source = 'titan', decision_type = 'execution', rationale = '' }) {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error('SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing');

  const endpoint = url.replace(/\/$/, '') + '/rest/v1/op_decisions';
  const payload = JSON.stringify({
    decision_text: text,
    tags: tags || [],
    project_source,
    decision_type,
    rationale,
    operator_id: 'OPERATOR_AMG',
  });
  const res = await postJson(endpoint, {
    'apikey': key,
    'Authorization': `Bearer ${key}`,
    'Prefer': 'return=minimal',
  }, payload);
  if (res.status >= 400) {
    throw new Error(`MCP log_decision failed ${res.status}: ${res.body.slice(0, 200)}`);
  }
  return { ok: true, status: res.status };
}

async function getRecentDecisionsByTag(tag, limit = 5) {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error('SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing');
  const endpoint = `${url.replace(/\/$/, '')}/rest/v1/op_decisions?select=id,tags,decision_text,created_at&order=created_at.desc&limit=${limit}&tags=cs.{${encodeURIComponent(tag)}}`;
  return new Promise((resolve, reject) => {
    const u = new URL(endpoint);
    const req = https.request({
      method: 'GET',
      hostname: u.hostname,
      port: u.port || 443,
      path: u.pathname + (u.search || ''),
      headers: { 'apikey': key, 'Authorization': `Bearer ${key}`, 'Accept': 'application/json' },
    }, (res) => {
      let buf = '';
      res.on('data', (c) => { buf += c; });
      res.on('end', () => {
        try { resolve(JSON.parse(buf || '[]')); }
        catch (e) { reject(new Error(`JSON parse: ${e.message} — body=${buf.slice(0, 200)}`)); }
      });
    });
    req.on('error', reject);
    req.end();
  });
}

module.exports = { logDecision, getRecentDecisionsByTag };
