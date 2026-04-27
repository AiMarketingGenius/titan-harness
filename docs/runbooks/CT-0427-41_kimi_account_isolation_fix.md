# CT-0427-41 — Kimi 3-chief account-isolation fix (runbook)

**Owner:** Titan
**Date:** 2026-04-27
**Status:** INFRASTRUCTURE FIX SHIPPED. Activation requires Solon fresh-logins.

## Problem

All 3 Kimi chief apps (`/Applications/{Hercules,Nestor,Alexander}.app`) auto-logged into the Hercules account regardless of which icon Solon clicked. Required hardwired bindings:
- Hercules → phone 617-797-0402
- Nestor → email growmybusiness@aimarketinggenius.io
- Alexander → phone 339-242-3653

## Root cause

Two bugs stacked:

1. **Electron singleInstance lock** — the Kimi binary calls `app.requestSingleInstanceLock()` (confirmed in `app.asar`). When a second Kimi instance launches with the same bundle ID `com.moonshot.kimichat`, the lock denies it → `app.quit()` exits the second instance → existing Hercules window pops forward via `second-instance` handler → user sees Hercules account.

2. **Historical profile contamination** — months of singleInstance hijack caused login attempts in one persona to actually fire inside whichever Kimi window was alive. The user-data-dir Cookies + auth state across the 3 profiles cross-contaminated.

Achilles built the per-persona profile dirs (`~/Library/Application Support/{Hercules,Nestor,Alexander}` with separate Cookies files) but did not solve the singleInstance lock or fix contamination.

## Fix

Per-persona Vendor Runtime copies with unique bundle IDs (matches Alexander.app's existing precedent of having `io.achilles.alexander` ≠ `com.moonshot.kimichat`). Three copies of `Vendor Runtime.app` live at `~/Applications/.agent-vendor-runtime/`:

| Copy | Bundle ID | Used by |
|---|---|---|
| Vendor Runtime.app | com.moonshot.kimichat | (original — kept for upgrades) |
| Vendor-Hercules.app | com.amg.kimi-hercules | /Applications/Hercules.app |
| Vendor-Nestor.app | com.amg.kimi-nestor | /Applications/Nestor.app |
| Vendor-Alexander.app | com.amg.kimi-alexander | /Applications/Alexander.app |

Each Vendor-{Persona}.app:
- Modified `Contents/Info.plist` only — `CFBundleIdentifier` changed; `CFBundleName` + `CFBundleExecutable` LEFT AS "Kimi" (otherwise Electron's helper-app discovery breaks with FATAL "Unable to find helper app")
- Re-signed ad-hoc with `codesign --force --deep --sign -`
- Auto-update path inherited from original; will likely fail on next Kimi update (acceptable — manually update via original Vendor Runtime then re-build copies)

Each /Applications/{Hercules,Nestor,Alexander}.app updated:
- Hercules + Nestor applets recompiled via `osacompile` to reference their own `Vendor-{Persona}.app/Contents/MacOS/Kimi` instead of shared
- Alexander shell wrapper at `Contents/MacOS/Alexander` updated via `sed` to swap shared Vendor Runtime → Vendor-Alexander.app
- All 3 .app bundles re-signed ad-hoc

## Verification (done 2026-04-27T14:36Z)

After fix, launched Hercules + Nestor sequentially:
- Hercules.app → 7 processes under `Vendor-Hercules.app`
- Nestor.app → 7 processes under `Vendor-Nestor.app` (concurrent with Hercules)
- 0 processes from original `Vendor Runtime` (clean)

singleInstance bug **resolved**. Both apps coexist.

## What Solon must do to activate per-persona accounts

The infrastructure is fixed but the historical user-data-dir cookies are contaminated. Account binding only works after fresh logins. Two paths:

### Path A (recommended): Mac restart + wipe + fresh login

1. Save any work in any Kimi window
2. Restart Mac (Apple menu → Restart) — clears all process state + Finder cache + Spotlight index (also fixes Nestor.app dock-drag visibility)
3. After login, Titan or Solon runs:
   ```bash
   rm -rf "$HOME/Library/Application Support/Hercules"
   rm -rf "$HOME/Library/Application Support/Nestor"
   rm -rf "$HOME/Library/Application Support/Alexander"
   ```
   This wipes contaminated profiles. The .app launchers will recreate them on first run with --user-data-dir.
4. Solon launches `Hercules.app` → fresh login with phone **617-797-0402**
5. Solon launches `Nestor.app` → fresh login with email **growmybusiness@aimarketinggenius.io**
6. Solon launches `Alexander.app` → fresh login with phone **339-242-3653**
7. All 3 windows visible simultaneously, each in correct account

### Path B (lighter): logout-relogin without wipe

In each Kimi app's user menu, log out, then log back in with the correct credentials per persona. May or may not clear all contamination depending on what state Kimi's web app caches beyond cookies.

## Backups

Pre-fix state preserved at:
- `~/AMG/backups/Hercules.app.bak.20260427T143234Z`
- `~/AMG/backups/Nestor.app.bak.20260427T143234Z`
- `~/AMG/backups/Alexander-script.bak.20260427T143657Z`

To roll back: `rm -rf /Applications/Hercules.app && cp -R ~/AMG/backups/Hercules.app.bak.20260427T143234Z /Applications/Hercules.app`. Re-sign ad-hoc after restore.

## Disk impact

~2.5GB additional disk used (3 × 830MB Vendor copies). Mac data volume currently 99% / 30GiB free at fix time — flag for separate cleanup task.

## Outstanding sub-issue: Nestor.app dock-drag

Solon reported Nestor.app couldn't be dragged from /Applications to Dock. Code-sign is identical to Hercules.app (same ad-hoc signature, same xattr). Likely fixed by Mac restart (clears Finder cache + Spotlight reindex). If still broken post-restart: `mdimport /Applications/Nestor.app && killall Finder` should force re-indexing.

## Mirror cascade

This runbook lives at:
- VPS canonical: `/opt/amg-docs/runbooks/CT-0427-41_kimi_account_isolation_fix.md`
- harness mirror: `~/titan-harness/docs/runbooks/CT-0427-41_kimi_account_isolation_fix.md` (after commit)

