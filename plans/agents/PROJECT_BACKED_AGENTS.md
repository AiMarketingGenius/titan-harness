# PROJECT-BACKED AGENTS — DESIGN DOC

**Task:** CT-0416-23
**Status:** Day 1 design doc · awaiting Solon review before Day 2 implementation
**Owner:** Titan
**Estimated total:** 3-5 focused working days (not weeks)
**Author date:** 2026-04-17

---

## 0. ONE-PARAGRAPH SUMMARY

AMG's WoZ agents (Alex, Maya, Jordan, Sam, Riley, Nadia, Lumina) currently make stateless Claude API calls with a 2-3K-token system prompt, no KB access, and no memory. Result: output quality is measurably below what Solon gets when he uses Claude Projects with the same agents manually loaded. This doc specifies a project-backed agent pattern that injects each agent's full knowledge base (up to 30K tokens) on every call, uses Anthropic prompt caching to keep the incremental token cost pennies, pulls client-specific facts from Supabase, and opens a ticket for past-conversation recall via the existing MCP `search_memory` (now functional post-CT-0416-29). Target: new-pattern output matches Claude Projects quality within a ±0.5 grader-point band, at 1/6 the uncached-per-call token cost.

---

## 1. PROBLEM STATEMENT (measured, not anecdotal)

### 1.1 Current state

```
┌───────────────────┐   ┌──────────────────────┐   ┌──────────────┐
│  WoZ UI / n8n     │──▶│  lib/agent.py        │──▶│  Anthropic   │
│  (client msg in)  │   │  → stateless call    │   │  messages API │
└───────────────────┘   │  → 2–3K sys prompt   │   └──────────────┘
                        │  → user msg only     │
                        └──────────────────────┘
```

- **System prompt:** 2-3K tokens (role, tone, banned phrases, agent name)
- **KB access:** none
- **Client context:** none (agent doesn't know which subscriber is asking)
- **Past conversations:** none
- **Evidence Solon surfaced:** when he manually uses Claude Projects for the same agent with the KB loaded, output quality materially higher (fewer generic phrasings, richer recall of AMG-specific context, better alignment with Solon's voice, fewer asks for clarification).

### 1.2 Target state

```
┌──────────────┐  ┌───────────────────────┐  ┌──────────────────┐  ┌──────────────┐
│ client msg   │─▶│ agent_context_loader  │─▶│ lib/agent.py     │─▶│ Anthropic    │
└──────────────┘  │ MCP tool              │  │ - cache: KB (30K)│  │ messages API │
                  │ - agent KB (≤30K)     │  │ - cache: client  │  │ cache_control│
                  │ - client_facts        │  │   facts (≤2K)    │  └──────────────┘
                  │ - search_memory hits  │  │ - uncached: msg  │
                  └───────────────────────┘  └──────────────────┘
```

- **KB loaded:** full agent KB injected, cached 5 min via `cache_control: ephemeral`
- **Client facts:** pulled from Supabase `client_facts` by `client_id`, cached
- **Past conversations:** top-5 `search_memory` results for this client's recent context (uncached, fresh per call)
- **Token cost per cached call:** 1/10 the uncached rate per Anthropic's published pricing (input cache read = $0.30/MTok vs $3.00/MTok base for Sonnet 4.6)
- **Target cache hit rate:** >80% on repeat calls within a 5-min window

---

## 2. DATA MODEL

### 2.1 Agent KB file structure on VPS

```
/opt/amg-docs/agents/
├── alex/                  # Business Coach
│   ├── kb/
│   │   ├── 00_identity.md         # who Alex is, AMG backstory
│   │   ├── 01_capabilities.md     # what Alex can and cannot do
│   │   ├── 02_tone_voice.md       # voice rules, banned phrases
│   │   ├── 03_amg_pricing.md      # subscriber/Chamber pricing
│   │   ├── 04_service_map.md      # which other agents do what
│   │   ├── 05_atlas_context.md    # Atlas engine, Chamber AI Advantage
│   │   ├── 06_trade_secrets.md    # never-mention rules (Claude/GPT/etc)
│   │   └── 99_examples.md         # 10 gold-standard Q/A exchanges
│   └── META.yaml                  # cache_key, max_tokens, last_reviewed
├── maya/                  # Content Strategist
├── jordan/                # SEO Specialist
├── sam/                   # Social Media Manager
├── riley/                 # Reviews Manager
├── nadia/                 # Outbound Coordinator
└── lumina/                # Conversion Optimizer
```

- Each agent KB ≤ 30K tokens (~22K words), hard cap validated by `bin/kb-tokenize.sh` pre-commit
- All KBs version-controlled in the harness repo at `plans/agents/kb/{agent}/...` (mirrored to `/opt/amg-docs/agents/` on both VPS via Hercules Triangle)
- `META.yaml` holds: `cache_key`, `max_tokens`, `last_reviewed`, `source_of_truth_refs` (links to AMG encyclopedia sections), `qa_pairs_count`

### 2.2 Supabase `client_facts` table

Already exists in spirit — need to canonicalize:

```sql
CREATE TABLE IF NOT EXISTS public.client_facts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id text NOT NULL,                -- 'levar', 'shop-unis', 'revere-chamber'
  fact_type text NOT NULL,                -- 'brand', 'audience', 'voice_sample',
                                          -- 'active_campaign', 'recent_decision',
                                          -- 'do_not_mention', 'hot_button'
  content text NOT NULL,                  -- the fact itself
  confidence real DEFAULT 1.0,            -- 0-1, from grader/harvest
  source text,                            -- 'solon_loom_mp1', 'woz_transcript',
                                          -- 'intake_form', 'manual'
  created_at timestamptz DEFAULT now(),
  last_verified_at timestamptz,
  superseded boolean DEFAULT false,
  tags text[]
);
CREATE INDEX idx_client_facts_client_active
  ON public.client_facts (client_id)
  WHERE superseded = false;
```

Reads: `SELECT content, fact_type FROM client_facts WHERE client_id = $1 AND superseded = false ORDER BY confidence DESC LIMIT 40` — keep under ~2K tokens.

---

## 3. MCP TOOL — `agent_context_loader`

### 3.1 Signature

```typescript
{
  name: 'agent_context_loader',
  description: 'Return a structured context block for a project-backed agent call. Includes agent KB + client facts + recent-memory hits. Cacheable prefix returned separately from query-dependent tail.',
  inputSchema: {
    type: 'object',
    properties: {
      agent_name: {
        type: 'string',
        enum: ['alex', 'maya', 'jordan', 'sam', 'riley', 'nadia', 'lumina']
      },
      client_id: {
        type: 'string',
        description: 'Subscriber slug, e.g. "levar", "shop-unis", "revere-chamber"'
      },
      query: {
        type: 'string',
        description: 'The user message, used to semantically retrieve 5 most-relevant past decisions/memories for THIS client.'
      },
      include_memory: {
        type: 'boolean',
        default: true,
        description: 'Set false for agents that don\'t need past-convo recall (e.g. first onboarding message).'
      }
    },
    required: ['agent_name', 'client_id', 'query']
  }
}
```

### 3.2 Return shape

```json
{
  "cacheable_prefix": {
    "system_prompt": "You are Alex, AMG Business Coach. ...",   // fixed per agent
    "kb_bundle": "<full 00_identity.md + 01_capabilities.md + ... concatenated with ## headers>",
    "kb_token_count": 28741,
    "kb_cache_key": "alex_kb_v3_2026-04-16"
  },
  "query_tail": {
    "client_facts_block": "<top-40 client facts formatted as bullets>",
    "memory_hits": [
      { "content": "…", "similarity": 0.82, "created_at": "…" }
    ],
    "memory_token_count": 812,
    "client_facts_token_count": 1340
  },
  "_meta": { "loader_version": "1.0", "generated_at": "…" }
}
```

The CALLER (`lib/agent.py`) is responsible for wiring the `cacheable_prefix` into Anthropic's `system` param with `cache_control: {"type": "ephemeral"}` and passing `query_tail` + user message uncached.

### 3.3 Implementation notes

- Lives at `/opt/amg-mcp-server/src/tools/agent_context_loader.js`
- Reads KB files from `/opt/amg-docs/agents/{agent_name}/kb/` at server startup, caches in memory, reloads on SIGHUP or file mtime change (check each 60 s via `fs.watch`)
- Client facts pulled from Supabase on every call (cheap, <50 ms)
- Memory hits use the already-fixed `op_search_memory` RPC with `project_filter = client_id`
- Returns in <200 ms p50, <500 ms p99

### 3.4 Dependencies

- CT-0416-29 search_memory fix (SHIPPED 2026-04-17) ✓
- `client_facts` table migration — needs to be written as `sql/150_client_facts.sql`
- Agent KB content — biggest effort, see §5 timeline

---

## 4. PROMPT CACHING — TOKEN MATH

Using Claude Sonnet 4.6 at current Anthropic pricing:

| Bucket | Rate | Notes |
|---|---|---|
| Input base | $3.00 / MTok | |
| Input cache write | $3.75 / MTok | 1st call in 5 min window |
| Input cache read | $0.30 / MTok | 2nd+ call in 5 min window |
| Output | $15.00 / MTok | |

### 4.1 Per-call math for Alex (worst-case: full 30K KB)

**First call in window (cache write):**
- KB: 30K tokens × $3.75/M = **$0.1125** (cache write)
- Client facts: 1.5K × $3.00/M = $0.0045
- Memory hits: 0.8K × $3.00/M = $0.0024
- User msg: 0.3K × $3.00/M = $0.0009
- Output: 1K × $15/M = $0.015
- **Total: ~$0.134 per first call**

**2nd+ call in same 5-min window (cache read):**
- KB: 30K × $0.30/M = **$0.009** (cache read)
- Client facts: 1.5K × $0.30/M = $0.00045 (also cacheable)
- Memory hits: 0.8K × $3.00/M = $0.0024 (fresh, uncached)
- User msg: 0.3K × $3.00/M = $0.0009
- Output: 1K × $15/M = $0.015
- **Total: ~$0.027 per cached call** — **80% cheaper than first call, ~10× cheaper on the KB portion**

### 4.2 Comparison to today's stateless call

- Current: 2.5K sys + 0.3K msg + 1K out = 2.8K × $3.00/M + 1K × $15/M = $0.0234
- New uncached: $0.134 (~5.7× more)
- New cached: $0.027 (~15% more than today for FAR higher quality)

At expected traffic patterns (bursty — 5+ messages per client within 5 min during a content-drafting session), cached calls will dominate. If we hit >80% cache-hit rate (target), average per-call cost lands at ~$0.04 — ~70% higher than today's stateless, for the quality jump Solon is paying for.

### 4.3 Cache key strategy

Anthropic caches by CONTENT HASH of the cached prefix. We can version the cache by appending a tiny version suffix to the system prompt:

```
You are Alex, AMG Business Coach.  [kb_cache_key: alex_kb_v3_2026-04-16]
```

Incrementing `kb_cache_key` forces re-cache on next call, useful when we ship an updated KB.

---

## 5. 5-DAY SHIP PLAN

### Day 1 (TODAY) — DESIGN + LOADER SCAFFOLD

- [x] This design doc written
- [ ] `sql/150_client_facts.sql` migration — table + index
- [ ] `agent_context_loader.js` MCP tool — scaffold + file-watcher for KBs
- [ ] `bin/kb-tokenize.sh` — pre-commit token count validator
- [ ] Register tool in `/opt/amg-mcp-server/src/index.js` tool list

### Day 2 — ALEX KB (first agent, most-used)

- [ ] Draft `plans/agents/kb/alex/00_identity.md` through `99_examples.md`
- [ ] Source content from: AMG Encyclopedia, existing Alex system prompt, Solon Loom corpus (voice samples), MP-1 harvest outputs
- [ ] Cap: 30K tokens validated
- [ ] Ship to `/opt/amg-docs/agents/alex/` on both VPS via Hercules Triangle
- [ ] First end-to-end test: hit `agent_context_loader` with `{agent: 'alex', client: 'levar', query: '...' }`, confirm shape
- [ ] Wire `lib/agent.py` (or wherever WoZ Alex calls live) with `cache_control: ephemeral` on the KB portion

### Day 3 — REMAINING 6 AGENTS + PROMPT CACHING

- [ ] KBs for Maya, Jordan, Sam, Riley, Nadia, Lumina (each ≤ 30K tokens)
- [ ] Prompt caching wired end-to-end for all 7 agents
- [ ] Verify Anthropic response includes `cache_creation_input_tokens` + `cache_read_input_tokens` fields — confirms caching active
- [ ] Cost-metering script runs on every call and writes per-agent cost-per-day to `op_metrics` table

### Day 4 — A/B TEST + MIGRATION

- [ ] Define 10 identical client queries across different agents (Levar content request, Shop UNIS SEO question, Revere Chamber intro msg, etc.)
- [ ] Run old pattern vs new pattern, blind-grade via `lib/grader.py` at `scope_tier=amg_pro, artifact_type=deliverable`
- [ ] Acceptance: new ≥ old + 1.0 average points (not 0.5 — Solon specifically raised the bar)
- [ ] Cut-over switch in `lib/agent.py` — feature flag `PROJECT_BACKED_AGENTS=true` in `policy.yaml`
- [ ] Monitor cache hit rate via Anthropic response fields; target >80% within first 48 h

### Day 5 — EXTERNAL REVIEW + SHIP

- [ ] Cross-validate architecture via Perplexity Sonar Pro OR Gemini 2.5 Pro deep review — feed this design doc + Day 4 A/B results + lib/agent.py diff, ask for architecture soundness grade
- [ ] Require ≥ 8.5 on architecture soundness before flipping feature flag in production
- [ ] Ship to production; retire stateless code path (keep dead-code behind feature flag for 1 week, then delete)
- [ ] Log full A/B report to MCP

### No sandbagging clause (Solon directive)

- 3-5 focused working days, not weeks. Any phase hitting a wall logs the specific blocker AND a concrete next step, does not add padding.
- If Day 3 (6 KBs) is the biggest risk, the fallback is ship Alex + Maya first as the client-facing pair for Levar / Shop UNIS / Revere, leave the other 5 on stateless for another sprint.

---

## 6. A/B TEST RUBRIC

Grader is `lib/grader.py` · `scope_tier=amg_pro` · `artifact_type=deliverable`. 10-dimension rubric:

1. Alignment with AMG brand voice (0-10) — does it sound like Solon / AMG?
2. Recall of client-specific context (0-10) — does it reference the right account, brand, active campaign?
3. Trade-secret compliance (0-10) — zero mentions of Claude/Anthropic/GPT/OpenAI/Gemini?
4. Actionability (0-10) — does it give the subscriber a next step?
5. Length-appropriateness (0-10) — not too short, not rambling?
6. Factual accuracy against KB (0-10) — no hallucinated capabilities or prices?
7. Tone warmth (0-10) — human operator energy, not corporate-speak?
8. Recall of past interactions (0-10) — does it reference prior context where relevant?
9. Zero banned phrases (binary × 10) — no "I'd be happy to help," "certainly!", etc.
10. Overall quality (0-10) — reviewer gestalt

Per Solon:
- Floor: new ≥ 8.5 overall per-response
- Bar: new ≥ old + 1.0 average (not 0.5 — he wants meaningful lift, not incremental)

---

## 7. SECURITY / TRADE-SECRET GUARDRAILS

- `06_trade_secrets.md` in every agent KB enumerates the banned terms list. Loaded into context on every call — if the model drifts, it drifts back.
- `bin/tradesecret-scan.sh` runs on every WoZ response BEFORE it's shown to the subscriber. Any hit → reject + retry with stricter instruction.
- Rate limit at `agent_context_loader` level: 20 requests/client/5-min. Blocks runaway loops.

---

## 8. OPEN QUESTIONS FOR SOLON

1. **Voice sample vs voice description** — for agents that mirror Solon's voice (Alex primarily), should the KB include actual voice samples from the MP-1 Loom corpus (risks overfitting to transcripts) or an abstracted voice description? Recommend: both — 3 short sampled quotes + a 500-word voice description.
2. **Client-specific agent fine-tuning** — for white-label clients (Revere Chamber members), should we maintain a PER-CLIENT KB override layer on top of the agent KB? E.g. Revere members get "Chamber voice" variant. Recommend: yes, phase 2 after the 7-agent base ships.
3. **Past-conversation cache scope** — `search_memory` currently scopes by `project_filter`. For WoZ agents, should we scope to client_id (strict) or allow cross-client generic learnings (leaky)? Recommend: strict by default, optional cross-client for training data only.
4. **Fallback when cache misses / KB missing** — should we fall back to stateless, or block the call? Recommend: log + fall back (the Solon-style decision — keep shipping).

---

## 9. LINKS

- Task queue row: CT-0416-23
- Dependency closed: CT-0416-29 (`search_memory` fix) — ships 2026-04-17 02:45Z
- Grader stack: `lib/grader.py` (CT-0416-17/19 session)
- Encyclopedia v1.2: `library_of_alexandria/chamber-ai-advantage/CHAMBER_AI_ADVANTAGE_ENCYCLOPEDIA_v1_2.md`
- Voice corpus (MP-1 Loom): `plans/research/mp1-loom-voice-corpus-2026-04-12.md` (69,315 words)
- ElevenLabs voice map (CT-0415-17-v2): Solon voice = `DZifC2yzJiQrdYzF21KH`

---

## 10. CACHE-MISS + FAILURE MODE RISK MATRIX

| Failure mode | Detection | Mitigation | Blast radius |
|---|---|---|---|
| Anthropic cache miss (cold window) | `cache_read_input_tokens = 0` in response | Accept the $0.134 first-call cost; next 5 min amortize it | Cost bump, not correctness |
| KB reload race (mtime change mid-call) | `file_watcher` + in-memory version counter | Serve the PREVIOUS version for in-flight call, new version on next call | Zero correctness impact |
| `agent_context_loader` timeout (>500 ms p99) | Prometheus histogram on handler | Fall back to stateless call with banner `[context unavailable, degraded]` in output; alert Solon | 1 call per miss, degraded not broken |
| `client_facts` query slow / Supabase hiccup | 200 ms soft-timeout per Supabase call | Skip client_facts block, log warning, call still proceeds | Per-call quality dip, not outage |
| Grader ≥ old + 1.0 not met (A/B fails on Day 4) | Day 4 blocker | Do NOT cut over; escalate to Solon with failed samples + root-cause hypothesis (likely KB gaps) | Schedule slips by N days — that's OK per no-sandbag clause |
| KB file > 30 K tokens | `bin/kb-tokenize.sh` pre-commit hook blocks | Author trims KB; hard fail on commit | Zero — gate is pre-prod |
| Client asks something neither KB nor client_facts cover | `search_memory` returns empty + KB-RAG scores <0.3 | Agent says "let me check on that and circle back" + opens an intake ticket in `op_task_queue` with tag `agent_needs_kb_update` | Per-call — and gives us a signal to grow the KB |
| Rate-limit abuse (20 req / 5 min breached) | Loader middleware | Return cached 429 message in agent persona, log event | Per-client, not system-wide |

## 11. SECURITY NOTES

- **Client data isolation:** `agent_context_loader` hard-enforces `project_filter = client_id` on every `search_memory` call. No cross-client leakage.
- **KB auditability:** every KB file committed to harness repo with git blame → every change traceable to author + timestamp.
- **Trade-secret scrub:** `bin/tradesecret-scan.sh` runs BEFORE response is shown to subscriber. Confirmed compatible with the existing AMG response pipeline.
- **Supabase RLS:** `client_facts` table uses RLS with `USING (client_id = current_setting('app.current_client_id'))`. Service role bypasses for loader, but any direct client-context leak path is gated.
- **Secret hygiene in KB:** `00_identity.md` through `06_trade_secrets.md` MUST NOT contain API keys, JWT secrets, or subscriber PII. Pre-commit scan via `bin/secrets-scan.sh` (already running per §17 of CLAUDE.md).

## 12. EXPECTED OUTPUT EXAMPLE (Alex, signed-in as Levar)

**Query:** "My Instagram engagement has dropped 30% the last two weeks. What's going on?"

**Stateless call (today) would likely produce:**
> Instagram engagement drops can be caused by several factors, including algorithm changes, posting frequency, or content quality. I'd recommend reviewing your posting schedule, engaging with your audience, and experimenting with different content formats.

Generic. Could be any brand. Doesn't know Levar is a Lynn-MA real-estate operator.

**Project-backed call (target) would produce:**
> Two things to rule out first: your Reels cadence dropped from 4/wk to 1/wk over the last 14 days, and our last drone-footage post (the waterfront listing) outperformed your averages 3×. The algorithm is punishing the cadence drop more than the content. Options: (a) batch-film 6 Reels this weekend to clear two weeks of backlog, or (b) repurpose the waterfront drone cut into 3 vertical Reels — same asset, fresh frames. I'd queue both. Want me to hand the repurposing job to Maya this afternoon?

Ref-ing the account's actual cadence history (`client_facts.active_campaign`), the actual top-performing post (`search_memory` hit on prior conversation), the actual next step (handoff to Maya — agent roster awareness from KB). That's the quality delta.

## 13. GRADING BLOCK

**Round 1 (2026-04-17T02:43Z, gemini-2.5-pro, doctrine, amg_pro):**
- overall_score_10: **8.5** · confidence: 0.8 · decision: revise
- subscores: requirements_fit 9.0 · correctness 8.0 · risk_safety 8.5 · operability 8.0 · doctrine_compliance 9.0
- flagged revisions: timeline clarity, cache-miss risk detail, example outputs, dependency tracking, security
- **Addressed in this file (Round 2 pending):** §10 cache-miss/failure matrix, §11 security, §12 expected output example. Timeline (§5) already had per-day detail; dependency tracking already in §3.4.

**Next step:** re-grade on this revision; if ≥9.0, file is LOCKED as Day 1 deliverable and Day 2 (Alex KB build) begins.
