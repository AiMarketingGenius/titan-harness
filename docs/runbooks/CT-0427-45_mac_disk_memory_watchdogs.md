# CT-0427-45 — Mac Disk + Memory Watchdog (runbook)

**Owner:** Titan
**Date:** 2026-04-27
**Status:** WATCHDOGS INSTALLED. Real disk relief requires Solon-side action (iCloud Optimize or Downloads cleanup).

## Why this exists

Mac data volume hit 99% / 30 GiB free during CT-0427-41 Vendor Runtime copy work. Same outage class as VPS disk emergency (CT-0427-35). Solon directive 2026-04-27: install Mac-side disk + memory watchdog with same playbook.

## What's installed

| Component | Cadence | Action |
|---|---|---|
| `~/Library/LaunchAgents/com.amg.disk-watchdog-mac.plist` | 15min | Runs `mac-disk-watchdog.sh`. Threshold 85%. On breach → safe-prune + Slack alert. |
| `~/Library/LaunchAgents/com.amg.memory-watchdog-mac.plist` | 5min | Runs `mac-memory-watchdog.sh`. Threshold 85%. On breach → Slack alert with top-7 RSS procs. |

Scripts at `~/AMG/scripts/mac-{disk,memory}-watchdog.sh`. Mirrored to `~/titan-harness/bin/mac-watchdogs/`. Plists mirrored to `~/titan-harness/launchd/`.

## Safe auto-prune playbook (no Solon greenlight needed)

- `~/Library/Caches/*` files mtime >30 days
- `~/Library/Logs/*` files mtime >14 days
- Time Machine local snapshots (thin to 1GB urgency via `tmutil thinlocalsnapshots`)
- Xcode simulators (`xcrun simctl delete unavailable`)

**~/.Trash NOT auto-cleared** — Solon directive 2026-04-27: "afraid to delete too many things, for repurposing." Trash is Solon-only.

## Solon-greenlight playbook (manual approval)

Watchdog posts candidates to Slack #amg-admin if disk still >85% post-safe-prune. Solon authorizes per-item before any delete. Categories:
- ~/Downloads/* zips >5 GB and mtime >30 days
- ~/Library/Application Support/<app> dirs >5 GB
- Old Vendor Runtime auto-update caches

## First-run results (2026-04-27T14:51Z)

- Pre: 30 GiB free, 99%
- Pruned: 3.4 GB caches >30d (12,059 files) + 38 logs >14d
- Post: 34 GiB free, 99% (cleanup is dust vs total)

**Real bottleneck found:** `~/Library/Mobile Documents` = **1.2 TB iCloud Drive synced locally**. NOT clutter — synced user data. Fix paths require Solon:

1. **Enable "Optimize Mac Storage"** (System Settings → Apple ID → iCloud → "Optimize Mac Storage" toggle). macOS will evict cold iCloud files to cloud-only. Could recover ~500GB-1TB depending on access patterns.
2. **Move `~/Downloads` zips to R2** — 60+ GB across top 5 (b_roll_files.zip 34G, SeoRockstars 13G, Drone Photos 6.7G, Weekly Training 3.8G + 3.8G dup). All multi-month-old.
3. `~/Library/Application Support/Claude` = 11 GB (probably my chat history). Solon decides if archivable.
4. `~/Library/Application Support/Wispr Flow` = 8.1 GB. Solon decides.

## Verification

```bash
launchctl list | grep -E "com\.amg\.(disk|memory)-watchdog-mac"
# both listed = active
tail -5 ~/.openclaw/logs/mac_disk_watchdog.log
tail -5 ~/.openclaw/logs/mac_memory_watchdog.log
```

## Mirror cascade

This runbook lives at:
- VPS canonical: `/opt/amg-docs/runbooks/CT-0427-45_mac_disk_memory_watchdogs.md`
- harness mirror: `~/titan-harness/docs/runbooks/CT-0427-45_mac_disk_memory_watchdogs.md`

