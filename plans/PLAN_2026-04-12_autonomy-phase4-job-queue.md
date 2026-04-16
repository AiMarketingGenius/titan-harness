# PLAN — Autonomy Phase 4: Scheduling & Queue (Week 4-5)

**Task ID:** CT-0412-06
**Status:** DRAFT — self-graded 9.41/10 A PENDING_ARISTOTLE
**Source of truth:** `plans/DR_TITAN_AUTONOMY_BLUEPRINT.md` Implementation Sequence Phase 4 + §5 OS Scheduling
**Phase:** 4 of 5
**Depends on:** Phase 1 (Infisical for worker secrets injection)
**Duration per blueprint:** Week 4-5

---

## 1. Canonical phase content (verbatim from DR Implementation Sequence)

> ### Phase 4 — Scheduling & Queue (Week 4–5)
> 1. Convert night-grind script to systemd timer with `Persistent=true`
> 2. Deploy BullMQ + Redis, migrate RADAR to BullMQ with priority tiers
> 3. Set up `titan-urgent`, `titan-harvest`, `titan-background` separate worker pools
> 4. Install supervisord wrapping for all long-running Titan daemons

---

## 2. Intent

Replace the current Mac-cron-style scheduling (bin/titan-hourly-drain.sh + bin/titan-night-grind.sh from the Never-Stop directive commit `8a9006a`) with production-grade systemd timers + a Redis-backed BullMQ job queue. Separate worker pools for urgent vs harvest vs background work. supervisord keeps long-running daemons alive across crashes.

Per blueprint §5: *"Prefer systemd timers over raw cron for all VPS jobs ... BullMQ is the correct choice over raw cron or Celery."*

## 3. Note on canonical BullMQ vs Python-first harness

The canonical blueprint says BullMQ "Native TypeScript (matches Titan's stack)." The current `titan-harness` is Python-first (`lib/llm_client.py`, `lib/war_room.py`, `titan-queue-watcher.py`, etc.). This is a reality check the blueprint author didn't have.

**Per Solon's directive** ("treat the blueprint I pasted as the only source of truth"), Titan honors BullMQ as the canonical choice. The integration pattern:

- **BullMQ producers can be Python:** there are community Python BullMQ clients (or Titan calls the Redis commands directly — BullMQ is just a Redis protocol)
- **BullMQ workers can be Node.js OR Python:** the canonical blueprint shows TypeScript workers, but Titan will ship a Python worker adapter that consumes BullMQ jobs from Redis and executes them with existing Python code
- **Alternative:** if Solon prefers pure-Python during Phase 4 implementation, the drop-in is RQ (Redis Queue, Python-native) with the same Redis backend — zero migration cost to swap

**Titan's recommendation in chat at implementation time:** show Solon both options (BullMQ + Python adapter vs pure Python RQ) with a 1-min pros/cons so Solon picks before Titan commits to 1 week of integration work. Default to BullMQ per canonical unless Solon says otherwise.

## 4. Implementation steps (match canonical order 1→4)

### Step 4.1 — Convert night-grind script to systemd timer with `Persistent=true` [~30 min Titan]

Canonical systemd unit from blueprint §5:

```ini
# /etc/systemd/system/titan-harvest.service
[Unit]
Description=Titan Nightly Harvest — MP-1 Pipeline
After=network-online.target postgresql.service
Requires=network-online.target

[Service]
Type=oneshot
User=titan
WorkingDirectory=/opt/titan-harness
EnvironmentFile=/etc/titan.env
ExecStartPre=/opt/infisical/bin/infisical run -- echo "secrets loaded"
ExecStart=/usr/bin/python3 /opt/titan-harness/harvest.py --pipeline MP-1
TimeoutStartSec=3600
MemoryMax=32G
CPUQuota=800%
StandardOutput=append:/var/log/titan/harvest.log
StandardError=append:/var/log/titan/harvest-error.log
Restart=on-failure
RestartSec=300

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/titan-harvest.timer
[Unit]
Description=Run Titan Harvest nightly 01:00–05:00 Boston

[Timer]
OnCalendar=*-*-* 01:00:00 America/New_York
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

Enable: `sudo systemctl enable --now titan-harvest.timer`

**Migration from current scheduler:**
- Keep `bin/titan-hourly-drain.sh` (still useful for hourly drains) but wrap it in a systemd unit + timer
- Retire `bin/titan-night-grind.sh` in favor of `titan-harvest.timer` (canonical pattern)
- Update `policy.yaml scheduler:` block to reflect systemd-timer-based scheduling
- All timer units have `Persistent=true` so missed runs catch up on boot

### Step 4.2 — Deploy BullMQ + Redis, migrate RADAR to BullMQ with priority tiers [~4 hours Titan]

1. **Install Redis** on VPS (may already be present): `sudo apt-get install redis-server && sudo systemctl enable --now redis-server`
2. Configure Redis: `bind 127.0.0.1`, password in Infisical, AOF persistence every 1 second
3. **Install BullMQ:** `npm install bullmq` in a new `/opt/titan-harness/bullmq-workers/` directory (TypeScript)
4. **OR (Titan recommends presenting this option):** `pip install rq rq-scheduler` for Python-native
5. Implement canonical queue topology from blueprint §5:
   - `titan-radar` queue with priorities (1 = highest, 4 = lowest)
   - `defaultJobOptions`: 3 attempts, exponential backoff, removeOnComplete after 500 jobs or 24h
   - Rate limiter: 20 jobs/min cap to protect vendor APIs

Canonical BullMQ producer pattern from blueprint:

```typescript
import { Queue, Worker, FlowProducer } from 'bullmq';
const connection = { host: 'localhost', port: 6379 };

const radarQueue = new Queue('titan-radar', {
  connection,
  defaultJobOptions: {
    attempts: 3,
    backoff: { type: 'exponential', delay: 30000 },
    removeOnComplete: { count: 500, age: 86400 },
    removeOnFailed: { count: 100 },
  }
});

await radarQueue.add('harvest-campaign-data',
  { client: 'acme', pipeline: 'MP-1' },
  { priority: 1 }  // lower = higher priority
);
```

Job priority schema (canonical blueprint §5):
- **P1** (immediate, < 1hr): Client deliverable deadlines, proposal sends, billing events
- **P2** (same night): Campaign data harvests, outbound sequences, reporting runs
- **P3** (this weekend): Research synthesis, library catalog updates, VPS maintenance
- **P4** (low, when idle): Background enrichment, historical data fills, archive tasks

### Step 4.3 — Set up `titan-urgent`, `titan-harvest`, `titan-background` separate worker pools [~2 hours Titan]

Canonical rule from blueprint §5: *"Never let P3/P4 jobs block the queue. Use separate BullMQ queues with separate worker pools."*

Three queues, three worker pools:
- **titan-urgent** — P1 work only. 4 concurrent workers. Rate limit: unlimited.
- **titan-harvest** — P2 harvest work. 3 concurrent workers. Rate limit: 20/min (vendor API safety).
- **titan-background** — P3/P4. 2 concurrent workers. Rate limit: 10/min.

Each worker is a systemd service:
```
titan-worker-urgent@{1,2,3,4}.service
titan-worker-harvest@{1,2,3}.service
titan-worker-background@{1,2}.service
```

Total: 9 worker processes. Each uses ~200MB RAM. Total RAM: ~1.8GB (well within 64GB VPS).

### Step 4.4 — Install supervisord wrapping for all long-running Titan daemons [~1 hour Titan]

Canonical supervisord config from blueprint §5:

```ini
# /etc/supervisor/conf.d/titan-worker.conf
[program:titan-worker]
command=/usr/bin/node /opt/titan-harness/dist/worker.js
directory=/opt/titan-harness
user=titan
autostart=true
autorestart=true
startsecs=5
stopwaitsecs=30
stderr_logfile=/var/log/titan/worker-error.log
stdout_logfile=/var/log/titan/worker.log
environment=NODE_ENV="production",INFISICAL_TOKEN="%(ENV_INFISICAL_TOKEN)s"
```

**Titan implementation:**
- Install: `sudo apt-get install supervisor`
- Write supervisord conf files for each Titan worker pool
- Reload: `sudo supervisorctl reread && sudo supervisorctl update`
- Verify: `sudo supervisorctl status` shows all workers RUNNING

**Note:** systemd and supervisord can coexist. systemd for system-level services (redis, postgresql, titan-harvest.timer), supervisord for Node.js workers + Python daemons that need process keepalive with faster restart times than systemd's Restart=on-failure.

## 5. Blockers / Solon actions

| # | Action | Time | Where |
|---|---|---|---|
| 1 | Approve systemd unit specs before install | 5 min | Titan shows in chat |
| 2 | Pick BullMQ vs RQ (Conflict resolution) | 2 min | Titan shows 1-min pros/cons, Solon picks |
| 3 | Redis install approval (may conflict with existing services) | 2 min | Titan checks port 6379 free first |
| 4 | Approve supervisord introduction alongside systemd | 2 min | Justify: faster restarts for Node workers |

## 6. Rollback

- **systemd timers removable:** `sudo systemctl disable --now titan-harvest.timer`
- **BullMQ removable:** Redis keys can be flushed via `redis-cli FLUSHDB`
- **supervisord removable:** `sudo apt-get remove supervisor`
- **Full rollback:** existing `titan-queue-watcher.service` stays untouched during Phase 4 and continues running in parallel until Phase 4 is fully soaked

## 7. Grading block (self-grade, PENDING_ARISTOTLE)

| # | Dimension | Score /10 | Notes |
|---|---|---|---|
| 1 | Correctness | 9.4 | Matches canonical Phase 4 order 1→4 exactly; systemd + BullMQ + supervisord patterns verbatim |
| 2 | Completeness | 9.5 | 4 canonical steps + Python/TypeScript integration note + blockers + rollback |
| 3 | Honest scope | 9.5 | Python-first harness reality flagged; Solon decision point documented |
| 4 | Rollback availability | 9.4 | Each component removable; existing queue-watcher runs in parallel during soak |
| 5 | Fit with harness patterns | 9.3 | systemd + Infisical integration clean; supervisord is new pattern alongside systemd |
| 6 | Actionability | 9.4 | Each step has commands + time estimates |
| 7 | Risk coverage | 9.4 | Redis port conflict + Python/TypeScript mismatch + supervisord/systemd coexistence all addressed |
| 8 | Evidence quality | 9.5 | Canonical systemd units + BullMQ patterns quoted verbatim |
| 9 | Internal consistency | 9.4 | Depends on Phase 1 Infisical for worker secret injection |
| 10 | Ship-ready for production | 9.3 | ~1 week of implementation after Phase 1 Step 1.1 lands |
| **Overall** | | **9.41/10 A** | **PENDING_ARISTOTLE** |

---

## 8. Change log

| Date | Change |
|---|---|
| 2026-04-12 | Initial draft (v1, source-missing scaffold) |
| 2026-04-12 | REBUILT v2 from canonical blueprint. Matches Phase 4 order 1→4 exactly. Self-graded 9.41/10 A (up from v1 9.17 B+). |
