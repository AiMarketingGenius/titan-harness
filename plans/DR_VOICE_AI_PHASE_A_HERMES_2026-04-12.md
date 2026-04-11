# PLAN — Voice AI Phase A (Hermes) — CPU-First Internal/Demo Lane

**Task ID:** CT-0412-05
**Codename:** Hermes — Voice AI Path A (demo voice lane) — locked per RADAR §Greek Codename
**Status:** DRAFT → pending Reviewer Loop A/A- clearance
**Project:** Atlas demo experience (orb + desktop + Loom), self-hosted on existing Titan VPS
**Owner:** Titan (autonomous under standing-auth directive 2026-04-12)
**Created:** 2026-04-12
**Binding doctrine:** [`plans/DOCTRINE_VOICE_AI_STACK_v1.0.md`](DOCTRINE_VOICE_AI_STACK_v1.0.md) (ingested verbatim 2026-04-12 from Perplexity Computer report)
**Supersedes:** `plans/PLAN_2026-04-12_voice-ai-path-a-demo.md` (local-only, not git-tracked) — prior plan assumed Deepgram + ElevenLabs as primaries; doctrine v1.0 reclassifies ElevenLabs as fallback-only and replaces Deepgram with faster-whisper for app/desktop.

**Naming note:** `DR_` prefix only because `plans/.gitignore` restricts tracked files to `DOCTRINE_*` and `DR_*`. Content is Phase plan scope (Greek codename **Hermes**, doctrine v1.0 §"Phase A" subset), not a standalone Deep Research.

---

## 1. Intent

Ship a working orb + desktop voice layer for Atlas demos that is (a) faithful to doctrine v1.0, (b) runs entirely on the existing Titan VPS without renting a new GPU VPS (Hard-Limit-protected cost), and (c) zero new recurring spend. Trade-off: CPU inference means ~500ms TTFB vs GPU's ~100ms — acceptable for desktop/orb demos, not for phone calls. Phase B (Telnyx phone calls) is **not** in scope for this plan and remains gated on a separate GPU-VPS decision that requires Solon approval.

## 2. Non-negotiable constraints (from standing directive + harness rules)

1. **No new recurring spend** (Hard Limit #5: >$50/mo). Rules out renting GPU VPS. Rules out ElevenLabs Creator tier ($22/mo) except as emergency fallback using existing allowance if already paid. Rules out Deepgram streaming ($0.0077/min).
2. **No new credentials.** Anything requiring Solon to create an account or paste an API key is deferred with a one-line flag.
3. **No destructive prod-data ops.** New services are additive — separate systemd units, separate ports, separate Docker containers.
4. **No doctrine-file edits** to CORE_CONTRACT.md / CLAUDE.md / DR_TITAN_AUTONOMY_BLUEPRINT.md.
5. **Reviewer budget:** ≤5 calls/day, ≤$5/month, $0.05/call. This plan's reviewer expenditure must fit inside the existing daily budget without asking for a cap bump.
6. **IP protection** (doctrine `plans/DOCTRINE_AMG_PRODUCT_TIERS.md §2`): Atlas frontend never calls TTS/STT/LLM vendors directly; all traffic goes through VPS API shim.

## 3. CPU-path decision log

Titan VPS audit (2026-04-12): AMD EPYC 7763 12 cores, 62 GB RAM, 60 GB free disk, Docker 28.2, Python 3.10, **no GPU** (no `nvidia-smi`). Doctrine v1.0 prerequisites list "GPU VPS with Python 3.10+, Docker, CUDA 12.x". Doctrine also documents CPU fallback latencies for Kokoro ("5× CPU" RTF), implying CPU deploys are a known-but-slower path.

**Decision (Titan, logged to MCP):** pivot Phase A to the CPU-compatible subset of doctrine v1.0. Defer GPU-only components. This keeps the session inside the standing-auth envelope and delivers a working orb/desktop demo this week with zero new spend.

| Doctrine step | CPU feasibility | This plan's disposition |
|---|---|---|
| Step 1 — Kokoro v1.0 FastAPI | ✅ CPU variant `ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.2` documented in doctrine §"Implementation Rollout" | **IN SCOPE** |
| Step 2 — LiveKit-on-Telnyx | ❌ Phase B only; requires Telnyx agent runner | **DEFERRED** (Phase B gate) |
| Step 3 — Deepgram Flux STT | ❌ Paid API, streaming $0.0077/min; new recurring spend | **DEFERRED** (Hard Limit) |
| Step 4 — Silero VAD v4 | ✅ ONNX, "negligible GPU overhead", runs fine on CPU | **IN SCOPE** |
| Step 5 — faster-whisper large-v3-turbo | 🟡 Downscoped: use `medium.en` int8 on CPU (~2× real-time) instead of large-v3-turbo (would be ~0.5× RTF on CPU). Quality trade-off documented. | **IN SCOPE (medium.en variant)** |
| Step 6 — Chatterbox-Turbo voice clone | ❌ 6× RTF is GPU-spec; CPU ≈ 0.3–0.5× RTF, unusable for demos | **DEFERRED** (GPU gate) |
| Step 7 — Sentence buffering Claude → TTS | ✅ pure Python logic, no GPU | **IN SCOPE** |
| Step 8 — RNNoise CPU noise suppression | ✅ CPU-viable per doctrine ("negligible latency") | **IN SCOPE** |
| Step 9 — Health checks + systemd Restart=always | ✅ infra only | **IN SCOPE** |
| Step 10 — ElevenLabs Starter fallback | ❌ Requires new API key + $5/mo (Hard Limit borderline) | **DEFERRED** (Hard Limit) |

**In-scope surface:** 1, 4, 5 (downscoped), 7, 8, 9 — six steps, all CPU, all self-hosted, zero new spend, zero new creds.

## 4. Target architecture (Phase A, CPU subset)

```
Atlas frontend (os.aimarketinggenius.io orb + desktop)
        │ (WebSocket /ws/voice/{session_id})
        ▼
Atlas API shim (new FastAPI on VPS, Caddy-reverse-proxied)
   ├─ inbound audio → [RNNoise] → [Silero VAD] → [faster-whisper medium.en]
   │                                                    │
   │                                                    ▼
   │                                          [LiteLLM gateway → Claude]
   │                                                    │
   │                                                    ▼
   │                                          [sentence buffer]
   │                                                    │
   ├─ outbound text → [Kokoro FastAPI localhost:8880]   │
   │                                                    ▼
   └─ outbound audio chunks → WebSocket back to frontend
```

IP-protection rule: frontend only speaks to Atlas API shim. Shim is the only process that talks to Kokoro, Claude (via LiteLLM), or any future vendor.

Session continuity reuses `atlas_session_id` handshake from HERCULES_BACKFILL_REPORT §TODO.3. Unchanged from prior Path A plan.

## 5. Implementation steps

### Step 1 — Kokoro v1.0 FastAPI (CPU variant)

**Deliverable:** `kokoro-cpu` systemd-managed Docker container on VPS, listening on `127.0.0.1:8880`, exposing `/v1/audio/speech` (OpenAI-compatible).

**Commands:**
```bash
docker pull ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.2
mkdir -p /opt/titan-harness/services/kokoro
# systemd unit
cat >/etc/systemd/system/titan-kokoro.service <<EOF
[Unit]
Description=Titan Kokoro TTS (CPU variant)
After=docker.service
Requires=docker.service
[Service]
Restart=always
RestartSec=5
ExecStartPre=-/usr/bin/docker rm -f titan-kokoro
ExecStart=/usr/bin/docker run --rm --name titan-kokoro \
  -p 127.0.0.1:8880:8880 \
  --memory=8g --cpus=6 \
  ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.2
ExecStop=/usr/bin/docker stop titan-kokoro
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now titan-kokoro
```

**Acceptance:** `curl -sf http://127.0.0.1:8880/health` returns 200; `curl -s http://127.0.0.1:8880/v1/audio/speech -H 'Content-Type: application/json' -d '{"model":"kokoro","voice":"af_bella","input":"Hello, this is Hermes."}' -o /tmp/hermes_smoke.mp3` produces a playable MP3 ≥10 KB. TTFB measured with `curl -w '%{time_starttfb}'` must be ≤1500ms (CPU budget, 15× the GPU figure from doctrine).

**Rollback:** `systemctl disable --now titan-kokoro && docker rm -f titan-kokoro && rm /etc/systemd/system/titan-kokoro.service`.

**Risks + mitigations:**
- Container image not yet pinned → lock digest after first successful pull, store in `services/kokoro/IMAGE_DIGEST.txt`.
- 8 GB memory cap is generous (Kokoro uses 2–3 GB per doctrine); leaves headroom for faster-whisper.
- CPU contention with existing VPS workloads → `--cpus=6` caps the container at half the 12 cores.

### Step 4 — Silero VAD v4

**Deliverable:** `lib/silero_vad.py` wrapper loading `silero_vad` via ONNX runtime, callable from the Atlas API shim to (a) gate faster-whisper input and (b) emit `start_of_speech` / `end_of_speech` events for barge-in.

**Commands:**
```bash
pip install --user onnxruntime==1.17.3 numpy
python3 -c "import torch, torchaudio; model,_=torch.hub.load('snakers4/silero-vad','silero_vad',trust_repo=True); print('ok')"
```
(Install the ONNX weights alongside the Python wrapper; do not load via `torch.hub` at runtime to avoid network dependency.)

**Acceptance:** `python3 -m lib.silero_vad --self-test` runs on a 3-second clip `tests/fixtures/hermes_hello.wav` and returns `{speech_detected: true, segments: [...]}` in ≤200ms.

**Rollback:** delete `lib/silero_vad.py`, remove the pip installs (no other harness code depends on them).

### Step 5 — faster-whisper `medium.en` int8

**Deliverable:** `lib/whisper_cpu.py` wrapper around `faster_whisper.WhisperModel("medium.en", device="cpu", compute_type="int8")`, called from the Atlas API shim when Silero VAD confirms speech.

**Why medium.en not large-v3-turbo:** large-v3-turbo on CPU is ~0.5× real-time — unusable for streaming. `medium.en` at int8 runs ~2× real-time on modern x86, covering the demo latency budget (≤1s transcription for a 2s chunk). English-only is acceptable for Phase A (demo language is English).

**Commands:**
```bash
pip install --user faster-whisper==1.0.3
python3 -c "from faster_whisper import WhisperModel; m=WhisperModel('medium.en',device='cpu',compute_type='int8'); print('ok')"
```

**Acceptance:** `python3 -m lib.whisper_cpu --self-test tests/fixtures/hermes_hello.wav` transcribes "hello this is Hermes" (case-insensitive) in ≤2s.

**Rollback:** delete `lib/whisper_cpu.py`, uninstall faster-whisper.

### Step 7 — Sentence buffering

**Deliverable:** `lib/sentence_buffer.py` implementing the doctrine §Step 7 regex buffer with URL + phone-number exclusions, plus unit tests in `tests/test_sentence_buffer.py`.

**Acceptance:** `python3 -m pytest tests/test_sentence_buffer.py` passes 6 cases (short sentence, long sentence, mid-URL, mid-phone, mid-decimal, empty).

### Step 8 — RNNoise server-side

**Deliverable:** `lib/rnnoise_wrapper.py` calling the C binary `/usr/local/bin/rnnoise_demo` via subprocess, applied to inbound PCM before Silero VAD.

**Commands:**
```bash
apt-get install -y build-essential autoconf libtool
cd /opt/titan-harness/services && \
  git clone https://github.com/xiph/rnnoise.git && \
  cd rnnoise && ./autogen.sh && ./configure && make && cp examples/rnnoise_demo /usr/local/bin/
```

**Acceptance:** `python3 -m lib.rnnoise_wrapper --self-test tests/fixtures/noisy.wav tests/fixtures/clean_expected.wav` passes (SNR improvement ≥10 dB).

### Step 9 — Health checks + systemd auto-restart

**Deliverable:** `/health` HTTP endpoint added to Kokoro sidecar (doctrine says it's built-in to the FastAPI image — verify and wire to a cron check). `bin/titan-kokoro-healthcheck.sh` runs every minute via systemd timer, logs to `/var/log/titan/kokoro-health.jsonl`, alerts via existing `lib/war_room.py` notification path if 3 consecutive failures.

**Acceptance:** `systemctl list-timers | grep titan-kokoro` shows the timer; induced failure (docker stop) produces an entry in `/var/log/titan/kokoro-health.jsonl` within 90s.

## 6. Step sequencing + reviewer-budget plan

With 3 reviewer calls remaining today (or 5 if the UTC day has rolled), at ~$0.05 each:

1. **Call 1** — grade this plan end-to-end (pre-execution).
2. **Call 2** — grade the Step 1 + Step 9 bundle (Kokoro deployed + health-check wired + smoke test passes). Groups the two most infra-heavy items.
3. **Call 3** — grade the Step 4 + Step 5 + Step 7 bundle (VAD + whisper + sentence buffer all integration-tested together).
4. **Call 4 (tomorrow)** — grade Step 8 (RNNoise) standalone, leaves room for 1 escalation call.

Bundles are structured so that a failure in any one substep surfaces in the same reviewer call that grades the bundle — no hidden skipped gates.

## 7. Cost model

| Line item | One-time | Monthly |
|---|---|---|
| GPU VPS rental | $0 (deferred; not in scope) | $0 |
| Kokoro v1.0 (CPU Docker) | $0 | $0 |
| faster-whisper medium.en | $0 | $0 |
| Silero VAD | $0 | $0 |
| RNNoise | $0 | $0 |
| Reviewer Loop (4 calls) | $0.20 | ~$0.20 incremental (well inside $5/mo cap) |
| **Total new spend** | **$0.20** | **$0.20/mo** |

Compares to existing Path A plan which assumed ~$200–$270/mo for Deepgram + ElevenLabs. This plan is **1000× cheaper** to run, at the cost of GPU-grade latency.

## 8. Success criteria (Phase A end-state)

An end-to-end run from a cold VPS must:

1. `systemctl status titan-kokoro` shows `active (running)` for ≥5 minutes.
2. `curl -sf http://127.0.0.1:8880/v1/audio/speech -d '{...}'` produces an MP3 ≤1500ms TTFB.
3. `python3 -m lib.silero_vad --self-test` passes on the fixture clip.
4. `python3 -m lib.whisper_cpu --self-test` transcribes the fixture clip correctly in ≤2s.
5. `python3 -m pytest tests/test_sentence_buffer.py` green.
6. `python3 -m lib.rnnoise_wrapper --self-test` green.
7. `/var/log/titan/kokoro-health.jsonl` has ≥5 consecutive "ok" lines.

No Atlas frontend orb UX is in scope for this plan — the orb build is a separate deliverable that consumes this stack. This plan ships the **substrate** only.

## 9. Rollback plan (end-to-end)

Single command rolls the entire Phase A stack back:
```bash
systemctl disable --now titan-kokoro && \
  docker rm -f titan-kokoro && \
  rm -f /etc/systemd/system/titan-kokoro.service /etc/systemd/system/titan-kokoro-health.timer && \
  rm -rf /opt/titan-harness/services/kokoro /opt/titan-harness/services/rnnoise && \
  pip3 uninstall -y faster-whisper onnxruntime && \
  git checkout lib/silero_vad.py lib/whisper_cpu.py lib/sentence_buffer.py lib/rnnoise_wrapper.py 2>/dev/null; \
  systemctl daemon-reload
```
No database changes, no external service state, no DNS changes, no Caddy changes — rollback is fully local.

## 10. Vendor outage / dependency risk

This plan has **zero paid-API dependencies**, so the vendor-outage surface is small:

- **Docker Hub / ghcr.io outage** — image pulls fail. Mitigation: pin digest after first pull, cache in local registry if needed.
- **GitHub outage (silero-vad, rnnoise repos)** — wheels/weights already downloaded after first install. No runtime dependency.
- **Claude API outage** — affects LLM call, not the voice substrate. Existing LiteLLM gateway retry/fallback logic handles this (out of scope for this plan).

## 11. Scope boundaries (what this plan does NOT do)

- Does NOT build the Atlas frontend voice orb (separate deliverable, not in scope).
- Does NOT wire the Atlas API shim WebSocket endpoint (separate deliverable — depends on this substrate).
- Does NOT touch `sql/` migrations.
- Does NOT touch `policy.yaml` — no new autopilot flags required for Phase A substrate.
- Does NOT rent GPU VPS, subscribe to any paid API, or request any Solon credential.
- Does NOT commit any Greek codename locks (Hermes is already locked per RADAR §Greek Codename; no new names).
- Does NOT edit CORE_CONTRACT.md / CLAUDE.md / DR_TITAN_AUTONOMY_BLUEPRINT.md.

## 12. Grading block

**Grading method:** `perplexity-api` (Reviewer Loop primary per `policy.yaml autopilot.reviewer.fallback_order`)
**Why this method:** Slack-Computer transport dormant (bot-to-bot event filter + /oauth SPA unresolved); `aristotle_enabled: false`; perplexity-api is the active primary per Solon directive 2026-04-11 v2.
**Pending:** re-grade by Slack Aristotle when `aristotle_enabled=true` and `/titan-aristotle` channel goes live.
**Budget impact:** 4 reviewer calls across the Phase A lifecycle = $0.20, well inside the $5/month cap.

*(Scores to be inserted after `bin/review_gate.py` returns — this block intentionally left blank until Reviewer Loop call 1/4 completes.)*

## 13. Decision

Promote to **ACTIVE** once Reviewer Loop call 1 returns A or A- with zero risk tags. Begin Step 1 execution immediately thereafter under standing autonomous-execution authorization (Solon directive 2026-04-12).
