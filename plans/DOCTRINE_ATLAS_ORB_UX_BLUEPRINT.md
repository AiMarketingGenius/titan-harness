# Atlas Orb & App UX Blueprint
### AI Marketing Genius — Voice Orb, Desktop App, and Sales Conversation Design

---

> **Audience:** Solon Zafiropoulos / Titan (Claude Code on VPS)
> **Stack doctrine:** Kokoro TTS · faster-whisper STT · Silero VAD · WebRTC AEC3
> **Scope:** UX flows, orb behavior, conversation design, guardrails, implementation checklist

---

## Part 1: Competitive Breakdown

### 1.1 Competitive Analysis Table

| Product | Category | What Works | What Fails | Atlas Lesson |
|---|---|---|---|---|
| **Intercom Fin Voice** | AI customer service + voice orb | WebGL hero + Rive state-machine asset visualizes AI↔customer conversations in real time; Eva Kautz shipped design and production code with Cursor + Figma in parallel — no handoff lag; multi-LLM architecture (retrieval, reranker, summary, escalation-detection models) maintains coherence across task types | CS-only framing; pricing page does not exist because it's a platform feature, not a standalone product; orb is emotionally neutral (service-context appropriate but dull for sales) | Build the orb as a designed artifact, not a UI widget — motion *is* the brand signal. Rive state machine for rapid iteration; WebGL for production fidelity |
| **Drift (Salesloft)** | Conversational marketing / pipeline | High-intent visitor targeting (pricing page, return visitors, IP-resolved account recognition); $180K attributed pipeline from 3 months of deployment; 35% demo conversion lift on pricing page; in-chat calendar booking 3.3× better than form redirects; 55% engagement on ABM-targeted accounts vs. 18% generic | Starts at $2,500/mo with no free trial and no transparent pricing; requires Salesforce for full function; post-Salesloft merger roadmap unclear; purely text chat, zero voice capability; needs 10K+ monthly visitors to generate ROI | AMG needs the targeting logic (high-intent page detection, return visitor recognition) but must deliver it without the $2,500/mo floor — build it natively into Atlas's session context |
| **Bland AI** | Enterprise telephony voice agents | Genuinely human-sounding voice via self-hosted TTS/ASR/LLM stack on dedicated GPUs; voice cloning from a single 1–2 minute MP3, no fine-tuning; conversational pathways (scripted business logic + guardrails); developer-first API with SIP trunking, webhook routing, GPT-4 prompt chaining; handles thousands of concurrent calls | No web orb UI — the "demo experience" is dialing a phone number, not a visual product moment; no visual brand layer at all; purely telephony-native, awkward for live website demos; enterprise pricing wall | The voice infrastructure quality bar Bland sets is the reference point. Atlas should match that audio fidelity but wrap it in a designed visual experience Bland doesn't attempt |
| **ElevenLabs Conversational AI Widget** | Embeddable voice widget | Trivial embed (Webflow, custom sites); knowledge base grounding; voice cloning; multilingual; strong API for low-latency streaming; credit-based pricing accessible at any scale | Generic widget chrome — a plain button with a border; zero state-machine animation; no visual identity; feels bolted onto the page rather than native to it; purely a TTS/conversation engine, not a full designed product | ElevenLabs sets the TTS quality floor. The widget is the cautionary tale: embed-and-forget is not enough. AMG needs an orb that owns the page |
| **Hume AI EVI** | Emotionally expressive voice API | Prosody/intonation modeling via the Empathic Voice Interface (EVI); emotion-aware response generation; speech-to-speech pipeline that analyzes user tone and mirrors affect; SOC2 + HIPAA options; straightforward tiered per-minute pricing | No visual UI layer whatsoever — API only, requires full custom build to get any interface; English-focused for advanced emotional modes; emotional tuning requires significant effort to align with specific brand voice | Emotional prosody modeling is a future Atlas differentiator — not in V1 but worth tracking. The complete absence of UI is the lesson: the conversation engine alone is not a product |
| **Synthflow** | No-code telephony voice agent builder | Visual node-based flow designer (drag-and-drop); deterministic conversation logic; variable collection nodes; branching; appointment booking blocks; ElevenLabs voice integration; sub-100ms latency telephony stack; white-label for agencies | Purely telephony — no web orb, no visual identity layer; no-code constraint means hitting complex dynamic logic requires workarounds; zero concept of an orb or ambient presence on a website; call handling is scripted, not adaptive | Synthflow's node-based flow designer is worth studying for Atlas's conversation state architecture, even if Atlas is implemented in code rather than a visual builder |
| **Qualified** | B2B revenue platform (Salesforce-native) | Account-based targeting via IP intelligence; instant rep routing; intent signals from 6sense/Demandbase integration; deep Salesforce embedding for pipeline attribution and routing; enterprise-grade territory management | Requires Salesforce (hard dependency); custom enterprise pricing typically reaches high five to six figures annually; no voice orb or ambient web presence; SDR availability required — humans must be online for the platform to convert | ABM targeting logic is directionally right for Atlas. Hard Salesforce dependency and enterprise pricing wall are exactly what Atlas avoids by being purpose-built for AMG |
| **ShowMe AI** | AI inbound sales rep (avatar + voice) | Multi-agent architecture: conversation agents, evaluator agents, creator agents coordinated by a workflow layer managing the full lead-to-close journey; decomposes a single sales call into specialized sub-agents (greeting, qualifying, pitching) to manage latency; adding a HeyGen avatar dramatically changed prospect engagement; confidence scoring and frustration detection trigger real-time human handoff | Avatar video is computationally heavy — real-time video calls with avatar incur significant latency; awkward on mobile; HeyGen dependency adds infrastructure complexity; not embeddable as an ambient orb on a marketing site | ShowMe's multi-agent evaluation loop (confidence scoring + sentiment to trigger handoff) is a direct blueprint for Atlas's guardrail layer. The decomposed sub-agent pattern is a latency management technique worth adopting |
| **Voiceflow** | Multi-LLM flow builder (design-to-production) | Collaboration tools for designer-developer handoff; visual prototyping-to-production pipeline; CMS integration; multi-LLM routing; testing simulator; strong for teams with mixed technical skills | Generic UI — no visual identity layer, no orb, no ambient web presence; usage-based credit model complex to forecast; not an end-to-end voice platform (requires separate telephony); designed for building agents, not delivering a designed product experience | Voiceflow's prototyping approach is useful for conversation design iteration. As a shipped experience it offers nothing Atlas aspires to be — it's a tool, not a product |

---

### 1.2 Deep Analysis — Top 4 Competitors

#### Intercom Fin Voice

Intercom's Fin Voice page represents the current benchmark for AI product presentation on the web. The WebGL hero — designed by Eva Kautz with Cursor and Figma, shipped directly to production — demonstrates that [the Rive-animated orb is not decorative but functional](https://www.linkedin.com/posts/evatkautz_design-code-recently-launched-fin-activity-7414275948038111232-zfUJ): it visualizes the AI↔customer conversation state through motion, making the product legible at a glance. The Rive asset runs as a state machine, not a looping animation, which means it responds to real UI events rather than playing back a fixed timeline. The [Rive engine](https://rive.app) (used by Spotify, Duolingo, and Intercom) reports 4× faster production cycles and 90% smaller file sizes versus After Effects/Lottie workflows, and it runs at 120fps via GPU-accelerated vector rendering. This is the design quality level Atlas must match.

The critical weakness: Fin is a customer service product. Its orb is emotionally neutral and branded around resolution, not aspiration. It doesn't sell — it serves. Atlas operates in the opposite register: the orb should feel like talking to a senior marketing partner, not a support queue.

#### Drift (now Salesloft)

[Drift's conversational marketing platform](https://workflowautomation.net/reviews/drift) remains the most evidence-based proof that chat-native qualification converts. The $180K attributed pipeline in three months, 35% demo conversion lift on the pricing page, and 3.3× booking improvement over form redirects are the benchmark numbers Atlas is being built to beat — at a fraction of Drift's $2,500/mo floor. Drift's targeting logic — recognizing pricing page visitors, return visitors, and IP-resolved target accounts — is the correct visitor segmentation model. The UX failure is complete absence of voice and a generic chat widget UI that hasn't meaningfully evolved. The post-Salesloft merger uncertainty is a structural weakness Atlas can exploit: Drift's B2B customers are actively evaluating alternatives.

#### Bland AI

[Bland AI](https://callbotics.ai/blog/bland-ai-review) occupies the enterprise telephony position and gets voice quality right: self-hosted TTS/ASR/LLM stack on dedicated GPUs, voice cloning from a 1–2 minute audio sample, and programmatic call flow control via API. The "conversational pathways" feature — scripted business logic + guardrails that constrain the LLM to approved topic areas — is the telephony equivalent of what Atlas's guardrail system needs to implement. The fundamental gap is product presentation: Bland's demo experience is a phone call. There is no visual layer, no orb, no ambient presence. The experience of *evaluating* Bland is itself a telephony call, which creates a cold and undesigned first impression. Atlas fills exactly this gap: the same voice quality but wrapped in a premium visual experience designed for the web.

#### ShowMe AI

[ShowMe AI](https://www.producttalk.org/building-ai-sales-reps-showme/) is the most architecturally sophisticated inbound sales AI currently in production. Founded April 2025, it decomposes a sales conversation into multiple specialized sub-agents — greeting, qualifying, pitching, next steps — coordinated by a workflow orchestrator managing the full lead-to-close journey across days. Adding a [HeyGen](https://www.heygen.com) avatar dramatically changed prospect engagement by giving the AI a visual body that triggers human social cognition. The evaluator agents that score every call for quality, sentiment, and confidence — triggering real-time human handoff when thresholds drop — are a direct design blueprint for Atlas's guardrail layer. The weaknesses are real: HeyGen avatar video is computationally heavy and latency-sensitive, awkward on mobile, and adds dependency complexity. Atlas sidesteps avatar video entirely in favor of an orb — lower computational cost, higher design expressiveness, mobile-native.

---

## Part 2: Atlas Orb & App Blueprint

### 2.1 Information Architecture

#### Flow A: New Visitor → First Question → Qualified Lead → Booked Call

1. **Arrival** — Visitor lands on AMG homepage or service page. Orb is in Idle state: slow rotation, breathing pulse, micro-copy "Ask me anything about AI marketing" fades in after 8 seconds.

2. **Activation** — Visitor taps/clicks orb or speaks. Orb transitions to Listening (200ms ease-out). Mic opens. Silero VAD activates.

3. **Atlas opener (always first):**
   > *"Hey — welcome to AI Marketing Genius. Quick question before I dive in: what's going on with your marketing right now? Are you starting from scratch, trying to fix something that's not working, or looking to scale what's already working?"*

4. **Q1 branch processing** — Atlas listens, classifies response into Branch A (starting), B (fixing), or C (scaling). Adjusts subsequent framing accordingly.

5. **Q2 — Authority signal:**
   > *"Got it. Are you the one running the day-to-day on this, or do you have a team you're working with?"*

6. **Q3 — Budget range (soft):**
   > *"Just so I can point you in the right direction — are you thinking more 'pilot budget' territory, under five figures, or are you ready to go bigger if the ROI is there?"*

7. **Q4 — Timeline / urgency:**
   > *"When does this need to be moving? Are you in 'figure it out by end of month' mode, or is this more of a strategic planning thing?"*

8. **Q5 — Service fit:**
   > *"One more — which of these sounds most like your problem: getting found online — SEO and content — converting the traffic you already have with ads and landing pages, or automating follow-up and nurture with AI agents?"*

9. **Pricing presentation** — Atlas identifies the engagement type from qualification responses, applies the Anchor → Range → Value → CTA pattern (see Part 3.2).

10. **CTA delivery:**
    > *"Want me to put together a quick audit so Solon can give you a specific number? I can drop a booking link right here — takes about 15 minutes on his calendar."*

11. **Calendly embed** — react-calendly drops inline in the conversation thread. Visitor selects time.

12. **Confirmation** — Orb transitions to a warm confirmation state. Atlas says:
    > *"Perfect — you're booked. Solon will have a look at your site before the call. Check your email for confirmation."*

13. **Post-booking** — Orb returns to Idle with modified micro-copy: "See you at [time]." Conversation logged with BANT score, qualification signals, and escalation flags.

---

#### Flow B: Existing Client → Quick Answers / Campaign Check

1. **Recognition** — Session token or cookie identifies returning user. Atlas cross-references user ID against conversation history. If recognized, orb activates with a differentiated greeting cadence.

2. **Returning greeting variant A (known client, recent activity):**
   > *"Good to hear from you again. What are you working through today — campaign questions, something new, or a quick check-in?"*

3. **Returning greeting variant B (known client, no recent activity):**
   > *"Welcome back. It's been a minute — how's the [last discussed campaign / service type] going? Anything you want to dig into?"*

4. **Topic shortcuts** — Atlas surfaces 2–3 contextual topics based on conversation history as quick-tap chips: "Campaign performance," "New service question," "Something else." Reduces time-to-answer for repeat users.

5. **Resolution** — Atlas answers from AMG knowledge base + conversation history context. No BANT questions asked — client is already qualified.

6. **Upsell moment (conditional)** — If the client's question touches a service area outside their current engagement, Atlas surfaces it naturally:
   > *"That's actually something Solon could layer in on top of what you're already running — the AI Stack add-on. Want me to put a 15-minute check-in on his calendar?"*

7. **Escalation to Solon** — If client mentions contract, pricing change, dissatisfaction, or enterprise expansion, Atlas hard-escalates immediately (see Guardrail Rule 3).

---

#### Flow C: Founder "Wow" Live Demo Flow

*Optimized for Solon running a live demo on screen share or in-person. Target impression window: 90 seconds.*

1. **Solon kicks it off** by saying to the prospect: *"Let me show you what Atlas can do. I'll just ask it a question the way a visitor would."*

2. **Solon speaks to orb:** *"Hey Atlas, what does AMG actually do for a SaaS company trying to grow inbound?"*

3. **Atlas responds (demonstrates depth, not list):**
   > *"Great question. For a SaaS company, the highest-leverage play is usually a combination of SEO-driven content that compounds over time and conversion optimization on the pages that already have traffic. AMG handles both — we build the content engine, the distribution system, and the AI automation layer that makes sure every lead gets followed up immediately. Depending on where you are in the funnel, we typically start with a focused audit, then move into a full retainer once we've validated the approach. Most clients in that setup invest between $4,000 and $8,000 a month and see meaningful inbound lift within 90 days."*

4. **Prospect reacts** — Atlas has demonstrated: (a) domain knowledge, (b) service framing, (c) pricing range volunteered proactively, (d) timeline credibility.

5. **Atlas follows with a smart question back:**
   > *"Quick question — are you mostly trying to generate more pipeline, or is converting the pipeline you already have the bigger priority right now?"*

6. **This is the "holy shit" moment** — the prospect realizes Atlas just asked a qualifying question that a senior strategist would ask, unprompted.

7. **Atlas closes the demo loop:**
   > *"If you want to go deeper, I can drop Solon's calendar right here — he's usually good for a 20-minute call within 48 hours. Want that link?"*

8. **Solon steps back in** if the prospect says yes, or allows Atlas to complete the booking.

*Total time to this point: 60–90 seconds. The prospect has heard strategic depth, pricing, a timeline, and a specific next step — without Solon saying anything after the initial prompt.*

---

### 2.2 Screen & State Map

#### App Screens

| Screen | Purpose | Key Components | State Dependencies |
|---|---|---|---|
| **Home / Landing** | First impression, orb idle, visitor engagement | Orb (Idle), micro-copy prompt, minimal chrome | Orb: Idle |
| **Active Conversation** | Live voice + text interaction | Orb (Listening/Thinking/Speaking), transcript scroll (Framer Motion), mute button | Orb: Listening / Thinking / Speaking |
| **Pricing Reveal** | Inline pricing display after BANT completion | Pricing tier card (animated entrance), value prop line, CTA button | Orb: Speaking → Idle transition |
| **Booking Confirmation** | Post-Calendly booking confirmation | Confirmation card, Atlas confirmation line, calendar details | Orb: Idle (warm variant) |
| **Existing Client Dashboard** | Returning client recognition + history | Prior conversation summary, topic shortcuts, quick-access CTA | Orb: Idle (returning variant) |
| **Settings / Admin** | Solon-only view: transcripts, BANT scores, escalation flags | Live feed of conversations, qualification score column, escalation flag badges, Calendly booking confirmations | Backend only; orb not displayed |

#### Orb States

| State | Visual | Animation | Copy Prompt / System Behavior |
|---|---|---|---|
| **Idle** | Deep navy sphere (#0A0F1E), subtle electric blue glow (#2563EB at 30% opacity), white-ice surface shimmer (#E8F4FD) | Rotation: 0.003 rad/frame; breathing pulse: scale 0.98 → 1.02 over 3s ease-in-out-quad; outer glow opacity 0.3 → 0.6 over 4s | "Ask me anything about AMG" [after 8s silence]: "Need help with marketing?" [after 20s]: "Tap to start" |
| **Listening** | Sphere brightens, glow expands, surface becomes reactive | Rotation: 0.008 rad/frame; Web Audio API AnalyserNode on mic input → FFT 256-bin → vertex displacement maps to amplitude; glow opacity snaps to 0.9; outer ring tightens | No copy — mic is open. VAD detecting speech. STT buffer accumulating. |
| **Thinking / Processing** | Cooler palette shift, inner core swirls, muted outer glow | Rotation: 0.005 rad/frame; 3 offset sinusoidal arcs animating inner core; pulsing halo 1.0s period; palette shifts toward cooler blue-purple (#7C3AED influence increases) | [After 2.5s]: "Give me just a moment..." — spoken by Atlas. Hard timeout at 5s → Error state. |
| **Speaking** | Full audio reactivity, glow flares on syllable peaks | AnalyserNode on TTS audio output; vertex displacement maps to frequency bins 20Hz–4kHz; glow flares on peak amplitude; rotation: 0.006 rad/frame | No micro-copy — Atlas is speaking. Barge-in detection active: user speech during TTS → interrupt, switch to Listening immediately. |
| **Error / No-response** | Dim palette, slow pulse only | Rotation halts; sphere dims to 60% opacity; single slow pulse (2s period) | "Didn't catch that — tap to try again" [displayed as text overlay, also spoken] |

---

### 2.3 Detailed Orb UX Spec

#### Geometry & Rendering

**Shape:** Perfect sphere, `SphereGeometry(1, 128, 128)` — 128 segments for smooth vertex displacement at the poles. Diameter: 200px desktop, 140px mobile (CSS `width: clamp(140px, 15vw, 200px)`).

**Renderer:** Three.js `WebGLRenderer` with `antialias: true`, `alpha: true` (transparent background), `powerPreference: 'high-performance'`. Canvas injected into React component via `useRef`.

**Shader approach:** Custom `ShaderMaterial` with vertex and fragment shaders. Do not use `MeshPhongMaterial` or `MeshStandardMaterial` — they cannot produce the organic fluid displacement required. Reference implementation: [aguscruiz/voiceorb](https://github.com/aguscruiz/voiceorb) on GitHub demonstrates the complete Three.js + custom GLSL vertex displacement proof-of-concept with `SphereGeometry`, `ShaderMaterial`, simplex noise vertex displacement, and Fresnel edge glow in fragment shader.

**Color palette (Atlas):**
- Core sphere: `#0A0F1E` (deep navy)
- Glow / electric accent: `#2563EB` (electric blue)
- Surface shimmer: `#E8F4FD` (white-ice)
- Inner core / thinking mode accent: `#7C3AED` (purple undertone)

**GLSL vertex shader pattern:**
```glsl
uniform float uTime;
uniform float uAudioLevel;  // 0.0 → 1.0 from AnalyserNode
uniform float uState;       // 0=idle, 1=listening, 2=thinking, 3=speaking

// Simplex noise displacement
float noise = snoise(position * 1.5 + uTime * 0.3);
float displacement = noise * (0.05 + uAudioLevel * 0.25);
vec3 newPosition = position + normal * displacement;
gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
```

**GLSL fragment shader pattern:**
```glsl
// Fresnel edge glow
float fresnel = pow(1.0 - dot(vNormal, vViewDirection), 3.0);
vec3 glowColor = mix(uCoreColor, uGlowColor, fresnel);
float glowIntensity = 0.3 + uAudioLevel * 0.7;
gl_FragColor = vec4(glowColor * glowIntensity, 1.0);
```

#### State Animations (Precise)

**Idle:**
- `rotation.y += 0.003` per frame in `requestAnimationFrame` loop
- Breathing: `THREE.MathUtils.lerp(scale, targetScale, 0.02)` where targetScale oscillates 0.98 → 1.02 via `Math.sin(uTime / 3.0) * 0.5 + 0.5`
- `uAudioLevel` driven to 0.0 (no mic input)
- Outer glow: CSS `box-shadow` on canvas wrapper, opacity oscillates 0.3 → 0.6 over 4s via keyframe animation

**Listening:**
- `rotation.y += 0.008` per frame
- `AnalyserNode.getByteFrequencyData(dataArray)` on each frame; compute RMS from bins 10–40 (voice frequency range) → normalize 0.0–1.0 → set `uniforms.uAudioLevel.value`
- Vertex displacement amplifies with audio level; surface becomes "active"
- Smooth interpolation: `currentLevel = currentLevel * 0.85 + rawLevel * 0.15` (prevents jarring)
- Glow CSS opacity: 0.9

**Thinking:**
- `rotation.y += 0.005` per frame
- Three sinusoidal arc overlays rendered as `THREE.Line` objects with `sin(uTime * 1.2 + offset)` paths
- Palette uniform shifts: `uGlowColor` blends toward `#7C3AED` (purple)
- `uAudioLevel` driven to low constant 0.1 (gentle background pulse)
- Halo pulse: 1.0s period CSS animation on outer glow element

**Speaking:**
- `AnalyserNode.getByteFrequencyData(dataArray)` on TTS audio output element (connect to `AudioContext.createMediaElementSource`)
- Frequency bins 0–180 (20Hz–4kHz voice range) → average → normalize → `uniforms.uAudioLevel.value`
- On syllable peak (level > 0.7): brief glow flare — `uGlowIntensity` spikes to 1.5 for 80ms then decays
- `rotation.y += 0.006` per frame

#### Micro-Copy Prompts (by State)

| Trigger | Copy | Delivery |
|---|---|---|
| Idle, t=0 | "Ask me anything about AMG" | Fade in over 600ms |
| Idle, t=8s | "Need help with marketing?" | Crossfade replace |
| Idle, t=20s | "Tap to start a conversation" | Crossfade replace |
| User finishes speaking | [silence — Atlas responds, no prompt] | — |
| Atlas finishes response, 2s silence | "Want me to dig deeper into that?" | Fade in |
| Error / empty STT | "Didn't catch that — tap to try again" | Instant display + spoken |

#### Transition Timings

| Transition | Duration | Easing | Notes |
|---|---|---|---|
| Idle → Listening | 200ms | ease-out | Rotation ramp via lerp, glow brighten |
| Listening → Thinking | 150ms | ease-in-out | Mic closes, STT committed, swirl starts |
| Thinking → Speaking | 100ms | ease-out | Near-instant — no perceptible gap |
| Speaking → Idle | 600ms | ease-in | Do not snap; TTS end event triggers 600ms decay |
| Any → Error | 300ms | ease-in | Dim + halt |

---

## Part 3: Conversation + Pricing Behavior

### 3.1 Discovery Question Framework

The [BANT framework](https://blog.coffee.ai/using-bant-framework-b2b-sales/) — Budget, Authority, Need, Timeline — is implemented as a conversational arc, not an interrogation checklist. Questions are woven into natural dialogue. Atlas never runs through them sequentially without acknowledgment — each question lands *after* processing the previous answer. Per BANT best practice, budget is not the first question; need and context come first to establish value before investment is discussed.

**Q1 — Opener / Context (always asked first)**

> *"Quick question before I dive in — what's going on with your marketing right now? Are you starting from scratch, trying to fix something that's not working, or looking to scale what's already working?"*

| Answer Type | Branch | Atlas Pivot |
|---|---|---|
| "Starting from scratch" / early stage | Branch A — Awareness | SEO foundation, content strategy, brand visibility — "getting found" framing |
| "Fix something" / not working | Branch B — Audit | Diagnosis framing: "Let me ask a few more things and I'll tell you exactly what I think is broken" |
| "Scale what's working" / growth | Branch C — Performance | Paid media, conversion, automation — "acceleration" framing |

**Q2 — Authority Signal (conversational)**

> *"Got it — are you the one running the day-to-day on this, or do you have a team you're working with?"*

| Answer | Branch | Atlas Pivot |
|---|---|---|
| Solo / founder-led | Branch A | Position AMG as scalable team replacement: "We essentially become your marketing department" |
| Has a team | Branch B | Position AMG as strategy + AI layer: "We work with your team and give them leverage they don't have right now" |

**Q3 — Budget Range (soft)**

> *"Just to point you in the right direction — are you thinking more 'pilot budget' territory, under five figures, or are you ready to go bigger if the ROI is there?"*

| Answer | Branch | Atlas Pivot |
|---|---|---|
| Pilot / cautious / "depends" | Branch A | AMG entry packages ($1,500–$3,000/mo SEO Foundation; $500 audit) |
| "Ready to invest" / serious | Branch B | Full retainer + custom AI stack ($4,000–$15,000/mo range) |

**Q4 — Timeline / Urgency**

> *"When does this need to be moving? Are you in 'figure it out by end of month' mode, or is this more of a strategic planning thing?"*

- **Urgent (≤30 days):** Atlas flags high urgency internally, shortens discovery, moves to pricing + CTA faster
- **Strategic (60–90 days):** Atlas positions audit as a first step with no pressure

**Q5 — Service Fit**

> *"One more — which of these sounds most like your problem: getting found online — SEO and content — converting the traffic you already have with ads and landing pages, or automating the follow-up and nurture with AI agents and email?"*

- Maps directly to AMG service tier selection for pricing presentation

---

### 3.2 Pricing Presentation Pattern

**Never lead with a number.** Always: Anchor → Range → Value → CTA.

The [escalation design principle](https://www.bucher-suter.com/escalation-design-why-ai-fails-at-the-handoff-not-the-automation/) applies here: pricing missteps — giving a number without context, quoting out of range, or implying guarantees — are the handoff failures that damage trust. Atlas anchors context before the number lands.

**Pattern in full:**

1. **Anchor** — Name the engagement type:
   > *"Based on what you've described, this sounds like a [SEO Foundation / Performance Content / AI Marketing Stack / Full Partner Retainer] engagement."*

2. **Range** — Deliver the range:
   > *"Most clients in your situation invest between [$X and $Y per month]."*

3. **Value** — One ROI sentence:
   > *"For context, [relevant proof point: first-page rankings / 3× organic traffic / automated follow-up within 5 minutes of every lead]."*

4. **CTA** — Move to next step:
   > *"Want me to set up a quick audit so Solon can give you a specific number? It's a 15-minute call and there's no obligation."*

**AMG Service Pricing Tiers (Atlas knowledge base — exact):**

| Service | Monthly Range | Included |
|---|---|---|
| SEO Foundation | $1,500–$3,000/mo | Keyword research, on-page optimization, 4 content pieces/mo, monthly reporting |
| Performance Content | $2,500–$5,000/mo | Full content strategy, 8+ pieces/mo, link building, E-E-A-T authority building |
| Paid + Conversion | $2,000–$4,500/mo | Google/Meta ads management, landing pages, CRO testing |
| AI Marketing Stack | $4,000–$8,000/mo | Custom AI agents, marketing automation, full-funnel AI integration |
| Full Retainer (AMG Partner) | $7,500–$15,000/mo | All services + fractional CMO |
| One-time Audit | $500–$1,500 | Deep site audit, competitive analysis, roadmap |

---

### 3.3 Three Sample Conversation Transcripts

#### Transcript 1: Cold E-Commerce Visitor, Price-Shopping

**Visitor:** How much does SEO cost?

**Atlas:** Good question — and I'll give you a real number, not a runaround. But the range is wide enough that the right answer depends on a few things. What's going on with your SEO right now — are you starting from zero, or do you already have some rankings and you're trying to do more with them?

**Visitor:** We have a Shopify store, been around two years, getting some organic traffic but it's not growing.

**Atlas:** Got it — so you've got a foundation, it's just not compounding. Are you the one running marketing day-to-day, or do you have someone on your team handling it?

**Visitor:** It's just me.

**Atlas:** Makes sense. Are you thinking a pilot-size investment to test it out — under five figures a month — or are you ready to go bigger if you see the ROI?

**Visitor:** Probably something reasonable to start. I'm not trying to spend five thousand a month right off the bat.

**Atlas:** Totally fair. Last question — are you more focused on getting found for more search terms, converting the traffic you already have, or both?

**Visitor:** Mostly getting found. My conversion rate is okay, just not enough people landing on the site.

**Atlas:** Okay — based on everything you've said, this is a clean SEO Foundation engagement. Two-year-old Shopify store, existing rankings, solo operator who needs a content and optimization engine without a huge team. Most clients in that exact situation invest between $1,500 and $3,000 a month. For context, our SEO clients in e-commerce typically see meaningful first-page movement within 90 days, and compounding organic traffic growth through month six. Want me to put together a quick audit so Solon can look at your specific site and give you a tighter number?

**Visitor:** Yeah, I'd be interested.

**Atlas:** Perfect. Here's Solon's calendar — grab a 15-minute slot that works for you. He'll review your site before the call so you're not starting from scratch explaining it.

*[Calendly embed appears inline]*

---

#### Transcript 2: B2B Founder, High-Intent (AI Automation)

**Visitor:** I need AI agents for my sales team.

**Atlas:** You're in the right place — that's actually one of AMG's most in-demand services right now. Tell me a bit more: are you looking to automate inbound follow-up, outbound prospecting, or the full pipeline from lead to close?

**Visitor:** Mainly inbound. We're getting leads from content but our reps are slow to follow up and we're losing deals.

**Atlas:** Classic conversion gap — fast follow-up is the difference between a deal and a no-show. Are you running this with a team, or is it mostly you managing the reps?

**Visitor:** I have five SDRs.

**Atlas:** Got it. And in terms of investment — are you thinking something scoped and controlled, or are you open to a full AI stack if the ROI math works out?

**Visitor:** If it actually works, we'll invest. We've been burned by tools before.

**Atlas:** Understood — and that's a fair instinct. This is a full AI Marketing Stack engagement. What AMG builds is a custom inbound AI agent that follows up with every lead within five minutes, qualifies them before an SDR touches it, and only routes the warm ones. Your reps get better leads and spend zero time chasing cold follow-ups. Most clients in your situation invest between $4,000 and $8,000 a month. For context, the typical outcome is a 40–60% reduction in lead response time and a measurable lift in SDR productivity within the first 60 days.

**Visitor:** That's expensive.

**Atlas:** I get it — it's a real investment. The frame that helps: if your SDRs are currently spending 30% of their time on cold follow-up that doesn't convert, you're already paying for it. This replaces that cost with a system that scales without headcount. That said, I don't want to pitch you a number without Solon seeing your actual setup. A 15-minute audit call is the right next step — he can tell you if this makes sense for your volume, and give you a specific build scope. Want that?

**Visitor:** Yeah, set it up.

**Atlas:** Done. Grab any slot here — Solon will be prepared.

*[Calendly embed appears inline]*

---

#### Transcript 3: Browser / "Just Looking" Visitor

**Visitor:** Just browsing.

**Atlas:** No problem at all — take your time. I'm here if anything sparks a question. One thing I'm curious about: is marketing something that's top of mind right now, or is it more of a "someday" thing for you?

**Visitor:** I mean, it's something I think about. We need to do better but haven't figured out the approach yet.

**Atlas:** That's exactly the stage where a lot of clients come to AMG — not a crisis, just a sense that there's more leverage to be found. What's the business — are you selling to consumers, other businesses?

**Visitor:** B2B. Software company.

**Atlas:** B2B SaaS is AMG's core focus, so you're in the right spot. The two things that move the needle most for companies at the "we need to do better" stage are usually SEO-driven content that builds compounding inbound and an AI layer that makes sure no lead falls through the cracks. No pressure at all right now — but I'll leave a link to a couple of our case studies in B2B SaaS so you can see the kind of results we've produced. And if you ever want to talk specifics, just come back and ask. The calendar is always open.

*[Case study links appear as a card in the transcript thread]*

**Atlas:** Come back anytime — I'll remember where we left off.

---

### 3.4 Guardrails & Escalation Rules

Voice AI [safety is an architecture problem, not a model problem](https://www.gladia.io/blog/safety-voice-ai-hallucinations). Guardrails must be enforced at the orchestration layer — prompt engineering alone is insufficient. The following rules are implementable policy conditions, not suggestions.

#### Escalation Triggers (condition → action)

| # | Condition | Atlas Action |
|---|---|---|
| 1 | Visitor mentions a specific budget over $10K/mo | *"That sounds like a conversation worth having with Solon directly. Want me to get you on his calendar?"* — Calendly CTA, no further pricing discussion |
| 2 | Visitor describes enterprise-scale need (100+ person company, multi-country, compliance requirements) | Immediate escalation: *"This is a build that Solon would want to scope personally. Let me get you connected."* |
| 3 | Visitor is an existing AMG client (identified by session token, stated directly, or recognized by conversational context) | Skip all discovery: *"Great to hear from you — let me get Solon looped in directly."* No renegotiation via Atlas |
| 4 | Visitor asks about custom AI development outside standard AMG service tiers | *"That's a custom build conversation — I want to make sure I don't give you inaccurate scope or pricing. Solon can speak to that directly in 15 minutes."* |
| 5 | Visitor expresses frustration or distrust ("I've been burned before," "I don't trust AI," "this feels like a scam") | De-escalate tone, do not defend, immediately offer human: *"That's a fair concern — the best thing I can do is connect you with Solon directly. No pitch, just a conversation."* |
| 6 | 4+ conversation turns with no qualification progress ("stuck" pattern — topic loops, refusal to answer questions, off-topic) | Soft CTA: *"Let me not waste your time with more questions. If it ever makes sense to talk specifics, Solon's calendar is right here."* |

#### Never Say (hard prohibition)

- Specific guarantees on rankings, ROI, or timelines (e.g., "you will rank #1," "guaranteed 3× traffic")
- Any competitor name — never reference, compare, or position against named competitors
- "I'm just an AI" or any disclaimer of AI status — Atlas speaks as a confident entity with agency
- Any pricing number without a context anchor preceding it
- Fabricated case study numbers or testimonials not present in the AMG knowledge base

#### Confidence Scoring Rule

If RAG retrieval confidence for any AMG-specific claim is below 0.7:
> *"Let me be honest — I want to make sure I give you accurate information on that. Solon can speak to that directly in 15 minutes."*

This is enforced at the LLM prompt layer: every RAG retrieval result must include a confidence score; the LLM is instructed to trigger this exact response below threshold. Per [Klarna's escalation implementation](https://www.bucher-suter.com/escalation-design-why-ai-fails-at-the-handoff-not-the-automation/), confidence-gated escalation allows Atlas to handle higher volume accurately by defining and respecting its own boundaries.

---

## Part 4: Implementation Checklist for Titan

### 4.1 Orb Component Checklist (Web)

1. Create `AtlasOrb` React component using Three.js `WebGLRenderer` mounted on an HTML5 Canvas via `useRef` and `useEffect`
2. Implement 4-state state machine with Zustand store: `idle | listening | thinking | speaking` — expose state to parent via `useOrbStore` hook
3. Connect `idle` animation: `rotation.y += 0.003` per frame; breathing scale pulse via `Math.sin(uTime)` mapped to 0.98–1.02 via `THREE.MathUtils.lerp`; `uAudioLevel` clamped to 0.0
4. Connect `listening` animation: `getUserMedia` → `AudioContext.createMediaStreamSource` → `AnalyserNode` (FFT size 256) → `getByteFrequencyData` each frame → average bins 10–40 → normalize → `uniforms.uAudioLevel.value`; smooth with `currentLevel = currentLevel * 0.85 + rawLevel * 0.15`; `rotation.y += 0.008`
5. Connect `thinking` animation: 3 sinusoidal arc `THREE.Line` objects with phase offsets; `uGlowColor` lerp toward `#7C3AED`; halo CSS pulse 1.0s period; `rotation.y += 0.005`
6. Connect `speaking` animation: connect TTS `<audio>` element to `AudioContext.createMediaElementSource` → `AnalyserNode` → FFT → bins 0–180 → normalize → `uniforms.uAudioLevel.value`; glow flare logic: if level > 0.7, spike `uGlowIntensity` to 1.5, decay 80ms; `rotation.y += 0.006`
7. State transitions: implement `transitionTo(newState)` with GSAP or manual lerp — 200ms idle→listening, 150ms listening→thinking, 100ms thinking→speaking, 600ms speaking→idle; never snap between states
8. Add micro-copy prompt overlay as absolute-positioned div below orb; Framer Motion `AnimatePresence` for fade in/out; delay logic: 8s → first swap, 20s → second swap; reset on any user interaction
9. Mobile responsive: `clamp(140px, 15vw, 200px)` on canvas container; tap event listener maps to click; Three.js `renderer.setPixelRatio(window.devicePixelRatio)` for retina
10. Expose `setOrbState(state: OrbState)` on the Zustand store; parent conversation engine dispatches state changes via this interface

### 4.2 Conversation Engine Checklist

11. Wire Atlas system prompt with: (a) AMG knowledge base — services, exact pricing tiers, case study outcomes, FAQs; (b) BANT 5-question discovery sequence with branching logic; (c) pricing presentation pattern (Anchor → Range → Value → CTA) enforced as a prompt constraint; (d) all guardrail conditions as explicit IF/THEN rules in system prompt
12. Implement RAG over AMG docs (service pages, case studies, FAQs, testimonials) using vector embeddings (OpenAI embeddings or sentence-transformers); cosine similarity retrieval; confidence score = top-result similarity score; threshold 0.7 triggers escalation response
13. Implement escalation trigger detection: check each of the 6 guardrail conditions after every user turn; on trigger, insert Calendly CTA as a special message type in conversation state; set orb to Idle; prevent further qualification questions
14. Store conversation state in session: track array of `{question: BANTQuestionKey, asked: boolean, answer: string}`, qualification score (0–4 integer, incremented on each clear signal received), user signals object `{budget: string | null, authority: string | null, need: string | null, timeline: string | null}`
15. Implement "stuck" detection: after each turn, check if `turnsWithoutProgress >= 4` — define "progress" as any BANT dimension answered; on trigger, insert soft CTA message, log escalation flag to admin view

### 4.3 Voice Pipeline Checklist (per Doctrine v1.0)

16. STT: faster-whisper with Silero VAD (Phase A config per doctrine); VAD gates STT processing — only send audio to whisper when Silero detects speech; use `faster-whisper` large-v3 model for accuracy; return transcript + confidence score
17. TTS: Kokoro on GPU VPS (per doctrine); stream audio chunks via WebSocket to browser; play via Web Audio API for AnalyserNode connection; do not use `<audio>` src directly — pipe through AudioContext for reactivity
18. AEC: WebRTC AEC3 (browser-side per doctrine); configure via `getUserMedia` constraints: `{ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } }`; AEC3 runs natively in Chromium-based browsers
19. Barge-in: on every frame during Speaking state, monitor AnalyserNode on mic input (separate from TTS analyser); if mic RMS > threshold for 200ms → stop TTS audio, flush TTS buffer, dispatch `setOrbState('listening')`; log barge-in event
20. Turn-taking: after STT returns transcript, apply 300–500ms pre-response delay (randomized in range, prevents robotic instant-response); send to LLM; apply 200ms buffer after LLM response before TTS begins; never start TTS within 100ms of user stop

### 4.4 Desktop App Checklist (Solon OS)

21. Port `AtlasOrb` component to Electron main window via `BrowserWindow` with transparent background and `vibrancy: 'ultra-dark'` on macOS; share all Three.js and conversation engine code via npm workspace or monorepo
22. Add `DEMO_MODE` environment flag: when true, skip all BANT discovery questions, lead immediately with AMG depth demonstration (Flow C), surface pricing range proactively; demo mode activatable via admin toggle in Settings screen
23. Add keyboard shortcut `Cmd+Shift+A` (macOS) / `Ctrl+Shift+A` (Windows) via Electron `globalShortcut.register` to toggle Atlas panel visibility
24. Sync conversation context between web orb and desktop via user session token stored in browser localStorage (web) and Electron `store` (desktop); on session token match, both surfaces share the same conversation history and BANT qualification state
25. Admin view for Solon — dedicated Electron window or web-only admin route at `/admin`: real-time WebSocket feed of active conversations, columns for qualification score (0–4), BANT dimensions filled, escalation flags (boolean), booking status; auto-refresh every 5 seconds

### 4.5 Recommended Libraries

| Library | Package | Role | Notes |
|---|---|---|---|
| **Three.js** | `three` | 3D WebGL sphere, custom GLSL shader orb | Use `SphereGeometry(1, 128, 128)` + `ShaderMaterial`; reference [aguscruiz/voiceorb](https://github.com/aguscruiz/voiceorb) for simplex noise vertex displacement + Fresnel fragment pattern |
| **Rive** | `@rive-app/react-canvas` | Alternative orb approach: state-machine animation from design tool | [rive.app](https://rive.app) — 4× faster production, 90% smaller files vs. Lottie; use if team prefers design-tool workflow over raw GLSL; Intercom Fin uses this for their orb |
| **Framer Motion** | `framer-motion` | UI micro-animations around orb | Text fade-in/out (micro-copy), CTA card entrance, transcript scroll, pricing reveal card animation |
| **Web Audio API** | Browser native | AnalyserNode for mic and TTS audio reactivity | No library needed; `AudioContext`, `createAnalyser()`, `createMediaStreamSource()`, `createMediaElementSource()` |
| **Zustand** | `zustand` | Orb state machine + conversation state | Lightweight; avoids Redux overhead; `useOrbStore` hook exposes `setOrbState`, `orbState`, conversation context |
| **react-calendly** | `react-calendly` | Inline Calendly booking embed | Drops `PopupWidget` or `InlineWidget` on escalation/CTA trigger; no external redirect |
| **GSAP** | `gsap` | Smooth state transition animation | Optional but recommended for lerping Three.js uniform values and CSS properties during state transitions |

### 4.6 Voice Timing & UX Must-Haves

- **Max TTS response length:** 3 sentences for discovery questions; up to 5 sentences for pricing presentation; never more. Enforced as a system prompt constraint: "Your response must be 3 sentences or fewer for discovery questions."
- **Long response fallback:** If LLM returns > 5 sentences, Atlas prepends: *"Let me give you the short version first"* and truncates to summary. Full response available as text in transcript.
- **Pre-response delay:** 300–500ms randomized delay after STT returns before LLM call is dispatched. If under 100ms, user perceives the response as robotic. If over 600ms, user assumes the system is broken.
- **Empty/low-confidence STT:** If faster-whisper returns empty string or word-level confidence < 0.4, Atlas responds: *"Sorry, didn't quite catch that — want to try again?"* (spoken, not just text).
- **Thinking timeout:** At 2.5s in Thinking state with no LLM response, Atlas speaks: *"Give me just a moment..."* — this is a spoken filler, not a UI spinner. At 5.0s hard timeout, transition to Error state.
- **Orb never frozen:** The orb must always be visually animating, even in Error state (slow single pulse). A completely still orb reads as a crash, not a designed state.
- **Barge-in UX:** When user interrupts TTS, Atlas must not resume the interrupted sentence. Flush the TTS buffer completely. The next Atlas response starts fresh from the new user input context.
- **Mobile silence detection:** On mobile, Silero VAD threshold should be slightly higher than desktop (more ambient noise); expose `vadSensitivity` as a configurable parameter per device type.

---

## Appendix: Key Source References

| Source | URL | Relevance |
|---|---|---|
| Intercom Fin Voice design (Eva Kautz) | [LinkedIn post](https://www.linkedin.com/posts/evatkautz_design-code-recently-launched-fin-activity-7414275948038111232-zfUJ) | WebGL hero + Rive orb design/implementation pattern |
| aguscruiz/voiceorb | [GitHub](https://github.com/aguscruiz/voiceorb) | Three.js + GLSL vertex displacement proof-of-concept; simplex noise, Fresnel shader |
| Rive animation engine | [rive.app](https://rive.app) | State machine animation; alternative to raw GLSL; used by Intercom, Spotify, Duolingo |
| Drift review | [workflowautomation.net](https://workflowautomation.net/reviews/drift) | $180K pipeline attribution, 35% conversion lift benchmark data |
| BANT framework for B2B | [blog.coffee.ai](https://blog.coffee.ai/using-bant-framework-b2b-sales/) | Discovery question sequencing; consultative vs. interrogation pattern |
| Escalation design | [bucher-suter.com](https://www.bucher-suter.com/escalation-design-why-ai-fails-at-the-handoff-not-the-automation/) | Confidence-gated escalation; Klarna implementation reference |
| ShowMe AI | [producttalk.org](https://www.producttalk.org/building-ai-sales-reps-showme/) | Multi-agent architecture; evaluator agents; HeyGen engagement impact |
| Voice AI guardrails | [gladia.io](https://www.gladia.io/blog/safety-voice-ai-hallucinations) | RAG grounding; confidence scoring; hallucination prevention architecture |
| AI voice agents comparison | [makeautomation.co](https://makeautomation.co/best-ai-voice-agents/) | ElevenLabs, Hume AI, Voiceflow feature/weakness profiles |
| Dynamic AI voice orb tutorial | [YouTube](https://www.youtube.com/watch?v=REqmieLpCwk) | Visual orb state animation reference |
| Three.js orb states reference | [LinkedIn post](https://www.linkedin.com/posts/george-joshua-330a94285_interactivedesign-productdesign-motiongraphics-activity-7402387463861628928-z10V) | Three.js orb state animation motion design reference |

---

*Report compiled for AI Marketing Genius — Atlas V1 implementation. All specifications are implementable as written. No placeholder sections.*
