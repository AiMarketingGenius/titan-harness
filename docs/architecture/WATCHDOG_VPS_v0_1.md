# WATCHDOG VPS v0.1

**Target canonical path:** `/opt/amg-docs/architecture/WATCHDOG_VPS_v0_1.md`
**Staged path:** `/Users/solonzafiropoulos1/titan-harness/docs/architecture/WATCHDOG_VPS_v0_1.md`
**Owner:** Achilles, CT-0427-56
**Status:** Ship-ready build spec for Titan CT-0427-57. No deploy, credential, or live cleanup performed in this doc-only phase.

## 1. Purpose

CT-0427-35 proved the VPS had no resident disk watchdog: disk climbed to 97% before humans noticed. CT-0427-57 exists to build the missing guardrail. This spec defines the first safe production version.

Primary goals:

- Detect disk, inode, memory, and watchdog-process failures before the VPS enters operator-visible outage.
- Perform only bounded safe remediation automatically.
- Escalate owner-risk cleanup candidates without silently deleting valuable data.
- Produce structured receipts so Aletheia/Argus can verify the watchdog honestly.

## 2. Non-Goals

This v0.1 watchdog does not:

- delete Ollama models automatically
- delete KB binaries automatically
- prune active Docker images or volumes automatically
- restart databases or critical services automatically
- rotate credentials
- mutate cloud, DNS, payment, or firewall state

Those are explicit owner-risk actions or separate runbooks.

## 3. Signals

### 3.1 Disk

| Metric | Warn | Action | Critical |
|---|---:|---:|---:|
| root filesystem used % | 80 | 85 | 92 |
| free GiB | 25 | 15 | 8 |
| inode use % | 80 | 85 | 92 |

### 3.2 Memory

| Metric | Warn | Action | Critical |
|---|---:|---:|---:|
| RAM used % | 85 | 90 | 95 |
| swap used % | 50 | 75 | 90 |

### 3.3 Process/Service Health

Required process groups:

- queue workers
- Redis shared
- Atlas API
- operator memory / MCP surface
- Docker daemon

Required behavior:

- detect missing service
- detect service flapping
- detect stale heartbeat from the watchdog itself

## 4. Cadence

| Loop | Cadence | Purpose |
|---|---|---|
| `watchdog-fast` | every 5 min | disk %, free GiB, RAM %, swap %, heartbeat |
| `watchdog-slow` | every 15 min | top-N disk offenders, inode scan, service-health audit |
| `watchdog-daily` | daily | summary decision, trend delta, repeated offender list |

## 5. Safe Auto-Remediation

Safe remediation is allowed only after crossing the Action threshold and only for the following classes:

1. `journalctl --vacuum-size=<cap>` to a fixed cap.
2. delete transient tool caches older than policy threshold:
   - Playwright cache
   - Trivy cache
   - temp staging dirs
3. delete clearly stale rotated logs beyond retention.
4. run `docker image prune` for dangling images only.
5. rotate watchdog-owned logs.

Every safe action must be:

- idempotent
- individually logged
- size-measured before and after
- reversible only where practical; if not reversible, the target class must still be clearly non-user data

## 6. Owner-Risk Escalation Buckets

If the VPS remains above 85% after safe remediation, the watchdog does not guess. It creates an escalation bundle containing:

- top 20 disk consumers
- reclaim estimate per candidate
- exact command that would be run
- why the candidate is owner-risk

Owner-risk classes for v0.1:

- Ollama model deletion
- KB binary relocation/deletion
- non-dangling Docker image or volume pruning
- application data directories
- any file under `/home/amg/kb`

## 7. No-Touch List

The watchdog must never auto-delete from:

- `/home/amg/kb`
- active Docker volumes
- live database storage
- `/etc`
- current Ollama model set
- any path tagged in config as `protected_path`

## 8. Structured Receipt Contract

Every run emits a JSON receipt:

```json
{
  "ok": true,
  "mode": "fast|slow|daily",
  "ts": "2026-04-27T22:30:00Z",
  "disk_used_pct": 77,
  "free_gib": 42.1,
  "inode_used_pct": 18,
  "ram_used_pct": 63,
  "swap_used_pct": 0,
  "safe_actions": [
    {
      "name": "journal_vacuum",
      "bytes_reclaimed": 251658240,
      "status": "applied"
    }
  ],
  "owner_risk_candidates": [
    {
      "path": "/usr/share/ollama/.ollama/models",
      "bytes_est": 32000000000,
      "reason": "model deletion requires owner approval"
    }
  ],
  "alerts_sent": [
    "mcp_decision",
    "slack_admin"
  ],
  "blocked": false,
  "blocker": ""
}
```

Invalid receipt output is a failure.

## 9. Logging And Escalation

Required writes:

- `log_decision(project_source="achilles", tags=["ct-0427-57", "watchdog-vps", "watchdog-fast|slow|daily"])`
- `flag_blocker` when:
  - repeated critical threshold across 2 consecutive loops
  - safe remediation fails
  - receipt is missing
  - watchdog heartbeat is stale

Slack/admin notification rules:

- warn threshold: MCP decision only
- action threshold: MCP decision + Slack admin post
- critical threshold: MCP decision + Slack admin post + `flag_blocker`

## 10. Build Shape For Titan

Minimum deliverables for CT-0427-57:

- one config file with thresholds and protected paths
- one fast loop script/service
- one slow loop script/service
- one daily summary script/service
- one receipt directory
- one launch/supervisor manifest appropriate for VPS
- one read-only verification script

## 11. Acceptance Criteria

1. The watchdog detects root disk %, free GiB, inode %, RAM %, and swap %.
2. The watchdog emits a JSON receipt on every loop.
3. Safe remediation is limited to the allowed classes in §5.
4. Protected paths in §7 are never auto-mutated.
5. Action-threshold breaches create both a receipt and a decision log.
6. Critical-threshold breaches escalate via blocker, not just logging.
7. Owner-risk candidates are surfaced with path + reclaim estimate + reason.
8. Dangling-image prune is the maximum Docker mutation allowed in v0.1.
9. The watchdog can be verified by a read-only script with no side effects.
10. Missing watchdog receipt is itself treated as a failure condition.
11. One synthetic test proves critical disk state becomes alert + blocker without destructive cleanup.
12. One synthetic test proves safe cache/journal cleanup logs reclaimed bytes correctly.

## 12. Self-Score

| Dimension | Score | Note |
|---|---:|---|
| Technical soundness | 9.2 | Conservative signal set and bounded actions. |
| Completeness | 9.1 | Covers disk, memory, inodes, services, receipts, and escalation. |
| Edge cases | 9.0 | Missing receipt and repeated critical loops are explicit. |
| Risk identification | 9.4 | Separates safe cleanup from owner-risk cleanup clearly. |
| Evidence quality | 9.2 | Structured receipt and verification path are first-class. |
| Operational discipline | 9.3 | No destructive silent behavior; blocker path is fail-closed. |

Overall: 9.2/10.
