/**
 * MCP tool: agent_context_loader
 *
 * Returns a structured context block for a project-backed agent call.
 *   - cacheable_prefix: system prompt + full agent KB (idempotent, cache-controllable)
 *   - query_tail: client_facts (top-N from Supabase) + recent-memory hits (top-5 via op_search_memory)
 *
 * Caller (lib/agent.py or WoZ handler) wires the cacheable_prefix with
 * Anthropic `cache_control: {"type": "ephemeral"}` on the KB blocks, and
 * passes query_tail + user message uncached.
 *
 * KB files live at /opt/amg-docs/agents/{agent}/kb/*.md — loaded at startup,
 * hot-reloaded on mtime change via fs.watch.
 *
 * Design doc: plans/agents/PROJECT_BACKED_AGENTS.md (CT-0416-23)
 */
import { supabase } from '../db/supabase.js';
import fs from 'node:fs';
import path from 'node:path';

const KB_ROOT = process.env.AGENT_KB_ROOT || '/opt/amg-docs/agents';
const VALID_AGENTS = ['alex', 'maya', 'jordan', 'sam', 'riley', 'nadia', 'lumina'];
const MAX_FACTS_DEFAULT = 40;
const MEMORY_HITS_DEFAULT = 5;
const KB_CACHE_RELOAD_MS = 60_000;

// In-memory KB cache — { agent: { bundle: '…concatenated md…', token_count: N, loaded_at: Date, mtime_latest: number } }
const kbCache = new Map();

// Rough token estimator — chars / 4. Conservative; matches bin/kb-tokenize.sh.
function estimateTokens(s) {
  return Math.ceil((s || '').length / 4);
}

function loadAgentKB(agent) {
  const agentDir = path.join(KB_ROOT, agent, 'kb');
  if (!fs.existsSync(agentDir)) {
    return { bundle: '', token_count: 0, files: 0, mtime_latest: 0 };
  }
  const files = fs.readdirSync(agentDir)
    .filter(f => f.endsWith('.md'))
    .sort(); // deterministic order — enables cache-hit consistency

  let bundle = '';
  let mtimeLatest = 0;
  for (const f of files) {
    const full = path.join(agentDir, f);
    const stat = fs.statSync(full);
    if (stat.mtimeMs > mtimeLatest) mtimeLatest = stat.mtimeMs;
    const body = fs.readFileSync(full, 'utf8');
    bundle += `\n\n## KB: ${f}\n\n${body}`;
  }
  return {
    bundle: bundle.trim(),
    token_count: estimateTokens(bundle),
    files: files.length,
    mtime_latest: mtimeLatest,
  };
}

function getKB(agent) {
  const cached = kbCache.get(agent);
  const now = Date.now();
  if (cached && (now - (cached._checked || 0)) < KB_CACHE_RELOAD_MS) {
    return cached;
  }
  const fresh = loadAgentKB(agent);
  fresh._checked = now;
  // If mtime bumped, re-version the cache key so Anthropic re-caches
  if (cached && cached.mtime_latest !== fresh.mtime_latest) {
    fresh.cache_version = (cached.cache_version || 0) + 1;
  } else if (cached) {
    fresh.cache_version = cached.cache_version || 1;
  } else {
    fresh.cache_version = 1;
  }
  kbCache.set(agent, fresh);
  return fresh;
}

async function getClientFacts(clientId, maxFacts = MAX_FACTS_DEFAULT) {
  try {
    const { data, error } = await supabase.rpc('op_get_client_facts', {
      p_client_id: clientId,
      p_max_facts: maxFacts,
      p_fact_types: null,
    });
    if (error) return { facts: [], error: error.message };
    const block = (data || [])
      .map(f => `- [${f.fact_type}] (confidence ${(f.confidence * 100).toFixed(0)}%) ${f.content}`)
      .join('\n');
    return {
      facts: data || [],
      block,
      token_count: estimateTokens(block),
    };
  } catch (e) {
    return { facts: [], error: e.message };
  }
}

async function getMemoryHits(query, clientId, count = MEMORY_HITS_DEFAULT) {
  try {
    // Embed via the same pathway log_decision uses (see db/embeddings.js)
    const { embedText } = await import('../db/embeddings.js');
    const emb = await embedText(query);
    if (!emb) return { hits: [], block: '', token_count: 0 };

    const { data, error } = await supabase.rpc('op_search_memory', {
      query_embedding: `[${emb.join(',')}]`,
      match_count: count,
      filter_project: clientId,   // scope isolation per §11 of design doc
      filter_chunk_types: null,
      include_archived: false,
    });
    if (error) return { hits: [], block: '', error: error.message };
    const block = (data || [])
      .map((m, i) =>
        `${i + 1}. [${m.chunk_type || 'fact'}] (similarity ${(m.similarity * 100).toFixed(1)}%) ${m.summary || (m.content || '').slice(0, 240)}`
      ).join('\n');
    return { hits: data || [], block, token_count: estimateTokens(block) };
  } catch (e) {
    return { hits: [], block: '', error: e.message };
  }
}

export const agentContextLoaderTool = {
  name: 'agent_context_loader',
  description: 'Return a structured context block for a project-backed agent call. Includes agent KB (cacheable_prefix) + client facts + recent semantic memory hits (query_tail). Caller wires cacheable_prefix with Anthropic cache_control ephemeral.',
  inputSchema: {
    type: 'object',
    properties: {
      agent_name: {
        type: 'string',
        enum: VALID_AGENTS,
        description: 'Which agent is being called. Loads /opt/amg-docs/agents/{agent_name}/kb/*.md',
      },
      client_id: {
        type: 'string',
        description: 'Subscriber slug, e.g. "levar", "shop-unis", "revere-chamber".',
      },
      query: {
        type: 'string',
        description: 'The user message, used for semantic memory retrieval scoped to client_id.',
      },
      include_memory: {
        type: 'boolean',
        default: true,
        description: 'Set false for first-turn messages where past-conversation recall isn\'t useful.',
      },
      max_facts: {
        type: 'number',
        default: MAX_FACTS_DEFAULT,
      },
    },
    required: ['agent_name', 'client_id', 'query'],
  },
  handler: async (args) => {
    if (!VALID_AGENTS.includes(args.agent_name)) {
      return { content: [{ type: 'text', text: `Error: unknown agent ${args.agent_name}. Valid: ${VALID_AGENTS.join(', ')}` }] };
    }

    const kb = getKB(args.agent_name);
    const factsPromise = getClientFacts(args.client_id, args.max_facts || MAX_FACTS_DEFAULT);
    const memPromise = (args.include_memory !== false)
      ? getMemoryHits(args.query, args.client_id)
      : Promise.resolve({ hits: [], block: '', token_count: 0 });

    const [facts, mem] = await Promise.all([factsPromise, memPromise]);

    const cacheableSystem = `You are the ${args.agent_name} agent for AMG (AI Marketing Genius). Use the KB below verbatim for ground truth; defer to it for any client-facing factual statement. [kb_cache_v${kb.cache_version}_${args.agent_name}]`;

    const result = {
      cacheable_prefix: {
        system_prompt: cacheableSystem,
        kb_bundle: kb.bundle,
        kb_token_count: kb.token_count,
        kb_files: kb.files,
        kb_cache_version: kb.cache_version,
        kb_cache_key: `${args.agent_name}_kb_v${kb.cache_version}`,
      },
      query_tail: {
        client_facts_block: facts.block || '',
        client_facts_count: (facts.facts || []).length,
        client_facts_token_count: facts.token_count || 0,
        memory_block: mem.block || '',
        memory_hits_count: (mem.hits || []).length,
        memory_token_count: mem.token_count || 0,
      },
      _meta: {
        loader_version: '1.0',
        generated_at: new Date().toISOString(),
        kb_loaded_from: path.join(KB_ROOT, args.agent_name, 'kb'),
        facts_error: facts.error || null,
        memory_error: mem.error || null,
      },
    };

    return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
  },
};
