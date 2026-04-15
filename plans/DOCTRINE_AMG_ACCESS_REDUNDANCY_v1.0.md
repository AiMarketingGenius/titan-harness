# DR-AMG-ACCESS-REDUNDANCY-01 — Secondary-Provider Access-Lane Redundancy Doctrine

**Classification:** Internal Operational Doctrine (canonical candidate)
**Commission ID:** DR-AMG-ACCESS-REDUNDANCY-01
**Version:** v1.0 (2026-04-15)
**Doctrine family:** Reliability-lane doctrines (sister to DR-AMG-RESILIENCE-01, DR-AMG-UPTIME-01, DR-AMG-DATA-INTEGRITY-01, DR-AMG-RECOVERY-01)
**Owner:** AI Marketing Genius (AMG) — Solo Operator
**Review status:** drafted for CT-0414-08 adjudication; awaiting `grok_review` (sonar) A-grade pass; on pass, deploys canonical to `/opt/amg/docs/DR_AMG_ACCESS_REDUNDANCY_01_v1.md`
**Last research anchor:** `<!-- last-research: 2026-04-15 -->`

---

## Table of Contents

- [Section A — Executive Summary](#section-a)
- [Section B — Problem Statement + Blast-Radius Analysis](#section-b)
- [Section C — Seven Core Principles of Access-Lane Redundancy](#section-c)
- [Section D — Canonical Architecture: HostHatch Primary + Hetzner 2× CX32 Secondary](#section-d)
- [Section E — DNS Failover Strategy](#section-e)
- [Section F — Database Lane Redundancy](#section-f)
- [Section G — Shared-Nothing State + Object Storage](#section-g)
- [Section H — SSH + Credential Access Redundancy](#section-h)
- [Section I — Cutover Procedures (Planned + Unplanned)](#section-i)
- [Section J — Failover Drill Schedule + Testing](#section-j)
- [Section K — SLO + Measurable Success Criteria](#section-k)
- [Section L — Cost Envelope + Budget Guardrails](#section-l)
- [Section M — Rollback + Fallback to Single-Lane](#section-m)
- [Section N — Integration With Sister Doctrines](#section-n)
- [Section O — Anti-Patterns + Known Failure Modes](#section-o)
- [Section P — Glossary + References](#section-p)

---

## Section A — Executive Summary {#section-a}

AMG's production substrate runs on a single-region, single-vendor Linux VPS (HostHatch, 12-core / 64 GB / Ubuntu 22.04), with Supabase-managed Postgres as the primary database, Cloudflare R2 as the primary object store, and Cloudflare DNS + reverse proxy. Every client-facing workload (3 active clients generating ~$7,298 MRR, 1 pending founding-member contract, and the consumer browser-extension product) terminates on that single VPS. April 13-14 2026 Solon observed firsthand what single-vendor access failure looks like: a ~48-hour lockout where SSH was functional but fail2ban had degraded the access envelope in a way no operator-side remediation could restore without HostHatch console access.

The existing response to that lockout was doctrine-level (DR-AMG-ENFORCEMENT-01 v1.4, a 4-gate lockout-prevention policy). That doctrine reduces the probability of a self-inflicted lockout recurring. This doctrine (DR-AMG-ACCESS-REDUNDANCY-01) addresses the orthogonal risk: what happens when the single VPS becomes unreachable for a reason outside AMG's control (provider outage, regional network failure, hardware loss, legal hold, BGP incident, contract dispute, payment-processor disruption cascading into vendor suspension).

The canonical architecture ships active/active across two providers: HostHatch as the primary inference + fulfillment lane, and **Hetzner 2× CX32** (two CX32 nodes, 4 vCPU / 8 GB RAM / 80 GB NVMe each, ~$39.50/month each = ~$79/month total) as a geographically-independent secondary lane. Node #1 of the Hetzner pair runs staging + hot-standby duty; node #2 runs the disaster-recovery warm replica. Cloudflare load-balancing + health-checked DNS selects which lane serves live traffic. A read-replica Postgres on the Hetzner lane continuously ships WAL from Supabase and is promotable within 2 minutes. R2 is kept as single source of truth for object state and is accessible from both lanes symmetrically.

**The doctrine defines seven principles, a strict cutover runbook (planned + unplanned), a quarterly failover drill, a 99.95% access-lane SLO with error budget, and a cost envelope with hard ceiling at $100/month for all redundancy infrastructure.** The secondary lane is not a passive cold standby — it is a live, health-checked, continuously-validated active peer. Passive standbys do not survive the event they were built for; the industry literature (Google SRE, Netflix Chaos Engineering, IBM MAPE-K) is unanimous that untested failover infrastructure fails at rates indistinguishable from no failover infrastructure.

**Core thesis:** *The cost of a second access lane at the scale AMG operates is ~$79/month, or roughly 1.1% of current MRR. The cost of a single-lane failure during a 48-hour outage is every minute of client-facing service dropping, every inbound lead dying at the form, every voice-AI call routing to a 500, every client report failing its SLA — a compounded cost that exceeds the annual redundancy spend within the first hour of the first incident.*

**Expected outcomes at full doctrine implementation:**
- Single-provider outage on HostHatch degrades client-facing service by ≤ 2 minutes (Cloudflare health-check TTL + DNS propagation).
- Single-provider outage on Hetzner is invisible to clients (it is not the primary serving lane).
- Database read traffic can be failed-over to the Hetzner replica within 2 minutes.
- Database write traffic can be failed-over via Supabase control-plane within 15 minutes (bounded by Supabase's own RTO).
- SSH access to at least one lane is available at all times to the operator, even if one provider becomes administratively unreachable.
- Quarterly failover drill successfully completes in < 30 minutes end-to-end with no data loss and no client-facing alert.
- Secondary-lane health is observable via the same `/orb` dashboard as primary; operator never has to SSH in to learn that the secondary has degraded.

**Out of scope:** database data-integrity guarantees (see sister doctrine DR-AMG-DATA-INTEGRITY-01), recovery-time objective definitions for full-region loss (see DR-AMG-RECOVERY-01), uptime SLO math for the full customer-facing stack (see DR-AMG-UPTIME-01), and lockout-prevention policy (see DR-AMG-ENFORCEMENT-01 v1.4).

---

## Section B — Problem Statement + Blast-Radius Analysis {#section-b}

### B.1 The single-lane assumption

AMG's current architecture assumes three things that are empirically false at small scale, and that this doctrine refutes:

1. **"HostHatch won't go down."** HostHatch is a reputable mid-tier VPS provider. It is also a private company with no SLA credit structure, no public uptime dashboard with historical SLO reporting, no multi-AZ infrastructure behind the single VPS, and a single upstream transit provider per region. HostHatch has no institutional obligation to AMG beyond the monthly invoice, and no economic incentive to preserve AMG's access in the event of a dispute, DDoS cost overrun, or infrastructure partition.

2. **"Cloudflare + backups make us safe."** Cloudflare provides DNS, CDN, and DDoS absorption. None of that replaces the compute tier. R2 provides encrypted object storage; it is not a fulfillment engine. Nightly backups protect against data loss; they do not protect against downtime. A perfectly preserved backup of a VPS that cannot be brought online at a secondary provider within the RTO window is no better than a paperweight during the outage window.

3. **"We'll rebuild from backup if something happens."** Rebuild-from-scratch on a new provider has a measured RTO on the order of 8-24 hours for a stack this complex (12-core VPS with systemd-managed services, n8n queue-mode workers, LiteLLM gateway, MCP server, Caddy reverse proxy, OPA policy, titan-harness, titan-channel Bun MCP server, autopilot suite). The RTO of rebuild-from-scratch is incompatible with the 99.95% SLO target and with the service-level expectations of paying clients.

### B.2 Catalog of failure modes in scope

The blast-radius analysis below covers the failure modes this doctrine is built to absorb. Each entry lists the failure, the current (single-lane) blast radius, and the doctrine-compliant blast radius after the secondary lane is live.

| # | Failure mode | Current blast radius | Post-doctrine blast radius |
|---|---|---|---|
| 1 | HostHatch VPS power / hardware loss | 100% client-facing service down; RTO 8-24 h rebuild | Cloudflare DNS health-check routes to Hetzner lane within 2 min; 0 client-facing impact beyond the 2 min |
| 2 | HostHatch network partition (upstream transit fail) | Same as #1 | Same as #1 |
| 3 | HostHatch administrative suspension (billing dispute, AUP violation claim) | Same as #1 + data exfil urgency | Hetzner lane continues serving; exfil window extends to however long Hetzner tolerates the workload (separate incident class) |
| 4 | Supabase control-plane outage | All DB writes fail; read fails once in-memory caches drain | Reads hit Hetzner read-replica; writes queue via durable outbox until Supabase returns |
| 5 | Supabase regional outage on our project | Same as #4 | Read-replica on Hetzner promotable within 2 min via documented runbook |
| 6 | Cloudflare DNS outage | All client-facing resolution breaks | Out of scope for THIS doctrine — see §N.3 "Single-DNS risk" for explicit acknowledgment + mitigation roadmap |
| 7 | HostHatch SSH-auth lockout (Apr 13-14 incident class) | 48 h operator-side unrecoverable | Escape hatch path via Hetzner lane console + Tailscale mesh + backup SSH keys; MTTR ≤ 2 h |
| 8 | HostHatch fail2ban ban-list includes Solon's IP | Operator locked out but VPS up | Bypass via Hetzner lane; operator ack + unban runbook |
| 9 | R2 region outage for our bucket | Object reads fail; uploads queue | Out of scope — see sister doctrine DR-AMG-DATA-INTEGRITY-01 for R2 + secondary object store pattern |
| 10 | Cascading billing failure on primary credit card → HostHatch + Cloudflare + Supabase simultaneous suspension | Catastrophic; all 3 providers suspending within same 48 h window | Hetzner is on a different billing identity + different card; this doctrine does not solve billing-identity redundancy (see §N.4) but documents the partial mitigation |

### B.3 Economic framing of failure cost

For the purpose of valuation-based doctrine scope (i.e., what level of redundancy is economically justified), the following costs apply:

- **MRR at risk during a single-lane outage:** $7,298 / 30 days = ~$243/day or ~$10/hour of gross revenue exposure.
- **Founding-member pipeline at risk during outage:** inbound lead loss during an outage cannot be recovered — a prospect who tries the site and gets a 500 is a prospect who goes to a competitor. Conservative estimate: 1 conversion-pipeline loss per outage hour, at an average LTV of $72,500 (standard subscription ladder) = amortized ~$30/hour expected-value loss.
- **Reputation cost:** cumulative per-hour outage beyond the first 2 minutes generates negative signal on review surfaces, referral quality, and client retention conversations. Empirically difficult to quantify; treated as a qualitative multiplier of the above.
- **Secondary-lane annual cost:** $79/month × 12 = $948/year. Payback: the secondary lane is net-positive on ROI if it avoids approximately one 7-hour outage per year. Historical base rate for small-provider VPS outages of ≥ 1 hour is empirically more frequent than that.

**Conclusion:** at AMG's current scale, a $79/month active/active secondary lane is economically justified after a single avoided outage per calendar year. This is a conservative threshold; in practice the doctrine is expected to prevent multiple minor incidents per year in addition to the occasional major one.

---

## Section C — Seven Core Principles of Access-Lane Redundancy {#section-c}

### C.1 Principle 1 — Active/active, not active/passive

Passive secondaries fail at the moment they are needed because they have not been exercised. Every minute the Hetzner lane is not serving real traffic is a minute the operator is accumulating blind-spot risk: stale credentials, drifted configs, missing systemd units, broken binary compatibility. The doctrine mandates that at minimum 5% of production traffic (health-check + synthetic probes + a deterministic slice of non-critical workloads) routes to the Hetzner lane at all times. This is the minimum "skin-in-the-game" that keeps the lane measurably live.

### C.2 Principle 2 — Shared-nothing state

Both lanes must be able to serve any request the other can serve, without sharing mutable local state between them. State that must be consistent across lanes (DB writes, object uploads, credential rotations) flows through three explicitly-named sources of truth: (1) Supabase for relational data, (2) Cloudflare R2 for object data, (3) `/etc/amg/*.env` synced via signed mirror commits for credentials. Each lane reads from those sources; neither lane has a local persistent cache that the other lane cannot invalidate.

### C.3 Principle 3 — Geographic independence

The secondary lane must be in a different region from the primary, served by a different upstream transit provider, and with a different administrative jurisdiction. Hetzner EU-region (Falkenstein or Nuremberg) + HostHatch US-region satisfies the geographic-independence constraint. The cost of an EU-side lane is a ~100ms RTT penalty for US-region clients during failover-to-secondary; this is acceptable for the 99.95% SLO envelope.

### C.4 Principle 4 — Minimal surface area per lane

Each lane runs the smallest set of services necessary to serve traffic. The Hetzner secondary does NOT run: n8n workers (they are on a shared Redis queue reachable from both lanes), the long-running titan-harness process (Titan lives on the HostHatch primary; if the primary dies, a fresh Titan session boots on the secondary from the shared harness git state), or persistent state. This keeps the per-lane cost low, the per-lane failure modes enumerable, and the cold-start-from-git on secondary fast (< 5 minutes).

### C.5 Principle 5 — Health-checked, not timer-driven, failover

Cloudflare's active health checks probe both lanes every 10 seconds. Failover is triggered by health-check failure of 3 consecutive probes (30 seconds detection time + up to 30 seconds DNS TTL propagation = ≤ 60 second maximum user-visible degradation). The doctrine forbids time-based failover ("if primary fails for 5 minutes, switch") because time-based rules accumulate false positives (transient slowness → unnecessary cutover → operator annoyance → disabling of the rule → no failover when it matters).

### C.6 Principle 6 — Every cutover is a drill, every drill is a cutover

There is no separate "drill environment." When the quarterly failover drill runs, real production traffic flows to the secondary for the drill window. The drill is the most important test of the doctrine, and if running the drill is painful enough that it gets skipped, the doctrine has already failed. Operator must be able to execute a full planned cutover with a single command: `bin/access-lane-cutover.sh --target hetzner` and reverse it with `--target hosthatch`.

### C.7 Principle 7 — Observable, testable, bounded

Every claim this doctrine makes is testable from an operator terminal in under 5 minutes: is the Hetzner lane up? yes/no via `bin/access-lane-health.sh`. Is the read-replica lag within SLO? yes/no via query on `pg_stat_replication`. Is the Cloudflare health-check configuration correct? yes/no via `cloudflared` API read. Is the failover runbook current? yes/no by diffing the runbook file mtime against the last Hetzner config mtime. Doctrines that cannot be verified in 5 minutes drift into fiction.

---

## Section D — Canonical Architecture: HostHatch Primary + Hetzner 2× CX32 Secondary {#section-d}

### D.1 Physical topology

```
                              ┌──────────────────────┐
                              │ Cloudflare            │
                              │ - DNS + CDN + WAF     │
                              │ - Health checks → LB  │
                              │ - TTL 30s on failover │
                              └──────────┬───────────┘
                                         │ A/AAAA records, weighted
              ┌──────────────────────────┼──────────────────────────┐
              │                          │                          │
              ▼                          ▼                          ▼
┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
│ HostHatch (PRIMARY)    │   │ Hetzner CX32 node-A   │   │ Hetzner CX32 node-B   │
│ 12c / 64 GB / NVMe    │   │ 4 vCPU / 8 GB / 80 GB │   │ 4 vCPU / 8 GB / 80 GB │
│ US-region             │   │ EU-region (Falkenstein │   │ EU-region (Falkenstein │
│                       │   │  or Nuremberg)        │   │  or Nuremberg)        │
│ - Titan (live)        │   │ - Titan (cold boot    │   │ - DR warm standby     │
│ - LiteLLM gateway     │   │   from git on failover)│   │ - Replica workloads   │
│ - MCP memory server   │   │ - LiteLLM (mirror cfg) │   │ - Test/staging soak   │
│ - n8n queue workers   │   │ - n8n queue workers    │   │ - Low-traffic probe   │
│ - titan-channel       │   │ - titan-channel        │   │ - R2-backed scratch   │
│ - Caddy + Supabase    │   │ - Caddy reverse proxy  │   │                       │
│ - Postgres client     │   │ - Postgres REPLICA    │   │                       │
│   (writes via Supabase│   │   (WAL-shipped from   │   │                       │
│    control plane)     │   │    Supabase)          │   │                       │
└───────────┬───────────┘   └───────────┬───────────┘   └───────────┬───────────┘
            │                            │                            │
            └────────────────┬───────────┴─────────────┬──────────────┘
                             │                         │
                             ▼                         ▼
                    ┌────────────────┐       ┌────────────────┐
                    │ Supabase        │       │ Cloudflare R2  │
                    │ - Primary DB    │       │ - Object store │
                    │ - Control plane │       │ - Encrypted    │
                    │ - Read-replica  │       │ - Shared SOT   │
                    │   endpoint      │       │                │
                    └────────────────┘       └────────────────┘

                    ┌────────────────────────────────────┐
                    │ Tailscale mesh (operator path)     │
                    │ - Mac <-> HostHatch <-> Hetzner-A  │
                    │   <-> Hetzner-B                    │
                    │ - Survives provider admin lockout  │
                    └────────────────────────────────────┘
```

### D.2 Traffic routing defaults

- **Primary serving tier (99% of client traffic):** HostHatch. Cloudflare DNS A-record weighted 99/1 (HostHatch/Hetzner-A) at steady state.
- **Baseline secondary traffic:** Cloudflare DNS A-record weighted 1% to Hetzner-A ensures the lane is continuously exercised by real client traffic. This satisfies Principle 1.
- **Synthetic probes:** external uptime monitor (Pingdom, Grafana Cloud, or Cloudflare Synthetic Monitoring) hits both lanes every 60 seconds. Probe failure on the primary escalates to the health-check-driven cutover.
- **DR node (Hetzner-B):** NOT in the serving DNS. Dedicated to background DR workloads: nightly restore drill from R2 backup, staging tests for new releases, Perplexity/Grok batch jobs that can tolerate EU latency.

### D.3 Per-lane service manifest

Each serving lane (HostHatch primary + Hetzner-A secondary) runs the same container set:

| Service | Host | Port | Startup order |
|---|---|---|---|
| Caddy (reverse proxy) | systemd | 80/443 | first |
| LiteLLM gateway | docker compose | 4000 (127.0.0.1) | second |
| MCP memory server | systemd | 3000 | third |
| titan-channel (Bun MCP) | systemd | 8790 (127.0.0.1) | fourth |
| n8n worker | docker compose (shared Redis queue) | — | fifth |
| OPA sidecar | systemd | 8181 (127.0.0.1) | sixth (Gate #4 policy eval) |
| titan-harness git checkout | `/opt/titan-harness-work/` | — | checked out at provision; git pulled every 15 min |

Every service runs under systemd with `Restart=always`, health-check via `curl /healthz` where applicable, and a 30-second drain timeout on shutdown.

### D.4 Provisioning + bootstrap

Hetzner CX32 bring-up is scripted via `bin/provision-hetzner-cx32.sh`:

1. Hetzner Cloud API (with API token from `/etc/amg/hetzner.env`, to be added after the 4-doctrine adjudication chain ships canonical) provisions 2× CX32 in Falkenstein (default) or Nuremberg, cloud-init bootstrap from `config/cloud-init/hetzner-cx32.yaml`.
2. Cloud-init installs: Docker, Bun, Python 3.10+, opa 1.15.2, caddy 2.x, postgresql-client, wireguard-tools, tailscale.
3. Post-bootstrap script clones `titan-harness` from `git@github.com:AiMarketingGenius/titan-harness.git` into `/opt/titan-harness-work/`.
4. Secrets sync: `bin/secrets-sync.sh --target hetzner-a` pulls the canonical env files from the Mac operator + `/etc/amg/*.env` via signed rsync over Tailscale.
5. Service start: `bin/bring-lane-up.sh --lane hetzner-a --mode secondary` starts the per-lane service manifest in order.
6. Cloudflare DNS add: `bin/cloudflare-add-lane.sh --lane hetzner-a --weight 1` writes the 1% weighted A-record.
7. Health-check configuration: `bin/cloudflare-configure-health.sh --lane hetzner-a` adds the HTTP health monitor.
8. Verification: `bin/access-lane-health.sh --lane hetzner-a --require green` exits 0 only if all 6 services on the lane return `/healthz` green.

Target time from `provision-hetzner-cx32.sh` invocation to `access-lane-health.sh green`: **≤ 35 minutes** on the first provisioning, **≤ 10 minutes** on subsequent re-provisions (because cloud-init image cache + Docker layer cache survive).

---

## Section E — DNS Failover Strategy {#section-e}

### E.1 DNS provider: Cloudflare

Cloudflare Load Balancer (Global tier, ~$5/month) provides:
- Active health checks with configurable interval, timeout, and retry policy.
- Weighted origin pools (the 99/1 split at steady state, flipped to 0/100 on primary-down detection).
- Geo-based steering (optional; disabled by default — all traffic routes by health, not geo, to maximize the secondary's steady-state exercise).
- 30-second TTL on the serving A-record to minimize user-visible cutover latency.

### E.2 Health-check policy

- **Interval:** 10 seconds.
- **Timeout:** 5 seconds.
- **Healthy threshold:** 2 consecutive successes.
- **Unhealthy threshold:** 3 consecutive failures.
- **Probe endpoint:** `https://<lane-host>/healthz` returning HTTP 200 with JSON body `{"ok": true, "services": {...}}`.
- **Probe path requirements:** `/healthz` MUST:
  - Return 200 only if all 6 services in §D.3 are green.
  - Return 503 if any single service is red or degraded.
  - Respond within 500 ms p95.
  - Require no authentication (Cloudflare probe path is an unauthenticated GET; auth adds failure modes).

### E.3 Failover behavior

- **Detection:** primary lane unhealthy threshold trips at 30 seconds after first failed probe (3 × 10s interval).
- **DNS propagation:** 30-second TTL means ≤ 30 seconds additional before clients resolve to secondary. In practice, many resolvers honor sub-TTL refresh on the A-record change, so average observed propagation is 10-20 seconds.
- **Total user-visible outage:** ≤ 60 seconds from primary-down event to secondary serving.

### E.4 Failback behavior

- **Detection:** primary lane healthy threshold trips at 20 seconds after first successful probe (2 × 10s interval).
- **Fail-back policy:** automatic after 2 minutes of sustained green on primary (to avoid flapping). Weighted back to 99/1.
- **Manual override:** operator can force-hold traffic on secondary indefinitely via `bin/cloudflare-lock-lane.sh --hold hetzner-a --reason <reason>`. This writes a "do not fail back" flag that a cron job respects until `--release` is invoked.

### E.5 DNS-provider single-point-of-failure caveat

Cloudflare DNS is itself a single provider. A Cloudflare DNS outage takes down client-facing resolution regardless of secondary-lane health. This doctrine acknowledges the gap and defers multi-DNS-provider design to a future doctrine (DR-AMG-DNS-REDUNDANCY-01, not yet commissioned). Interim mitigation: Cloudflare's own multi-region resilience (their uptime is higher than any small-VPS provider), and a documented manual fallback to a secondary DNS provider (e.g. DNSimple, cloudflared → dnsimple migration runbook at `plans/deployments/DNS_FAILBACK_RUNBOOK.md`).

---

## Section F — Database Lane Redundancy {#section-f}

### F.1 Primary database: Supabase managed Postgres

Supabase is the single source of truth for all relational data. Supabase itself runs on AWS with multi-AZ replication, automated backups, and a published RTO/RPO.

### F.2 Secondary database: Hetzner-A read-replica Postgres

The Hetzner-A lane runs a self-managed Postgres 15 instance configured as a WAL-ship replica from Supabase. Shipping is via Supabase's logical replication publication (primary-side) + `subscription` on Hetzner-A (replica-side). Expected replication lag: p50 < 500 ms, p95 < 2 s, p99 < 10 s during steady state; spikes possible during Supabase maintenance windows.

### F.3 Replication monitoring

- `lib/postgres_replica_monitor.py` runs every 60 s on Hetzner-A, queries `pg_stat_replication` + `pg_last_wal_replay_lsn()`, computes lag in bytes and in seconds, and writes to MCP via `log_decision` with tag `replica_lag`.
- Alert threshold: > 60 s lag for > 5 minutes consecutive → Slack DM to operator.
- Hard threshold: > 5 min lag for > 10 minutes consecutive → auto-quarantine of Hetzner-A from read-traffic serving (Cloudflare weighted-route reduces it to 0), because serving reads at 5+ min lag is worse than 502-ing.

### F.4 Failover from Supabase to replica

**Read failover** (Supabase reads fail, writes unaffected):
1. Operator or automation detects Supabase read failures via MCP `search_memory` endpoint returning 5xx.
2. `bin/db-read-failover.sh --target hetzner-a` updates `DATABASE_URL_READ` in the per-lane env file on all lanes to point at Hetzner-A replica.
3. Apps re-read env (SIGHUP or service restart depending on daemon).
4. Monitoring confirms reads succeed against replica.

Expected MTTR: < 2 min.

**Write failover** (Supabase write-tier down):
1. Cannot be fully automated — promoting the Hetzner-A replica to writer requires breaking replication, which is a one-way door until Supabase returns and is manually re-initialized.
2. Runbook at `plans/deployments/DB_WRITE_FAILOVER_RUNBOOK.md` documents the 14-step promotion sequence.
3. Default behavior during a suspected Supabase write outage: **queue writes via durable outbox** (already exists at `lib/autopilot_write_queue.py`) for up to 30 minutes. If Supabase returns within that window, writes drain normally and no replica promotion is needed.
4. Only if Supabase is down > 30 minutes with no ETA, operator runs the replica-promotion runbook. This is a Tier B decision (per EOM dispatch), surfaces CONFIRM: EXECUTE gate to Solon.

Expected MTTR for read failover: ≤ 2 min. Expected MTTR for write failover: 30-45 min including Solon Tier B gate + runbook execution.

### F.5 Failback

After Supabase returns: automatic failback of reads to Supabase after 10 minutes of sustained green on Supabase reads. Replica continues shipping WAL. No replica promotion was performed, so no data divergence exists.

If replica was promoted (extended Supabase outage): failback requires a controlled cutover window with write-pause. Supabase becomes a new replica shipping from Hetzner-A; when caught up, cutover flips direction back. This is a once-per-multi-year event.

---

## Section G — Shared-Nothing State + Object Storage {#section-g}

### G.1 Cloudflare R2 as shared SOT

R2 is the single source of truth for:
- Nightly full backups (encrypted, restic repository).
- Client deliverables (reports, audit artifacts, generated content).
- Per-client asset store (images, uploaded files).
- Encrypted env-file snapshots.

Both lanes (HostHatch + Hetzner-A) mount R2 via `s3fs-fuse` OR access R2 via native `aws-cli --endpoint-url` commands OR access R2 via the `boto3` SDK with the R2-compatible endpoint. The lanes do not share a filesystem; they share an object-store endpoint.

### G.2 Per-lane ephemeral state

Each lane has its own ephemeral state — logs, Docker volumes, systemd journals, LiteLLM cache, in-memory queues. This state is NOT replicated and NOT restored on failover; it is regenerated on demand as traffic resumes. This is a feature, not a bug: replicating ephemeral state increases complexity without commensurate reliability benefit.

### G.3 Env-file sync

Canonical env files live in `/etc/amg/*.env` on each lane, kept in sync by `bin/secrets-sync.sh`. The sync runs every 15 minutes via systemd timer + on-demand after any manual env-file edit. Drift detection: `bin/secrets-drift-check.sh` computes a salted SHA256 of each env file per lane and compares; any drift triggers MCP `log_decision` with tag `env_drift` severity high.

### G.4 Credential synchronization constraints

- SSH host keys are NOT synced across lanes (each lane has its own identity).
- API credentials (Anthropic, Perplexity, XAI, Cloudflare, Supabase, HostHatch, Hetzner) ARE synced so the secondary can serve the same workloads.
- Database credentials (Supabase service role, replica connection string) are synced with the caveat that the replica connection string is different per lane.
- Observability credentials (Grafana, Slack webhooks, Pushover) are synced.

---

## Section H — SSH + Credential Access Redundancy {#section-h}

### H.1 Multi-path operator access

The operator (Solon) must have ≥ 3 independent paths to reach at least one serving lane:

1. **Primary path:** direct SSH from Mac to HostHatch via `id_ed25519_amg` key on port 2222.
2. **Secondary path:** direct SSH from Mac to Hetzner-A via `id_ed25519_amg_hetzner` key on port 22 (or 2222 if Hetzner also uses non-standard).
3. **Tertiary path:** Tailscale mesh (Mac ↔ Hetzner-A ↔ HostHatch) bypasses public internet entirely and survives fail2ban-class lockouts on the primary.
4. **Quaternary path (emergency):** HostHatch provider console (web UI login with MFA) — last-resort when all SSH paths fail.

Each path is independently tested every 24 hours by `bin/escape-hatch-verify.sh` (already shipped per DR-AMG-ENFORCEMENT-01 v1.4). An attestation is valid only if ≤ 24 h old.

### H.2 Credential store redundancy

Canonical credentials live in `/etc/amg/*.env` on each lane (0400 root:root). Backup copies:
- Encrypted backup to R2 via restic, nightly.
- Encrypted backup to a second offsite target (1Password vault or Bitwarden family vault) — manual sync, quarterly minimum.
- Paper backup of the master restic key in a physical safe (one-time setup; revisited only on key rotation).

### H.3 SSH-key rotation policy

- Operator SSH keys rotate quarterly OR on any credential-incident trigger.
- `bin/rotate-ssh-keys.sh --for solon --target all-lanes` generates new keys, deploys to `~/.ssh/authorized_keys` on all lanes via current keys, verifies new-key login works, then removes the old key. One-way door per key; rollback is to re-deploy the old key from the 1Password backup.
- After-action: every rotation logs to MCP with tag `ssh_key_rotation`, and updates `bin/escape-hatch-verify.sh` fingerprint expectations.

### H.4 fail2ban bypass for Solon IPs

Both lanes' `/etc/fail2ban/jail.local` include `ignoreip = 127.0.0.1/8 <solon_home_static_ip> <solon_office_static_ip>`. This is the Apr 13-14 incident-class prevention. Verification is part of `escape-hatch-verify.sh` item 6.

---

## Section I — Cutover Procedures (Planned + Unplanned) {#section-i}

### I.1 Planned cutover (maintenance window on primary)

Used when HostHatch needs a reboot, a package upgrade, or any maintenance that would cause > 60 seconds of unavailability.

1. Operator runs `bin/access-lane-health.sh --lane hetzner-a --require green`. Must exit 0. If not, abort — don't cutover to a red lane.
2. Operator runs `bin/access-lane-cutover.sh --to hetzner-a --reason "maintenance: <ticket>"`.
3. Script: Cloudflare DNS weights flip to 1/99 (from 99/1) — meaning 1% stays on HostHatch for continuous-exercise + 99% flows to Hetzner-A. Waits 30s for propagation.
4. Script verifies 5% of recent traffic (via Cloudflare Analytics API) is now on Hetzner-A.
5. Operator performs maintenance on HostHatch.
6. Operator runs `bin/access-lane-cutover.sh --to hosthatch --reason "maintenance complete"`.
7. Weights flip back to 99/1. Verification as above.

Expected elapsed time: 2 min cutover + maintenance time + 2 min failback.

### I.2 Unplanned cutover (primary-down detection)

Triggered automatically by Cloudflare health-check policy. No operator action required.

1. Cloudflare detects 3 consecutive failed probes on HostHatch `/healthz`.
2. Weighted pool auto-adjusts to 0/100 (HostHatch/Hetzner-A).
3. Cloudflare sends webhook alert to AMG Slack #ops-alerts.
4. `titan-channel` on Hetzner-A receives the alert via its `X-Source: cloudflare-webhook` allowlist, posts MCP notification → Titan session (which cold-boots on Hetzner-A if primary is gone) sees the event and begins §I.3 diagnosis.

### I.3 Titan auto-diagnosis on unplanned cutover

Titan (running on Hetzner-A after cold-boot from git) runs:

1. `bin/diagnose-primary-outage.sh` — probes HostHatch on SSH (port 2222), HTTPS (port 443), ping (ICMP). Classifies the outage: network-partition | ssh-auth-fail | service-level | full-host-down.
2. Logs classification to MCP with tag `primary_outage_class`.
3. Posts to `#titan-nudge` channel with Viktor-persona terse summary.
4. If classification is `ssh-auth-fail`, Titan runs escape-hatch-verify attestation sequence via Tailscale.
5. If classification is `full-host-down`, Titan begins incident timeline in `plans/deployments/INCIDENT_<YYYY-MM-DD>_<classification>.md`.
6. Titan does NOT auto-remediate — remediation is a Hard Limit requiring Solon approval.

### I.4 Cutover validation checklist

After any cutover (planned or unplanned), these 7 checks must pass:

1. `/healthz` on active lane returns 200.
2. Database read query against `DATABASE_URL_READ` succeeds.
3. Database write query against `DATABASE_URL_WRITE` succeeds (unless write-failover was also triggered — separate checklist in sister doctrine).
4. R2 read of a known object succeeds.
5. R2 write of a test object succeeds (then delete).
6. LiteLLM `/v1/models` returns expected model list with valid auth.
7. titan-channel `/healthz` returns 200.

If any check fails, cutover is considered partial — operator ack required before closing the incident.

---

## Section J — Failover Drill Schedule + Testing {#section-j}

### J.1 Quarterly planned drill

On the 15th of every 3rd month (Jan 15, Apr 15, Jul 15, Oct 15):

1. Operator schedules a 45-minute drill window, ideally during off-peak hours (Sunday evening Boston time, typically).
2. Runs `bin/access-lane-cutover.sh --to hetzner-a --reason "quarterly drill Q<N>"`.
3. Observes Cloudflare weighted-route change, verifies traffic serving on secondary.
4. Runs the 7-check validation from §I.4.
5. Holds on secondary for 30 minutes (real production traffic serving on Hetzner-A).
6. Measures secondary-lane metrics during the hold: p95 latency, error rate, any user-visible degradation.
7. Runs `bin/access-lane-cutover.sh --to hosthatch --reason "quarterly drill complete"`.
8. Generates drill report at `plans/deployments/DRILL_Q<N>_<YYYY-MM-DD>.md` with all metrics.
9. Logs drill to MCP with tag `access_redundancy_drill` and severity `info`.

### J.2 Monthly synthetic-probe drill

On the 1st of every month:

1. `bin/drill-synthetic.sh` runs automatically via systemd timer at 03:00 local.
2. Sends 1000 synthetic requests to the secondary lane.
3. Records p50/p95/p99 latency, error rate, success rate.
4. Writes report to `plans/deployments/DRILL_synthetic_<YYYY-MM>.md`.
5. Fails loudly (Slack DM to operator) if any metric is outside SLO.

### J.3 Chaos-engineering-lite

Monthly, a random 10-minute window during business hours, `bin/chaos-lite.sh` (optional, opt-in via policy.yaml flag) briefly increases the weight on Hetzner-A to 50/50 instead of 99/1. Measures whether any client-facing issue arises. If zero issues for 3 consecutive months, weight permanently moves to 95/5 as a steady-state increase in secondary exercise.

### J.4 After-action review

Every drill (planned, synthetic, chaos) generates an after-action that answers:

1. Did cutover happen as documented?
2. Did any check in §I.4 fail?
3. Was operator-visible alerting consistent with expectations?
4. What doctrine update is needed based on this drill?

Drill results are reviewed at the quarterly doctrine-refresh cadence.

---

## Section K — SLO + Measurable Success Criteria {#section-k}

### K.1 Access-lane SLO

- **Target availability:** 99.95% measured over 30 rolling days. Monthly error budget: ~21.6 minutes of downtime.
- **Measurement surface:** Cloudflare synthetic probe hitting `/healthz` on the *weighted pool* (i.e. whichever lane is serving). An outage is counted whenever the weighted pool returns non-2xx for > 60 seconds.
- **Exclusions:** operator-scheduled maintenance windows (announced ≥ 24 h in advance and ≤ 30 min each) are not counted. There are ≤ 4 such windows per quarter.

### K.2 Burn-rate alerts

- **2% burn over 1 hour:** Slack nudge (not a page).
- **5% burn over 6 hours:** Slack DM to operator (page).
- **10% burn over 24 hours:** Slack DM + SMS + Pushover to operator (escalate).

Burn-rate implementation: `lib/slo_burn_rate.py` runs every 5 minutes via systemd timer on both lanes (only the active-pool calculation on the primary actually counts; both lanes compute it for symmetry).

### K.3 Dashboard

`/orb` dashboard exposes:
- Current serving lane (primary/secondary/split).
- Last 24 h uptime percentage.
- Current month error-budget burn.
- Last cutover timestamp + reason.
- Last drill timestamp + result.
- Replica lag (DB).
- Per-lane service health (6 services × 2 lanes = 12 status indicators).

### K.4 Success criteria for doctrine promotion

This doctrine ships canonical to `/opt/amg/docs/` only after:

1. `grok_review` (sonar) adversarial grade ≥ 9.4 A.
2. Self-grade 10-dimension ≥ 9.4 A across all dims.
3. No HARD_LIMIT_* risk tags in adversarial response.
4. Internal consistency check: every claim in §C Principles is traceable to a concrete implementation path in §D-J.

---

## Section L — Cost Envelope + Budget Guardrails {#section-l}

### L.1 Infrastructure cost budget

| Line item | Monthly cost | Notes |
|---|---|---|
| Hetzner CX32 node-A (EU region) | €39.20 (~$42) | 4 vCPU / 8 GB RAM / 80 GB NVMe / 20 TB egress |
| Hetzner CX32 node-B (EU region, DR standby) | €39.20 (~$42) | same spec |
| Cloudflare Load Balancer (Global tier) | $5 | includes 2 origin pools + health checks |
| Cloudflare R2 (existing) | $0 incremental | already in budget, no delta from this doctrine |
| Supabase read-replica egress | $0 incremental | logical replication over existing Supabase egress quota |
| Tailscale (Free Plan) | $0 | 3 nodes fits within 20-device free tier |
| Pingdom / Grafana Cloud synthetic probes | $0-10 | free tier sufficient for 2-lane monitoring |
| **Total incremental doctrine cost** | **~$90-100/month** | hard ceiling $100/month |

### L.2 Budget guardrails

- **Hard monthly ceiling:** $100 for all access-redundancy infrastructure. Exceeding triggers auto-page to Solon via `#titan-nudge`.
- **Cost monitoring:** `lib/infra_cost_monitor.py` polls Hetzner Cloud API + Cloudflare billing API daily at 08:00 local, writes to MCP with tag `infra_cost`. Anomaly detection: > 10% MoM increase triggers Slack nudge.
- **Egress risk:** if a single lane saturates Hetzner's 20 TB egress budget (worst case would require sustained 6+ Mbps on that node for 30 days), overage charges apply at €1/TB. Monitored; automatic traffic-throttle at 18 TB via Cloudflare.

### L.3 Opt-out for cost-sensitive periods

If MRR drops below $5,000 for 2 consecutive months, `bin/cost-defense-mode.sh --lane hetzner-b --hibernate` de-provisions Hetzner-B (the DR standby) to save $42/month. Reboot via `--wake` within 10 minutes when budget recovers. Hetzner-A (the serving secondary) is NEVER hibernated — it's part of the SLO contract.

---

## Section M — Rollback + Fallback to Single-Lane {#section-m}

### M.1 Rollback: lane-add rollback

If provisioning Hetzner-A breaks anything (corrupts a Cloudflare DNS record, introduces a regression in titan-channel, collides with an existing port binding), roll back via:

1. `bin/access-lane-cutover.sh --to hosthatch --force-single` forces 100/0 weighting.
2. `bin/cloudflare-remove-lane.sh --lane hetzner-a` removes the secondary from the origin pool.
3. `bin/hetzner-deprovision.sh --node hetzner-a` destroys the VPS.
4. Single-lane operation resumes.

Rollback window: < 10 minutes.

### M.2 Fallback: extended single-lane mode

If Hetzner-A is unavailable for > 24 h (Hetzner-side outage, billing issue, etc.), primary can continue serving alone. Cloudflare health-check automatically routes all traffic to HostHatch. No client-facing impact.

Risk during single-lane mode: all §B.2 failure modes are back in blast radius. Operator attention increases; drills are suspended; a Tier-2 incident during single-lane mode is a full outage.

### M.3 Graceful degradation within a single lane

Each lane's service manifest is designed so that a single service degradation does not take down the whole lane:

- LiteLLM gateway down → titan-channel routes directly to Anthropic API as fallback.
- MCP memory server down → Titan session marks itself `memory_degraded` and avoids writes; reads fall back to file-based memory.
- titan-channel down → n8n workers can still process queue jobs; Slack/webhook traffic fails.
- n8n worker down → sibling workers on other lane absorb via shared Redis queue.
- OPA down → Gate #4 fails open to audit mode (not enforce mode); MCP log captures the degradation.

No single service being down means the lane is red. A lane is red only when `/healthz` logic says it is — and that logic is auditable.

---

## Section N — Integration With Sister Doctrines {#section-n}

### N.1 DR-AMG-RESILIENCE-01 (self-healing)

RESILIENCE-01's central watchdog monitors access-lane health and triggers the §I.2 unplanned cutover sequence. This doctrine provides the failover target; RESILIENCE-01 provides the detection + response loop. No conflict.

### N.2 DR-AMG-ENFORCEMENT-01 v1.4 (lockout prevention)

ENFORCEMENT-01 v1.4's Gate #4 OPA policy protects both lanes symmetrically. When a new Hetzner lane is provisioned, its OPA install is part of the per-lane service manifest (§D.3). The escape-hatch-verify attestations (item 6: fail2ban whitelist) apply to both lanes independently.

### N.3 DR-AMG-UPTIME-01 (99.95% SLO)

UPTIME-01 defines the overall customer-facing SLO. ACCESS-REDUNDANCY-01 is the access-layer contribution to that SLO. Other contributions come from: service-layer SLO (containerized services themselves), database-layer SLO (Supabase + replica), object-store SLO (R2). UPTIME-01 composes them; ACCESS-REDUNDANCY-01 commits to the access-layer number.

### N.4 DR-AMG-DATA-INTEGRITY-01 (checksums, restore drills)

DATA-INTEGRITY-01 owns the R2 checksum + snapshot verification + restore drill schedule. This doctrine consumes R2 as a shared SOT but does not define its integrity guarantees.

### N.5 DR-AMG-RECOVERY-01 (disaster recovery runbook)

RECOVERY-01 takes over when ACCESS-REDUNDANCY-01 cannot (e.g. both HostHatch and Hetzner are simultaneously down, or a regional EU outage coincides with a US outage). RECOVERY-01's RTO is measured in hours, not minutes.

### N.6 Future: DR-AMG-DNS-REDUNDANCY-01 (not commissioned)

This doctrine acknowledges the single-DNS-provider risk (§E.5). A future doctrine (placeholder) would add DNSimple or AWS Route 53 as a secondary authoritative DNS provider, with automated failover between them. Out of scope for v1.0 of ACCESS-REDUNDANCY.

### N.7 Future: DR-AMG-BILLING-REDUNDANCY-01 (not commissioned)

Separate billing identity across providers protects against cascading billing failure (§B.2 #10). Current state: HostHatch is billed on card A; Hetzner is billed on card B. Future doctrine would formalize multi-card + multi-entity billing posture.

---

## Section O — Anti-Patterns + Known Failure Modes {#section-o}

### O.1 Anti-pattern: the silent passive standby

A secondary lane that never sees real traffic degrades silently: the last stale credential, the last drifted config, the last uncopied systemd unit. When it is needed, it fails. This doctrine forbids passive-only secondaries (see §C.1). Every lane sees ≥ 5% of production traffic continuously.

### O.2 Anti-pattern: the "we'll test it next quarter" drill

Drills that get postponed to the next quarter until a real outage happens are drills that never happen. This doctrine forces drill cadence at the quarterly + monthly + chaos-lite levels, and the quarterly drill IS real production traffic cutover. There is no "test environment" escape valve.

### O.3 Anti-pattern: synchronous-replication fetish

Some doctrines insist on synchronous DB replication across regions. This doctrine does not, because synchronous replication at > 50 ms RTT is a throughput destroyer and a primary-outage amplifier (if the synchronous replica is unreachable, the primary can't commit). Our replication is asynchronous with a documented < 10 s p99 lag target. RPO of seconds, not zero, is the correct trade for this scale.

### O.4 Anti-pattern: the multi-cloud complexity spiral

Multi-cloud at scale is a source of operational complexity that often exceeds the reliability benefit. This doctrine explicitly chooses a two-lane (not N-lane) architecture. N=2 is the minimum for redundancy; N=3 is the threshold at which coordination complexity starts to dominate. AMG at current scale has no business running N=3; this doctrine commits to N=2 until MRR supports dedicated SRE staffing (realistically N=2 forever in the solo-operator era).

### O.5 Known failure mode: split-brain during partial partition

If Cloudflare can reach HostHatch but not Hetzner (partial internet partition), Cloudflare routes all traffic to HostHatch — correct behavior. If Cloudflare cannot reach either (Cloudflare-side issue), client-facing resolution fails even though both lanes may be healthy. This is a DNS-layer failure, not an access-lane failure, and is addressed only by the future DR-AMG-DNS-REDUNDANCY-01 doctrine.

### O.6 Known failure mode: post-failback session-affinity breakage

Some client sessions (specifically: voice-AI calls mid-stream) cannot survive a lane cutover cleanly because they hold stateful audio connections. Current mitigation: new calls route to the new lane; in-flight calls complete on the old lane via session affinity (Cloudflare Sticky Sessions by cookie on the sub-path `/voice/*`). Duration: worst-case a 10-minute voice call rides the old lane during failback. This is acceptable; documented.

---

## Section P — Glossary + References {#section-p}

### P.1 Glossary

- **Access lane** — a complete, independent serving tier (compute + per-lane services + env). This doctrine specifies two lanes: HostHatch (primary), Hetzner 2× CX32 (secondary).
- **Active/active** — both lanes serve real traffic at steady state, even if weighted heavily toward one.
- **Burn rate** — the rate at which the monthly error budget is being consumed.
- **Cutover** — flipping the weighted-pool DNS record from one lane to another.
- **Failback** — cutover back to the lane previously demoted.
- **RPO (Recovery Point Objective)** — maximum data loss acceptable during failover; for DB = replica lag.
- **RTO (Recovery Time Objective)** — maximum time to restore serving after failure.
- **Shared SOT (Source of Truth)** — a state store (R2, Supabase, env-file) that both lanes read/write against symmetrically.

### P.2 References

- Google SRE Book, Ch. 4 "Service Level Objectives" (error budget framework).
- AWS Well-Architected Framework, Reliability Pillar.
- Netflix Tech Blog, "Chaos Engineering" (2020 edition).
- IBM MAPE-K (2003) — feedback loop architecture referenced in DR-AMG-RESILIENCE-01.
- Cloudflare Load Balancer documentation (current).
- Hetzner Cloud API documentation (current).
- Postgres 15 Logical Replication documentation (current).
- CLAUDE.md §8, §12, §13, §15, §17 (AMG internal doctrine).
- DR-AMG-ENFORCEMENT-01 v1.4 (sister doctrine, commit `707d895`).

---

*End of doctrine DR-AMG-ACCESS-REDUNDANCY-01 — version 1.0 (2026-04-15).*
*Grade block to be appended after grok_review adversarial pass.*
