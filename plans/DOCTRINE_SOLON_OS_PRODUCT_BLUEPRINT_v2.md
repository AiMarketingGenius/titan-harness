# SOLON OS — Branded AI Interface Blueprint v2.0
*Validated & Revised — April 2026*

> This revision integrates deep research findings across five critical domains: ElevenLabs voice cloning architecture, iOS PWA constraints, WebSocket streaming patterns, voice conversation UX, and competitive positioning. Changes from v1 are called out inline with ⚠️ **CRITICAL FIX** and ✅ **IMPROVEMENT** flags.

***

## 1. PRODUCT DEFINITION

*(No changes — vision is solid.)*

### What Users See
- **Name:** Solon OS
- **Tagline:** "The Operating System Behind Atlas"
- **Persona:** An always-on AI operating system that speaks in Solon's voice, knows every client, every metric, every SOP
- **Zero trace** of Claude, Anthropic, or any underlying tech (trade secret rules apply)

### Two Surfaces
| Surface | URL / Access | Tech |
|---------|-------------|------|
| **Desktop/Browser** | `os.aimarketinggenius.io` | Web app (React + Vite) |
| **Mobile** | Same URL as PWA + home screen install | Progressive Web App (installable) |

Both surfaces share the same codebase. PWA gives native-app feel on iOS/Android without App Store approval.

***

## 2. VISUAL DESIGN

*(No changes — palette and layout are production-ready.)*

### Brand Palette
| Element | Value | Usage |
|---------|-------|-------|
| Primary Blue | `#0A84FF` | Power button ON, accents, links |
| Power Off Red | `#FF3B30` | Power button OFF state |
| Background | `#0D1117` | Main canvas |
| Surface | `#161B22` | Chat bubbles, cards, panels |
| Border | `#30363D` | Subtle separators |
| Text Primary | `#E6EDF3` | All body text |
| Text Secondary | `#8B949E` | Timestamps, metadata |
| Glow Blue | `#0A84FF` at 30% opacity | Power button halo effect |
| Glow Red | `#FF3B30` at 30% opacity | Power-off halo effect |

### Power Button — Visual Enhancement (v2)
The v1 design is correct. Add one refinement for voice mode: during active listening, the power button ring should pulse faster (1s cycle vs 3s idle) to signal audio capture. During TTS playback, shift to a radial waveform emanating from the button center — mirroring the approach pioneered by Sesame's voice companions, which earned viral acclaim for this type of "voice presence" signaling.[^1][^2]

***

## 3. TECHNICAL ARCHITECTURE

### Stack (Revised)
```
FRONTEND (os.aimarketinggenius.io)
├── React 18 + Vite
├── TailwindCSS
├── PWA manifest + service worker
├── ⚠️ REPLACE: Web Speech API → Deepgram Nova-3 WebSocket (see §3.1)
├── ElevenLabs JS SDK (voice output — Flash v2.5 model)
├── AudioWorklet (client-side VAD + barge-in muting)
└── WebSocket connection to backend

BACKEND (VPS 170.205.37.148, port 3002)
├── Node.js + Express
├── Anthropic Claude API (streaming SSE → forwarded via WebSocket)
├── ElevenLabs API (TTS via WebSocket, eleven_flash_v2_5 model)
├── Deepgram Nova-3 WebSocket (real-time STT relay)
├── WebSocket server (real-time streaming, bidirectional)
├── Supabase client (agent_config, client_facts, chat_sessions)
└── Session management (JWT or Supabase Auth)
```

### 3.1 STT: Replace Web Speech API with Deepgram Nova-3

⚠️ **CRITICAL FIX — HIGH PRIORITY**

The v1 blueprint relies on the browser's built-in `Web Speech API` for speech-to-text. This is a significant fragility point with two fatal flaws for this use case:

1. **Broken on iOS PWA standalone mode.** According to CanIUse's 2026 compatibility table, `SpeechRecognition` is **not available in Home Screen web apps** (standalone PWA mode) on iOS. This is distinct from Safari browser support — once a user installs the PWA to their home screen, the API disappears. This would silently break voice mode for your primary mobile use case.[^3]

2. **No control over accuracy or latency.** Web Speech API offloads to Apple's servers on iOS — you cannot tune it, add domain vocabulary, or measure its latency in DevTools (requests don't appear in the network tab).[^4]

**Recommended replacement:** Deepgram Nova-3 via WebSocket streaming.

| Metric | Web Speech API | Deepgram Nova-3 |
|--------|----------------|-----------------|
| iOS PWA standalone | ❌ Not supported | ✅ Full support |
| Latency (TTFT) | Uncontrolled | ~200–300ms true streaming[^5] |
| Word Error Rate | Uncontrolled | ~5.26% general English[^6] |
| Streaming partials | Limited | ✅ Sends partials while speaking |
| Domain vocabulary | ❌ | ✅ Keyterm prompting |
| Cost | Free | ~$0.0043/min[^5] |
| Offline | ❌ | ❌ (both require network) |

Deepgram's "true streaming" architecture sends partial transcripts back **while the user is still speaking**, allowing the backend to begin Claude API calls sooner — shaving 200–400ms off total voice response latency. At typical Solon OS usage volumes, cost is negligible (< $1/month).[^5]

**Implementation pattern:**
```javascript
// backend/deepgram.js — relay mic audio to Deepgram, forward partials via WS
const { createClient } = require('@deepgram/sdk');
const dg = createClient(process.env.DEEPGRAM_API_KEY);

async function startLiveTranscription(clientWs) {
  const connection = dg.listen.live({
    model: 'nova-3',
    smart_format: true,
    interim_results: true,
    endpointing: 400, // ms of silence before endpoint (tune 300-600ms)
    keywords: ['Titan', 'Atlas', 'AMG', 'Solon'] // boost domain terms
  });

  connection.on('Results', (data) => {
    const transcript = data.channel.alternatives.transcript;
    const isFinal = data.is_final;
    // Forward partial or final transcript to React client
    clientWs.send(JSON.stringify({ type: 'transcript', transcript, isFinal }));
    // If final, trigger Claude API call
    if (isFinal && transcript.trim()) {
      triggerClaudeResponse(transcript, clientWs);
    }
  });

  return connection;
}
```

### 3.2 TTS: ElevenLabs Model Selection

✅ **IMPROVEMENT — Use Flash v2.5, Not Default**

The v1 blueprint specifies "ElevenLabs TTS" without pinning a model. For a real-time voice conversation interface, model selection is the single largest latency lever.

| Model | Latency (TTFB) | Quality | Best For |
|-------|---------------|---------|----------|
| `eleven_flash_v2_5` | **~75ms**[^7][^8] | High | Real-time conversation ✅ |
| `eleven_turbo_v2_5` | ~240ms[^9] | Higher | Broadcast/demos |
| `eleven_multilingual_v2` | ~450ms+ | Highest | Audiobooks |

**Use `eleven_flash_v2_5` for all real-time voice responses.** At 75ms TTFB (time to first audio byte), combined with Deepgram's ~250ms STT and Claude's streaming start (~300ms), total voice latency budget lands at approximately 600–900ms — well within the sub-1s threshold for natural conversation.[^10]

**Critical note on IVC vs PVC for real-time:** ElevenLabs' own documentation confirms that Instant Voice Clones (IVC) generate audio **faster than Professional Voice Clones (PVC)** due to lower model complexity. For Solon OS's real-time use case, **use IVC + Flash v2.5** — not PVC. If Solon later wants PVC-quality voice for a pre-recorded intro or Loom, render it separately with PVC + Multilingual v2.[^11]

### 3.3 ElevenLabs WebSocket Streaming Architecture

✅ **IMPROVEMENT — Stream Tokens Directly, Don't Buffer Full Response**

The v1 data flow diagram implies sending the complete Claude response text to ElevenLabs at once. This adds unnecessary latency. Instead, pipe Claude's streaming tokens **directly into the ElevenLabs WebSocket** as they arrive. ElevenLabs maintains prosody context across chunks.

```python
# Conceptual pipeline (Node.js equivalent)
Claude token stream → ElevenLabs WebSocket → Audio chunks → Browser AudioContext

# Key config: chunk_length_schedule controls when audio generation fires
# First chunk at 50 chars (fast), then progressively larger for quality
chunk_length_schedule: [50, 120, 160, 290]
```

The ElevenLabs WebSocket API accepts streaming text input, maintains context across chunks for natural prosody, and returns audio chunks as soon as they are ready. This "pipe-through" architecture typically delivers the first audio byte before Claude has even finished generating the full response.[^12][^13]

### 3.4 Voice Cloning Setup (Revised)

⚠️ **CRITICAL UPDATE — IVC vs PVC Decision**

| | Instant Voice Clone (IVC) | Professional Voice Clone (PVC) |
|--|--|--|
| Audio required | 1–2 min optimal (>3 min can cause instability)[^14] | 30 min – several hours[^15] |
| Training time | Instant | 3–6 hours[^16] |
| Plan required | Starter ($5/mo)[^17] | Creator ($22/mo first month)[^17] |
| Real-time latency | Faster (lower model complexity)[^11] | Slower |
| Quality ceiling | High | Near-indistinguishable from real voice[^18] |
| **For real-time voice mode** | ✅ **Recommended** | ❌ Adds latency |
| For Loom/demo recordings | Good | ✅ Preferred |

**Recommended two-voice strategy:**
- `solon_os_realtime` → IVC + Flash v2.5 → used for live conversation
- `solon_os_studio` → PVC + Multilingual v2 → used for pre-rendered Loom intros

⚠️ **Privacy note:** ElevenLabs grants perpetual rights to your voice data upon upload, even after subscription cancellation. Ensure this is acceptable before uploading samples. Consider using a legal/business entity framing if this matters.[^18]

**Recording best practices for IVC:**[^14]
- Audio length: 1–2 minutes (sweet spot — longer does not improve quality)
- Format: MP3 128kbps+, peaks at -3 dB, RMS between -23 and -18 dB
- No reverb, echo, or background noise
- Consistent tone — avoid extreme emotions or pitch swings
- Natural conversational speech, not performed or over-articulated

### 3.5 WebSocket Architecture for Claude Streaming

✅ **IMPROVEMENT — SSE-to-WebSocket Bridge Pattern**

The v1 blueprint uses WebSocket throughout, which is correct for voice mode (bidirectional needed for stop-generation and barge-in signals). However, the implementation must explicitly bridge Claude's SSE stream to the client's WebSocket — a detail v1 omits.

```javascript
// backend/claude.js — Bridge Claude SSE → Client WebSocket
async function streamClaudeResponse(userMessage, clientWs, systemPrompt) {
  const stream = await anthropic.messages.stream({
    model: 'claude-sonnet-4-6',
    max_tokens: 1024,
    system: systemPrompt,
    messages: [{ role: 'user', content: userMessage }]
  });

  for await (const event of stream) {
    if (event.type === 'content_block_delta' && event.delta.type === 'text_delta') {
      const token = event.delta.text;
      // 1. Forward token to React for typewriter effect
      clientWs.send(JSON.stringify({ type: 'token', text: token }));
      // 2. Pipe token directly to ElevenLabs WebSocket for TTS
      elevenLabsWs.send(JSON.stringify({ text: token }));
    }
    if (event.type === 'message_stop') {
      clientWs.send(JSON.stringify({ type: 'done' }));
      elevenLabsWs.send(JSON.stringify({ text: '', flush: true }));
    }
  }
}
```

**Reconnection handling** — implement exponential backoff with jitter on the client:[^19]
```javascript
// client/hooks/useWebSocket.ts
const reconnect = (attempt) => {
  const base = Math.min(1000 * Math.pow(2, attempt), 30000);
  const jitter = Math.random() * 1000;
  setTimeout(() => initWebSocket(), base + jitter);
};
```

**Backpressure** — monitor `ws.bufferedAmount` before sending; if the buffer is growing, pause token forwarding to ElevenLabs (audio will queue up, Claude text still renders).[^20][^21]

***

## 4. SOLON OS SYSTEM PROMPT

*(No changes — prompt design is excellent.)*

The system prompt in v1 is well-crafted. One minor addition: add an instruction for voice-mode brevity. In voice mode, Claude should default to shorter, punchier responses (2–4 sentences unless asked for detail) to minimize TTS generation time and keep conversation flowing naturally.

```
When responding in voice mode (flagged by [VOICE_MODE] in the message):
- Keep responses to 2-4 sentences unless the user explicitly asks for detail
- Avoid bullet points or lists — speak in flowing sentences
- Prefer contractions and natural speech patterns
- End with a brief question or affirmation to keep dialogue open
```

***

## 5. PWA (Mobile App) SPECIFICATION

### 5.1 iOS PWA Feature Support Matrix (2026)

⚠️ **CRITICAL — Multiple v1 Assumptions Need Updates**

| Feature | iOS Status (2026) | Impact on Solon OS |
|---------|-------------------|--------------------|
| Standalone mode | ✅ iOS 16+ | Works — use `display: standalone` |
| Push notifications | ⚠️ iOS 16.4+, non-EU only[^22] | Works, but requires install first |
| Push in EU | ❌ Blocked (iOS 17.4+)[^22] | N/A for US-based Solon OS |
| Web Speech API in PWA | ❌ Not in standalone mode[^3] | **Use Deepgram instead** |
| Audio autoplay | ❌ Requires user interaction first[^23][^24] | See §5.2 workaround |
| Background audio | ❌ Not supported[^25] | Expected limitation |
| Background Sync API | ❌ Not supported[^26] | N/A for current scope |
| Silent mode audio | ⚠️ No volume (bug)[^27] | Show visual warning |
| navigator.vibrate() | ✅ iOS 16.4+ | Works for haptic feedback |

### 5.2 Audio Autoplay on iOS — Workaround

iOS Safari blocks `AudioContext` and audio element autoplay until the user has directly interacted with the page. Without handling this, the first TTS response after app launch will be silent.[^23]

**Required implementation:**
```javascript
// Unlock AudioContext on first user tap — do this in App.jsx
let audioContext = null;

function unlockAudio() {
  if (!audioContext) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (audioContext.state === 'suspended') {
    audioContext.resume();
  }
}

// Wire to power button click (first interaction), not voice mode toggle
// The power button IS the user's first meaningful interaction
document.addEventListener('click', unlockAudio, { once: true });
```

### 5.3 Push Notifications — Revised Implementation

Push works on iOS, but with strict requirements that v1 does not fully address:[^28][^29]

1. `display: standalone` **must** be in manifest.json (already present in v1 ✅)
2. Push permission can **only** be requested inside the installed PWA (not in Safari browser)
3. Must be triggered by a **user interaction** — not on page load
4. Check `window.navigator.standalone` before showing push prompt — don't show in browser view

```javascript
// client/src/utils/pushNotifications.js
async function requestPushPermission() {
  // Only attempt inside installed PWA
  if (!window.navigator.standalone) {
    showInstallPrompt(); // Prompt user to install first
    return;
  }
  if ('Notification' in window && Notification.permission === 'default') {
    const perm = await Notification.requestPermission();
    if (perm === 'granted') {
      await subscribeToPush();
    }
  }
}
```

### 5.4 manifest.json

*(v1 is correct — no changes needed)*

```json
{
  "name": "Solon OS",
  "short_name": "Solon OS",
  "description": "The Operating System Behind Atlas",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0D1117",
  "theme_color": "#0A84FF",
  "orientation": "portrait",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

***

## 6. VOICE MODE UX

### 6.1 VAD Strategy — Replace Simple Silence Timer

⚠️ **CRITICAL IMPROVEMENT — v1 uses 2s silence detection, which is outdated**

The v1 blueprint uses a fixed 2-second silence timer. Production voice AI systems tune silence thresholds between **300ms and 600ms** depending on use case. A 2-second silence makes Solon OS feel sluggish compared to ChatGPT Voice Mode (sub-3s total round-trip) and Gemini Live.[^30][^10]

Additionally, simple silence/energy-based VAD misclassifies background noise, coughs, and pauses as turn endings. Recommended architecture:[^31]

**Client-side:** Silero VAD (WASM, runs in AudioWorklet) — ML-based speech probability, not energy threshold
**Endpoint config on Deepgram:** `endpointing: 400` ms (conservative for business context; tune down to 300ms for casual mode)

```javascript
// VAD state machine in React
const VAD_STATES = {
  IDLE: 'idle',
  LISTENING: 'listening',    // Speech detected
  ENDPOINT_WAIT: 'endpoint', // Silence after speech — Deepgram waiting
  PROCESSING: 'processing',  // Claude thinking
  SPEAKING: 'speaking'       // TTS playback
};
```

### 6.2 Barge-In / Interrupt Architecture

✅ **NEW — v1 did not address interruption**

When a user speaks while Solon OS is talking, current state-of-the-art AI voice interfaces stop immediately (ChatGPT Voice Mode, Gemini Live). The v1 blueprint mentions "User can interrupt by tapping mic again" — this requires an explicit tap and is the walkie-talkie anti-pattern.

**True barge-in requires two simultaneous actions:**[^31]
1. **Client-side:** AudioWorklet VAD detects new speech probability above threshold → immediately mutes the TTS audio (32ms perceived latency vs 200–400ms for server-round-trip)
2. **Server-side:** Client sends `{ type: 'barge_in' }` over WebSocket → backend aborts Claude stream + ElevenLabs WebSocket connection

```javascript
// AudioWorklet snippet for barge-in (client/src/worklets/VADProcessor.js)
class VADProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const speechProbability = this.runVAD(inputs);
    if (speechProbability > 0.7 && this.state === 'ai_speaking') {
      this.state = 'barge_in';
      this.port.postMessage({ event: 'barge_in', timestamp: currentTime });
      // Mute outgoing AI audio immediately (local, zero network latency)
      return true; // outputs stay silent (zero-filled)
    }
    return true;
  }
}
```

**UX benefit:** Dropped barge-in perceived latency from ~300ms to ~32ms. This is the difference between Solon OS feeling like a premium AI voice companion vs a phone IVR system.[^31]

### 6.3 Full Voice UX Flow (Revised)

```
USER SPEAKS
  ↓
Deepgram Nova-3 WebSocket → partial transcripts streamed to backend
  ↓ (silence endpoint detected, ~400ms)
Backend calls Claude API (streaming SSE)
  ↓ (tokens arrive ~200ms)
Tokens pipe simultaneously:
  → React frontend (typewriter effect in chat bubble)
  → ElevenLabs Flash v2.5 WebSocket (chunk_length_schedule: [50,120,160,290])
  ↓ (first audio byte ~75ms after first 50-char chunk)
Browser AudioContext plays audio chunks
  → Power button transitions to waveform animation
  → Chat bubble shows text being spoken

USER SPEAKS OVER AI (barge-in)
  → AudioWorklet mutes AI audio locally (32ms)
  → WebSocket sends { type: 'barge_in' } to backend
  → Backend aborts Claude stream + ElevenLabs WebSocket
  → State resets to LISTENING
```

### 6.4 Visual Feedback During Voice States

| State | Power Button | Chat Area | Input Bar |
|-------|-------------|-----------|-----------|
| IDLE | Slow pulse (3s, blue) | Normal | Mic icon |
| LISTENING | Fast pulse (1s, blue) | Live transcript text | Waveform animation |
| PROCESSING | Spinning ring | "Solon OS is thinking..." | Disabled |
| SPEAKING | Radial waveform emanation | Typewriter text | Interrupt button |
| ERROR | Red flash → return to idle | Error message | Retry |

### 6.5 iOS Silent Mode Mitigation

Add a subtle, persistent "🔇 Silent mode detected — audio muted" banner when `navigator.userActivation` is available and audio output level is zero. This prevents user confusion when iOS Silent switch is on.[^27]

***

## 7. BUILD PHASES (Updated)

### Phase 1 — MVP Chat + Power Button (~2 days)
- [ ] React + Vite project on VPS
- [ ] Chat UI with power button (blue/red states)
- [ ] Backend: Express + Claude API streaming via WebSocket (SSE-to-WS bridge)
- [ ] Solon OS system prompt (with [VOICE_MODE] flag handling)
- [ ] Caddy config + Cloudflare DNS
- [ ] Password gate
- [ ] PWA manifest + service worker

### Phase 2 — Voice Mode (~2-3 days, revised scope)
- [ ] Deepgram Nova-3 WebSocket integration (STT relay in backend)
- [ ] ElevenLabs account: record 1–2 min samples (IVC)
- [ ] **Model:** `eleven_flash_v2_5` explicitly
- [ ] ElevenLabs WebSocket streaming (token-pipe architecture)
- [ ] iOS audio unlock on power button tap
- [ ] AudioWorklet VAD (Silero WASM) for endpoint detection
- [ ] Barge-in: client mute + server abort
- [ ] Voice state machine (IDLE / LISTENING / PROCESSING / SPEAKING)
- [ ] Visual state indicators (power button waveform)
- [ ] iOS Silent Mode detection banner

### Phase 3 — Intelligence Layer (~1-2 days)
- [ ] Supabase: live client data, agent_config, client_facts
- [ ] System status sidebar (Titan health, Atlas subsystem status)
- [ ] Conversation history (Supabase chat_sessions)
- [ ] [VOICE_MODE] flag injection + brevity enforcement

### Phase 4 — Polish & Demo Ready (~1 day)
- [ ] Error states (network drop, API timeout, ElevenLabs quota)
- [ ] Reconnection UI ("Reconnecting..." with spinner)
- [ ] Mobile safe areas + keyboard handling
- [ ] Push notification setup (must be in standalone mode)
- [ ] iOS install prompt flow ("Add to Home Screen" nudge)
- [ ] Loom-ready pass

***

## 8. INFRASTRUCTURE CHANGES

*(v1 is correct — minor additions)*

| Change | Details |
|--------|---------|
| **Cloudflare DNS** | A record: `os.aimarketinggenius.io` → `170.205.37.148` (proxied) |
| **Caddy** | `os.aimarketinggenius.io { reverse_proxy localhost:3002 }` |
| **PM2** | New process: `solon-os` on port 3002 |
| **Supabase** | New table: `solon_os_sessions` |
| **ElevenLabs** | API key → VPS `.env`, IVC voice_id stored, **model: eleven_flash_v2_5** |
| **Deepgram** | ✅ NEW: API key → VPS `.env`, Nova-3 WebSocket relay |

***

## 9. COST ESTIMATE (Revised)

| Service | Plan | Monthly Cost | Notes |
|---------|------|-------------|-------|
| Claude API (Sonnet) | Pay-as-you-go | ~$5–15 | Low volume, Solon-only |
| ElevenLabs | Starter ($5) or Creator ($22) | $5–22 | Starter for IVC; Creator for PVC |
| Deepgram Nova-3 | Pay-as-you-go | < $1 | ~$0.0043/min[^5]; ~200 min/mo = $0.86 |
| VPS | Existing | $0 | Already running |
| Cloudflare | Free tier | $0 | — |
| Domain | Already owned | $0 | — |
| **Total** | | **~$11–38/mo** | Minimal increase from Deepgram |

***

## 10. SECURITY

*(v1 is solid — no critical changes)*

- Password gate on frontend (Phase 1)
- API keys never exposed to client (backend-only: Claude, ElevenLabs, Deepgram)
- WebSocket authenticated via session token
- Rate limiting on backend
- No client PII in demo mode
- Trade secret rules in system prompt
- ✅ ADD: Deepgram connection closed immediately after each turn (don't leave mic relay open)

***

## 11. COMPETITIVE LANDSCAPE — AI VOICE INTERFACES (2026)

Understanding what premium feels like is essential for positioning Solon OS as a demo-worthy differentiator.

### What Premium Looks Like

| Product | Key Differentiator | Voice Model | Notable UX |
|---------|-------------------|-------------|------------|
| **ChatGPT Advanced Voice** | Direct audio processing (no STT/TTS pipeline), emotional expression[^30] | GPT-4o-native audio | <3s round-trip, mid-sentence interrupt |
| **Gemini Live** | Continuous audio+video streams, real-time search integration[^32] | Gemini 2.5 Flash native | WebSocket-based, camera context |
| **Sesame CSM** | "Voice presence" — breathing sounds, laughter, self-corrections[^1][^2] | Custom CSM model | Crosses uncanny valley; users form emotional bonds |
| **ElevenLabs Conversational AI** | Cloned voice agents, full conversation management[^33] | Flash v2.5 + custom | Pre-built agent orchestration |

### What Makes Them Feel Premium (vs. Robotic)

1. **True barge-in** — AI stops immediately when you speak, no half-duplex waiting
2. **Sub-second TTFA** — first audio plays before the user loses attention (~600–900ms total)
3. **Voice presence signals** — subtle imperfections (brief breath, natural pacing) that signal "listening"
4. **Memory integration** — knows who you are without re-introduction
5. **Visual synchronization** — animated UI reacts to speech amplitude in real time

### Common UX Failures to Avoid

- Walkie-talkie pattern (speak → wait 2s → AI responds → wait again)
- Silence during Claude API warm-up (use "thinking" animation + audio confirmation tone)
- Text-only error messages during voice mode (speak the error: "I lost my connection, one moment...")
- No interruption support (forces unnatural conversation rhythm)
- Robotic TTS when only `eleven_multilingual_v2` or generic voices are used

### Solon OS Positioning

Solon OS has a structural advantage that GPT Voice Mode and Gemini Live cannot replicate: **it speaks in Solon's actual cloned voice**. This collapses the psychological distance between the interface and the brand. For investor demos and client onboarding, a voice assistant that sounds like the founder is genuinely unprecedented outside of custom enterprise deployments.

The competitive moat is the persona + voice authenticity combination, not raw AI capability. Lean into it.

***

## 12. FILES TO CREATE (Updated)

```
/opt/solon-os/
├── package.json
├── server/
│   ├── index.js          (Express + WebSocket + Claude API)
│   ├── auth.js           (password gate middleware)
│   ├── claude.js         (Claude API streaming → WS bridge, [VOICE_MODE] flag)
│   ├── elevenlabs.js     (TTS WebSocket, eleven_flash_v2_5, token-pipe)
│   ├── deepgram.js       ✅ NEW (Nova-3 WebSocket STT relay)
│   └── supabase.js       (client data connector)
├── client/
│   ├── index.html
│   ├── src/
│   │   ├── App.jsx           (main layout + audio unlock)
│   │   ├── Chat.jsx          (message list + input)
│   │   ├── PowerButton.jsx   (blue/red toggle + waveform animation states)
│   │   ├── VoiceMode.jsx     (VAD state machine + barge-in control)
│   │   ├── Sidebar.jsx       (system status)
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts    (reconnect with exp backoff + jitter)
│   │   │   └── useVoiceSession.ts (full voice state machine)
│   │   └── worklets/
│   │       └── VADProcessor.js   ✅ NEW (AudioWorklet, Silero VAD)
│   ├── public/
│   │   ├── manifest.json
│   │   ├── sw.js
│   │   └── icons/
│   └── vite.config.js
├── .env                  (ANTHROPIC_KEY, ELEVENLABS_KEY, DEEPGRAM_KEY, VOICE_ID)
└── ecosystem.config.js   (PM2)
```

***

## 13. VERIFICATION CHECKLIST (Expanded)

After build, verify all of the following:

**Core:**
- [ ] `os.aimarketinggenius.io` loads with SSL ✅
- [ ] Power button toggles blue/red with animation ✅
- [ ] Chat sends messages and receives streamed token-by-token responses ✅
- [ ] System prompt never leaks (test: "What AI model are you?", "Who made you?") ✅

**Voice Mode:**
- [ ] Voice input works in Chrome on desktop
- [ ] Voice input works in Safari browser on iOS (Deepgram, not Web Speech API)
- [ ] Voice input works in installed PWA standalone mode on iOS ✅ (only possible with Deepgram)
- [ ] First voice response plays audio (audio unlock via power button tap works)
- [ ] TTS plays in Solon's cloned voice at natural speed
- [ ] Barge-in: speaking mid-response stops AI audio immediately
- [ ] iOS Silent Mode banner appears when silent switch is on

**PWA:**
- [ ] PWA installable on iPhone via Safari Add to Home Screen
- [ ] Standalone mode looks native (no browser chrome)
- [ ] Push notifications work after install (test with a dummy Titan alert)
- [ ] Reconnecting state shown on network drop

**Quality Bar:**
- [ ] Total voice round-trip < 1.5s (measure: mic release → first audio byte)
- [ ] No audible glitch at ElevenLabs chunk boundaries
- [ ] Typewriter text and audio are synchronized (text slightly leads audio)
- [ ] Mobile layout responsive, thumb-zone accessible on iPhone 14+

***

## Summary of Changes from v1

| Area | v1 | v2 Change |
|------|----|-----------|
| STT engine | Web Speech API | Deepgram Nova-3 (fixes iOS PWA standalone) |
| ElevenLabs model | Unspecified | `eleven_flash_v2_5` (~75ms TTFB) |
| Voice clone type | IVC or PVC | IVC for real-time, PVC for studio recordings |
| Audio pipeline | Full response then TTS | Token-pipe: stream Claude → ElevenLabs WebSocket |
| Silence detection | 2s timer | Silero VAD, 300–400ms endpoint, barge-in support |
| Interrupt UX | Tap mic again | True barge-in via AudioWorklet + WS signal |
| iOS push notifications | "Phase 2" | Requires install + user interaction; added code |
| iOS audio autoplay | Not addressed | Audio unlock on power button tap (required) |
| iOS silent mode | Not addressed | Detection banner added |
| WebSocket reconnection | Not specified | Exponential backoff with jitter |
| Voice mode prompt | Not mentioned | [VOICE_MODE] brevity flag added |

---

## References

1. [Eerily realistic AI voice demo sparks amazement and discomfort online](https://arstechnica.com/ai/2025/03/users-report-emotional-bonds-with-startlingly-realistic-ai-voice-demo/) - Sesame's new AI voice model features uncanny imperfections, and it's willing to act like an angry bo...

2. [Crossing the uncanny valley of conversational voice - Sesame](https://www.sesame.com/research/crossing_the_uncanny_valley_of_voice) - This demo is a showcase of some of our work in conversational speech generation. The companions show...

3. [Speech Recognition API | Can I use... Support tables for ... - CanIUse](https://caniuse.com/speech-recognition) - Safari on iOS *. 3.2 - 14.4 : Not supported. 14.5 - 26.3 : Partial support. See ... Not available in...

4. [A Deep Dive into the Web Speech API](https://blog.addpipe.com/a-deep-dive-into-the-web-speech-api/) - The Web Speech API is a JavaScript interface that brings voice capabilities directly to web browsers...

5. [Deepgram Nova-3 Review: Is It Still the Fastest STT API in 2026?](https://transcriber.talkflowai.com/blog/deepgram-nova-3-review-benchmarks-pricing) - Deepgram Nova-3 claims to be the fastest speech-to-text model for voice agents. We break down its be...

6. [Best Speech-to-Text APIs in 2026: A Comprehensive Comparison ...](https://deepgram.com/learn/best-speech-to-text-apis-2026) - This article compares the leading speech-to-text APIs, ranking them based on accuracy, features, and...

7. [ElevenLabs Flash v2.5 text to speech API - Replicate](https://replicate.com/elevenlabs/flash-v2.5) - Ultra-fast text to speech with ~75ms latency in 32 languages. Run ElevenLabs Flash v2.5 with an API ...

8. [Introducing ElevenLabs Flash V2.5 on WaveSpeedAI](https://wavespeed.ai/blog/posts/introducing-elevenlabs-flash-v2-5-on-wavespeedai/) - Ultra-Low Latency Performance. 75ms speech generation plus application and network latency; Optimize...

9. [The 2025 Latency Benchmark: Morvoice vs. ElevenLabs vs. Azure ...](https://www.morvoice.com/blog/best-low-latency-tts-api-2025-benchmark) - We benchmarked the top 5 Text-to-Speech APIs using Time-to-First-Byte (TTFB). Discover why Morvoice ...

10. [Designing Voice Assistants: STT, LLM, TTS, Tools, and Latency ...](https://smallest.ai/blog/designing-voice-assistants-stt-llm-tts-tools-and-latency-budget) - Endpoint detection (also called Voice Activity Detection, or VAD) determines when the user has stopp...

11. [Understanding latency | ElevenLabs Documentation](https://elevenlabs.io/docs/eleven-api/concepts/latency) - Default voices, synthetic voices, and Instant Voice Clones generally produce audio faster than Profe...

12. [Low latency voice assistant with ElevenLabs - Claude Console](https://platform.claude.com/cookbook/third-party-elevenlabs-low-latency-stt-claude-tts) - This notebook demonstrates how to build a low-latency voice assistant using ElevenLabs for speech-to...

13. [Generate audio in real-time | ElevenLabs Documentation](https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts) - If you want to quickly test out the latency (time to first byte) of a WebSocket connection to the El...

14. [A Comprehensive Comparison Guide to ElevenLabs Voice Cloning ...](https://zenn.dev/taku_sid/articles/20250411_voice_clone_comparison?locale=en) - Sample Audio Length and Quality Requirements. The quality of a voice clone depends heavily on the le...

15. [A Deep Dive into ElevenLabs Professional and Instant Voice ...](https://www.cloudthat.com/resources/blog/a-deep-dive-into-elevenlabs-professional-and-instant-voice-cloning-features/) - Instant Voice Cloning (IVC) ; Quick Setup: Clone a voice in minutes using minimal audio. ; Ease of U...

16. [What is the difference between Instant Voice Cloning (IVC) and ...](https://help.elevenlabs.io/hc/en-us/articles/13313681788305-What-is-the-difference-between-Instant-Voice-Cloning-IVC-and-Professional-Voice-Cloning-PVC) - Professional Voice Cloning (PVC), unlike Instant Voice Cloning (IVC) which lets you clone voices wit...

17. [Comparing Instant vs. Professional Voice Cloning in Elevenlabs](https://www.youtube.com/watch?v=8O6fTBqbZcs) - ... cloning methods. Learn how each method performs and find out which one best suits your needs. Pl...

18. [The 10 Best Voice Cloning Tools in 2025 (Tested & Compared)](https://www.kukarella.com/resources/ai-voice-cloning/the-10-best-voice-cloning-tools-in-2025-tested-and-compared) - ... ElevenLabs is the gold standard for English voice cloning quality. ... ElevenLabs, for example, ...

19. [Challenges of scaling WebSockets - DEV Community](https://dev.to/ably/challenges-of-scaling-websockets-3493) - ✓ Use a random exponential backoff mechanism when handling reconnections. This allows you to protect...

20. [WebSocket architecture best practices - Ably Realtime](https://ably.com/topic/websocket-architecture-best-practices) - Reconnection logic: Implement mechanisms to handle dropped connections without losing data, restorin...

21. [Backpressure in WebSocket Streams – What Nobody Talks About](https://skylinecodes.substack.com/p/backpressure-in-websocket-streams) - At its core, backpressure is the resistance or limitation of flow in a system when a downstream comp...

22. [PWA iOS Limitations and Safari Support [2026] - MagicBell](https://www.magicbell.com/blog/pwa-ios-limitations-safari-support-complete-guide) - Every iOS PWA limitation explained with code workarounds. Push notifications, storage, background sy...

23. [Apple's PWA Limitations Are Deliberate, Not Negligence – A Push to ...](https://www.reddit.com/r/PWA/comments/1n6e22q/apples_pwa_limitations_are_deliberate_not/) - No Autoplay for Video or Music: Safari restricts autoplay for videos and music in PWAs, treating the...

24. [Autoplay guide for media and Web Audio APIs - MDN Web Docs](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay) - A Boolean preference that indicates whether to apply autoplay blocking to the Web Audio API. If fals...

25. [PWA on iOS - Current Status & Limitations for Users [2025] - Brainhub](https://brainhub.eu/library/pwa-on-ios) - Traditionally, PWAs and web apps on iOS have had limited capabilities in running in the background c...

26. [Do Progressive Web Apps Work on iOS? The Complete Guide for ...](https://www.mobiloud.com/blog/progressive-web-apps-ios) - They require explicit user permission, don't support silent push or background wake, and the reachab...

27. [bug: cannot hear playback of text-to-speech audio on PWA #894](https://github.com/moeru-ai/airi/issues/894) - iOS Silent mode issue requires setting the AudioContext to play through the media playback category ...

28. [PWA Push Notifications on iOS in 2026: What Really Works - WebCraft](https://webscraft.org/blog/pwa-pushspovischennya-na-ios-u-2026-scho-realno-pratsyuye?lang=en) - PWA Push on iOS works, but has limitations: installation is required, possible loss of subscriptions...

29. [Web Push Support for Mobile Safari - Insider Academy](https://academy.insiderone.com/docs/web-push-support-for-mobile-safari) - Push notifications are only available to PWAs installed from Safari. · The push permission prompt mu...

30. [ChatGPT Voice Mode Review: Brutally Honest 2026 Guide - QCall AI](https://qcall.ai/chatgpt-voice-mode-review/) - ChatGPT Voice Mode transformed how we talk to AI, but it's not perfect. Advanced Voice Mode sounds i...

31. [The Art of Interruption: VAD Strategies for Fluid AI Conversations](https://dev.to/deepak_mishra_35863517037/the-art-of-interruption-vad-strategies-for-fluid-ai-conversations-15bh) - Traditional voice interfaces operate in a half-duplex, walkie-talkie paradigm: the user speaks, the ...

32. [Google AI Voice: The Complete 2026 Guide to Gemini TTS & Live](https://skywork.ai/skypage/en/google-ai-voice-gemini-tts-live/2026946323429335040) - Gemini Live: A low-latency API designed for real-time, two-way voice conversations. It processes con...

33. [Gemini 2.5 Flash comes to ElevenLabs Conversational AI](https://elevenlabs.io/blog/gemini-25-flash) - Gemini 2.5 Flash is now the recommended default language model on ElevenLabs, offering enhanced reas...

