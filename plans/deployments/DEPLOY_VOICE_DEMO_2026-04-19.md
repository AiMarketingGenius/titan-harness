# aimg-voice-demo Deploy Handoff (CT-0419-05 Lane D)

**Built:** 2026-04-19 by Titan under Lumina v2 execution authority
**Lumina self-approval:** ~/.lumina-approvals/2026-04-19_aimg-voice-demo_636970852.yaml (9.45 overall)
**Target domain:** voice.aimarketinggenius.io
**Deadline:** Monday 2026-04-20 09:00 ET (2hr buffer to 11am Revere pitch)

## What this is

A standalone single-page voice demo. Hold the orb to speak, release to hear Alex reply. 5-turn conversation memory. Real backend pipeline — NOT a mock.

## Pipeline (front to back)

```
[User browser]
  ↓ press-and-hold orb → MediaRecorder captures audio (webm/opus)
  ↓ POST audio blob to
[atlas-api /api/titan/voice-in]  (Whisper transcription)
  ↓ JSON transcript response
[User browser]
  ↓ POST transcript to
[atlas-api /api/titan/message]  (session memory + LLM reply)
  ↓ JSON reply response
[User browser]
  ↓ GET /api/titan/tts?voice=alex&text=<reply>
[atlas-api /api/titan/tts]  (premium TTS → audio/mpeg stream)
  ↓ audio stream
[User browser]
  ↓ HTML5 <audio> element plays
[User can press orb to interrupt — client-side barge-in]
```

## Backend dependencies (already live in lib/atlas_api.py)

All three endpoints exist and are production-live on atlas-api (port 8081 on the primary VPS):

- **POST /api/titan/voice-in** — multipart `audio` field, returns `{transcript, session_id}`. Rate-limited 10/min per IP. Requires `OPENAI_API_KEY` for Whisper transcription.
- **POST /api/titan/message** — JSON `{text, session_id}` → `{reply, session_id}`. Session memory via in-process `_TITAN_SESSIONS` dict (persists across requests for up to session-TTL).
- **GET /api/titan/tts?voice=alex&text=…** — returns `audio/mpeg` stream. Rate-limited 30/min per IP + daily cost cap (env `ELEVENLABS_DAILY_CAP_USD`, default $10 per Sunday runway commit 3eeeb73). HTTP 429 on cap hit. Default voice: `alex` (the canonical Solon-OS-clone voice per the locked voice map).

No backend changes required. All Lane D functionality is client-side glue over the existing endpoint surface.

## Cost model (per 60-second conversation)

Estimated per-turn cost:
- Whisper: ~$0.006 / minute → ~$0.003 / 30s turn
- LLM reply (lightweight model behind atlas-api): ~$0.004 / turn (200 tokens out)
- Premium TTS (Turbo tier): ~$0.30 / 1K chars → ~$0.08 / 250-char reply

~$0.09 / turn. Cost cap at $10/day ≈ ~110 turns / day cap. For a live Don-demo pitch this is far more than enough.

## Deploy steps (VPS Caddy — preferred)

The backend is already on the VPS (170.205.37.148, port 8081). Simplest deploy is to serve this static HTML from the same VPS behind a subdomain.

1. **DNS** — Solon adds CNAME or A-record in Cloudflare: `voice.aimarketinggenius.io` → primary VPS. Titan's CF token does NOT control this zone; Solon-side.
2. **VPS file copy:**
   ```bash
   ssh root@170.205.37.148 'mkdir -p /opt/aimg-voice-demo'
   scp deploy/aimg-voice-demo/index.html root@170.205.37.148:/opt/aimg-voice-demo/
   ```
3. **Caddy config** — append to `/etc/caddy/Caddyfile`:
   ```
   voice.aimarketinggenius.io {
     encode gzip zstd
     root * /opt/aimg-voice-demo
     file_server
     header Cache-Control "public, max-age=300"
     header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; connect-src 'self' https://atlas.aimarketinggenius.io; media-src https://atlas.aimarketinggenius.io; img-src 'self' data:"
     log {
       output file /var/log/caddy/voice.aimarketinggenius.io.log
     }
   }
   ```
4. **Reload Caddy:** `systemctl reload caddy`. Let's Encrypt auto-provisions TLS cert (~30s after DNS resolves).
5. **Verify:** `curl -sSI https://voice.aimarketinggenius.io/` → HTTP/2 200; browser load → orb appears; press-and-hold triggers permission prompt; release → transcript appears.

## Deploy steps (Vercel — alternate)

1. Create Vercel project pointing at `deploy/aimg-voice-demo/` directory in the harness repo
2. Set custom domain `voice.aimarketinggenius.io`
3. Add Vercel environment override if needed: the page reads `window.AMG_API_BASE` (defaults to `https://atlas.aimarketinggenius.io`); Vercel doesn't inject this, so page uses the default — which is correct.
4. Verify as above.

## Browser permissions required

- **Microphone** — granted on first orb press. If denied, page shows "Mic permission required" error + instructions.
- **Autoplay audio** — first audio playback may be blocked by browser autoplay policy if no user gesture preceded it. The page triggers audio after a user gesture (orb press → release → AI reply), so this is not normally an issue. If blocked, status pill shows "Voice blocked (tap orb once to unlock)".

## Don-demo flow (Monday 2026-04-20 11am ET)

**Beat 3: MOBILE CMD POCKET DEMO (1 min)** per Sunday playbook §"DEMO FLOW v3".

Show Don the voice orb on Solon's phone or tablet. Hold orb, ask:
- "Alex, what does the Atlas Metro tier include?"
- "Can you walk me through how the Chamber program works?"
- "What's the guarantee you're offering?"

Alex replies with brand voice per the _titan_system_prompt. First audio ~1-2s post-release (Whisper + LLM + ElevenLabs round trip). Don sees: the AI actually talks, actually knows the business, responds in real time.

If live-demo hiccups mid-pitch, fall back to the 90sec Lane D fallback video (documented in the Step 3 plan).

## Verification checklist (post-deploy)

- [ ] `curl -sSI https://voice.aimarketinggenius.io/` returns HTTP/2 200
- [ ] Page load: orb appears + "LIVE VOICE DEMO" kicker pulses + "Press and hold to talk" label
- [ ] Mic permission prompt fires on first orb press (browser standard)
- [ ] Release triggers transcription → "Alex is thinking" → voice reply plays
- [ ] Tap orb during playback: audio stops immediately (barge-in)
- [ ] 5 turns in a row: session memory works (reply references prior turn)
- [ ] Download transcript button produces valid .txt
- [ ] Mobile (iOS Safari + Android Chrome): orb works, audio plays, no layout break
- [ ] Cost cap test: not force-triggerable for the demo; verified at endpoint level via tests/test_tts_cost_kill_switch.py (4/4 PASS, Sunday runway)

## Known limitations

- **First-audio latency**: 1-2 seconds, not <500ms. True <500ms requires WebRTC streaming audio pipeline (vs current HTTP request/response model). That's 2-3 days of backend work; deferred.
- **No WebRTC VAD barge-in**: the client-side barge-in works via "user presses orb to interrupt" — honest and functional, but not continuous-voice-always-on interruption. The VAD fanciness is a future polish.
- **No session-lookback beyond backend `_TITAN_SESSIONS` window**: server-side history is in-memory; a worker restart clears it. For production a Redis-backed session store is the upgrade path. For the Don-demo this is fine.
- **Cost cap $10/day default**: can be raised via env `ELEVENLABS_DAILY_CAP_USD=X` per commit 3eeeb73 if Solon wants a longer demo budget.

## Embed option (for aimg.io + aimemoryguard.com)

The Lane B + Lane C pages have a "Talk to our AI now" button pointing at `voice.aimarketinggenius.io`. Once this page is live at that URL, the 3-birds convergence is complete:

- aimarketinggenius.io/#voice-cta → opens voice.aimarketinggenius.io in new tab
- aimemoryguard.com visitors → chatbot widget embed references voice subdomain
- Standalone voice page → links back to aimarketinggenius.io

Alternative: iframe the voice demo into the main sites. Not recommended for this sprint — cross-origin audio playback restrictions + iframe UX cost more than the "open in new tab" approach.

## Rollback

Pure static HTML, zero state. Rollback = remove the Caddy block (or Vercel deployment) and restart. No data loss.
