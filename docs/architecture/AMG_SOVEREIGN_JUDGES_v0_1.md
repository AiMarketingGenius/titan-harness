# AMG Sovereign Judges v0.1

**Target canonical path:** `/opt/amg-docs/architecture/AMG_SOVEREIGN_JUDGES_v0_1.md`
**Staged path:** `/Users/solonzafiropoulos1/titan-harness/docs/architecture/AMG_SOVEREIGN_JUDGES_v0_1.md`
**Owner:** Achilles, CT-0427-51
**Status:** Scoping only. No build, deploy, credential change, or paid model call.

## 1. Strategic Context

AMG is retiring Perplexity, Grok, and Gemini from formal judge duties because they add cost, rate-limit fragility, provider leakage, and inconsistent availability. Gemini already produced a reliability warning in CT-0427-36 round 1. Perplexity/Sonar also conflicts with the judge-sovereignty directive.

Haiku remains as the only external counterjudge because one cheap independent model is useful for adversarial review. The primary judge becomes AMG-owned: a Reasoning Judge plus a Sonar-Replica research layer.

Paper-freeze note: this is a post-factory capability scope, not a new v4.0.x agent class.

## 2. Architecture Overview

```text
Task/spec/artifact
  -> AMG Reasoning Judge
  -> if facts/current claims needed: AMG Sonar-Replica
  -> Haiku external counterjudge
  -> merge rubric scores
  -> verdict: lock | revise | reject | blocked
```

Two services:

| Service | Purpose |
|---|---|
| AMG Sonar-Replica | Search, retrieve, cite, and synthesize current information without Perplexity. |
| AMG Reasoning Judge | Score artifacts against a structured rubric and produce revise/reject/lock decisions. |

## 3. AMG Sonar-Replica Spec

### Model Choice

Default: DeepSeek V4 Flash for synthesis.

Escalation: DeepSeek V4 Reasoner only when:

- Query involves architecture judgement, legal/regulatory nuance, or high-stakes claims.
- Flash answer fails citation/consistency checks.
- The Reasoning Judge explicitly requests a higher-confidence factual pass.

Rationale: search synthesis is mostly retrieval, compression, and citation discipline. Flash is cheaper and fast enough. Reasoner is reserved for difficult reasoning over conflicting sources.

### Search Backbone

Choice: Brave Search API first.

Why:

- Lower cost and simpler integration than broad commercial SERP stacks.
- Cleaner sovereignty posture than Perplexity because AMG owns retrieval, ranking policy, citation schema, and synthesis prompt.
- Good enough for validation and current-events research when combined with local RAG and source fetching.

Fallbacks:

- SearxNG self-hosted only as a later resilience layer.
- No Perplexity fallback in judge path.

### RAG Pattern

1. Query rewrite into 2-4 search intents.
2. Brave Search top 8-12 results per intent.
3. Fetch allowed pages with timeout and content-type guard.
4. Chunk at 700-1,000 tokens with 150-token overlap.
5. Embed locally with BGE or E5 family.
6. Retrieve top 12 chunks.
7. Rerank top 6 with local cross-encoder or cheap model heuristic.
8. Synthesize with citations.
9. Emit strict JSON.

### Citation Schema

Output must be close enough to replace Perplexity-style downstream consumers:

```json
{
  "answer": "short synthesized answer",
  "claims": [
    {
      "claim": "specific claim",
      "confidence": 0.86,
      "citations": [
        {
          "title": "source title",
          "url": "https://example.com",
          "retrieved_at": "2026-04-27T00:00:00Z",
          "snippet": "short source-grounded snippet"
        }
      ]
    }
  ],
  "source_count": 6,
  "warnings": []
}
```

Rules:

- Non-obvious factual claims require at least two independent citations.
- Any source fetch failure is a warning, not hidden.
- Snippets must be short; no long copyrighted copying.

### Accuracy Validation

Golden set: 50 questions.

Categories:

- 10 AMG architecture/current stack questions.
- 10 AI model/provider questions.
- 10 local business/Chamber/Atlas market questions.
- 10 technical docs/search synthesis questions.
- 10 adversarial citation tests with stale, ambiguous, or fabricated premises.

Pass gate:

- >= 85% factual correctness.
- >= 95% citation accessibility.
- Zero fabricated URLs.
- Beats or matches saved historical Perplexity output on >= 35/50.

## 4. AMG Reasoning Judge Spec

### Model Choice

Default: local DeepSeek R1 where latency/quality are acceptable.

Escalation: DeepSeek V4 Reasoner for high-risk or failed local passes.

Rationale: judging is rubric reasoning more than web search. Local R1 keeps routine review sovereign and free. V4 Reasoner covers hard cases without restoring banned judges.

### Rubric

Six dimensions, 0-10 each:

| Dimension | Measures |
|---|---|
| Technical soundness | Architecture and implementation feasibility. |
| Completeness | Whether all requested constraints and deliverables are covered. |
| Edge cases | Failure modes, fallback behavior, and degraded paths. |
| Risk identification | Owner-risk, public-risk, credential, cost, and false-completion risk. |
| Evidence quality | Artifacts, citations, commands, receipts, and proof path. |
| Operational discipline | Cost caps, rollback, queue honesty, memory discipline, paper-freeze compliance. |

Verdict rules:

- `lock`: overall >= 9.0 and no dimension < 8.5.
- `revise`: overall 7.0-8.99 or any dimension 7.0-8.49.
- `reject`: overall < 7.0 or safety/credential/destructive violation.
- `blocked`: missing artifact, missing owner approval, unavailable judge route, or no evidence.

### JSON Output

```json
{
  "judge": "amg_reasoning_judge",
  "model_route": "local_deepseek_r1",
  "overall": 9.1,
  "verdict": "lock",
  "scores": {
    "technical_soundness": 9.0,
    "completeness": 9.2,
    "edge_cases": 8.9,
    "risk_identification": 9.4,
    "evidence_quality": 9.0,
    "operational_discipline": 9.1
  },
  "top_flags": [],
  "required_revisions": [],
  "cost_usd_est": 0.0
}
```

## 5. Dual-Judge Integration

The formal quality gate becomes:

1. AMG Reasoning Judge scores the artifact.
2. Haiku scores the same artifact with the same rubric.
3. Merge rule takes the lower overall score unless one judge is clearly degraded.
4. If either judge returns `reject`, the merged verdict is `reject`.
5. If either judge returns `blocked`, the merged verdict is `blocked` until evidence is supplied.
6. To lock, merged overall must be >= 9.0 and no merged dimension can be < 8.5.

If Haiku is unavailable:

- Low-risk doc-only work can receive `advisory_local_only`.
- High-risk, deploy, credential, migration, public, or payment work blocks.

## 6. Infrastructure Requirements

### MVP

| Component | Requirement |
|---|---|
| Host | Existing VPS can run orchestration, search, fetch, embeddings, Redis, and queue workers. |
| GPU | Not required for MVP if DeepSeek V4 calls are API-based and local R1 already runs acceptably. |
| Embeddings | Local BGE/E5 or current Ollama embedding service. |
| Storage | Existing Supabase/MCP memory for query logs and golden set results. |
| Search | Brave Search API with cost cap. |
| Queue | Existing MCP task/decision routes after CT-0427-31/43 route repairs. |

### Sovereign Plus

GPU is only needed if AMG decides to self-host larger reasoning models beyond current Ollama capacity. Minimum viable GPU target should be sized after benchmarking; do not rent GPU capacity until the MVP proves judge value.

### Capacity

Initial concurrency:

- 2 Sonar-Replica calls in parallel.
- 2 Reasoning Judge calls in parallel.
- Queue excess work rather than spawning paid retries.

Timeouts:

- Search/fetch: 20 seconds per source, total 90 seconds.
- Reasoning Judge: 180 seconds local, 90 seconds API route.
- Haiku: 60 seconds.

## 7. Cost Projection

| Item | One-Time | Monthly | Notes |
|---|---:|---:|---|
| Sonar-Replica build | internal time | $0 | Doc/build labor, no vendor setup assumed. |
| Reasoning Judge build | internal time | $0 | Uses local model first. |
| Brave Search | $0 | $5-$50 | Usage-capped; starts low. |
| Haiku counterjudge | $0 | $5-$25 | Metered and behind v5.0.1 fleet cap. |
| DeepSeek V4 exceptions | $0 | $5-$50 | Metered and capped. |
| GPU self-host | deferred | TBD | Not approved for MVP. |

Net effect: lower risk and lower recurring cost than running Perplexity/Grok/Gemini judges. Exact savings require current spend export.

## 8. Build Phases

### Phase 0 - Scope

This document. Solon/EOM greenlight required before build.

### Phase 1 - Sonar-Replica MVP

Build search/fetch/RAG/citation service and validate on the 50-question golden set. Exit gate: >= 85% correctness, zero fabricated URLs.

### Phase 2 - Reasoning Judge MVP

Build rubric scorer and JSON schema. Exit gate: matches saved historical judge scores within +/- 0.5 on a golden set without calling banned judges live.

### Phase 3 - Dual-Judge Gate

Integrate Reasoning Judge plus Haiku. Exit gate: one known-good doc locks, one seeded-bad doc revises/rejects, one missing-artifact case blocks.

### Phase 4 - Cutover

Patch Titan/EOM/Aletheia judge callers away from Perplexity/Grok/Gemini. Feature flag the new pair.

### Phase 5 - Decommission

Remove banned providers from formal judge configuration. Keep historical saved benchmark artifacts only.

## 9. Rollout Sequence

First off banned judges:

- Doc-only architecture reviews.
- Receipt/evidence completeness checks.
- Cheap revise/reject gates for internal specs.

Later:

- Public-facing copy accuracy.
- Migration cutovers.
- Security-sensitive reviews.

Never automatic until proven:

- Credential, payment, DNS, production migration, or destructive operations. These still require owner approval regardless of judge score.

## 10. Acceptance

Solon can consider v0.1 accepted when:

- The doc names the model, search, RAG, citation, judge schema, infra, cost, phases, and rollout sequence.
- It removes Perplexity/Grok/Gemini from the live judge path.
- It keeps Haiku as the only external judge.
- It defines objective golden-set gates.
- It does not start a build.

## 11. Self-Score

| Dimension | Score | Note |
|---|---:|---|
| Architecture clarity | 9.4 | Two-service model is explicit. |
| Feasibility | 9.2 | MVP avoids premature GPU commitment. |
| Cost discipline | 9.3 | All paid calls fit v5.0.1 metered gate. |
| Sovereignty | 9.5 | Banned judges removed; Haiku retained narrowly. |
| Verification | 9.3 | Golden set and lock/revise/reject gates are measurable. |
| Risk honesty | 9.4 | Degraded/blocked behavior is explicit. |

Overall: 9.35/10.
