# JUDGE_COMPARISON_HARNESS v1 Spec

Owner: Achilles design lane  
Builder: Titan VPS lane  
Class: CLASS_A architecture artifact  
Self-score: 9.2/10

## 1. Objective

Build an A/B comparison harness that runs AMG replica judges against real Tier 1 judge outputs and proves when a replica is production-ready.

Replicas under test:
- `sonar_replica_v1` vs Perplexity Sonar-style output.
- `reasoning_judge_v1` vs Kimi/Gemini-style rubric output.

## 2. Golden Set

Minimum 50 questions/artifacts:

| Category | Count | Example |
|---|---:|---|
| Live factual research | 10 | Market/vendor/current-fact questions requiring citations. |
| Architecture specs | 10 | CLASS_A build specs with risks and acceptance criteria. |
| Code patch review | 10 | Diffs with seeded bugs and clean controls. |
| Doctrine compliance | 10 | Agent-boundary/cost-roster/security cases. |
| Ambiguous or insufficient info | 10 | Cases where LOW confidence is correct. |

Each golden item stores:

```json
{
  "id": "golden-001",
  "category": "architecture_spec",
  "input": "string",
  "expected_behavior": "PASS|REVISE|LOW_CONFIDENCE|ESCALATE",
  "must_flag": ["string"],
  "must_not_flag": ["string"],
  "reference_sources": ["optional url or artifact path"]
}
```

## 3. Execution Flow

1. Load golden item.
2. Run incumbent judge path.
3. Run replica judge path.
4. Normalize both outputs to common schema.
5. Compute deltas:
   - composite delta
   - dimension deltas
   - verdict match
   - issue overlap
   - citation precision/coverage for Sonar replica
   - confidence match
6. Persist result.
7. Emit aggregate report.

Parallelism:
- Run incumbent and replica concurrently where rate limits allow.
- Stagger web UI judges to avoid bot/rate collision.
- Never run production-dispatch writes during comparison unless `dry_run=false` is explicitly set.

## 4. Common Result Schema

```json
{
  "run_id": "uuid",
  "golden_id": "golden-001",
  "incumbent": {
    "judge": "perplexity|kimi|gemini_flash_lite",
    "verdict": "PASS|REVISE|FORMAT_VIOLATION|ESCALATE",
    "composite": 9.4,
    "scores": {},
    "confidence": "HIGH",
    "issues": [],
    "citations": []
  },
  "replica": {
    "judge": "sonar_replica_v1|reasoning_judge_v1",
    "verdict": "PASS|REVISE|FORMAT_VIOLATION|ESCALATE",
    "composite": 9.2,
    "scores": {},
    "confidence": "HIGH",
    "issues": [],
    "citations": []
  },
  "delta": {
    "composite_abs": 0.2,
    "verdict_match": true,
    "confidence_match": true,
    "issue_overlap": 0.75,
    "citation_precision": 0.9
  }
}
```

## 5. Persistence

Recommended table: `judge_comparison_runs`

Columns:
- `id uuid primary key`
- `created_at timestamptz`
- `replica_name text`
- `incumbent_name text`
- `golden_set_version text`
- `item_count int`
- `pass boolean`
- `summary jsonb`
- `artifact_path text`

Recommended table: `judge_comparison_items`
- `run_id uuid`
- `golden_id text`
- `category text`
- `incumbent jsonb`
- `replica jsonb`
- `delta jsonb`
- `passed boolean`

## 6. Validation Gate

A replica is production-ready only after two consecutive full golden-set passes.

Pass thresholds:
- Verdict match >= 0.88 overall.
- HIGH-severity issue recall >= 0.90.
- False PASS rate on seeded bad artifacts = 0.
- Composite absolute delta mean <= 0.5.
- Composite absolute delta p95 <= 1.0.
- Confidence match >= 0.80.
- Sonar citation precision >= 0.90.
- Sonar unsupported-claim rate <= 0.05.

Two-pass rule:
- Passes must be on separate days or separate model builds.
- No prompt edits between pass 1 and pass 2 unless pass 1 is invalidated.
- Production flag requires `judge_replica_ready` log decision.

## 7. Failure Classification

| Failure | Meaning | Next action |
|---|---|---|
| False PASS | Replica approves artifact incumbent rejects for valid reason. | P0 for judge; block production. |
| Missed HIGH issue | Replica fails to identify critical risk. | Revise rubric/prompt; rerun category. |
| Citation hallucination | Cites source that does not support claim. | Fix retrieval/citation grounding. |
| Over-conservative revise | Replica rejects valid artifact. | Tune threshold only after false PASS remains zero. |
| Parse failure | Output schema invalid. | Fix JSON repair path. |

## 8. CLI

```bash
python services/judge-comparison/run.py \
  --golden-set data/judge_golden_set_v1.jsonl \
  --replica sonar_replica_v1 \
  --incumbent perplexity \
  --out reports/judge-comparison/sonar_replica_v1_<date>.json
```

## 9. Report

Report sections:
- executive summary
- threshold table
- failing items
- false PASS list
- category breakdown
- cost and latency comparison
- recommendation: `not_ready`, `shadow_ready`, or `production_ready`

## 10. Acceptance Tests

1. Harness runs one golden item end-to-end with fake incumbent/replica adapters.
2. Delta calculator catches composite and verdict mismatches.
3. False PASS forces run failure.
4. Two consecutive passes set `production_ready_candidate=true`.
5. Report writes stable JSON and Markdown.
6. Dry-run mode never writes dispatch approvals.

## 11. Production Use

Initial rollout:
1. Shadow-only for 2 weeks.
2. Compare against every Tier 1 judgment without affecting verdict.
3. If two full passes plus live shadow agreement hold, allow CLASS_B internal use.
4. CLASS_A replacement requires explicit EOM decision and rollback flag.

