# AMG Threat Model — DR-AMG-SECURITY-01 (Enhanced)

## Architecture
- Single HostHatch VPS (Ubuntu 22.04, 48GB RAM, 8 cores)
- Docker: Caddy (reverse proxy), n8n (workflow automation)
- PM2: MCP server (memory.aimarketinggenius.io)
- Supabase: PostgreSQL + Auth + RLS
- Cloudflare: DNS, WAF, R2 storage, Workers

## Threat Actors
1. **Opportunistic scanners** — automated bots probing exposed ports/endpoints
2. **Targeted attackers** — competitors or actors targeting AI platform IP
3. **Supply chain** — compromised npm/pip packages in dependencies
4. **Insider (agent)** — Titan autonomous agent acting beyond boundaries
5. **AI-specific** — prompt injection via MCP memory poisoning

## STRIDE Analysis

| STRIDE Category | Applicable Threats | Mitigations | Residual |
|----------------|-------------------|-------------|----------|
| **Spoofing** | Forged JWT tokens, SSH key theft, impersonated API calls | JWT auth on MCP, SSH key-only auth, fail2ban, Caddy basic_auth on operator/browser domains | Stolen JWT valid until expiry (8h for n8n, no revocation list) |
| **Tampering** | Modified audit logs, altered backup manifests, MCP memory poisoning, Caddyfile injection | Hash chain on governance_audit (append-only, no-update RLS), SHA-256 backup manifests, watchdog self-integrity hash, MCP input sanitization | Tamper at DB level if service_role key leaked |
| **Repudiation** | Agent claims action not taken, operator denies approval | governance_audit immutable log, MCP decision log, security-events.jsonl, Wazuh FIM | No cryptographic non-repudiation (no signing) |
| **Information Disclosure** | Credential leak via env files, PII exposure via Supabase RLS bypass, MCP memory exfiltration | /etc/amg 0700, gitleaks pre-commit+weekly, RLS daily audit, Suricata IDS egress rules, titan-agent iptables | PM2 env dump exposes secrets in memory |
| **Denial of Service** | DDoS on public endpoints, resource exhaustion by watchdog/crons, n8n workflow loops | Caddy rate limits (xcaddy module), CF WAF, fail2ban, watchdog MemoryMax/CPUQuota, n8n execution timeout | Volumetric L3/L4 attacks bypass Caddy (need CF proxy) |
| **Elevation of Privilege** | titan-agent escaping isolation, security-watchdog sudoers abuse, Docker container escape | titan-agent no sudo + iptables egress + /etc/amg 0700, security-watchdog limited sudoers (specific commands only), AppArmor profile, seccomp | Docker socket access = root equivalent |

## OWASP LLM Top 10 (2025) Coverage

| # | OWASP LLM Risk | AMG Exposure | Mitigation | Gap |
|---|---------------|-------------|------------|-----|
| LLM01 | Prompt Injection | Titan agent processes external input | Pre-action gate (3-layer: denylist, rule engine, reserved LLM), shell wrapper | No input classifier fine-tuned yet |
| LLM02 | Insecure Output Handling | LLM outputs executed as commands | titan-bash-wrapper.sh, git pre-push gate | Wrapper bypass via direct syscall (seccomp mitigates) |
| LLM03 | Training Data Poisoning | MCP memory stores agent context | MCP input sanitization (credential-pattern regex), memory integrity check | Semantic poisoning not detected by regex |
| LLM04 | Model Denial of Service | API rate limits on LLM providers | LiteLLM gateway rpm/tpm limits, capacity.py hard blocks | Provider-side rate limit changes not monitored |
| LLM05 | Supply Chain Vulnerabilities | npm/pip dependencies | gitleaks pre-commit, weekly TruffleHog, Trivy container scan | Zero-day window between scans |
| LLM06 | Sensitive Information Disclosure | Agent may leak secrets in outputs | Credential-pattern regex on MCP writes, /etc/amg isolation | Agent could encode secrets to bypass regex |
| LLM07 | Insecure Plugin Design | n8n Code nodes, MCP tools | n8n Code node audit, MCP JWT per-caller rate limits | Code nodes not sandboxed |
| LLM08 | Excessive Agency | Titan autonomous actions | Hard-stop taxonomy (10 triggers), operator gates, governance audit | Pre-action gate has false-negative risk |
| LLM09 | Overreliance | Operator trusts agent reports | Auditor cross-check (CF Worker), held-out reviewer examples, red team | Auditor checks lag real-time |
| LLM10 | Model Theft | Proprietary prompts in MCP memory | MCP JWT auth, memory integrity hashing | Memory accessible to authenticated callers |

## Attack Surface (ranked by risk)
| # | Vector | Likelihood | Impact | STRIDE | Mitigation | Residual Risk |
|---|--------|-----------|--------|--------|------------|---------------|
| 1 | Titan agent prompt injection | High | Critical | E,T | Pre-action gate, shell wrapper, seccomp, AppArmor | Gate logic bypass |
| 2 | MCP memory poisoning | Medium | High | T,I | JWT auth, input sanitization, integrity hashing | Semantic poisoning |
| 3 | Supabase RLS misconfiguration | Medium | Critical | I | Daily RLS audit via watchdog, 33 tables flagged | New tables ship without RLS |
| 4 | Credential theft via exposed env | Low | Critical | I,S | /etc/amg 0700, gitleaks, secret scanning | PM2 env dump |
| 5 | Supply chain CVE | Medium | High | T | Weekly gitleaks/TruffleHog, Trivy, pre-commit | Zero-day window |
| 6 | DDoS on public endpoints | Medium | Medium | D | Caddy rate limits, CF WAF, fail2ban | L3/L4 volumetric |
| 7 | SSH brute force | Low | Critical | S,E | Port 2222, key-only, fail2ban, Wazuh FIM | Key compromise |
| 8 | n8n workflow injection | Low | High | T,E | Code node audit, encryption key, Caddy proxy | Webhook input |
| 9 | Data exfiltration via egress | Low | Critical | I | Suricata IDS, titan-agent iptables | IDS mode only |
| 10 | Backup integrity | Low | High | T | SHA-256 manifests, R2 upload, verify cron | Object Lock pending |

## Kill Chain Defenses (by MITRE ATT&CK phase)
- **Reconnaissance** (TA0043): Caddy rate limits, CF WAF scanner UA block
- **Initial Access** (TA0001): SSH hardening, fail2ban, MCP JWT auth
- **Execution** (TA0002): Pre-action gate, titan-bash-wrapper, seccomp
- **Persistence** (TA0003): Wazuh FIM (realtime on /etc/ssh, /etc/amg), SSH key monitoring
- **Privilege Escalation** (TA0004): titan-agent no sudo, /etc/amg 0700, AppArmor
- **Defense Evasion** (TA0005): Hash chain, self-integrity check, auditor CF Worker
- **Credential Access** (TA0006): Secrets in env files, gitleaks scanning, credential rotation
- **Discovery** (TA0007): Listening port monitoring vs canonical
- **Lateral Movement** (TA0008): Single VPS, no internal network (mitigated by architecture)
- **Collection** (TA0009): Supabase RLS, MCP input sanitization
- **Exfiltration** (TA0010): Suricata IDS, titan-agent egress rules
- **Impact** (TA0040): R2 backups, restore drills, GDPR/CCPA notification workflow

## Operator Gate Justification
1. **R2 Object Lock Compliance Mode**: Cloudflare R2 Compliance mode is irreversible — once enabled, CANNOT be disabled by anyone including root, account owner, or Cloudflare support. Retention periods are permanent. This is architecturally different from AWS S3 Governance mode which allows admin overrides. CT-0413-04, deadline 2026-05-13.
2. **n8n Encryption Key Rotation**: Changes the AES key that encrypts all stored credentials at rest in n8n's SQLite database. Invalidates ALL ~20 stored credentials immediately. OAuth tokens require browser-based re-authorization flows (not API-scriptable). This cannot be automated via Ansible or any CLI tool because OAuth2 authorization code flow requires human interaction in a browser. CT-0413-05, deadline 2026-05-13.
3. **HA Architecture**: Requires purchasing additional infrastructure ($4-10/mo). Budget allocation is a business decision. CT-0413-06, deadline 2026-05-13.

## Dismissed Audit Flags (documented for future auditors)
- **"fail2ban exponential backoff is standard"**: DISMISSED. While fail2ban supports `bantime.increment`, the specific formula (`ban.Time * math.exp(float(ban.Count+1)*banFactor)/math.exp(1*banFactor)`), maxtime=24h, and per-jail overrides (SSH maxretry=3/1h vs default) are custom configuration, not defaults.
- **"Pre-commit hooks redundant with weekly scan"**: DISMISSED. Pre-commit hooks catch secrets at commit-time (prevention). Weekly TruffleHog scans catch secrets in git history (detection). These are complementary defense layers, not redundant.
- **"R2 Object Lock overridable"**: DISMISSED. Grok confused Cloudflare R2 Compliance mode with AWS S3 Governance mode. R2 Compliance mode has no admin override.
- **"n8n credentials automatable via Ansible"**: DISMISSED. OAuth2 authorization code flow requires browser-based human interaction. API keys could theoretically be re-entered via n8n API, but OAuth tokens (Slack, Google, etc.) cannot.

Last updated: 2026-04-13
