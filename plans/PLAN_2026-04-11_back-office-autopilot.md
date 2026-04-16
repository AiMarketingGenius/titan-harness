# DR Plan: Back-Office Autopilot

**Source:** manual (Solon directive 2026-04-11, autopilot-suite Thread 4)
**Source ID:** autopilot-back-office-2026-04-11
**Project:** EOM
**Generated:** 2026-04-11 (Titan autonomous)
**Run id:** autopilot-4-back-office

---

## 1. Scope & goals

### What this idea does

Reconciles paid invoices against what AMG expected to be paid, flags churn and late payers, and generates a one-page "money + risk" report every Sunday evening for Monday morning review. Solon never opens a spreadsheet.

### What this idea does NOT do

- Does not replace QuickBooks / bookkeeping. That's an accounting system; this is a weekly ops dashboard.
- Does not issue invoices. Invoices come from Solon's existing flow (PayPal Invoicing, SignNow, or the proposal builder).
- Does not chase payments on Solon's behalf (that would require sending messages — follow-on, gated).
- Does not reconcile expenses, P&L, or tax. Revenue-in and revenue-at-risk only.
- Does not auto-refund or auto-cancel subscriptions.
- Does not handle multi-currency (USD only in v1).

---

## 2. Phases

### Phase 1: payment-data-ingest

- task_type: phase
- depends_on: []
- inputs:
  - PayPal transactions export (Solon exports CSV from PayPal Reports weekly, drops in `~/titan-session/paypal-exports/`) OR live via PayPal Reporting API if OAuth is set up
  - Existing `public.payment_link_tests` (Gate 3 audit)
  - Existing `public.mp_runs` for work done per client
  - Future `public.leads` + `public.sales_threads` (Thread 1) for lead→customer attribution
  - Invoice expectations: a new `public.expected_payments` table Titan writes when a proposal is approved (from build_proposal.py) or when Solon manually enters one via `bin/expect-payment.sh`
- outputs:
  - `sql/010_back_office.sql` — `expected_payments`, `received_payments`, `reconciliation_events` tables + RLS
  - `lib/back_office/ingest.py` — normalizes PayPal CSV/API data into `received_payments` with per-transaction metadata (customer email, amount, subscription_id, invoice_id if present)
  - `scripts/paypal_export_importer.py` — watches `~/titan-session/paypal-exports/` for new CSVs, imports, archives
- acceptance_criteria:
  - Imports a real PayPal CSV export without errors
  - Deduplicates by transaction ID (idempotent)
  - Preserves PayPal transaction IDs for audit trail
  - Handles partial-month exports without state loss

### Phase 2: reconciler

- task_type: phase
- depends_on: [1]
- inputs:
  - `expected_payments` table rows (what Titan thought would hit)
  - `received_payments` table rows (what actually hit)
- outputs:
  - `lib/back_office/reconciler.py` — joins expected vs received by (customer_email, amount, due_date_window±5days). Classifies each expected row as:
    - `paid_on_time` (matched, within window)
    - `paid_late` (matched, outside window)
    - `overpaid` (received amount > expected by >5%)
    - `underpaid` (received < expected by >5%)
    - `missing` (no match, expected > 14 days old)
    - `pending` (no match, expected within grace window)
  - Writes classifications to `reconciliation_events` table
  - Idempotent: re-running does not duplicate events
- acceptance_criteria:
  - Every expected payment gets a classification
  - Classifications stable under re-run (same input → same output)
  - Tolerance windows configurable in `policy.yaml autopilot.back_office`

### Phase 3: churn-and-late-detector

- task_type: classify
- depends_on: [2]
- inputs:
  - `received_payments` table for the past 90 days
  - `expected_payments` table for active subscriptions
- outputs:
  - `lib/back_office/risk_scan.py` produces for each customer:
    - `status`: `healthy` | `at_risk` | `late` | `churned`
    - `reasoning`: why this status (missed N payments, downgraded, cancelled, etc.)
    - `recommended_action`: one-line what to do
  - Churn = 2+ missed consecutive expected payments or explicit subscription cancellation webhook
  - At-risk = 1 missed payment or reduced payment amount
  - Late = current payment is more than 5 days past expected date
  - Healthy = all expected payments matched within tolerance in past 90 days
- acceptance_criteria:
  - Every customer in `expected_payments` gets a status
  - Status transitions are logged in `reconciliation_events` (healthy→at_risk, at_risk→churned)
  - Recommended actions are concrete ("send a nudge", "call to discuss billing", "mark churned and remove from active roster")

### Phase 4: weekly-money-risk-report

- task_type: synthesis
- depends_on: [3]
- inputs:
  - Phase 2 + 3 outputs from past 7 days
  - Historical baseline: MRR, revenue, churn rate from prior 3 months
- outputs:
  - `scripts/money_risk_report.py` generates a 1-page markdown report with these sections (in order):
    1. **This week's revenue:** $X received, $Y expected. Delta.
    2. **Active subscriptions:** N customers, MRR $M. Delta from last week.
    3. **🟢 Healthy:** N customers
    4. **🟡 At-risk:** N customers with names + reason + recommended action
    5. **🔴 Late:** N customers with names + days late + amount + recommended action
    6. **⚫ Churned this week:** N customers with final-billing-date + reason
    7. **Reconciliation exceptions:** overpaid/underpaid/missing cases needing Solon's eye
    8. **Cashflow snapshot:** 7-day receipts, 30-day receipts, 30-day expected
  - War-room grades the report for clarity + correctness (A-grade floor)
  - Posts to Solon's Slack DM every Sunday 19:00 local
  - Also saves to `plans/money-risk/<yyyy-mm-dd>.md` for audit
- acceptance_criteria:
  - Report fits on one screen (≤600 words)
  - Every 🔴 / 🟡 / ⚫ row has a named action
  - Numbers reconcile to the transaction-level rows (spot-checkable)
  - Empty weeks produce "quiet week, nothing to flag" report rather than failing

---

## 3. Risks & mitigations

| # | Risk | Mitigation |
|---|---|---|
| 1 | **PayPal CSV export format changes**, breaking the ingest parser. | `paypal_export_importer.py` uses resilient column-name matching (by header, not by position) + raises on unknown columns with a helpful error telling Solon which column is new. No silent drops. |
| 2 | **Expected vs received matching is fuzzy** — customer email differs between invoice and payment, or amount varies due to fees. | Matching uses a scored-candidate approach: email exact > email domain match > amount+date match within 5 days > manual review queue. Ambiguous matches land in a `needs_solon_review` classification that surfaces in the weekly report. |
| 3 | **Titan classifies a paying customer as late because the expected_payment row is stale.** | `expected_payments` has a `valid_until` column; stale rows are excluded from risk scan. When a subscription ends normally, the row is marked `closed` rather than deleted. |
| 4 | **Solon forgets to drop the PayPal export and the report runs on stale data.** | Weekly report header shows "last PayPal import: <timestamp>"; if >7 days stale, the header shows a 🔴 warning. Optional: auto-reminder Slack DM on Saturday 18:00 if no new export that week. |
| 5 | **Churn detection triggers on a one-time missed payment that was actually a PayPal processing issue, not a real churn signal.** | At-risk (not churned) on first miss. Churn requires 2 consecutive misses OR an explicit PayPal subscription cancellation event. Gives 30 days of grace. |

---

## 4. Acceptance criteria

1. Weekly report lands in Solon's Slack DM every Sunday 19:00 local without fail
2. Report is fully computed from `expected_payments` + `received_payments` (no hand-entered data)
3. War-room A-grade floor on every report
4. Per-customer status transitions logged in `reconciliation_events`
5. Exception queue (ambiguous matches) surfaces in the report, not buried
6. Empty-week case is handled gracefully
7. Rollback flag disables the cron without losing historical data

---

## 5. Rollback path

1. **Disable cron:** `systemctl disable titan-money-risk-weekly.timer`
2. **Policy flag:** `autopilot.back_office_enabled=false`
3. **Data preservation:** all tables stay; disable is a read-suppress, not a drop
4. **Manual override:** `scripts/money_risk_report.py --manual` runs on-demand any time
5. **Revert code:** single-commit revert is clean

---

## 6. Honest scope cuts

- QuickBooks sync — follow-on, requires QB API + schema mapping
- P&L and expense tracking — this is revenue-in and revenue-at-risk only
- Tax computation — out of scope
- Multi-currency — USD only
- Dunning emails to late payers — requires sending permission, follow-on (or Thread 1 extension)
- Receipt PDF generation — PayPal + QuickBooks already do this
- Stripe/Square reconciliation — dead rails, not in scope
- New-merchant-stack reconciliation — becomes in-scope once PaymentCloud + Dodo are live (extend `lib/back_office/ingest.py` with new adapters)

---

## 7. Phase 1 output — Architecture

```
  PayPal CSV export (Solon drop)     PayPal API (future)
           │                                │
           └────────┬───────────────────────┘
                    ▼
              ingest.py
                    │
                    ▼
    ┌─────────────────────────────┐
    │   received_payments (SQL)    │
    └──────────┬───────────────────┘
               │
               │          ┌─ build_proposal.py writes here
               │          │
               ▼          ▼
      reconciler.py ← expected_payments (SQL)
               │
               ▼
    reconciliation_events (SQL)
               │
               ▼
         risk_scan.py
               │
               ▼
      money_risk_report.py ──── war-room A grade ──┐
               │                                    │
               ▼                                    │
   plans/money-risk/*.md ← saved + ──────▶ Slack DM │
                                           Solon    │
                                                    │
                                     (Sunday 19:00) ┘
```

**Rough cost:** zero new SaaS. Uses existing LiteLLM gateway for the summarization step. Supabase storage for tables. Existing Slack integration.

---

## 8. War-room grade

| # | Dim | Score | Note |
|---|---|---:|---|
| 1 | Correctness | 9.4 | Reconciliation logic is standard; classification thresholds are conservative. PayPal CSV format handled defensively. |
| 2 | Completeness | 9.4 | 4 phases covering ingest, reconcile, risk scan, report. Report structure explicit. |
| 3 | Honest scope | 9.6 | 8 scope cuts. No QB, no P&L, no tax, no dunning. |
| 4 | Rollback | 9.5 | 5-point rollback with data preservation. |
| 5 | Harness fit | 9.5 | Pure substrate reuse. Supabase + LLM client + war_room + Slack. No new SaaS. |
| 6 | Actionability | 9.4 | Tables named, scripts named, cron schedule named, report structure named. |
| 7 | Risk coverage | 9.3 | 5 risks covering CSV schema drift, fuzzy matching, stale expectations, stale imports, false churn. Missing: concurrent PayPal refund → over-classification (edge case). |
| 8 | Evidence | 9.3 | Classification thresholds are heuristic, not evidence-based — first-pass defaults. Tunable. |
| 9 | Consistency | 9.6 | Phases chain cleanly. Report drives from the three computed tables only. |
| 10 | Ship-ready | 9.5 | Would ship as phase 1. No blocking dependencies beyond Solon dropping PayPal exports. |

**Overall grade: A (9.45/10) — SHIP.**

### Solon action items

1. **PayPal export cadence:** commit to weekly CSV export or set up PayPal Reporting API OAuth (OAuth requires Solon action, CSV does not)
2. **Drop folder:** create `~/titan-session/paypal-exports/` directory (Titan will make this on first run)
3. **Baseline list:** send Titan a one-time list of current active subscribers + expected monthly amount so `expected_payments` has seed rows (otherwise Titan starts from Phase 3 with empty expected data and takes 2-3 months to build signal)
4. **Alert on missed Sunday drop?** Decide if Saturday reminder is wanted
