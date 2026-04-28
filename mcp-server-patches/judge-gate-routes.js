// =============================================================================
// THREE-JUDGE QUALITY GATE — Phase 1.2 routes (per spec v1.0 §10).
// Inserted into /opt/amg-mcp-server/src/index.js right before
// `app.get("/static/doc09", ...)`.
//
// Endpoints:
//   POST /api/judgments/submit          — submit_for_judgment (cache check + insert)
//   GET  /api/judgments/pending         — get_pending_judgments (anonymized aggregate)
//   POST /api/judgments/force-approve   — solon_force_approve (Solon-only override)
//   POST /api/judgments/:id/score       — courier writeback (per-judge per-iteration)
//   POST /api/judgments/:id/finalize    — composite + verdict roll-up after 3 scores
//   GET  /api/judgments/:id             — full row (Solon-only audit; returns per-judge)
//
// Anonymization is enforced at /pending — EOM never sees per-judge breakdown
// during the revision loop. Full per-judge audit lives at /:id (Solon use only).
// =============================================================================

import { createHash } from 'node:crypto';

// ---------------------------------------------------------------------------
// POST /api/judgments/submit
// ---------------------------------------------------------------------------
app.post('/api/judgments/submit', async (request, reply) => {
  const body = request.body || {};
  const directive_md = body.directive_md;
  if (!directive_md || typeof directive_md !== 'string' || directive_md.length < 80) {
    return reply.status(400).send({ error: 'directive_md required (string, >= 80 chars)' });
  }
  const directive_class = body.directive_class || 'CLASS_A';
  if (!['CLASS_A','CLASS_B','CLASS_C'].includes(directive_class)) {
    return reply.status(400).send({ error: 'directive_class must be CLASS_A|CLASS_B|CLASS_C' });
  }
  const judges_required = Array.isArray(body.judges_required) && body.judges_required.length
    ? body.judges_required
    : ['perplexity','grok','kimi'];
  const threshold       = typeof body.threshold === 'number' ? body.threshold : 9.3;
  const target_agent    = body.target_agent || null;
  const parent_judgment_id = body.parent_judgment_id || null;
  const iteration       = parent_judgment_id ? Math.min(3, (body.iteration || 2)) : 1;
  const directive_hash  = createHash('sha256').update(directive_md).digest('hex');

  try {
    const { supabase } = await import('./db/supabase.js');

    // §9.3 hash-based cache: if a non-superseded approved judgment already
    // exists for this exact directive_md, return that judgment_id instead of
    // inserting a duplicate.
    const { data: cached } = await supabase
      .from('eom_judgments')
      .select('id, status, dispatched_at, final_directive_sha')
      .eq('directive_hash', directive_hash)
      .eq('status', 'approved')
      .order('created_at', { ascending: false })
      .limit(1);
    if (cached && cached.length > 0) {
      return { success: true, cached: true, judgment_id: cached[0].id, status: cached[0].status };
    }

    const { data, error } = await supabase
      .from('eom_judgments')
      .insert([{
        directive_md,
        directive_hash,
        directive_class,
        iteration,
        parent_judgment_id,
        status: 'pending',
        judges_required,
        threshold,
        target_agent,
      }])
      .select('id, status, iteration, directive_hash')
      .single();
    if (error) return reply.status(500).send({ error: error.message });
    return { success: true, cached: false, judgment_id: data.id, status: data.status, iteration: data.iteration, directive_hash };
  } catch (e) {
    reply.status(500).send({ error: e.message });
  }
});

// ---------------------------------------------------------------------------
// GET /api/judgments/pending — anonymized for EOM
// Query: ?since=ISO8601&limit=N&include_all=0|1
// include_all=1 returns approved+revision_needed+pending; default returns only
// rows whose status changed since `since`.
// ---------------------------------------------------------------------------
app.get('/api/judgments/pending', async (request, reply) => {
  const q = request.query || {};
  const limit = Math.min(parseInt(q.limit || '25'), 100);
  const since = q.since || null;
  const include_all = q.include_all === '1' || q.include_all === 'true';
  try {
    const { supabase } = await import('./db/supabase.js');
    let query = supabase
      .from('eom_judgment_aggregate')
      .select('judgment_id, iteration, status, directive_class, directive_hash, composite_min, composite_max, composite_mean, score_spread, contested, dimensions_failing, aggregated_top_issues, aggregated_revision_hints, confidence_summary, created_at, updated_at')
      .order('updated_at', { ascending: false })
      .limit(limit);
    if (since)             query = query.gte('updated_at', since);
    if (!include_all)      query = query.in('status', ['pending','in_review','revision_needed']);
    const { data, error } = await query;
    if (error) return reply.status(500).send({ error: error.message });
    return { success: true, anonymized: true, rubric_version: 'v1.0', count: (data || []).length, rows: data || [] };
  } catch (e) {
    reply.status(500).send({ error: e.message });
  }
});

// ---------------------------------------------------------------------------
// POST /api/judgments/force-approve — Solon-only override
// Body: { judgment_id, reason }
// ---------------------------------------------------------------------------
app.post('/api/judgments/force-approve', async (request, reply) => {
  const body = request.body || {};
  if (!body.judgment_id) return reply.status(400).send({ error: 'judgment_id required' });
  if (!body.reason || body.reason.length < 8) return reply.status(400).send({ error: 'reason >= 8 chars required' });
  try {
    const { supabase } = await import('./db/supabase.js');
    const { data: ovr, error: ovrErr } = await supabase
      .from('amg_judge_override')
      .insert([{ judgment_id: body.judgment_id, invoked_by: body.invoked_by || 'solon', reason: body.reason }])
      .select('id')
      .single();
    if (ovrErr) return reply.status(500).send({ error: ovrErr.message });
    const { error: updErr } = await supabase
      .from('eom_judgments')
      .update({ status: 'approved', force_approve_override_id: ovr.id, dispatched_at: new Date().toISOString() })
      .eq('id', body.judgment_id);
    if (updErr) return reply.status(500).send({ error: updErr.message });
    return { success: true, override_id: ovr.id, status: 'approved' };
  } catch (e) {
    reply.status(500).send({ error: e.message });
  }
});

// ---------------------------------------------------------------------------
// POST /api/judgments/:id/score — courier writes per-judge result
// Body: { judge_name, iteration, composite, scores:{...}, verdict, confidence,
//         top_issues:[], revision_hints:[], judge_status, response_latency_seconds, raw_response }
// ---------------------------------------------------------------------------
app.post('/api/judgments/:id/score', async (request, reply) => {
  const judgment_id = request.params.id;
  const b = request.body || {};
  if (!b.judge_name) return reply.status(400).send({ error: 'judge_name required' });
  const scores = b.scores || {};
  const raw_response_hash = b.raw_response
    ? createHash('sha256').update(String(b.raw_response)).digest('hex')
    : null;
  try {
    const { supabase } = await import('./db/supabase.js');
    const { data, error } = await supabase
      .from('eom_judgment_scores')
      .upsert([{
        judgment_id,
        judge_name: b.judge_name,
        iteration: b.iteration || 1,
        composite: b.composite ?? null,
        score_clarity:      scores.clarity      ?? null,
        score_technical:    scores.technical    ?? null,
        score_completeness: scores.completeness ?? null,
        score_risk:         scores.risk         ?? null,
        score_amg_fit:      scores.amg_fit      ?? null,
        score_acceptance:   scores.acceptance   ?? null,
        score_idempotency:  scores.idempotency  ?? null,
        verdict:            b.verdict           ?? null,
        confidence:         b.confidence        ?? null,
        top_issues:         b.top_issues        ?? [],
        revision_hints:     b.revision_hints    ?? [],
        judge_status:       b.judge_status      ?? 'scored',
        response_latency_seconds: b.response_latency_seconds ?? null,
        raw_response_hash,
      }], { onConflict: 'judgment_id,judge_name,iteration' })
      .select('id, judge_name, judge_status, composite')
      .single();
    if (error) return reply.status(500).send({ error: error.message });
    // bump parent updated_at
    await supabase.from('eom_judgments').update({ status: 'in_review' }).eq('id', judgment_id);
    return { success: true, score_id: data.id, judge_name: data.judge_name, judge_status: data.judge_status, composite: data.composite };
  } catch (e) {
    reply.status(500).send({ error: e.message });
  }
});

// ---------------------------------------------------------------------------
// POST /api/judgments/:id/finalize — composite roll-up + verdict per §3 §7
// Computes min/max/mean across ALL non-unavailable judges for current
// iteration. Sets eom_judgments.status to approved | revision_needed |
// rejected_max_iter | escalated.
// Pass: composite >= threshold AND every dimension >= 9.0 across all judges.
// ESCALATE: any judge verdict='ESCALATE'.
// REVISE wins over PASS when judges disagree (conservative bias §7.3).
// ---------------------------------------------------------------------------
app.post('/api/judgments/:id/finalize', async (request, reply) => {
  const judgment_id = request.params.id;
  try {
    const { supabase } = await import('./db/supabase.js');
    const { data: jrow, error: jerr } = await supabase
      .from('eom_judgments')
      .select('id, iteration, threshold, judges_required')
      .eq('id', judgment_id)
      .single();
    if (jerr || !jrow) return reply.status(404).send({ error: 'judgment not found' });

    const { data: scores, error: serr } = await supabase
      .from('eom_judgment_scores')
      .select('judge_name, judge_status, verdict, composite, score_clarity, score_technical, score_completeness, score_risk, score_amg_fit, score_acceptance, score_idempotency')
      .eq('judgment_id', judgment_id)
      .eq('iteration', jrow.iteration);
    if (serr) return reply.status(500).send({ error: serr.message });
    const scored = (scores || []).filter(s => s.judge_status === 'scored' && s.composite != null);

    if (scored.length < 2) {
      return reply.status(409).send({ error: 'need >= 2 scored judges before finalize', scored_count: scored.length });
    }

    const composites = scored.map(s => Number(s.composite));
    const composite_min  = Math.min(...composites);
    const composite_max  = Math.max(...composites);
    const composite_mean = composites.reduce((a,b)=>a+b,0) / composites.length;

    const dimsBelow9 = scored.some(s =>
      ['score_clarity','score_technical','score_completeness','score_risk','score_amg_fit','score_acceptance','score_idempotency']
        .some(k => s[k] != null && Number(s[k]) < 9.0)
    );
    const escalate = scored.some(s => s.verdict === 'ESCALATE');
    const anyRevise = scored.some(s => s.verdict === 'REVISE');
    const passing = composite_min >= jrow.threshold && !dimsBelow9 && !anyRevise && !escalate;

    let next_status;
    if (escalate)                   next_status = 'escalated';
    else if (passing)               next_status = 'approved';
    else if (jrow.iteration >= 3)   next_status = 'rejected_max_iter';
    else                            next_status = 'revision_needed';

    const upd = {
      status: next_status,
      composite_min:  Number(composite_min.toFixed(2)),
      composite_max:  Number(composite_max.toFixed(2)),
      composite_mean: Number(composite_mean.toFixed(2)),
    };
    if (next_status === 'approved') {
      upd.dispatched_at        = new Date().toISOString();
      upd.final_directive_sha  = (await supabase
        .from('eom_judgments').select('directive_hash').eq('id', judgment_id).single()
      ).data?.directive_hash || null;
    }
    const { error: uerr } = await supabase.from('eom_judgments').update(upd).eq('id', judgment_id);
    if (uerr) return reply.status(500).send({ error: uerr.message });

    return {
      success: true,
      judgment_id,
      iteration: jrow.iteration,
      next_status,
      composite_min, composite_max, composite_mean,
      scored_count: scored.length,
      dims_below_9: dimsBelow9,
      escalate,
    };
  } catch (e) {
    reply.status(500).send({ error: e.message });
  }
});

// ---------------------------------------------------------------------------
// GET /api/judgments/:id — full row (Solon-only audit, includes per-judge)
// ---------------------------------------------------------------------------
app.get('/api/judgments/:id', async (request, reply) => {
  const judgment_id = request.params.id;
  try {
    const { supabase } = await import('./db/supabase.js');
    const { data: j, error: je } = await supabase.from('eom_judgments').select('*').eq('id', judgment_id).single();
    if (je || !j) return reply.status(404).send({ error: 'not found' });
    const { data: s }  = await supabase.from('eom_judgment_scores').select('*').eq('judgment_id', judgment_id).order('iteration').order('judge_name');
    const { data: ov } = await supabase.from('amg_judge_override').select('*').eq('judgment_id', judgment_id);
    return { success: true, judgment: j, scores: s || [], overrides: ov || [] };
  } catch (e) {
    reply.status(500).send({ error: e.message });
  }
});
