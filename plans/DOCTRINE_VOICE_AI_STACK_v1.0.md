# Titan Voice AI Stack — Doctrine v1.0
### English-First, Phone-Call Quality, Self-Hosted Core
*Owner: Titan / ADS · Last validated: April 2026 · Status: Doctrine-grade*

---

## 2026 Updates vs. Original Draft (v0.9 → v1.0 Delta)

The following claims in v0.9 were updated or corrected based on April 2026 re-validation:

| # | Original Claim | Updated Finding | Impact |
|---|----------------|-----------------|--------|
| 1 | Kokoro real-time factor: "210× on RTX 4090, 90× on 3090, 36× on T4" | **Confirmed accurate.** Multiple independent benchmarks in 2026 replicate these numbers. One Mac M-series test shows avg RTF 0.44 (2.3× real-time on MPS), consistent with the model's profile. | No change |
| 2 | Chatterbox "runs at 6× real-time on GPU" | **Partially correct but incomplete.** Chatterbox (500M base) runs at ~6× RTF on RTX 4090. Chatterbox-Turbo (350M, distilled) was released in Jan 2026 with **sub-200ms latency**, ~6× RTF, same MIT license — this is now the production-grade version. The 500M original is the quality reference; Turbo is the deployment target. | Recommend Chatterbox-Turbo for production |
| 3 | Deepgram Nova-3 pricing: "$0.0077/min PAYG or $0.0065/min Growth" | **Confirmed for streaming.** However, pre-recorded/batch is $0.0043/min PAYG — notably cheaper if you're post-processing recordings. The draft correctly uses $0.0077 for real-time streaming (the relevant case for phone calls). New model: **Deepgram Flux** (Jan 2026) adds integrated end-of-turn detection via acoustic + semantic cues at 250ms EOT latency, reducing false positive start-of-turn by 70%. This is a material upgrade for VAD strategy. | Add Flux to STT recommendations |
| 4 | Deepgram WER cited as "12.8% on AISHELL" | **Outdated and misleading.** AISHELL is a Mandarin benchmark; irrelevant for English-first stack. Nova-3 achieves **5.26% WER on general English** (Deepgram internal, batch), **~18.3% WER on Artificial Analysis** (stricter third-party evaluation), **2.2% WER** on LibriSpeech clean (CodeSOTA leaderboard). Real-world noisy call center audio is ~15–25% WER for all providers. | Correct the WER claim |
| 5 | ElevenLabs Flash v2.5 real-world TTFB: "532–906ms" | **Partially updated.** The draft's 532–906ms figure referenced real-world tests including network. Current independent benchmarks cite Flash v2.5 at **~150ms TTFA P90** under normal conditions (not 532ms median). The 532–906ms range likely reflects old API congestion or non-streaming conditions. Corrected range: **~75ms model inference, ~150–300ms real-world P90 TTFA**. Still slower than Cartesia or self-hosted Kokoro. | Moderate update — changes fallback calculus |
| 6 | ElevenLabs Flash pricing: "$0.05–0.06 per 1,000 chars" | **Confirmed at $0.06/1k chars** (API pay-as-you-go on Business tier). Starter plan ($5/mo) gives 30k chars included; Creator ($22/mo) gives 100k. Overage on Starter not publicly listed for per-char; Flash quota is ~2× the Multilingual v2 quota per plan dollar. | No material change |
| 7 | Cartesia Sonic 3 TTFA: "90ms, Turbo: 40ms" | **Confirmed.** Cartesia's own page and independent benchmarks confirm Sonic 3 = 90ms TTFA, Sonic Turbo = 40ms TTFA. However, one independent streaming benchmark found Cartesia Sonic Turbo's TTFB to be **3× slower than ElevenLabs Flash** under load — the 40ms figure is model inference only, not end-to-end with network overhead. Real production P90 is closer to 130–150ms. Cartesia pricing is now public: Pro plan = **$5/month, 100k credits, 1 credit per character**. | Material — Cartesia's real-world advantage is smaller than its advertised spec |
| 8 | faster-whisper "WER of ~10.6% vs Deepgram 12.8%" | **Both numbers were on the wrong benchmark (AISHELL/non-English).** On LibriSpeech clean, faster-whisper large-v3-turbo achieves **1.9–7.8% WER** depending on test conditions. On mixed real-world benchmarks it's ~7.75%. Deepgram Nova-3 achieves 5.26% batch WER on English. The cost differential remains accurate: faster-whisper self-hosted is ~38× cheaper than Deepgram PAYG. | Correct WER citation; conclusion unchanged |
| 9 | No mention of Deepgram Flux, Qwen3-TTS, CosyVoice 2, or Inworld TTS | **New contenders emerged since v0.9** that must be evaluated. See Section (a) and (b) updates. | Adds new material |
| 10 | Telnyx LiveKit beta: "no session fees" | **Confirmed as of April 6, 2026.** Session fees ($0.01/min that LiveKit Cloud charges) are waived during beta. STT/TTS costs are 50% lower than LiveKit Cloud equivalents. GPU-colocated inference delivers sub-200ms RTT. This is not time-limited by a hard date yet — "beta" pricing is the current production offering. | Confirmed; no change to recommendation |

---

## Executive Summary

- **Self-hosted TTS is now production-grade.** Kokoro v1.0 (conversation voice, preset) and Chatterbox-Turbo (voice cloning) deliver quality that beats ElevenLabs in blind tests at near-zero marginal cost on your existing GPU VPS.
- **Deepgram Flux is the new recommended STT for phone calls.** It replaces pure Nova-3 + Silero VAD for end-of-turn detection with a single model that handles acoustic + semantic turn detection at 250ms EOT latency, cutting false interruptions by 70%.
- **For phone calls, Silero VAD is still required alongside Flux for barge-in** — Flux handles turn completion; Silero handles the real-time interruption signal during TTS playback.
- **Telnyx LiveKit-on-Telnyx (launched April 2026) eliminates the most expensive layer** of the phone stack — no $0.01/min session fees during beta, 50% cheaper STT/TTS than LiveKit Cloud, and sub-200ms RTT built in.
- **ElevenLabs remains a valid fallback, not a primary.** At ~$0.06/1k chars PAYG for Flash, it's 6× more expensive per character than Inworld TTS ($0.01/1M chars) and 60× more than Kokoro self-hosted. Keep a Starter plan ($5/mo) strictly for language coverage gaps and high-stakes demos.
- **New contender: Qwen3-TTS** (Apache 2.0, 0.6B–1.7B, 97ms streaming latency) is now a strong alternative to Kokoro for multilingual use cases and zero-shot voice cloning — worth evaluating as a Chatterbox replacement if voice cloning quality matters more than speed.
- **Inworld TTS-1.5** (#1 on Artificial Analysis ELO 1,236) is the best paid TTS if you want API simplicity without self-hosting, at $10/1M chars — far cheaper than ElevenLabs at comparable or superior quality.
- **Do not build production services on XTTS-v2.** Coqui has shut down. The hallucination problem is real and unresolved. This is a red-line decision.
- **Total added monthly cost at ~5,000 call-minutes and moderate app usage: ~$28–38/month**, versus $500–2,000/month for an equivalent fully-managed stack.
- **The two-phase build is the right approach**: Phase A (orb/desktop/demo) is entirely self-hosted. Phase B (phone calls) uses Telnyx + LiveKit-on-Telnyx + Deepgram Flux/Nova-3 + Kokoro self-hosted for TTS.
- **Chatterbox-Turbo, not full Chatterbox 500M, is the deployment target.** The 350M distilled model delivers sub-200ms latency with comparable voice quality.
- **One engineering risk to plan for:** streaming TTS under concurrent load degrades to 800ms+ at 100 concurrent streams. At solo/agency scale (under 20 concurrent), GPU-VPS Kokoro is stable. Monitor GPU utilization as call volume grows.

---

## Component-by-Component Analysis

### (a) TTS: Full Doctrine

#### ❌ AVOID: XTTS-v2
**Red line decision.** Coqui shut down — no updates, no maintenance. Documented hallucination bug inserts nonsense words mid-utterance. Community rates quality as "inconsistent" even with parameter tuning. Do not build production services on XTTS-v2. This is permanent.

#### ❌ AVOID for production: Piper
Edge-device model (Raspberry Pi class). Quality is well below phone-call standard. Skip unless deploying to a low-power ARM device with no GPU available.

#### ✅ RECOMMENDED NOW — Kokoro v1.0 (Conversation Voice)
- **Params:** 82M | **License:** Apache 2.0 | **VRAM:** 2–3 GB
- **Speed:** 210× real-time on RTX 4090, 90× on 3090, 36× on T4
- **Latency:** ~100ms TTFB on GPU VPS (validated production)
- **Voice cloning:** No — 54 preset voices, 8 languages (EN, ES, FR, JA, ZH, HI, PT, KO)
- **Deploy:** OpenAI-compatible FastAPI endpoint, Docker image available
- **Why it wins:** Audio is generated 90–210× faster than it will be spoken, so the first audio chunk is available in ~100ms — fast enough for both web orb and phone call contexts. Zero marginal cost on existing GPU. MIT-compatible license for commercial use.
- **Fall back to Inworld or ElevenLabs if:** you need a language Kokoro doesn't support, or if preset voices don't match your brand requirements.

#### ✅ RECOMMENDED NOW — Chatterbox-Turbo (Voice Cloning)
- **Params:** 350M | **License:** MIT | **VRAM:** ~4 GB
- **Speed:** ~6× real-time on GPU | **Latency:** sub-200ms sustained
- **Voice cloning:** Yes — zero-shot from 3–5 seconds of reference audio
- **Blind test:** 63.75% preference over ElevenLabs (Podonos benchmark, validated)
- **Emotion control:** Built-in paralinguistic tags `[laugh]`, `[cough]`, `[chuckle]`
- **Why it wins:** Best open-source voice clone quality available. Turbo variant (distilled from 500M → 350M with one-step decoder) is the production deployment target. If you want Titan to have *your* voice, Chatterbox-Turbo is how.
- **Known gotcha:** Occasional low-level end-of-sentence noise on some voice clips. Acceptable for most use cases; not for studio-quality narration.
- **Fall back to ElevenLabs if:** You need a professional voice clone that must match a specific real person exactly for client-facing commercial work.

#### ✅ RECOMMENDED NOW — StyleTTS2 (English Maximum Quality)
- **Params:** ~200M | **License:** MIT | **VRAM:** ~4 GB
- **Speed:** 95× real-time on RTX 4090
- **Voice cloning:** Fine-tuning required (not zero-shot)
- **Languages:** English only — hard limit
- **Why it's still relevant:** Highest benchmark quality for English-only applications. Rated at or above ElevenLabs Multilingual v2 for English speech quality. If you're building a premium English-only voiceover pipeline (Solon Z demos, marketing audio), StyleTTS2 is worth maintaining alongside Kokoro.
- **Fall back to Kokoro:** For all real-time applications where ~100ms latency matters more than peak quality.

#### 🆕 WORTH EVALUATING — Qwen3-TTS (Apache 2.0, Alibaba)
- **Params:** 0.6B–1.7B | **License:** Apache 2.0 | **VRAM:** 3–6 GB
- **First-packet latency:** 97ms (0.6B, 12Hz tokenizer) — competitive with Kokoro
- **Voice cloning:** Zero-shot (3 seconds of reference audio), 10 languages
- **Speed:** RTF 0.28–0.48 on RTX 4090 (faster than real-time even on 1.7B)
- **Why it's relevant:** If Chatterbox-Turbo's voice cloning quality is insufficient, Qwen3-TTS-1.7B is the next zero-shot cloning option with sub-100ms TTFB and permissive license. Strong multilingual support. Trade-off is higher VRAM usage (5–6 GB for 1.7B) versus Chatterbox-Turbo's 4 GB.

#### [OK BUT OPTIONAL] — Cartesia Sonic 3 / Sonic Turbo (Paid API)
- **TTFA:** 90ms (Sonic 3), 40ms (Sonic Turbo) — model inference only
- **Real-world P90 TTFA:** ~130–150ms under normal load (network included)
- **Pricing:** Pro $5/mo (100k chars), 1 credit/char standard, 1.5 credits/char for Pro Voice Clone
- **Why it's optional:** Fast, voice cloning, emotional range, no GPU management. Better than ElevenLabs for latency-critical paid API use. But at solo/agency scale, self-hosted Kokoro + Chatterbox-Turbo is cheaper and comparable in quality.
- **Use if:** You want a single paid API for a client deployment where GPU management is off-limits.

#### [OK BUT OPTIONAL] — Inworld TTS-1.5 (Paid API)
- **Quality:** #1 on Artificial Analysis ELO 1,236 — **beats ElevenLabs on independent benchmarks**
- **Latency:** P90 TTFA 130ms (Mini) to 250ms (Max)
- **Pricing:** $5/1M chars (Mini), $10/1M chars (Max) — 6× cheaper than ElevenLabs Flash
- **Why it's optional:** If you want the highest-quality paid TTS API that isn't ElevenLabs, this is it. Dramatically cheaper per character. But self-hosted Kokoro at ~$0/char is still better economics at your scale.

#### [OK BUT OPTIONAL] — ElevenLabs Flash v2.5 (Emergency Fallback Only)
- **TTFA:** 75ms model inference, ~150–300ms real-world P90 TTFA
- **Pricing:** $0.06/1k chars PAYG; $5/mo Starter (30k chars included)
- **Why it's a fallback:** Use for: (a) languages not supported by Kokoro/Qwen3-TTS, (b) high-stakes marketing/demo recordings requiring emotional depth beyond what Chatterbox delivers, (c) emergency when GPU VPS is down.
- **Do not use as primary.** At $0.06/1k chars vs Kokoro at ~$0, the cost differential is prohibitive at any meaningful volume.

---

### (b) STT: Full Doctrine

#### ✅ RECOMMENDED NOW — Deepgram Flux (Phone Calls + Turn Detection)
- **Latency:** Sub-300ms streaming, 250ms end-of-turn detection
- **Architecture:** Acoustic + semantic end-of-turn detection in a single model
- **False positive reduction:** 70% fewer false start-of-turn detections vs VAD-only
- **Pricing:** Same tier as Nova-3 — $0.0077/min PAYG streaming
- **Why it wins over Nova-3 alone:** Flux replaces the separate "silence timer" VAD for turn completion with a model that understands *meaning*, not just audio energy. It knows "I'll call you..." is an incomplete sentence and won't trigger a bot response prematurely. For phone calls, this is the single biggest conversational quality upgrade available in 2026.
- **Use Silero VAD alongside Flux** for barge-in (real-time interruption during TTS playback) — Flux handles end-of-turn; Silero handles start-of-turn detection in near-real-time.

#### ✅ RECOMMENDED NOW — Deepgram Nova-3 (Phone Calls, No Turn Detection Needed)
- **WER:** 5.26% batch English (Deepgram internal); ~18.3% Artificial Analysis; 2.2% LibriSpeech clean
- **Latency:** Sub-300ms streaming, ~200ms typical TTFB
- **Pricing:** $0.0077/min PAYG streaming, $0.0043/min batch
- **Why it's still valid:** If you're using Silero VAD for turn detection and don't need Flux's semantic EOT, Nova-3 is marginally cheaper to reason about. Keep it as the baseline; upgrade to Flux for complex agent conversations.

#### ✅ RECOMMENDED NOW — faster-whisper large-v3-turbo (App/Desktop STT)
- **WER:** 1.9% LibriSpeech clean (fp16), 7.75% mixed benchmarks, 13.4% noisy real-world YouTube
- **Speed:** 216× real-time on GPU infrastructure; ~130× on typical GPU VPS
- **Cost:** ~$0.0002/min self-hosted (38× cheaper than Deepgram PAYG)
- **Architecture limitation:** 30-second chunk model — not native streaming
- **Streaming workaround:** Use 1–2 second chunks with a short VAD-triggered stability buffer. Introduces ~300–600ms additional latency vs Deepgram but acceptable for desktop/app where phone-grade latency is not required.
- **Why it's the right call for app/desktop:** At 38× cheaper and better clean-audio WER than Deepgram, there's no reason to pay for streaming STT when you control the endpoint and audio is clean.
- **Known gotcha:** Hallucinations during silence (inserts filler phrases like "thank you for watching"). Mitigate with Silero VAD to gate input — only transcribe when VAD confirms speech.

#### [AVOID for real-time] — Whisper via OpenAI API
- $0.006/min, no streaming, 500ms+ variable latency. No advantage over self-hosted faster-whisper and costs more. Use only for one-off batch transcription when GPU VPS is unavailable.

---

### (c) VAD: Full Doctrine

#### ✅ RECOMMENDED NOW — Silero VAD v4
- **AUC:** 0.91 vs WebRTC VAD 0.73 (2026 multi-domain benchmark)
- **Frame window:** 150–250ms (vs WebRTC's 10–30ms)
- **Deploy:** ONNX runtime, ~negligible GPU overhead
- **Use for:** (1) Gating faster-whisper input to prevent hallucinations during silence. (2) Real-time barge-in detection during TTS playback — interrupts Kokoro output when user starts speaking. (3) App/desktop start-of-speech trigger.
- **Alongside Deepgram Flux:** Silero handles barge-in (real-time); Flux handles end-of-turn (semantic). They are complementary, not competitive.

#### [AVOID as primary] — WebRTC VAD
- Use only on edge hardware where PyTorch/ONNX is unavailable (e.g., ESP32, RPi Zero). Its 0.73 AUC is "pretty poor at separating speech from noise" — unacceptable for a voice agent persona.

---

### (d) AEC / Noise Suppression: Full Doctrine

#### ✅ RECOMMENDED NOW — WebRTC AEC3 (Browser/App Layer)
- **Performance:** 20–40 dB ERLE, drift compensation, residual echo suppressor
- **Cost:** Free — built into every browser and WebRTC client
- **Critical rule:** Never disable echo cancellation in your peer connection config. Many voice bot implementations break AEC by setting `echoCancellation: false`. Verify yours is enabled.
- **Applies to:** Web orb, desktop Solon OS (if WebRTC-based), any browser endpoint.

#### ✅ RECOMMENDED NOW — RNNoise (Server-Side Complement)
- Neural noise suppressor for residual noise AEC doesn't address (keyboard clicks, HVAC, ambient hum)
- Add to VPS-side audio pipeline as a post-AEC stage
- Lightweight: CPU-viable, negligible latency

#### [AVOID as primary] — SpeexDSP
- Linear adaptive filter only — cannot cancel non-linear echo distortion
- No drift compensation
- Use only on embedded hardware where WebRTC is unavailable (ESP32, etc.)

---

### (e) Telephony + Orchestration: Full Doctrine

#### ✅ RECOMMENDED NOW — Telnyx + LiveKit-on-Telnyx
- **Session fees:** Waived during beta (LiveKit Cloud charges $0.01/min)
- **STT/TTS cost:** 50% lower than LiveKit Cloud equivalents
- **Latency:** Sub-200ms RTT via GPU-colocated inference + owned telephony PoPs
- **Features:** Carrier-grade SIP, AMR-WB codec, call recording, transfers — native, not bolt-on
- **Migration:** If you have existing LiveKit agents, migration requires only a Dockerfile — same LiveKit framework, SDK, and CLI. No code changes.
- **Why it wins:** You already have Telnyx. Adding LiveKit-on-Telnyx removes the need for a separate LiveKit Cloud subscription ($50–500/mo), eliminates the $0.01/min session fee, and gets your TTS/STT co-located with the telephony layer so audio never takes a cross-country API round trip.

#### [OK BUT OPTIONAL] — LiveKit Cloud (Standalone)
- Valid if you need non-Telnyx PSTN or want multi-carrier redundancy
- Costs: $50/mo (Ship) + $0.01/min agent sessions + STT/TTS markup
- At 5,000 call-minutes: $50 + $50 session fees + STT costs = ~$130+/mo vs ~$40/mo on LiveKit-on-Telnyx
- Only use standalone LiveKit Cloud for non-Telnyx deployments.

---

## What Breaks Quality If You Go Fully Open-Source

| Quality Dimension | Gap | Severity | Mitigation |
|---|---|---|---|
| **STT streaming for phone calls** | faster-whisper 30s chunks add 300–800ms latency to turn detection | High | Use Deepgram Flux for all phone calls — non-negotiable |
| **Voice cloning consistency** | Chatterbox-Turbo has occasional end-of-sentence noise artifacts | Medium | Acceptable for agent persona; ElevenLabs if client-facing commercial clone required |
| **TTS emotional range** | Open-source lags on extreme happy/sad/excited expressiveness | Low | Not needed for Titan's work assistant persona |
| **Multilingual naturalness** | Kokoro covers 8 languages; Qwen3-TTS covers 10; ElevenLabs covers 70+ | Low-Medium | ElevenLabs Flash as fallback for unsupported languages only |
| **Operational reliability** | GPU VPS requires uptime management, model health-checks | Medium | Add `/health` endpoint + systemd restart policy + Grafana alert |
| **Concurrent load degradation** | GPU TTS degrades to 800ms+ at 100+ concurrent streams | Low at current scale | Monitor GPU utilization; scale GPU VPS before hitting 20 concurrent calls |

---

## Phase A — Internal + Demo Voice Architecture

### Use Case
- Web/mobile orb (Titan)
- Solon OS desktop assistant
- High-quality demo recordings
- English-first; multilingual via Kokoro fallback or ElevenLabs for unsupported languages

### Architecture at a Glance

```
USER ENDPOINT (Browser / Desktop App)
        │
        ▼
  [WebRTC AEC3]  ◄── Free, built-in, always enabled
        │
        ▼
  [Silero VAD]   ◄── GPU VPS, ONNX, gates audio input
        │ (speech detected)
        ▼
  [faster-whisper large-v3-turbo]  ◄── GPU VPS, ~1–2s chunks
        │ (transcript chunk)
        ▼
  [Claude API]   ◄── Streaming, sentence-buffered output
        │ (first sentence complete)
        ▼
  [Kokoro v1.0 FastAPI]  ◄── GPU VPS, OpenAI-compatible, ~100ms TTFB
  [Chatterbox-Turbo]     ◄── GPU VPS, voice clone mode (optional)
        │ (audio stream)
        ▼
  [WebAudio API Playback]  ◄── iOS AudioContext unlock required
        │
        ▼
  [Silero VAD barge-in monitor]  ◄── Interrupts TTS if user speaks
        │
        └─── Loop: auto-listen on TTS onended
```

### Exact Services / Models — Phase A

| Layer | Service / Model | Notes |
|---|---|---|
| AEC | WebRTC AEC3 | Browser built-in; verify not disabled |
| Noise suppression | RNNoise | VPS-side, post-AEC |
| VAD | Silero VAD v4 | ONNX, GPU VPS |
| STT | faster-whisper large-v3-turbo | Self-hosted GPU VPS, 1–2s chunks |
| LLM | Claude API (streaming) | Sentence-buffered, first sentence triggers TTS |
| TTS (standard) | Kokoro v1.0 FastAPI | Self-hosted GPU VPS, ~100ms TTFB |
| TTS (voice clone) | Chatterbox-Turbo | Self-hosted GPU VPS, ~150–200ms TTFB |
| TTS (premium demo) | StyleTTS2 or ElevenLabs Starter | StyleTTS2 for English max quality; EL Starter for multilingual fallback |
| Playback | WebAudio API | iOS AudioContext unlock on first user gesture |

### Multilingual Note
Kokoro supports EN, ES, FR, JA, ZH, HI, PT, KO. For other languages: route to ElevenLabs Flash (Starter plan) or Inworld TTS-1.5 ($0.01/1M chars). Implement a language-detection step in the LLM prompt to auto-route.

---

## Phase B — Real Phone Calls (Telnyx) Architecture

### Use Case
- Outbound and inbound calls via Telnyx
- "This feels like talking to a person" quality threshold
- English-first; Spanish/French via Kokoro; other languages via ElevenLabs fallback

### Architecture at a Glance

```
SIP/PSTN CALLER
        │
        ▼
  [Telnyx SIP Trunk]
        │
        ▼
  [LiveKit on Telnyx]  ◄── Carrier-native, GPU-colocated, beta = no session fees
        │
        ├──► [Deepgram Flux STT]  ◄── Acoustic + semantic EOT detection, 250ms EOT latency
        │         │ (transcript + turn-end signal)
        │         ▼
        │    [Silero VAD]          ◄── Barge-in detection only (Flux handles EOT)
        │         │
        │         ▼
        │    [Claude API]          ◄── Streaming, sentence-buffered
        │         │ (first sentence)
        │         ▼
        │    [Kokoro v1.0 FastAPI] ◄── GPU VPS, ~100ms TTFB
        │    [Chatterbox-Turbo]    ◄── If using custom voice clone
        │         │ (audio stream)
        ▼         ▼
  [LiveKit on Telnyx audio mixing]
        │
        ▼
  [AMR-WB codec]  ◄── HD voice codec, carrier-native via Telnyx
        │
        ▼
  CALLER HEARS RESPONSE
```

### Exact Services / Models — Phase B

| Layer | Service / Model | Notes |
|---|---|---|
| Telephony | Telnyx SIP trunk | Existing account; PAYG per-minute |
| Orchestration | LiveKit on Telnyx | Beta: no session fees; 50% cheaper STT/TTS than LK Cloud |
| STT | Deepgram Flux | $0.0077/min streaming; semantic + acoustic EOT |
| VAD (barge-in) | Silero VAD | Interrupt Kokoro output when user speaks during response |
| LLM | Claude API | Streaming; sentence-buffer before TTS |
| TTS | Kokoro v1.0 FastAPI | Self-hosted GPU VPS |
| TTS fallback | ElevenLabs Flash (Starter) | Language gaps only |
| Codec | AMR-WB (built into Telnyx) | HD voice — do not transcode to narrow-band |

### Latency Budget (Phone Call, End-to-End)

| Stage | Target Latency |
|---|---|
| Speech → Deepgram Flux transcript | ~200ms |
| Flux EOT signal | ~250ms (after last word) |
| Claude first-sentence completion | ~200–400ms (depends on sentence length) |
| Kokoro TTFB | ~100ms |
| LiveKit-on-Telnyx RTT | <200ms |
| **Total perceived lag (speech end → first audio)** | **~750ms–950ms total pipeline** |
| **Perceived lag (user experience, first audio starts quickly)** | **<200ms after Kokoro fires** |

> **Note on perceived vs. actual lag:** The "feels like a real call" threshold is about when the caller *hears* audio begin, not the total pipeline time. With sentence buffering, the caller hears the first word within ~100ms of Kokoro starting. The 750–950ms total is the gap between when they stop talking and when they hear the first word — acceptable for a real conversation, comparable to a human pausing to think.

---

## Cost Estimate (~5,000 Call-Minutes/Month + Moderate App Usage)

| Component | Service | Monthly Cost |
|---|---|---|
| STT — app/desktop | faster-whisper self-hosted | ~$0 (GPU already paid) |
| STT — Telnyx calls | Deepgram Flux ($0.0077/min) | ~$38.50 (5,000 min) |
| TTS — all surfaces | Kokoro + Chatterbox-Turbo self-hosted | ~$0 (GPU already paid) |
| TTS fallback | ElevenLabs Starter | $5/mo |
| Telephony | Telnyx per-minute | Existing plan |
| LiveKit orchestration | LiveKit on Telnyx (beta) | $0 session fees |
| VAD + AEC | Silero + WebRTC (self-hosted) | $0 |
| LLM | Claude API | Separate (not a voice-stack cost) |
| **Total added cost** | | **~$43.50/mo** |

Compare: fully-managed stack (ElevenLabs + LiveKit Cloud + Deepgram at scale) = $500–2,000/month.

---

## Implementation Rollout Plan for Titan

### Prerequisites
- GPU VPS with Python 3.10+, Docker, CUDA 12.x
- Telnyx account with SIP trunking enabled
- Deepgram account ($200 free credits)
- Existing Claude API access
- Ports 80/443 open; GPU VPS accessible from internet for WebRTC

---

### Step 1 — Deploy Kokoro v1.0 FastAPI
**What:** Spin up the Kokoro TTS server as a Docker container on GPU VPS with an OpenAI-compatible `/v1/audio/speech` endpoint.

**Code/Infra:**
```bash
docker run -d --gpus all -p 8880:8880 \
  -e KOKORO_MODEL=kokoro-v1_0.pth \
  ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.2  # or GPU variant
```
Point your existing TTS calls at `http://localhost:8880/v1/audio/speech`. No application code changes — it's OpenAI-compatible.

**Prerequisites:** Docker, GPU drivers, CUDA on VPS.

**Effort:** S (2–4 hours including testing)

**Risks:**
- iOS AudioContext requires a user-gesture unlock before first playback — add `context.resume()` on first button click in web orb.
- Verify VRAM budget: Kokoro = 2–3 GB. If running alongside LLM inference, confirm you have headroom.

---

### Step 2 — Migrate to LiveKit on Telnyx
**What:** Redeploy your existing LiveKit voice agent on Telnyx's infrastructure. Same LiveKit Agents SDK — only the deployment target changes.

**Code/Infra:**
- Follow [Telnyx LiveKit docs](https://telnyx.com/products/livekit-on-telnyx)
- Build your agent Docker image as normal
- Push to Telnyx's agent runner instead of LiveKit Cloud
- Update SIP trunk to route to LiveKit-on-Telnyx endpoint

**Prerequisites:** Existing LiveKit agent; Telnyx account; Step 1 complete.

**Effort:** M (4–8 hours; most of this is Telnyx account config + DNS/SIP routing)

**Risks:**
- Beta platform: document your rollback path (keep LiveKit Cloud account active during transition period)
- AMR-WB codec must be enabled on the Telnyx SIP trunk for HD voice — verify this in Telnyx console

---

### Step 3 — Upgrade STT to Deepgram Flux
**What:** Switch the LiveKit agent's STT from Nova-3 to Flux. Add semantic EOT turn detection.

**Code/Infra:**
```python
# In LiveKit agent
session = AgentSession(
    turn_handling=TurnHandlingOptions(
        turn_detection="stt",
    ),
    stt=inference.STT(
        model="deepgram/flux-general",
        language="en",
        eot_threshold=0.8,
    ),
    vad=silero.VAD.load(),  # Keep for barge-in
    # ...
)
```

**Prerequisites:** Deepgram account; LiveKit-on-Telnyx running (Step 2).

**Effort:** S (1–3 hours; mostly testing EOT threshold tuning)

**Risks:**
- Flux is English-optimized. For Spanish/French calls, fall back to Nova-3 with Silero VAD for turn detection.
- `eot_threshold=0.8` is recommended for production — lower values trigger faster but with more false positives.
- Test with realistic phone audio (not clean studio audio) before going live.

---

### Step 4 — Deploy Silero VAD for App/Desktop
**What:** Add Silero VAD to the Phase A pipeline to gate faster-whisper input and handle barge-in.

**Code/Infra:**
```python
import torch
model, utils = torch.hub.load('snakers4/silero-vad', 'silero_vad')
(get_speech_timestamps, _, _, _, _) = utils
# Gate faster-whisper: only transcribe when Silero confirms speech
```
For barge-in: monitor audio stream during TTS playback; if Silero fires, send interrupt signal to Kokoro and resume listening.

**Prerequisites:** PyTorch on GPU VPS; Kokoro running (Step 1).

**Effort:** S (2–4 hours)

**Risks:**
- Silero window is 150–250ms — fast enough for barge-in but adds a small perceptible delay vs WebRTC VAD. This is the correct trade-off (accuracy >> reaction time for barge-in).
- Tune `threshold` parameter: 0.5 is default; lower = more sensitive = more false barge-ins.

---

### Step 5 — Deploy faster-whisper for App/Desktop STT
**What:** Replace any existing cloud STT in the Phase A (orb/desktop) pipeline with faster-whisper large-v3-turbo.

**Code/Infra:**
```python
from faster_whisper import WhisperModel
model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")

# Stream 1–2s chunks, trigger transcription on Silero VAD end-of-speech
def transcribe_chunk(audio_bytes):
    segments, _ = model.transcribe(audio_bytes, beam_size=5, language="en")
    return " ".join([s.text for s in segments])
```

**Prerequisites:** CUDA GPU; Silero VAD deployed (Step 4); VRAM budget confirmed (~2.5 GB for large-v3-turbo).

**Effort:** M (4–8 hours including streaming wrapper and stability buffer)

**Risks:**
- Silence hallucinations: Silero VAD gating (Step 4) is the mitigation — do not run faster-whisper on silent audio.
- 30-second chunk architecture: With 1–2s chunks and VAD gating, perceived latency is ~300–600ms. For desktop/orb, this is acceptable. Do not use for phone calls.
- Chunk boundary artifacts: Add a 200ms overlap between chunks and deduplicate duplicate words at boundaries.

---

### Step 6 — Deploy Chatterbox-Turbo (Voice Clone Endpoint)
**What:** Add Chatterbox-Turbo as a second TTS endpoint for any surface where a custom voice clone is needed (Titan persona voice, agency client demos).

**Code/Infra:**
```bash
pip install chatterbox-tts  # or from Resemble AI GitHub
# Provide 3–5s reference audio clip
# Expose as a secondary FastAPI endpoint on different port
```

**Prerequisites:** GPU VPS with ~4 GB VRAM free after Kokoro is running; reference voice audio clip prepared.

**Effort:** M (4–8 hours including voice quality testing)

**Risks:**
- VRAM: Kokoro (2–3 GB) + Chatterbox-Turbo (~4 GB) = 6–7 GB total. Verify your GPU has headroom. If not, run them on alternating load (Kokoro default, Chatterbox on-demand).
- End-of-sentence noise artifacts: listen for subtle static/click on sentence endings; apply a short fade-out envelope if present.
- Do not use Chatterbox-Turbo for phone calls where latency is critical — stick with Kokoro for Phase B.

---

### Step 7 — Sentence Buffering + First-Chunk Streaming
**What:** Implement sentence-level buffering in the Claude → TTS pipeline so the first audio chunk plays as soon as the first sentence is complete, not when the full response is done.

**Code/Infra:**
```python
import re

def sentence_buffer(stream):
    buffer = ""
    for chunk in stream:
        buffer += chunk
        # Detect sentence boundary
        sentences = re.split(r'(?<=[.!?])\s+', buffer)
        if len(sentences) > 1:
            yield sentences[0]
            buffer = " ".join(sentences[1:])
    if buffer.strip():
        yield buffer

for sentence in sentence_buffer(claude_stream):
    tts_audio = kokoro_tts(sentence)
    play_audio(tts_audio)  # Non-blocking
```

**Prerequisites:** Steps 1–5 complete; Claude streaming API integrated.

**Effort:** S (2–4 hours)

**Risks:**
- Sentence boundaries in code/data responses (e.g., "call me at 555.123.4567") can false-trigger the splitter. Add a simple heuristic: only split on `.!?` followed by a space and capital letter.
- Do not split mid-number or mid-URL — add exclusion regex.

---

### Step 8 — Add RNNoise to VPS Audio Pipeline
**What:** Apply RNNoise neural noise suppression to inbound audio on the server side before STT processing.

**Code/Infra:**
```bash
pip install rnnoise-python
# Apply to audio buffer before passing to faster-whisper or Deepgram
```
Or use the C library via subprocess for lower latency.

**Prerequisites:** Steps 4–5 complete.

**Effort:** S (2–3 hours)

**Risks:**
- RNNoise adds ~3–5ms latency — negligible.
- Do not double-apply: if client-side WebRTC AEC3 is active, RNNoise on the server is a second pass targeting residual noise, not echo. Both are appropriate.

---

### Step 9 — Health Checks + Auto-Restart
**What:** Add monitoring so Titan auto-restarts crashed TTS/STT services and alerts if GPU utilization spikes.

**Code/Infra:**
```bash
# systemd service for Kokoro
[Service]
Restart=always
RestartSec=5

# Health endpoint check (add to Kokoro FastAPI)
GET /health → {"status": "ok", "gpu_mem_used_mb": 2400}

# Cron or Grafana alert: if GPU mem > 80% for >60s, page
```

**Prerequisites:** All services deployed (Steps 1–8).

**Effort:** S (2–3 hours)

**Risks:**
- GPU memory leaks in TTS models under long uptime are possible — add a nightly restart cron as a precaution during first 30 days.

---

### Step 10 — ElevenLabs Fallback Routing
**What:** Implement a language-detection router that redirects TTS requests to ElevenLabs Flash when the detected language is not in Kokoro's supported set.

**Code/Infra:**
```python
KOKORO_LANGUAGES = {"en", "es", "fr", "ja", "zh", "hi", "pt", "ko"}

def route_tts(text: str, detected_lang: str):
    if detected_lang in KOKORO_LANGUAGES:
        return kokoro_tts(text, lang=detected_lang)
    else:
        return elevenlabs_flash_tts(text)  # Starter plan fallback
```

**Prerequisites:** ElevenLabs Starter plan API key stored in secrets; Steps 1–9 complete.

**Effort:** S (1–2 hours)

**Risks:**
- Language detection errors can route to ElevenLabs unnecessarily. Use `langdetect` with a minimum confidence threshold (>0.85) before routing out.
- ElevenLabs Starter plan (30k chars/mo) is the safety valve. If fallback volume grows, upgrade to Creator ($22/mo, 100k chars).

---

## Engineering Checklist for Titan (MP-3 / MP-4 Autonomy Blueprint)

```
VOICE AI STACK — ENGINEERING CHECKLIST v1.0

[ ] Step 1: Kokoro v1.0 FastAPI running on GPU VPS (Docker, port 8880, OpenAI-compat)
[ ] Step 2: LiveKit-on-Telnyx agent deployed; SIP trunk routing confirmed; AMR-WB enabled
[ ] Step 3: Deepgram Flux STT active (model=deepgram/flux-general, eot_threshold=0.8)
[ ] Step 4: Silero VAD v4 deployed; barge-in interrupt signal wired to Kokoro output
[ ] Step 5: faster-whisper large-v3-turbo (float16) running; Silero gating applied
[ ] Step 6: Chatterbox-Turbo endpoint live; VRAM budget verified (<7 GB total TTS)
[ ] Step 7: Sentence buffering in Claude → TTS pipeline; first chunk fires on first sentence
[ ] Step 8: RNNoise applied to server-side audio before STT
[ ] Step 9: /health endpoint on Kokoro; systemd Restart=always; GPU mem alert at 80%
[ ] Step 10: ElevenLabs Starter API key in secrets; language router live (fallback only)

RED LINES (do not cross):
[ ] NEVER deploy production TTS on XTTS-v2
[ ] NEVER use faster-whisper for phone calls (30s chunk latency breaks conversational feel)
[ ] NEVER disable WebRTC AEC3 (echoCancellation: false) in peer connection config
[ ] NEVER use ElevenLabs as primary TTS — it is fallback only
[ ] NEVER run Kokoro + Chatterbox-Turbo simultaneously without VRAM budget confirmation

VERIFY MONTHLY:
[ ] Deepgram Flux pricing (confirm $0.0077/min still applies; Flux is same tier as Nova-3)
[ ] LiveKit-on-Telnyx beta session fee status (confirm still $0 before committing calls)
[ ] Kokoro/Chatterbox-Turbo upstream repos for new releases (model quality updates)
[ ] GPU VPS memory utilization under peak call load (target: <70% at expected concurrency)
```

---

## References

1. [Kokoro v1.0 real-time factor — ocdevel TTS comparison 2026](https://ocdevel.com/blog/20250720-tts) — 210× (4090), 90× (3090), 36× (T4), 5× (CPU)
2. [Kokoro production latency: 100ms on GPU](https://blog.dtelecom.org/we-replaced-elevenlabs-with-kokoro-tts-on-an-m4-gpu-latency-fell-to-100-ms-and-tts-cost-nearly-68bcc3313cdd) — dtelecom, March 2026
3. [Chatterbox-Turbo: 350M, sub-200ms, MIT](https://codersera.com/blog/chatterbox-turbo-run-and-install-locally-free-elevenlabs-alternative-2026) — Codersera 2026
4. [Chatterbox 63.75% blind test preference over ElevenLabs](https://developer.puter.com/blog/elevenlabs-alternatives/) — Puter Technologies, April 2026
5. [Deepgram Nova-3: 5.26% WER English batch, $0.0077/min streaming](https://deepgram.com/learn/best-speech-to-text-apis-2026) — Deepgram, Feb 2026
6. [Deepgram Flux: 250ms EOT, 70% fewer false positives](https://deepgram.com/learn/flux-just-got-a-little-smarter) — Deepgram, Jan 2026
7. [Deepgram Flux turn detection integration with LiveKit](https://docs.livekit.io/agents/models/stt/deepgram/) — LiveKit Docs
8. [ElevenLabs Flash v2.5: ~150ms TTFA P90 real-world, $0.06/1k chars API](https://www.getaiperks.com/en/articles/elevenlabs-pricing) — AI Perks, March 2026
9. [Cartesia Sonic 3: 90ms TTFA, Turbo: 40ms TTFA (model-only), Pro plan $5/mo](https://cartesia.ai/pricing) — Cartesia AI, April 2026
10. [Telnyx LiveKit-on-Telnyx: sub-200ms RTT, 50% lower cost, no session fees beta](https://telnyx.com/products/livekit-on-telnyx) — Telnyx, April 2026
11. [LiveKit Cloud session fees: $0.01/min](https://checkthat.ai/brands/livekit/pricing) — CheckThat.ai, March 2026
12. [Silero VAD v4: AUC 0.91 vs WebRTC VAD 0.73](https://arxiv.org/html/2601.17270v1) — arXiv, Jan 2026
13. [faster-whisper large-v3-turbo: 1.9% WER LibriSpeech clean, 7.75% mixed](https://github.com/SYSTRAN/faster-whisper/issues/1030) — GitHub benchmark, Oct 2024
14. [Inworld TTS-1.5: #1 Artificial Analysis ELO 1,236, $10/1M chars](https://inworld.ai/resources/tts-api-pricing-comparison) — Inworld AI, April 2026
15. [Qwen3-TTS: 97ms first-packet latency, Apache 2.0, 10 languages](https://arxiv.org/html/2601.15621v1) — arXiv technical report, Jan 2026
16. [WebRTC AEC3: 20–40 dB ERLE, always enable](https://bloggeek.me/voice-ai-best-practices/) — BlogGeek.me
17. [Streaming TTS under load: 800ms+ at 100 concurrent](https://deepgram.com/learn/streaming-tts-latency-accuracy-tradeoff-2026) — Deepgram, Feb 2026
