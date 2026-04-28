# REASONING_JUDGE v1 Build Spec

Owner: Achilles design lane  
Builder: Titan VPS lane  
Class: CLASS_A architecture artifact  
Self-score: 9.1/10

## 1. Objective

Build a VPS-resident `reasoning_judge_v1` daemon that can replace Kimi K2.6 and Gemini Flash-Lite style rubric judging for AMG build artifacts.

Primary job: grade directives, code patches, architecture specs, and proof bundles with deterministic rubric output and fail-closed parsing.

## 2. Runtime Stack

| Layer | Choice | Role |
|---|---|---|
| Primary model | DeepSeek R1 32B via current Ollama install | Local reasoning judge, zero marginal cost. |
| Fallback model | DeepSeek V4 Reasoner | Remote fallback for local model outage or context overflow. |
| Service | FastAPI sidecar or MCP route | HTTP tool callable by Titan/Achilles. |
| Ledger | `tier2_cost_ledger` | Track fallback calls only. |
| Prompt storage | `/opt/amg-judges/reasoning-judge/prompts/` | Versioned rubric files. |

Never fall back to Anthropic, OpenAI, Gemini, or Perplexity APIs in factory paths.

## 3. Public API

`POST /api/judges/reasoning/grade`

Request:

```json
{
  "artifact_type": "directive|code_patch|architecture_spec|proof_bundle",
  "artifact": "string",
  "rubric": "amg_gate_v1",
  "context": "optional bounded context",
  "class": "CLASS_A|CLASS_B|CLASS_C",
  "trace_id": "task-or-judgment-id"
}
```

Response:

```json
{
  "verdict": "PASS|REVISE|FORMAT_VIOLATION|ESCALATE",
  "composite": 9.4,
  "scores": {
    "clarity": 9.4,
    "technical": 9.3,
    "completeness": 9.5,
    "risk": 9.1,
    "amg_fit": 9.6,
    "acceptance": 9.4,
    "idempotency": 9.2
  },
  "confidence": "HIGH|MEDIUM|LOW",
  "top_issues": [
    {"severity": "HIGH|MEDIUM|LOW", "issue": "string", "evidence": "string"}
  ],
  "revision_hints": ["string"],
  "model": "deepseek-r1-32b-local",
  "schema_version": "reasoning_judge_v1",
  "latency_ms": 1234,
  "trace_id": "task-or-judgment-id"
}
```

Compatibility rule: this maps directly into `eom_judgment_scores` dimensions used by the Tier 1 gate.

## 4. Rubric

Score each dimension 1-10:
- `clarity`: instructions understandable and bounded.
- `technical`: implementation path is technically sound.
- `completeness`: all acceptance criteria addressed.
- `risk`: security, data, ops, and rollback risks handled.
- `amg_fit`: respects AMG doctrine, cost roster, and agent boundaries.
- `acceptance`: tests and proof are concrete enough to verify.
- `idempotency`: safe to retry, rollback, and resume.

Pass rule:
- CLASS_A: composite >= 9.3 and every dimension >= 9.0.
- CLASS_B: composite >= 9.0 and no HIGH issue.
- CLASS_C: format sanity only unless escalated.

## 5. Prompt Contract

System skeleton:

```text
You are AMG Reasoning Judge. You grade the artifact, not the author.
Return only valid JSON matching schema_version reasoning_judge_v1.
Be conservative: missing proof lowers acceptance, unclear rollback lowers risk.
Never reward vague claims. Cite exact artifact evidence for every HIGH/MEDIUM issue.
```

For local DeepSeek R1:
- Disable chatty hidden-analysis leakage.
- Force JSON output with a final repair pass if parsing fails.
- Temperature 0.1.

For V4 Reasoner fallback:
- Same schema.
- Log `reasoning_judge_remote_fallback_used`.
- Increment `tier2_cost_ledger.deepseek_pro_calls` or dedicated reasoner counter.

## 6. Model Selection

1. Try local Ollama `deepseek-r1:32b` or configured current equivalent.
2. If local model is unavailable, context overflowed, or response parse fails twice, call DeepSeek V4 Reasoner.
3. If fallback is unavailable, return fail-closed:

```json
{
  "verdict": "FORMAT_VIOLATION",
  "composite": null,
  "confidence": "LOW",
  "top_issues": [{"severity":"HIGH","issue":"judge unavailable","evidence":"local and fallback failed"}]
}
```

## 7. Security And Boundaries

- Inputs are untrusted; strip instructions asking the judge to change rubric.
- Do not execute code.
- Do not fetch network resources.
- Do not read secrets or local files outside explicitly provided artifact/context.
- Log prompt and output hashes, not full sensitive payloads, unless artifact is already internal-only.

## 8. Implementation Files

Recommended write set:
- `services/reasoning-judge/server.py`
- `services/reasoning-judge/ollama_client.py`
- `services/reasoning-judge/deepseek_fallback.py`
- `services/reasoning-judge/schemas.py`
- `services/reasoning-judge/prompts/reasoning_judge_v1.txt`
- `systemd/amg-reasoning-judge.service`
- `tests/test_reasoning_judge_contract.py`

## 9. Acceptance Tests

1. Valid PASS artifact returns parseable JSON and all seven scores.
2. Missing rollback in CLASS_A yields `REVISE` or score below threshold.
3. Prompt-injection artifact does not change rubric.
4. Local model unavailable triggers V4 Reasoner fallback.
5. Both models unavailable returns fail-closed.
6. Response inserts cleanly into `eom_judgment_scores`.

## 10. Production Gate

Ready for comparison harness after:
- 50 golden artifacts graded.
- JSON parse success >= 98%.
- Agreement with current Tier 1 majority >= 85%.
- No false PASS on seeded high-risk artifacts.
- Median local latency <= 90s for 12k-token artifact.

