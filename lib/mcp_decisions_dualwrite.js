/**
 * Patched log_decision handler — dual-writes to op_decisions AND op_memory_vectors.
 *
 * CT-0416-29 fix: the prior implementation only wrote to op_decisions.
 * op_search_memory queries op_memory_vectors, so decisions were invisible to
 * semantic search even though they had embeddings. 1343 decisions accumulated
 * between Apr 3 and Apr 17 before Solon caught the gap.
 *
 * This version writes to BOTH tables in one call using the same op_decisions.id
 * as the op_memory_vectors.id for idempotency. A retry on op_memory_vectors
 * failure does NOT abort the op_decisions write — the decision is canonical,
 * the search index is derived.
 */
import { supabase } from '../db/supabase.js';
import { embedText } from '../db/embeddings.js';

function summarize(text, maxChars = 180) {
  const t = (text || '').trim();
  if (t.length <= maxChars) return t;
  const head = t.slice(0, maxChars);
  const nl = head.lastIndexOf('\n');
  const pd = head.lastIndexOf('. ');
  const cut = Math.max(nl, pd);
  if (cut > maxChars / 2) return head.slice(0, cut).trim() + '…';
  return head.trim() + '…';
}

export const logDecisionTool = {
  name: 'log_decision',
  description: 'Log a decision made during a conversation. Automatically embeds for semantic search and triggers conflict detection.',
  inputSchema: {
    type: 'object',
    properties: {
      text: { type: 'string', description: 'The decision text' },
      rationale: { type: 'string', description: 'Why this decision was made' },
      project_source: { type: 'string', description: 'Which project made this decision (e.g., EOM, SEO_CONTENT)' },
      tags: { type: 'array', items: { type: 'string' }, description: 'Tags for categorization' }
    },
    required: ['text', 'project_source']
  },
  handler: async (args) => {
    const embedding = await embedText(args.text + ' ' + (args.rationale || ''));
    const embeddingStr = embedding ? `[${embedding.join(',')}]` : null;

    // Write 1: canonical op_decisions row
    const { data, error } = await supabase
      .from('op_decisions')
      .insert({
        decision_text: args.text,
        rationale: args.rationale || '',
        project_source: args.project_source,
        tags: args.tags || [],
        embedding: embeddingStr,
        operator_id: 'OPERATOR_AMG',
        model_name: 'nomic-embed-text',
        embedding_dim: 768
      })
      .select('id');

    if (error) return { content: [{ type: 'text', text: `Error logging decision: ${error.message}` }] };

    const decisionId = data?.[0]?.id;

    // Write 2: mirror into op_memory_vectors so search_memory can find it.
    // CT-0416-29 fix: previously this step didn't exist → decisions were invisible to semantic search.
    // Non-fatal: if this fails, the canonical decision is still stored; cron/backfill can repair.
    if (embedding && decisionId) {
      const content = [
        args.text,
        args.rationale ? `\n\nRationale: ${args.rationale}` : '',
        args.tags && args.tags.length ? `\nTags: ${args.tags.join(', ')}` : ''
      ].join('');

      const mvRow = {
        id: decisionId, // reuse decision id → idempotent, one-to-one linkage
        content,
        summary: summarize(args.text),
        embedding: embeddingStr,
        project_tag: args.project_source,
        project_id: args.project_source,
        chunk_type: 'decision',
        operator_id: 'OPERATOR_AMG',
        model_name: 'nomic-embed-text',
        embedding_dim: 768,
        topic_tags: args.tags || [],
        status: 'active',
        pinned: false,
        muted: false
      };
      const mvResp = await supabase.from('op_memory_vectors').upsert(mvRow, { onConflict: 'id' });
      if (mvResp.error) {
        console.error('[log_decision] op_memory_vectors mirror failed (decision stored, search will be stale until re-backfill):', mvResp.error.message);
      }
    }

    // Sprint state update
    await supabase
      .from('op_sprint_state')
      .update({ last_decision: args.text, last_updated: new Date().toISOString() })
      .eq('project_id', args.project_source);

    // Fire-and-forget conflict check
    try {
      fetch('https://n8n.aimarketinggenius.io/webhook/amg-conflict-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision_id: decisionId, decision_text: args.text, project_source: args.project_source })
      }).catch(() => {});
    } catch (e) { /* ignore */ }

    return { content: [{ type: 'text', text: `Decision logged (${args.project_source}): "${args.text}" — Conflict check triggered.` }] };
  }
};

export const getRecentDecisionsTool = {
  name: 'get_recent_decisions',
  description: 'Get the N most recent decisions across all projects.',
  inputSchema: {
    type: 'object',
    properties: {
      count: { type: 'number', description: 'Number of decisions (default: 5, max: 20)', default: 5 },
      project_filter: { type: 'string', description: 'Optional: filter to a specific project' }
    }
  },
  handler: async (args) => {
    const count = Math.min(args.count || 5, 20);
    let query = supabase
      .from('op_decisions')
      .select('decision_text, rationale, project_source, tags, created_at')
      .order('created_at', { ascending: false })
      .limit(count);

    if (args.project_filter) query = query.eq('project_source', args.project_filter);

    const { data, error } = await query;
    if (error) return { content: [{ type: 'text', text: `Error: ${error.message}` }] };

    const formatted = (data || []).map((d, i) =>
      `${i + 1}. [${d.project_source}] ${d.decision_text}\n   Rationale: ${d.rationale || 'none'}\n   Created: ${d.created_at}`
    ).join('\n\n');

    return { content: [{ type: 'text', text: formatted || 'No decisions found.' }] };
  }
};
