# CT-0417-24 — Voice Pipeline Spec (VPS-deploy ready)

**Date:** 2026-04-17
**Scope:** end-to-end streaming voice for Alex (public widget) + Atlas (Chamber portal Revere demo). Same backend brain + different voice identities + different surface.
**Targets:** <800ms perceived latency to first audio chunk · streaming word-by-word TTS · interruption handling · cost kill-switches · trade-secret clean.
**CT cross-ref:** CT-0417-34 (Voice Orb broken on Revere demo P0) + CT-0417-17 (Alex widget staged).

---

## 1. Pipeline (streaming architecture)

```
[browser mic stream] → WebSocket → atlas-api voice router → STT streaming → LLM streaming → TTS streaming → [browser audio stream]
```

Components:

- **STT:** Deepgram streaming (primary) OR Whisper streaming (fallback). Partial transcripts stream to LLM as they become stable (~250-500ms audio chunks).
- **LLM:** Haiku-tier (fast first response, ~300-500ms TTFT for most queries) + Sonnet handoff on complex queries (classifier decides per query).
- **TTS:** ElevenLabs Flash v2.5 (fastest model, ~150ms TTFT). Streams word-by-word as LLM generates, not batched. Interruption detection pauses TTS immediately.

## 2. Voice identities (Solon approves IDs per surface)

| Surface | Voice name | ElevenLabs voice ID | Tier | Notes |
|---|---|---|---|---|
| aimarketinggenius.io public widget | Alex | [TO SELECT — "warm male US English" per Addendum #1 L.4 + Solon's pre-set decision] | standard | default friendly conversational |
| portal.aimarketinggenius.io/revere-demo + /revere | Atlas | [TO SELECT from ElevenLabs gallery] | standard | Chamber-facing, more authoritative |

Solon picks exact voice IDs from ElevenLabs gallery + logs decision via MCP before go-live.

## 3. Latency budget (must hit on every session)

| Stage | Budget | Measurement |
|---|---|---|
| Browser mic → WS packet arrival | ≤50ms | network RTT |
| WS → STT partial transcript | ≤400ms | first stable partial |
| STT → LLM TTFT | ≤400ms | Haiku on cache-warm prompt |
| LLM → TTS first audio chunk | ≤200ms | ElevenLabs Flash v2.5 |
| TTS → browser playback | ≤100ms | WS ship + audio queue |
| **TOTAL to first perceived audio** | **≤1150ms raw** | target <800ms perceived |

Optimizations to hit <800ms perceived:
- Pre-warm LLM with system prompt + persona on session open (connection-time cache)
- Speculative STT → LLM call on high-confidence partial transcripts (cancel on revision)
- Streaming TTS starts on first 3-5 LLM tokens
- Persistent WebSocket connection (no per-utterance handshake)
- Haiku cache prefix with full Alex system prompt (Anthropic prompt caching)

## 4. Interruption handling

- Voice Activity Detection (VAD) on browser mic streams detects user-speaking events.
- When user starts speaking during Alex TTS playback:
  1. Immediately pause TTS audio queue (browser)
  2. Cancel in-flight TTS synthesis (server, abort signal to ElevenLabs)
  3. Cancel in-flight LLM generation (server, abort signal to LLM)
  4. Start new STT stream for the interrupting utterance
  5. When new utterance completes, LLM generates new response

## 5. Cost kill-switches (HARD limits)

| Cost center | Monthly cap | 75% alert | 100% action |
|---|---|---|---|
| ElevenLabs Flash v2.5 | $300 | Slack #solon-command | auto-disable voice; widget shows "Voice temporarily unavailable — text chat available" |
| Claude API (Alex Haiku + Sonnet handoff) | $200 | Slack #solon-command | graceful degradation (Haiku-only, no Sonnet) until 100% → full widget disable |
| Deepgram STT | $100 | Slack | auto-disable voice, keep text chat |

All caps enforced via `lib/cost_kill_switch.py` sqlite ledger + per-session dry-run cost estimation.

## 6. Rate limits (per IP + per session)

- 3 voice sessions per IP per hour
- 15 minute OR 40 exchanges per session (whichever first)
- Max concurrent voice sessions across entire atlas-api: 10 (scales with VPS capacity)
- On limit hit: graceful "I'm going to pause here for now — drop your email and I'll make sure Solon picks up where we left off" + end session

## 7. Trade-secret discipline

- Same extended scrub list from `CT-0417-24_CORRECTIONS_LOG.md §7` applies to Alex + Atlas voice outputs.
- Runtime output filter runs on LLM text BEFORE TTS synthesis — if banned term detected, re-query LLM with "DO NOT mention X" constraint. Prevents voice from speaking the banned term.
- Voice identity names (Alex, Atlas) are AMG brand — no issue.
- Never say "I'm running on Claude" or "ElevenLabs" or "Deepgram" — all banned.

## 8. Widget integration (aimarketinggenius.io)

- Existing Alex widget at `deploy/amg-chatbot-widget/widget.js` adds voice orb layer
- Floating orb FAB bottom-right, navy background pulse animation (use AMG brand tokens — correct existing navy+gold to blue+green per Addendum #5, see §9 below)
- Two modes: text chat (existing) + voice (new)
- Tap-and-hold to speak, release to send (or toggle-to-talk — pick per UX testing)
- Visual states: idle (gentle pulse at #00A6FF), listening (active cyan ring), processing (spinner), speaking (animated audio wave #10B77F)
- Keyboard accessible + screen-reader labels
- Graceful fallback: voice pipeline unavailable → widget shows text-only mode with subtle "Voice temporarily unavailable" note

## 9. Widget rebrand (Addendum #5 requirement)

Current `deploy/amg-chatbot-widget/widget.js` hardcodes Revere navy+gold+Montserrat. Must update to AMG live-site tokens:

| Current (WRONG) | Replace with (AMG) |
|---|---|
| `#0B2572` navy | `#131825` dark navy |
| `#1a3a94` secondary navy | `#1A2033` card/secondary |
| `#d4a627` gold (FAB icon + focus outline) | `#10B77F` bright green (FAB icon + focus outline) OR `#00A6FF` cyan (if green clashes with voice wave) |
| `#fbf9f3` cream message area bg | `#0F172A` slate alternate OR `#131825` |
| `'Montserrat'` font | `"DM Sans"` font |
| navy linear-gradient header | navy-to-slate gradient `linear-gradient(135deg, #131825 0%, #0F172A 100%)` |

Pending decision: should FAB icon + focus outline use green `#10B77F` (matches CTA CTAs) or cyan `#00A6FF` (matches nav)? Default: cyan `#00A6FF` for focus ring, green `#10B77F` reserved for active-speaking wave animation.

## 10. Pitch-day risk mitigation (Monday 11am ET Revere pitch)

Since voice is the highest new-build risk:

1. **Sat PM:** Titan ships voice pipeline (STT + LLM + TTS wired end-to-end on staging)
2. **Sun AM:** Solon conducts 20 full dry-run conversations (each <2min), documents any failures
3. **Sun PM:** Solon records a 2-min backup demo video showing voice orb working smoothly on /revere-demo — stored as pitch fallback if live voice fails
4. **Monday AM:** Full walk-through test with Solon's actual meeting audio setup
5. **Go/no-go gate (Sun 6pm):** If voice unreliable across ≥3 test runs → ship text-only widget + disable voice, pitch proceeds with backup video. Pitch outcome does NOT depend on live voice working.

## 11. Deployment checklist (VPS)

- [ ] atlas-api voice router WebSocket endpoint `/api/voice/stream` live
- [ ] Deepgram API key stored at `/etc/amg/deepgram.env` 0600 root
- [ ] ElevenLabs API key stored at `/etc/amg/elevenlabs.env` 0600 root (already exists per prior deploys)
- [ ] Voice ID for Alex + Atlas confirmed in `/etc/amg/voice-identities.env`
- [ ] Cost kill-switches active ($300 EL + $200 Claude + $100 Deepgram caps)
- [ ] Rate limit middleware on voice endpoint
- [ ] Output filter with full extended scrub list
- [ ] Widget rebrand shipped (§9)
- [ ] Widget script deployed at `https://widgets.aimarketinggenius.io/alex-voice/v1.js`
- [ ] Integration test: widget loads on staging aimarketinggenius.io mirror + voice session completes successfully <800ms to first audio
- [ ] Adversarial test: 10 prompts trying to extract vendor names → 10/10 clean voice responses
- [ ] Solon dry-run approved (20 conversations)
- [ ] Backup demo video recorded + stored in both iCloud + Drive

## 12. Revere portal voice (CT-0417-34 cross-task)

Atlas voice orb on portal.aimarketinggenius.io/revere-demo + /revere uses this same pipeline with:
- Atlas voice ID (different from Alex)
- Same STT + LLM backend
- Same cost kill-switches (shared caps across surfaces)
- Same output filter
- Surface context `data-amg-widget-context="revere-portal"` so LLM tunes greeting accordingly

Both surfaces proven working = Monday pitch ready.

---

**End of spec. Sat PM build target. Sun PM go/no-go. Solon always has text-only fallback + backup demo video.**
