"""
titan-harness/lib/back_office.py

Thread 4 of the Autopilot Suite — Back-Office Autopilot.
See plans/PLAN_2026-04-11_back-office-autopilot.md for the full DR.

Weekly cadence: ingest PayPal CSV exports → reconcile expected vs
received → classify churn/late/healthy → generate 1-page money+risk
report for Solon's Slack DM.

Status: STUB module — public API shipped, implementation TODO per
DR's 4-phase plan.

Phase wiring:
  Phase 1 payment-data-ingest          → import_paypal_csv() (TODO)
  Phase 2 reconciler                   → reconcile() (TODO)
  Phase 3 churn-and-late-detector      → scan_risk() (TODO)
  Phase 4 weekly-money-risk-report     → generate_weekly_report() (TODO)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Optional


class ReconciliationClass(str, Enum):
    PAID_ON_TIME = "paid_on_time"
    PAID_LATE = "paid_late"
    OVERPAID = "overpaid"
    UNDERPAID = "underpaid"
    MISSING = "missing"
    PENDING = "pending"
    NEEDS_SOLON_REVIEW = "needs_solon_review"


class CustomerStatus(str, Enum):
    HEALTHY = "healthy"
    AT_RISK = "at_risk"
    LATE = "late"
    CHURNED = "churned"


@dataclass
class ReceivedPayment:
    paypal_txn_id: Optional[str]
    processor: str  # 'paypal' | 'paymentcloud' | 'dodo' | 'durango' | 'wise' | 'zelle' | 'wire' | 'other'
    customer_email: Optional[str]
    customer_name: Optional[str]
    gross_amount_usd: Decimal
    fee_usd: Optional[Decimal]
    net_amount_usd: Optional[Decimal]
    txn_date: date
    subscription_id: Optional[str] = None
    invoice_id: Optional[str] = None
    memo: Optional[str] = None


@dataclass
class ExpectedPayment:
    customer_email: str
    customer_name: Optional[str]
    amount_usd: Decimal
    due_date: date
    source: str  # 'manual' | 'build_proposal' | 'subscription' | 'invoice'
    subscription_id: Optional[str] = None
    invoice_id: Optional[str] = None
    plan_id: Optional[str] = None
    valid_until: Optional[date] = None


@dataclass
class ReconciliationEvent:
    expected_payment_id: Optional[str]
    received_payment_id: Optional[str]
    classification: ReconciliationClass
    variance_amount_usd: Optional[Decimal] = None
    variance_days: Optional[int] = None
    notes: Optional[str] = None


@dataclass
class CustomerRiskStatus:
    customer_email: str
    customer_name: Optional[str]
    status: CustomerStatus
    reasoning: str
    recommended_action: str
    mrr_usd: Decimal
    last_payment_date: Optional[date] = None
    missed_payment_count: int = 0


@dataclass
class MoneyRiskReport:
    week_start: date
    week_end: date
    received_total_usd: Decimal
    expected_total_usd: Decimal
    delta_usd: Decimal
    active_subscription_count: int
    mrr_usd: Decimal
    mrr_delta_usd: Decimal
    healthy: list[CustomerRiskStatus] = field(default_factory=list)
    at_risk: list[CustomerRiskStatus] = field(default_factory=list)
    late: list[CustomerRiskStatus] = field(default_factory=list)
    churned_this_week: list[CustomerRiskStatus] = field(default_factory=list)
    reconciliation_exceptions: list[ReconciliationEvent] = field(default_factory=list)
    report_markdown: str = ""
    war_room_grade: Optional[str] = None


# ---------------------------------------------------------------------------
# Phase 1 — ingest (TODO)
# ---------------------------------------------------------------------------

def import_paypal_csv(csv_path: Path,
                      project_id: str = "EOM") -> dict:
    """Parse a PayPal transactions CSV export and upsert into
    received_payments. Idempotent via paypal_txn_id.

    Resilient to column-name changes (matches by header, not position).
    Raises on unknown columns with a helpful error.

    TODO: implement Phase 1. Currently stubbed.
    """
    raise NotImplementedError(
        "import_paypal_csv: Phase 1 payment-data-ingest not yet implemented. "
        "See plans/PLAN_2026-04-11_back-office-autopilot.md Phase 1 spec."
    )


# ---------------------------------------------------------------------------
# Phase 2 — reconciler (TODO)
# ---------------------------------------------------------------------------

def reconcile(project_id: str = "EOM",
              since_days: int = 35) -> list[ReconciliationEvent]:
    """Join expected_payments vs received_payments, classify each
    expected row, write to reconciliation_events.

    Scored candidate matching:
      email exact > email domain match > amount+date±5 days > manual review

    TODO: implement Phase 2. Currently stubbed.
    """
    raise NotImplementedError(
        "reconcile: Phase 2 reconciler not yet implemented."
    )


# ---------------------------------------------------------------------------
# Phase 3 — risk scan (TODO)
# ---------------------------------------------------------------------------

def scan_risk(project_id: str = "EOM") -> list[CustomerRiskStatus]:
    """Classify each active customer as healthy/at_risk/late/churned.

    Rules:
      churned  = 2+ consecutive missed payments OR explicit cancellation
      at_risk  = 1 missed payment OR reduced amount (>5% drop)
      late     = current expected payment >5 days past due
      healthy  = all expected matched within tolerance in past 90 days

    TODO: implement Phase 3. Currently stubbed.
    """
    raise NotImplementedError(
        "scan_risk: Phase 3 churn-and-late-detector not yet implemented."
    )


# ---------------------------------------------------------------------------
# Phase 4 — weekly report (TODO)
# ---------------------------------------------------------------------------

def generate_weekly_report(week_start: Optional[date] = None,
                           project_id: str = "EOM",
                           deliver_to_slack: bool = True) -> MoneyRiskReport:
    """Assemble the one-page weekly report, war-room grade it, deliver
    to Solon's Slack DM, save to plans/money-risk/<yyyy-mm-dd>.md.

    Report structure per DR Phase 4 acceptance_criteria:
      1. This week's revenue (received vs expected, delta)
      2. Active subscriptions (N customers, MRR, delta)
      3. Healthy (count)
      4. At-risk (customer names + reason + action)
      5. Late (customer names + days late + amount + action)
      6. Churned this week (names + reason)
      7. Reconciliation exceptions (needs Solon eye)
      8. Cashflow snapshot (7d, 30d, 30d-expected)

    TODO: implement Phase 4. Currently stubbed.
    """
    raise NotImplementedError(
        "generate_weekly_report: Phase 4 weekly-money-risk-report not yet "
        "implemented."
    )


def is_enabled() -> bool:
    """True iff policy.yaml autopilot.back_office_enabled is true."""
    import os
    return os.environ.get("POLICY_AUTOPILOT_BACK_OFFICE_ENABLED", "0") == "1"
