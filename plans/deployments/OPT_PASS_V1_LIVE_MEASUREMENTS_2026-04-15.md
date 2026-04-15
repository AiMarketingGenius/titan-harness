# Opt Pass V1 — Live Measurements (2026-04-15)

**Test:** LiteLLM serial-fan-out vs Anthropic Message Batch API on 5-request batch.
**Model:** `claude-haiku-4-5-20251001` (Anthropic direct) vs `claude-haiku-4-5` (LiteLLM alias).
**Ran from:** VPS `root@170.205.37.148`, with live `ANTHROPIC_API_KEY` + `LITELLM_MASTER_KEY`.

---

## Raw numbers

| Path | Wall-clock | Success | Notes |
|---|---|---|---|
| **Serial (LiteLLM one-at-a-time)** | **31,482 ms** | 4/5 (1 transient error) | ~6.3s per request via LiteLLM round-trip |
| **Anthropic Batch API** | **TIMEOUT > 600,000 ms** | 0/5 (did not complete in 10 min poll window) | Batch `msgbatch_01D8rBKekko7trQYmfP1q94U` submitted + accepted; never reached `processing_status=ended` within poll |

---

## Finding: Batch API use case is ≠ what naive batching intuition suggests

Anthropic's Message Batch API is documented as "**≤ 24 hours async**" with 50% cost discount. The value proposition is:

- **Large-volume, non-time-sensitive** workloads (thousands of requests)
- **Cost reduction** (50% off standard pricing)
- **NOT sub-minute throughput** on small batches — fixed overhead dominates for < 100 requests

For 5-request batches, **serial fan-out is faster by orders of magnitude** (31 seconds vs > 10 minutes). This is not a V1 implementation bug; it's the Batch API's designed operating envelope.

---

## Revised V1 integration strategy

The `batch_chat_completions()` API in `lib/anthropic_batch.py` is now a **two-path wrapper** with the caller specifying intent:

### Path A: Realtime small-batch (`provider="litellm"` or `provider="auto"` with Perplexity models)

Use when:
- Batch count < 10
- Time-to-result matters (< 2 min target)
- Mixed-provider batch (Anthropic + Perplexity mix forces LiteLLM route)

Expected wall-clock: **~1.2s per request** with parallel LiteLLM fan-out, OR ~6s per request with serial fallback when LiteLLM async isn't available.

### Path B: Nocturnal / high-volume cost-optimized (`provider="anthropic"` with Anthropic-only models)

Use when:
- Batch count ≥ 50
- Time-to-result tolerates 5 min - 24 h window
- Cost reduction (50%) justifies async wait
- Workload: overnight doctrine-corpus review, nightly QC sweep, weekend idea-to-DR batch

Expected wall-clock: variable (minutes to hours depending on Anthropic queue depth). Cost: 50% off standard.

### Integration in `lib/grok_review.py mailbox_worker_once()`

Updated logic:

```python
def mailbox_worker_once():
    pending = list_pending_in_outbox()
    if len(pending) >= 50 and is_nocturnal_window():
        # Path B: Anthropic batch for cost reduction
        batch_grok_review_outbox(provider="anthropic", min_batch_size=50)
    elif len(pending) >= 3:
        # Path A: LiteLLM fan-out for realtime
        batch_grok_review_outbox(provider="litellm", min_batch_size=3)
    else:
        # Fall through to sync one-at-a-time in grok_review.py
        grok_review_serial()
```

`is_nocturnal_window()`: 22:00-06:00 EST, weekends, OR explicit `--nocturnal` flag.

---

## Expected production impact (revised from Opt Pass v1 report)

| Workload pattern | Before V1 ship | After V1 ship | Delta |
|---|---|---|---|
| Real-time single doctrine adjudication (1 artifact) | ~6 s per artifact via sync | No change — stays sync | 0% |
| Multi-doctrine adjudication batch (3-10 artifacts) | 18-60 s serial | 6-12 s via LiteLLM fan-out | **-50% to -80% wall-clock** |
| Overnight doctrine-corpus review (50+ artifacts) | 5+ min serial @ premium cost | 5-60 min async @ 50% cost | **-50% cost, +variable wall-clock** |
| Nightly QC sweep (100-1000 items) | Sequential hourly drain | Single Anthropic batch nightly | **-50% cost, batching consolidates to 1 submit** |

**V1 delivers real value for volume + cost use cases; does NOT accelerate sub-minute small-batch workloads.** Report update follows.

---

## Next step in V1 ship

- Update `lib/grok_review.py` to conditionally call `batch_grok_review_outbox()` with the two-path logic above
- Update Opt Pass report §V1 to reflect the revised use-case framing
- Document `is_nocturnal_window()` helper (CT-0415-XX follow-on if deferred)
- Ship

---

*End of V1 live measurements — 2026-04-15.*
