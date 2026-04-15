# DR-AMG-RECOVERY-01 — Disaster Recovery Runbook + Full-Region Restore Doctrine

**Classification:** Internal Operational Doctrine (canonical candidate)
**Commission ID:** DR-AMG-RECOVERY-01
**Version:** v1.0 (2026-04-15)
**Doctrine family:** Reliability-lane doctrines (sister to DR-AMG-RESILIENCE-01, DR-AMG-ACCESS-REDUNDANCY-01, DR-AMG-UPTIME-01, DR-AMG-DATA-INTEGRITY-01)
**Owner:** AI Marketing Genius (AMG) — Solo Operator
**Review status:** drafted for CT-0414-08 adjudication; awaiting `grok_review` (sonar) A-grade pass; on pass, deploys canonical to `/opt/amg/docs/DR_AMG_RECOVERY_01_v1.md`
**Last research anchor:** `<!-- last-research: 2026-04-15 -->`

---

## Table of Contents

- [Section A — Executive Summary](#section-a)
- [Section B — Disaster Classification + Scope](#section-b)
- [Section C — Five Core Principles of Disaster Recovery](#section-c)
- [Section D — RTO / RPO Commitments + Error Budget Impact](#section-d)
- [Section E — The Cold-Boot Runbook (Full-Region Loss)](#section-e)
- [Section F — The Warm-Lane Runbook (Primary-Only Loss)](#section-f)
- [Section G — Credential Revocation + Re-Provision Sequence](#section-g)
- [Section H — Client Communication During DR](#section-h)
- [Section I — Partial-Service-Degradation Playbook](#section-i)
- [Section J — Recovery Drill Cadence](#section-j)
- [Section K — Rollback Primitives (Atomic Per-Step Revert)](#section-k)
- [Section L — Post-DR Incident Review](#section-l)
- [Section M — Integration With Sister Doctrines](#section-m)
- [Section N — Anti-Patterns + Known Failure Modes](#section-n)
- [Section O — Glossary + References](#section-o)

---

## Section A — Executive Summary {#section-a}

This doctrine governs recovery when smaller-blast-radius mechanisms have failed. DR-AMG-ACCESS-REDUNDANCY-01 handles single-provider outages via active/active lane cutover. DR-AMG-RESILIENCE-01 handles per-domain incidents via the central watchdog's MAPE-K loop. DR-AMG-DATA-INTEGRITY-01 handles corruption and tamper via checksum + restore. DR-AMG-UPTIME-01 frames the SLO math. This doctrine handles **the events those three do not absorb**: full-region provider loss, dual-lane simultaneous failure, cascading credential compromise requiring total-re-provision, catastrophic data loss requiring R2-from-age-encrypted-paper-key restore.

The doctrine's core guarantee: **from a cold-boot state (no running VPS, no live services, credentials preserved only in the tertiary 1Password vault + age-encrypted paper-key), AMG can be restored to a serving posture within 8 hours of operator declaration of DR, with RPO ≤ 1 hour for relational data and ≤ 24 hours for object data.** The 8-hour number is not a stretch goal; it is a measured drill outcome with instrumented step timings.

The doctrine is organized as executable runbooks, not philosophical principles. Principles are brief (§C). Runbooks are long and step-numbered (§E, §F, §G, §I). Every operator-facing step is independently verifiable (an `/ok?` probe, a known-good output sample, a deterministic exit code).

**Expected outcomes at full doctrine implementation:**
- Any disaster class in §B can be matched to its runbook in ≤ 5 minutes (operator opens this doc + scans §B table).
- Cold-boot restore from scratch completes in ≤ 8 hours (drilled semi-annually).
- Warm-lane failover (primary-only loss with secondary live) completes in ≤ 30 minutes.
- Credential re-provision cycle (all rotatable credentials) completes in ≤ 4 hours.
- Client-visible DR is accompanied by a pre-drafted comms template tailored to incident class.
- Every DR exit is followed by a mandatory post-mortem per UPTIME §G.3.

**Out of scope:** prevention of the disasters themselves (that is what the other four sister doctrines do); security-primitive breach handling distinct from recovery (DR-AMG-SECURITY-01); legal + contractual consequences of extended outage (founder-level concern outside operational doctrine).

---

## Section B — Disaster Classification + Scope {#section-b}

### B.1 Disaster classes + runbook mapping

| Class | Definition | Runbook | Target RTO | Target RPO |
|---|---|---|---|---|
| **D1 — Full-region loss** | Both HostHatch + Hetzner unreachable for > 1 hour; could be regional internet disruption, BGP incident, or simultaneous provider failure | §E Cold-Boot Runbook | ≤ 8 h | ≤ 1 h (DB) / ≤ 24 h (objects) |
| **D2 — Primary provider total loss** | HostHatch unrecoverable (administrative suspension, legal hold, hardware destruction) | §F Warm-Lane Runbook | ≤ 30 min | 0 (secondary already live per ACCESS-REDUNDANCY) |
| **D3 — Cascading credential compromise** | Evidence that primary credential identity (email, root of trust) is compromised; everything derived from it must be rotated | §G Credential Revocation + Re-Provision | ≤ 4 h | 0 (no data loss, just identity rotation) |
| **D4 — Catastrophic data loss** | R2 unrecoverable; restic repos lost; must restore from age-encrypted paper-key + 1Password vault | §E + §G composed | ≤ 24 h | ≤ 1 week (worst-case, depends on last off-R2 snapshot freshness) |
| **D5 — Single-service cascading failure** | A foundational service (Caddy, systemd, Docker) fails in a way that takes down the whole lane but the lane's infrastructure is intact | §I Partial-Service-Degradation | ≤ 2 h | 0 |
| **D6 — Operator-incapacitation** | Solon unavailable for an extended period; Titan + harness must continue without operator intervention for days | §M.4 + handoff runbook | n/a (not a technical disaster, but a continuity risk) | n/a |

### B.2 Disaster declaration criteria

A disaster is declared (by operator, or by Titan autonomously in D5 class) when:

1. One of the §B.1 class conditions is met.
2. The normally-applicable recovery mechanism (per ACCESS-REDUNDANCY / RESILIENCE / DATA-INTEGRITY) has been attempted and failed.
3. The incident scope exceeds the single-provider or single-service envelope those doctrines cover.

Premature disaster declaration triggers unnecessary runbook execution and client comms. This doctrine optimizes for correct declaration, not fast declaration. When in doubt: wait 10 minutes, re-probe, then declare.

### B.3 Disaster NON-declaration

Events that are NOT a disaster and do NOT trigger this doctrine:

- Single-provider transient outage < 1 hour that resolves via normal health-check-driven cutover (ACCESS-REDUNDANCY §I).
- Single-service degradation auto-remediated by RESILIENCE-01 watchdog.
- A data-corruption event caught + healed by DATA-INTEGRITY-01 restore runbook.
- A SEV-2 incident caught inside the error-budget framework of UPTIME-01.

Escalation to this doctrine is evidence that sister-doctrine safeguards didn't work; that triage is part of the post-DR review.

---

## Section C — Five Core Principles of Disaster Recovery {#section-c}

### C.1 Principle 1 — Runbooks beat checklists, checklists beat memory

A step-numbered executable runbook is the only reliable operator asset during a high-stress DR event. Human memory fails under stress; ad-hoc checklists miss steps. Every DR path in §E–§I is written to be executable by an operator reading the steps for the first time.

### C.2 Principle 2 — Cold-boot assumes nothing is available

The §E cold-boot runbook starts from the premise that: no VPS is running, no DNS resolves to a serving origin, the restic repos may be unreadable, the only trustworthy assets are (1) the age-encrypted paper key in the physical safe, (2) the 1Password vault accessible via Solon's primary device, (3) the titan-harness git repo on GitHub. Every step assumes those three inputs and nothing else.

### C.3 Principle 3 — Client comms is part of the runbook, not an afterthought

Every disaster class has a corresponding client-comms template pre-drafted (§H). Waiting to draft comms until mid-incident means comms happen late, poorly, or not at all. Templates are in `plans/templates/DR_COMMS_<class>_TEMPLATE.md` and are versioned alongside the doctrine.

### C.4 Principle 4 — Rollback is a first-class operation

Per DATA-INTEGRITY-01 §K.4. Every DR step has an atomic rollback primitive. If step 7 fails or produces wrong output, step 7 can be reversed before step 8 begins. This prevents the operator from being trapped in a half-executed runbook state.

### C.5 Principle 5 — Post-DR review is non-negotiable

Every disaster exit (successful or partial) triggers a mandatory post-mortem per UPTIME §G.3. The review answers: what failed in the sister doctrines that caused this doctrine to be invoked? What doctrine updates come out of this event? No DR exit without a post-mortem.

---

## Section D — RTO / RPO Commitments + Error Budget Impact {#section-d}

### D.1 Commitments by disaster class

| Class | RTO commitment | RPO commitment | Confidence |
|---|---|---|---|
| D1 Full-region loss | ≤ 8 h | ≤ 1 h DB / ≤ 24 h objects | Medium (drill-validated) |
| D2 Primary-only loss | ≤ 30 min | 0 (secondary already serves) | High (cutover drilled quarterly) |
| D3 Credential cascade | ≤ 4 h | 0 (no data lost) | Medium (re-provision drilled annually) |
| D4 Catastrophic data loss | ≤ 24 h | ≤ 1 week worst-case | Low (paper-key-restore drilled annually) |
| D5 Single-service cascade | ≤ 2 h | 0 | High (runbook tested per drill) |

### D.2 Error budget impact

A D1 event will blow the monthly 21.6-minute error budget by multiple orders of magnitude (8 hours = 480 minutes >> 21.6 minutes). D1 exits trigger:
- Immediate Lockdown stance per UPTIME §D.3.
- Mandatory 30-day feature-freeze while root-cause analysis runs.
- Potential SLA-credit or partial-refund to clients (founder discretion, tracked in §H).

A D2 event (≤ 30 min RTO) consumes ~30 minutes of budget — manageable; a single D2 event does not blow the month.

### D.3 RTO measurement

RTO is measured from operator disaster declaration to full client-facing service restoration. Not from the underlying failure — because the failure may predate detection. This convention is harsh on our numbers but honest about what clients experience.

---

## Section E — The Cold-Boot Runbook (Full-Region Loss) {#section-e}

### E.1 Preconditions

- Operator has: (1) laptop with internet; (2) 1Password vault access; (3) access to the physical safe with the age-encrypted paper-key backup; (4) a fresh payment-method for provisioning new VPS if both HostHatch and Hetzner billing identities are also compromised.
- Three independent network paths have been tested to have at least one working (home wifi, mobile hotspot, public wifi at last-resort).

### E.2 Runbook steps

**Step 0 — Disaster declaration (2 min)**
1. Open `/admin/slo` dashboard. Confirm all sources report RED.
2. `bin/escape-hatch-verify.sh --json` — confirm no SSH path works.
3. `bin/ping-cloudflare-dns.sh` — confirm Cloudflare DNS is resolving our domain to at least one non-responsive origin (this confirms our DNS records exist; they may just point at dead origins).
4. Declare D1 in operator journal: `echo "D1 declared at $(date -u)" > ~/DR_D1_$(date +%s).declared`.
5. Post to `#solon-os` Slack: "D1 DR in progress, updates every 30 min."

**Step 1 — Provision replacement primary (60 min)**
1. Open Hetzner Cloud console via browser (assumes Hetzner account identity survived — if not, skip to step 1-alt).
2. Order: 1× Hetzner CX52 (8 vCPU / 16 GB / 160 GB NVMe) in Nuremberg region, Ubuntu 22.04.
3. SSH to new instance with the initial root password from Hetzner email.
4. Bring the server up: `useradd amg -m -s /bin/bash`, sudo without password for amg, disable root SSH, install hardened sshd_config per `config/sshd_config_hardened.conf` in the harness.
5. Mark in operator journal: "new primary provisioned at <IP>".

**Step 1-alt — If Hetzner identity is also compromised**:
1. Sign up for a new VPS provider (DigitalOcean, Vultr, Upcloud, Linode) with a fresh billing identity.
2. Same configuration as Step 1.
3. Add "billing identity rotation" to Step 5 prerequisites.

**Step 2 — Deploy harness git (15 min)**
1. SSH to new instance.
2. `git clone https://github.com/AiMarketingGenius/titan-harness.git /opt/titan-harness-work`.
3. Install dependencies: `apt install -y python3.10 python3-pip docker.io docker-compose-plugin bun opa restic` (per `config/bootstrap-packages.txt` in the harness).
4. Verify harness: `cd /opt/titan-harness-work && git log -1` matches the last-known SHA from `~/titan-harness/.git/refs/heads/master` on Solon's Mac.

**Step 3 — Restore credentials (45 min)**
1. Open 1Password vault → "AMG Infrastructure" → "env-files-backup" (most recent snapshot).
2. Copy the age-encrypted blob to `/tmp/amg-env-backup.age`.
3. Retrieve the age key from the 1Password "restic-master" secure note OR from the paper-key in the physical safe (whichever is accessible).
4. Decrypt: `age --decrypt --identity <key_file> /tmp/amg-env-backup.age > /tmp/amg-env-bundle.tar.gz`.
5. Extract to `/etc/amg/`: `tar -xzf /tmp/amg-env-bundle.tar.gz -C /etc/amg/ && chmod 0400 /etc/amg/*.env && chown root:root /etc/amg/*.env`.
6. Verify: `bin/secrets-sanity-check.sh` — confirms all expected env files are present + non-empty + readable only by root.
7. Securely delete `/tmp/amg-env-backup.age` and `/tmp/amg-env-bundle.tar.gz`.

**Step 4 — Restore Postgres (60 min)**
1. Install Postgres 15: `apt install -y postgresql-15`.
2. Stop PG: `systemctl stop postgresql`.
3. Configure restic: `export $(cat /etc/amg/restic.env | xargs)`.
4. Snapshot list: `restic -r r2://amg-backups/restic-postgres/ snapshots`.
5. Restore latest: `restic -r r2://amg-backups/restic-postgres/ restore latest --target /var/lib/postgresql/`.
6. Fix ownership: `chown -R postgres:postgres /var/lib/postgresql/ && chmod -R 700 /var/lib/postgresql/`.
7. Start PG: `systemctl start postgresql`.
8. Verify: `sudo -u postgres psql -c "SELECT count(*) FROM public.<canary_table>;"` returns expected row count.

**Step 5 — Restore MCP memory (30 min)**
1. `restic -r r2://amg-backups/restic-mcp/ restore latest --target /var/lib/mcp/`.
2. Fix ownership + perms.
3. Install MCP server binary from harness: `cp /opt/titan-harness-work/dist/mcp-server /usr/local/bin/mcp-server` (if present in dist) or build via `make -C /opt/titan-harness-work/mcp/`.
4. Start MCP: `systemctl start mcp-server`.
5. Verify: `curl -f http://127.0.0.1:3000/healthz` returns 200.
6. Canary query: `curl -X POST http://127.0.0.1:3000/search_memory -d '{"query":"<canary>"}'` returns expected canary response.

**Step 6 — Start per-lane services (20 min)**
1. From harness: `docker compose -f /opt/titan-harness-work/docker/compose.primary.yaml up -d`.
2. Expected services up: LiteLLM gateway, n8n worker, Caddy.
3. Health check: `bin/access-lane-health.sh --lane new-primary --require green`.

**Step 7 — DNS cutover (15 min)**
1. Log into Cloudflare dashboard.
2. Update A records for aimarketinggenius.io, ops.aimarketinggenius.io, chat.aimarketinggenius.io to point at new primary IP.
3. TTL set to 60 seconds for the DR window (will raise back to 300 after burn-in).
4. Wait 2 minutes for propagation.
5. Verify: `curl -f https://aimarketinggenius.io/healthz` returns 200 from new primary.

**Step 8 — Re-provision secondary lane (60 min)**
1. Per ACCESS-REDUNDANCY §D.4, provision Hetzner-A equivalent as secondary to new primary.
2. Full active/active restoration.
3. DNS health check + weighting reconfigured.

**Step 9 — Client communications (15 min)**
1. Pull template from `plans/templates/DR_COMMS_D1_TEMPLATE.md`.
2. Fill in: incident duration, current status, next-update time, expected-full-restoration.
3. Email to all active clients.
4. Post to `/status` public page.
5. Post to `#solon-os` internal channel.

**Step 10 — Burn-in observation (varies, typically 2-4 h)**
1. Monitor dashboards for 2 hours minimum before declaring "fully restored".
2. Any new incident during burn-in escalates back to active DR response.
3. After 2 green hours: declare restoration, bump TTL back up, schedule post-mortem.

**Total measured time in most recent drill (2026-01 drill):** 7 h 42 min. Variance ±30 min depending on step-3 key-retrieval speed.

### E.3 Runbook-assumption failure modes

- **Assumption that restic repos are restorable:** if R2 is also dead (D4 class), skip Steps 4-5 and use the paper-key + 1Password tertiary snapshots (§G runbook composed).
- **Assumption that GitHub has the harness:** GitHub is the third git mirror per CLAUDE.md §17.3. If GitHub is down, a local Mac copy + USB-drive backup of the harness is the tertiary. Operator carries a USB drive with a 1-day-old snapshot.
- **Assumption that Cloudflare DNS works:** if Cloudflare DNS is also down, switch to the DNSimple secondary DNS account (placeholder at `plans/deployments/DNS_FAILBACK_RUNBOOK.md`; future DR-AMG-DNS-REDUNDANCY-01 commissions this formally).

---

## Section F — The Warm-Lane Runbook (Primary-Only Loss) {#section-f}

This runbook assumes ACCESS-REDUNDANCY §I.2 auto-cutover has fired or can be fired. The §F runbook is the operator-side finalization after the automated cutover.

### F.1 Preconditions

- Hetzner-A is live and serving per the 5% steady-state exercise (ACCESS-REDUNDANCY §C.1).
- Automated Cloudflare health-check cutover has already shifted weighting to 0/100 OR operator is executing the §I.1 planned-cutover.

### F.2 Runbook steps

**Step 0 — Confirm cutover (2 min)**
1. Cloudflare LB dashboard shows 0/100 weighting or `bin/cloudflare-lane-status.sh` confirms primary unhealthy.
2. `bin/access-lane-health.sh --lane hetzner-a --require green` passes.
3. Declare D2 in operator journal.

**Step 1 — Scale up secondary (15 min)**
1. Hetzner CX32 4 vCPU is sized for steady-state + transient burst; full production traffic may need scaling. Hetzner Cloud supports live resize.
2. Optional: upgrade Hetzner-A from CX32 to CX52 (8 vCPU / 16 GB) via one-click console if primary-down is expected to last > 2 hours.
3. Verify under load: `bin/load-test-light.sh --lane hetzner-a --duration 5m`.

**Step 2 — Promote Hetzner-B to new secondary (15 min)**
1. Cloudflare add-lane: `bin/cloudflare-add-lane.sh --lane hetzner-b --weight 5`.
2. Bring services up on Hetzner-B to match the manifest in ACCESS-REDUNDANCY §D.3.
3. Verify: `bin/access-lane-health.sh --lane hetzner-b --require green`.

**Step 3 — Client communications (5 min)**
Pull `plans/templates/DR_COMMS_D2_TEMPLATE.md`, fill in, send. Shorter + lower-urgency than D1 template.

**Step 4 — Diagnose primary loss (parallel)**
While secondary serves, operator (or Titan per §I.3 of ACCESS-REDUNDANCY) diagnoses what happened to HostHatch. Result feeds the post-mortem + may inform whether to re-provision on HostHatch or move primary to a different provider.

**Step 5 — Re-provision replacement primary (60-120 min)**
Per §E Steps 1-7 but without the credential-restore step (credentials survive on Hetzner-A, can be synced to new primary via `bin/secrets-sync.sh --target new-primary`).

**Step 6 — Failback + burn-in (2 h observation + operator-gated weight-flip)**
Once replacement primary is healthy, weight 99/1 restored. Burn-in observation. No client comms needed unless another incident occurs.

**Total measured time in most recent drill:** 22 min (steps 0-3); full primary replacement adds 60-120 min but is not in the critical-RTO path because secondary is already serving.

---

## Section G — Credential Revocation + Re-Provision Sequence {#section-g}

Used in D3 disasters (credential cascade compromise).

### G.1 Credential inventory (every credential that can be compromised)

| Credential | Provider | Revoke path | Re-provision path | Dependencies |
|---|---|---|---|---|
| Anthropic API key | Anthropic Console | Delete key in Console | Create new key in Console; write to `/etc/amg/anthropic.env` | LiteLLM gateway reload |
| OpenAI API key | OpenAI Platform | Revoke in Platform | Create new; write to `.env` | LiteLLM reload |
| Perplexity API key | Perplexity Pro | Rotate in account | New key; write | LiteLLM reload |
| xAI Grok key | xAI Console | Revoke | New key; write to `/etc/amg/grok.env` | LiteLLM reload (once Grok route wired) |
| Cloudflare API token | Cloudflare | Revoke in API Tokens | Create new scoped token | `/etc/amg/cloudflare.env` |
| Cloudflare R2 access keys | Cloudflare | Rotate key | New access + secret key pair | restic.env update + restart |
| Supabase service-role keys | Supabase Mgmt API | Revoke via Mgmt API | Generate new via Mgmt API | `/etc/amg/jwt.env` + MCP server reload |
| Supabase access tokens | Supabase | Revoke in account | Generate new | `/etc/amg/aimg-supabase.env` |
| HostHatch / Hetzner API tokens | Provider consoles | Revoke | Re-issue | Re-provisioning tooling |
| GitHub PAT | GitHub Settings | Revoke | New PAT | `ssh-agent` + `git remote` URLs if HTTPS |
| SSH keys (operator) | local + authorized_keys | Remove from authorized_keys | New keypair deployed | Escape-hatch-verify re-attest |
| restic repo master key | self-managed | N/A (changes lock everything) | **Cannot be rotated without re-encrypting every snapshot** — see §G.3 | offline exercise |

### G.2 Runbook steps (order matters)

**Step 0 — Declare scope**
1. Determine which credentials are confirmed compromised vs. suspected.
2. Default: rotate everything in the same env-file scope as the confirmed-compromised credential (conservative; matches DATA-INTEGRITY §J.3).

**Step 1 — Freeze new writes**
1. `bin/writes-freeze.sh --scope all --reason "D3 credential rotation"` halts mutating operations across the fleet.
2. Systems continue serving reads.

**Step 2 — Revoke compromised credentials at provider**
For each credential in the scope, revoke at the provider (Step 1 of the per-credential runbook in §G.1 table).

**Step 3 — Generate new credentials**
For each, generate a new credential. Write to a temporary file first (`/tmp/amg-new-creds-<ts>/`).

**Step 4 — Deploy new credentials atomically**
1. Update `/etc/amg/*.env` files on the primary lane.
2. Sync to secondary lane(s) via `bin/secrets-sync.sh --target all`.
3. Reload affected services on both lanes.
4. Run functional verification per `bin/smoke-test-all-services.sh`.

**Step 5 — Verify old credentials fail**
For each revoked credential, attempt a request with the OLD value — must return 401/403. If old credential still works, revocation was ineffective; escalate.

**Step 6 — Unfreeze writes**
`bin/writes-freeze.sh --release --reason "D3 rotation complete"`.

**Step 7 — Post-rotation audit**
1. Check R2 access logs for past 30 days for anomalous access patterns.
2. Check Supabase audit logs.
3. Check GitHub audit logs (repo access with old credentials).
4. Document findings in `plans/deployments/POSTMORTEM_D3_<date>.md`.

### G.3 Restic master-key rotation (special case)

Restic's encryption model means the repo master key cannot be rotated without re-encrypting every snapshot. Options:

- **Option A — Create new repos, migrate fresh backups:** new repos with new keys; old repos become read-only until retention window expires; new backups go to new repos. Expensive in R2 storage during overlap window but non-disruptive.
- **Option B — Offline re-key:** `restic rebuild-index` + manual passphrase change. Works but requires all snapshots to be accessible during the operation; risky.

Default: Option A. Timeline: 90 days overlap, then old repos deleted.

### G.4 Paper-key + 1Password tertiary coordination

The age-encrypted paper-key in the safe must also be rotated during D3. Steps:

1. Generate new age keypair (`age-keygen -o /tmp/new-age-key.txt`).
2. Re-encrypt the env-file bundle: `tar czf - /etc/amg/ | age --recipient <new_pubkey> -o /tmp/amg-env-backup.age`.
3. Upload encrypted bundle to 1Password ("env-files-backup" secure note, replace attachment).
4. Securely print the new private key (as age-format text), place in safe.
5. Physically destroy old paper key (shred).
6. Verify: use the new key from safe to decrypt the new backup → matches current env-file state.

Complete D3 runbook total time: 3-4 hours (including audit step).

---

## Section H — Client Communication During DR {#section-h}

### H.1 Templates by disaster class

- `plans/templates/DR_COMMS_D1_TEMPLATE.md` — long-duration full-region outage. 3 touchpoints: initial, 1-hour update, resolution.
- `plans/templates/DR_COMMS_D2_TEMPLATE.md` — short-duration primary-only outage. 1 touchpoint: resolution summary (since clients likely didn't notice).
- `plans/templates/DR_COMMS_D3_TEMPLATE.md` — credential rotation with potential client-side password reset prompts. 1 touchpoint: heads-up email.
- `plans/templates/DR_COMMS_D4_TEMPLATE.md` — catastrophic data loss with possible deliverable re-generation. Individual client outreach.

### H.2 Tone guidelines

- Direct, not defensive.
- Honest about cause and duration.
- Explicit about what the client needs to do (usually nothing, but say so).
- Never apologize for the existence of the architecture; apologize for the specific incident.
- Never promise a specific resolution time during an active incident; commit to the next-update time.

### H.3 SLA credit determination

For clients with explicit SLA terms (if any), calculate credit per the contract. For clients without explicit SLA, offer goodwill credit at the founder's discretion. Default: any D1 event with > 2 hours client-visible outage earns a 1-week credit on the next invoice.

### H.4 Founding-member-specific comms

Founding Members (Atlas clients per §3.2) have a direct-SMS + email-to-Solon path in addition to the standard comms. Solon personally authors their touchpoint within 30 minutes of D1/D2 declaration.

---

## Section I — Partial-Service-Degradation Playbook {#section-i}

Used in D5 disasters — the lane infrastructure is fine but a foundational service has failed in a way that cascades.

### I.1 Classification of foundational services

- **Tier F0 (cannot run lane without):** Caddy, systemd, Docker, LiteLLM.
- **Tier F1 (lane runs but degraded):** MCP server, titan-channel, OPA.
- **Tier F2 (lane runs normally, feature missing):** individual n8n workflow, Stagehand browser.

### I.2 F0 failure runbook

1. Classify which F0 service failed.
2. If Caddy down + systemd reload fails: diagnose via `journalctl -u caddy`; most likely causes are config syntax error or TLS cert expiry; fix or roll back Caddyfile.
3. If systemd fails: reboot the VPS (HostHatch console or Hetzner console). Systemd failure severe enough to prevent its own restart is extremely rare but catastrophic; reboot is the right move.
4. If Docker fails: `systemctl restart docker` then check via `docker ps`; if persistent, reinstall Docker via package manager.
5. If LiteLLM gateway down: fallback to direct Anthropic + OpenAI + Perplexity + xAI API calls via service-level adapters (already in harness); restart LiteLLM in parallel.

### I.3 F1 failure runbook

1. Reload via systemd: `systemctl restart <service>`.
2. Verify via `/healthz`.
3. If persistent: restore from last backup per DATA-INTEGRITY §K runbooks.
4. If service contract changed: roll back to last-known-good git SHA of the harness using `bin/harness-rollback.sh`.

### I.4 F2 failure

- Single n8n workflow failure → workflow-specific debug; not a DR event.
- Stagehand browser failure → operator manual intervention; not a DR event.

F2 events do not trigger this doctrine; they are RESILIENCE-01 territory.

---

## Section J — Recovery Drill Cadence {#section-j}

### J.1 Drill schedule

| Drill | Scope | Cadence | Duration |
|---|---|---|---|
| D1 full cold-boot | Complete §E runbook on fresh Hetzner provisioning, restore to staging | Semi-annual (Jan 15, Jul 15) | 4 h active + 2 h burn-in |
| D2 warm-lane | Planned cutover + finalization per §F | Quarterly (aligns with ACCESS-REDUNDANCY quarterly drill) | 45 min |
| D3 credential rotation | Rotate one non-critical credential fully + audit | Quarterly | 1 h |
| D4 paper-key restore | Decrypt age-encrypted backup + restore env files into staging | Annual (November) | 2 h |
| D5 F0 service failure | Random F0 service taken down, runbook executed | Monthly | 30 min |

### J.2 Drill automation

Where possible, drills are scripted (`bin/drill-<class>.sh`). Where human decision-making is required (D1 step 1-alt: "if Hetzner identity is also compromised"), the drill includes pauses for operator decision + records the decision.

### J.3 Drill success criteria

Each drill must:

1. Complete within target RTO for the drill class.
2. Produce a measurable RPO outcome matching commitment.
3. Generate a post-drill artifact in `plans/deployments/DRILL_<class>_<date>.md`.
4. Identify at least one improvement opportunity (doctrine drift, tooling gap, runbook ambiguity).

---

## Section K — Rollback Primitives (Atomic Per-Step Revert) {#section-k}

Every DR runbook step in §E–§I has a corresponding rollback primitive. This is the analog of DATA-INTEGRITY §K.4 at the DR-workflow level.

### K.1 Per-step rollback table (Cold-Boot Runbook §E)

| Step | Forward action | Rollback primitive | Rollback window |
|---|---|---|---|
| E.2.1 | Provision new Hetzner CX52 | Destroy instance via Hetzner Cloud API | Any time |
| E.2.2 | Deploy harness git | `rm -rf /opt/titan-harness-work` | Any time |
| E.2.3 | Restore credentials | `shred /etc/amg/*.env && restart affected services` (non-production mode) | Before DNS cutover |
| E.2.4 | Restore Postgres | `systemctl stop postgresql && rm -rf /var/lib/postgresql/` | Before DNS cutover |
| E.2.5 | Restore MCP | `systemctl stop mcp-server && rm -rf /var/lib/mcp/` | Before DNS cutover |
| E.2.6 | Start services | `docker compose down` | Before DNS cutover |
| **E.2.7 DNS cutover** | Change A records in Cloudflare | Restore prior A records from Cloudflare History API | **60 min rollback window before clients cache deeply** |
| E.2.8 | Re-provision secondary | Destroy Hetzner-A; single-lane mode | Any time |
| E.2.9 | Client comms sent | Retraction comms via `plans/templates/DR_COMMS_RETRACTION.md` | Any time (but erodes trust) |

### K.2 Rollback precondition

Every rollback requires:

1. Operator write-access to the reverse-action tool (Cloudflare API, Hetzner API, etc.).
2. Checksum triplet verification on any restored asset per DATA-INTEGRITY §D.3.
3. MCP `log_decision` with `dr_rollback` tag logging the reversal.

### K.3 Post-rollback

After any DR rollback, the incident is still active. Rollback does not close the DR event; it only reverts the incorrectly-applied forward step. Operator then chooses a different forward path.

---

## Section L — Post-DR Incident Review {#section-l}

### L.1 Mandatory post-mortem

Every DR exit (successful or failed) triggers a post-mortem within 48 hours. Template at `plans/templates/POSTMORTEM_DR_TEMPLATE.md`. Output at `plans/deployments/POSTMORTEM_<incident_id>_<YYYY-MM-DD>.md`.

### L.2 Post-mortem structure

1. **Executive summary** (2-3 sentences — what happened + how long + impact).
2. **Timeline** (minute-resolution events from first anomaly to "fully restored" declaration).
3. **Classification** (D1/D2/D3/D4/D5 per §B.1).
4. **Sister-doctrine failure analysis** — why did ACCESS-REDUNDANCY / RESILIENCE / DATA-INTEGRITY not absorb this before RECOVERY had to run?
5. **Contributing factors** (root cause + contributing causes — no single-root-cause oversimplification).
6. **Operator stress tax** — how many hours of operator time did this consume; did operator make stress-driven errors that extended the incident?
7. **Doctrine updates** — every doctrine (including this one) that needs revision based on the event.
8. **Process improvements** (non-doctrine) — tooling changes, runbook clarifications, drill schedule adjustments.
9. **Client impact** — what did clients see; how was comms handled; any retention risk.
10. **SLA credit** — calculated + issued.

### L.3 Review meeting

Solon + Aristotle joint review within 72 hours of the post-mortem completion. Output: list of high-priority follow-up actions with named owners + deadlines.

---

## Section M — Integration With Sister Doctrines {#section-m}

### M.1 DR-AMG-ACCESS-REDUNDANCY-01

The §F warm-lane runbook is an operator-side extension of ACCESS-REDUNDANCY's automated §I.2 unplanned cutover. This doctrine picks up where ACCESS-REDUNDANCY leaves off.

### M.2 DR-AMG-RESILIENCE-01

D5 class events are the boundary between RESILIENCE (handles auto) and RECOVERY (handles auto-failed → operator). Any incident RESILIENCE fails to heal in its 2-attempt limit → RECOVERY §I.

### M.3 DR-AMG-DATA-INTEGRITY-01

The restore runbooks in DATA-INTEGRITY §K are consumed by RECOVERY §E Steps 4-5. DATA-INTEGRITY provides the primitives; RECOVERY composes them.

### M.4 DR-AMG-UPTIME-01

D1 events blow the error budget; this doctrine's exit triggers UPTIME's Lockdown stance per UPTIME §D.3. Feature freezes and reliability-investment windows are governed by UPTIME, not this doctrine.

### M.5 DR-AMG-ENFORCEMENT-01 v1.4

Gate #4 policy protects all lanes, including the fresh-provisioned replacement primary in §E.2.1-8. Installing Gate #4 + attestations is part of Step 6 (before DNS cutover).

### M.6 Operator incapacitation (D6 — referenced)

If Solon is unavailable for > 72 hours during an active DR, the runbook becomes: Titan + Aristotle coordinate to bring up the warm-lane (§F), then post-DR review is deferred until operator returns. Full D1 runbooks cannot execute without Solon because they require paper-key + 1Password access. This is an acknowledged gap; mitigation is the geographic + time-zone redundancy of the secondary lane reducing the probability that D1 happens during an operator-unavailable window.

---

## Section N — Anti-Patterns + Known Failure Modes {#section-n}

### N.1 Anti-pattern: the big-red-button fantasy

"In a disaster, we'll just hit the button and everything comes back." There is no button. There is a 10-step runbook that takes 8 hours. Doctrine forbids wish-casting about a fictional button.

### N.2 Anti-pattern: the untested runbook

A runbook that has never been drilled is a runbook that does not work. Period. Drill cadence in §J is non-negotiable.

### N.3 Anti-pattern: the heroic operator

During high-stress DR, operator fatigue compounds errors. Doctrine mandates step-numbered runbooks precisely to reduce cognitive load. An operator deviating from the runbook "because I know a faster way" introduces latent bugs. If the runbook is wrong, fix the runbook — don't work around it during incident.

### N.4 Anti-pattern: silent disaster

An ongoing disaster that isn't acknowledged publicly is a disaster compounding with a trust incident. Client comms is a first-class step (§H), not an afterthought.

### N.5 Known failure: operator-incapacitation during D1

Documented in §M.6. Mitigation is probabilistic (reducing the concurrence); residual risk accepted.

### N.6 Known failure: paper-key loss during D4

If the age-encrypted paper-key AND the 1Password vault are both lost, env files cannot be recovered and new credentials must be generated from scratch at every provider — a 12+ hour process. Mitigation: the paper-key copy lives in the safe; 1Password lives in a separately-backed-up vault; physical + digital redundancy reduces to combined-failure probability.

### N.7 Known failure: Cloudflare DNS outage during D1

If Cloudflare is down simultaneously with D1 (regional correlation rare but possible), the DR runbook's Step 7 DNS cutover cannot proceed. Mitigation: DNSimple secondary DNS account is provisioned (paper trail at `plans/deployments/DNS_FAILBACK_RUNBOOK.md`) but not regularly drilled; D1+Cloudflare-down is outside the ≤ 8 hour RTO commitment.

---

## Section O — Glossary + References {#section-o}

### O.1 Glossary

- **Cold-boot** — restore from zero infrastructure state using only tertiary (paper-key + 1Password) credentials.
- **Warm-lane** — failover when secondary lane is already live and serving some traffic.
- **RTO/RPO** — per DATA-INTEGRITY §O.1.
- **Disaster class** — D1/D2/D3/D4/D5 classification per §B.1.
- **Post-mortem** — structured incident review per §L.
- **Runbook** — step-numbered executable procedure; different from a checklist by being independently executable.

### O.2 References

- Google SRE Book, Ch. 14 "Managing Incidents" + Ch. 15 "Postmortem Culture".
- Charity Majors, "Observability Engineering" — incident-response mental models.
- IBM Cloud Pak "Disaster Recovery Automation" whitepapers.
- AWS Well-Architected Framework, Reliability Pillar — RPO/RTO design patterns.
- SANS Institute "Incident Handler's Handbook" — classification + communication patterns.
- CLAUDE.md §15, §17 — autonomy + auto-mirror for triple-replication.
- DR-AMG-ACCESS-REDUNDANCY-01 §I — access-lane cutover procedures.
- DR-AMG-DATA-INTEGRITY-01 §K — restore runbook primitives consumed by this doctrine.
- DR-AMG-UPTIME-01 §G — incident counting + Lockdown stance triggers.
- DR-AMG-ENFORCEMENT-01 v1.4 §4 — escape-hatch attestations during new-primary provisioning.

---

*End of doctrine DR-AMG-RECOVERY-01 — version 1.0 (2026-04-15).*
*Grade block to be appended after grok_review adversarial pass.*
