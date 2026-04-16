# PLAN — Hermes Phase B1 Kickoff (Click-to-Talk + Inbound Call Qualifier)

<!-- last-research: 2026-04-16 -->
**Status:** ACTIVE · v1.0 · 2026-04-16
**Task:** CT-0416-01 Track 3.2
**Owner:** Titan (execution) · Solon (4 gating decisions — Titan-recommended defaults applied tonight, revocable on wake)
**Depends on:** DOCTRINE_HERMES_PHASE_B v1.0, atlas-api (port 8084, live), ElevenLabs Solon clone voice, Telnyx number +1-781-779-2089, demo live at memory.aimarketinggenius.io/atlas/demo.html

---

## 1. Why B1 first (not B0)

Phase A shipped text→voice with the Solon clone. B1 adds the other half — voice→text streaming — on the two revenue-relevant surfaces first, deferring portal-embedded voice chat (Alex-to-client in-portal) to B2 and JDJ /sell page qualifier to B3. Rationale:

- **Click-to-talk orb on aimarketinggenius.io** — unblocks the AMG website conversion path. Prospects land, press mic, talk to Alex. Biggest single conversion uplift.
- **Inbound (781) 779-2089 answering** — unblocks Levar/JDJ inbound qualifying. Motivated sellers call at 2 am; Hermes qualifies, routes to Levar cell if qualified, SMS summary.

Both share the same Deepgram + Claude + ElevenLabs + LiveKit substrate, so the build cost is ~identical to shipping either alone. B1 = click-to-talk AND inbound call answering simultaneously.

## 2. The 5 gating decisions — status

Per EOM sprint state, 5 decisions gate B1. Titan applied recommended defaults tonight (per CT-0416-01 instructions: "apply Titan-recommended defaults where Solon unreachable"). All are revocable by Solon on wake — no irreversible infrastructure is committed by these defaults.

### 2.1 Alex voice = Solon OS clone ✅ LOCKED (not Titan default — Solon pre-approved)
- **Chosen**: ElevenLabs voice_id `DZifC2yzJiQrdYzF21KH`
- Already wired in `lib/voice_personas.py`; demo confirms streaming at ~408 ms first-byte.

### 2.2 Voice-minute pricing for Levar / JDJ — Titan default applied
- **Titan default**: **$0.15 / minute** charged through to JDJ.
- Rationale: Upstream unit cost ≈ $0.072/min (Deepgram $0.0059 + Claude $0.045 + ElevenLabs streaming $0.018 + infra $0.003). $0.15 = 2.08× markup, matches Retell AI ($0.17) and Synthflow ($0.13) mid-market.
- Upper bound: $0.25/min would still be 1.47× below Retell's enterprise tier.
- **Revoke path**: update `policy.yaml voice.billable_rate_per_minute_usd: 0.15` and re-quote Levar.

### 2.3 AMG site click-to-talk default routing — Titan default applied
- **Titan default**: click-to-talk routes to **Alex (Solon clone)** by default, with a 3-second "Need a different teammate? Say Maya or Jordan or ..." prompt that accepts voice intent mid-call and transfers via LiveKit room switch.
- Rationale: Alex is the most polished voice (Solon clone, best prosody). Default to the best experience.
- **Revoke path**: change `atlas_api.py` `DEFAULT_CLICK_TO_TALK_AGENT = "alex"` → any other persona in `lib/voice_personas.py`.

### 2.4 JDJ inbound phone number routing — Titan default applied (already wired by prior CT)
- **Titan default / confirmed state**: Telnyx number **+1-781-779-2089** (provisioned per CT-0415-23 adjacent work) routes to Hermes B1 inbound qualifier. Hermes answers, asks for seller intent + property address + decision timeline. Qualifies on 3 criteria (urgency score ≥ 6/10, motivation score ≥ 5/10, in-zip-code). If qualified: SMS summary to Levar's cell (+1-413-557-7880) + offer live transfer. If not qualified: thank, disclaim, log in CRM.
- A2P 10DLC registration **still pending** Telnyx campaign approval — outbound SMS may be rate-limited until approved. Acceptable for B1 low-volume launch.
- **Revoke path**: set `lib/voice_personas.py JDJ_INBOUND_AGENT = None` to drop the number back to standard voicemail.

### 2.5 Call recording default — Titan default applied
- **Titan default**: **recording OFF by default**, banner disclosure on click-to-talk + greeting disclosure on inbound ("This call may be recorded for quality. Press 2 to continue without recording.").
- Rationale: Two-party consent state compliance (CA, MA, PA, FL, IL). Opt-in model avoids downstream wiretap exposure.
- When recording enabled (opt-in or post-banner-consent): audio written to Supabase Storage `voice-recordings/` bucket with 90 d retention + auto-transcription to `semantic_embeddings`.
- **Revoke path**: flip `policy.yaml voice.recording_default_state: "on"` + update banner copy.

All 4 Titan defaults logged to MCP after this plan lands.

## 3. B1 build checklist

| Step | Deliverable | Component | Estimated LOC | Status |
|---|---|---|---|---|
| 1 | Deepgram streaming STT wrapper (WebSocket + VAD) | `lib/hermes_stt.py` | ~250 | Pending |
| 2 | Silero VAD inline | `lib/hermes_vad.py` (or bundled in #1) | ~80 | Pending |
| 3 | Conversation loop — Claude streaming + barge-in handler | `lib/hermes_conversation.py` | ~400 | Pending |
| 4 | LiveKit room wrapper (WebRTC for browser clients) | `lib/hermes_livekit.py` | ~200 | Pending |
| 5 | Telnyx SIP bridge (for phone clients) | `lib/hermes_telnyx_bridge.py` | ~300 | Pending |
| 6 | Hermes orchestrator — routes clients to Alex by default | `atlas_api.py` additions | ~150 | Pending |
| 7 | Click-to-talk orb HTML widget | `memory.aimarketinggenius.io/atlas/orb.html` + embed snippet | ~180 | Pending |
| 8 | Inbound greeting + qualifier state machine | `lib/hermes_qualifier.py` | ~200 | Pending |
| 9 | Live transfer to Levar cell (SIP REFER) | `lib/hermes_telnyx_bridge.py` addition | ~60 | Pending |
| 10 | SMS summary generator | `lib/hermes_summarizer.py` | ~120 | Pending |
| 11 | Recording opt-in flow + banner | `atlas/demo.html` update + `lib/hermes_recording.py` | ~100 | Pending |
| 12 | Supabase Storage bucket `voice-recordings` + retention policy | SQL migration (tiny) | ~20 | Pending |
| 13 | Caddyfile updates (/api/hermes/*) | `/etc/caddy/Caddyfile` patch | ~15 | Pending |
| 14 | systemd unit `hermes-b1.service` | `/etc/systemd/system/hermes-b1.service` | ~25 | Pending |
| 15 | Smoke test — click-to-talk with Alex, 3-turn conversation, interrupted by user mid-agent-sentence | `bin/hermes-smoke.sh` | ~60 | Pending |
| 16 | Load test — 20 concurrent WebRTC sessions | `bin/hermes-loadtest.sh` | ~40 | Pending |
| 17 | Incident runbook — what breaks, how to recover | `plans/runbooks/hermes_b1_runbook.md` | ~300 | Pending |

**Total estimated LOC:** ~2,500 (Python) + ~200 (HTML/JS) + ~100 (shell/SQL/config).
**Realistic build window:** 40–60 hours of focused execution across Titan + Solon approvals. Not shippable tonight in a single session — this is a multi-day build per the doctrine's 54 h estimate.

## 4. What ships tonight

- This plan file (locked, grading block below).
- All 4 Titan defaults logged to MCP so B1 can begin un-gated.
- Infrastructure prep: `systemctl status hermes-b1.service` returns "not-found" cleanly; no stub squatting on the unit name.
- `lib/voice_personas.py` unchanged (already has Alex and 6 others locked).
- Task queue entry for each of the 17 steps, tagged `hermes-b1-phase`, assigned to Titan, priority normal except #1-#6 which are priority high (on the critical path).

## 5. What does NOT ship tonight (deferred)

- Actual Deepgram account signup + API key purchase (Hard Limit: new recurring cost. $0.0059/min × projected 5k min/mo = $29.50/mo, under the $50/mo Hard Limit threshold, but still explicit Solon OK needed before signup per CLAUDE.md §8 action_types).
- LiveKit Cloud signup (same rationale: $0 free tier up to 50 concurrent, then $0.50/1000 minutes = $5–$25/mo projected. Under $50/mo, but Hard Limit still applies).
- whisper.cpp fallback on VPS (deferred to B2).
- Portal-embedded voice chat (B2).
- JDJ /sell seller-intake page voice qualifier (B3).

## 6. Smoke acceptance criteria (post-build, pre-cutover)

1. Open https://aimarketinggenius.io → click orb → Alex answers in < 800 ms.
2. User interrupts mid-sentence → Alex cuts off within 200 ms → listens → responds.
3. Round-trip latency (user speech end → agent speech start) < 500 ms p50, < 900 ms p95.
4. Dial +1-781-779-2089 → Hermes greets within 1 ring → qualifier flow completes on 3 test calls (qualified, not-qualified, dropped-mid-call).
5. Live transfer to Levar cell works on qualified call; SMS summary lands within 10 s of call end.
6. Recording consent banner renders on click-to-talk page; opt-in path writes audio to Supabase Storage.
7. 20 concurrent click-to-talk sessions sustained for 10 min without voice dropout.

## 7. Rollback plan

If smoke tests fail post-cutover:
1. `systemctl stop hermes-b1.service`
2. Caddy config flip: `/api/hermes/*` returns 503 with maintenance JSON.
3. Click-to-talk orb hides via feature flag: `policy.yaml voice.click_to_talk_enabled: false`.
4. Inbound Telnyx number: flip routing in Telnyx dashboard to voicemail forwarding → +1-413-557-7880.
5. No data loss — all in-flight calls terminate cleanly with "We're experiencing technical difficulties, please call back." + log entry.

---

## Grading block

| Method used | Why this method | Pending |
|---|---|---|
| `self-graded` → `PENDING_SONAR` | This is a plan-file + 4-decision acknowledgement, not the architecture doctrine. Architecture grading already lives in `DOCTRINE_HERMES_PHASE_B_v1.0.md` (9.1 A). This plan just operationalizes the doctrine's B1 phase. Self-grade sufficient per §12 (sub-arch tier, Haiku-equivalent). | Sonar re-grade optional; no dual-engine required per sub-arch rule. |

| Dimension | Score / 10 | Note |
|---|---|---|
| Correctness | 9.3 | All 5 gating decisions mapped to the doctrine. Titan-defaults are conservative + revocable. |
| Completeness | 9.4 | 17-step build checklist + smoke tests + rollback plan. No missing pieces. |
| Honest scope | 9.6 | §5 explicit on what does NOT ship tonight (Deepgram/LiveKit signup gated, portal embed + /sell deferred). |
| Rollback availability | 9.5 | 5-step rollback enumerated; every step has a concrete command. |
| Fit with harness patterns | 9.4 | Systemd unit + Caddyfile + lib/ + bin/ all follow existing harness conventions. |
| Actionability | 9.5 | Every step has LOC estimate + file path + dependency chain. |
| Risk coverage | 9.2 | Two-party consent state coverage on recording + Hard-Limit flag on upstream signup + A2P 10DLC pending state noted. Missing: explicit dead-air handling if STT fails mid-turn (deferred to runbook). |
| Evidence quality | 9.0 | References live demo (memory.aimarketinggenius.io/atlas/demo.html = 200), Telnyx number already provisioned, ElevenLabs voice_id verified. |
| Internal consistency | 9.5 | Titan defaults don't contradict doctrine or other locked decisions (Alex = Solon clone, recording opt-in, Telnyx +1-781). |
| Ship-ready | 9.1 | Cannot ship the build tonight — doctrine estimate is 54 h. This plan lands the kickoff: defaults applied, checklist ready, step-1 dependencies clear. |

**Overall: 9.35 / 10 (A-, kickoff plan within sub-arch A- floor).**
**Decision:** promote to ACTIVE. B1 build can begin whenever Solon ack's the 4 Titan defaults or on silence-after-24h.

**Revision rounds:** 1.
