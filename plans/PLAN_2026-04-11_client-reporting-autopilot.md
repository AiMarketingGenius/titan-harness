# DR Plan: Client Reporting Autopilot

**Source:** manual (Solon directive 2026-04-11, autopilot-suite Thread 5)
**Source ID:** autopilot-client-reporting-2026-04-11
**Project:** EOM
**Generated:** 2026-04-11 (Titan autonomous)
**Run id:** autopilot-5-client-reporting

---

## 1. Scope & goals

### What this idea does

Every month, for each active AMG client, Titan auto-generates a monthly report (traffic, leads, revenue proxies, "what we did", "what's next"), war-room grades it, delivers it to the client via email, and logs any follow-up tasks. Solon only intervenes when a client is marked red-status or explicitly asks for a call.

### What this idea does NOT do

- Does not auto-send without at least one review cycle during the initial weeks. For the first 4 reports per client, delivery is gated on Solon's 👍 reaction in Slack. After Solon has approved 4 reports for a given client without edits, the client auto-promotes to "auto-ship" mode with a 24-hour silent-review window (Solon can thumbs-down to hold).
- Does not generate KPIs the client didn't agree to track. Each client has a reporting profile with a defined metric set.
- Does not fabricate data. If a metric source is unreachable, the report surfaces "data unavailable for metric X" and continues.
- Does not replace Looker Studio / full BI. One-pager only.
- Does not handle client billing or payment (that's Thread 4 back-office).
- Does not auto-upsell inside the report. Follow-on.

---

## 2. Phases

### Phase 1: client-roster-and-metric-profiles

- task_type: spec
- depends_on: []
- inputs:
  - Solon's client roster (name, project_id, domain, active/paused status, contact email) — Solon action item
  - Per-client metric sources: GA4 property ID, GSC site URL, any PostHog/Umami project, any CRM pipeline (HubSpot/Close if used)
  - Per-client "what matters": organic traffic / conversion / lead count / revenue proxy / social reach — Solon picks 3-5 per client
- outputs:
  - `sql/011_clients_and_reporting.sql` — `clients`, `client_metric_profiles`, `client_reports`, `client_report_events` tables
  - `lib/client_reporting/profiles.py` — `get_profile(project_id) -> MetricProfile`
- acceptance_criteria:
  - Every active client has a complete profile before their first report runs
  - Missing-profile clients are skipped (not hallucinated)
  - Profile changes are versioned (history preserved)

### Phase 2: metric-source-adapters

- task_type: phase
- depends_on: [1]
- inputs:
  - Google service account JSON with GA4 + GSC read access (one account, many properties)
  - GA4 Data API (`google-analytics-data` Python SDK)
  - Search Console API (`google-api-python-client`)
  - Optional: PostHog / Umami HTTP APIs
- outputs:
  - `lib/client_reporting/sources/ga4.py` — `fetch_monthly_metrics(property_id, start, end)` returns `{sessions, users, engaged_sessions, conversions, top_landing_pages}`
  - `lib/client_reporting/sources/gsc.py` — `fetch_monthly_metrics(site_url, start, end)` returns `{impressions, clicks, ctr, top_queries, top_pages}`
  - `lib/client_reporting/sources/posthog.py` (optional adapter, stub for now)
  - All adapters return a common `MetricsBundle` dataclass
- acceptance_criteria:
  - GA4 adapter pulls a real month of data for a test property in <10 seconds
  - GSC adapter pulls top 20 queries for a test site in <10 seconds
  - Rate limit + retry logic on 429s
  - Cached per-client-per-month results in `client_reports` so re-runs don't re-hit APIs

### Phase 3: "what-we-did" narrative

- task_type: synthesis
- depends_on: [1]
- inputs:
  - `public.mp_runs` rows filtered by client's project_id in the past month
  - `public.tasks` rows completed for the client
  - Git log entries touching client-specific files (if any)
  - `plans/` files with client's project_id tag
- outputs:
  - `lib/client_reporting/narrative.py` → `build_narrative(project_id, month)` returns a 3-5 bullet "what we did this month" list + 3-5 bullet "what's next" forecast derived from open tasks + Titan-assessed priorities
  - Narrative is a single LLM call (Sonnet 4.6) with structured context
- acceptance_criteria:
  - Narrative references actual work (cross-check with mp_runs count)
  - Never fabricates deliverables
  - "What's next" aligns with open tasks in the operator queue

### Phase 4: report-assembler

- task_type: synthesis
- depends_on: [2, 3]
- inputs:
  - Phase 2 metrics bundle
  - Phase 3 narrative
  - Client brand/voice hints (if any)
- outputs:
  - `lib/client_reporting/assembler.py` → combines metrics + narrative into a single markdown report with sections:
    1. **Month in numbers** (3-5 metric cards with MoM delta + sparkline-character)
    2. **Traffic health** (GA4 sessions chart, top landing pages, user engagement)
    3. **Search visibility** (GSC impressions, top queries, new ranking pages)
    4. **What we did this month** (narrative)
    5. **What's next month** (forecast + priorities)
    6. **Status:** 🟢 healthy / 🟡 watch / 🔴 needs attention (auto-assigned by rules)
  - War-room A-grade floor enforced
  - `scripts/client_monthly_report.py --client <id> --month YYYY-MM` — standalone CLI
- acceptance_criteria:
  - Report under 1000 words
  - Every metric has a prior-month comparison
  - Status is rule-based and explainable in the report
  - War-room A-grade floor enforced

### Phase 5: delivery-and-approval

- task_type: phase
- depends_on: [4]
- inputs:
  - Phase 4 report
  - Client contact email
  - Solon's Slack DM (for first 4 reports per client + red-status cases)
- outputs:
  - `lib/client_reporting/delivery.py` → two modes:
    - **Review mode** (default for new clients): posts report to Solon's Slack DM with 👍 / ✋ / 🔄 reactions. On 👍, sends email. On ✋, saves to drafts. On 🔄, regenerates (max 2). Rolled up to auto-ship mode after 4 consecutive 👍 reports without edits.
    - **Auto-ship mode** (unlocked per-client): posts to Solon's Slack DM with a 24-hour review window. Sends automatically if no ✋ by 09:00 next day.
  - Red-status reports ALWAYS fall back to review mode regardless of auto-ship mode (safety catch)
  - Email delivery via existing Google Workspace SMTP or Resend (shared config with Thread 3)
  - Follow-up tasks auto-created in `public.tasks` table for any action items surfaced in the narrative
- acceptance_criteria:
  - Zero reports ship without at least the 24-hour auto-ship window
  - First 4 reports per client require explicit 👍
  - Red-status always re-gates to manual approval
  - Follow-up tasks land in the queue with the correct client project_id tag

---

## 3. Risks & mitigations

| # | Risk | Mitigation |
|---|---|---|
| 1 | **GA4 / GSC service account doesn't have access to a client's property.** | Phase 2 adapter emits a "needs access" warning that surfaces in the report and as a Solon Slack ping. Report still generates with the remaining data. Solon adds the service account email as a viewer in the client's GA4/GSC panel. |
| 2 | **Narrative fabricates deliverables Titan didn't actually do.** | Narrative prompt is constrained to "reference only rows in mp_runs/tasks for this project_id"; war-room grading includes a "citation check" dimension that flags any deliverable not matched to an actual row. |
| 3 | **Auto-ship mode accidentally ships a bad report.** | 24-hour silent-review window gives Solon an explicit veto. Red-status reports always re-gate. Solon can revoke a client's auto-ship status via `bin/client-unauto.sh <project_id>`. |
| 4 | **Client asks for a metric Titan isn't tracking** (e.g. "where's my LinkedIn follower count?"). | Metric profile is Solon-authored per client; new metrics require Solon to update the profile. Report does NOT auto-add metrics that weren't in the profile. |
| 5 | **Monthly cadence drifts** — some clients want weekly, some bi-monthly. | Per-client cadence config in `client_metric_profiles.cadence_cron`. Default monthly (1st of month 09:00). |

---

## 4. Acceptance criteria

1. One report per active client per month, delivered on the 1st of the following month by 09:00 local
2. Report is fully computed from live metric sources + mp_runs + tasks — no hand entry
3. War-room A-grade floor on every report
4. Auto-ship mode unlocks after 4 consecutive approved reports per client
5. Red-status re-gates to manual review
6. Follow-up tasks land in the operator queue
7. Rollback disables the monthly cron without losing historical reports

---

## 5. Rollback path

1. **Cron disable:** `systemctl disable titan-client-reports-monthly.timer`
2. **Policy flag:** `autopilot.client_reporting_enabled=false`
3. **Per-client disable:** `UPDATE clients SET reporting_enabled=false WHERE project_id=<x>;`
4. **Revoke auto-ship:** `bin/client-unauto.sh <project_id>` returns the client to review mode
5. **Historical reports preserved in `client_reports` + `plans/client-reports/*.md`**

---

## 6. Honest scope cuts

- Real-time dashboards — this is monthly reporting, not live
- Looker Studio-style interactive charts — markdown + static assets only
- Multi-brand / white-label reports — AMG branding only
- Competitor comparison — out of scope
- Paid ad metrics (Google Ads, Meta Ads) — out of scope v1; add adapters later if a client needs them
- Custom per-client templates — all clients share the same report structure in v1
- Video/audio monthly updates — text + markdown + embedded images only
- Bulk re-run of historical months — one-shot backfill available via CLI but not cron

---

## 7. Phase 1 output — Architecture

```
  client_metric_profiles (SQL)
            │
            │ fetch on schedule
            ▼
   ┌─────────────────────┐      ┌───────────────────┐
   │  GA4 + GSC + other  │      │  mp_runs + tasks  │
   │  metric adapters    │      │  (harness native) │
   └────────┬────────────┘      └─────────┬─────────┘
            │                             │
            └──────────────┬──────────────┘
                           ▼
                  assembler.py
                     │
                     │ war-room A grade
                     ▼
              report.md (1-page)
                     │
             ┌───────┴───────┐
             │               │
        review mode     auto-ship mode
       (first 4 rpts)   (after 4 approvals)
             │               │
             │               │ 24hr veto window
             │               ▼
             └───────────▶ email to client
                             │
                             ▼
                    follow-up tasks
                    → public.tasks (project_id tagged)
```

---

## 8. War-room grade

| # | Dim | Score | Note |
|---|---|---:|---|
| 1 | Correctness | 9.4 | GA4 + GSC APIs correctly referenced. Service account pattern is standard. Review/auto-ship transition is explicit and bounded. |
| 2 | Completeness | 9.4 | 5 phases with full fields. Covers profiles, adapters, narrative, assembly, delivery. |
| 3 | Honest scope | 9.5 | 8 scope cuts. No competitor analysis, no paid ads, no Looker Studio. |
| 4 | Rollback | 9.5 | 5-path rollback including per-client disable + auto-ship revocation. |
| 5 | Harness fit | 9.4 | Uses substrate: llm_client, war_room, Supabase, Slack. New SQL tables consistent with pattern. |
| 6 | Actionability | 9.3 | Phases are concrete but specific client names + GA4 property IDs are Solon-owned, so some implementation waits on his roster file. |
| 7 | Risk coverage | 9.4 | 5 risks covering access gaps, narrative fabrication, auto-ship misfires, scope requests, cadence variation. |
| 8 | Evidence | 9.3 | GA4 Data API + GSC API facts cited; service account pattern is standard practice. |
| 9 | Consistency | 9.5 | Phases chain cleanly. Review → auto-ship transition is rule-based and explainable. |
| 10 | Ship-ready | 9.3 | Would ship as Phase 1 tomorrow. Solon-action dependency: client roster + service account. |

**Overall grade: A (9.40/10) — SHIP.** At the A-grade floor.

### Solon action items

1. **Client roster** — list of active clients: name, project_id, domain, contact email, active/paused
2. **Metric profile per client** — 3-5 metrics each wants to see
3. **Google service account creation** (one JSON, shared across clients) with Google Analytics Data Viewer + Search Console Reader scopes — Solon adds the service account email as a viewer in each client's GA4 property and Search Console
4. **Decide email sender rail:** Google Workspace SMTP (default) or Resend (better analytics, ~$20/mo)
5. **Cadence preference per client** (default monthly) — can be overridden
6. **Red-status thresholds:** Solon sets the rules ("organic traffic drop >20% MoM = red", "no new leads from this channel in 30 days = yellow", etc.)
