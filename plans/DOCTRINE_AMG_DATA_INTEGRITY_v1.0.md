# DR-AMG-DATA-INTEGRITY-01 — Data Integrity, Checksum, and Restore-Drill Doctrine

**Classification:** Internal Operational Doctrine (canonical candidate)
**Commission ID:** DR-AMG-DATA-INTEGRITY-01
**Version:** v1.0 (2026-04-15)
**Doctrine family:** Reliability-lane doctrines (sister to DR-AMG-RESILIENCE-01, DR-AMG-ACCESS-REDUNDANCY-01, DR-AMG-UPTIME-01, DR-AMG-RECOVERY-01)
**Owner:** AI Marketing Genius (AMG) — Solo Operator
**Review status:** drafted for CT-0414-08 adjudication; awaiting `grok_review` (sonar) A-grade pass; on pass, deploys canonical to `/opt/amg/docs/DR_AMG_DATA_INTEGRITY_01_v1.md`
**Last research anchor:** `<!-- last-research: 2026-04-15 -->`

---

## Table of Contents

- [Section A — Executive Summary](#section-a)
- [Section B — Data Asset Classification](#section-b)
- [Section C — Six Core Principles of Data Integrity](#section-c)
- [Section D — Checksum Architecture](#section-d)
- [Section E — Backup Topology](#section-e)
- [Section F — Snapshot Verification + Restore-Drill Schedule](#section-f)
- [Section G — RPO / RTO Commitments](#section-g)
- [Section H — Silent Corruption Detection](#section-h)
- [Section I — Write-Path Integrity Guarantees](#section-i)
- [Section J — Secrets + Credential Integrity](#section-j)
- [Section K — Restore Runbook Pattern](#section-k)
- [Section L — Tamper Detection + Response](#section-l)
- [Section M — Integration With Sister Doctrines](#section-m)
- [Section N — Anti-Patterns + Known Failure Modes](#section-n)
- [Section O — Glossary + References](#section-o)

---

## Section A — Executive Summary {#section-a}

Data is the asset AMG cannot rebuild from git. Code, config, and doctrine all regenerate from source control; client data, memory state, credentials, and generated deliverables do not. This doctrine defines the integrity posture for every data asset across AMG's infrastructure — what gets backed up, how often, how the backup is verified, how restores are drilled, and how silent corruption is caught before it compounds.

**The doctrine's central guarantee is: for every data asset, at any given moment, there exists at least one validated-uncorrupted copy that can be restored within the committed RTO, and the validation itself has happened within the committed freshness window.** An unvalidated backup is functionally indistinguishable from no backup; an unrestored backup is indistinguishable from a corrupt one. This doctrine forbids both.

The practical shape:
- **Postgres (Supabase managed primary + Hetzner-A read-replica):** RPO ≤ 1 second for replicated data (replica lag); daily logical + physical backups to R2 with sha256-verified checksums.
- **R2 object store:** server-side checksums on write + read; monthly prefix-level checksum audit; weekly restore-one-random-object drill.
- **MCP memory server state:** exported nightly to R2 as encrypted restic archive; weekly restore-into-staging-mcp verification.
- **File-based operator memory (`~/.claude/.../memory/`):** nightly restic to R2; weekly diff-check against source.
- **Credential env files (`/etc/amg/*.env`):** nightly encrypted restic snapshot; age-encrypted copies in 1Password as manual backup; quarterly restore-drill + rotation validation.
- **Titan-harness git state:** triple-mirror (Mac + VPS bare + GitHub) already per CLAUDE.md §17; this doctrine adds a per-mirror checksum audit.
- **Client deliverables (reports, audit artifacts):** each file sha256-pinned at creation; integrity verified on read; 3-month retention in R2 with lifecycle rule.

The doctrine commits to: **RPO ≤ 1 hour for relational data, ≤ 24 hours for object data, ≤ 5 minutes for memory state, zero for code (git). RTO ≤ 4 hours for full restore of any single asset, ≤ 30 minutes for partial / single-client restore.** Every commitment is drilled, not hypothesized.

**Expected outcomes:**
- Zero data-loss incidents in any rolling 12-month window.
- Every backup asset has been test-restored within its freshness window (quarterly minimum, weekly for critical assets).
- Silent corruption is detected and flagged within 24 hours of first corruption occurrence.
- Credential snapshots are readable and usable on any supported restore target.
- Restore runbooks are executable by operator from cold-start state without tribal knowledge.

**Out of scope:** availability (see UPTIME-01), access-lane redundancy (see ACCESS-REDUNDANCY-01), full-region disaster recovery (see RECOVERY-01), data-in-transit encryption / TLS posture (see DR-AMG-SECURITY-01).

---

## Section B — Data Asset Classification {#section-b}

### B.1 Asset tiers

Every data asset is tagged with one of four tiers:

| Tier | Definition | RPO | RTO | Backup cadence | Verify cadence |
|---|---|---|---|---|---|
| **T0 — Irreplaceable** | Lost forever if backup fails. Example: client-provided content the client doesn't have a copy of. | ≤ 5 min | ≤ 30 min | continuous | weekly |
| **T1 — Primary** | Re-acquirable but painful. Example: Postgres, MCP memory, operator memory. | ≤ 1 h | ≤ 4 h | hourly + daily full | weekly |
| **T2 — Regenerable** | Can be regenerated from upstream. Example: LiteLLM cache, embedding cache, intermediate pipeline outputs. | ≤ 24 h | ≤ 8 h | daily | monthly |
| **T3 — Ephemeral** | Local-only state; regenerates on service restart. Example: systemd journal, Docker logs. | n/a | n/a | best-effort | n/a |

### B.2 Asset inventory (point-in-time snapshot, 2026-04-15)

| Asset | Location | Tier | Backup target | Backup cadence |
|---|---|---|---|---|
| Postgres `public.*` (Supabase project `egoazyasyrhslluossli`) | Supabase managed | T1 | R2 bucket `amg-backups/postgres/` + Hetzner-A replica | Hourly WAL + daily full |
| MCP memory server state | VPS `/var/lib/mcp/` | T1 | R2 bucket `amg-backups/mcp/` | Nightly encrypted restic |
| Operator memory files | Mac `~/.claude/projects/-Users-solonzafiropoulos1-titan-harness/memory/` | T1 | R2 bucket `amg-backups/claude-memory/` + dotfiles repo | Nightly rsync + git |
| R2 client deliverables | R2 bucket `amg-client-deliverables/` | T0 (client-facing) | R2 cross-region replication (when enabled) + monthly audit | Write-once |
| R2 object snapshots | R2 bucket `amg-backups/` | T1 | self (source of truth for other backups) | — |
| `/etc/amg/*.env` files | VPS | T0 (can't regenerate keys) | R2 encrypted + 1Password vault | Nightly |
| titan-harness git | Mac + VPS bare + GitHub | T1 (regenerable from any one of 3) | self (triple-mirror already) | Every commit |
| Client deliverables (generated content per tier) | R2 | T1 | R2 (source) | N/A (write-once) |
| LiteLLM request/response cache | VPS `/var/lib/litellm/` | T2 | — | N/A |
| n8n execution logs | VPS Postgres | T2 | covered by Postgres backup | Hourly |
| Fireflies + Loom transcripts (for MP-1 corpus) | R2 bucket `amg-corpus-raw/` | T1 | R2 (replication when enabled) | Write-once |

### B.3 Classification governance

New assets are tagged during commissioning. The tag is stamped as a comment at the top of the service's config file (e.g. `# DATA_TIER: T1` in systemd unit). Untagged assets are presumed T3 ephemeral and receive no doctrine protection — this asymmetry pushes operators to tag deliberately.

---

## Section C — Six Core Principles of Data Integrity {#section-c}

### C.1 Principle 1 — A backup you have not restored is not a backup

Every T0 and T1 backup is exercised by a restore drill on a cadence proportional to its tier. The drill is not a "try to read it and see if bytes come back" — it is a full restore into a clean staging environment followed by functional validation (queries succeed, memory queries return correct results, credential opens correct vault).

### C.2 Principle 2 — Every byte written has a checksum

Every file that is backed up carries a sha256 checksum that was computed at write time, stored adjacent to the file, and verified on read. Corruption anywhere in the chain (bitrot, network transport error, transport-layer attack, ransomware targeting backup infrastructure) is detectable by comparing current-read sha256 against the stamped-at-write sha256.

### C.3 Principle 3 — Checksums are stored separately from the data

A checksum stored in the same object as the data it checks is useless against a replace-whole-object attack. Checksums live in a separate R2 bucket (`amg-checksums/`) with independent access credentials, and in Supabase (`public.backup_checksums` table) as a third replication.

### C.4 Principle 4 — Backup frequency is bounded by RPO commitment

If we commit to RPO ≤ 1 hour, backups run at least every hour. The commitment drives the schedule, not the other way around. Reducing RPO requires commensurately tightening backup cadence; loosening backup cadence (to save cost) requires explicit RPO commitment relaxation that ships as a doctrine amendment.

### C.5 Principle 5 — Restore runbooks are plain-English step-by-step from cold-boot

A restore runbook is written such that an operator who has never seen the asset can execute a successful restore by following the numbered steps. No "you'll know what to do" handwaving. Tribal knowledge in a restore runbook is a failure waiting to happen.

### C.6 Principle 6 — Silent corruption is louder than loud corruption

A ransomware event is obvious — half the servers are offline, alerts are firing. A silent bit-flip in an R2 object 14 months ago that's only noticed when the quarterly audit catches it is the dangerous class. This doctrine optimizes for catching silent corruption fast, not for showy response to obvious corruption.

---

## Section D — Checksum Architecture {#section-d}

### D.1 Checksum algorithm: sha256

Used universally for backup verification. Collision-resistant enough for this use-case; fast enough that backup + verify doesn't cost meaningful CPU; universally supported.

### D.2 Checksum stamping at write

Every backup write follows this sequence:

1. Stream data to R2 via multipart upload.
2. R2 computes ETag (not a sha256 by default — it's a content-MD5 or multipart-composite hash).
3. After upload completes, `bin/backup-stamp-checksum.sh` downloads the object, computes sha256, writes the checksum + object_key + upload_ts to:
   a. `amg-checksums/` R2 bucket as `<object_key>.sha256` text file (one-line).
   b. Supabase table `public.backup_checksums` row.
4. If the two writes don't succeed, the upload is considered failed and retried; no orphan objects left.

### D.3 Checksum verification on read

When a restore runbook is executed, the first step is always:

1. Download the target object from R2.
2. Fetch the checksum from `amg-checksums/<object_key>.sha256` (R2 copy).
3. Compute local sha256 of the downloaded object.
4. Compare local vs. R2-stored vs. Supabase-stored.
5. If ALL THREE match → proceed with restore.
6. If R2-stored and Supabase-stored match but local differs → object corrupted in transport, re-download.
7. If R2-stored and local match but Supabase differs → Supabase table was tampered, investigate as integrity incident before proceeding.
8. If R2-stored differs from Supabase-stored → one of the checksums was tampered, trigger §L incident response.

Multi-source checksum verification defeats single-location tampering.

### D.4 Continuous checksum audit

`bin/continuous-checksum-audit.sh` runs as a systemd timer every 4 hours on Hetzner-B (DR node per ACCESS-REDUNDANCY-01):

1. Lists every object in `amg-backups/` prefix.
2. For every object written ≥ 1 hour ago (allow batch uploads to settle), downloads + re-checksums.
3. Flags any mismatch to MCP `log_decision` tag `checksum_mismatch` severity critical.

This is the anti-silent-corruption insurance.

---

## Section E — Backup Topology {#section-e}

### E.1 Primary backup target: Cloudflare R2

R2 is the durability SOT. Choice justification:
- 99.999999999% durability claim per Cloudflare docs.
- No egress charges (critical for restore-drill cost envelope).
- Server-side encryption at rest.
- Lifecycle rules available for retention enforcement.
- API-compatible with S3 tooling (restic, rclone, aws-cli).

### E.2 Backup tooling: restic

`restic` is the canonical backup tool for all encrypted-at-rest snapshots.
- Deduplication: only changed blocks upload, keeping R2 storage cost predictable.
- Encryption: repo-level symmetric key; keys stored in `/etc/amg/restic.env` (mode 0400).
- Snapshots: each backup is a content-addressable snapshot; pruning is explicit.
- Integrity check: `restic check --with-cache` runs weekly.

### E.3 Repository structure

One restic repo per asset class, NOT one monolithic repo:

- `r2://amg-backups/restic-postgres/`
- `r2://amg-backups/restic-mcp/`
- `r2://amg-backups/restic-claude-memory/`
- `r2://amg-backups/restic-env-files/`
- `r2://amg-backups/restic-fireflies-corpus/`

Per-asset repos mean one compromise doesn't lose everything, and restore drills can be scoped per repo without scanning unrelated data.

### E.4 Retention policy per repo

| Repo | Hourly | Daily | Weekly | Monthly | Yearly |
|---|---|---|---|---|---|
| restic-postgres | 24 | 30 | 12 | 12 | 5 |
| restic-mcp | 0 | 14 | 8 | 12 | 3 |
| restic-claude-memory | 0 | 14 | 8 | 6 | 2 |
| restic-env-files | 0 | 14 | 8 | 12 | 10 (long for audit) |
| restic-fireflies-corpus | 0 | 7 | 4 | 6 | 2 |

Retention policy enforced via `restic forget --prune --keep-hourly N --keep-daily N ...` in a weekly cron.

### E.5 Off-R2 tertiary

For the T0 env-files asset, a second off-R2 copy exists:
- age-encrypted snapshot pushed to 1Password vault as a secure-note attachment.
- Quarterly cadence (aligned with the env-file rotation schedule).
- Manual trigger: `bin/push-env-snapshot-to-1password.sh`.

This is the "Cloudflare R2 regional disaster" insurance. Not used operationally; used only when R2 itself is the failure.

---

## Section F — Snapshot Verification + Restore-Drill Schedule {#section-f}

### F.1 Per-asset drill cadence

| Asset | Drill type | Cadence |
|---|---|---|
| Postgres | Full restore into staging-postgres → schema + row-count + sample query | Weekly |
| Postgres | Point-in-time restore to arbitrary timestamp in last 7 days | Monthly |
| MCP memory | Full restore into staging-mcp → semantic query returns expected results | Weekly |
| Claude memory files | Diff-check restore target matches current source within acceptable deltas | Weekly |
| Env files | Restore + can-unlock verification (keys successfully open corresponding services) | Quarterly |
| R2 client deliverables | Random-sample 10 objects → checksum + open | Weekly |
| R2 Fireflies corpus | Random-sample 5 transcripts → open + word-count sanity | Monthly |

### F.2 Drill automation

`bin/drill-restore.sh --asset <name>` runs a scripted drill:

1. Creates a scratch namespace (staging DB, staging MCP on Hetzner-B, temp directory).
2. Pulls the latest backup for the named asset.
3. Verifies checksum per §D.3.
4. Restores into the scratch namespace.
5. Runs the asset's functional-check script (e.g. `SELECT count(*) FROM users` on Postgres; `search_memory("known query")` on MCP).
6. Emits a pass/fail result + elapsed time.
7. Logs to MCP with tag `drill_<asset>` and `drill_result`.

### F.3 Drill failure handling

A failed drill is a P1 incident:
- Slack DM to operator.
- MCP log_decision severity high.
- Automatic escalation if 2 consecutive drills on the same asset fail: enters Lockdown stance per UPTIME-01 §D until drill succeeds.

### F.4 Chaos-drill (optional quarterly)

Random-object corruption drill:

1. Quarterly, `bin/chaos-inject-corruption.sh --repo restic-postgres --one-block` flips a single bit in a non-critical snapshot block.
2. Wait for §D.4 continuous audit to detect.
3. Measure time-to-detection.
4. Heal via `restic rebuild-index` or point-in-time restore from last-known-good.
5. Restore original snapshot (chaos drill is non-destructive; original is preserved in a sibling path).

---

## Section G — RPO / RTO Commitments {#section-g}

### G.1 Per-asset commitments

| Asset | RPO | RTO | Confidence |
|---|---|---|---|
| Postgres relational | ≤ 1 s (replica lag) / ≤ 1 h (PITR) | ≤ 30 min | High |
| MCP memory | ≤ 5 min (if memory-write-through enabled) / ≤ 24 h | ≤ 1 h | High |
| Claude memory files | ≤ 24 h | ≤ 30 min | High |
| Env files | ≤ 24 h | ≤ 15 min | High |
| R2 client deliverables | Zero (write-once) | ≤ 30 min | High |
| R2 Fireflies corpus | Zero (write-once) | ≤ 2 h | Medium (depends on corpus size) |
| titan-harness git | Zero (3-way replication) | Zero (any of 3) | High |

### G.2 Committed RTO measurement

RTO numbers are not aspirations — they are measured from drill execution times (§F). If a drill consistently exceeds the committed RTO by > 2×, the commitment is either revised (doctrine amendment) or invested against (tooling improvement).

### G.3 Degraded-restore RTO

Partial restore (single-client, single-table) must be ≤ 30 minutes for T0/T1 assets. Single-asset scoping is tested quarterly via the `bin/drill-restore.sh --scope single-client` variant.

---

## Section H — Silent Corruption Detection {#section-h}

### H.1 Bitrot detection

`amg-backups/` objects ≥ 1 hour old are continuously verified via §D.4. Any mismatch between R2-stored and recomputed-from-download sha256 is a bitrot event.

### H.2 Database corruption detection

- Postgres `pg_amcheck` runs weekly on the Hetzner-A replica (non-disruptive).
- `amcheck` results stored in `public.db_integrity_checks` table with timestamp.
- Any heap-corruption report triggers P1 alert + immediate full restore drill to verify replica catches it.

### H.3 Replica divergence detection

- Hourly: `lib/replica_divergence_check.py` samples 100 random primary-key rows from a canary table, compares primary vs replica.
- Divergence > 0 rows triggers P1.
- This catches replication-layer corruption that lag metrics miss.

### H.4 Memory corruption detection

- Weekly: `lib/mcp_memory_integrity_check.py` queries for known-stable canary records seeded during setup.
- Missing or changed canary values indicate MCP state corruption (e.g. from Supabase schema drift, embedding recomputation gone wrong).

### H.5 Tamper detection vs corruption detection

Corruption = accidental state change.
Tamper = intentional state change.

Same detection method (checksum mismatch) flags both. Classification happens during incident response per §L: evidence of unauthorized access patterns (unusual Supabase API calls, R2 access from unexpected IPs) distinguishes tamper from corruption.

---

## Section I — Write-Path Integrity Guarantees {#section-i}

### I.1 Atomic writes

All canonical data writes are atomic at the storage layer:
- Postgres: transactions with ACID.
- R2: multipart upload atomically completes or does not; never leaves half-objects.
- restic: snapshot-level atomicity; partial snapshots are automatically discarded on next `restic check`.
- Env files: written via `install -m 0400 <src> <dst>` or `mv -f temp target` for atomic replace.

### I.2 Idempotency

Every backup-write operation is idempotent. Re-running a backup shortly after a successful one produces (a) no-op if the data hasn't changed (restic dedup) or (b) a new snapshot that doesn't corrupt the previous one.

### I.3 Write-ahead logging

Postgres WAL-shipping to Hetzner-A replica provides write-path replay capability. WAL files are retained on Supabase for 7 days (their default) and on Hetzner-A for 30 days.

### I.4 Multi-write consistency

Operations that write to multiple backends (e.g. updating Supabase + writing a backup snapshot + posting an MCP memory record) follow the outbox pattern:

1. Primary write to Supabase.
2. On success, queue the secondary writes to durable outbox (`public.outbox_messages`).
3. Outbox worker processes them; retries on failure; poison-message after 10 retries (logged + operator-flagged).

This prevents partial failures from producing inconsistent cross-backend state.

---

## Section J — Secrets + Credential Integrity {#section-j}

### J.1 Env-file write discipline

- Every `/etc/amg/*.env` edit goes through `bin/edit-env-file.sh <name>` which (a) diffs, (b) computes old+new sha256, (c) writes atomically, (d) logs edit via MCP tag `env_edit`, (e) triggers nightly restic backup out-of-band.
- Direct `vi /etc/amg/*.env` is discouraged but not blocked (operator occasionally needs emergency edits).

### J.2 Rotation validation

Every credential rotation is followed by:
- Immediate restic snapshot of post-rotation state.
- Functional verification: the service using the credential successfully authenticates.
- 1Password vault update (manual) to match.
- MCP log_decision with tag `credential_rotation`.

### J.3 Compromised-credential response

Evidence of a compromised credential triggers:
- Immediate rotation (new key generation, new env-file write, service reload).
- Old credential revocation at the provider (Supabase Management API, Cloudflare API token revoke, etc.).
- MCP log_decision severity critical.
- If scope is uncertain, rotate all credentials in the same env-file scope as the compromised one.

---

## Section K — Restore Runbook Pattern {#section-k}

### K.1 Runbook template

Every restore runbook follows this structure:

1. **Preconditions:** what must be true before starting.
2. **Escape-hatch check:** verify operator can reach the restore target (SSH, Tailscale, console).
3. **Checksum fetch:** obtain the latest checksum record from the 3-location triplet (§D.3).
4. **Download:** pull backup from R2 with checksum verification inline.
5. **Staging restore:** restore into scratch namespace first (not production).
6. **Functional test:** run the asset's known-good validation query / operation.
7. **Cutover:** promote staging to production (with appropriate coordination).
8. **Post-restore validation:** 7-check list analogous to ACCESS-REDUNDANCY §I.4.
9. **Log:** MCP log_decision with restore metadata.
10. **After-action:** if this was an emergency restore (not a drill), schedule post-mortem per UPTIME §G.3.

### K.2 Canonical runbooks (files)

- `plans/deployments/RESTORE_POSTGRES.md`
- `plans/deployments/RESTORE_MCP_MEMORY.md`
- `plans/deployments/RESTORE_CLAUDE_MEMORY_FILES.md`
- `plans/deployments/RESTORE_ENV_FILES.md`
- `plans/deployments/RESTORE_R2_OBJECT.md`
- `plans/deployments/RESTORE_GIT_FROM_MIRROR.md`

Each file is subject to the drill cadence from §F.1.

### K.3 Runbook freshness

Every runbook has a `<!-- last-drill-pass: YYYY-MM-DD -->` marker at the top. Runbooks whose marker is older than their expected drill cadence + grace period (e.g. weekly drill + 2 weeks grace = stale at 3 weeks) trigger a `#titan-nudge` Slack nudge.

---

## Section L — Tamper Detection + Response {#section-l}

### L.1 Indicators of tamper

- Checksum mismatch inconsistent with bitrot probability (multiple objects in same prefix flagged simultaneously).
- Unusual R2 access pattern (unknown IPs in R2 audit logs).
- Unusual Supabase API activity (Management API calls from off-hours, unknown source).
- Env-file mtime change without corresponding `bin/edit-env-file.sh` invocation log.
- Systemd service config mtime changes not in git.

### L.2 Immediate response

1. Freeze writes: `bin/writes-freeze.sh --scope <suspect-asset>` sets a Postgres advisory lock + R2 bucket write-deny policy (temporary).
2. MCP log_decision severity critical tag `tamper_suspected`.
3. Slack alert to operator (Pushover critical — wake-up).
4. Do NOT restore until scope is determined — restoring from a potentially-tampered backup compounds the issue.

### L.3 Scope determination

Using the audit log triplet (MCP, R2 access log, Supabase audit log), determine:

- What accounts / tokens performed the suspect actions?
- What time window?
- What range of assets were touched?

### L.4 Recovery path

After scope is clear:

1. Identify last-known-good backup (one before the tamper window).
2. Restore via runbook to staging.
3. Validate staging integrity.
4. Cutover production from staging.
5. Rotate every credential that had R/W access to tampered assets.
6. Post-mortem, plus an incident-class entry in RESILIENCE-01's incident-learning loop.

---

## Section M — Integration With Sister Doctrines {#section-m}

### M.1 DR-AMG-ACCESS-REDUNDANCY-01

Access-lane failover (§I of sister) carries zero RPO for data served from R2 (shared SOT per §G of sister). Postgres-replica lag is the RPO floor for DB-backed surfaces; this doctrine's § G.1 commits ≤ 1 s.

### M.2 DR-AMG-UPTIME-01

Data-integrity incidents can trigger SLO incidents if restore takes longer than acceptable. Per UPTIME §G.1 SEV-2 classification; weighted minute counting.

### M.3 DR-AMG-RESILIENCE-01

Drill failures feed RESILIENCE-01's incident-learning loop. Repeated drill failures on the same asset indicate a doctrine-level gap (maybe the backup tool is wrong, maybe the runbook is wrong) and trigger a quarterly doctrine refresh.

### M.4 DR-AMG-RECOVERY-01

Full-region disaster recovery uses this doctrine's backups + restore runbooks as primitives, but composes them in a different sequence optimized for single-day re-provision from cold. RECOVERY-01 is the composition; this doctrine provides the components.

### M.5 DR-AMG-ENFORCEMENT-01 v1.4

ENFORCEMENT-01's Gate #4 protects against the credentials-compromise class that could tamper with backup integrity. Rotation runbooks here feed audit records there.

### M.6 DR-AMG-SECURITY-01 (commissioned)

Security doctrine owns encryption-at-rest validation, key management, and access-control policies. This doctrine assumes those guarantees and focuses on integrity given them.

---

## Section N — Anti-Patterns + Known Failure Modes {#section-n}

### N.1 Anti-pattern: the backup that is never restored

Covered under §C.1 principle. Addressed via mandatory drill cadence §F.1.

### N.2 Anti-pattern: the single-location checksum

Covered under §C.3 principle. Addressed via triple-location checksum storage §D.3.

### N.3 Anti-pattern: the synchronous cross-region write

For Postgres, we use asynchronous replication (ACCESS-REDUNDANCY §O.3). For R2, we rely on Cloudflare's durability; cross-region replication is opt-in and adds latency to writes. This doctrine does not turn on cross-region R2 replication; if a future regulatory requirement mandates it, that's a doctrine amendment.

### N.4 Anti-pattern: restoring to production without staging

Bypassing staging is fast but dangerous. Doctrine forbids it for T0/T1 assets except in declared emergency (operator must tag the runbook invocation with `--emergency-direct` which logs to MCP severity critical).

### N.5 Known failure mode: restic repo-key loss

If `/etc/amg/restic.env` is lost without backup, the restic repos become unreadable. Mitigation: the key is part of the env-files tier T0 with triple-backup (R2 + 1Password + age-encrypted paper copy of the master).

### N.6 Known failure mode: R2 region outage

R2 region outage blocks backups + restores for the duration. Mitigation: the tertiary 1Password snapshot of env files survives; Postgres replica on Hetzner-A survives; git mirror triple-redundancy survives. Client deliverables stored only in R2 are temporarily unavailable but not lost (durability guarantee).

### N.7 Known failure mode: outbox-worker stall

If the outbox worker dies and isn't restarted, secondary writes stop, and cross-backend consistency drifts. Mitigation: outbox worker is a systemd unit with `Restart=always`; the operator's `/orb` dashboard shows outbox depth; depth > 1000 messages triggers `#titan-nudge`.

---

## Section O — Glossary + References {#section-o}

### O.1 Glossary

- **RPO (Recovery Point Objective)** — maximum acceptable data loss measured in time (e.g. ≤ 1 h means we can lose at most the last hour's data).
- **RTO (Recovery Time Objective)** — maximum acceptable restore time (e.g. ≤ 4 h means the system must be back within 4 h of declared outage).
- **Bitrot** — spontaneous flip of a single bit in storage; cumulative in long-retained backups.
- **Tamper** — intentional unauthorized modification of data.
- **Canary** — a known-stable record used as a continuous-integrity sentinel.
- **Drill** — scripted restore exercise that proves the backup works in the real failure path.
- **Outbox** — durable queue of secondary writes; prevents partial-failure inconsistency.

### O.2 References

- Google SRE Workbook, Ch. 9 "Data Integrity: What You Read Is What You Wrote" (canonical industry framework).
- "Effective Data Consistency Patterns" — Pat Helland (2013).
- Amazon Aurora technical papers on WAL-shipping replication patterns.
- Cloudflare R2 documentation — object model + durability guarantees.
- restic.readthedocs.io — backup tool semantics.
- CLAUDE.md §17.2 — Auto-Harness auto-mirror for git triple-replication.
- DR-AMG-ACCESS-REDUNDANCY-01 §G — shared-nothing state consumption model.
- DR-AMG-UPTIME-01 §G — incident counting (data-integrity-triggered outages).

---

*End of doctrine DR-AMG-DATA-INTEGRITY-01 — version 1.0 (2026-04-15).*
*Grade block to be appended after grok_review adversarial pass.*
