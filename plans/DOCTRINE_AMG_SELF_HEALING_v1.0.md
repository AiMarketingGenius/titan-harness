# AMG Self-Healing Operational Doctrine v1.0

**Classification:** Internal Operational Doctrine  
**Commission ID:** DR-AMG-RESILIENCE-01  
**Owner:** AI Marketing Genius (AMG) — Solo Operator  
**Status:** v1.0 — Production  
**Sister Doctrine:** DR-AMG-SECURITY-01 (security handoffs flagged inline)  
**Last Updated:** April 2026

---

## Table of Contents

- [Section A — Executive Summary](#section-a)
- [Section B — Framework Foundations](#section-b)
- [Section C — The Seven Universal Principles](#section-c)
- [Section D — Domain-by-Domain Implementation Spec](#section-d)
- [Section E — Central Watchdog Architecture](#section-e)
- [Section F — Learning Loop](#section-f)
- [Section G — Implementation Roadmap](#section-g)
- [Section H — Metrics & Success Criteria](#section-h)
- [Section I — Anti-Patterns](#section-i)
- [Section J — Glossary + References](#section-j)

---

## Section A — Executive Summary {#section-a}

AMG operates a hybrid infrastructure across a MacBook development environment, a HostHatch Ubuntu 22.04 VPS (12-core, 64 GB RAM), Cloudflare R2 object storage, Supabase managed Postgres, Caddy reverse proxy, n8n workflow orchestration, a custom MCP memory server, and an autonomous build agent ("Titan") running as Claude Code on the VPS. This is a high-complexity, zero-redundancy-staff architecture: every failure mode that would ordinarily page a team of on-call engineers lands on a single operator.

**Extended architecture — two-head autonomous-builder model.** AMG's autonomous build and operations layer is a dual-head agent architecture. **Achilles / Codex** runs on the founder's MacBook as the principal builder and control tower (OpenAI Codex CLI at `~/achilles-harness`), owning final architecture, priorities, canonical doctrine, sequencing, and integration approval across AMG, AI Marketing Genius, Atlas, Solon OS, Memory Vault, Watchdog, and Mobile Command. **Titan** runs as Claude Code on both the MacBook (interactive development at `~/titan-harness`) and the HostHatch VPS (autonomous long-running work at `/opt/titan-harness`), owning bounded implementation, verification, repo inspection, concrete artifact production, and infrastructure support. Both heads share state via a Supabase-backed MCP memory server (`op_decisions`, `sprint_state`, `operator_task_queue`), log decisions in real time, and synchronize through explicit handoff tags (`RESTART_HANDOFF`, `safe-restart-eligible`, `tla-trigger-ready`). Neither head flips governance without explicit founder approval. **Aristotle** (Perplexity) is the external strategic-research co-agent. Grading runs through a tiered validator stack — **Gemini 2.5 Flash + Grok 4.1 Fast** as the default dual validator at a 9.3-score floor, **Gemini 2.5 Pro** reserved for architecture-critical review, and **Lumina** visual-grader gates every client-facing artifact before commit.

**Extended tech stack.** Voice pipeline: **Kokoro TTS** (self-hosted), **Chatterbox-Turbo** (voice cloning), **faster-whisper + Deepgram Nova-3 / Flux** (STT), **Silero VAD**, **WebRTC AEC3**, **Telnyx LiveKit-on-Telnyx** (telephony). Autonomy: **OpenAI Codex CLI** (Achilles), **Claude Code** (Titan), **Hammerspoon** permission auto-approve, **launchd** (Mac) + **systemd** (VPS), git **post-commit + post-receive hooks** (auto-mirror Mac → VPS bare → VPS working → GitHub → MCP). Quality-enforcement pipeline: **QE interceptor** between LLM output and user, **Hallucinometer** thread-health scoring with tiered intervention, **Einstein Fact Checker** credit-gated verification, **Auto-Carryover** threshold-triggered thread handoff + cross-vendor memory bridge. Memory layers — two distinct persistence systems: (1) **AI Memory Guard** — the consumer-facing cross-platform AI thread capture layer with mandatory provenance stamping (platform, thread_id, thread_url, exchange_number, user_timestamp) across ChatGPT, Claude, Gemini, Perplexity, and Grok, with automated threshold-triggered carryover and cross-vendor memory bridge; (2) **Atlas closed-loop Memory/CRM** — the internal AMG operational persistence layer that bidirectionally mirrors Atlas conversational memory into the AMG client-record CRM for continuous client context across sessions, implementing the broker-core event → proposal → approval → canonical memory → context packet → recall → correction loop that keeps client history, preferences, commitments, and in-flight work synchronized between Atlas agents, the Chamber AI Advantage member portal, and the Founding Partner subscriber-reporting surface.

This doctrine defines a **self-healing operational posture** for each of twelve infrastructure domains. The central design constraint is that the operator must not be interrupted for any failure that the system can diagnose and repair autonomously within its defined recovery envelope. Operator attention is the scarcest resource in the AMG system — every alert that fires without requiring action is cognitive debt that degrades decision quality over time.

**Core Architecture Decision:** All self-healing is implemented as a Central Watchdog daemon — a single long-running process on the VPS that implements the [IBM MAPE-K](http://www.cs.unibo.it/~lanese/work/microservices2022-autonomic-Guidi.pdf) feedback loop (Monitor, Analyze, Plan, Execute, Knowledge) across all twelve domains. This daemon writes structured incident logs, drives automated remediation, and escalates only when remediation fails twice or when action requires operator intent.

**The Three-Tier Response Model:**

| Tier | Condition | Action |
|------|-----------|--------|
| **Tier 0** | Auto-resolvable in <5 min | Silent repair + structured log only |
| **Tier 1** | Needs operator awareness | Slack DM summary after resolution |
| **Tier 2** | Requires operator decision | Immediate Slack alert + pause automation |

**Expected Outcomes (at full doctrine implementation):**
- ≥85% of incidents resolve autonomously at Tier 0
- Operator receives ≤3 Tier-2 pages per week
- MTTR for all domains ≤15 minutes
- Disk utilization maintained <70% without manual intervention
- Zero missed Git mirror divergences reaching production

**Out of Scope:** Security posture, credential rotation, access controls, and vulnerability management are deferred to DR-AMG-SECURITY-01. Where self-healing mechanisms create security surface area, this document flags the handoff explicitly.

---

## Section B — Framework Foundations {#section-b}

### B.1 Google Site Reliability Engineering

[Google's SRE model](https://sre.google), codified in the *Site Reliability Engineering* book (Beyer et al., 2016), establishes the foundational principle that operations is a software problem. Key constructs applied in this doctrine:

- **Error Budgets:** The acceptable degradation envelope before operator intervention is required. AMG's error budget per domain is defined in Section H.
- **Toil Elimination:** Any manual remediation that is automatable is by definition toil. This doctrine's goal is toil budget = zero for any failure occurring more than once.
- **SLOs over SLAs:** AMG has no external SLA contracts, but internal SLOs drive error budget calculations and escalation thresholds.

The [2025 SRE evolution](https://visualpathblogs.com/site-reliability-engineering/the-biggest-changes-in-site-reliability-engineering-practices-in-2025/) emphasizes AI-driven self-healing: "machine learning models are being used to forecast traffic surges, detect slow degradations in service performance, and initiate remediation steps like scaling resources or restarting components." This doctrine operationalizes that principle at the single-operator scale.

### B.2 Netflix Chaos Engineering

[Netflix's Principles of Chaos Engineering](https://www.infoq.com/news/2015/09/netflix-chaos-engineering/) define the discipline as "experimenting on a distributed system in order to build confidence in the system's capability to withstand turbulent conditions in production." The four principles directly applicable to AMG:

1. **Steady State Hypothesis:** For each domain, define what "healthy" looks like as a measurable output (not internal attributes).
2. **Vary Real-World Events:** Failure modes are cataloged from actual failure history, not hypothetical scenarios.
3. **Run Experiments in Production:** In a solo-operator environment with no staging, controlled failure injection is the only chaos option — implemented via Titan's test harness described in Domain 10.
4. **Automate Experiments Continuously:** Weekly fault injection drills (Section G) prove remediation paths remain live.

The [2025 evolution of chaos engineering](https://www.srao.blog/p/chaos-engineering-the-evolution-from) has moved toward AI-driven autonomous experiments. AMG adopts the principle selectively: fault injection is automated; blast radius is bounded to non-critical paths.

### B.3 IBM Autonomic Computing — MAPE-K Loop

The [MAPE-K architecture](https://www.conf-micro.services/2022/papers/paper_9.pdf) (Monitor, Analyze, Plan, Execute, Knowledge) from IBM Research (Kephart & Chess, 2003) is the foundational control loop for this doctrine. Every domain's self-healing behavior is implemented as a MAPE-K instance:

```
┌─────────────┐
│  KNOWLEDGE  │ ← Shared state store: incident history, thresholds, playbooks
└──────┬──────┘
       │
┌──────▼──────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   MONITOR   │───▶│   ANALYZE   │───▶│    PLAN     │───▶│   EXECUTE   │
│ (sensors)   │    │ (thresholds)│    │ (playbooks) │    │ (actuators) │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

The [2025 MAPE-K research](https://www.emergentmind.com/topics/mape-k-loop) shows that in microservice resilience applications, MAPE-K implementations reduced MTTR by 45% and improved availability from 99.2% to 99.8%. Applied to AMG's twelve domains, MAPE-K ensures every remediation action is policy-driven, logged, and fed back into the knowledge base.

### B.4 Self-Healing Microservices

[Current self-healing microservice literature](https://ijetcsit.org/index.php/ijetcsit/article/view/381) (Chintakindhi, 2025) identifies five core healing layers applicable to AMG's architecture:

1. **Data Collection Layer** — sensors emitting structured telemetry
2. **AI/ML Engine** — anomaly detection (at AMG scale: threshold-based rules, not ML models)
3. **Anomaly Detection Module** — adaptive thresholds, correlation analysis
4. **Self-Healing Module** — automated recovery actions
5. **Monitoring and Feedback Layer** — incident log feeds back into threshold calibration

### B.5 AgentOps 2025

[ZBrain's AgentOps framework](https://zbrain.ai/agentops/) (2025) defines seven principles for production autonomous agent systems. The most directly applicable to AMG:

- **Resilience:** "Bounded retries, backoff strategies, and safe fallbacks so the agent does not repeatedly call a failing tool or create runaway loops."
- **Versioning and Reproducibility:** "Tracking versions of prompts, flows, and model choices" — applied here to Titan session state and n8n workflow versions.
- **Feedback:** "Closes the communication loop between users, developers and the agents themselves" — operationalized in Section F.

[Kinde's AgentOps observability guide](https://kinde.com/learn/ai-for-software-engineering/ai-agents/agentops/) introduces the "lazy split retry" pattern — instead of re-running a full failed task, the trace identifies the single point of failure and retries only that step. This pattern is implemented in Domain 9 (n8n) and Domain 10 (Titan).

---

## Section C — The Seven Universal Principles of AMG Self-Healing {#section-c}

These principles apply uniformly across all twelve domains. Any remediation action that violates one of these principles is invalid and must be escalated to the operator regardless of the failure mode.

### Principle 1: Single Source of Truth

Every domain's desired state is defined in exactly one authoritative location. Git is truth for code and config. Supabase is truth for application data. R2 is truth for cold object storage. MIRROR_STATUS.md is truth for Titan's execution context. When any component drifts from its truth source, the truth source wins — never the running state. **Corollary:** The watchdog never modifies the truth source without explicit operator authorization (Tier 2 escalation).

### Principle 2: Bounded Autonomy

The system may act autonomously within a defined blast radius. Autonomous actions that could cause data loss, permanent deletion, external communication, or financial commitment require operator confirmation. The watchdog knows its own limits and stops at the boundary, not through the boundary. This is the direct application of [AgentOps HITL safeguards](https://zbrain.ai/agentops/): "HITL is a core feedback mechanism in AgentOps, ensuring that agents can pause, request clarification or hand off decisions to a human reviewer when uncertainty or risk is detected."

### Principle 3: Fail Loud, Never Fail Silent

Every failure event — whether auto-resolved or not — generates a structured log entry. Silent failures are categorically worse than noisy failures because they compound invisibly. A Tier-0 resolution that logs nothing is indistinguishable from a Tier-0 failure that was never detected. Every execution of the MAPE-K loop writes to `/var/log/amg/watchdog.jsonl`.

### Principle 4: Defense Against the Cascade

No remediation action may trigger a failure in a second domain. Before any autonomous action executes, the watchdog checks cross-domain dependencies. If a Caddy restart might interrupt an in-flight n8n webhook, the watchdog serializes the actions or escalates. Cascades are the [#1 self-healing anti-pattern](#section-i) — the remedy must not become a new incident.

### Principle 5: Idempotent Remediation

Every automated fix script must be safe to run multiple times. If the disk cleanup script runs twice because of a timing edge case, it must not delete files that were restored by the first run. If the Git repair script runs on an already-healthy repo, it must exit cleanly. Scripts that are not idempotent are bugs, not features.

### Principle 6: The Learning Budget

Every incident that requires Tier-2 escalation generates a mandatory 30-minute post-mortem (Section F). If the same failure mode triggers Tier-2 escalation twice without an improvement to the playbook, it is a doctrine failure, not an infrastructure failure. The knowledge base must grow after every incident.

### Principle 7: ADHD-Compatible Signal Design

The operator receives a maximum of one Slack message per incident cluster. Multiple sub-failures within the same root cause are grouped into a single notification. Dashboards are not mandatory reading — the watchdog is the only required interface. All alerts include: (1) what broke, (2) what was done about it, (3) what the operator needs to decide, if anything. No alert fires without a clear next action.

---

## Section D — Domain-by-Domain Implementation Spec {#section-d}

---

### Domain 1: Git Mirror Pipeline Integrity

**Topology:** Mac working tree → Mac local repo → VPS bare repo (`/opt/repos/amg.git`) → GitHub remote

#### Detection

| Signal | Mechanism | Threshold |
|--------|-----------|-----------|
| Diverged commits | `git rev-list --count HEAD..origin/main` | > 0 for >5 min |
| Dirty working tree | `git status --porcelain` | Non-empty for >15 min |
| Bare repo corruption | `git fsck --full` exit code ≠ 0 | Any failure |
| Push failure | SSH exit code from push cron | Any failure |
| Stale last-push timestamp | `/var/log/amg/git-sync.log` | No push in >2 hours |

Watchdog check interval: every 5 minutes via systemd timer.

#### Remediation Sequence

```bash
#!/bin/bash
# /opt/amg/scripts/git-heal.sh
# Idempotent Git mirror repair script

set -euo pipefail
LOG="/var/log/amg/watchdog.jsonl"
BARE_REPO="/opt/repos/amg.git"
WORK_REPO="/opt/amg/workspace"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

log_event() {
  echo "{\"ts\":\"$TIMESTAMP\",\"domain\":\"git\",\"event\":\"$1\",\"detail\":\"$2\"}" >> "$LOG"
}

# Step 1: Verify bare repo integrity
if ! git -C "$BARE_REPO" fsck --full 2>/dev/null; then
  log_event "BARE_REPO_CORRUPT" "Attempting repair via gc"
  git -C "$BARE_REPO" gc --prune=now
  if ! git -C "$BARE_REPO" fsck --full 2>/dev/null; then
    log_event "BARE_REPO_UNRECOVERABLE" "Escalating: fsck failed after gc"
    exit 2  # Tier 2: operator must re-clone
  fi
fi

# Step 2: Fetch from GitHub to bare repo
git -C "$BARE_REPO" fetch origin --prune 2>/dev/null \
  && log_event "FETCH_OK" "GitHub → bare repo synced" \
  || log_event "FETCH_WARN" "GitHub fetch failed (network?)"

# Step 3: Check working tree for stale state
if [[ -d "$WORK_REPO" ]]; then
  DIVERGE=$(git -C "$WORK_REPO" rev-list --count HEAD..origin/main 2>/dev/null || echo "0")
  if [[ "$DIVERGE" -gt 0 ]]; then
    log_event "DIVERGE_DETECTED" "Working tree is $DIVERGE commits behind"
    git -C "$WORK_REPO" fetch origin
    git -C "$WORK_REPO" merge --ff-only origin/main \
      && log_event "FF_MERGE_OK" "Fast-forward merge applied" \
      || { log_event "FF_MERGE_FAIL" "Cannot fast-forward, escalating"; exit 2; }
  fi
fi

log_event "GIT_HEALTHY" "Mirror pipeline verified clean"
exit 0
```

**Systemd Timer:**
```ini
# /etc/systemd/system/amg-git-heal.timer
[Timer]
OnCalendar=*:0/5
Persistent=true

# /etc/systemd/system/amg-git-heal.service
[Service]
Type=oneshot
ExecStart=/opt/amg/scripts/git-heal.sh
StandardOutput=null
StandardError=journal
```

#### Escalation Path

| Condition | Escalation Level | Action |
|-----------|-----------------|--------|
| `git fsck` fails after `git gc` | Tier 2 | Slack alert: "Bare repo corrupted — operator must re-clone from GitHub" |
| Fast-forward merge impossible | Tier 2 | Slack alert: "Diverged non-FF history on VPS — manual resolution required" |
| No successful push for >8 hours | Tier 1 | Slack summary: "Git push dry streak — check Mac ↔ VPS SSH" |

#### Watchdog (Who Watches the Watcher)

The git-heal timer is supervised by systemd. The watchdog daemon checks `systemctl status amg-git-heal.timer` as part of its own health loop. If the timer is inactive, it restarts it. The watchdog daemon itself is supervised by a separate `amg-watchdog.service` with `Restart=always`.

#### Failure Catalog

| Failure Mode | MTTR | Root Cause |
|-------------|------|-----------|
| SSH key expired / rotated | 30 min | Requires operator to update `.ssh/authorized_keys` |
| Bare repo pack file corruption | 10 min | Automated: `git gc --prune=now` + `git fsck` |
| VPS disk full blocking push | 5 min | Cascades from Domain 2; Domain 2 heals first |
| GitHub API outage | N/A | No remediation possible; watchdog suppresses git alerts during known GitHub outages |
| Mac working tree has uncommitted changes | 0 min | Watchdog only detects; does not auto-commit (out of autonomous scope) |

#### Implementation Notes

- SSH push from Mac uses a dedicated deploy key, not personal key — handoff to DR-AMG-SECURITY-01
- Bare repo created with: `git init --bare /opt/repos/amg.git`
- Mac uses a post-commit hook to trigger push: `~/.git/hooks/post-commit`
- MIRROR_STATUS.md updated by git-heal.sh on every run with timestamp and commit hash

---

### Domain 2: Disk / Storage Hygiene

**Topology:** VPS ext4 filesystem (primary `/`), Docker layers at `/var/lib/docker`, n8n data at `/opt/n8n`, logs at `/var/log`, venvs at `/opt/amg/venvs`, tmp at `/tmp`

#### Detection

| Signal | Threshold | Mechanism |
|--------|-----------|-----------|
| Root partition utilization | >70% → Tier-1 sweep; >85% → Tier-2 alert | `df -h /` every 15 min |
| Docker layer accumulation | >20 GB in `/var/lib/docker` | `docker system df` check |
| Log directory | Any single log file >500 MB | `find /var/log -size +500M` |
| Stale venvs | Python venv not accessed in >30 days | `find /opt/amg/venvs -atime +30d` |
| n8n execution data | n8n DB >10 GB | SQLite `PRAGMA page_count` check |

#### Remediation Sequence

```bash
#!/bin/bash
# /opt/amg/scripts/disk-heal.sh
# Run daily via systemd timer; emergency run on >70% utilization

set -euo pipefail
LOG="/var/log/amg/watchdog.jsonl"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
THRESHOLD_PCT=70
R2_BUCKET="amg-cold-archive"  # Cold offload target

log_event() {
  echo "{\"ts\":\"$TIMESTAMP\",\"domain\":\"disk\",\"event\":\"$1\",\"detail\":\"$2\"}" >> "$LOG"
}

get_disk_pct() { df / | awk 'NR==2{print int($5)}'; }

BEFORE=$(get_disk_pct)
log_event "DISK_SWEEP_START" "Utilization: ${BEFORE}%"

# Phase 1: Docker cleanup (safe)
DOCKER_BEFORE=$(docker system df --format '{{.Size}}' 2>/dev/null | head -1)
docker system prune -f --filter "until=168h" 2>/dev/null  # Remove >7-day old unused
docker image prune -a -f --filter "until=168h" 2>/dev/null
docker builder prune -f --filter "until=72h" 2>/dev/null
docker volume prune -f 2>/dev/null
log_event "DOCKER_PRUNED" "Before: $DOCKER_BEFORE"

# Phase 2: Log rotation enforcement (respects logrotate config)
find /var/log -name "*.log" -size +100M -not -name "watchdog.jsonl" \
  -exec gzip -f {} \; 2>/dev/null
find /var/log -name "*.gz" -mtime +14 -delete 2>/dev/null
log_event "LOGS_ROTATED" "Compressed files >100MB, deleted >14d gz files"

# Phase 3: Tmp cleanup
find /tmp -mtime +2 -delete 2>/dev/null
log_event "TMP_CLEANED" "Removed /tmp entries older than 2 days"

# Phase 4: Stale venvs
STALE_VENVS=$(find /opt/amg/venvs -maxdepth 1 -type d -atime +30 -not -name "venvs" 2>/dev/null)
if [[ -n "$STALE_VENVS" ]]; then
  # Offload manifest to R2 before deletion (names + atime)
  echo "$STALE_VENVS" | while read -r venv; do
    VENV_NAME=$(basename "$venv")
    log_event "STALE_VENV_REMOVED" "Removed $VENV_NAME (30d+ unused)"
    rm -rf "$venv"
  done
fi

# Phase 5: Check post-sweep; escalate if still high
AFTER=$(get_disk_pct)
log_event "DISK_SWEEP_END" "After: ${AFTER}%"

if [[ "$AFTER" -gt 85 ]]; then
  log_event "DISK_CRITICAL" "Still at ${AFTER}% — checking for large files"
  # Surface top-10 space consumers for operator
  TOP10=$(du -sh /* 2>/dev/null | sort -rh | head -10)
  log_event "DISK_TOP10" "$TOP10"
  exit 2  # Tier 2 escalation
elif [[ "$AFTER" -gt 70 ]]; then
  exit 1  # Tier 1: report but don't alert urgently
fi

exit 0
```

**Cold Offload to R2:**
Files older than 90 days in `/opt/amg/archive` are synced to R2 using the AWS S3-compatible CLI:
```bash
aws s3 sync /opt/amg/archive/ s3://$R2_BUCKET/archive/ \
  --endpoint-url https://<accountid>.r2.cloudflarestorage.com \
  --delete
```
This runs weekly. After sync, verified files are removed locally. Verification uses `aws s3 ls` count check before deletion.

#### Escalation Path

| Condition | Level | Action |
|-----------|-------|--------|
| >85% post-sweep | Tier 2 | Slack: "Disk at ${AFTER}% after cleanup — top consumers attached" |
| >95% (critical) | Tier 2 immediate | Halt all non-essential writes; operator must act within 30 min |
| R2 sync failure | Tier 1 | Log and retry next cycle; if 3 consecutive failures → Tier 2 |

#### Watchdog

- Disk check timer: every 15 minutes (not just daily)
- Emergency trigger: if utilization crosses 70% between scheduled sweeps, disk-heal.sh runs immediately
- Systemd `amg-disk-monitor.service` polls `df /` and triggers emergency sweep

#### Failure Catalog

| Failure Mode | MTTR | Notes |
|-------------|------|-------|
| Runaway n8n execution log | 5 min | n8n configured with max_execution_log_size; auto-truncated |
| Docker build cache accumulation | 10 min | Automated prune with 72h threshold |
| R2 sync blocked by credential expiry | 30 min | → DR-AMG-SECURITY-01 handoff |
| VPS tmp full from crashed process | 5 min | Auto-clean via timer |
| Database WAL file accumulation | 15 min | Supabase managed; VPS Postgres vacuum cron in Domain 6 |

---

### Domain 3: Cloudflare R2 Lifecycle Management

**Topology:** R2 bucket `amg-cold-archive` (cold offload), `amg-assets` (served assets), `amg-backups` (database snapshots)

#### Detection

| Signal | Threshold | Mechanism |
|--------|-----------|-----------|
| Bucket size growth >10% week-over-week | Alert | R2 API usage metrics via Cloudflare dashboard API |
| Objects without lifecycle rule | Any | Weekly audit script |
| Incomplete multipart uploads | >7 days old | Built-in R2 lifecycle default |
| Backup freshness | Latest backup >25 hours old | Timestamp check via R2 API |
| Integrity check failure | Any | Weekly `aws s3api head-object` checksum verification |

#### Lifecycle Rules (Configured via Cloudflare API)

Per [Cloudflare R2 lifecycle documentation](https://developers.cloudflare.com/r2/buckets/object-lifecycles/):

```json
{
  "Rules": [
    {
      "ID": "Archive logs after 90 days",
      "Filter": {"Prefix": "logs/"},
      "Transitions": [{"Days": 30, "StorageClass": "INFREQUENT_ACCESS"}],
      "Expiration": {"Days": 90}
    },
    {
      "ID": "Rotate DB backups",
      "Filter": {"Prefix": "backups/"},
      "Expiration": {"Days": 30}
    },
    {
      "ID": "Abort stale multipart uploads",
      "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}
    },
    {
      "ID": "Cold archive assets transition",
      "Filter": {"Prefix": "archive/"},
      "Transitions": [{"Days": 7, "StorageClass": "INFREQUENT_ACCESS"}]
    }
  ]
}
```

Apply via:
```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket amg-cold-archive \
  --lifecycle-configuration file://r2-lifecycle.json \
  --endpoint-url https://<accountid>.r2.cloudflarestorage.com
```

#### Integrity Verification Script

```bash
#!/bin/bash
# /opt/amg/scripts/r2-verify.sh
# Weekly integrity check on critical R2 objects

BUCKET="amg-backups"
ENDPOINT="https://<accountid>.r2.cloudflarestorage.com"
LOG="/var/log/amg/watchdog.jsonl"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Verify latest backup exists and is fresh
LATEST=$(aws s3 ls "s3://${BUCKET}/daily/" \
  --endpoint-url "$ENDPOINT" | sort | tail -1 | awk '{print $4}')

if [[ -z "$LATEST" ]]; then
  echo "{\"ts\":\"$TIMESTAMP\",\"domain\":\"r2\",\"event\":\"BACKUP_MISSING\",\"detail\":\"No backup found\"}" >> "$LOG"
  exit 2
fi

# Check age < 25 hours
BACKUP_TS=$(aws s3api head-object --bucket "$BUCKET" \
  --key "daily/$LATEST" \
  --endpoint-url "$ENDPOINT" \
  --query 'LastModified' --output text 2>/dev/null)
AGE_HOURS=$(( ($(date +%s) - $(date -d "$BACKUP_TS" +%s)) / 3600 ))

if [[ "$AGE_HOURS" -gt 25 ]]; then
  echo "{\"ts\":\"$TIMESTAMP\",\"domain\":\"r2\",\"event\":\"BACKUP_STALE\",\"detail\":\"Latest backup ${AGE_HOURS}h old\"}" >> "$LOG"
  exit 2
fi

echo "{\"ts\":\"$TIMESTAMP\",\"domain\":\"r2\",\"event\":\"R2_HEALTHY\",\"detail\":\"Backup $LATEST is ${AGE_HOURS}h old\"}" >> "$LOG"
exit 0
```

#### Restore Drill Protocol

Monthly restore drill (first Sunday, 9 AM):
1. Download latest backup from `amg-backups/daily/` to VPS `/tmp/restore-test/`
2. Restore to a test Postgres database: `pg_restore -d amg_test /tmp/restore-test/latest.dump`
3. Run schema validation query: `SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'`
4. Log result to watchdog; if table count matches expected baseline → DRILL_PASS

#### Escalation Path

| Condition | Level | Action |
|-----------|-------|--------|
| Backup >25 hours old | Tier 2 | Immediate alert: "Backup gap detected" |
| Lifecycle rule missing | Tier 1 | Auto-reapply rule config; log event |
| Restore drill failure | Tier 2 | Alert: "Restore drill failed — backup integrity uncertain" |

#### Failure Catalog

| Failure Mode | MTTR | Notes |
|-------------|------|-------|
| Cloudflare R2 regional outage | N/A | No remediation; operator notified; zero egress fees mean no backup cost risk |
| Credential expiry for R2 CLI | 30 min | → DR-AMG-SECURITY-01 |
| Lifecycle rule drift (dashboard reset) | 5 min | Auto-reapply from config file |
| Incomplete multipart stacking costs | Auto | 7-day abort rule eliminates this |

---

### Domain 4: Slack Signal-to-Noise

**Topology:** Slack workspace with AMG operational channels; n8n webhook sources; Titan status posts; external API webhook notifications

#### Detection

| Signal | Threshold | Mechanism |
|--------|-----------|-----------|
| Channels with >0 messages, 0 human responses in 30 days | Auto-archive candidate | Slack API channel audit |
| Bot message rate >10/hour in a channel | Noise threshold | n8n Slack node message counter |
| Unread DM from watchdog | Operator confirmation rate <80% | Watchdog delivery log |

#### Noise Suppression Architecture

**Rule 1 — Deduplication:** All watchdog Slack messages route through a dedup buffer. If the same failure mode fires within 1 hour, the second notification is suppressed and appended to the first thread (`:thread_reply` action).

**Rule 2 — Grouped Summaries:** Tier-0 events are batched into a single daily digest posted at 08:00 EST to `#amg-ops-digest`. Format:

```
✅ AMG Daily Ops Digest — [DATE]
• [12] Tier-0 auto-heals: Git sync (×3), Docker prune (×1), Caddy health (×8)
• [0] Tier-1 summaries
• [0] Tier-2 alerts
System health: GREEN
```

**Rule 3 — Bot Channel Isolation:** All n8n workflow notifications post to `#amg-n8n-log` not `#general`. Watchdog posts to `#amg-ops-alerts`. Cross-posting is prohibited.

**Rule 4 — Actionability Gate:** Before any message is sent, the watchdog applies: "Does this message require the operator to DO something?" If no → Tier-0 log only. If yes → include exactly one CTA button.

**n8n Noise Filter Workflow:**

```json
{
  "name": "Slack Noise Filter",
  "nodes": [
    {"type": "Webhook", "name": "Receive notification"},
    {"type": "Function", "name": "Classify signal",
     "code": "const msg = $input.item.json; const isActionable = msg.tier >= 2; return [{...msg, route: isActionable ? 'alert' : 'digest'}]"},
    {"type": "Switch", "on": "route",
     "cases": {"alert": "→ #amg-ops-alerts", "digest": "→ buffer"}}
  ]
}
```

#### Channel Hygiene Automation

Weekly Sunday audit via n8n + Slack API:
1. List all channels: `slack.conversations.list`
2. For each channel: check last human message date
3. If >30 days with no human messages → post warning: "This channel will be archived in 7 days unless activity detected"
4. If >37 days → `slack.conversations.archive`

**Exclusions list** (never auto-archive): `#general`, `#amg-ops-alerts`, `#amg-ops-digest`, `#amg-n8n-log`

#### Escalation Path

No Tier-2 for noise/archival. Worst case: a legitimate channel gets auto-archived and is restored by operator (`/unarchive`).

#### Failure Catalog

| Failure Mode | MTTR | Notes |
|-------------|------|-------|
| Watchdog Slack webhook expired | 5 min | Watchdog posts to backup email if Slack fails 3x |
| Dedup buffer full (>100 suppressed events) | Auto | Buffer flushes as digest; operator sees summary |
| Wrong channel auto-archived | 1 min | Operator runs `/unarchive`; restoration is instant |

---

### Domain 5: AI Voice / Chat Resilience

**Topology:** WebSocket-based STT pipeline → RNNoise → LLM API → TTS API → audio output; session state held in MCP memory layer

#### Detection

| Signal | Threshold | Mechanism |
|--------|-----------|-----------|
| WebSocket close code ≠ 1000 (normal) | Any | Client-side close handler |
| STT silence timeout | >10 seconds no transcript | STT API timeout callback |
| TTS chunk delay | >3 seconds between chunks | Client-side TTS buffer monitor |
| RNNoise output silent for >5 seconds | During active session | Audio level monitor |
| Session state divergence from MCP | Context window mismatch | Integrity check on session resume |
| Barge-in not acknowledged | >500ms | TTS cancel message unacknowledged |

#### WebSocket Reconnection Implementation

Per [OneUptime's production WebSocket guide](https://oneuptime.com/blog/post/2026-01-24-websocket-reconnection-logic/), the AMG voice client implements:

```javascript
// /opt/amg/voice/ws-client.js
class AMGVoiceSocket {
  constructor(url) {
    this.url = url;
    this.initialDelay = 1000;
    this.maxDelay = 30000;
    this.multiplier = 1.5;
    this.currentDelay = this.initialDelay;
    this.reconnectAttempts = 0;
    this.maxAttempts = 10;
    this.sessionState = {};  // Recovered from MCP on reconnect
    this.messageQueue = [];
    this.connect();
  }

  connect() {
    this.ws = new WebSocket(this.url);
    this.ws.onopen = () => {
      this.currentDelay = this.initialDelay;
      this.reconnectAttempts = 0;
      this.recoverSessionState();  // Replay from MCP
      this.flushQueue();
    };
    this.ws.onclose = (e) => {
      if (e.code !== 1000) this.scheduleReconnect();
    };
  }

  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxAttempts) {
      this.fallbackToHTTP();  // See below
      return;
    }
    const jitter = (Math.random() * 0.2 - 0.1);
    const delay = Math.min(this.currentDelay * (1 + jitter), this.maxDelay);
    setTimeout(() => this.connect(), delay);
    this.currentDelay = Math.min(this.currentDelay * this.multiplier, this.maxDelay);
    this.reconnectAttempts++;
  }

  recoverSessionState() {
    // Pull last conversation context from MCP server
    fetch('/mcp/session/recover', {
      method: 'POST',
      body: JSON.stringify({sessionId: this.sessionId})
    }).then(r => r.json()).then(state => {
      this.sessionState = state;
    });
  }

  fallbackToHTTP() {
    // Degrade to REST-based TTS (higher latency, no streaming)
    console.warn('WS failed after 10 attempts — degrading to HTTP TTS');
    this.mode = 'http_fallback';
  }
}
```

#### STT/TTS Fallback Chain

| Level | Provider | Trigger Condition |
|-------|----------|------------------|
| Primary | Deepgram (WebSocket streaming) | Default |
| Fallback 1 | Deepgram REST | WS fails after 3 reconnects |
| Fallback 2 | Whisper local (on-VPS) | Deepgram API down |

**Barge-in Recovery:**
When user speaks mid-response, the TTS stream must be cancelled within 500ms. Implementation:
```javascript
// Send cancel message via WebSocket
ws.send(JSON.stringify({type: 'tts_cancel', utterance_id: currentUtteranceId}));
// If no acknowledgement in 500ms, force-close audio output and re-init session
```

#### RNNoise Degradation Handling

RNNoise runs as a pre-processing filter before STT input. If RNNoise crashes or produces silent output:
1. Detection: Audio level meter shows <-60 dBFS for >5 seconds during active session
2. Remediation: Kill and restart `rnnoise-filter` process via systemd; fallback to raw audio passthrough
3. Quality penalty: STT accuracy drops ~15% in noisy environments; acceptable for continuity

#### Escalation Path

| Condition | Level | Action |
|-----------|-------|--------|
| All WS reconnect attempts failed | Tier 1 | Notify: "Voice session degraded to HTTP mode — quality reduced" |
| Whisper local OOM crash | Tier 2 | Alert: "STT unavailable — voice services offline" |
| Session state unrecoverable from MCP | Tier 1 | New session started; user notified of context loss |

#### Failure Catalog

| Failure Mode | MTTR | Notes |
|-------------|------|-------|
| WebSocket timeout (network flap) | <5 sec | Auto-reconnect with backoff |
| Deepgram API outage | 2 min | Fallback to local Whisper |
| TTS synthesis queue backup | 30 sec | Circuit breaker flushes queue; TTS chunk split reduced |
| Barge-in lost packet | 500 ms | Force-cancel fallback |
| RNNoise SIGSEGV | 10 sec | Systemd restart + raw audio passthrough |

---

### Domain 6: Supabase / Database Resilience

**Topology:** Supabase managed Postgres (primary, cloud) → Supavisor connection pooler → application connections; VPS Postgres (mirror, failover) per Multi-Lane Doctrine

#### Detection

| Signal | Threshold | Mechanism |
|--------|-----------|-----------|
| Supabase connection pool saturation | >80% pool used | Supavisor metrics query |
| Query latency P99 | >2 seconds | Application-layer timing |
| Supabase API HTTP 503 | Any | Health check endpoint every 60 sec |
| VPS mirror lag | >5 minutes behind | `SELECT NOW() - pg_last_xact_replay_timestamp()` |
| Backup age | >25 hours | R2 backup timestamp check (Domain 3) |
| Connection leak | `pg_stat_activity` idle connections >50 | Query: `SELECT count(*) FROM pg_stat_activity WHERE state='idle' AND wait_event_type IS NULL` |

#### Connection Pool Health

Per [Supabase Supavisor documentation](https://supabase.com/blog/supavisor-postgres-connection-pooler), AMG uses transaction mode (port 6543) for all application connections. Direct connections (port 5432) are reserved for admin operations and migrations only.

**Pool sizing formula:** `pool_size = (cores × 2) + 2` → for VPS with 12 cores: `pool_size = 26`

**Auto-retry with exponential backoff:**
```javascript
// /opt/amg/lib/db.js
async function queryWithRetry(query, params, maxAttempts = 3) {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await pool.query(query, params);
    } catch (err) {
      if (err.code === '57P03' || err.code === 'ECONNREFUSED') {
        // Connection unavailable — try VPS mirror
        if (attempt === maxAttempts - 1) return await vpsPool.query(query, params);
        await sleep(Math.pow(2, attempt) * 500);  // 500ms, 1000ms, 2000ms
      } else {
        throw err;
      }
    }
  }
}
```

#### Multi-Lane Failover to VPS Postgres

When Supabase is unavailable:
1. Watchdog detects 3 consecutive failed health checks (3 minutes)
2. Application connection string switches from Supabase to VPS Postgres mirror
3. VPS Postgres is kept current via pg_logical replication with 5-minute max lag
4. n8n environment variable `DATABASE_URL` updated via `systemctl restart n8n`
5. Watchdog logs failover event; operator notified via Tier-1 summary

**Replication setup (run once during provisioning):**
```sql
-- On Supabase (publisher)
CREATE PUBLICATION amg_pub FOR ALL TABLES;

-- On VPS Postgres (subscriber)
CREATE SUBSCRIPTION amg_sub
  CONNECTION 'host=db.supabase.co user=postgres password=... dbname=postgres'
  PUBLICATION amg_pub;
```

#### Idle Connection Cleanup

```bash
#!/bin/bash
# Run every 30 minutes via watchdog
psql $DATABASE_URL -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE state = 'idle'
    AND wait_event_type IS NULL
    AND query_start < NOW() - INTERVAL '10 minutes'
    AND pid <> pg_backend_pid();"
```

#### VPS Postgres Vacuum Cron

```bash
# Weekly VACUUM ANALYZE to prevent table bloat
0 3 * * 0 psql $VPS_DATABASE_URL -c "VACUUM ANALYZE;"
```

#### Escalation Path

| Condition | Level | Action |
|-----------|-------|--------|
| Supabase down >3 min | Tier 1 | Auto-failover to VPS; operator notified after |
| VPS mirror >30 min lag | Tier 2 | Alert: "Mirror out of sync — failover data may be stale" |
| Backup missing >25 hours | Tier 2 | Alert: "Backup gap — initiate manual backup immediately" |
| Connection pool at 100% | Tier 2 | Alert: "Pool exhausted — connections being dropped" |

#### Failure Catalog

| Failure Mode | MTTR | Notes |
|-------------|------|-------|
| Supabase maintenance window | Auto | Failover to VPS; auto-return when Supabase healthy |
| Connection string misconfiguration | 5 min | n8n restart with corrected env var |
| Supabase project paused (inactivity) | 5 min | API call to unpause; Supabase free tier pauses after 1 week |
| Replication slot bloat | 30 min | Watchdog monitors replication slot LSN lag; → operator if >1 GB |
| pg_logical replication conflict | 30 min | Escalate to operator; data divergence risk |

---

### Domain 7: Caddy Reverse Proxy

**Topology:** Caddy v2 on VPS port 443 → upstreams: n8n (port 5678), AI voice API (port 8080), custom app services (ports 3000-3010)

#### Detection

| Signal | Threshold | Mechanism |
|--------|-----------|-----------|
| 502 error rate | >5% of requests in 60 sec | Caddy access log parser |
| Upstream health check failure | Any upstream failing | Active health checks (every 30s) |
| TLS cert expiry | <14 days remaining | `openssl s_client` check |
| Config file drift | Caddyfile checksum change outside deploy | `md5sum` compare against git-tracked hash |
| Caddy process missing | Process not in `ps` | systemd status check |

#### Caddyfile with Health Checks

Per [Caddy reverse proxy documentation](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy):

```caddyfile
# /etc/caddy/Caddyfile
{
  admin off
  log {
    output file /var/log/caddy/access.log {
      roll_size 100mb
      roll_keep 5
    }
    format json
  }
}

n8n.amg.internal {
  reverse_proxy localhost:5678 {
    health_uri /healthz
    health_interval 30s
    health_timeout 5s
    health_status 200

    lb_policy round_robin
    lb_retries 2

    fail_duration 30s
    max_fails 3
    unhealthy_status 502 503

    @timeout {
      not header Connection *
    }
  }
}

voice.amg.internal {
  reverse_proxy localhost:8080 {
    health_uri /health
    health_interval 15s
    health_timeout 3s
  }
}
```

#### 502 Auto-Recovery Sequence

```bash
#!/bin/bash
# /opt/amg/scripts/caddy-heal.sh
# Triggered by watchdog when 502 rate >5%

LOG="/var/log/amg/watchdog.jsonl"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

log_event() {
  echo "{\"ts\":\"$TIMESTAMP\",\"domain\":\"caddy\",\"event\":\"$1\",\"detail\":\"$2\"}" >> "$LOG"
}

# Step 1: Identify which upstream is failing
# Parse last 100 Caddy access log lines for 502s
FAILING_UPSTREAM=$(tail -100 /var/log/caddy/access.log | \
  python3 -c "
import sys, json
for line in sys.stdin:
  try:
    entry = json.loads(line)
    if entry.get('status') == 502:
      print(entry.get('upstream_address', 'unknown'))
  except: pass
" | sort | uniq -c | sort -rn | head -1 | awk '{print $2}')

log_event "502_UPSTREAM" "Identified failing upstream: $FAILING_UPSTREAM"

# Step 2: Try to restart the upstream service
case "$FAILING_UPSTREAM" in
  *5678*) systemctl restart n8n; log_event "N8N_RESTARTED" "n8n restarted";;
  *8080*) systemctl restart amg-voice; log_event "VOICE_RESTARTED" "voice service restarted";;
  *3000*|*3001*|*3002*|*3003*)
    PORT=$(echo $FAILING_UPSTREAM | grep -oP ':\K[0-9]+')
    systemctl restart "amg-app-${PORT}"
    log_event "APP_RESTARTED" "Service on port $PORT restarted";;
  *)
    log_event "UNKNOWN_UPSTREAM" "Cannot identify upstream to restart"
    exit 2;;
esac

# Step 3: Wait 10 seconds and re-check
sleep 10
RATE=$(tail -50 /var/log/caddy/access.log | \
  python3 -c "import sys,json; lines=[json.loads(l) for l in sys.stdin if l.strip()]; total=len(lines); bad=sum(1 for l in lines if l.get('status')==502); print(f'{bad/total*100:.1f}' if total else '0')")

if (( $(echo "$RATE > 5" | bc -l) )); then
  log_event "502_PERSISTS" "Rate still ${RATE}% — escalating"
  exit 2
fi

log_event "CADDY_RECOVERED" "502 rate now ${RATE}%"
exit 0
```

#### TLS Certificate Monitoring

```bash
#!/bin/bash
# /opt/amg/scripts/tls-check.sh
DOMAINS=("n8n.amg.internal" "voice.amg.internal")

for DOMAIN in "${DOMAINS[@]}"; do
  EXPIRY=$(openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" \
    </dev/null 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | \
    cut -d= -f2)
  DAYS_LEFT=$(( ($(date -d "$EXPIRY" +%s) - $(date +%s)) / 86400 ))
  
  if [[ "$DAYS_LEFT" -lt 14 ]]; then
    # Force Caddy to renew
    curl -s http://localhost:2019/load \
      -H "Content-Type: application/json" \
      -d "{\"@id\":\"renew_$DOMAIN\"}"
    echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"domain\":\"caddy\",\"event\":\"TLS_RENEW_TRIGGERED\",\"detail\":\"$DOMAIN expires in $DAYS_LEFT days\"}" >> /var/log/amg/watchdog.jsonl
  fi
done
```

#### Config Drift Detection

```bash
# On every Caddyfile save via git hook:
md5sum /etc/caddy/Caddyfile > /opt/amg/.caddyfile.md5

# Watchdog checks every 10 min:
CURRENT=$(md5sum /etc/caddy/Caddyfile | awk '{print $1}')
EXPECTED=$(cat /opt/amg/.caddyfile.md5 | awk '{print $1}')
if [[ "$CURRENT" != "$EXPECTED" ]]; then
  # Restore from git
  git -C /etc/caddy checkout Caddyfile
  caddy reload --config /etc/caddy/Caddyfile
  log_event "CADDYFILE_DRIFT" "Config restored from git"
fi
```

#### Escalation Path

| Condition | Level | Action |
|-----------|-------|--------|
| 502 persists after upstream restart | Tier 2 | Alert: "Caddy 502 unresolved — upstream may be down" |
| TLS cert expires within 3 days | Tier 2 | Immediate: "Certificate expiring — HTTPS will break" |
| Caddy process dead | Tier 0 | Auto-restart via systemd (`Restart=always`) |
| Config drift, git restore fails | Tier 2 | Alert: "Caddyfile restored from git; verify manually" |

#### Failure Catalog

| Failure Mode | MTTR | Notes |
|-------------|------|-------|
| Caddy crash | <10 sec | systemd Restart=always |
| Upstream OOM kill (502 storm) | 30 sec | caddy-heal.sh restarts upstream |
| TLS ACME challenge failure | 2 min | Caddy retry logic; if blocked by rate limit → 7 days |
| Config syntax error after manual edit | 1 min | `caddy validate` pre-reload hook rejects invalid config |

---

### Domain 8: n8n Workflow Integrity

**Topology:** n8n v1.x on VPS, SQLite (or Postgres) backend, ~30 active workflows, external API integrations (Slack, OpenAI, Deepgram, Supabase, custom webhooks)

#### Detection

| Signal | Threshold | Mechanism |
|--------|-----------|-----------|
| Failed execution not retried | >0 failures on "critical" tagged workflows | n8n webhook + error handler workflow |
| Credential expiry | Token TTL <24 hours | Credential audit workflow (daily) |
| Workflow version drift | Workflow JSON hash differs from git | Weekly git-n8n-audit.sh |
| n8n process OOM | systemd restart count >1 | `systemctl show n8n --property=NRestarts` |
| Execution queue depth | >20 pending executions | n8n API: `GET /api/v1/executions?status=waiting` |

#### Error Classification and Remediation

Inspired by [the self-healing n8n workflow built by the community](https://www.reddit.com/r/n8n/comments/1se31kx/built_a_selfhealing_workflow_system_that_detects/), AMG implements an error classification layer:

```javascript
// Error handler workflow Function node
const error = $input.item.json.error;
const context = $input.item.json.execution;

const classify = (err) => {
  if (err.code === 429 || err.message?.includes('rate limit')) return 'RATE_LIMIT';
  if (err.code === 401 || err.message?.includes('unauthorized')) return 'AUTH_EXPIRED';
  if (err.code === 400 || err.message?.includes('schema')) return 'SCHEMA_DRIFT';
  if (err.code >= 500 || err.message?.includes('timeout')) return 'TRANSIENT_5XX';
  return 'UNKNOWN';
};

const remediation = {
  'RATE_LIMIT': {action: 'exponential_backoff', initialDelay: 30000, maxAttempts: 5},
  'AUTH_EXPIRED': {action: 'refresh_token', credentialId: context.credentialId},
  'SCHEMA_DRIFT': {action: 'notify_operator', tier: 2},
  'TRANSIENT_5XX': {action: 'retry', delay: 5000, maxAttempts: 3},
  'UNKNOWN': {action: 'notify_operator', tier: 2}
};

return [{
  errorType: classify(error),
  remediation: remediation[classify(error)],
  workflowId: context.workflowId,
  executionId: context.executionId
}];
```

**Retry Implementation:**
- Rate limit errors: exponential backoff starting at 30 seconds, max 5 attempts
- Auth errors: trigger credential refresh workflow before retry
- Transient 5xx: immediate retry × 1, then 5-second delay retry × 2
- All other errors after 2 failed auto-repair attempts → Tier-2 escalation

Per the [n8n community node `n8n-nodes-vialos`](https://community.n8n.io/t/self-healing-wrapper-node-that-auto-repairs-failed-http-api-calls-with-pattern-learning/285177), pattern learning stores successful repair strategies to resolve identical failures in <1ms on recurrence.

#### Credential Expiry Audit Workflow

Runs daily at 06:00 EST:
1. Query n8n credentials API: `GET /api/v1/credentials`
2. For OAuth2 tokens: check `expiresAt` field
3. For API keys: query external API with test call (HEAD /ping or equivalent)
4. Log results; if any credential expires in <24 hours → auto-refresh or Tier-1 alert

#### Workflow Drift Detection

```bash
#!/bin/bash
# /opt/amg/scripts/n8n-audit.sh
# Export all workflows and compare to git-tracked versions

N8N_API="http://localhost:5678/api/v1"
N8N_KEY="$N8N_API_KEY"
REPO_PATH="/opt/amg/workflows"

# Export current workflows
curl -s -H "X-N8N-API-KEY: $N8N_KEY" "$N8N_API/workflows" | \
  jq -r '.data[] | .id + " " + .name' | while read ID NAME; do
    SAFE_NAME=$(echo "$NAME" | tr ' /' '_')
    curl -s -H "X-N8N-API-KEY: $N8N_KEY" "$N8N_API/workflows/$ID" > \
      "/tmp/n8n-export-$SAFE_NAME.json"
    
    # Compare to git version
    if [[ -f "$REPO_PATH/$SAFE_NAME.json" ]]; then
      DIFF=$(diff <(jq 'del(.updatedAt,.createdAt)' "$REPO_PATH/$SAFE_NAME.json") \
                  <(jq 'del(.updatedAt,.createdAt)' "/tmp/n8n-export-$SAFE_NAME.json"))
      if [[ -n "$DIFF" ]]; then
        echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"domain\":\"n8n\",\"event\":\"WORKFLOW_DRIFT\",\"detail\":\"$NAME drifted from git\"}" >> /var/log/amg/watchdog.jsonl
      fi
    fi
done
```

#### Escalation Path

| Condition | Level | Action |
|-----------|-------|--------|
| Critical workflow fails after 2 auto-repair attempts | Tier 2 | Alert with execution ID and error type |
| Credential expires without auto-refresh | Tier 2 | "Credential X expired — manual reauth required" |
| Workflow drift detected | Tier 1 | "Workflow Y modified outside git — review or commit" |
| n8n process restarted >3 times in 1 hour | Tier 2 | "n8n unstable — may need memory limit adjustment" |

#### Failure Catalog

| Failure Mode | MTTR | Notes |
|-------------|------|-------|
| OAuth token expiry | 30 sec | Auto-refresh if refresh token present |
| OpenAI 429 rate limit | 30-120 sec | Exponential backoff; rarely needs operator |
| n8n SQLite corruption | 30 min | Restore from R2 backup; → Tier 2 |
| Webhook endpoint 404 (URL changed) | Tier 2 | Schema drift; operator must update URL |
| n8n memory leak | 30 min | systemd `MemoryMax=4G` kills and restarts process automatically |

#### Implementation Notes

- n8n `ERROR_TRIGGER_WORKFLOW_ID` env var points to the error handler workflow ID
- All "critical" workflows tagged with `{"critical": true}` in workflow metadata
- n8n runs as systemd service with `MemoryMax=4G`, `Restart=always`, `RestartSec=10`
- Workflow exports committed to `/opt/amg/workflows/` in git repo on deploy

---

### Domain 9: MCP Memory Layer

> **DESCOPED 2026-04-14** — Doctrine Domain 9 predates current architecture. Real MCP runs at `https://memory.aimarketinggenius.io` (separate Cloudflare-fronted infra on its own dedicated host), NOT a local Node.js server on VPS port 3030 at `/opt/amg/mcp/`. The janitor, embedding drift, OOM, and session-leak controls below do not apply to the current MCP deployment; equivalents are handled upstream by the live MCP endpoint's own ops layer. DELTA-E is marked COMPLETE-BY-DESCOPE. Any future MCP hardening will be tracked as a new DR against the live endpoint, not this section.

**Topology (HISTORICAL — not current):** Custom Node.js MCP server running on VPS port 3030, persisting rule/context embeddings to a JSON store on disk and optionally to Supabase pgvector table

#### Detection

| Signal | Threshold | Mechanism |
|--------|-----------|-----------|
| Stale rules | Rule not accessed in >7 days | TTL field on each rule entry |
| Conflicting rules | Two rules matching same pattern with different outputs | Conflict detection on write |
| Embedding drift | Embedding model version mismatch | Model version tag on all entries |
| Decision deduplication | Same query resolved >3× with same result | Dedup cache hit rate |
| MCP server OOM | Heap >2 GB | Node.js `--max-old-space-size=2048` flag |
| Session state leak | `pg_stat_activity` MCP sessions idle >30 min | Idle session eviction |

#### Stale Rule Detection + Cleanup

Per [MCP Server Memory Management best practices](https://fast.io/resources/mcp-server-memory-management/):

```javascript
// /opt/amg/mcp/rule-janitor.js
// Runs daily — identifies and archives stale rules

const STALE_THRESHOLD_DAYS = 7;
const CONFLICT_CHECK = true;

async function runJanitor(ruleStore) {
  const now = Date.now();
  const staleRules = [];
  const conflicts = [];
  
  // Pass 1: Find stale rules (not accessed in 7 days)
  for (const [id, rule] of Object.entries(ruleStore)) {
    const lastAccess = new Date(rule.lastAccessed).getTime();
    const ageDays = (now - lastAccess) / 86400000;
    if (ageDays > STALE_THRESHOLD_DAYS) {
      staleRules.push({id, rule, ageDays: Math.round(ageDays)});
    }
  }
  
  // Pass 2: Find conflicting rules
  if (CONFLICT_CHECK) {
    const patternMap = {};
    for (const [id, rule] of Object.entries(ruleStore)) {
      const key = rule.pattern;
      if (patternMap[key]) {
        conflicts.push({
          pattern: key,
          rule1: patternMap[key],
          rule2: id
        });
      } else {
        patternMap[key] = id;
      }
    }
  }
  
  return {staleRules, conflicts};
}

// Stale rules: move to archive store, not delete
async function archiveStaleRules(staleRules) {
  for (const {id, rule, ageDays} of staleRules) {
    await archiveStore.set(id, {...rule, archivedAt: new Date(), ageDays});
    await ruleStore.delete(id);
    log(`Archived stale rule: ${id} (${ageDays}d unused)`);
  }
}

// Conflicts: keep the more recently accessed rule; flag the other
async function resolveConflicts(conflicts) {
  for (const {pattern, rule1, rule2} of conflicts) {
    const r1 = ruleStore[rule1];
    const r2 = ruleStore[rule2];
    const winner = new Date(r1.lastAccessed) > new Date(r2.lastAccessed) ? rule1 : rule2;
    const loser = winner === rule1 ? rule2 : rule1;
    
    // Tag loser as deprecated; keep both but loser will not be served
    ruleStore[loser].status = 'deprecated';
    ruleStore[loser].supersededBy = winner;
    log(`Conflict resolved: ${loser} deprecated in favor of ${winner} for pattern "${pattern}"`);
  }
}
```

#### Embedding Freshness Policy

All embeddings generated with a model version tag:
```json
{"id": "rule_001", "embedding": [...], "modelVersion": "text-embedding-3-small-v1", "createdAt": "...", "lastAccessed": "..."}
```

When the embedding model changes:
1. Watchdog detects version tag mismatch on read
2. Re-embeds stale entries in background (batch of 50/min to stay within API limits)
3. Logs re-embedding count to watchdog

#### Decision Deduplication

```javascript
// LRU cache for recent decisions — prevents redundant LLM calls
const dedupeCache = new LRUCache({max: 500, ttl: 1000 * 60 * 30}); // 30 min TTL

async function resolveWithDedup(query) {
  const cacheKey = hashQuery(query);
  if (dedupeCache.has(cacheKey)) {
    metrics.increment('mcp.dedup_hit');
    return dedupeCache.get(cacheKey);
  }
  const result = await resolveQuery(query);
  dedupeCache.set(cacheKey, result);
  return result;
}
```

#### Escalation Path

| Condition | Level | Action |
|-----------|-------|--------|
| MCP server crash (OOM) | Tier 0 | systemd restart; state recovers from disk |
| >10 unresolved conflicts | Tier 1 | "MCP has 10+ rule conflicts — review rule store" |
| Embedding model deprecated | Tier 1 | "Re-embedding in progress — N rules updated" |
| Disk backing store corrupted | Tier 2 | Restore from Supabase mirror; operator must verify |

#### Failure Catalog

| Failure Mode | MTTR | Notes |
|-------------|------|-------|
| MCP process OOM | <10 sec | Systemd restart; heap cap at 2 GB |
| Stale in-memory state (per [GitHub issue](https://github.com/eyaltoledano/claude-task-master/issues/1637)) | Instant | Mutations invalidate cache entry immediately |
| Rule store divergence from DB | 5 min | Reconcile on startup; write-through to Supabase |
| Embedding API outage | 30 min | Queue re-embedding; serve stale embeddings with warning flag |

---

### Domain 10: Titan Session Hygiene

**Topology:** Titan = Claude Code running as autonomous build agent on VPS under a dedicated tmux session (`titan-session`), with MIRROR_STATUS.md as handoff state file, operating under multi-hour task sequences

#### Detection

| Signal | Threshold | Mechanism |
|--------|-----------|-----------|
| Context depth approaching limit | >80% of context window used | Titan self-reports via MIRROR_STATUS.md |
| MIRROR_STATUS.md not updated | >30 minutes during active session | `find /opt/amg -name MIRROR_STATUS.md -mmin +30` |
| tmux session missing | Session `titan-session` not in `tmux ls` | Watchdog tmux check every 5 min |
| Uncommitted working tree | `git status --porcelain` non-empty at end of task | Post-task hook |
| State flush not completed | MIRROR_STATUS.md contains `STATUS: IN_PROGRESS` | End-of-session check |
| Runaway tool calls | >50 tool calls in 10 minutes | Titan's internal counter |

#### MIRROR_STATUS.md Schema

```markdown
# TITAN SESSION STATUS

STATUS: [READY|IN_PROGRESS|BLOCKED|POWER_OFF]
SESSION_ID: titan-2026-04-12-001
LAST_UPDATED: 2026-04-12T14:30:00Z
CONTEXT_DEPTH: 45%
CURRENT_TASK: [task description]
COMPLETED_STEPS:
- [step 1]
- [step 2]
NEXT_STEPS:
- [next action]
BLOCKERS:
- [any blockers]
GIT_STATE:
  BRANCH: main
  LAST_COMMIT: abc1234
  WORKING_TREE: clean
WATCHDOG_VERIFIED: false
```

#### Clean POWER OFF Protocol

```bash
#!/bin/bash
# /opt/amg/scripts/titan-poweroff.sh
# Enforced clean shutdown for Titan session

LOG="/var/log/amg/watchdog.jsonl"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
MIRROR_FILE="/opt/amg/MIRROR_STATUS.md"

log_event() {
  echo "{\"ts\":\"$TIMESTAMP\",\"domain\":\"titan\",\"event\":\"$1\",\"detail\":\"$2\"}" >> "$LOG"
}

# Step 1: Verify git working tree is clean
if [[ -n "$(git -C /opt/amg status --porcelain)" ]]; then
  log_event "TITAN_DIRTY_TREE" "Uncommitted changes at shutdown — committing checkpoint"
  git -C /opt/amg add -A
  git -C /opt/amg commit -m "chore: titan checkpoint at $TIMESTAMP"
fi

# Step 2: Verify MIRROR_STATUS.md is updated
STATUS=$(grep "^STATUS:" "$MIRROR_FILE" | awk '{print $2}')
if [[ "$STATUS" == "IN_PROGRESS" ]]; then
  log_event "TITAN_STATUS_FLUSH" "Forcing STATUS to POWER_OFF"
  sed -i "s/^STATUS: IN_PROGRESS/STATUS: POWER_OFF/" "$MIRROR_FILE"
  git -C /opt/amg add "$MIRROR_FILE"
  git -C /opt/amg commit -m "chore: titan POWER_OFF state flush at $TIMESTAMP"
fi

# Step 3: Push to VPS bare repo
git -C /opt/amg push origin main

# Step 4: Mark watchdog verified
sed -i "s/^WATCHDOG_VERIFIED: false/WATCHDOG_VERIFIED: true/" "$MIRROR_FILE"

# Step 5: Optionally kill tmux session
if [[ "$1" == "--kill-session" ]]; then
  tmux kill-session -t titan-session 2>/dev/null
  log_event "TITAN_SESSION_KILLED" "tmux titan-session terminated"
fi

log_event "TITAN_POWEROFF_COMPLETE" "Session safely closed"
exit 0
```

#### Context Depth Monitoring

Titan is instructed to update `MIRROR_STATUS.md`'s `CONTEXT_DEPTH` field every 10 tool calls. The watchdog reads this field:

- If `CONTEXT_DEPTH` > 80%: send Tier-1 notification "Titan context approaching limit — plan to summarize or start new session"
- If `CONTEXT_DEPTH` > 95%: trigger `titan-poweroff.sh` autonomously (Tier-0 safe action — state is preserved)

#### Escalation Path

| Condition | Level | Action |
|-----------|-------|--------|
| MIRROR_STATUS.md stale >30 min | Tier 1 | "Titan may be unresponsive — check tmux session" |
| tmux session missing | Tier 1 | "Titan session dead — last known state in MIRROR_STATUS.md" |
| Uncommitted changes at unexpected halt | Tier 0 | Auto-commit checkpoint; operator notified in daily digest |
| Context >95% | Tier 0 | Auto-poweroff + state flush |
| Runaway tool calls | Tier 2 | "Titan exceeding call rate — possible loop detected" |

#### Failure Catalog

| Failure Mode | MTTR | Notes |
|-------------|------|-------|
| Titan context overflow | 30 sec | Auto-poweroff; state preserved in MIRROR_STATUS.md |
| VPS OOM kills Titan process | 1 min | tmux session persists; new Claude Code instance can resume |
| MIRROR_STATUS.md corrupted | 5 min | Restore last known-good version from git log |
| Titan stuck in retry loop | Tier 2 | Operator must send interrupt command via tmux |
| SSH session disconnect during Titan run | 0 min | tmux ensures session continues; Titan unaffected |

---

### Domain 11: Cost / API Spend Caps

**Topology:** Per-service API spend tracked via gateway layer + provider dashboards; hard ceilings enforced before calls are made, not after

#### Detection

| Service | Limit | Mechanism |
|---------|-------|-----------|
| Anthropic (Claude API) | $500/month hard cap | Anthropic account budget alert + gateway quota |
| OpenAI | $200/month hard cap | OpenAI usage limits API |
| Deepgram STT/TTS | $100/month | Deepgram billing API |
| All services | 150% of 7-day rolling average | Rate anomaly detector |
| Per-session Titan | $10/session ceiling | Internal token counter |

#### Spend Enforcement Architecture

Per [TrueFoundry's enforcement model](https://dev.to/deeptishuklatfy/how-to-enforce-llm-spend-limits-per-team-without-slowing-down-your-engineers-ml):

```bash
#!/bin/bash
# /opt/amg/scripts/spend-check.sh
# Called before any expensive LLM operation; exits nonzero to block if over limit

SERVICE=$1  # "anthropic" | "openai" | "deepgram"
ESTIMATED_COST=${2:-0.01}  # Estimated cost in USD for this call

# Load current month spend from local ledger
CURRENT_SPEND=$(cat "/opt/amg/spend/${SERVICE}-$(date +%Y-%m).total" 2>/dev/null || echo "0")
MONTHLY_LIMIT=$(cat "/opt/amg/spend/${SERVICE}.limit")

# Check if adding estimated cost would exceed 95% of limit
PROJECTED=$(echo "$CURRENT_SPEND + $ESTIMATED_COST" | bc)
THRESHOLD=$(echo "$MONTHLY_LIMIT * 0.95" | bc)

if (( $(echo "$PROJECTED > $THRESHOLD" | bc -l) )); then
  echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"domain\":\"cost\",\"event\":\"SPEND_GATE_BLOCKED\",\"detail\":\"$SERVICE at \$$CURRENT_SPEND / \$$MONTHLY_LIMIT\"}" >> /var/log/amg/watchdog.jsonl
  
  if (( $(echo "$PROJECTED > $MONTHLY_LIMIT" | bc -l) )); then
    exit 2  # Hard block; Tier 2 escalation
  else
    exit 1  # Soft warning; route to cheaper model if available
  fi
fi

# Debit ledger
echo "$PROJECTED" > "/opt/amg/spend/${SERVICE}-$(date +%Y-%m).total"
exit 0
```

**Model Downgrade Cascade on Budget Pressure:**
- At 75% of monthly cap: log warning only
- At 90% of monthly cap: route to cheaper model tier (claude-haiku, gpt-4o-mini)
- At 100% of monthly cap: hard block + Tier-2 alert + automatic n8n workflow pause for affected integrations

#### Surge Detection (Anomaly-Based)

```bash
#!/bin/bash
# /opt/amg/scripts/spend-anomaly.sh

# Calculate 7-day rolling average
DAYS=7
AVG=0
for i in $(seq 1 $DAYS); do
  DATE=$(date -d "$i days ago" +%Y-%m-%d)
  DAILY=$(cat "/opt/amg/spend/anthropic-$DATE.daily" 2>/dev/null || echo "0")
  AVG=$(echo "$AVG + $DAILY" | bc)
done
AVG=$(echo "$AVG / $DAYS" | bc)

# Today's spend so far
TODAY=$(cat "/opt/amg/spend/anthropic-$(date +%Y-%m-%d).daily" 2>/dev/null || echo "0")

# Alert if 2× the rolling average by midday, 1.5× any time
FACTOR=$(echo "$TODAY / $AVG" | bc -l 2>/dev/null || echo "1")
if (( $(echo "$FACTOR > 2" | bc -l) )); then
  log_event "SPEND_SURGE" "Anthropic today \$$TODAY is ${FACTOR}x rolling avg \$$AVG"
  exit 1  # Tier-1 alert
fi
```

#### Escalation Path

| Condition | Level | Action |
|-----------|-------|--------|
| At 75% monthly cap | Tier 0 | Log only; daily digest mention |
| At 90% monthly cap | Tier 1 | "Approaching spend limit — routing to cheaper models" |
| At 100% monthly cap | Tier 2 | "Hard cap reached — API calls blocked" |
| 2× daily spend surge | Tier 1 | "Unusual spend detected — review API usage" |
| Titan session >$10 | Tier 0 | Auto-pause session; report in daily digest |

#### Failure Catalog

| Failure Mode | MTTR | Notes |
|-------------|------|-------|
| Ledger file corrupted | 5 min | Re-pull from provider API billing endpoint |
| n8n loop creates runaway API calls | 30 sec | Circuit breaker in Domain 8 catches this first |
| Provider billing API unavailable | N/A | Default to conservative estimate; alert operator |

---

### Domain 12: Process / Service Availability (Identified Gap)

**Topology:** Core VPS services that underpin all other domains: n8n, Caddy, MCP server, VPS Postgres, watchdog daemon itself

This domain emerged from analysis — it is the foundational health layer that all other domains depend on, but no domain explicitly owned it.

#### Detection

| Service | Health Signal | Check Method |
|---------|--------------|-------------|
| n8n | HTTP 200 on `/healthz` | curl every 60 sec |
| Caddy | Process alive + port 443 listening | systemctl + ss -tlnp |
| MCP server | HTTP 200 on `/health` | curl every 60 sec |
| VPS Postgres | `pg_isready` | pg_isready every 60 sec |
| Watchdog daemon | Heartbeat file updated <2 min ago | External check (Uptime Robot free tier) |

#### Remediation

All core services run under systemd with `Restart=always` and `RestartSec=5`. First-pass remediation is automatic. If a service restarts >3 times in 10 minutes, it enters the "unstable" state and triggers Tier-2 escalation.

#### Watchdog Self-Monitoring

The watchdog daemon cannot watch itself. External monitoring uses [Uptime Robot](https://uptimerobot.com) free tier to ping a heartbeat endpoint (`GET /watchdog/heartbeat`) on Caddy every 5 minutes. If the heartbeat fails, Uptime Robot sends an email + SMS alert to the operator.

The heartbeat endpoint is a simple HTTP 200 response served by Caddy that routes to a static file updated by the watchdog daemon every 90 seconds:

```bash
# In watchdog main loop:
while true; do
  date -u +"%Y-%m-%dT%H:%M:%SZ" > /var/www/amg/watchdog-heartbeat.txt
  sleep 90
done
```

#### Failure Catalog

| Service | Failure Mode | MTTR |
|---------|-------------|------|
| n8n OOM | 10 sec (systemd restart) | MemoryMax cap prevents cascade |
| MCP server crash | 10 sec | Disk state preserved; session context restored |
| VPS Postgres crash | 30 sec | systemd restart; WAL recovery automatic |
| Watchdog daemon dead | SMS to operator within 5 min | Uptime Robot alert |
| Full VPS reboot | 2-3 min | All systemd services start in correct order via `After=` dependencies |

---

## Section E — Central Watchdog Architecture {#section-e}

### E.1 Watchdog Design Overview

The AMG Central Watchdog is a single long-running Node.js process (`amg-watchdog.service`) running on the VPS. It implements the MAPE-K loop across all twelve domains with a unified execution model.

```
┌──────────────────────────────────────────────────────────┐
│                    AMG CENTRAL WATCHDOG                  │
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │   SENSORS   │  │  KNOWLEDGE  │  │    ACTUATORS    │  │
│  │ (12 domain  │  │   STORE     │  │ (shell scripts, │  │
│  │  checkers)  │  │ (JSONL log +│  │  API calls,     │  │
│  └──────┬──────┘  │  thresholds)│  │  systemd cmds)  │  │
│         │         └──────┬──────┘  └────────┬────────┘  │
│         │                │                  │           │
│  ┌──────▼──────────────▼──────────────────▼──────────┐  │
│  │              MAPE-K DECISION ENGINE                │  │
│  │                                                    │  │
│  │  [Monitor] → [Analyze] → [Plan] → [Execute]        │  │
│  │       every 60s         ↕                          │  │
│  │                    Playbook DB                     │  │
│  └──────────────────────────────┬─────────────────────┘  │
│                                 │                        │
│  ┌──────────────────────────────▼─────────────────────┐  │
│  │               NOTIFICATION ROUTER                  │  │
│  │  Tier 0 → /var/log/amg/watchdog.jsonl only         │  │
│  │  Tier 1 → JSONL + daily digest buffer              │  │
│  │  Tier 2 → JSONL + immediate Slack DM               │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### E.2 Domain Check Schedule

| Domain | Check Interval | Trigger |
|--------|---------------|---------|
| Git Mirror | 5 min | Timer |
| Disk Hygiene | 15 min (sweep on >70%) | Timer + threshold |
| R2 Lifecycle | Daily at 03:00 | Cron |
| Slack Noise | Weekly Sunday | Cron |
| AI Voice/WS | Event-driven | Socket close handler |
| Supabase | 60 sec | Timer |
| Caddy | 30 sec | Timer |
| n8n Workflows | 60 sec + error webhook | Timer + webhook |
| MCP Memory | Daily at 02:00 | Cron |
| Titan Session | 5 min | Timer |
| Cost Caps | Per-call + hourly | Pre-call gate + cron |
| Process Health | 60 sec | Timer |

### E.3 Autonomous Action Safety Classification

**Safe (no human confirmation required):**
- Service restart via systemd
- `git fetch` and fast-forward merges
- Log rotation and compression
- Docker layer cleanup
- Slack channel archival (with 7-day warning)
- n8n workflow retry (error classification confirmed)
- Titan poweroff and state flush
- R2 lifecycle rule reapplication
- Caddy config restore from git
- Database idle connection termination

**Unsafe (requires operator confirmation / Tier-2 escalation):**
- `git push --force`
- Deleting any database table or bucket prefix
- Modifying Supabase schema
- Spending >$50 in a single hour
- Restarting VPS Postgres with potential in-flight transactions
- Any action that modifies a file not tracked in git

**Forbidden (never autonomous):**
- Deleting git history
- Dropping database tables
- Removing R2 buckets
- Committing to `main` without task context (except checkpoint commits flagged in MIRROR_STATUS.md)

### E.4 Watchdog Source Code Skeleton

```javascript
// /opt/amg/watchdog/index.js
// AMG Central Watchdog Daemon

const {execSync} = require('child_process');
const fs = require('fs');
const https = require('https');

const WATCHDOG_LOG = '/var/log/amg/watchdog.jsonl';
const SLACK_WEBHOOK = process.env.SLACK_WATCHDOG_WEBHOOK;

const domains = [
  {name: 'git', script: '/opt/amg/scripts/git-heal.sh', interval: 300000},
  {name: 'disk', script: '/opt/amg/scripts/disk-heal.sh', interval: 900000},
  {name: 'caddy', script: '/opt/amg/scripts/caddy-heal.sh', interval: 30000},
  {name: 'supabase', script: '/opt/amg/scripts/db-check.sh', interval: 60000},
  {name: 'n8n', script: '/opt/amg/scripts/n8n-check.sh', interval: 60000},
  {name: 'mcp', script: '/opt/amg/scripts/mcp-check.sh', interval: 3600000},
  {name: 'titan', script: '/opt/amg/scripts/titan-check.sh', interval: 300000},
  {name: 'cost', script: '/opt/amg/scripts/spend-check.sh', interval: 3600000},
  {name: 'process', script: '/opt/amg/scripts/service-health.sh', interval: 60000},
];

function log(domain, event, detail, tier = 0) {
  const entry = JSON.stringify({
    ts: new Date().toISOString(),
    domain, event, detail, tier
  });
  fs.appendFileSync(WATCHDOG_LOG, entry + '\n');
  if (tier >= 2) notifySlack(entry);
  else if (tier === 1) bufferDigest(entry);
}

function notifySlack(message) {
  // Dedup: skip if same event within 1 hour
  const payload = JSON.stringify({
    text: `🚨 *AMG Watchdog Alert*\n${message}`
  });
  // POST to SLACK_WEBHOOK...
}

function runDomain(domain) {
  try {
    const result = execSync(domain.script, {timeout: 30000});
    log(domain.name, 'CHECK_PASS', 'Healthy', 0);
  } catch (err) {
    const tier = err.status === 2 ? 2 : 1;
    log(domain.name, 'CHECK_FAIL', err.stderr?.toString() || err.message, tier);
  }
}

// Schedule all domain checks
domains.forEach(domain => {
  setInterval(() => runDomain(domain), domain.interval);
  runDomain(domain);  // Run immediately on start
});

// Daily digest at 08:00 EST
scheduleDigest('08:00');

// Heartbeat
setInterval(() => {
  fs.writeFileSync('/var/www/amg/watchdog-heartbeat.txt',
    new Date().toISOString());
}, 90000);

console.log('AMG Watchdog started');
```

---

## Section F — Learning Loop {#section-f}

### F.1 Incident Classification and Feed-in

Every entry in `watchdog.jsonl` is structured:

```json
{
  "ts": "2026-04-12T14:30:00Z",
  "domain": "caddy",
  "event": "502_UPSTREAM",
  "detail": "n8n on :5678 returning 502",
  "tier": 2,
  "remediation": "n8n restarted",
  "resolution": "resolved",
  "ttrecover_seconds": 45
}
```

Weekly, the watchdog runs `log-analyze.sh` which:
1. Counts incidents per domain
2. Calculates MTTR per event type
3. Identifies the top-3 recurring failure modes
4. Posts summary to `#amg-ops-digest`

### F.2 Post-Mortem Template

For any Tier-2 incident, a post-mortem must be completed within 24 hours. Template stored at `/opt/amg/docs/postmortem-template.md`:

```markdown
# Post-Mortem: [INCIDENT_ID] — [SHORT_TITLE]

**Date:** [YYYY-MM-DD]
**Duration:** [HH:MM start → HH:MM end, TZ]
**Domain(s) Affected:** [list]
**Tier:** 2
**Auto-Resolved:** [Yes/No]
**MTTR:** [minutes]

## What Happened
[2-3 sentences: what failed and what the observable impact was]

## Timeline
| Time | Event |
|------|-------|
| HH:MM | Alert fired |
| HH:MM | Operator notified |
| HH:MM | Root cause identified |
| HH:MM | Remediation applied |
| HH:MM | Verified resolved |

## Root Cause
[Single sentence. Be specific.]

## Contributing Factors
- [Factor 1]
- [Factor 2]

## Why Doctrine Didn't Auto-Resolve
[Required for Tier-2. This must result in a doctrine improvement.]

## Doctrine Update
- [ ] New failure mode added to domain failure catalog
- [ ] Detection threshold adjusted: [what changed]
- [ ] Remediation script updated: [what changed]
- [ ] Escalation path modified: [what changed]

## Commit Reference
[Link to git commit containing doctrine update]
```

### F.3 Learning Metrics

| Metric | Target | Current Baseline |
|--------|--------|-----------------|
| Tier-0 auto-resolution rate | ≥85% | Establish in Month 1 |
| Tier-2 pages per week | ≤3 | Establish in Month 1 |
| Repeat Tier-2 for same failure mode | 0 after first occurrence | — |
| MTTR improvement month-over-month | ≥10% | — |
| Doctrine updates per month | ≥1 | — |

### F.4 Knowledge Base Evolution

The watchdog's `thresholds.json` file is updated based on observed incident patterns:

```json
{
  "disk": {"alert_pct": 70, "critical_pct": 85, "adjusted_from": 80, "adjusted_on": "2026-03-01", "reason": "Docker builds often spike to 78%"},
  "caddy": {"health_interval_sec": 30, "502_threshold_pct": 5, "502_window_sec": 60},
  "n8n": {"retry_max": 2, "backoff_base_ms": 30000}
}
```

Any threshold change is committed to git with the post-mortem as context.

---

## Section G — Implementation Roadmap {#section-g}

Domains are prioritized by: (1) failure frequency, (2) revenue risk if down, (3) blast radius.

### Phase 1 — Foundation (Week 1-2) — ~16 hours

**Goal:** Watchdog daemon running; highest-risk domains covered; no blind spots.

| Task | Estimated Hours |
|------|----------------|
| Deploy watchdog daemon skeleton with logging | 3 |
| Domain 12: Core service health checks + systemd hardening | 2 |
| Domain 7: Caddy health checks + 502 auto-recovery | 3 |
| Domain 2: Disk cleanup timer + Docker prune systemd | 2 |
| Domain 8: n8n error handler workflow + error classification | 4 |
| Set up Uptime Robot heartbeat monitoring | 1 |
| Deploy SLACK_WATCHDOG_WEBHOOK + test alert routing | 1 |

### Phase 2 — Data Layer (Week 3) — ~12 hours

**Goal:** Database and storage resilience fully operational.

| Task | Estimated Hours |
|------|----------------|
| Domain 6: Supabase health check + VPS Postgres failover | 4 |
| Domain 3: R2 lifecycle rules configuration + backup verify | 3 |
| Domain 1: Git mirror integrity timer + bare repo fsck | 3 |
| Domain 2: R2 cold offload sync (extend disk-heal.sh) | 2 |

### Phase 3 — Agent Layer (Week 4) — ~10 hours

**Goal:** Titan session hygiene and MCP memory management operational.

| Task | Estimated Hours |
|------|----------------|
| Domain 10: MIRROR_STATUS.md schema + titan-poweroff.sh | 3 |
| Domain 9: MCP rule janitor + stale detection + dedup cache | 4 |
| Domain 11: Spend ledger + per-call gate + anomaly detector | 3 |

### Phase 4 — Signal Quality (Week 5) — ~8 hours

**Goal:** Operator noise minimized; Slack hygiene operational; AI voice resilient.

| Task | Estimated Hours |
|------|----------------|
| Domain 4: Slack noise filter workflow + channel audit | 3 |
| Domain 5: WebSocket resilience client + STT fallback chain | 3 |
| Daily digest workflow in n8n | 2 |

### Phase 5 — Hardening (Week 6+) — Ongoing

| Task | Estimated Hours |
|------|----------------|
| First restore drill (R2 backup) | 1 |
| First chaos experiment (controlled Caddy restart) | 1 |
| Learning loop: analyze first month's incidents | 2 |
| Threshold calibration based on observed data | 1 |
| Post-mortem template test on first Tier-2 incident | 1 |

**Total estimated build hours:** ~47 hours over 5-6 weeks

**For Titan execution:** Each phase can be given to Titan as a discrete task. Phase boundaries = natural POWER OFF checkpoints. MIRROR_STATUS.md documents phase completion before each handoff.

---

## Section H — Metrics & Success Criteria {#section-h}

### H.1 Operational Metrics

| Metric | Baseline Target (Month 1) | Mature Target (Month 6) |
|--------|--------------------------|------------------------|
| % incidents auto-resolved (Tier 0) | ≥70% | ≥90% |
| Operator pages per week (Tier 2) | ≤5 | ≤2 |
| Mean Time to Recovery (all domains) | ≤30 min | ≤10 min |
| Mean Time to Detect | ≤5 min | ≤2 min |
| Disk utilization maintained | <80% | <70% |
| Database connection pool headroom | ≥40% free | ≥40% free |
| Caddy 502 rate (weekly average) | <0.1% | <0.05% |
| Doctrine post-mortems completed | 100% of Tier-2s | 100% of Tier-2s |

### H.2 Domain-Specific SLOs

| Domain | SLO | Error Budget (30-day) |
|--------|-----|----------------------|
| Git Mirror | 99.9% push success rate | 43 min downtime/month |
| Caddy/HTTPS | 99.95% availability | 22 min/month |
| Supabase | 99.5% query success | 3.6 hours/month |
| n8n Workflows | 95% critical workflow success | 36 hours/month |
| AI Voice | 99% session establishment | 7.2 hours/month |
| Disk <70% | 100% compliance | 0 min breach |
| R2 Backup Freshness | 100% <25-hour lag | 0 missed backups/month |

### H.3 Proof-of-Doctrine Gates

Before declaring Phase 5 complete, the following must pass:

1. **Chaos test:** Kill n8n process manually → watchdog detects in <60 sec → n8n restarted and healthy in <90 sec total
2. **Git inject:** Manually corrupt a ref in the bare repo → watchdog detects via fsck → repaired without operator action in <5 min
3. **Disk flood:** Create a 10 GB temp file → watchdog detects >70% → cleanup runs → disk returns to <70% → operator not paged
4. **Slack storm:** Trigger 20 n8n workflow failures in 10 min → operator receives ≤2 Slack messages (dedup + digest)
5. **Restore drill:** Execute full R2 backup restore to test DB → schema validation passes

---

## Section I — Anti-Patterns {#section-i}

### I.1 The Healer That Causes Cascades

**Pattern:** Remediation of Domain A triggers a failure in Domain B.

**Example:** Disk cleanup script (`disk-heal.sh`) deletes Docker images during an n8n workflow execution that's building a new container. n8n execution fails. n8n error handler fires. Slack alert fires. Operator pages. System appears more broken than before cleanup.

**Mitigation:** Before any destructive action, the watchdog checks `n8n-executions-running` count. If >0, destructive Docker cleanup is deferred 10 minutes. Domain 2 scripts include a `--safe-mode` flag that skips Docker layer removal when other domains report activity.

### I.2 Alert Fatigue Loop

**Pattern:** A high-frequency failure mode generates a Tier-1 alert. Operator is notified but takes no action. The same alert fires again. And again. After 50 repetitions, the operator stops reading the channel. A critical Tier-2 alert is then missed.

**Mitigation:** Any alert that fires >5 times in 24 hours without a post-mortem is automatically escalated to Tier-2. The doctrine requires every Tier-1 to have a silencing decision: fix it, suppress it, or escalate it. Alerts with no response within 4 hours auto-generate a Tier-2 asking: "This alert has fired N times. Resolve or suppress?"

### I.3 The Watchdog That Watches Nothing

**Pattern:** The watchdog daemon is deployed. It runs. It generates logs. Nobody reads the logs. Months later, an operator realizes the log file has been writing to `/dev/null` due to a path misconfiguration, and the last 90 days of incidents are unknown.

**Mitigation:** Section E.4 — the watchdog writes a heartbeat file every 90 seconds. Uptime Robot pings it. If the heartbeat file is stale, SMS alert fires. The watchdog's own health is not self-assessed.

### I.4 Zombie Remediation Scripts

**Pattern:** An automated script runs, encounters an unexpected state (e.g., git repo locked by another process), fails silently, and marks the domain as "healthy" anyway because the exit code was 0 from `set -e` catching the wrong point.

**Mitigation:** All scripts use `set -euo pipefail`. Every script has an explicit final health verification step that confirms the intended post-remediation state, not just that no error occurred. The last line of every healing script is a positive health assertion, not just an absence of errors.

### I.5 The Over-Eager Healer

**Pattern:** Watchdog detects an "anomaly" (actually a legitimate maintenance operation by the operator) and autonomously reverts it. Example: operator manually edits Caddyfile to test a new upstream. Watchdog detects config drift, restores Caddyfile from git, and undoes the change mid-test.

**Mitigation:** All autonomous config restores require a 5-minute confirmation window. The watchdog posts "Config drift detected in Caddyfile — will restore in 5 min unless operator confirms with `/amg hold caddy`". A simple n8n webhook implements the hold mechanism, writing a file `/opt/amg/holds/caddy.hold` that the watchdog checks before acting. Holds expire in 2 hours.

### I.6 Runaway Exponential Backoff

**Pattern:** n8n workflow hits a rate limit. Error handler applies exponential backoff. But the backoff timer is stored in-memory. n8n restarts (for unrelated reasons). Timer resets. Workflow immediately retries. Hits rate limit again. n8n restarts again (now from the 429 overload). Loop.

**Mitigation:** Retry state is persisted to Supabase, not held in memory. Retry counter survives n8n restart. Backoff metadata: `{workflowId, errorType, attempts, nextRetryAt}`. Any retry with `attempts > 5` escalates to Tier-2 regardless of error type.

### I.7 The Accumulating Knowledge Base

**Pattern:** MCP memory layer accumulates rules over months. Rule count grows to 10,000+. Query resolution slows from 50ms to 2 seconds. Eventually the MCP server times out on every query. Voice sessions degrade. The "memory" feature becomes a reliability liability.

**Mitigation:** Domain 9 rule janitor enforces hard cap: max 1,000 active rules. Stale rules are archived (not deleted). Embedding queries use a max-similarity threshold — if no rule scores >0.7, return "no match" rather than a poor-quality match. Regular profiling of resolution latency; alert if P99 >500ms.

### I.8 Security / Self-Healing Boundary Confusion

**Pattern:** A self-healing script, in order to fix a credential expiry, generates and distributes a new API key autonomously. This bypasses credential review processes and creates untracked secrets.

**Mitigation:** This doctrine explicitly does not manage credentials, secret rotation, or authentication tokens. Any remediation path that requires a new credential terminates with a Tier-2 escalation: "Credential expired — operator must rotate. See DR-AMG-SECURITY-01." Automated credential refresh is only permitted for OAuth2 refresh token flows where the refresh token is already present and the exchange is a standard protocol operation.

---

## Cross-Validation: The 3AM Failure Mode Adversarial Review

This section documents the adversarial challenge applied before finalizing the doctrine: *"What is the 3am failure that defeats every pattern here?"* Each scenario was tested against the doctrine's defenses and, where gaps were found, defenses were incorporated above.

### CV-1: The Watchdog Eats the Disk

**Scenario:** The watchdog daemon's `watchdog.jsonl` log file grows unboundedly. Over 90 days, it reaches 40 GB, consuming 60% of available VPS disk alone. The disk alarm (Domain 2) fires. disk-heal.sh runs. Its exclusion list protects `watchdog.jsonl`. Disk hits 85%. Tier-2 escalates. Operator investigates — finds the problem IS the watchdog log.

**Defense Added:** `watchdog.jsonl` uses logrotate with `rotate 7`, `compress`, `maxsize 100M`, `daily`. The watchdog's own log is explicitly included in log rotation configuration, not excluded from it. Cap behavior: if watchdog log >500 MB despite rotation, it is truncated (oldest entries purged, warning logged to a separate alert file that does NOT grow unboundedly).

### CV-2: VPS Full Reboot During Active Titan Session

**Scenario:** HostHatch performs unannounced emergency maintenance. VPS reboots at 3:13 AM. Titan is mid-task, 12 tool calls into a complex refactor. git working tree has 47 modified files — not yet committed. tmux session is dead. MIRROR_STATUS.md has `STATUS: IN_PROGRESS`. On boot, all systemd services restart. Watchdog runs. It detects `STATUS: IN_PROGRESS` in MIRROR_STATUS.md and `git status --porcelain` shows 47 modified files.

**Defense Added:** Domain 10's titan-check.sh detects `STATUS: IN_PROGRESS` + dirty working tree on startup (not just on timer). It auto-commits ALL modified files with message: `chore: titan emergency checkpoint post-reboot [TIMESTAMP]`. This preserves all work. MIRROR_STATUS.md is updated to `STATUS: INTERRUPTED_REBOOT`. Tier-1 notification: "VPS reboot detected — Titan session interrupted at [last known step]. Work preserved in git. Resume from MIRROR_STATUS.md."

**Implementation:** A `@reboot` cron entry runs `titan-recovery.sh` on every boot before any other AMG service starts.

### CV-3: n8n and Caddy Restart in the Same 60-Second Window

**Scenario:** A memory spike on the VPS triggers both n8n's `MemoryMax` limit AND causes Caddy to temporarily lose a port binding. Both Domain 7 and Domain 8 trigger simultaneously. Caddy-heal.sh tries to restart n8n (identified as the failing upstream). n8n-check.sh also tries to restart n8n. Both scripts run `systemctl restart n8n` within 5 seconds of each other. The double restart puts n8n in a broken state mid-boot, systemd restart counter hits the limit, and n8n stays down for 10 minutes.

**Defense Added:** All domain healing scripts use a **domain lock file** before taking action on a shared resource. Pattern:
```bash
LOCKFILE="/var/lock/amg-n8n.lock"
if ! flock -n 4; then
  log_event "LOCK_SKIP" "n8n action skipped — another healer holds lock"
  exit 0
fi
``` (on fd 4 pointing to `$LOCKFILE`)
Only the first script to acquire the lock proceeds. The second skips and logs. Cross-domain lock awareness prevents double-restart races.

### CV-4: Supabase Failover Creates Logical Replication Split-Brain

**Scenario:** Supabase experiences a 4-minute outage. Watchdog triggers Domain 6 failover to VPS Postgres mirror. n8n workflows write 847 new records to the VPS mirror. Supabase comes back online. The watchdog's Supabase health check returns green. The system automatically reverts all connections to Supabase. The 847 records written to the VPS mirror during the outage are now orphaned — they exist on the VPS but not in Supabase. Application appears healthy. Data divergence grows silently.

**Defense Added:** Failover to VPS is **read-only** during planned failovers lasting <15 minutes. Writes are paused (n8n workflows that require writes are suspended via a watchdog-controlled n8n webhook). For outages >15 minutes, write mode on VPS is enabled, but the watchdog sets a `SPLIT_BRAIN_RISK` flag. Operator must explicitly run `db-reconcile.sh` before Supabase is re-enabled as primary. The reconcile script compares VPS row counts with Supabase counts by table and flags divergence. Auto-resolution only if divergence = 0. Otherwise, Tier-2 escalation with diff report.

### CV-5: All Three Git Remotes Disagree at 3AM

**Scenario:** Network partition during a Mac → VPS push leaves the VPS bare repo with a partial pack file (11 of 23 objects written). GitHub has the previous clean state. Mac has the new working state. `git fsck` on the bare repo finds corruption. git-heal.sh runs `git gc --prune=now`. gc fails because pack file is partially written and gc cannot parse it. The script exits 2. Operator paged at 3 AM.

**Defense Added:** The Tier-2 escalation message for bare repo corruption now includes the exact recovery commands:
```
⚠️ Git bare repo corrupted on VPS
Recovery:
  1. cd /opt/repos/amg.git
  2. git remote add origin git@github.com:AMG/repo.git  (if needed)
  3. git fetch origin
  4. git reset --hard origin/main
  5. Run git-heal.sh to verify
```
This transforms a 3AM confusion panic into a 3-minute copy-paste recovery. The escalation message is the playbook.

### CV-6: Cost Cap Ledger Reset on Month Boundary

**Scenario:** It is 11:58 PM on March 31st. The Anthropic spend ledger shows $487 against a $500 cap. A Titan session starts at 11:59 PM and runs a large batch job. At midnight, `spend-check.sh` resets the ledger to $0 (new month). The batch job, which now sees $0 remaining against $500 limit, continues unthrottled. It runs until 3 AM, accruing $340 in a single night.

**Defense Added:** Monthly cap reset happens at 00:30 (not 00:00) to avoid midnight boundary race. The ledger reset is **not instantaneous** — it writes the new month's file but keeps the old month's file readable for 24 hours. Any single-session spend exceeding $50 (regardless of month) triggers an immediate Tier-1 alert. Titan sessions always check per-session cap ($10) in addition to monthly cap.

### CV-7: The Watchdog Daemon Itself Crashes During a Multi-Domain Incident

**Scenario:** At 3 AM, disk hits 85% (Domain 2 fires), n8n has a runaway workflow (Domain 8 fires), and a Caddy health check fails (Domain 7 fires). All three domain scripts are invoked simultaneously. The disk-heal script deletes the Node.js temp directory that the watchdog daemon is using for its IPC socket. The watchdog daemon crashes with `ENOENT`. All monitoring goes dark. The domains continue failing with no remediation.

**Defense Added:** The watchdog daemon uses `/var/run/amg-watchdog/` for its IPC socket — a dedicated directory not cleaned by any healing script. The excluded paths list in disk-heal.sh explicitly includes `/var/run/amg-watchdog/`. Additionally, the watchdog daemon's systemd service has `Restart=always` with `RestartSec=3` — a crash recovers within 3 seconds. The Uptime Robot heartbeat (Domain 12) detects the watchdog's absence within 5 minutes regardless of how it died.

### Summary: 3AM Resilience Posture

After adversarial review, the doctrine's true 3AM failure modes are:
1. **Power loss / VPS reboot** — mitigated by startup recovery scripts and git checkpoint commits
2. **Multi-domain simultaneous failure** — mitigated by domain lock files and cross-domain dependency checking
3. **Data consistency after failover** — mitigated by read-only failover mode and mandatory reconciliation
4. **The watchdog itself failing** — mitigated by external heartbeat monitoring and systemd `Restart=always`

The one remaining honest risk: **HostHatch datacenter total loss**. This doctrine has no defense for it because AMG has no secondary VPS. That is an architectural gap to be addressed in a future infrastructure expansion, not a doctrine gap. The doctrine acknowledges the boundary and does not pretend otherwise.

---

## Section J — Glossary + References {#section-j}

### Glossary

| Term | Definition |
|------|-----------|
| **Actuator** | A watchdog component that takes an action (restart service, rotate log, push git) |
| **ADHD-Compatible** | Design constraint: operator must never need to monitor >1 interface or read >3 lines to understand system state |
| **Autonomic Computing** | Self-managing computing paradigm from IBM Research (2003); systems that configure, heal, optimize, and protect themselves |
| **Blast Radius** | Maximum scope of damage an autonomous action can cause |
| **Bounded Autonomy** | The principle that automated remediation operates within defined safe limits and stops at the boundary |
| **Chaos Engineering** | Disciplined experimentation on a system to build confidence in its ability to withstand turbulent conditions |
| **Cold Offload** | Moving files from hot VPS storage to cheaper cold storage (R2 Infrequent Access) |
| **Config Drift** | State where a running system configuration diverges from its authoritative source (git) |
| **Error Budget** | The maximum acceptable degradation for a given SLO within a time period |
| **Exponential Backoff** | Retry strategy where wait time doubles after each failed attempt |
| **HITL** | Human-In-The-Loop; points where automated systems pause for human decision |
| **Idempotent** | A script or operation that produces the same result regardless of how many times it's run |
| **MAPE-K** | Monitor-Analyze-Plan-Execute-Knowledge; IBM's autonomic computing control loop |
| **MIRROR_STATUS.md** | Titan's shared-state handoff file; truth source for current session context |
| **MTTR** | Mean Time to Recovery; average time to restore service after a failure |
| **MTTD** | Mean Time to Detect; average time between failure onset and detection |
| **Multi-Lane Doctrine** | AMG architecture principle: critical data paths have a primary and at least one failover lane |
| **n8n** | Open-source workflow automation platform; AMG's primary integration orchestration layer |
| **Playbook** | Pre-defined, step-by-step remediation procedure for a known failure mode |
| **SLI** | Service Level Indicator; a measurable metric (e.g., request error rate) |
| **SLO** | Service Level Objective; the target value for an SLI (e.g., <1% error rate) |
| **Sensor** | A watchdog component that reads system state and emits signals |
| **Supavisor** | Supabase's cloud-native Postgres connection pooler (successor to PgBouncer) |
| **Tier 0/1/2** | AMG's three-tier incident response model (silent/notify/escalate) |
| **Titan** | AMG's autonomous build agent; Claude Code running on VPS as a persistent session |
| **Toil** | Manual, repetitive operational work that is automatable and does not produce permanent value |
| **WATCHER_WATCHED** | The principle that the watchdog itself must be monitored by an external system |

### References

| Source | URL |
|--------|-----|
| Google SRE Book (Beyer et al.) | [sre.google](https://sre.google) |
| SRE Evolution 2025 | [visualpathblogs.com](https://visualpathblogs.com/site-reliability-engineering/the-biggest-changes-in-site-reliability-engineering-practices-in-2025/) |
| Netflix Chaos Engineering Principles | [infoq.com](https://www.infoq.com/news/2015/09/netflix-chaos-engineering/) |
| Chaos Engineering AI Evolution 2025 | [srao.blog](https://www.srao.blog/p/chaos-engineering-the-evolution-from) |
| IBM MAPE-K Autonomic Microservices | [conf-micro.services PDF](https://www.conf-micro.services/2022/papers/paper_9.pdf) |
| MAPE-K Loop Architecture 2025 | [emergentmind.com](https://www.emergentmind.com/topics/mape-k-loop) |
| MAPE-K Applied to Microservices | [unibo.it PDF](http://www.cs.unibo.it/~lanese/work/microservices2022-autonomic-Guidi.pdf) |
| AgentOps Guide 2025 | [zbrain.ai](https://zbrain.ai/agentops/) |
| AgentOps Error Recovery Patterns | [kinde.com](https://kinde.com/learn/ai-for-software-engineering/ai-agents/agentops/) |
| AI Self-Healing Kubernetes 2025 | [wjaets.com PDF](https://wjaets.com/sites/default/files/fulltext_pdf/WJAETS-2025-1255.pdf) |
| AI-Enhanced SRE Conf42 2025 | [conf42.com](https://www.conf42.com/Site_Reliability_Engineering_SRE_2025_Vijaybhasker_Pagidoju_selfhealing_infrastructure) |
| Self-Healing Microservices (IJETCSIT) | [ijetcsit.org](https://ijetcsit.org/index.php/ijetcsit/article/view/381) |
| GitOps Drift Detection | [oneuptime.com](https://oneuptime.com/blog/post/2026-02-26-configuration-drift-detection-gitops/view) |
| n8n Self-Healing Workflow | [reddit.com/r/n8n](https://www.reddit.com/r/n8n/comments/1se31kx/built_a_selfhealing_workflow_system_that_detects/) |
| n8n Community Self-Healing Node | [community.n8n.io](https://community.n8n.io/t/self-healing-wrapper-node-that-auto-repairs-failed-http-api-calls-with-pattern-learning/285177) |
| Caddy Reverse Proxy Docs | [caddyserver.com](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy) |
| Caddy Health Checks Guide | [thedevelopercafe.com](https://thedevelopercafe.com/articles/reverse-proxy-in-caddy-5c40d2fe21fe) |
| Supabase Connection Management | [supabase.com](https://supabase.com/docs/guides/database/connection-management) |
| Supavisor Pooler Architecture | [supabase.com blog](https://supabase.com/blog/supavisor-postgres-connection-pooler) |
| Supabase Crash Resilience | [reddit.com/r/Supabase](https://www.reddit.com/r/Supabase/comments/1r3a6es/supabase_crash_resilience_suggestions/) |
| Cloudflare R2 Lifecycle Docs | [developers.cloudflare.com](https://developers.cloudflare.com/r2/buckets/object-lifecycles/) |
| Docker Cleanup Automation | [oneuptime.com](https://oneuptime.com/blog/post/2026-02-08-how-to-automate-docker-cleanup-with-shell-scripts/view) |
| Docker systemd Timer | [shey.ca](https://shey.ca/2025/04/10/daily-docker-prune-with-systemd.html) |
| WebSocket Reconnection Production | [oneuptime.com](https://oneuptime.com/blog/post/2026-01-24-websocket-reconnection-logic/view) |
| WebSocket vs REST TTS | [deepgram.com](https://deepgram.com/learn/websocket-vs-rest-text-to-speech) |
| MCP Server Memory Management | [fast.io](https://fast.io/resources/mcp-server-memory-management/) |
| MCP Stale State Bug | [github.com](https://github.com/eyaltoledano/claude-task-master/issues/1637) |
| MCP Lifecycle Spec | [modelcontextprotocol.io](https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle) |
| LLM Spend Enforcement | [dev.to](https://dev.to/deeptishuklatfy/how-to-enforce-llm-spend-limits-per-team-without-slowing-down-your-engineers-ml) |
| AI Agent Budget Management | [tonic3.com](https://blog.tonic3.com/guide-to-smart-ai-agent-budget-token-consumption) |
| Post-Mortem Template | [uptimerobot.com](https://uptimerobot.com/knowledge-hub/monitoring/ultimate-post-mortem-templates/) |
| Incident Post-Mortem (incident.io) | [incident.io](https://incident.io/hubs/post-mortem/incident-post-mortem-template) |
| SLO / Error Budget Guide | [uptrace.dev](https://uptrace.dev/blog/sla-slo-monitoring-requirements) |
| SaaS SLA/SLO Guide | [up.report](https://up.report/blog/sla-slo-error-budgets-guide/) |

---

*AMG Self-Healing Operational Doctrine v1.0 — DR-AMG-RESILIENCE-01*  
*Companion doctrine: DR-AMG-SECURITY-01 (security, credentials, access control)*  
*Next scheduled doctrine review: July 2026*
