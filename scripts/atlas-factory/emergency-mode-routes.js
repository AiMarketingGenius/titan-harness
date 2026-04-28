// =============================================================================
// DIR-2026-04-28-002a Step 3.3 — Emergency Mode MCP routes
// =============================================================================
// 3 routes per v3 §3.3 (P9 polish: HMAC-SHA256 over body, secret in
// Supabase vault `emergency_signal_hmac_key`):
//
//   POST /api/emergency/signal       — emergency_signal(...) → INSERT row
//   POST /api/emergency/killall      — solon_emergency_killall(reason)
//                                      Solon-only, fires KILL to titan + achilles
//   POST /api/emergency/acknowledge  — acknowledge_emergency_signal(signal_id, agent)
//
// Auth headers (all 3 routes):
//   X-Caller-Identity: 'eom' | 'solon' (killall: 'solon' only)
//   X-Signature:       hex HMAC-SHA256 of stringified request body
//
// HMAC secret is loaded once at first call from vault.decrypted_secrets via
// the existing supabase service-role client; cached in module scope.
// =============================================================================

import { createHmac, timingSafeEqual } from 'node:crypto';

let _hmacSecretCache = null;
let _hmacSecretFetchPromise = null;

async function getHmacSecret() {
  if (_hmacSecretCache) return _hmacSecretCache;
  if (_hmacSecretFetchPromise) return _hmacSecretFetchPromise;
  _hmacSecretFetchPromise = (async () => {
    const { supabase } = await import('./db/supabase.js');
    // SECURITY DEFINER RPC public.get_emergency_hmac_secret() is the
    // standard Supabase pattern for service-role-only vault access.
    // Direct .schema('vault').from('decrypted_secrets') is blocked by RLS.
    const { data, error } = await supabase.rpc('get_emergency_hmac_secret');
    if (error || !data) {
      throw new Error('emergency_signal_hmac_key RPC failed: ' + (error?.message || 'empty'));
    }
    _hmacSecretCache = data;
    return _hmacSecretCache;
  })();
  try {
    return await _hmacSecretFetchPromise;
  } finally {
    _hmacSecretFetchPromise = null;
  }
}

function canonicalizeBody(body) {
  // Stable serialization: sorted keys so client + server produce same string.
  const sorted = {};
  for (const k of Object.keys(body || {}).sort()) sorted[k] = body[k];
  return JSON.stringify(sorted);
}

async function verifyHmac(request) {
  const providedSig = request.headers['x-signature'];
  const callerIdentity = request.headers['x-caller-identity'];
  if (!providedSig || typeof providedSig !== 'string') {
    return { ok: false, status: 401, error: 'X-Signature header required' };
  }
  if (!callerIdentity || !['eom', 'solon'].includes(String(callerIdentity).toLowerCase())) {
    return { ok: false, status: 401, error: 'X-Caller-Identity must be eom or solon' };
  }
  const secret = await getHmacSecret().catch(e => null);
  if (!secret) {
    return { ok: false, status: 500, error: 'hmac secret unavailable' };
  }
  const expected = createHmac('sha256', secret)
    .update(canonicalizeBody(request.body || {}))
    .digest('hex');
  const provided = Buffer.from(String(providedSig), 'utf8');
  const expectedBuf = Buffer.from(expected, 'utf8');
  if (provided.length !== expectedBuf.length) {
    return { ok: false, status: 401, error: 'invalid signature length' };
  }
  if (!timingSafeEqual(provided, expectedBuf)) {
    return { ok: false, status: 401, error: 'invalid signature' };
  }
  return { ok: true, callerIdentity: String(callerIdentity).toLowerCase() };
}

// ---------------------------------------------------------------------------
// POST /api/emergency/signal — emergency_signal(...)
// Body: { signal_type: 'KILL'|'EDIT'|'PAUSE'|'RESUME',
//         target_agent: 'titan'|'achilles'|'all',
//         reason: string,
//         target_task_id?: string }
// Auth: eom or solon. HMAC-SHA256 verified.
// ---------------------------------------------------------------------------
app.post('/api/emergency/signal', async (request, reply) => {
  const auth = await verifyHmac(request);
  if (!auth.ok) return reply.status(auth.status).send({ error: auth.error });

  const body = request.body || {};
  if (!['KILL', 'EDIT', 'PAUSE', 'RESUME'].includes(body.signal_type)) {
    return reply.status(400).send({ error: 'signal_type must be KILL|EDIT|PAUSE|RESUME' });
  }
  if (!['titan', 'achilles', 'all'].includes(body.target_agent)) {
    return reply.status(400).send({ error: 'target_agent must be titan|achilles|all' });
  }
  if (!body.reason || typeof body.reason !== 'string' || body.reason.length < 4) {
    return reply.status(400).send({ error: 'reason >= 4 chars required' });
  }

  try {
    const { supabase } = await import('./db/supabase.js');
    const { data, error } = await supabase
      .from('op_emergency_signals')
      .insert([{
        signal_type:    body.signal_type,
        target_agent:   body.target_agent,
        target_task_id: body.target_task_id || null,
        reason:         body.reason,
        invoked_by:     auth.callerIdentity,
      }])
      .select('id, signal_type, target_agent, status, expires_at, created_at')
      .single();
    if (error) return reply.status(500).send({ error: error.message });
    return { success: true, signal_id: data.id, status: data.status, expires_at: data.expires_at };
  } catch (e) {
    reply.status(500).send({ error: e.message });
  }
});

// ---------------------------------------------------------------------------
// POST /api/emergency/killall — solon_emergency_killall(reason)
// Solon-only. Fires KILL to titan + achilles. Logs to amg_judge_override
// for cross-system audit (per v3 §3.3).
// Body: { reason: string }
// ---------------------------------------------------------------------------
app.post('/api/emergency/killall', async (request, reply) => {
  const auth = await verifyHmac(request);
  if (!auth.ok) return reply.status(auth.status).send({ error: auth.error });
  if (auth.callerIdentity !== 'solon') {
    return reply.status(403).send({ error: 'killall is solon-only' });
  }

  const body = request.body || {};
  if (!body.reason || typeof body.reason !== 'string' || body.reason.length < 4) {
    return reply.status(400).send({ error: 'reason >= 4 chars required' });
  }

  try {
    const { supabase } = await import('./db/supabase.js');

    // Insert one KILL per agent (titan + achilles) with shared reason.
    const inserts = [
      { signal_type: 'KILL', target_agent: 'titan',    reason: body.reason, invoked_by: 'solon' },
      { signal_type: 'KILL', target_agent: 'achilles', reason: body.reason, invoked_by: 'solon' },
    ];
    const { data: signals, error: sErr } = await supabase
      .from('op_emergency_signals')
      .insert(inserts)
      .select('id, target_agent');
    if (sErr) return reply.status(500).send({ error: sErr.message });

    // Audit-log to amg_judge_override (per v3 §3.3 directive).
    const { data: ovr, error: ovrErr } = await supabase
      .from('amg_judge_override')
      .insert([{
        invoked_by: 'solon',
        reason: 'EMERGENCY KILLALL: ' + body.reason,
        judgment_id: null,
      }])
      .select('id')
      .single()
      .then(r => r, () => ({ data: null, error: null })); // tolerate if FK requires judgment_id

    return {
      success: true,
      signals: signals.map(s => ({ id: s.id, target: s.target_agent })),
      override_id: ovr?.id || null,
    };
  } catch (e) {
    reply.status(500).send({ error: e.message });
  }
});

// ---------------------------------------------------------------------------
// GET /api/emergency/pending?agent=titan|achilles
// Harness fetch path. Returns pending signals targeting the given agent
// (or 'all'), ordered by created_at ASC for deterministic concurrent-signal
// race handling per v3 §3.6. No HMAC required — read-only and only exposes
// signals that are already targeted at the agent calling.
// ---------------------------------------------------------------------------
app.get('/api/emergency/pending', async (request, reply) => {
  const agent = String(request.query?.agent || '').toLowerCase();
  if (!['titan', 'achilles'].includes(agent)) {
    return reply.status(400).send({ error: 'agent must be titan or achilles' });
  }
  try {
    const { supabase } = await import('./db/supabase.js');
    const { data, error } = await supabase
      .from('op_emergency_signals')
      .select('id, signal_type, target_agent, target_task_id, reason, invoked_by, created_at, expires_at')
      .in('target_agent', [agent, 'all'])
      .eq('status', 'pending')
      .order('created_at', { ascending: true })
      .limit(10);
    if (error) return reply.status(500).send({ error: error.message });
    return { success: true, count: (data || []).length, signals: data || [] };
  } catch (e) {
    reply.status(500).send({ error: e.message });
  }
});

// ---------------------------------------------------------------------------
// POST /api/emergency/acknowledge — acknowledge_emergency_signal(signal_id, agent)
// Called by harness top-of-loop on receipt to flip status='acknowledged'.
// Auth: eom or solon (the harness uses its own identity per v3 §3.5).
// Body: { signal_id: uuid, agent: 'titan'|'achilles' }
// ---------------------------------------------------------------------------
app.post('/api/emergency/acknowledge', async (request, reply) => {
  const auth = await verifyHmac(request);
  if (!auth.ok) return reply.status(auth.status).send({ error: auth.error });

  const body = request.body || {};
  if (!body.signal_id) {
    return reply.status(400).send({ error: 'signal_id required' });
  }
  if (!['titan', 'achilles'].includes(body.agent)) {
    return reply.status(400).send({ error: 'agent must be titan or achilles' });
  }

  try {
    const { supabase } = await import('./db/supabase.js');

    // Append agent to acknowledged_by + flip status if not already.
    const { data: row, error: gErr } = await supabase
      .from('op_emergency_signals')
      .select('id, status, acknowledged_by, target_agent')
      .eq('id', body.signal_id)
      .single();
    if (gErr || !row) return reply.status(404).send({ error: 'signal not found' });

    const newAck = Array.from(new Set([...(row.acknowledged_by || []), body.agent]));
    const { data: upd, error: uErr } = await supabase
      .from('op_emergency_signals')
      .update({
        acknowledged_by: newAck,
        status: 'acknowledged',
        acknowledged_at: new Date().toISOString(),
      })
      .eq('id', body.signal_id)
      .select('id, status, acknowledged_by, acknowledged_at')
      .single();
    if (uErr) return reply.status(500).send({ error: uErr.message });

    return { success: true, signal: upd };
  } catch (e) {
    reply.status(500).send({ error: e.message });
  }
});
