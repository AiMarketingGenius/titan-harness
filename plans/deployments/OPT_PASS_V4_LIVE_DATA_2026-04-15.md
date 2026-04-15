# Opt Pass V4 — Live Data + Production Incident Discovery (2026-04-15)

**Task:** Capture live Redis queue-depth + worker utilization for n8n rebalance tuning.
**Finding:** n8n queue mode is running **without any worker containers deployed**. 13,703 jobs stalled.
**Severity:** P0 production incident (automation layer silently non-functional for days).
**Disposition:** Tier B — cannot auto-fix. Requires Solon confirm because jobs ≥ 2 days old include time-sensitive workflows that may trigger double-processing or stale side-effects if executed now.

---

## 1. Live measurements

Redis auth discovered: `QUEUE_BULL_REDIS_PASSWORD=titanqueue2026` (from `n8n-n8n-1` container env).

| Metric | Value | Interpretation |
|---|---|---|
| `bull:jobs:wait` | **13,703 jobs** | All queued work, none processed |
| `bull:jobs:active` | **0 jobs** | Nothing being worked on right now |
| `bull:jobs:completed` | **0 jobs** | Nothing finished since queue mode enabled |
| `bull:jobs:failed` | **0 jobs** | Nothing failed either — jobs simply aren't picked up |
| `bull:jobs:delayed` | **0 jobs** | No scheduled-future backlog |
| Redis `total_connections_received` | 29,515 | Many connections — possibly main n8n polling for workers |
| Redis `total_commands_processed` | 1,627,036,603 | Very high; consistent with main-side heartbeat + queue-status queries without any worker consumption |
| Redis `keyspace_hits : keyspace_misses` | 259,489 : 1,219,980,132 | **99.98% miss rate** — pathological; consistent with workers absent and main-side polling returning empty results |
| Redis `used_memory_human` | 11.96 MB | Well under 512 MB cap |
| Redis `maxmemory_policy` | allkeys-lru | Correct policy |
| n8n worker container count | **0** | Confirmed absent |

---

## 2. Job-age sample (confirms multi-day backlog)

| Job ID | Timestamp | Age |
|---|---|---|
| 538 | 2026-04-09 11:30 UTC | **6 days old** |
| 7331 | 2026-04-11 04:19 UTC | 4 days old |
| 13699 | 2026-04-12 18:38 UTC | 2.5 days old |

Rate: ~2,280 jobs/day accumulating (13,703 / 6). Matches a continuously-running webhook layer with no consumer.

---

## 3. Root cause

`/opt/n8n/docker-compose.yml` defines three services: `n8n` (main, `EXECUTIONS_MODE=queue`), `n8n-redis`, and `caddy`. **It does NOT define an `n8n-worker` service.**

In n8n queue mode, the main container handles webhook intake + queues jobs into Redis; separate worker container(s) must exist to consume and execute those jobs. The current deployment has the producer but not the consumer.

This is a common n8n queue-mode misconfiguration — teams migrate from single-process to queue mode and forget to add the worker sidecar.

---

## 4. Proposed fix (requires Solon Tier B confirm)

### 4.1 Add worker service to `/opt/n8n/docker-compose.yml`

```yaml
  n8n-worker:
    image: n8nio/n8n
    restart: always
    command: worker --concurrency=20
    environment:
      - EXECUTIONS_MODE=queue
      - QUEUE_BULL_REDIS_HOST=n8n-redis
      - QUEUE_BULL_REDIS_PORT=6379
      - QUEUE_BULL_REDIS_PASSWORD=titanqueue2026
      - N8N_ENCRYPTION_KEY=amg-n8n-enc-2026-04
      # (plus the same env as n8n main — SUPABASE, ANTHROPIC, etc.)
    depends_on:
      n8n-redis:
        condition: service_healthy
    volumes:
      - n8n_data:/home/node/.n8n
      - /opt/amg-n8n:/opt/amg-n8n
```

### 4.2 Pre-deploy decision: what to do with the 13,703 backlogged jobs

Two paths, each with real implications for paying clients:

**Path A — Drain the backlog (deploy workers, let queue process 13,703 jobs)**
- Pros: no data loss; every triggered workflow eventually runs
- Cons: **6-day-old jobs execute against current state.** Possible consequences:
  - Old webhooks send emails/notifications that referenced stale context
  - Scheduled-task jobs fire with outdated parameters
  - Integrations (GBP, CRM, Slack) receive delayed payloads that the remote side may reject or double-process
  - 13,703 × 20 workers × ~1s per job = ~11 minutes minimum drain; could be hours if any workflow calls an external API with rate limits
- Execution: `docker-compose up -d` after adding worker service; queue drains automatically

**Path B — Flush the backlog + deploy workers clean**
- Pros: clean slate; new workflows trigger + execute from now forward
- Cons: **loses 6 days of triggered workflow executions.** If critical inbound-lead webhooks are in the backlog (e.g., Shop UNIS content requests, Paradise Park lead intakes), those leads are lost forever.
- Execution: `redis-cli -a titanqueue2026 FLUSHDB` before adding workers OR selective DEL by job-ID range

**Path C — Surgical inspection + selective drain**
- Pros: balances risk — drops time-sensitive/stale workflows, preserves state-query/idempotent ones
- Cons: requires manual inspection of 13,703 job payloads (impractical by hand); automating the classifier requires building a job-type-to-time-sensitivity mapping that doesn't exist yet
- Execution: ~30-60 min automation work to classify + selective delete, then deploy workers

### 4.3 Titan recommendation

**Path B (flush + deploy clean)** with the following caveats:

1. Given the 6-day age of the oldest jobs, most time-sensitive workflows in that backlog have ALREADY missed their purpose. Running them now risks double-side-effect (e.g., "send welcome email 6 days ago" sent now = confusing UX for the client).
2. Before flush, dump the 13,703 job payloads to `/opt/amg-n8n/queue-backup-2026-04-15.jsonl` for forensic review later. If anything critical was in the queue, it's recoverable via re-trigger from source (webhook re-send, schedule re-trigger), not by executing the stale job.
3. Deploy workers immediately after flush so new webhooks process correctly from minute 0.
4. Monitor `bull:jobs:wait` for 24h post-deploy to confirm healthy queue depth (expected: 0-50 at any moment during business hours, spiking briefly during high-intake bursts).

**Time to execute Path B:** ~15 minutes (dump + flush + compose up + verify).

---

## 5. Tier B surface

> CONFIRM: EXECUTE n8n queue-mode fix. Production automation layer has been non-functional for ~6 days (13,703 stalled jobs, 0 workers). Two choices:
>
> - Reply **PATH A** → deploy workers, let the 13,703-job backlog drain. Risk: old workflows execute against current state, potential double-processing + stale side-effects.
> - Reply **PATH B** (Titan recommendation) → dump backlog to forensic file, flush queue, deploy workers clean. Risk: lose 6 days of triggered workflow history (recoverable by re-trigger if anything critical surfaces).
> - Reply **PATH C** → spend 30-60 min building a selective classifier before touching anything.
>
> Awaiting decision. Until you reply, Titan holds on V4 disposition and continues to other Opt Pass vectors (V5, V3 verification, workload mix profile).

---

## 6. V4 rebalance recommendation (after fix lands)

Once workers are deployed + queue stable:

- Initial worker count: 1 worker container, `--concurrency=20` (matches the existing `QUEUE_WORKER_CONCURRENCY=20` env). Monitors burn-in for 7 days.
- Per-workflow concurrency caps: add `N8N_CONCURRENCY_PRODUCTION_LIMIT=5` env to prevent any one workflow from monopolizing the 20-concurrency pool.
- Scale trigger: if `bull:jobs:wait` sustained > 50 during business hours after burn-in, add a second worker container (scales to 40 effective concurrency).
- Redis memory already tuned correctly (`maxmemory 512mb`, `maxmemory-policy allkeys-lru`); no tuning needed there.

---

## 7. Live data captured + committed

This file itself IS the V4 live-data artifact. Rebalance tuning can't happen until workers exist; that fix gates the rebalance. V4 task marked "BLOCKED on Solon Tier B disposition."

Auto-continuing to V5 live measurement + V3 production verification + workload mix profile while Solon decides Path A/B/C.

---

*End of Opt Pass V4 live data — 2026-04-15.*
