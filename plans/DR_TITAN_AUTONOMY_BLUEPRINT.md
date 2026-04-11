# Titan 99.99% Autonomy Blueprint
## Production-Grade Architecture for Mac + VPS + Cloud/SaaS Orchestration

**Prepared for:** Solon / AI Marketing Genius (AMG) — Titan / Solon OS stack
**Scope:** Mac (local orchestration surface) + HostHatch VPS (Ubuntu, 12-core, 64GB) + GitHub + Supabase + cloud/SaaS stack
**Classification:** Doctrine file — feed directly into CORE_CONTRACT and routing rules
**Ingested:** 2026-04-12 per Solon autonomy directive (this file is the canonical verbatim source of truth)
**Annotations + conflict analysis + implementation plans live at:** `plans/PLAN_2026-04-12_autonomy-phase{1..5}-*.md`

---

## Executive Summary

Achieving 99.99% autonomous operation requires solving four distinct problem classes simultaneously: **identity continuity** (secrets never expire unexpectedly), **auth surface reduction** (fewer human touchpoints per cycle), **anti-bot bypass** (real browsers handle Cloudflare for Titan), and **operational safety** (audit trails + rollback keep broad access from causing catastrophic drift). This blueprint gives Titan concrete, opinionated defaults across all eight research areas, with every recommendation tagged `[PROVEN]`, `[RECOMMENDED]`, or `[EXPERIMENTAL]`. The key architectural principle throughout: **Titan decides; real browsers and dedicated runners execute**.

---

## 1. Secrets & Identity Model

### Core Architecture Decision

**Do not use a single secrets layer.** Use a two-tier model:

- **Tier 1 — Runtime secrets (VPS):** Infisical self-hosted (Community Edition) or Doppler, injecting into every process at startup. This is the system of record for all API keys, OAuth tokens, database credentials.
- **Tier 2 — Mac-side secrets (bootstrap):** macOS Keychain stores only the master credentials needed to bootstrap Tier 1 (Infisical/Doppler token, SSH key passphrases, grab-cookies.py triggers). Nothing sensitive lives in `.env` files committed to repos.

### Secrets Store Comparison

| Criterion | Infisical (Self-Hosted) | Doppler (Cloud) | HashiCorp Vault |
|---|---|---|---|
| Hosting | VPS-native | SaaS only | VPS-native |
| Auto-rotation | Yes (DB, some APIs) | Yes (fully managed) | Yes (dynamic secrets) |
| CLI injection | `infisical run -- <cmd>` | `doppler run -- <cmd>` | `vault agent inject` |
| SDK languages | Node, Python, Go, .NET | REST only (no SDK) | Node, Python, Go, Ruby |
| Complexity | Medium | Low | High |
| Cost | Free (self-hosted) | Free tier + paid | Free (OSS) |
| Best for Titan | ✅ Self-hosted on VPS, full control | Fast start, less ops overhead | Overkill unless dynamic DB creds needed |

**Opinionated default:** [RECOMMENDED] **Infisical self-hosted on the HostHatch VPS.** It runs as a Docker container, uses PostgreSQL as a backend (you already have Supabase available), supports automatic rotation for database credentials, and its Python + Node SDKs match Titan's stack. Doppler is the right answer if you want zero ops overhead but introduces cloud dependency.

### macOS Keychain Pattern for Titan

Store secrets in Keychain using the `security` CLI — never in shell history:

```bash
# Add a secret (prompts interactively — no shell history exposure)
security add-generic-password -a "$USER" -s "infisical-token" -w

# Read in scripts (pipe directly, never echo)
INFISICAL_TOKEN=$(security find-generic-password -a "$USER" -s "infisical-token" -w 2>/dev/null)
export INFISICAL_TOKEN
```

Key rule: [PROVEN] **The Mac Keychain stores only bootstrap credentials** — the Infisical service token, SSH key passphrases, and the TOTP seed for services that require hardware-backed 2FA. Everything downstream flows from Infisical at runtime.

### Secrets Lifecycle — Token Lifetimes

| Credential Type | Recommended Lifespan | Rotation Method |
|---|---|---|
| GitHub Fine-Grained PAT | 90 days | Infisical auto-notify + manual rotate |
| SSH keys (VPS access) | 180 days | Rotate + delete old, update Keychain |
| Supabase Service Role Key | 90 days | Manual via dashboard + Infisical update |
| OAuth refresh tokens | Until revoked (store & reuse) | Re-auth only if revoked by provider |
| Browser session cookies | 7–30 days (varies by service) | grab-cookies.py weekly ritual |
| API keys (ElevenLabs, Deepgram) | Per platform (typically 1 year+) | Infisical calendar reminder at 90 days |
| Database passwords | 30–90 days | Infisical auto-rotation |

[PROVEN] **Rotate API keys every 90 days maximum**, even if providers allow indefinite validity. Static credentials are silent technical debt that become catastrophic when leaked.

---

## 2. 2FA & Auth Refresh Strategy

### The Weekly Auth Ritual Pattern

The goal is to compress all human authentication moments into a single 15–30 minute weekly session, batching every token and cookie refresh into one ceremony. Structure this as a **Friday-afternoon ritual script** (or whichever day before the weekend night-grind).

**Titan's `auth-ritual.sh` — conceptual structure:**

```bash
#!/bin/bash
# Run weekly (Friday 5pm) before overnight harvests
# All prompts happen in one session — no drip interruptions

echo "=== TITAN AUTH RITUAL ==="

# 1. Refresh browser cookies for Cloudflare-protected services
python3 /opt/titan-harness/grab-cookies.py --services all --output /opt/titan-harness-secrets/cookies/

# 2. Refresh OAuth tokens that are near expiry
python3 /opt/titan-harness/oauth-refresh.py --check-expiry --warn-days 7

# 3. Rotate any API keys flagged as expiring within 14 days
infisical secrets get --token "$INFISICAL_TOKEN" | python3 /opt/titan-harness/rotation-check.py

# 4. TOTP-dependent logins (where required)
# Script uses pyotp + stored TOTP secrets in Keychain
python3 /opt/titan-harness/totp-refresh.py

echo "=== RITUAL COMPLETE. Titan cleared for weekend autonomy. ==="
```

### TOTP Automation Pattern

[PROVEN] For services using TOTP 2FA (Google Authenticator-style), you can automate code generation without human involvement by storing the TOTP seed:

```python
import pyotp
import keyring  # reads from macOS Keychain

# At 2FA setup time, store the base32 seed in Keychain:
# security add-generic-password -a "titan" -s "totp-hubspot" -w

def get_totp_code(service_name: str) -> str:
    seed = keyring.get_password(f"totp-{service_name}", "titan")
    totp = pyotp.TOTP(seed)
    return totp.now()

# Usage: get_totp_code("hubspot") → "492039"
```

This works for any TOTP-based service. The seed is stored once (during your initial 2FA setup), and Titan generates codes autonomously forever after. This eliminates 2FA friction for most services.

### Per-Service Auth Guide

| Service | Auth Method | Recommended Token | Lifespan | Human Touch Required? |
|---|---|---|---|---|
| **Gmail** | OAuth 2.0 | Refresh token (offline_access) | Until revoked | Once at setup |
| **GitHub** | Fine-Grained PAT | 90-day PAT with minimal scopes | 90 days | Rotate quarterly |
| **Supabase** | Service Role Key | API key (server-side only) | 90 days | Rotate quarterly |
| **Claude.ai** | Browser cookie | Session cookie via grab-cookies.py | 7–14 days | Weekly ritual |
| **Perplexity.ai** | Browser cookie | Session cookie via grab-cookies.py | 7–14 days | Weekly ritual |
| **HubSpot** | OAuth 2.0 + TOTP | Refresh token + TOTP seed | Refresh: until revoked | TOTP: never (automated) |
| **Stripe** | API Key | Restricted key (read/write scopes) | 90 days | Rotate quarterly |
| **ElevenLabs** | API Key | Per-service scoped key | Platform default | Annual or on breach |
| **Deepgram** | API Key | Per-service key | Platform default | Annual or on breach |
| **Loom** | OAuth 2.0 or cookie | Session cookie | 30 days | Monthly ritual |
| **GitHub Actions** | GitHub App | Installation token (1-hr, auto-refresh) | 1 hour (auto) | Setup only |
| **Slack** | OAuth 2.0 | Bot token (non-expiring) | Until revoked | Setup only |

**Key insight:** [PROVEN] **Prefer API keys over cookies** for services that offer them. API keys are stable, deterministic, and not subject to Cloudflare challenges. Cookies are a last resort for consumer-facing SaaS platforms (Claude.ai, Perplexity.ai, Loom) that lack programmatic access APIs.

### Gmail OAuth Automation

Google ended "less secure app" passwords in March 2025. The correct pattern for Titan's Gmail harvesting:

```python
# One-time setup: run interactively to get refresh token
# Store refresh_token in Infisical as GMAIL_REFRESH_TOKEN

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import json, os

def get_gmail_access_token():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        client_id=os.environ["GMAIL_CLIENT_ID"],
        client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"]
    )
    creds.refresh(Request())
    return creds.token  # fresh access token, auto-refreshed
```

Once the refresh token is stored, Titan never needs human input to access Gmail again — until Google revokes the token (rare, typically on suspicious activity or explicit revocation).

---

## 3. Anti-Bot & Cloudflare Bypass

### The Core Problem (and Its Solution)

Raw Python `requests` and `curl` fail against Cloudflare because they lack a real browser's TLS fingerprint, JavaScript execution, HTTP/2 settings, and behavioral patterns. The only reliable solution is **real browser execution** — but Titan doesn't need to run the browser himself. He delegates.

**Decision tree for Titan:**

```
Does the target use Cloudflare / JS challenges?
├── NO → Use requests/curl with API key. Fast, cheap, reliable.
└── YES →
    ├── Is it a well-supported site (Claude.ai, Perplexity, Loom)?
    │   └── Use grab-cookies.py weekly + requests with cookies.
    │       Cookie refresh happens in weekly auth ritual.
    │
    ├── Is it a one-off research/harvest task?
    │   └── Delegate to Perplexity Computer via prewritten task prompt.
    │
    └── Is it a recurring structured harvest (data pipeline)?
        └── Use local Nodriver or Camoufox on VPS (headless, scheduled).
```

### Tool Recommendations by Use Case

#### [PROVEN] Nodriver — Default for Python Chrome Automation

Nodriver (successor to `undetected-chromedriver`, by the same author) is the 2026 recommended tool for Cloudflare bypass. It uses Chrome DevTools Protocol directly with no WebDriver signature:

```bash
pip install nodriver
```

```python
import asyncio
import nodriver as uc

async def harvest_cloudflare_site(url: str) -> str:
    browser = await uc.start(headless=True)
    tab = await browser.get(url)
    await tab  # wait for CF challenge to pass automatically
    await asyncio.sleep(3)  # behavioral delay
    content = await tab.get_content()
    browser.stop()
    return content

asyncio.run(harvest_cloudflare_site("https://target.com"))
```

Bypass rate: ~90% against standard Cloudflare. Fails on Turnstile interactive challenges. Best for Claude.ai-style protection levels.

#### [RECOMMENDED] Camoufox — Firefox-Based Stealth for High-Security Targets

When Nodriver fails (Chrome fingerprint profiles by target), Camoufox provides Firefox-based stealth with C++-level fingerprint spoofing:

```bash
pip install -U camoufox[geoip] browserforge
camoufox fetch  # downloads the patched Firefox binary
```

```python
from camoufox.sync_api import Camoufox

def harvest_with_camoufox(url: str) -> str:
    with Camoufox(headless=True, humanize=True, os=["windows"]) as browser:
        page = browser.new_page()
        page.goto(url)
        page.wait_for_load_state("networkidle")
        return page.content()
```

Bypass rate: ~80–95% depending on target. Best for sites with Chrome-specific behavioral detection. Cannot run fully headless against all Turnstile variants.

#### [RECOMMENDED] Browserless.io — Managed Browser for Mission-Critical Harvests

For high-value harvests where local browser failure is unacceptable, Browserless runs real Chrome in a managed cloud with pre-tuned stealth profiles:

```typescript
import { chromium } from 'playwright-core';

const browser = await chromium.connectOverCDP(
  `wss://production-sfo.browserless.io?token=${process.env.BROWSERLESS_TOKEN}&launch=${JSON.stringify({ stealth: true })}`
);
// ... standard Playwright code
```

Cost: pay-per-use. Best for overnight harvest tasks where VPS CPU limits would constrain parallel Nodriver sessions.

#### [PROVEN] Playwright `storageState` — Cookie Persistence Pattern

For grab-cookies.py workflow, use Playwright's storage state to export and reuse authenticated sessions:

```python
from playwright.sync_api import sync_playwright
import json

def refresh_and_save_cookies(service: str, login_url: str, output_path: str):
    """Run interactively during weekly auth ritual to refresh session cookies."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headed for interactive login
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url)

        # Human logs in here manually (15-second window)
        input(f"Log into {service} then press Enter...")

        # Save full session state (cookies + localStorage)
        context.storage_state(path=output_path)
        browser.close()

# Then for automated harvests:
def harvest_with_saved_session(url: str, session_path: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=session_path)
        page = context.new_page()
        page.goto(url)
        page.wait_for_load_state("networkidle")
        return page.content()
```

#### Perplexity Computer Delegation Rules

Titan's routing doctrine for Computer delegation:

- **Delegate to Computer** when: task involves DOM interaction + form filling + KYC flows + visual inspection of results + one-off browser sessions where spinning up a VPS browser is wasteful
- **Run locally on VPS** when: recurring structured harvest (nightly), data extraction with known schema, tasks requiring multiple parallel tabs
- **Never attempt raw HTTP** when: Cloudflare `cf_clearance` cookie is in play — just escalate immediately to browser tier

---

## 4. Mac-Level Automation

### Architecture Principle

[PROVEN] **Minimize what the Mac does autonomously.** The Mac is a human-present machine. Its primary role in the Titan stack is:

1. Running `grab-cookies.py` during the weekly auth ritual (headed browser, human-visible)
2. Hosting the Claude Code session (interactive)
3. Bridging to VPS for any task that needs a local IP or Keychain access

Push everything else to the VPS. The Mac sleeping or being closed is not a failure mode — it's expected. The VPS night-grind runs independently.

### Recommended Mac Automation Toolkit

#### [PROVEN] Hammerspoon — Primary Mac Orchestration Layer

Hammerspoon provides Lua-scripted system-level access: window management, WiFi event triggers, USB detection, application watching, and HTTP server. It's the right brain for "when Mac wakes, trigger auth ritual check":

```lua
-- ~/.hammerspoon/init.lua

-- Trigger auth ritual check when Mac wakes from sleep
hs.caffeinate.watcher.new(function(event)
  if event == hs.caffeinate.watcher.systemDidWake then
    -- Check if cookies are stale (> 6 days old)
    local result = hs.execute("/opt/titan-harness/check-cookie-freshness.sh")
    if result:find("STALE") then
      hs.notify.new({title="Titan", informativeText="Cookie refresh needed — run auth ritual"}):send()
    end
  end
end):start()

-- HTTP listener for VPS → Mac communication (e.g., "launch headed browser")
local server = hs.httpserver.new()
server:setPort(9876)
server:setCallback(function(method, path, headers, body)
  if path == "/launch-browser" then
    hs.execute("open -a 'Google Chrome' " .. body)
    return "ok", 200, {}
  end
end)
server:start()
```

#### [PROVEN] launchd — Mac-Side Scheduling (Not cron)

macOS replaced cron with launchd. Use it for cookie refresh and any Mac-side scheduled tasks:

```xml
<!-- ~/Library/LaunchAgents/com.titan.auth-ritual-reminder.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.titan.auth-ritual-reminder</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/opt/titan-harness/auth-ritual-check.py</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>5</integer>  <!-- Friday -->
    <key>Hour</key><integer>16</integer>    <!-- 4pm -->
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/var/log/titan/auth-ritual.log</string>
  <key>StandardErrorPath</key>
  <string>/var/log/titan/auth-ritual-error.log</string>
</dict>
</plist>
```

Load: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.titan.auth-ritual-reminder.plist`

#### [RECOMMENDED] AppleScript + osascript for App Interaction

When grab-cookies.py needs to interact with a running macOS browser profile, AppleScript provides reliable control:

```applescript
-- Open URL in specific Chrome profile and wait
tell application "Google Chrome"
  set newTab to make new tab at end of tabs of window 1
  set URL of newTab to "https://claude.ai"
  delay 2
  activate
end tell
```

Invoke from Python: `subprocess.run(["osascript", "-e", applescript_string])`

#### [AVOID] PyAutoGUI for Overnight Tasks

PyAutoGUI requires the application to be in the foreground and breaks when macOS moves focus. It is appropriate only for supervised, daytime automation with a human present. Never use it in scheduled overnight tasks — it will silently fail.

---

## 5. OS Scheduling & Job Orchestration

### VPS-Side: The Right Stack for Titan

#### [PROVEN] systemd timers — Primary VPS Scheduler

Prefer systemd timers over raw cron for all VPS jobs. Key advantages for Titan's use case:

- **Persistent=true**: runs missed jobs on reboot (critical for 01:00–05:00 night-grind window)
- **Dependency management**: job won't start if required service isn't ready
- **Resource caps**: `MemoryMax=` and `CPUQuota=` prevent runaway harvests consuming all RAM
- **Centralized logging**: `journalctl -u titan-harvest` gives full history with timestamps

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
RandomizedDelaySec=300  # spread load across 5 min window

[Install]
WantedBy=timers.target
```

Enable: `systemctl enable --now titan-harvest.timer`

#### [PROVEN] BullMQ (Redis-backed) — RADAR Job Queue

For the RADAR job queue that Titan adds tasks to throughout the day (to be consumed during the night-grind), BullMQ is the correct choice over raw cron or Celery:

- **Native TypeScript** (matches Titan's stack)
- **Built-in priorities** — P1 (time-sensitive client tasks) always run before P2 (research harvests)
- **Job dependencies** — MP-2 SYNTHESIS waits for MP-1 HARVEST via FlowProducer
- **Rate limiting** — prevents overnight harvests from hitting API rate limits
- **Delayed jobs** — schedule "run this at 02:00" without another cron entry

```typescript
import { Queue, Worker, FlowProducer } from 'bullmq';
const connection = { host: 'localhost', port: 6379 };

// RADAR queue with priorities
const radarQueue = new Queue('titan-radar', {
  connection,
  defaultJobOptions: {
    attempts: 3,
    backoff: { type: 'exponential', delay: 30000 },
    removeOnComplete: { count: 500, age: 86400 },
    removeOnFailed: { count: 100 },
  }
});

// Add a harvest task with priority
await radarQueue.add('harvest-campaign-data',
  { client: 'acme', pipeline: 'MP-1' },
  { priority: 1 }  // lower = higher priority
);

// Worker with concurrency control and rate limiting
const worker = new Worker('titan-radar', async (job) => {
  return await processPipelineJob(job.data);
}, {
  connection,
  concurrency: 4,          // max 4 parallel jobs
  limiter: { max: 20, duration: 60000 }  // 20 jobs/min rate cap
});
```

#### [RECOMMENDED] supervisord — Process Keepalive

For long-running daemons (BullMQ workers, webhook listeners, the Titan API server), supervisord keeps them alive across crashes and reboots:

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

#### Job Priority Schema for RADAR Backlog

```
P1 (immediate, < 1hr): Client deliverable deadlines, proposal sends, billing events
P2 (same night): Campaign data harvests, outbound sequences, reporting runs
P3 (this weekend): Research synthesis, library catalog updates, VPS maintenance
P4 (low, when idle): Background enrichment, historical data fills, archive tasks
```

[PROVEN] **Never let P3/P4 jobs block the queue.** Use separate BullMQ queues with separate worker pools — `titan-urgent`, `titan-harvest`, `titan-background`.

---

## 6. Safety, Logging & Recovery

### Logging Architecture

Every autonomous action Titan takes must be logged with three components: **what**, **why**, and **result**. This is non-negotiable for auditability.

#### [PROVEN] Structured JSON Logging — Universal Format

```python
import logging
import json
from datetime import datetime, timezone

class TitanAuditLogger:
    def __init__(self, log_path: str):
        self.log_path = log_path

    def log_action(self,
                   agent: str,
                   action: str,
                   target: str,
                   rationale: str,
                   result: str,
                   metadata: dict = None):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": agent,          # "titan", "harvest-worker", "radar"
            "action": action,         # "api_call", "file_write", "browser_session"
            "target": target,         # URL, file path, service name
            "rationale": rationale,   # why this action was taken
            "result": result,         # "success", "failed", "skipped"
            "metadata": metadata or {}
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
```

Log files rotate daily. Retain 90 days on VPS, archive to cold storage after.

#### [RECOMMENDED] Centralized Log Aggregation

For a one-person stack, Loki + Grafana (both free, self-hosted on VPS) gives searchable log dashboards without the complexity of ELK:

```bash
# docker-compose.yml addition
loki:
  image: grafana/loki:latest
  ports: ["3100:3100"]

grafana:
  image: grafana/grafana:latest
  ports: ["3000:3000"]
```

Add a Grafana alert: if `result: "failed"` appears more than 10 times in 30 minutes, send Slack notification to Solon.

### Rollback Strategies

#### [PROVEN] Git Snapshot Before Every Autonomous Change

Any time Titan modifies a config file, script, or repo, the change must be committed with a descriptive message before executing:

```bash
# titan-harness pre-change hook
git add -A
git commit -m "TITAN-AUTO: [action description] | rationale: [why] | ts: $(date -u +%Y%m%dT%H%M%SZ)"
```

Recovery is always: `git log --oneline -20` → find last known good → `git revert <hash>`.

#### [PROVEN] VPS Database Snapshots

Supabase mirror database: automated `pg_dump` nightly before night-grind starts (00:45 Boston time), stored to `/opt/titan-backups/db/` with 30-day retention:

```bash
pg_dump $DATABASE_URL | gzip > /opt/titan-backups/db/$(date +%Y%m%d).sql.gz
find /opt/titan-backups/db/ -name "*.sql.gz" -mtime +30 -delete
```

#### [PROVEN] Circuit Breaker Pattern — Never-Stop with Safety

The never-stop rule must have a circuit breaker to prevent runaway loops. Add a failure counter to any retry loop:

```python
MAX_CONSECUTIVE_FAILURES = 5
CIRCUIT_BREAK_SLEEP = 3600  # 1 hour cool-down

failures = 0
while True:
    try:
        result = execute_job(next_job())
        failures = 0
        audit_log.log_action(result=result)
    except Exception as e:
        failures += 1
        audit_log.log_action(result="failed", metadata={"error": str(e), "failure_count": failures})
        if failures >= MAX_CONSECUTIVE_FAILURES:
            notify_slack(f"TITAN CIRCUIT BREAK: {failures} consecutive failures. Sleeping 1hr.")
            time.sleep(CIRCUIT_BREAK_SLEEP)
            failures = 0
```

### Credential Leak Prevention

[PROVEN] Three rules for Titan's autonomous operation:

1. **Never log secrets** — audit logger must strip `api_key`, `token`, `password`, `cookie` fields from metadata before writing
2. **Never write secrets to repos** — `git secrets` or pre-commit hook scanning
3. **Never echo secrets in shell scripts** — always pipe directly: `security find-generic-password ... -w | command_needing_secret`

---

## 7. Hard Limits & Red Lines

These are absolute stops — Titan must escalate to Solon and wait for explicit approval before proceeding.

### Cannot Automate (Hard Stops)

| Action | Reason | Correct Pattern |
|---|---|---|
| **Password resets** | Triggers security alerts, may lock account | Always human-initiated |
| **New 2FA device enrollment** | Requires physical possession of old device | Weekly ritual only |
| **OAuth initial authorization** | Requires human browser consent flow | One-time setup with human |
| **Stripe/payment charges > $50** | Financial risk, ToS violation risk | HITL approval required |
| **Sending emails to >50 recipients** | CAN-SPAM, deliverability risk | Human review first |
| **Publishing public content** | Brand/legal risk | Human approval queue |
| **Deleting production data** | Irreversible, catastrophic risk | Human-confirmed only |
| **Modifying CORE_CONTRACT or routing doctrine** | Self-modification risk | Human review cycle |
| **Adding new OAuth scopes to existing apps** | Unexpected permission escalation | Human approval |
| **SSH key generation for new services** | Key management chain risk | Human-supervised |

### Should Not Automate (Soft Stops — Escalate with Recommendation)

| Action | Why Escalate | Pattern |
|---|---|---|
| Sending client proposals | Tone/legal sensitivity | Titan drafts, Solon sends |
| Domain purchases > $100 | Budget authority | Titan researches, Solon approves |
| Canceling SaaS subscriptions | Revenue impact | Titan flags, Solon confirms |
| New vendor API integrations | Legal/ToS review needed | Titan evaluates, Solon signs off |
| Changing pricing on AMG offerings | Business strategy decision | Human-only |

### macOS-Specific Hard Limits

- **System Integrity Protection (SIP)**: Cannot be bypassed even with sudo — affects `/System`, `/usr`, certain `/private/var` paths. Do not design workflows that depend on writing to SIP-protected paths.
- **TCC (Transparency, Consent, Control)**: Accessibility, Full Disk Access, Screen Recording permissions must be granted manually in System Settings — no programmatic override. Scripts relying on PyAutoGUI or screen capture must have TCC pre-approved.
- **Keychain Access prompts**: When a script first reads a Keychain item, macOS shows an approval dialog if the calling application isn't pre-authorized. Pre-authorize by running the script once interactively.
- **App Store sandboxing**: Mac App Store apps have sandboxed containers — AppleScript and automation access is restricted. Use non-App-Store versions (e.g., direct download) for apps Titan needs to automate.

---

## 8. Recommended Tool Stack

### The Full Titan Autonomy Stack

#### Secrets & Identity

| Tool | Role | Status | Priority |
|---|---|---|---|
| **Infisical (self-hosted)** | Primary secrets store, auto-rotation | [PROVEN] | Deploy now |
| **macOS Keychain + `security` CLI** | Bootstrap credentials only | [PROVEN] | Already usable |
| **pyotp** | Automated TOTP code generation | [PROVEN] | Add to auth-ritual.sh |
| **python-keyring** | Cross-platform Keychain access in Python | [PROVEN] | Use in grab-cookies.py |

#### Browser Automation & Anti-Bot

| Tool | Role | Status | Priority |
|---|---|---|---|
| **Nodriver** | Primary Cloudflare bypass (Chrome/async) | [PROVEN] | Replace undetected-chromedriver |
| **Camoufox** | Firefox-based stealth for high-security targets | [RECOMMENDED] | Add as fallback |
| **Playwright `storageState`** | Cookie persistence and session reuse | [PROVEN] | Core of grab-cookies.py |
| **Browserless.io** | Managed browser for mission-critical tasks | [RECOMMENDED] | Use for overnight high-value harvests |
| **Bright Data Scraping Browser** | Enterprise-grade bypass at scale | [EXPERIMENTAL] | Only if Nodriver+Camoufox both fail |

#### Mac-Side Automation

| Tool | Role | Status | Priority |
|---|---|---|---|
| **Hammerspoon** | Mac event triggers, HTTP listener for VPS→Mac bridge | [PROVEN] | Install this week |
| **launchd** | macOS scheduled tasks (auth ritual, cookie check) | [PROVEN] | Replace any cron-based Mac tasks |
| **osascript/AppleScript** | App-level interaction (browser launching) | [PROVEN] | Use sparingly, never overnight |

#### VPS Scheduling & Orchestration

| Tool | Role | Status | Priority |
|---|---|---|---|
| **systemd timers** | Primary VPS job scheduler | [PROVEN] | Convert night-grind to systemd |
| **BullMQ (Redis)** | RADAR job queue, priority scheduling | [PROVEN] | Core RADAR backend |
| **supervisord** | Long-running daemon keepalive | [PROVEN] | Wrap all Titan workers |
| **Redis 7.x** | BullMQ backend, also usable as cache | [PROVEN] | Should already exist on VPS |

#### Logging & Safety

| Tool | Role | Status | Priority |
|---|---|---|---|
| **Structured JSON audit log** | Action-level audit trail | [PROVEN] | Add to every pipeline |
| **Loki + Grafana** | Log aggregation + alerting | [RECOMMENDED] | Add to VPS Docker stack |
| **git pre-commit hooks** | Prevent secret leaks to repos | [PROVEN] | Add immediately |
| **Bitwarden Agent Access SDK** | Just-in-time credential injection for agents | [EXPERIMENTAL] | Monitor — alpha stage, not production-ready yet |

### What Titan Is Likely Missing (Add These)

1. [RECOMMENDED] **`infisical` CLI on VPS** — Replace `/opt/titan-harness-secrets/` flat files with proper secrets injection: `infisical run -- python harvest.py`. All secrets disappear from the filesystem.

2. [RECOMMENDED] **Playwright `storageState` in grab-cookies.py** — If grab-cookies.py still uses raw `requests` + Keychain to harvest cookies, upgrade it to Playwright's `context.storage_state()` export, which captures cookies + localStorage atomically. This is the production pattern.

3. [RECOMMENDED] **BullMQ dead-letter queue** — Any RADAR job that fails 3 times must move to a `titan-dlq` queue that surfaces in a weekly review, not silently disappear.

4. [RECOMMENDED] **`TimeoutStartSec` on every systemd unit** — Prevents a hung harvest from blocking the next scheduled run. Default to `3600` (1 hour) for harvest jobs, `300` for quick tasks.

5. [EXPERIMENTAL] **Camoufox on VPS for Perplexity.ai harvests** — If Perplexity.ai sessions require interactive challenge-solving, Camoufox running headless on VPS (with `humanize=True`) may pass the CF challenge without human involvement. Test in staging first; results vary by CF configuration at the time.

6. [EXPERIMENTAL] **tmux subagent pattern** — For coordinating multiple Claude Code agents on the same Mac session, the tmux pane communication pattern (send keystrokes to a named tmux pane, read stdout) allows Titan to spawn sub-agents without an API. Watch for session stability issues on long runs.

---

## Implementation Sequence

Execute in this order to move from current state toward 99.99% autonomy:

### Phase 1 — Secrets Hardening (Week 1–2)
1. Deploy Infisical on VPS (`docker compose up infisical`)
2. Migrate `/opt/titan-harness-secrets/` flat files into Infisical
3. Wrap all VPS scripts with `infisical run -- <command>`
4. Add `pyotp` to grab-cookies.py for all TOTP-protected services
5. Install `git secrets` pre-commit hook on titan-harness repo

### Phase 2 — Auth Ritual Systemization (Week 2–3)
1. Write `auth-ritual.sh` that batches all token/cookie refreshes
2. Add launchd plist to remind every Friday 4pm
3. Convert grab-cookies.py to use Playwright `storageState` export
4. Test weekly ritual end-to-end — time it (target < 20 minutes)

### Phase 3 — Anti-Bot Upgrade (Week 3–4)
1. Install Nodriver on VPS, test against Claude.ai + Perplexity.ai
2. Add Camoufox as fallback in harvest router
3. Update routing doctrine: "If HTTP 403 from CF target → escalate to Nodriver"
4. Add browserless.io account for mission-critical overnight sessions

### Phase 4 — Scheduling & Queue (Week 4–5)
1. Convert night-grind script to systemd timer with `Persistent=true`
2. Deploy BullMQ + Redis, migrate RADAR to BullMQ with priority tiers
3. Set up `titan-urgent`, `titan-harvest`, `titan-background` separate worker pools
4. Install supervisord wrapping for all long-running Titan daemons

### Phase 5 — Logging & Safety (Week 5–6)
1. Add structured JSON audit logger to every pipeline entry point
2. Deploy Loki + Grafana, pipe Titan logs to Loki
3. Create Grafana alert: >10 consecutive failures → Slack DM
4. Implement circuit breaker in the never-stop loop
5. Add circuit-break dead-letter review to weekly ritual

---

## Quick Reference: Weekly Auth Ritual Checklist

Run every Friday before 5pm (before weekend night-grinds):

```
□ Run grab-cookies.py --services all (30-sec interactive login per Cloudflare service)
□ Run oauth-refresh.py --check-expiry (auto-refreshes expiring tokens)
□ Check Infisical dashboard for any secrets flagged as expiring within 14 days
□ Review BullMQ dead-letter queue (jobs that failed 3+ times)
□ Scan Titan audit log for any RED_LINE escalation flags
□ Confirm VPS systemd timers are all active: `systemctl list-timers --all`
□ Run pg_dump manually if automated backup hasn't fired today
```

Total time target: **15–20 minutes**. If it takes longer, automate what's still manual.

---

*This document is a living doctrine file. Every time Titan's stack changes (new services, new auth patterns, new failure modes), update this blueprint as the authoritative design reference.*
