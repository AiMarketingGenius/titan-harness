# CT-0419-05 Step 3 — Fallback Video Strategy

**Built:** 2026-04-19 by Titan
**Purpose:** Pre-record 90-second demo videos for each Don-Demo artifact so Solon has a bulletproof fallback if live surfaces hiccup mid-pitch Monday 11am ET.
**Status:** Recording scripts shipped. Actual .mp4 capture deferred to Solon-side (requires his Mac + logged-in sessions for the voice demo).

## Why videos matter for Don

Monday pitch is live. If aimarketinggenius.io DNS glitches, if the voice demo hits the daily cap mid-conversation, if the chatbot service-worker misfires — Don sees a broken product. A 90-second pre-recorded walkthrough per surface means Solon can say "Let me show you the Einstein fact-check in action" and play the video in-line, no network dependency.

## Deliverable paths

Per CT-0419-05 task spec, fallback videos go to:

```
/opt/amg/demo-assets/don-backup-20260419-voice.mp4
/opt/amg/demo-assets/don-backup-20260419-chatbot.mp4
/opt/amg/demo-assets/don-backup-20260419-aimg-site.mp4
/opt/amg/demo-assets/don-backup-20260419-memoryguard-site.mp4
```

Filename convention: `don-backup-YYYYMMDD-{surface}.mp4`

## Recording approach — 2 paths

### Path A (preferred): Playwright script (automated)

Solon runs `node scripts/record-don-fallbacks.mjs` from his Mac. Opens each preview server, walks through a scripted interaction sequence, writes `.mp4` to `/opt/amg/demo-assets/`.

Pros: repeatable, deterministic, regenerates on every content change
Cons: voice demo needs a real mic + real audio round-trip to atlas-api (script can't fake that end-to-end autonomously)

See `scripts/record-don-fallbacks.mjs` (shipped in this commit).

### Path B (pragmatic): macOS Screen Recording

Solon opens each surface in a real browser, walks through the demo, QuickTime Player → File → New Screen Recording. Cut to 90s in iMovie. Upload to /opt/amg/demo-assets/.

Pros: captures real voice + real interaction, no scripting hiccups
Cons: 4 × ~5 minutes = 20 minutes of Solon time Sunday evening

**Recommended:** Path B for voice demo (needs real audio), Path A for the three visual surfaces (aimg-site + memoryguard + chatbot).

## Scripted sequences (what the video shows)

### 1. aimg-site (90s)
1. [0-5s] Landing. Hero title + italic serif "shows up" accent.
2. [5-15s] Scroll to 7-agent grid. Hover on each agent card one by one.
3. [15-30s] Scroll to pricing. Hover the featured Core tier.
4. [30-45s] Scroll to Chamber band. Show the 4 stat cards.
5. [45-60s] Scroll to case studies. Highlight Shop UNIS +41% organic.
6. [60-75s] Scroll to guarantee section. Rest on the Hormozi-style promise.
7. [75-90s] Scroll to closing CTA. Fade out.

### 2. memoryguard-site (90s)
1. [0-10s] Landing + ambient gradient drift visible.
2. [10-25s] **Live demo panel runs cycle 1** (Eiffel Tower flag). Einstein badge fires.
3. [25-35s] Cycle 2 (Claude Auto-Carryover verified).
4. [35-45s] Scroll to features (Thread Health dial + Auto-Carryover diagram + Einstein bubble).
5. [45-60s] Scroll to How It Works 4-step.
6. [60-80s] Scroll to pricing — toggle monthly/annual to show the animation.
7. [80-90s] Closing CTA.

### 3. chatbot widget (90s)
1. [0-5s] Page loads (any demo context). FAB visible bottom-right with pulse ring.
2. [5-10s] Click FAB. Panel opens with greeting.
3. [10-20s] Type "What are your prices?". Fake SSE streaming via demo interceptor.
4. [20-35s] Agent replies + pricing grid renders (3-col).
5. [35-50s] Click "Book a 15-min audit" button.
6. [50-65s] Type "Tell me about Chamber program". Streaming reply + guarantee card.
7. [65-80s] Click action button. Input pre-fills.
8. [80-90s] Close panel. Return to page.

### 4. voice demo (90s) — Solon records live (Path B)
1. [0-10s] Landing. Orb pulses blue with halo glow.
2. [10-25s] Press and hold orb. "Listening" state, level ring pulses with Solon's voice.
3. [25-40s] Release. Transcript appears. Status pill: "Alex is thinking" → "speaking".
4. [40-60s] Alex audio plays. Reply rendered in transcript.
5. [60-80s] Second turn — press/hold/release, show 5-turn memory.
6. [80-90s] Tap orb during playback (barge-in demo). Audio stops. New recording starts.

## Post-record verification

Each video should:
- Be exactly 85-95 seconds (tight enough to play in-line, not so short it looks rushed)
- Have no audio on visual-only captures (aimg-site, memoryguard, chatbot) — Solon narrates live
- Have clean audio on voice demo (Solon + Alex audible, no music, no ambient noise)
- Render at 1280×800 minimum (4:3 or 16:10 preferred — plays on Solon's iPad at pitch)
- Be encoded as h.264 / AAC for universal playback (QuickTime, VLC, iOS Photos)
- Be under 40 MB each (fits email attachment limits for "let me send you these")

## Fallback during pitch

If live surface hiccups mid-pitch:
1. Solon says: "While that spins up, let me show you the recorded walkthrough"
2. Opens Photos app on iPad (or QuickTime on Mac)
3. Plays the relevant .mp4
4. Narrates over it live

Time cost of fallback: 20s (open app + pick video) + 90s (video plays) = 110s. Tolerable inside the 20-min pitch budget.

## Current state (as of 2026-04-19T13:22Z)

- **Recording script shipped**: `scripts/record-don-fallbacks.mjs` (Playwright-based, for aimg-site + memoryguard + chatbot)
- **Voice demo recording**: Solon-side (needs real audio)
- **All 4 .mp4 files**: not yet generated. Solon runs the script + does the voice Path B record Sunday evening.

## Cost estimate (Solon time)

- Script-generated videos (3): 10 min total (run script, inspect, re-run if needed)
- Voice demo manual record: 10 min (practice 1 take + record 1 take + trim)
- Upload to /opt/amg/demo-assets/ on primary VPS: 2 min
- **Total: ~22 min of Solon time Sunday evening**

## Rollback

If fallback videos aren't generated Sunday evening, Don-demo still has the LIVE sites as primary. Fallbacks are belt-and-suspenders. Not ship-critical; risk-reducers.
