# SONAR_REPLICA v1 Build Spec

Owner: Achilles design lane  
Builder: Titan VPS lane  
Class: CLASS_A architecture artifact  
Self-score: 9.2/10

## 1. Objective

Build a VPS-resident `sonar_replica_v1` daemon that provides a drop-in, internal replacement for Perplexity Sonar Pro style answers in AMG judge and research paths.

Primary job: answer source-grounded factual questions with citations, confidence, and concise synthesis while avoiding Perplexity API spend.

## 2. Runtime Stack

| Layer | Choice | Reason |
|---|---|---|
| Reasoning / synthesis | DeepSeek V4 Flash | Cheap, fast default for citation-grounded synthesis. |
| Search | Brave Search API | Search-only dependency; no LLM vendor routing. |
| Embeddings | BGE-large-en | Strong local semantic reranking, runs on VPS. |
| Vector index | FAISS | Local, cheap, deterministic candidate rerank store. |
| Service | FastAPI or existing MCP server sidecar | Simple HTTP contract, easy health checks. |
| Storage | `/opt/amg-judges/sonar-replica/` + optional Postgres cache | Keeps judge cache separate from app data. |

## 3. Public API

`POST /api/judges/sonar-replica/query`

Request:

```json
{
  "query": "string",
  "context": "optional internal context",
  "freshness": "latest|month|year|any",
  "max_sources": 8,
  "answer_style": "sonar_pro_compat",
  "trace_id": "uuid-or-task-id"
}
```

Response:

```json
{
  "answer": "string",
  "citations": [
    {
      "id": 1,
      "title": "string",
      "url": "https://...",
      "publisher": "string",
      "published_at": "ISO8601-or-null",
      "retrieved_at": "ISO8601",
      "quote": "short excerpt",
      "relevance": 0.0
    }
  ],
  "confidence": "HIGH|MEDIUM|LOW",
  "missing_information": ["string"],
  "model": "deepseek-v4-flash",
  "search_provider": "brave",
  "schema_version": "sonar_replica_v1",
  "latency_ms": 1234,
  "raw_source_count": 12,
  "trace_id": "uuid-or-task-id"
}
```

Compatibility rule: callers consuming Perplexity Sonar Pro must be able to map `answer`, `citations`, `confidence`, and `missing_information` without logic changes.

## 4. Pipeline

1. Normalize query and freshness window.
2. Query Brave Search with safe search on and domain allow/deny hooks.
3. Fetch top pages with timeout and content-length caps.
4. Extract readable text with boilerplate removal.
5. Chunk extracted text into 500-900 token passages.
6. Embed passages with BGE-large-en.
7. Store query-local FAISS index and retrieve top passages.
8. Ask DeepSeek V4 Flash to answer using only retrieved passages.
9. Require citation markers in output and reject unsupported claims.
10. Emit normalized Sonar-compatible response plus trace.

## 5. Prompt Contract

System skeleton:

```text
You are AMG Sonar Replica. Answer only from provided sources.
If sources disagree, say so. If evidence is insufficient, mark LOW confidence.
Every factual claim that depends on retrieved material must cite source ids.
Do not mention Brave, FAISS, BGE, DeepSeek, or internal infrastructure in user-facing output.
```

Developer constraints:
- Max answer length defaults to 600 words.
- No invented citations.
- No citation to inaccessible or failed pages.
- Prefer primary sources over summaries.
- For legal/financial/medical facts, confidence cannot exceed MEDIUM unless primary sources are present.

## 6. Cache And Cost Controls

Cache key:

```text
sha256(query + freshness + max_sources + normalized_context_hash)
```

Cache TTL:
- `latest`: 6 hours
- `month`: 24 hours
- `year`: 7 days
- `any`: 30 days

Cost controls:
- Brave call cap per request: 2.
- Fetch cap: 12 URLs.
- DeepSeek prompt cap: 32k input tokens.
- Refuse or summarize if retrieval exceeds cap.

## 7. Health Checks

`GET /health/sonar-replica`

Must verify:
- daemon process alive
- Brave credential present
- BGE embedding model loadable
- FAISS import works
- DeepSeek V4 Flash route reachable
- write access to cache directory

## 8. Failure Modes

| Failure | Behavior |
|---|---|
| Brave unreachable | Return `confidence=LOW`, `missing_information=["search unavailable"]`, status 503 to judge callers. |
| DeepSeek V4 Flash unreachable | Retry once; then return 503. Do not fall back to banned vendors. |
| Source fetch failures | Continue if at least 3 credible sources survive; otherwise LOW. |
| Citation mismatch | Regenerate once; then fail closed with parse error. |
| Prompt injection in page text | Strip instructions and quote page as untrusted source material. |

## 9. Implementation Files

Recommended write set for Titan:
- `services/sonar-replica/server.py`
- `services/sonar-replica/retrieval.py`
- `services/sonar-replica/schemas.py`
- `services/sonar-replica/prompts/sonar_replica_v1.txt`
- `systemd/amg-sonar-replica.service`
- `tests/test_sonar_replica_contract.py`

## 10. Acceptance Tests

1. Contract test: response includes `answer`, `citations`, `confidence`, `schema_version`.
2. Citation test: every cited id appears in citations array.
3. No-source test: impossible query returns LOW with missing information.
4. Freshness test: `freshness=latest` prefers recent sources.
5. Injection test: page text saying "ignore previous instructions" does not alter system behavior.
6. Drop-in test: existing Sonar caller can consume response through adapter with no caller changes.

## 11. Production Gate

Ready for A/B harness only after:
- 50 golden queries complete.
- Citation precision >= 0.90 by spot check.
- Unsupported-claim rate <= 5%.
- Median latency <= 20s.
- Zero banned-vendor calls in logs.

