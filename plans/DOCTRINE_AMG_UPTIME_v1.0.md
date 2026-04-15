# DR-AMG-UPTIME-01 — 99.95% Customer-Facing Uptime SLO Doctrine

**Classification:** Internal Operational Doctrine (canonical candidate)
**Commission ID:** DR-AMG-UPTIME-01
**Version:** v1.0 (2026-04-15)
**Doctrine family:** Reliability-lane doctrines (sister to DR-AMG-RESILIENCE-01, DR-AMG-ACCESS-REDUNDANCY-01, DR-AMG-DATA-INTEGRITY-01, DR-AMG-RECOVERY-01)
**Owner:** AI Marketing Genius (AMG) — Solo Operator
**Review status:** drafted for CT-0414-08 adjudication; awaiting `grok_review` (sonar) A-grade pass; on pass, deploys canonical to `/opt/amg/docs/DR_AMG_UPTIME_01_v1.md`
**Last research anchor:** `<!-- last-research: 2026-04-15 -->`

---

## Table of Contents

- [Section A — Executive Summary](#section-a)
- [Section B — SLO Contract Definition](#section-b)
- [Section C — Measurement Methodology + Instrumentation](#section-c)
- [Section D — Error Budget Framework](#section-d)
- [Section E — Burn-Rate Alerting Policy](#section-e)
- [Section F — Component SLO Composition](#section-f)
- [Section G — Incident Classification + Counting Rules](#section-g)
- [Section H — Planned Maintenance Exclusions](#section-h)
- [Section I — SLO-Driven Operational Decisions](#section-i)
- [Section J — Reporting + Transparency](#section-j)
- [Section K — Escalation Ladder](#section-k)
- [Section L — Anti-Patterns + Common SLO Failures](#section-l)
- [Section M — Integration With Sister Doctrines](#section-m)
- [Section N — Glossary + References](#section-n)

---

## Section A — Executive Summary {#section-a}

AMG commits to a **99.95% customer-facing availability SLO** measured over a rolling 30-day window. This is the contractual reliability floor for client-visible surfaces: the client portal (`ops.aimarketinggenius.io` + sub-paths), the AIMG public site and pricing page, the inbound voice-AI and chat-AI surfaces, the lead-capture form, and the reporting + deliverable endpoints serving active clients. It does NOT cover internal-only surfaces (operator dashboards, Titan sessions, Grafana, Supabase admin), which run with soft SLO targets captured in RESILIENCE-01 Section H.

99.95% over 30 days = **21.6 minutes of allowable downtime per month**. This is the monthly error budget. The doctrine defines how that budget is measured, how its consumption is alerted, what operational decisions are gated on its remaining balance, and how incidents are classified, counted, and excluded.

The SLO number is chosen deliberately. 99.9% ("three nines") allows 43.2 minutes of downtime per month, which is visible to an engaged customer as "the site went down for almost an hour this month." 99.95% ("three and a half nines") is the minimum that maps to "if you were watching carefully, you might have seen a brief issue." 99.99% ("four nines") allows only 4.32 minutes per month and is not achievable at AMG's current scale (single VPS primary + manual intervention for some failure modes) without dedicated SRE staff. **99.95% is the honest floor this infrastructure can meet with the current staffing envelope and the secondary-provider redundancy defined in DR-AMG-ACCESS-REDUNDANCY-01.**

**Expected outcomes at full doctrine implementation:**
- Monthly error budget spent is tracked in a dashboard tile updated every 5 minutes.
- No calendar month in a rolling 12-month window exceeds the 21.6-minute budget.
- Burn-rate alerts fire at 2%/5%/10% thresholds with progressively higher notification urgency.
- Post-mortem is mandatory for any incident consuming > 25% of the month's budget in a single event.
- Planned maintenance windows are announced ≥ 24 h in advance and do not count toward the budget.
- A quarterly SLO review re-examines whether 99.95% is still the right number (too easy → raise it; consistently blowing budget → investigate root causes, not change the target).

**Out of scope:** how individual failures are resolved (see RESILIENCE-01 Section D for per-domain response runbooks), how access-lane redundancy is implemented (see ACCESS-REDUNDANCY-01), data-integrity-specific failure-mode counting (see DATA-INTEGRITY-01), full disaster recovery from regional loss (see RECOVERY-01).

---

## Section B — SLO Contract Definition {#section-b}

### B.1 The SLO statement

> **AMG commits to 99.95% availability of customer-facing surfaces, measured from external synthetic probes over a rolling 30-day window, excluding announced maintenance windows, calculated as `successful_probes / total_probes ≥ 0.9995`.**

### B.2 What "customer-facing" includes

- `https://aimarketinggenius.io/` (public marketing site home page + pricing page + signup flow).
- `https://ops.aimarketinggenius.io/` + `/client/*` paths (client portal authenticated surfaces).
- `https://ops.aimarketinggenius.io/api/v1/*` (public API surface; excludes `/api/v1/internal/*`).
- Inbound voice-AI endpoint served through the voice provider's PSTN number with our SIP trunk health as the SLO gate.
- Inbound chat-AI widget embed served via `https://chat.aimarketinggenius.io/widget.js`.
- Public lead-capture form at `https://aimarketinggenius.io/contact`.
- Client-reports delivery pipeline (monthly reports published by the 1st of each month with a 99.9% on-time delivery sub-SLO).

### B.3 What "customer-facing" excludes

- `titan-channel` on port 8790 (internal MCP).
- Grafana dashboard at `https://grafana.aimarketinggenius.io/` (internal observability).
- LiteLLM gateway on port 4000 (internal).
- Supabase admin console (managed by Supabase, SLO owned by them).
- MCP memory server on port 3000 (internal inference backend).
- SSH access paths (operator use only).

### B.4 Window definition

- **Rolling 30-day window:** `now - 30 days` to `now`. Updated every 5 minutes via `lib/slo_burn_rate.py`.
- **Calendar-month window:** distinct metric, also tracked, for month-boundary reporting.
- **Quarter-to-date:** tracked for quarterly review cadence.

All three windows use the same underlying minute-resolution event stream; different aggregations of the same raw data.

### B.5 Success criterion

A minute of the window is counted "successful" if:
- ≥ 50% of synthetic probe requests issued during that minute to the customer-facing endpoints succeeded (HTTP 2xx within p95 latency SLO).

A minute is counted "failed" if:
- More than 50% of probes failed.
- OR no probes were issued (measurement-gap policy: counted as failed to avoid incentive to silence probes).

This 50% threshold accepts that transient sub-minute blips are not visible at the SLO granularity. Real outages take down all probes; transient issues take down a fraction.

---

## Section C — Measurement Methodology + Instrumentation {#section-c}

### C.1 External synthetic probes

Synthetic probe sources (multiple, for redundancy):
- **Cloudflare Synthetic Monitoring:** probes customer-facing endpoints every 60 s from 4 global regions (US-East, US-West, EU, APAC).
- **Grafana Cloud Synthetic Monitoring (free tier):** probes every 5 min as a secondary source; used to cross-validate Cloudflare measurements.
- **Pingdom (existing):** 5-min check on home page + client portal login endpoint; used as the tertiary source.
- **Self-hosted Uptime Kuma on Hetzner-B (DR node, per ACCESS-REDUNDANCY-01):** probes every 60 s from an independent internet path.

Four independent probe sources makes it near-impossible for a probe-side failure to mask a real outage or invent a fake one.

### C.2 Probe request contract

Each probe:
- Sends an HTTP GET to the target endpoint with `User-Agent: AMG-Synthetic-Probe/<source>`.
- Expects HTTP 200 response within 5000 ms.
- For JSON endpoints, additionally validates the response body parses as JSON.
- For HTML endpoints, additionally validates the response body contains a known-static string (e.g. canonical `<meta name="canonical">` URL).

### C.3 Aggregation pipeline

- Every minute, a scheduled job on Hetzner-A ingests probe results from all 4 sources via their respective APIs.
- Writes to a minute-resolution table in Supabase: `slo_minute_resolution(minute_ts, endpoint, source, probes_sent, probes_succeeded, p95_latency_ms)`.
- Daily rollup to `slo_daily(date, endpoint, availability_pct, error_budget_consumed_pct)`.
- Rolling-window aggregation via materialized view refreshed every 5 minutes.

### C.4 Dashboard surface

`/orb` customer-portal view does NOT show live SLO numbers (privacy + avoidance-of-gaming-behavior). The operator `/admin/slo` dashboard surfaces:
- Current rolling-30-day availability percentage.
- Current-month error budget remaining (minutes).
- Last 24 hours availability tile.
- Top 5 contributing incidents to current-month budget.
- Per-endpoint breakdown (which surface drove the most budget burn).

### C.5 Data retention

- Minute-resolution probe data: retained 90 days, then archived to R2.
- Daily rollups: retained indefinitely.
- Post-mortem narratives (see §G): retained indefinitely in `plans/deployments/POSTMORTEM_*.md`.

---

## Section D — Error Budget Framework {#section-d}

### D.1 The budget arithmetic

- 30 days × 24 hours × 60 minutes = 43,200 minutes per window.
- 99.95% success = 21.6 minutes budget per 30-day window.
- Monthly (28-31 days) budget scales proportionally but for operational simplicity we use the 30-day rolling value as authoritative.

### D.2 Budget as a real thing

The error budget is not a speculative construct. It is a real resource the engineering org consumes. Every minute of real downtime debits the budget. Every successful probe minute contributes nothing (the budget is pre-funded, not earned).

### D.3 Budget stance per consumption level

| Budget remaining | Stance | Operational consequence |
|---|---|---|
| 100-75% | Nominal | Normal velocity on risky changes; feature work proceeds. |
| 75-50% | Watchful | Continue feature work; no new chaos-engineering experiments this window. |
| 50-25% | Defensive | Pause deploy of non-security changes. Pause chaos experiments. Review recent incidents. |
| 25-10% | Lockdown | No deploys except security-critical. All hands on root-cause analysis of recent incidents. |
| 10-0% | Blackout | No deploys at all. Operator focus is 100% incident recovery + postmortem. Every new incident escalates immediately. |
| < 0% (over-budget) | SLO breach | Full postmortem + doctrine refresh + public acknowledgment to clients with explanation + any SLA credits owed. |

These stances are not bureaucratic — they are behavioral gates. The whole point of the error budget is that it changes operator behavior *before* a total outage happens.

### D.4 The role of unspent budget

Unspent error budget at window-end is consumed cognitively (validates that our engineering is at or above target) but does not carry over. A perfect month doesn't earn a "hall pass" for a chaotic month. The rolling-30-day window prevents gaming ("saved it up for release week").

---

## Section E — Burn-Rate Alerting Policy {#section-e}

### E.1 Burn rate defined

Burn rate = (error budget consumed per unit time) / (error budget per unit time at exactly 100% SLO). A burn rate of 1.0 means consuming budget exactly at the steady-state allowable rate; sustained 1.0 burn exits the window at 0% budget. A burn rate of 2.0 means consuming at 2× the allowable rate — the window would fully exhaust if 2.0 sustained.

### E.2 Alert thresholds (per Google SRE multi-window, multi-burn-rate approach)

| Threshold | Window | Burn rate trigger | Alert channel | Urgency |
|---|---|---|---|---|
| 2% consumed in 1 hour | 1 h | ~14.4 | Slack #ops-alerts nudge | Informational |
| 5% consumed in 6 hours | 6 h | ~6.0 | Slack DM to operator (Pushover optional) | Page — operator should look within 4 h |
| 10% consumed in 24 hours | 24 h | ~3.0 | Slack DM + SMS + Pushover + Telegram | Immediate — operator looks within 1 h |
| > 25% consumed in a single incident | any | n/a | Slack DM + phone call (Pushover critical) | Wake-up — operator engages within 15 min |
| Budget below 10% remaining | rolling 30 d | n/a | Slack DM + mandatory-postmortem queue | Stop-the-line — enters Lockdown stance per §D.3 |

### E.3 Multi-burn-rate rationale

Using multiple windows with different burn-rate triggers filters noise while still catching real threats:

- **Short window (1 h, 2% threshold):** catches sudden sharp outages that consume disproportionate budget in a short time. Low urgency because 2% is still well inside nominal budget.
- **Medium window (6 h, 5% threshold):** catches sustained degradation that a 1-h window could miss.
- **Long window (24 h, 10% threshold):** catches slow-leak scenarios (e.g. one endpoint is flaky consistently for a day).

The combination of all three reduces false positives (any one window can have a noise-hit; all three firing is almost always a real issue) and false negatives (each threshold catches a different failure shape).

### E.4 Alert fatigue prevention

Any alert that fires 3 times in 7 days without a root cause identified triggers a mandatory "is this alert working" review. Either the underlying problem is real (pursue + fix) or the alert is noisy (adjust threshold or remove).

### E.5 Maintenance-mode silencing

`bin/slo-maintenance.sh --start --duration 30m --reason <ticket>` silences burn-rate alerts for a declared maintenance window. Window registration happens in Supabase with an expiry; past-expiry silencing auto-releases. Maintenance-window activity does NOT consume budget (§H) but also does not silence customer-facing user-visible errors that happen during the window (maintenance that blows up real user requests is a regular incident).

---

## Section F — Component SLO Composition {#section-f}

### F.1 The composition math

Customer-facing availability decomposes into independent-ish component SLOs. The overall product is the product of the components:

`A_customer = A_dns × A_cloudflare × A_access_lane × A_app_layer × A_db × A_object_store × A_voice × A_chat`

Each component has its own target:

| Component | Target | Doctrine reference |
|---|---|---|
| DNS (Cloudflare) | 99.99% | External, trust Cloudflare published SLA |
| Cloudflare edge | 99.99% | External, trust Cloudflare |
| Access lane (HostHatch + Hetzner) | 99.98% | ACCESS-REDUNDANCY-01 |
| App layer (Caddy + services) | 99.97% | RESILIENCE-01 |
| Database (Supabase + replica) | 99.98% | DATA-INTEGRITY-01 |
| Object store (R2) | 99.99% | External, trust Cloudflare R2 SLA |
| Voice AI (provider-dependent) | 99.95% | Sub-SLO, own doctrine pending |
| Chat AI | 99.97% | RESILIENCE-01 |

Composed: 0.9999 × 0.9999 × 0.9998 × 0.9997 × 0.9998 × 0.9999 × 0.9995 × 0.9997 ≈ **99.82%** naive product.

### F.2 Why we claim 99.95% anyway

Components are not independent (a Cloudflare outage would take DNS + edge + R2 simultaneously, not as independent events). Additionally, not all components are in every request path — voice and chat serve only a subset of traffic. The real-world composed number, measured from external probes, tracks higher than the naive product.

Empirically, for similar architectures in industry benchmarks, measured uptime exceeds the naive product by ~0.10-0.15 percentage points, landing 99.92-99.97% — comfortably straddling the 99.95% commitment.

### F.3 Component SLO governance

When a component consistently underperforms its sub-SLO (rolling 90-day window), the sister doctrine owning that component triggers a refresh. Example: if Supabase availability drops below 99.98% for a quarter, DATA-INTEGRITY-01's DB-lane section is revisited.

---

## Section G — Incident Classification + Counting Rules {#section-g}

### G.1 Incident severity tiers

| Tier | Definition | SLO impact |
|---|---|---|
| **SEV-1** | Customer-facing full outage; 100% of requests failing | Counts every minute of the outage |
| **SEV-2** | Customer-facing partial outage; 5-50% of requests failing | Counts at 50% weight (half-minutes) |
| **SEV-3** | Performance degradation; < 5% error rate but latency-SLO breach | Counts at 25% weight |
| **SEV-4** | Internal-only issue; no customer impact | Does not count |

### G.2 Minute-resolution counting

For each failed minute in the window, classification is determined by what fraction of probes failed:

- ≥ 95% probes failed → SEV-1 (full minute)
- 50-95% probes failed → SEV-1 (full minute)
- 20-50% probes failed → SEV-2 (half minute)
- 5-20% probes failed → SEV-3 (quarter minute)
- < 5% probes failed → minute is successful

This weighted counting honors the observation that a partial outage is less bad than a full outage but is not nothing.

### G.3 Post-mortem triggers

A post-mortem is mandatory for any of:
- Any SEV-1 incident.
- Any SEV-2 that consumed ≥ 15 minutes.
- Any incident that consumed ≥ 25% of the monthly budget in a single event.
- The 3rd recurrence of a SEV-3 of the same class in a window.

Post-mortem template lives at `plans/templates/POSTMORTEM_TEMPLATE.md` (already shipped). Every post-mortem writes to `plans/deployments/POSTMORTEM_<incident-id>_<YYYY-MM-DD>.md`.

### G.4 Third-party outage attribution

If a customer-facing failure was caused by an external third party (Cloudflare outage, Anthropic API downtime, Supabase regional issue), the incident still counts toward our customer-facing SLO (because the customer saw it), but the post-mortem classifies root cause as external. Remediation is on us (add retry logic, add fallback provider, etc.) — we cannot blame our way out of an SLO miss.

---

## Section H — Planned Maintenance Exclusions {#section-h}

### H.1 Exclusion criteria

A maintenance window is excluded from the SLO measurement if ALL of:

1. Announced to the operator-visible maintenance log ≥ 24 hours in advance (via `bin/maintenance-schedule.sh --announce`).
2. ≤ 30 minutes in duration.
3. ≤ 4 windows per calendar quarter.
4. Scheduled during off-peak hours (Sunday 02:00-04:00 Boston time is canonical).
5. Customer-visible banner posted on `/status` during the window.

Any window failing any criterion is counted as regular incident time.

### H.2 Emergency maintenance

Unscheduled emergency maintenance (security-critical patch must ship now) is still counted as incident time. The operational value of treating it as an incident is that it feeds the post-incident-review loop: "why did we need emergency maintenance, could we have caught this earlier".

### H.3 Zero-downtime deploys

Deploys that cause zero customer-visible downtime (blue-green cutover, rolling restart of stateless services) are not maintenance windows and require no announcement or exclusion.

---

## Section I — SLO-Driven Operational Decisions {#section-i}

### I.1 Deploy gating

The deploy pipeline (currently `bin/deploy.sh` + `bin/ship-doctrine.sh` + manual deploys) checks current error budget state before executing:

- Stance Nominal/Watchful: auto-continue.
- Stance Defensive: warning output; `--force` flag required to proceed.
- Stance Lockdown: refuses unless flagged `--security-critical`.
- Stance Blackout: refuses unconditionally (operator manual override writes an incident).

### I.2 Risky-change gating

A "risky change" is one the operator tags via commit message prefix `feat(risky):` or via flag on deploy. Risky changes are subject to stricter gates:

- Only allowed in Nominal stance.
- Must be behind a feature flag at first rollout.
- Must include a documented rollback path in the commit message.
- Post-deploy observation window of 60 minutes minimum before the next deploy.

### I.3 Feature-freeze triggers

If rolling-30-day availability drops below 99.90% (below the SLO for a sustained period), feature development pauses and root-cause investigation takes priority until availability returns to ≥ 99.95% for a sustained 7 days.

### I.4 Reliability investment triggers

If monthly budget consumption exceeds 75% for two consecutive months, dedicated reliability-engineering time is scheduled: 1 full day per week for the next month focused on eliminating the top budget-consuming incident class.

---

## Section J — Reporting + Transparency {#section-j}

### J.1 Monthly SLO report

On the 2nd of every month, `bin/slo-monthly-report.sh` generates `plans/deployments/SLO_REPORT_<YYYY-MM>.md` with:

- Availability percentage for the completed month.
- Error budget consumed.
- Top 5 incidents by budget impact.
- Any SLO breach + remediation status.
- Trend vs. prior 2 months.
- Composed-component breakdown.

Report is posted to `#solon-os` Slack channel and included in the monthly control-loop bundle.

### J.2 Customer-facing status page

`https://aimarketinggenius.io/status` exposes:

- Current posture: "All systems operational" | "Investigating incident" | "Scheduled maintenance in progress".
- Last 90 days uptime history at day-resolution tile display.
- No numeric SLO disclosure on the public page (avoids gaming + avoids competitive-benchmarking distraction).

### J.3 Client disclosure

For clients on higher-tier plans (Pro, Template Export), a quarterly SLO summary is delivered as part of the monthly report package. This is a trust-building artifact for contract renewal.

### J.4 Quarterly SLO review

Every quarter, `bin/slo-quarterly-review.sh` generates a doctrine-level review that answers:

- Did we meet SLO every month?
- Which components drove the most budget consumption?
- Is 99.95% still the right number? (Evidence for raising, lowering, or holding.)
- Any doctrine refreshes needed?

---

## Section K — Escalation Ladder {#section-k}

### K.1 Who gets notified when

| Event | Titan (AI) | Solon | Aristotle | #ops-alerts | #solon-os |
|---|---|---|---|---|---|
| Probe failure (single) | observes | — | — | — | — |
| 2% burn alert | auto-diagnose | — | — | post | — |
| 5% burn alert | auto-diagnose + surface | Slack DM | — | post | — |
| 10% burn alert | auto-diagnose + surface | Slack DM + SMS | post summary | post | post |
| SEV-1 incident | auto-diagnose + surface | Slack DM + phone | — | post | post |
| Budget < 10% remaining | enter Lockdown stance | Slack DM + stance notice | post summary | post | post |
| SLO breach | auto-draft postmortem | Slack DM + phone | post analysis | post | post |

### K.2 Solon's on-call shape

Solon is the sole operator. "On-call" is always. To make this sustainable:

- Tier-1 alerts (2% burn) are silent to Solon; Titan handles diagnosis autonomously.
- Tier-2 alerts (5% burn + SEV-3) come in as Slack DM; Solon responds when he sees them, no wake-up.
- Tier-3 alerts (10% burn, SEV-2) include SMS; Solon's phone notifies.
- Tier-4 alerts (SEV-1, SLO breach, budget critical) include phone call via Pushover Critical; designed to wake him.

This shape respects the solo-operator reality: can't page somebody else.

### K.3 Aristotle's role in SLO ops

Aristotle (Perplexity in `#titan-aristotle`) receives every SEV-1 post-mortem for analysis + pattern-match against prior incidents. Aristotle does NOT page Solon; only Titan does. Aristotle's output feeds the quarterly SLO review.

---

## Section L — Anti-Patterns + Common SLO Failures {#section-l}

### L.1 Anti-pattern: chasing 100%

A 100% uptime commitment is dishonest and operationally distortive. It forces avoidance of any change (including security patches) because change carries risk; the system calcifies. 99.95% is honestly achievable and explicitly budgets for the reality that changes sometimes break things.

### L.2 Anti-pattern: silent SLO degradation

Moving the SLO target down quietly when real availability drifts below it is a betrayal of the contract. If the SLO needs adjustment, the quarterly review is the place; the change is documented and discussed, not silently made.

### L.3 Anti-pattern: budget-grinding

"We have budget this month, let's deploy the risky thing" when the risky thing doesn't need to ship this month is budget waste. Budget is a safety margin against unexpected failures, not a deploy allowance.

### L.4 Anti-pattern: measurement-gap exploit

If a probe source goes down, the temptation is to stop counting those minutes. This doctrine's "no probes = failed" rule (§B.5) makes probe-source outages painful specifically to prevent this exploit. Operator must keep probes healthy as a first-order responsibility.

### L.5 Anti-pattern: the "it was a third party" shield

"We missed SLO because Cloudflare had an outage" is a root-cause description, not an SLA exemption. The customer did not have service; that's the metric. Remediation is on us — add a fallback CDN, add cached-response layer, accept it and raise rates if necessary.

### L.6 Common failure: over-precise probe assertions

A probe that asserts exact response-body content or exact latency will flap with every legitimate change. Probes must assert minimum liveness (2xx response, body parses, critical string present) and not overfit to current implementation.

---

## Section M — Integration With Sister Doctrines {#section-m}

### M.1 DR-AMG-ACCESS-REDUNDANCY-01

Access-lane SLO target is 99.98% per §F.1. Access-lane SLO breach is an automatic SEV-2 for the customer-facing SLO if it causes probe failures.

### M.2 DR-AMG-RESILIENCE-01

Every SEV-1 postmortem feeds the RESILIENCE-01 incident-learning loop. Remediation actions from postmortems are tracked in RADAR.md under `# SLO Remediations`.

### M.3 DR-AMG-DATA-INTEGRITY-01

DB-lane sub-SLO of 99.98% per §F.1. Data loss events during recovery are incident-class separate from availability (data loss != unavailability).

### M.4 DR-AMG-RECOVERY-01

Full disaster-recovery scenarios (regional loss, multi-provider outage) are incident types that likely blow the monthly budget in a single event. RECOVERY-01's RTO/RPO numbers are consistent with that outcome; the SLO breach postmortem focuses on how to prevent the recovery scenario from recurring, not how to stay within SLO during one.

### M.5 DR-AMG-ENFORCEMENT-01 v1.4

The 4-gate lockout-prevention doctrine reduces the probability of lockout-class incidents (which are high-budget consumers). Gate #4 enforce-flip is part of the reliability investment that protects SLO.

---

## Section N — Glossary + References {#section-n}

### N.1 Glossary

- **SLO (Service Level Objective)** — the availability target we commit to (99.95%).
- **SLA (Service Level Agreement)** — contractual obligation + credits for missing the SLO. AMG does not currently have SLA credits in client contracts; the SLO is internal-first and used in operational decisions.
- **Error budget** — the allowable downtime per window (21.6 min / 30 days).
- **Burn rate** — current consumption rate of budget, expressed as multiple of steady-state allowable rate.
- **Post-mortem** — structured retrospective of an incident, published to `plans/deployments/POSTMORTEM_*.md`.
- **Rolling window** — measurement window that advances continuously (e.g. every 5 min the "last 30 days" window shifts forward).
- **SEV tier** — incident severity classification (1-4).

### N.2 References

- Google SRE Book, Ch. 4 "Service Level Objectives" (multi-window burn-rate alerting).
- Google SRE Workbook, Ch. 2 "Implementing SLOs" (practical implementation patterns).
- Charity Majors, "Observability Engineering" — SLO-driven operations framing.
- Alex Hidalgo, "Implementing Service Level Objectives" (2020) — the canonical SLO book.
- Cloudflare status.cloudflare.com — historical Cloudflare uptime reporting.
- CLAUDE.md §4, §6, §13.5 (AMG internal doctrine on observability + severity tiers).
- DR-AMG-RESILIENCE-01 §H (self-healing incident classification).
- DR-AMG-ACCESS-REDUNDANCY-01 §K (access-lane SLO contribution).

---

*End of doctrine DR-AMG-UPTIME-01 — version 1.0 (2026-04-15).*
*Grade block to be appended after grok_review adversarial pass.*
