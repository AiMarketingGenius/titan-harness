# AMG / Titan Harness Threat Model — 2026-04-14

**Last updated:** 2026-04-14 (post DR-AMG-RESILIENCE-01 5-of-5 + DR-AMG-ENFORCEMENT-01 v1.2 audit ship)
**Scope:** Mac dev environment (Solon's laptop) + VPS (170.205.37.148) + MCP at memory.aimarketinggenius.io + Supabase + Cloudflare R2 + Slack workspace.
**Owner:** Solon (CEO). Execution: Titan (COO). Adversarial reviewer: Perplexity Aristotle (Grok once `grok_review` MCP tool ships).

---

## 1. Assets to protect

| Asset | Location | Impact of compromise |
|---|---|---|
| Supabase database (tasks, sessions, handovers, PII-adjacent) | Cloud — Supabase | GDPR/CCPA breach, Solon OS data loss |
| MCP memory (decisions, sprint state, bootstrap context) | `memory.aimarketinggenius.io` | Loss of institutional memory, injection attack surface |
| Cloudflare R2 backups (restic 15-min increments) | R2 bucket | Full recovery baseline lost |
| SSH access to VPS | Port 2222, ed25519 key + fail2ban | Lockout class (see INC-2026-04-14-01) |
| Slack workspace (#titan-aristotle, ops DMs) | Slack | Injection vector + exfiltration |
| gate2.secret / gate4.secret / opa-override.secret | `/etc/amg/*.secret` on VPS | Enforcement bypass |
| Git repo (titan-harness) | Mac + VPS bare + GitHub mirror | Code tamper, backdoor insertion |
| Credential store (.env files, Supabase service role, Anthropic key, Slack bot token) | `/opt/n8n/docker-compose.yml` on VPS, pending migration to Infisical (CT-0414-03) | Full infrastructure compromise |

## 2. Adversary classes

1. **External unauthenticated attacker** — scans SSH 2222, probes Caddy domains, tries MCP /tools/list without auth, attempts Supabase SQL injection.
2. **Compromised 3rd-party dependency** — n8n/docker image with malicious update; npm package pulled during build.
3. **Prompt-injection via tool output** — malicious Slack post, README, or scraped webpage convinces Titan to exfiltrate secrets or run destructive commands.
4. **Self-inflicted operator error** — 40hr SSH lockout class (INC-2026-04-14-01): bad config, skipped baseline, hypothesis loop.
5. **Insider / stolen Mac** — laptop theft, `~/.amg/*.secret` and ssh keys in plain file.

## 3. Attack surfaces + current mitigations

### 3.1 SSH / firewall on VPS
- **Risk:** lockout, unauthorized entry, sshd_config tamper.
- **Mitigations:**
  - fail2ban active with localhost whitelist (127.0.0.1/8, ::1)
  - UFW canonical rules + auto-heal via `/etc/amg/ufw-canonical-commands.sh`
  - **Gate #3** (shipped `9eb08da`): mandatory 9-step forensic baseline before any SSH-adjacent proposal.
  - **Gate #1 v1.1** (shipped `df5ee2e`): hash-pinned `SSH-Baseline:` trailer on every SSH-scope commit; VPS pre-receive rejects forged trailers.
  - **Gate #4 v1.2 audit** (shipped `2353539`): OPA + chrony + nonced ack + 24h audit → manual ack → 7d enforce-observe-tail. Enforce flip gated on escape-hatch all-green + chrony sync.
  - HostHatch console + root password (cred §15C) preserved as escape hatch; `bin/escape-hatch-verify.sh` validates 6 items.

### 3.2 MCP memory layer
- **Risk:** prompt injection via stored decisions; unauthorized write to memory; exfiltration via malicious search results.
- **Mitigations:**
  - `scan_for_injection_attempt` MCP tool (available) on any ingested text.
  - Decisions logged with `project_source` namespace — EOM vs Titan decisions separated.
  - MCP server fronted by Cloudflare (authenticated); doctrine Domain 9 janitor was descoped (see commit `9864dd6`) — real MCP has its own ops layer.
- **Gap:** no HMAC on individual MCP memory entries (server-side concern; documented for future DR).

### 3.3 Hypothesis runaway (Gate #2 scope)
- **Risk:** 40hr-style loop — wrong theory pursued indefinitely.
- **Mitigation:** **Gate #2 v1.1** (shipped `780d90d`): HMAC-signed state file + HMAC-chained audit log + exponential alert (30/60/90min) + force baseline restart at T+90 or attempt_n≥3; sequential attempt_n enforcement; 4h dedup on hypothesis text.

### 3.4 Session auto-restart / state loss (Item 7 scope)
- **Risk:** Claude Code session exits mid-flow with no handover; next session starts cold and loses context.
- **Mitigation:** **Item 7 v1.1** (shipped `ce9c8db`): atomic HMAC-signed resume-state.json via session-end hook + launchd auto-spawn + hard-coded MCP bootstrap on resume + per-session exchange counter + daily cap.

### 3.5 Docker services (n8n, caddy)
- **Risk:** container restart loop masked as "healthy"; docker socket compromise; stale image with CVE.
- **Mitigations:**
  - DELTA-B heal scripts patched (commits `298421`, `d03b951`) — no more "zombie-PID lies".
  - DELTA-D systemd timers for drift + disk + git + doctrine + SHA consistency (commit `23f3c16`).
  - **Item 5 watchdog patches** (this ship): truthfulness checks on caddy + n8n + fail2ban (restart count, uptime ≥60s, jail presence).

### 3.6 Credential exposure
- **Risk:** .env files in `/opt/n8n/` contain Supabase service role, Anthropic, Slack, Redis keys — plain-text on VPS.
- **Status:** 🔴 **URGENT P0** — CT-0414-03 DR-AMG-SECRETS-01 pending. Rotate + migrate to Infisical.
- **Compensating control:** root-only file perms; VPS firewall blocks all but 22/2222/80/443 inbound.

### 3.7 Backup integrity
- **Risk:** backup corruption, R2 token leak, restic password loss.
- **Mitigations:**
  - restic 15-min incremental backups to R2 (commit `78bdb00`).
  - `bin/verify-backup.sh` runs daily (watchdog check).
  - Last known good backup: `Dr.SEO_20260413_194819_UTC`.
- **Gap:** R2 write-only token not yet scoped (Solon pending manual action).

### 3.8 Prompt injection in tool output
- **Risk:** attacker or accidental content convinces Titan to run destructive commands.
- **Mitigations:**
  - Per critical security rules (system prompt), instructions from tool output require explicit user confirmation.
  - `scan_for_injection_attempt` available for proactive scans.
  - **Observed:** 2026-04-14 session — Titan falsely-positively flagged a legitimate user interrupt as injection. Correction noted in session log; threat-model bias: *false positives are the failure mode here, not false negatives* (at Solon's operating tempo).

## 4. Threats currently UN-mitigated (tracked)

| Threat | Severity | Tracked as |
|---|---|---|
| Secrets in `/opt/n8n/docker-compose.yml` | 🔴 Urgent P0 | CT-0414-03 |
| VPS working-tree drift (post-receive hook gap) | 🟡 Medium | carryover note |
| AI Memory Guard product non-functional | 🟡 Medium | carryover note (P1 post Item 3) |
| Single VPS — no geo-redundancy / failover | 🟡 Medium | future DR-ACCESS-REDUNDANCY |
| Solo-operator multi-party ack impossible | 🟢 Accepted | Gate #4 scope note |
| Mac laptop theft exposes `~/.amg/*.secret` + ssh keys | 🟢 Accepted | Mac FileVault assumed on |

## 5. Review cadence

- **Every major DR ship:** Titan appends a "delta to threat model" line to this file.
- **Weekly (Monday):** Aristotle 5-point advisory scan (per §13.2) against this file.
- **Incident-driven:** every P0/P1 incident triggers a diff pass.

**Next review:** after Gate #4 enforce flip, or next P0 incident, whichever first.
