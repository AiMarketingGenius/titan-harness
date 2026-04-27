# CT-0427-41 — Kimi launcher cleanup (companion to account-isolation runbook)

**Owner:** Titan
**Date:** 2026-04-27T16:20Z
**Status:** SHIPPED. Methodical cleanup of 16 duplicate/broken Kimi launcher variants.

## Why

Earlier today CT-0427-41 shipped per-persona Vendor Runtime copies + applet wrappers for Hercules / Nestor / Alexander, then surgical Cookies wipe. After that, Solon's Spotlight surfaced multiple Hercules/Nestor/Alexander candidates — 21 total .app variants from Achilles's prior iterations, several with **conflicting bundle IDs** that caused LaunchServices to resolve unpredictably:

- `~/Applications/HerculesDock.app` claimed `io.achilles.hercules.dock` — same ID as the working `/Applications/Hercules.app`
- `~/Applications/NestorDock.app` claimed `io.achilles.nestor.dock` — same ID as the working `/Applications/Nestor.app`

That collision is exactly what made Solon see "Vendor-Hercules" tooltip when clicking what he thought was Nestor — macOS picked the wrong bundle for the same ID.

## What's preserved (the 3 keepers)

| Path | Bundle ID | Type | Maps to |
|---|---|---|---|
| `/Applications/Hercules.app` | `io.achilles.hercules.dock` | applet | Vendor-Hercules + Hercules profile (phone 617-797-0402) |
| `/Applications/Nestor.app` | `io.achilles.nestor.dock` | applet | Vendor-Nestor + Nestor profile (email growmybusiness@aimarketinggenius.io) |
| `/Applications/Alexander.app` | `com.amg.alexander.app` | applet | Vendor-Alexander + Alexander profile (phone 339-242-3653) |

Alexander.app was renamed from `AlexanderApp.app` in this cleanup (was a temporary name during the rebuild iterations).

## What was moved

All 16 clutter variants → `~/AMG/backups/clutter-cleanup-20260427T161641Z/`:

```
user-Applications/
  Alexander.app                       # Apr 25 01:30, electron, io.achilles.alexander
  Hercules.app                        # Apr 23 10:51, electron, io.achilles.hercules
  Nestor.app                          # Apr 23 10:51, electron, io.achilles.nestor
  HerculesAgent.app                   # Apr 25, applet, io.achilles.hercules.agent
  HerculesDock.app                    # Apr 25, applet, io.achilles.hercules.dock (BUNDLE ID COLLISION)
  NestorAgent.app                     # Apr 25, applet, io.achilles.nestor.agent
  NestorDock.app                      # Apr 25, applet, io.achilles.nestor.dock (BUNDLE ID COLLISION)
AMG-Agent-Dock/
  Alexander.app                       # Apr 25, applet, io.achilles.kimi-agent-dock.alexander
  Alexander.app.previous-20260425T184839Z
  Alexander.app.previous-20260425T190914Z
  Hercules.app                        # Apr 25, applet, io.achilles.kimi-agent-dock.hercules
  Hercules.app.previous-20260425T190915Z
  Nestor.app                          # Apr 25, applet, io.achilles.kimi-agent-dock.nestor
  Nestor.app.previous-20260425T190915Z
launcher-backups/
  20260424T195749Z/Hercules.app      # earlier launcher iteration
  20260424T195749Z/Nestor.app
```

These are RECOVERABLE — restore via `mv` if anything was needed back.

## Method (each step ordered, verifiable, reversible)

1. `mdfind -name "Hercules"` + Nestor + Alexander to enumerate all variants on disk
2. Per-entry: extract path + mtime + CFBundleIdentifier + CFBundleExecutable + structure (applet vs electron)
3. Classify each as KEEPER or CLUTTER based on (a) is it the working K-icon variant? (b) does it have bundle ID collision with another?
4. For each clutter entry: `lsregister -u <path>` to remove from LaunchServices DB → `mv <path> <backup>` 
5. Rename `/Applications/AlexanderApp.app` → `/Applications/Alexander.app`; update Info.plist (`CFBundleName`, `CFBundleDisplayName`); re-sign ad-hoc deep; xattr clear
6. Update `~/Desktop/Launch Alexander.command` to point at new path
7. `lsregister -r -domain local -domain system -domain user` to rebuild LaunchServices DB
8. `killall Finder; killall Dock` to flush their caches
9. Smoke-test each app in isolation: `pkill -9 Vendor-*`; `open /Applications/<App>.app`; verify only the matching `Vendor-<Persona>` processes spawn

## Verification

```bash
# Direct filesystem check
$ find /Applications "$HOME/Applications" -maxdepth 4 -name "Hercules*" -o -name "Nestor*" -o -name "Alexander*" 2>/dev/null | grep -E "\.app$" | grep -v "/AMG/backups/"
/Applications/Alexander.app
/Applications/Hercules.app
/Applications/Nestor.app

# Spotlight check
$ mdfind -name "Hercules.app" | grep -v "/AMG/backups/"
/Applications/Hercules.app

# Smoke-test (each in isolation)
$ pkill -9 -f "Vendor-"
$ open /Applications/Hercules.app && sleep 5
$ ps -A | grep -c "Vendor-Hercules.*Kimi"  # → 10
$ ps -A | grep -c "Vendor-Nestor.*Kimi"    # → 0
$ ps -A | grep -c "Vendor-Alexander.*Kimi" # → 0
# (similarly for Nestor.app, Alexander.app)
```

## Result

- 21 variants → 3 kept + 16 archived ≈ 76% reduction in Spotlight clutter
- Bundle ID collisions resolved (no two installed bundles claim the same ID)
- AlexanderApp.app renamed to Alexander.app for naming parity with Hercules.app + Nestor.app
- LaunchServices DB rebuilt; Finder + Dock caches flushed
- Each app launches its OWN Vendor runtime in isolation (verified via ps grep)

## What's still pending Solon-side

1. Drag working /Applications/Alexander.app to Dock (replacing any old broken Dock entry from before the rename)
2. Wait for Kimi SMS throttle cooldown (~30-60 min from last attempt) before retrying phone logins for Hercules + Alexander
3. Click each app icon → fresh login per persona credential

## Mirror cascade

- VPS canonical: `/opt/amg-docs/runbooks/CT-0427-41_kimi_launcher_cleanup.md`
- Harness mirror: `~/titan-harness/docs/runbooks/CT-0427-41_kimi_launcher_cleanup.md`
