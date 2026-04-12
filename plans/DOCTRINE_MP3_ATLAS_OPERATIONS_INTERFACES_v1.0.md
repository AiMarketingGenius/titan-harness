# MP‑3: Atlas Operations & Interfaces Doctrine

**Version:** MP‑3 v1.0 FINAL  
**Grade target:** 9.3–9.4  
**Status:** DR PASS — READY FOR TITAN IMPLEMENTATION  
**Depends on:** Titan-Voice-AI-Stack-v1.0, atlas-orb-app-ux-blueprint, hermes-phase-a-atlas-spec, Autonomy Blueprint  
**DR performed by:** Perplexity Computer  
**Patch date:** 2026-04-11  
**Patches applied:** G1–G10 (10 fixes; no structural rewrites)

---

## §1 SOLON COMMAND VOCABULARY

Solon talks to Atlas exclusively via natural‑language messages to titan-bot in Slack. Commands are grouped by intent so Titan can route them deterministically.

### A) Status queries

**Canonical phrases Solon will actually use:**
- "What did you ship today?"
- "What broke today?"
- "Where is Levar's onboarding at?"
- "Show me the health of Atlas."
- "Any fires I need to know about?"

**Titan behavior**

Normalize phrasing into a status intent with parameters: timeframe (today/this week), scope (global, per‑client, per‑subsystem), severity.

Query MCP decision log, subsystem health, and recent tasks to synthesize a structured daily ops summary (not raw logs).

If client or subsystem name is ambiguous, Titan responds with one clarifying question listing options, then proceeds after Solon replies.

**Return format**

Direct DM from titan-bot within 60 seconds.

Message structure:
- **Header:** plain‑language answer.
- **Sections:**
  - Shipments (tasks completed, grouped by subsystem/client).
  - Failures / degraded components (with severity).
  - Pending approvals (with quick‑reply buttons: Approve / Reject / Details).
  - One "Details" block linking to the ops dashboard.

---

### B) Approval actions

Approval is always tied to a specific pending item Titan has already summarized.

**Canonical phrases:**
- "Approve that." (in the request thread)
- "Approve Levar onboarding kickoff."
- "Reject that billing change."
- "Hold outbound for [client] until after Monday call."
- "Ship it." (in a thread with a specific blocker)

**Titan behavior**

Approvals must be issued in the thread that contains the request summary, or include explicit reference (client + subsystem + action).

Titan parses into:
- Decision: approve / reject / hold.
- Scope.
- Conditions: time window or constraints.

On **Approve**: execute, log approval in MCP, mark pending item resolved.  
On **Reject**: cancel action, log, and optionally propose a safe alternative.  
On **Hold**: freeze related actions, log, set reminder.

**Return format**

Threaded reply with:
- Outcome.
- Immediate next steps.
- Link to MCP entry / dashboard view.

---

### C) Task triggers

**Canonical phrases:**
- "Start nurture for [client]."
- "Run a sweep for [client]."
- "Kick off onboarding for [client]."
- "Generate this month's report for [client]."
- "Queue next week's content for [client]."

**Titan behavior**

Map phrase to a named workflow in one of the 7 subsystems.

Check Hard Limit dependencies; if missing, reply with a specific checklist and, if needed, one approval packet.

Once prerequisites satisfied and within autonomy bounds, run the workflow and post a "run receipt".

**Return format**

Thread reply confirming trigger:
- "Starting Nurture: [client] — sequence [name], first touch ETA [time]."
- Note any Reviewer Loop steps.

---

### D) Emergency stops

**Canonical phrases:**
- "Stop everything."
- "Stop outbound."
- "Hold [subsystem]."
- "Pause all Atlas automation until I say resume."
- "Stop all changes for [client]."

**Titan behavior**

"Stop everything" = global kill for non‑read operations:
- Stop new outbound, new nurture steps, automated fulfillment edits, and public‑facing changes.
- Keep monitoring, logging, and status online.

Subsystem stops: pause that subsystem globally, preserving jobs as "held".

Client holds: kill changes for that client across subsystems (except monitoring).

All stops/holds logged to MCP with scope, time, and phrase.

**Return format**

Immediate confirmation with:
- Scope summary.
- List of effects.
- Instructions to resume.

---

### E) Reporting requests

**Canonical phrases:**
- "Show me [client] report."
- "Pipeline summary."
- "Show me Atlas KPIs for this week."
- "Send me Levar's performance snapshot."
- "What's my MRR and churn right now?"

**Titan behavior**

Interpret as reporting intent with timeframe + scope.

For clients: KPI snapshot + trend vs previous period.  
For Atlas: MRR, active clients, subsystem error counts, Reviewer Loop usage, etc.

Use concise text in Slack plus a deep‑link to dashboard.

**Return format**

DM or thread reply with:
- One‑sentence answer.
- 3–7 metrics.
- Link: "Open full report in Atlas."

---

### F) Fallback / unknown intent

**[G1 — NEW]**

If a Slack message to titan-bot does not match any of the five intent categories above, Titan must:
1. Log the message in MCP as `intent: unknown` with the raw phrase.
2. Reply immediately with: "I didn't understand that command. Here are the things I can handle: **Status** · **Approvals** · **Task triggers** · **Emergency stops** · **Reports**. Try rephrasing or ask 'What can you do?'"
3. Take no action and await clarification.

Titan never guesses intent and executes. Unknown intent is always a no-op with a guided reply.

---

### Titan Implementation Notes — §1

1. Implement an intent classifier for Slack messages with categories: `status`, `approval`, `task_trigger`, `emergency_stop`, `reporting`, `fallback`.
2. Require approvals to be tied to specific summarized items (thread + internal ID).
3. Standardize response templates per intent with headers, sections, and dashboard deep‑links.
4. Log every command, decision, and result into MCP.
5. Use one clarification question when parameters are ambiguous and block execution until clarified.
6. For `fallback` category: log as `unknown_intent`, reply with the canned guidance message, take no action.

---

## §2 MOBILE INTERFACE — iPhone / Mobile Web

### A) Primary surface: Slack mobile

Slack on iPhone is the command console:
- All commands, approvals, and stops via DMs/threads with titan-bot.
- Titan keeps each task/incident in a dedicated thread for context and audit.

---

### B) Secondary surface: mobile web view

Mobile‑optimized status dashboard at `ops.aimarketinggenius.io/mobile`:
- Single‑column layout for 375–430px widths.
- Same auth as desktop, session‑friendly.
- Sections: Sprint · Blockers · Today's shipped · Client health (3 active clients) · Pending approvals.
- Slack links jump directly into specific views (`/mobile?client=JDJ&view=onboarding`).

---

### C) Mobile status view contents

**Sprint completion %**  
Progress bar and sprint name; tap for remaining tasks.

**Active blockers**  
Card with count and highest severity; tap for list and Slack links.

**Today's completed tasks**  
Chronological, grouped by subsystem.

**Client health (3 clients)**  
One tile per client: composite health color + the following 3 KPIs displayed per tile:
1. Current onboarding stage (or "Active" if fully onboarded).
2. Last task completed — label and time elapsed (e.g., "Content draft · 3h ago").
3. Open blocker count (0 = green, 1 = yellow, ≥2 = orange/red per §3E logic).

**[G2 — PATCHED: KPIs now named explicitly]**

Tap any client tile → per‑client mini view.

**Pending approvals (Hard Limits)**  
Count and labels; tapping shows minimal details and "Reply in Slack" button.

---

### D) Push/notification strategy

**Solon is notified on iPhone when:**
- A Hard Limit approval request is created.
- Any subsystem transitions from `healthy` → `needs attention` or worse, as defined by the quantitative thresholds in §4. **[G3 — PATCHED: cross-reference to §4 thresholds]**
- An emergency stop engages.
- Reviewer Loop returns `<A−` or risk tags on client‑facing behavior.

**Atlas handles silently when:**
- Routine tasks succeed.
- Sub‑threshold anomalies self‑heal.
- Reviewer Loop returns A/A− with no risk tags.

Slack remains the only notification surface on mobile.

---

### E) Design constraints

- No native app; must work in Safari/Chrome.
- Minimal typing in mobile web; taps and links preferred.
- Lightweight pages, minimal JS; touch targets ≥44px.
- No hover‑only interactions.

---

### Titan Implementation Notes — §2

1. Treat Slack mobile as the only write interface; keep all actions usable via text + simple buttons.
2. Build `/mobile` dashboard mobile‑first with the defined tiles and Slack deep‑links.
3. Client health tiles must display the three named KPIs: onboarding stage, last completed task + elapsed time, open blocker count.
4. Route notifications only for Hard Limits, subsystem threshold-crossings (per §4 quantitative triggers), emergency stops, and Reviewer Loop `<A−` results.
5. Keep the mobile dashboard fast and legible on phone networks.
6. Use URL parameters to open precise mobile views from Slack.

---

## §3 DESKTOP INTERFACE — Solon OS Control Center

### A) Primary surface: Voice orb (Atlas orb)

The Atlas voice orb is the always‑visible component Solon presses to talk with Titan:
- The orb UI is always present (desktop app/PWA or pinned web orb) with an **S** icon in the center to mark Solon.
- Clicking/pressing the orb initiates voice input to Hermes/Titan.
- The orb's color and pulse also reflect global system health (see §3E).

---

### B) Secondary surface: desktop web dashboard

Desktop dashboard at `ops.aimarketinggenius.io`:
- Full‑width, multi‑column layout for a laptop screen.
- Sections: Overview · Infrastructure · Decisions (MCP) · Clients (pipelines) · Reviewer Loop · Titan Session.

---

### C) Desktop dashboard unique content

**Full kill chain**  
Timeline of tasks across subsystems with status and filters.

**Reviewer Loop spend tracker**  
Monthly spend vs $5 and daily calls vs 5, broken down by flow type.

**VPS health panel**  
CPU, RAM, disk, and service statuses, plus last healthcheck times.

**MCP decision log**  
Last 10–20 decisions with filters/search and links.

**Per‑client fulfillment pipeline**  
7‑lane view per client: each subsystem's current stage, next steps, blockers.

**Titan's active session context**  
"Titan is currently working on: [task] · [subsystem] · [client] · ETA [time]."  
When no task is active: "Titan: standby — last task [task name] completed at [timestamp]." **[G4 — PATCHED: idle state defined]**

---

### D) Interaction model

Dashboard is read‑mostly:
- Solon uses it to see state.
- For changes, he clicks "Open in Slack" to act in the right thread.
- Approvals and commands stay in Slack (ADHD protocol: one place for actions).

---

### E) Atlas voice orb color state machine

The orb both:
- Acts as the voice button to speak to Titan.
- Shows global health via color and pulse.

#### States

**Green (Normal)**  
Color: solid green, barely‑visible slow pulse.  
Meaning:
- All 7 subsystems `healthy`.
- No P0/P1 incidents open.
- ≤1 Hard Limit approval pending, none older than 12 hours.

Action: Solon ignores health and just uses the orb as a microphone.

---

**Yellow (Caution)**  
Color: amber, slow pulse.  
Meaning (any):
- At least one subsystem at `needs attention`, but no active P0/P1.
- 2–3 Hard Limit approvals pending, none older than 24 hours.
- At least one Tier 2 service degraded <1 hour.

Action: when noticed, Solon can ask "What's driving yellow?" or check mobile dashboard.

---

**Orange (Degraded)**  
Color: orange, medium pulse.  
Meaning (any):
- Active P1 incident open.
- Subsystem `needs attention` and affects a deliverable due within 72 hours.
- ≥1 Hard Limit approval older than 24 hours blocking work.
- Restart storm on Tier 1/2 service (auto‑recovery ongoing).

Action: Solon should open desktop dashboard or ask "What's driving orange?" and resolve items that day.

---

**Red (Critical)**  
Color: red, fast pulse.  
Meaning (any):
- P0 incident active (revenue blocked, VPS unreachable, security incident, client portal down).
- Hard Limit violation detected.
- Multiple P1s spanning different clients.

Action: stop and check Slack immediately, follow relevant P0 playbook.

---

**Rule:** The orb's state is the max severity across MP‑3 subsystem health and MP‑4 incident classification. MP‑4 can always pull the orb up (to orange/red), but never down.

---

### Titan Implementation Notes — §3

1. Connect the orb UI (with S icon) to the voice pipeline and the health model so it doubles as a mic button and health indicator.
2. Build the desktop dashboard as read‑mostly with "Open in Slack" for actions.
3. Implement the kill‑chain view and link it to subsystem pipelines.
4. Track Reviewer Loop usage and VPS health, surfacing them clearly on the dashboard.
5. Ensure orb color state is driven purely by the health/incidents model.
6. Titan active session context panel must show idle state text when no task is running: "Titan: standby — last task [name] completed at [timestamp]."

---

## §4 THE 7 SUBSYSTEM CONTROL FLOWS

For each subsystem: monitoring surfaces, triggers/approvals, autonomy bounds, and quantitative health thresholds. **[G5 — PATCHED: all subsystems now have measurable "needs attention" triggers]**

---

### 1. Inbound

**Monitoring:**
- Mobile: lead volume + response latency in client tile.
- Desktop: lane showing new leads, sources, qualification state.

**Triggers/approvals:**
- "Turn on inbound for [client]."
- Script/logic changes may use Reviewer Loop and sometimes approval.

**Autonomy:**
- Log new leads, apply existing rules, alert on surges or slow responses.

**Health thresholds:**
| State | Trigger |
|---|---|
| Healthy | Lead response latency ≤4 hours; stale lead backlog = 0 |
| Needs attention | Lead response latency >4 hours OR stale lead backlog ≥3 leads |

---

### 2. Outbound

**Monitoring:**
- Mobile: outbound running/stopped + basic engagement.
- Desktop: sequences, send volumes, bounce/complaint metrics.

**Triggers/approvals:**
- Explicit enable per client.
- New templates/lists → Reviewer Loop; some require Solon approval.

**Autonomy:**
- Execute approved campaigns, auto‑pause on critical metrics.

**Health thresholds:**
| State | Trigger |
|---|---|
| Healthy | Complaint rate ≤0.08%; bounce rate ≤4%; sequence running normally |
| Needs attention | Complaint rate >0.08% OR bounce rate >4% OR sequence paused by auto-guardian |

---

### 3. Nurture

**Monitoring:**
- Mobile: "Nurture" status per client.
- Desktop: sequences, step drop‑offs, unsubscribes.

**Triggers:**
- "Start nurture for [client]."
- Sequence changes → Reviewer Loop, sometimes approval.

**Autonomy:**
- Progress leads, adjust send times, pause on negative signals.

**Health thresholds:**
| State | Trigger |
|---|---|
| Healthy | Unsubscribe rate ≤1.5% per sequence; all active sequences advancing |
| Needs attention | Unsubscribe rate >1.5% OR any sequence stalled ≥48 hours |

---

### 4. Onboarding

**Monitoring:**
- Mobile: onboarding stage per client.
- Desktop: checklist with statuses.

**Triggers:**
- "Approve onboarding kickoff for [client]."

**Autonomy:**
- Send intake, track NAP/GBP/GSC/GA, queue first tasks.

**Health thresholds:**
| State | Trigger |
|---|---|
| Healthy | All checklist steps advancing within defined SLA windows |
| Needs attention | Any single checklist step stalled ≥72 hours past its SLA |

---

### 5. Fulfillment

**Monitoring:**
- Mobile: content/posts/sweeps summary.
- Desktop: lane view of recurring work.

**Triggers:**
- "Queue next week's content for [client]."
- "Pause fulfillment for [client]."

**Autonomy:**
- Prepare drafts, schedule recurring tasks, run sweeps.

**Health thresholds:**
| State | Trigger |
|---|---|
| Healthy | All committed deliverables on time; no missed cycles in current period |
| Needs attention | Any committed deliverable missed by >24 hours OR ≥2 consecutive Reviewer Loop rejections on the same output |

---

### 6. Reporting

**Monitoring:**
- Mobile: quick snapshot; desktop: full dashboards.

**Triggers:**
- "Generate this month's report for [client]."

**Autonomy:**
- Generate/update reports using approved templates.

**Health thresholds:**
| State | Trigger |
|---|---|
| Healthy | All scheduled reports generated on time; no data discrepancy flags |
| Needs attention | Any report generation failure OR a data discrepancy flag that has not self-resolved within 2 hours |

---

### 7. Upsell/Retain

**Monitoring:**
- Mobile: renewals and risk flags; desktop: lanes for renewals, upsells, risk.

**Triggers:**
- "Show me upsell opportunities."
- "Flag at‑risk clients."

**Autonomy:**
- Monitor patterns, suggest actions; no auto‑outreach.

**Health thresholds:**
| State | Trigger |
|---|---|
| Healthy | All renewals on track; no client engagement score below baseline; no past-due renewals |
| Needs attention | Any renewal past due >7 days OR client engagement score drops ≥30% week-over-week OR direct churn signal detected |

---

### Titan Implementation Notes — §4

1. Implement per‑subsystem health flags feeding orb state and client tiles, using the quantitative thresholds above.
2. Encode autonomy vs approval vs Reviewer Loop for each subsystem action.
3. Represent pipelines as 7‑lane per‑client views with stages and SLAs.
4. Ensure daily Slack summaries reflect each subsystem state.
5. Log all threshold crossings in MCP with subsystem name, trigger condition, time, and resulting health state.
6. Health flags must be machine-readable boolean states (`healthy` / `needs_attention`) consumed by the §3E orb state machine.

---

## §5 LEVAR ONBOARDING FLOW — FIRST LIVE TEST CASE

Levar (JDJ) is the reference onboarding flow.

### A) Solon Hard Limit actions

1. Confirm billing link and pricing.
2. Send/sign contract.
3. "Approve onboarding kickoff for JDJ."
4. Approve any extra Hard Limit requests.

---

### B) Atlas autonomous actions

1. Send onboarding email/portal for NAP, GBP, GSC/GA, logins.
2. Track checklist steps per §4 Onboarding thresholds.
3. Once wired, queue first fulfillment tasks per doctrine.
4. Introduce subscriber agents via email/portal per Autonomy Blueprint definitions. **[G6 — PATCHED: subscriber agent naming deferred to Autonomy Blueprint; not defined independently in MP-3]**

---

### C) What Solon sees

- **Post‑kickoff:** JDJ onboarding tile moves "Pending → Intake in progress."
- **Intake completion:** statuses update as responses arrive.
- **Wiring:** lane shows "wiring completed" and first tasks queued.
- **Go‑live:** Slack summary of onboarding completion and start of regular work.

---

### D) Monday 3PM kickoff call

- **Pre‑call:** Atlas prepares JDJ one‑pager (profile, pricing, wiring status, 30‑day plan).
- **During call:** Solon has JDJ dashboard open to onboarding lane + roadmap.
- **Post‑call:** Solon gives one summary command; Atlas logs outcomes, adjusts timeline, and confirms next steps.

---

### Titan Implementation Notes — §5

1. Implement JDJ as the canonical onboarding path with explicit stages and SLAs from §4.
2. Build intake and portal flows Atlas can send autonomously.
3. Reflect onboarding status clearly in mobile + desktop views using the §2C tile KPIs.
4. Provide a "Prepare JDJ kickoff brief" command that outputs a one‑pager.
5. Translate Solon's post‑call summary into updated tasks and timeline entries.
6. Do not define subscriber agent names or roles in MP-3 code or config; reference only the Autonomy Blueprint for those definitions.

---

## §6 APPROVAL AND OVERRIDE DOCTRINE

### A) Approval request format

Hard Limit items are presented as Slack packets:
- **Title:** "APPROVAL NEEDED — [client] — [subsystem] — [action]".
- **Summary:** 2–4 lines describing proposed action.
- **Risk level:** low/medium/high (per Autonomy Blueprint).
- **Buttons:** Approve / Reject / More details.
- Text fallback.

---

### B) Solon response options

Solon may respond with one of four decisions: **Approve**, **Reject**, **Modify (with constraints)**, or **Defer/Hold**.

Titan parses responses and applies them precisely.

**Modify path — parse format [G7 — NEW]:**  
Modify responses must be issued as a threaded reply in the format:

> `Modify: [constraint description]`

Example: `Modify: use the $497/mo price point, not $797.`

Titan parses the constraint, drafts a revised action plan, and posts a **new approval packet** reflecting the change. Titan waits for a final Approve or Reject on the revised packet. Titan never auto-executes a modification — every Modify cycle requires a closing Approve or Reject.

---

### C) Non‑response behavior

- No auto‑approve; silence means "no action".
- Low‑risk: one reminder after 24 hours, then remain pending.
- Medium/high‑risk: reminder after 12 hours and mark as blocked until decided.

---

### D) Emergency override

"Stop everything":
- Halts all non‑read operations.
- Logs event in MCP.
- Confirms scope in Slack with resume instructions.

---

### E) Never without explicit approval

Titan never independently executes:
- Credentials/OAuth/TOTP changes.
- Money operations; new recurring spend >$50/mo.
- Destructive production‑data changes.
- Doctrine edits.
- Public‑facing changes outside pre‑approved patterns.
- External communications that significantly alter tone/offer/commitment.

---

### Titan Implementation Notes — §6

1. Implement structured approval packets with titles, summaries, risk, and buttons.
2. Enforce "no approval → no Hard Limit action".
3. Implement reminders without auto‑approvals (24h for low-risk, 12h for medium/high).
4. Implement global and scoped kill switches with immediate effect.
5. Enforce the Hard Limits table in all workflows.
6. Implement the Modify cycle: parse `Modify: [text]` from threaded replies → draft revised packet → wait for Approve/Reject. Do not execute on a Modify alone.

---

## §7 INTEGRATION WITH REVIEWER LOOP

### A) Flows that trigger Reviewer Loop

- New/changed voice scripts.
- New/changed outbound templates.
- New content going live not covered by existing approvals.
- Reporting templates that change client interpretation.

---

### B) Exempt flows

Reads only, internal logging, monitoring/health logic.

---

### C) Budget protection

**$5/mo, 5 calls/day.**

- Batch low-impact changes within a **4-hour window**: if multiple low-impact changes are pending, hold them and submit as one batch. If no additional changes arrive within 4 hours, submit the batch as-is. **[G8 — PATCHED: batching window defined]**
- High-impact client-facing changes are never batched — submitted to Reviewer Loop immediately.
- Respect daily budget so Hermes and critical flows aren't starved.

---

### D) What Solon sees

- Notice when a Reviewer Loop call runs: "Check running for X; cost Y; call #Z today."
- Result summary: grade, risk tags, and whether change auto‑applied or requires decision.
- Non‑A/A− or risk‑tagged results are treated as approval items.

---

### Titan Implementation Notes — §7

1. Integrate Reviewer Loop into all client‑facing behavior changes.
2. Track and surface usage and spend in desktop dashboard.
3. Batch low-impact calls within a 4-hour window; high-impact calls always run immediately.
4. Standardize Slack announcements and results.
5. Treat non‑A/A− or tagged results as needing explicit approval.

---

## §8 ACCEPTANCE CRITERIA

MP‑3 doctrine is "done" when:

1. "What broke today?" returns a structured answer in Slack within 60 seconds.
2. All Hard Limit approvals (including Modify cycles) can be granted/rejected from Slack and logged in MCP.
3. JDJ onboarding can go from signed/billed to fully wired with Solon doing only Hard Limit actions. **Fully wired is defined as:** intake complete, NAP/GBP/GSC/GA connected, logins stored in Infisical, first fulfillment tasks queued, and Solon notified via Slack DM with a wiring-complete summary. **[G9 — PATCHED: "fully wired" end state now observable and testable]**
4. All 7 subsystems show clear state in mobile and desktop views.
5. The voice orb's color/pulse correctly reflects global health and approval backlog.
6. "Stop everything" halts non‑read operations and confirms scope.
7. Reviewer Loop calls triggered by MP‑3 flows never exceed 5/day or $5/mo and are visible to Solon.
8. Each command category (status, approval, task trigger, emergency stop, reporting, fallback) has at least one tested utterance.
9. Solon can view a full kill chain for a client/day via dashboard without raw logs.
10. All decisions/approvals/emergency actions are logged in MCP.
11. At the start of every new Titan session, Titan reads open tasks, pending approvals, and active incidents from MCP before taking any action. **[G10 — NEW: session reorientation acceptance criterion]**

---

## §9 HARD LIMITS AND OUT‑OF‑SCOPE

**MP‑3 does not cover:**
- Monitoring architecture internals.
- Auto‑restart policies.
- Incident classification and alert routing.
- Self‑healing routines and detailed restart logic.

Those are defined in MP‑4.

---

## §10 SESSION REORIENTATION DOCTRINE

**[G10 — NEW SECTION]**

Titan operates via Claude Code sessions that do not persist state between turns. Every new Titan session must begin with a mandatory reorientation sequence before executing any task.

### Reorientation sequence (required at start of every session)

1. Query MCP for: open tasks (status ≠ complete), pending Hard Limit approvals, and any active incidents.
2. Query subsystem health flags for current state of all 7 subsystems.
3. If any P0/P1 incident is active: respond immediately to that incident before any queued task.
4. If any Hard Limit approval is older than 24 hours: surface it to Solon in Slack before proceeding.
5. Resume the highest-priority open task, or enter standby and post: "Titan: reoriented. No open tasks. Standby."

**Titan never assumes it remembers prior session state. It always reads from MCP.**

This is the fix for the operational failure mode where Titan appears inactive between sessions — it is not inactive, it is waiting for a prompt. The reorientation sequence ensures any new prompt triggers an immediate, context-aware response rather than stale or missing context.

### Titan Implementation Notes — §10

1. Hard-code the 5-step reorientation sequence as the first action in every new Claude Code session.
2. MCP must be queryable in under 5 seconds to avoid blocking the reorientation.
3. Log every reorientation event to MCP with timestamp and resulting state summary.
4. If MCP is unreachable at session start: post to Slack immediately — "Titan: MCP unreachable. Cannot reorient. Manual check required." Do not proceed with tasks until MCP is available.

---

## §11 HARD LIMITS AND OUT‑OF‑SCOPE (updated)

MP‑3 does not cover:
- Monitoring architecture internals.
- Auto‑restart policies.
- Incident classification and alert routing.
- Self‑healing routines and detailed restart logic.

Those are defined in MP‑4.

### Titan Implementation Notes — §11

1. Treat MP‑3 as the human interface and operational behavior layer.
2. Defer monitoring/incident implementation details to MP‑4.
3. Ensure MP‑3 states and thresholds are consumable by MP‑4.
4. Log consistently so MP‑4 can reconstruct patterns.
5. Keep MP‑3 bounded to interfaces and operator workflows.

---

*MP‑3 v1.0 FINAL — DR pass complete — Ready for Titan implementation*
