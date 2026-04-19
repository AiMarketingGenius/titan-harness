# Don-Demo Fallback Videos — 2026-04-19

Part of CT-0419-05 Lane D (Step 3: fallback video strategy) executed autonomously
by Titan 2026-04-19T14:13Z per user directive "execute all four Solon actions via
Stagehand + API + SSH autonomously".

## Files (stored OUTSIDE git — too large for repo)

| File | Size | Surface captured |
|---|---|---|
| don-backup-20260419-aimg-site.mp4 | 4.2 MB | deploy/aimg-site/index.html (Lumina v2 Lane B) |
| don-backup-20260419-memoryguard-site.mp4 | 3.5 MB | deploy/aimemoryguard-landing/index.html (Lane C) |
| don-backup-20260419-chatbot.mp4 | 3.1 MB | deploy/amg-chatbot-widget/demo.html (Lane E) |

## Locations

- **VPS primary:** `/opt/amg/demo-assets/` on 170.205.37.148 (via rsync)
- **Mac local:** `/tmp/amg-fallback-videos/` on Solon's Mac (kept, not in git)
- **Harness repo:** intentionally NOT in git (binary + 10MB total)

## How they were generated

```
cd ~/titan-harness
npm install playwright  (one-time)
OUTPUT_DIR=/tmp/amg-fallback-videos node scripts/record-don-fallbacks.mjs
```

Viewport 1280x800, headless Chromium, local Python 3 static servers per surface.

## Voice demo NOT included

Per original FALLBACK_VIDEO_STRATEGY doc: voice demo requires real mic + real backend
round-trip, must be captured via macOS Screen Recording + live voice. Still deferred
to Solon.

## Solon action

To retrieve locally:

```
scp root@170.205.37.148:/opt/amg/demo-assets/don-backup-20260419-*.mp4 ~/Desktop/
```

Or use existing Mac copies at `/tmp/amg-fallback-videos/`.
