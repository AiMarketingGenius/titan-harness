# MP‑4: Atlas Reliability, Monitoring & Incident Ops Doctrine

**Version:** MP‑4 v1.0  
**Grade target:** 9.3–9.4  
**Status:** COMPUTER DR PASS COMPLETE  
**Depends on:** Titan-Voice-AI-Stack-v1.0, Autonomy Blueprint, AMG Multi-Lane Operations Doctrine v1.0, hermes-phase-a-atlas-spec  
**Classification:** AMG Internal — Implementation-Ready Doctrine

---

## §1 SERVICE REGISTRY AND HEALTH MATRIX

### 1.1 Canonical Log Schema

All monitored components emit JSONL health lines under `/var/log/titan/*.jsonl`, driven by systemd timers. Every line is a single valid JSON object. Mandatory fields:

```json
{
  "ts": "2026-04-11T03:00:01Z",
  "service": "kokoro",
  "status": "healthy",
  "detail": "synth_latency_ms=210, port=8880",
  "metrics": {
    "latency_ms": 210,
    "cpu_pct": 12.4,
    "mem_mb": 340
  },
  "check_version": "1"
}
```

`status` MUST be one of exactly three values: `healthy` | `degraded` | `dead`. No other values accepted. Any parse failure is treated as `dead`.

### 1.2 Full Health Matrix

| Unit | systemd unit / process | Check method | Interval | JSONL path | Healthy | Degraded | Dead |
|---|---|---|---|---|---|---|---|
| **Kokoro TTS** | `titan-kokoro.service` | HTTP probe local port, synth latency | 60s | `/var/log/titan/kokoro-health.jsonl` | HTTP 200, latency < 400ms | HTTP 200, latency 400–800ms | No response or latency > 800ms |
| **Hermes Pipeline** | `titan-hermes.service` | HTTP probe `/health`, queue depth check | 60s | `/var/log/titan/hermes-health.jsonl` | HTTP 200, queue < 50 | HTTP 200, queue 50–200 | No response or queue > 200 |
| **MCP** | `titan-mcp.service` | HTTP probe `memory.aimarketinggenius.io/health`, write+read roundtrip | 120s | `/var/log/titan/mcp-health.jsonl` | HTTP 200, roundtrip < 500ms | HTTP 200, roundtrip 500–2000ms | No response or write failure |
| **n8n** | `n8n.service` | HTTP probe `/healthz`, active workflow count | 60s | `/var/log/titan/n8n-health.jsonl` | HTTP 200, ≥1 active workflow | HTTP 200, 0 active workflows | No response |
| **Caddy** | `caddy.service` | HTTP probe on configured domains, TLS cert expiry | 120s | `/var/log/titan/caddy-health.jsonl` | HTTP 200, cert expiry > 14d | HTTP 200, cert expiry 7–14d | No response or cert expiry < 7d |
| **titan-processor** | `titan-processor.service` | Process liveness + systemd watchdog heartbeat | 30s | `/var/log/titan/processor-health.jsonl` | Process alive, watchdog OK | Process alive, missed 1 watchdog ping | Process dead or missed 2+ watchdog pings |
| **titan-bot (Slack)** | `titan-bot.service` | Slack API `auth.test` roundtrip | 60s | `/var/log/titan/titanbot-health.jsonl` | API 200, bot connected | API 200, latency > 3s | API failure or bot disconnected |
| **Supabase connectivity** | n/a (external) | TCP connect + SELECT 1 roundtrip | 120s | `/var/log/titan/supabase-health.jsonl` | Connect < 200ms, query < 300ms | Connect < 200ms, query 300–1000ms | Connect failure or query > 1000ms |
| **R2 (Cloudflare)** | n/a (external) | PUT/GET roundtrip on sentinel object | 300s | `/var/log/titan/r2-health.jsonl` | PUT+GET < 2s, HTTP 200 | PUT+GET 2–5s | PUT or GET failure |
| **Reviewer Loop budget** | Anthropic API headers | Read `anthropic-ratelimit-tokens-remaining` on each call; daily rollup | Per call + daily | `/var/log/titan/reviewer-budget.jsonl` | Remaining > 40% daily cap | Remaining 20–40% daily cap | Remaining < 20% daily cap |
| **VPS disk** | systemd timer + `df` | `/` mount usage percentage | 300s | `/var/log/titan/disk-health.jsonl` | < 70% used | 70–85% used | > 85% used |
| **VPS CPU/memory** | systemd timer + `vmstat`/`free` | 5-min load average vs core count; available memory % | 60s | `/var/log/titan/vps-health.jsonl` | Load < 1× cores, mem avail > 20% | Load 1–2× cores OR mem avail 10–20% | Load > 2× cores sustained 5+ min OR mem avail < 10% |

**Titan Implementation Notes — §1**

1. Deploy one systemd timer per service using `Type=oneshot` + `RemainAfterExit=no`. Timer fires the check script; script emits one JSONL line and exits.
2. Use `WatchdogSec=30s` + `Type=notify` on titan-processor specifically, since it runs continuously. All other checks are one-shot probes.
3. Canonical fields are mandatory. Additional fields are allowed. Titan must validate `status` is one of the three legal values before writing; on parse failure write `"status": "dead"` with `"detail": "parse_error"`.
4. The health matrix is the single source of truth for all downstream decisions in §2–§6.

---

## §2 AUTO-RESTART POLICY

### 2.1 Restart Tiers

| Tier | Condition | systemd policy | Notify Solon? |
|---|---|---|---|
| **Tier 1 — Always restart** | Kokoro, Hermes, titan-processor, titan-bot, n8n | `Restart=on-failure`, `RestartSec=5s` | No (transparent) |
| **Tier 2 — Restart + notify** | Caddy, MCP | `Restart=on-failure`, `RestartSec=10s` | Yes — Slack message within 60s of restart |
| **Tier 3 — Alert only** | Supabase, R2, Anthropic API, VPS resources | No auto-restart (external/infra) | Yes — Slack message immediately |

### 2.2 Restart Storm Protection

A restart storm is defined as: ≥5 restarts of the same service within any 300-second window.

**systemd configuration for all Tier 1/2 services:**

```ini
[Unit]
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Restart=on-failure
RestartSec=5s
```

On storm detection (StartLimitBurst exceeded):

1. systemd stops restart attempts automatically (StartLimitAction=none).
2. Titan writes `"status": "dead"` with `"detail": "restart_storm"` to the service JSONL.
3. Titan escalates to P1 (or P0 if the service is revenue/client-critical).
4. Titan does NOT attempt manual restart. Solon must issue explicit restart approval.

**Titan Implementation Notes — §2**

1. Apply the `StartLimitIntervalSec=300` / `StartLimitBurst=5` drop-in to every Tier 1 and Tier 2 service unit via `/etc/systemd/system/<service>.service.d/restart-policy.conf`.
2. Do not set `StartLimitIntervalSec=0` (infinite restart). That policy is explicitly prohibited — it masks cascading failures.
3. Tier 3 has no restart directive. The check script emits the JSONL alert and invokes the Slack notification path only.
4. Log all restart events to MCP via `log_decision` with `restart_tier`, `attempt_count`, and `triggered_storm: bool`.

---

## §3 NIGHTLY HEALTH SUITE

**Schedule:** 3:00 AM ET daily (08:00 UTC), via systemd timer `titan-nightly-health.timer`.  
**Timeout:** Suite must complete within 20 minutes. If any test exceeds its individual timeout, mark it `dead` and continue.  
**Output:** `/var/log/titan/nightly-suite-YYYYMMDD.jsonl` — one line per test; summary line at end.  
**Notification:** Slack `#titan-ops` digest at completion.

### 3.1 Ordered Test Sequence

| # | Test name | What it checks | Pass condition | Timeout |
|---|---|---|---|---|
| 1 | `vps-resources` | CPU load average, memory available, swap state | Load < 1× cores, mem > 20%, swap not growing | 30s |
| 2 | `disk-capacity` | `/` mount %, projected days-to-full at current rate | < 70% used, > 30 days headroom | 15s |
| 3 | `kokoro-synth` | Full TTS synthesis of a 50-word test phrase | HTTP 200, WAV returned, latency < 500ms | 30s |
| 4 | `hermes-pipeline` | Send a test message through Hermes; verify output | Message processed, output matches expected schema | 60s |
| 5 | `mcp-roundtrip` | Write a test key to MCP; read it back; delete it | Write+read+delete succeed, roundtrip < 1s | 30s |
| 6 | `n8n-workflows` | Verify at least 1 workflow is active; trigger a test webhook | Webhook returns 200, execution logged | 45s |
| 7 | `supabase-query` | `SELECT 1` + row count on a sentinel table | Query returns expected row count, latency < 500ms | 20s |
| 8 | `r2-secondary` | PUT sentinel object to R2; GET it back | PUT+GET succeed within 3s | 30s |
| 9 | `reviewer-budget` | Read Anthropic API headers for remaining token budget | Remaining > 40% of daily cap | 15s |
| 10 | `caddy-tls` | Check TLS cert expiry on all configured domains | Cert expiry > 14 days on all domains | 30s |

### 3.2 Suite Result States

- **ALL PASS:** Slack digest: ✅ Nightly suite passed — all 10 tests healthy.
- **1–2 DEGRADED:** Slack digest lists degraded items; no P-class incident declared unless SLA-critical service is affected.
- **ANY DEAD:** Triggers incident classification per §4. Nightly suite does not substitute for real-time monitoring; it augments it.

**Titan Implementation Notes — §3**

1. Implement the suite as a single bash or Python orchestrator that calls each test in sequence, captures JSONL output, and writes the summary line.
2. Tests must be idempotent. Test artifacts (keys, objects) are cleaned up within the test.
3. If the nightly suite itself fails to start (timer misfire), Titan detects the missing log file and raises a P2 by 4:00 AM ET.
4. Secondary-lane tests (R2, Supabase direct reads) double as monthly validation of the fallback path — log `secondary_lane_test: true` in the JSONL for those entries.

---

## §4 INCIDENT CLASSIFICATION DOCTRINE

### 4.1 Severity Definitions

| Class | Definition | Examples | Solon notification? | Auto-actions |
|---|---|---|---|---|
| **P0 — Critical** | Total loss of Solon's ability to command Titan, OR complete loss of client-facing service | VPS unreachable, credential exposure, Slack + email both down, Kokoro + Hermes both dead | Immediately (Slack; email if Slack down) | Maximum auto-healing per playbook |
| **P1 — High** | Significant degradation of a core system; workaround available or partial service intact | Single service dead but pipeline still functional, Reviewer Loop > 80% consumed, MCP degraded | Immediately | Auto-healing per playbook; Solon approval if irreversible action needed |
| **P2 — Medium** | Non-critical degradation; no immediate client impact | Caddy cert expiry 7–14d, Supabase latency elevated, nightly suite test failure | Next Titan status report (within 1 hour) | Logged; remediation queued |
| **Not an incident** | Expected behavior, transient blip that auto-resolved, test artifact | Single health check miss followed by immediate recovery, scheduled maintenance, R2 latency spike < 60s | No | Log only |

### 4.2 Classification Decision Tree

```
Health check emits status change
        │
        ▼
  Is it "dead"?
  ├─ No  → "degraded"? → Log P2 candidate; check if sustained > 5 min → P2 if yes
  └─ Yes
        │
        ▼
  Is it a command/control surface?
  (VPS, titan-bot, MCP, Caddy)
  ├─ Yes → P0
  └─ No
        │
        ▼
  Is client-facing revenue at risk?
  (Hermes, n8n, Kokoro for active jobs)
  ├─ Yes → P0
  └─ No → P1
```

**Titan Implementation Notes — §4**

1. Titan classifies incidents automatically based on this tree. No human classification required for initial triage.
2. Classification is logged to MCP with `incident_class`, `triggering_service`, and `auto_actions_taken`.
3. If two services hit `dead` simultaneously, classify at the highest applicable level (P0 takes precedence).
4. Incident class can be downgraded after resolution; downgrade is also logged to MCP.

---

## §5 INCIDENT RESPONSE PLAYBOOKS

Each playbook follows the same structure: **Trigger → Immediate auto-actions → Solon notification → Resolution criteria → Post-incident log**.

---

### Playbook 5.1 — VPS Unreachable

**Trigger:** Three consecutive failed health checks across any two or more services (VPS-level failure inferred). Or: direct SSH failure from external probe.

**Classification:** P0.

**Immediate auto-actions (no Solon approval required):**
1. Titan attempts ICMP ping and TCP port 22 probe from a secondary probe point (n8n webhook or external cron).
2. If unreachable confirmed: Titan sends P0 email to Solon ops email (§7 template).
3. Titan does NOT attempt VPS-level actions (reboot, reinstall). These are Hard Limit actions — Solon-only.
4. Titan queues all pending tasks; sets internal state to `VPS_UNREACHABLE`.

**Solon notification:**
```
Subject: P0 — VPS Unreachable (Slack down)
Body:
  What: All services unresponsive. VPS at [IP] not responding to ICMP or TCP:22.
  When: [timestamp]
  Auto-actions: Queued all tasks. Awaiting VPS recovery or your instruction.
  Reply with: ACK | STOP EVERYTHING | STATUS
```

**Resolution criteria:** VPS responds to probe AND at least 3 Tier 1 services return `healthy` within 5 minutes of VPS recovery.

**Post-incident:** MCP entry with duration, probable cause (if determinable), and recovery action.

---

### Playbook 5.2 — Credential Exposure

**Trigger:** Titan detects any of: (a) secret key present in a git commit, (b) environment variable logged to a non-secure JSONL path, (c) Infisical audit log shows unexpected secret access.

**Classification:** P0.

**Immediate auto-actions:**
1. Titan halts all outbound API calls immediately (circuit open).
2. Titan sends P0 Slack alert AND P0 email simultaneously (credential exposure is a case where both channels fire regardless of Slack health status).
3. Titan does NOT rotate credentials autonomously — rotation is a Hard Limit action.
4. Titan preserves the evidence log entry with exact commit SHA or log path.

**Solon notification:**
```
Subject: P0 — Credential Exposure Detected
Body:
  What: [secret type] detected in [location: commit SHA / log path].
  When: [timestamp]
  Auto-actions: All outbound API calls halted. Evidence preserved at [path].
  Action required: Rotate [credential name] immediately. Titan awaiting your go-ahead to resume.
  Reply with: ACK | STOP EVERYTHING | STATUS
```

**Resolution criteria:** Confirmed credential rotation + Titan resumes API calls under new credentials + commit/log sanitized.

**Post-incident:** Full timeline in MCP. Git history rewrite (if needed) is a separate Hard Limit action requiring Solon approval.

---

### Playbook 5.3 — Reviewer Loop Exhaustion

**Trigger:** `anthropic-ratelimit-tokens-remaining` falls below 20% of daily cap (Dead threshold per §1.2).

**Classification:** P1 (degraded grading throughput). Escalates to P0 only if Reviewer Loop is the sole blocker on a time-critical client deliverable.

**Immediate auto-actions:**
1. Titan halts all non-critical Reviewer Loop calls immediately (priority ordering per §8).
2. Only P0/P1 incident grading and active client deliverables continue consuming budget.
3. Titan switches non-critical grading to cached-input patterns where possible (Anthropic cached tokens do not count toward ITPM limits).
4. Titan sends P1 Slack alert with current budget state and estimated reset time.

**Solon notification (Slack):**
```
[P1] Reviewer Loop budget < 20%
• Remaining: ~[X] tokens
• Reset: [time until daily reset]
• Auto-actions: Non-critical reviews paused. Client deliverables and P0/P1 grading continue.
• Queue: [N] tasks deferred.
• No action required unless you want to override priority ordering.
```

**Resolution criteria:** Budget resets (daily) OR Solon approves budget increase request.

**Post-incident:** Log daily budget consumption trend. If exhaustion recurs 3+ days in 7, Titan generates cap-increase recommendation per §8.

---

### Playbook 5.4 — Slack (titan-bot) Down

**Trigger:** `titan-bot` health check returns `dead` for > 5 minutes.

**Classification:** P1 (communication degradation). Escalates to P0 if a P0 incident is simultaneously active.

**Immediate auto-actions:**
1. Titan sets internal state to `SLACK_DOWN`.
2. Titan checks if any P0 or high-priority P1 incident is currently active.
3. **If P0 or high-priority P1 active:** Titan sends email to Solon ops email within 2 minutes of Slack confirmed dead (template below).
4. **If no active P0/P1:** Titan queues notifications; resumes Slack delivery when recovered; no email sent.
5. Titan polls Slack health every 60 seconds. On recovery, drains queued notifications to Slack and logs the outage duration to MCP.

**Email template (P0/P1 active, Slack down):**
```
Subject: P[0|1] — [incident summary] (Slack down)
Body:
  Slack Status: titan-bot unreachable since [timestamp].
  Active Incident: [P0|P1] — [summary of what is happening].
  When: [incident start timestamp].
  Auto-actions underway: [list of actions Titan is taking automatically].
  
  Reply with ONE of:
    ACK — Acknowledge; Titan continues auto-handling.
    STOP EVERYTHING — Global stop (all tasks halted, no further auto-actions).
    STATUS — Titan emails you a full status summary.
```

**Email reply parsing:** Titan checks the designated ops email inbox every 5 minutes when in `SLACK_DOWN` state. Recognized replies: `ACK`, `STOP EVERYTHING`, `STATUS`. Any unrecognized reply is ignored (logged to MCP). `STOP EVERYTHING` triggers the global stop defined in MP-3.

**Resolution criteria:** titan-bot health returns `healthy` for 3 consecutive checks.

**Post-incident:** Titan resumes Slack as sole notification channel. Email is used only during confirmed Slack outage.

---

### Playbook 5.5 — Client Portal Down

**Trigger:** Caddy health check returns `dead` (domain probe fails or TLS cert error) OR n8n webhook endpoint for client-facing automations returns non-200 for 3 consecutive checks.

**Classification:** P1 (client-facing degradation). Escalates to P0 if client has an active SLA commitment.

**Immediate auto-actions:**
1. Titan attempts Caddy service restart (Tier 2 restart policy per §2).
2. If Caddy restarts successfully and domain probe recovers within 2 minutes: log as P2, no Solon notification.
3. If Caddy restart fails or domain probe remains dead after restart: escalate to P1, notify Solon.
4. If TLS cert expiry is < 7 days: Titan runs `caddy reload` to trigger cert renewal. If renewal fails, escalate to P1.

**Solon notification (Slack):**
```
[P1] Client portal degraded
• Service: Caddy / domain [domain]
• Status: [HTTP probe result / cert expiry]
• Auto-actions: Restart attempted — [succeeded|failed].
• Client impact: [describe if known].
• Next: [Titan's proposed next step].
```

**Resolution criteria:** All configured domains return HTTP 200, TLS cert expiry > 14 days.

**Post-incident:** MCP entry with downtime duration and client notification decision (Solon decides whether client communication is required).

---

**Titan Implementation Notes — §5**

1. Each playbook is a named function in the incident orchestrator. Trigger conditions are checked by the health monitoring loop, not ad-hoc.
2. All auto-actions that touch running services (restarts) are logged to MCP before execution.
3. Irreversible actions (credential rotation, VPS reboot, git history rewrite) are never auto-executed. Always Hard Limit.
4. Email parsing for Playbook 5.4 uses exact string matching, case-insensitive, on the first non-blank line of the reply body. If the reply cannot be parsed, Titan logs `email_reply_unparsed` to MCP and takes no action.

---

## §6 PERFORMANCE MONITORING DOCTRINE

### 6.1 Per-Call Metrics

Every Hermes pipeline call and every Reviewer Loop call emits the following to `/var/log/titan/perf-calls.jsonl`:

```json
{
  "ts": "2026-04-11T14:23:01Z",
  "call_type": "reviewer_loop",
  "model": "claude-sonnet-4-5",
  "input_tokens": 4200,
  "output_tokens": 380,
  "cached_input_tokens": 3100,
  "latency_ms": 1840,
  "cost_usd": 0.0042,
  "phase": "P3",
  "status": "completed"
}
```

`cached_input_tokens` is recorded separately because cached tokens do not count toward Anthropic ITPM limits — this distinction informs budget calculations in §8.

### 6.2 Daily Digest

Titan compiles a daily performance digest at 6:00 AM ET and posts to Slack `#titan-ops`:

```
Daily Perf Digest — [date]
Reviewer Loop
  • Calls: [N]
  • Budget used: [X]% of daily cap
  • Cache hit rate: [Y]%
  • Avg latency: [ms]
Hermes Pipeline
  • Jobs processed: [N]
  • Avg end-to-end: [ms]
  • Failures: [N] (auto-recovered: [N])
VPS
  • Peak CPU: [%] at [time]
  • Peak memory: [%] at [time]
  • Disk delta: +[MB] (projected full: [days])
```

### 6.3 Adaptive Thresholds

Static thresholds (§1.2) are the floor. Titan also maintains a 7-day rolling baseline for each metric. An alert fires if a value exceeds:

- **2× the 7-day rolling average** for latency metrics, OR
- **1.5× the 7-day rolling average** for budget consumption rate.

This catches slow-burn degradation that stays below static thresholds.

**Titan Implementation Notes — §6**

1. Per-call logging is append-only. Log rotation: keep 30 days of `perf-calls.jsonl`; compress files older than 7 days.
2. Rolling baseline calculation runs as part of the nightly suite (§3, conceptually after test 9).
3. Adaptive threshold alerts are classified P2 by default unless the metric is the Reviewer Loop budget (classify P1 at 2× consumption rate).
4. All cost figures use the Anthropic published token price at the time of the call. If price changes, update the calculation — do not use cached price after 30 days.

---

## §7 MULTI-LANE INFRASTRUCTURE DOCTRINE

Each lane has a primary and a secondary. Lane switches are automatic on degradation detection. All switches are logged to MCP.

### 7.1 Claude / LLM Lane

| | Primary | Secondary |
|---|---|---|
| **Provider** | Anthropic API (direct) | AWS Bedrock (Claude via Bedrock) or comparable Claude-compatible endpoint |
| **Activation trigger** | Sustained 429s or 5xx for > 3 minutes, OR latency > 10s for > 5 consecutive calls | Automatic |
| **Switch behavior** | Non-critical tasks route to secondary. Critical P0/P1 grading and active client deliverables stay on primary until confirmed non-functional. | |
| **Return trigger** | Primary returns HTTP 200 + latency < 3s for 5 consecutive probe calls | Automatic |

**Decision:** Sequential failover (not parallel hedging). Parallel hedging doubles token cost; for this solo-operator stack, latency tolerance is acceptable in exchange for cost predictability.

### 7.2 Memory Lane

| | Primary | Secondary |
|---|---|---|
| **Provider** | MCP (`memory.aimarketinggenius.io`) | Supabase direct reads |
| **Activation trigger** | MCP health check returns `degraded` or `dead` | Automatic |
| **Switch behavior** | Reads routed to Supabase direct. Writes queued in local file (`/var/log/titan/mcp-write-queue.jsonl`). Queued writes are replayed to MCP on recovery in order. | |
| **Return trigger** | MCP health returns `healthy` for 3 consecutive checks | Automatic |

**Critical constraint:** Queued writes are replayed before any new writes. Order is preserved. Maximum queue size: 500 entries. If queue exceeds 500, raise P1 alert.

### 7.3 File Storage Lane

| | Primary | Secondary |
|---|---|---|
| **Provider** | VPS NVMe (`/data`) | Cloudflare R2 (nightly offload) |
| **Activation trigger** | VPS disk health returns `degraded` (> 70%) or `dead` (> 85%), OR VPS unreachable | Automatic for reads; manual approval for destructive writes |
| **Switch behavior** | Reads prefer R2 when VPS is degraded. Non-destructive writes queue locally with R2 as backup. Destructive writes require Solon approval. | |
| **Return trigger** | VPS disk returns `healthy` | Automatic |

### 7.4 Solon Communications Lane

| | Primary | Secondary |
|---|---|---|
| **Channel** | Slack (titan-bot in `#titan-ops`) | Email only (designated Solon ops email) |
| **Activation trigger** | titan-bot health `dead` for > 5 minutes AND an active P0 or high-priority P1 incident | Automatic |
| **Return trigger** | titan-bot health returns `healthy` for 3 consecutive checks | Automatic — Titan resumes Slack, email reverts to contingency-only |

**Doctrine:** Slack is the single command and approval surface in normal operation. Email is used only during confirmed Slack outage with an active incident. No SMS. No other channels.

**Whitelisted email reply vocabulary:**

| Reply | Action |
|---|---|
| `ACK` | Acknowledge incident; Titan continues auto-handling |
| `STOP EVERYTHING` | Global stop — all tasks halted, no further auto-actions (MP-3 defined behavior) |
| `STATUS` | Titan emails full system status summary within 5 minutes |

Any other reply: logged to MCP as `email_reply_unparsed`; no action taken.

### 7.5 Payment Lane

| | Primary | Secondary |
|---|---|---|
| **Provider** | PayPal | TBD (Paddle or equivalent MoR) |
| **Activation trigger** | PayPal API returning errors for > 15 minutes | Manual — Solon approval required |
| **Notes** | Payment lane switches are Hard Limit actions. Titan alerts; Solon decides. |

### 7.6 Version Control Lane

| | Primary | Secondary |
|---|---|---|
| **Provider** | GitHub | VPS local mirror (`/data/git-mirror`) |
| **Activation trigger** | GitHub API returning errors or push failures for > 10 minutes | Automatic for local commits; push to mirror |
| **Return trigger** | GitHub API recovers; Titan syncs mirror to GitHub | Automatic |

### 7.7 Lane Switch Logging

Every lane switch — in either direction — writes a `log_decision` entry to MCP:

```json
{
  "decision_type": "lane_switch",
  "lane": "llm",
  "direction": "primary_to_secondary",
  "trigger": "sustained_429s_4min",
  "ts": "2026-04-11T14:01:22Z",
  "active_incidents": ["P1-hermes-latency"]
}
```

**Titan Implementation Notes — §7**

1. Implement lane state as a simple key-value store in MCP: `lane_states` with current primary/secondary status per lane.
2. Lane switch detection runs in the health monitoring loop — no separate process needed.
3. Nightly suite test #8 (R2) and test #7 (Supabase) double as periodic secondary-lane validation. Log `secondary_lane_test: true` in those JSONL entries.
4. Email reply parsing for Solon comms lane: Titan polls designated ops inbox every 5 minutes when in `SLACK_DOWN + active_incident` state. Polling stops when Slack recovers.
5. Keep fallback simple. The goal is command/control preservation during outages, not zero-latency failover.

---

## §8 REVIEWER LOOP BUDGET PROTECTION

### 8.1 Budget Tracking

Titan tracks Reviewer Loop budget using Anthropic API response headers on every call:
- `anthropic-ratelimit-tokens-remaining` (current window remaining)
- `anthropic-ratelimit-tokens-reset` (reset timestamp)

Daily cap is defined in `policy.yaml` as `reviewer_daily_token_cap`. This value is set by Solon at tier provisioning and updated when the cap changes. Titan does not autonomously update this value.

### 8.2 Throttle Thresholds

| Budget remaining | State | Action |
|---|---|---|
| > 60% | Normal | All reviews proceed normally |
| 40–60% | Watchful | Log to JSONL; no action change |
| 20–40% | Throttled | Defer non-critical reviews; prioritize by §8.3 |
| < 20% | Critical | Halt all non-priority-1 reviews; P1 alert; activate Playbook 5.3 |
| 0% (cap hit) | Exhausted | All reviews halt; P0 alert if active client deliverable blocked |

### 8.3 Priority Ordering (when throttled)

1. P0/P1 incident grading (always first)
2. Active client deliverables with SLA commitments
3. Current-phase project reviews (phases in active PLAN → EXECUTE pipeline)
4. Nightly suite grading
5. Exploratory / non-critical reviews (deferred to next budget window)

### 8.4 Cap-Hit Behavior

When budget hits 0%:
1. All Reviewer Loop calls return immediately with `budget_exhausted: true`.
2. Titan queues the tasks with estimated resume time (next reset per API headers).
3. Titan notifies Solon with queue length and estimated impact.
4. Titan does NOT make API calls that will return 429. Circuit open until reset.

### 8.5 Cap-Increase Recommendation Trigger

If Reviewer Loop exhaustion occurs on 3 or more days within any 7-day window, Titan auto-generates a cap-increase recommendation document at `/var/log/titan/budget-recommendation-YYYYMMDD.md` and sends Solon a Slack summary with the recommendation and estimated cost impact.

**Titan Implementation Notes — §8**

1. Budget state is derived from API headers, not from a local counter. Local counter is used only as a fallback if headers are absent.
2. Cached input tokens do not count toward ITPM limits per Anthropic docs — use `cached_input_tokens` from §6.1 to accurately model effective token consumption vs. cap.
3. The priority ordering in §8.3 is enforced programmatically: Titan checks `current_priority` of queued tasks against the current budget state before dispatching each call.
4. The cap-increase recommendation is flagged as requiring Solon review before any action — it is an informational document, not an autonomous spend increase.

---

## §9 ACCEPTANCE CRITERIA

MP-4 is considered implementation-complete when all 10 criteria are met and verified:

| # | Criterion | Verification method |
|---|---|---|
| 1 | All 13 health checks in §1.2 emit valid JSONL at correct intervals | Inspect `/var/log/titan/*.jsonl` for 24 hours; verify all services present |
| 2 | Tier 1 service restart occurs automatically within 60s of detected failure | Kill a Tier 1 service process; verify auto-restart and JSONL log entry |
| 3 | Restart storm protection halts restarts after 5 in 300s | Simulate rapid failures; verify service enters `dead` state and Solon is notified |
| 4 | Nightly health suite runs at 3:00 AM ET and posts Slack digest by 3:20 AM ET | Observe 3 consecutive nights |
| 5 | All 5 incident playbooks execute correctly on simulated triggers | Simulate each trigger in staging; verify auto-actions and notification content |
| 6 | Email fallback sends correctly formatted message within 2 minutes of Slack dead + P0 active | Simulate titan-bot failure with active P0; verify email arrives and reply parsing works |
| 7 | LLM lane switch routes non-critical tasks to secondary within 5 minutes of primary degradation | Simulate Anthropic API errors; verify secondary routing and MCP log entry |
| 8 | MCP write queue preserves order and replays correctly on MCP recovery | Take MCP offline; generate 10 writes; bring MCP back; verify queue replays in order |
| 9 | Reviewer Loop budget throttling engages at correct thresholds and priority ordering is enforced | Inject mock budget headers at each threshold level; verify task dispatch behavior |
| 10 | All lane switches and incident events are logged to MCP with correct schema | Review MCP entries after acceptance testing; verify schema compliance |

---

## §10 WHAT MP-4 EXPLICITLY DOES NOT COVER

The following are out of scope for this doctrine. Each is covered by its designated document:

| Topic | Owner document |
|---|---|
| Solon–Titan conversational interface, voice orb, Slack command vocabulary | MP-3 (Atlas Operations & Interfaces Doctrine) |
| Hermes pipeline architecture and message routing | hermes-phase-a-atlas-spec |
| Payment processing details, Paddle integration | Payments doctrine (TBD) |
| Outbound campaign strategy, lead generation | Outbound spec (not yet enabled) |
| Long-term capacity planning beyond current single-VPS | Future infra doc |
| Titan autonomy blueprint, Hard Limits table, approval workflows | DR_TITAN_AUTONOMY_BLUEPRINT.md |

**Titan Implementation Notes — §10**

1. Treat MP-4 as the reliability, monitoring, and incident layer only.
2. Route any UX, payment, or outbound-strategy questions to the appropriate doctrine.
3. Ensure MP-4 outputs (JSONL logs, health statuses, incident records) integrate cleanly into MP-3's interfaces but do not redefine them.
4. Keep implementation lean and focused on solo-operator constraints and the current single-VPS budget.
5. Structure logs and incident records so that future scaling (second VPS, additional lanes) can extend MP-4 without breaking existing log consumers or MCP schema.

---

*MP-4 v1.0 — Computer DR Pass Complete — 2026-04-11*
