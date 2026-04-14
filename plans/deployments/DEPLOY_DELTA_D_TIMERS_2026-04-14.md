# DEPLOY — DELTA-D systemd timer bundle

**Deploy ID:** DELTA-D (DR-AMG-RESILIENCE-01 / Item 3)
**Date:** 2026-04-14
**Operator:** Titan (mac-solon session)
**Approval:** Solon — `CONFIRM: EXECUTE DELTA-D` (2026-04-14)

## What ships

Five systemd timers for self-healing cadence + SHA drift detection on AMG VPS.

| Timer | Period | Runs | Purpose |
|---|---|---|---|
| `amg-git-heal.timer` | 5 min | `/opt/amg/scripts/git-heal.sh` | Domain 1 — bare repo integrity + mirror sync |
| `amg-disk-heal.timer` | daily | `/opt/amg/scripts/disk-heal.sh` | Domain 2 — disk hygiene + R2 offload |
| `amg-doctrine-drift.timer` | hourly | `/opt/amg/scripts/doctrine-drift-check.sh` | SHA check of doctrine v1.0 file (Tier 1 on drift) |
| `amg-config-drift.timer` | hourly | `/opt/amg/scripts/config-drift-check.sh` | SHA check of 6 security + operational configs |
| `amg-sha-consistency.timer` | weekly | `/opt/amg/scripts/sha-consistency-check.sh` | Harness vs VPS expected-SHA divergence (catches tampering of expected file itself) |

**Descope:** `amg-titan-check.timer` (Domain 10) — Titan runs on Mac, not VPS. Reactivates when ACCESS-REDUNDANCY places a Titan instance on Hetzner secondary.

## Drift tier assignments

Per Solon confirmation:

| File | Tier | Rationale |
|---|---|---|
| `/etc/ssh/sshd_config` | 2 (immediate Slack) | Security-critical — lockout risk |
| `/etc/amg/ufw-canonical-commands.sh` | 2 | Security-critical — firewall |
| `/etc/fail2ban/jail.local` | 2 | Security-critical |
| `/etc/fail2ban/jail.d/whitelist.conf` | 2 | Security-critical |
| `/opt/n8n/Caddyfile` | 1 (digest) | Operational — 24hr digest catches what INC-2026-04-14-01 missed |
| `/opt/n8n/docker-compose.yml` | 1 | Operational |
| `/opt/amg/docs/amg-self-healing-doctrine-v1.md` | 1 | Documentation drift, low urgency |

## Expected SHA baseline (captured 2026-04-14T20:52Z)

```
739edad7c846bafff30ebe208a049d71ab50e6a79921ce5e900b9e0123d0a155  /opt/amg/docs/amg-self-healing-doctrine-v1.md
ac372397859027c1347536d5845ffc605273b442d474829cac7dd0f9a86bf535  /opt/n8n/Caddyfile
317082f4ab28c7b1d867e36e126027e2dc287713ab179c651422163ff7773db1  /opt/n8n/docker-compose.yml
579e22d7b62a152ba869e2aeb7f8167e3d53044755b4a101df4cd97b05dacfd9  /etc/ssh/sshd_config
4cfae7e2842717d211a057abee0e5de23020d8313f04454d6a785be058c9dc83  /etc/amg/ufw-canonical-commands.sh
6d6a09ca925c5ce3197f2f9acb8e847232798748ec4ffccafd7d7b49072e4716  /etc/fail2ban/jail.local
a15df28a581346453e7ef09152cb905d09ef6130a5ecd86f785e1ebc2ebe086a  /etc/fail2ban/jail.d/whitelist.conf
```

Canonical harness-tracked at `services/amg-vps/sha256-expected.txt`.
Deployed to VPS at `/opt/amg/.sha256-expected.txt` via scp during install.

## Harness tree

```
services/amg-vps/
├── sha256-expected.txt                     # canonical expected SHAs (7 files)
├── install-delta-d-timers.sh               # installer + --rollback flag
├── opt-amg-scripts/
│   ├── doctrine-drift-check.sh             # new — single-file SHA check
│   ├── config-drift-check.sh               # new — 6-file SHA check w/ per-file tier
│   └── sha-consistency-check.sh            # new — weekly harness↔VPS compare
└── etc-systemd/
    ├── amg-git-heal.{service,timer}
    ├── amg-disk-heal.{service,timer}
    ├── amg-doctrine-drift.{service,timer}
    ├── amg-config-drift.{service,timer}
    └── amg-sha-consistency.{service,timer}
```

## Install safety pattern

`install-delta-d-timers.sh` executes in this order:

1. **Preflight:** verify all 10 unit source files + 5 scripts exist + executable + `/opt/amg/.sha256-expected.txt` exists. Non-zero exit on any miss.
2. **Install:** `cp` units to `/etc/systemd/system/` + `systemctl daemon-reload`.
3. **Test:** `systemctl start <each>.service` (oneshot) one at a time. Check `Result=success` OR exit=1 (for drift scripts where 1 = drift detected = correct behavior).
4. **Enable gate:** enable timers ONLY after all services exit cleanly. If any test fails → units installed but no timers enabled; operator runs `--rollback` or debugs.
5. **Rollback:** `./install-delta-d-timers.sh --rollback` disables + removes all 10 unit files.

## Lockout gate (DELTA-D)

| Q | A |
|---|---|
| Touches sshd/keys/AllowUsers/PAM/shadow? | NO (drift-watches, no modification) |
| Touches UFW/iptables/fail2ban? | NO (drift-watches, no modification) |
| Touches cron/systemd/launchd? | YES — installs 5 new systemd timers |
| OPA/enforcement block operator? | NO |
| Rollback without SSH? | YES — each timer individually disable-able via Hammerspoon/console |

Mitigations: (1) escape-hatch SSH alive during install, (2) per-service test gate blocks enablement on any error, (3) `--rollback` mass-removes cleanly.

## Deployment notes

- `amg-sha-consistency.service` initial test failed because `/opt/titan-harness/` mirror on VPS did not yet contain this commit's `sha256-expected.txt` — CORRECT behavior (script emitted `HARNESS_EXPECTED_MISSING` Tier 2 per spec). Fixed by committing harness artifact + post-commit hook auto-mirror → VPS working tree caught up → re-run installer → all 5 pass.

## Rollback (full)

```bash
ssh -4 -p 2222 root@170.205.37.148 \
  '/opt/amg/install-delta-d-timers.sh --rollback'
```

Idempotent. Disables all 5 timers, removes 10 unit files, daemon-reloads. Leaves scripts + SHA manifest in place (harmless — just not invoked).

## Grading block

- **Method used:** Titan self-grade against `§13.7 First-Pass Verification Gate` (infra delta class).
- **Why this method:** multi-file systemd install requires ground truth via `systemctl` + filesystem inspection — Perplexity cannot verify.
- **Grade:** A
  - Cross-file: unit files reference scripts that exist; scripts reference SHA manifest that exists; manifest matches live file SHAs
  - Correctness: 4/5 services pass test phase on first install; 5th (sha-consistency) failed correctly by design (harness mirror ahead-of-state); re-ran after harness commit → all 5 pass
  - Non-destructive: install gates enablement on per-service test
  - Reversible: `--rollback` flag removes cleanly
  - ADHD-format: numbered install phases, tabular timer spec
  - §12 grading block: present
  - Hook compliance: pre-commit + auto-mirror expected to pass (services/ prefix allowed)
- **Decision:** promote to active. Auto-continue to DELTA-E descope + Hermes check.
