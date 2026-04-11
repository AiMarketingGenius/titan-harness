"""
titan-harness/lib/client_reporting.py

Thread 5 of the Autopilot Suite — Client Reporting Autopilot.
See plans/PLAN_2026-04-11_client-reporting-autopilot.md for the full DR.

Monthly cadence: for each active client, pull GA4 + GSC + other metric
sources → narrate "what we did" / "what's next" from mp_runs + tasks →
assemble one-page markdown report → war-room grade → Slack-gated review
for first 4 reports per client, auto-ship after 4 consecutive approvals.

Status: STUB module — public API shipped, implementation TODO per
DR's 5-phase plan.

Phase wiring:
  Phase 1 client-roster-and-metric-profiles → Client + MetricProfile shipped
  Phase 2 metric-source-adapters             → fetch_*_metrics() (TODO)
  Phase 3 what-we-did narrative              → build_narrative() (TODO)
  Phase 4 report-assembler                   → assemble_report() (TODO)
  Phase 5 delivery-and-approval              → deliver_report() (TODO)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class ClientStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CHURNED = "churned"
    PROSPECT = "prospect"


class ReportStatus(str, Enum):
    DRAFT = "draft"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    AUTO_SHIPPING = "auto_shipping"
    SENT = "sent"
    HELD = "held"
    REGENERATING = "regenerating"
    FAILED = "failed"


@dataclass
class Client:
    """Mirrors public.clients."""
    project_id: str
    name: str
    primary_domain: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    status: ClientStatus = ClientStatus.ACTIVE
    cadence_cron: str = "0 9 1 * *"  # 1st of month 09:00
    auto_ship_enabled: bool = False
    auto_ship_approvals: int = 0
    auto_ship_unlock_at: int = 4
    red_status_rules: Optional[dict] = None


@dataclass
class MetricProfile:
    """Per-client metric source mapping."""
    project_id: str
    ga4_property_id: Optional[str] = None
    gsc_site_url: Optional[str] = None
    posthog_project_id: Optional[str] = None
    umami_website_id: Optional[str] = None
    tracked_metrics: list[str] = field(default_factory=list)
    custom_kpi_sql: Optional[str] = None


@dataclass
class MetricsBundle:
    """Common shape returned by all metric adapters."""
    source: str                              # 'ga4' | 'gsc' | 'posthog' | 'umami'
    period_start: date
    period_end: date
    metrics: dict[str, float | int]          # e.g. {'sessions': 1234, 'conversions': 12}
    top_items: list[dict] = field(default_factory=list)  # top pages/queries/etc.
    previous_period: Optional[dict[str, float | int]] = None
    errors: list[str] = field(default_factory=list)


@dataclass
class ClientReport:
    """One row in public.client_reports."""
    id: Optional[str]
    project_id: str
    month_iso: str                           # '2026-03'
    metrics_bundle: list[MetricsBundle]
    narrative_text: str
    report_markdown: str
    status: ReportStatus = ReportStatus.DRAFT
    red_status: bool = False
    war_room_grade: Optional[str] = None
    delivery_recipient: Optional[str] = None
    delivery_sent_at: Optional[datetime] = None
    follow_up_task_ids: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 2 — metric source adapters (TODO)
# ---------------------------------------------------------------------------

def fetch_ga4_metrics(property_id: str,
                      start_date: date,
                      end_date: date) -> MetricsBundle:
    """Pull GA4 metrics via the google-analytics-data Python SDK.

    Returns sessions, users, engaged_sessions, conversions, plus top
    landing pages. Previous-period comparison is a second call with
    shifted dates.

    TODO: Phase 2 GA4 adapter. Currently stubbed.
    """
    raise NotImplementedError(
        "fetch_ga4_metrics: Phase 2 metric-source-adapters (GA4) not yet "
        "implemented. Requires google-analytics-data + service account JSON."
    )


def fetch_gsc_metrics(site_url: str,
                      start_date: date,
                      end_date: date) -> MetricsBundle:
    """Pull Search Console metrics via google-api-python-client.

    Returns impressions, clicks, ctr, top queries, top pages.

    TODO: Phase 2 GSC adapter. Currently stubbed.
    """
    raise NotImplementedError(
        "fetch_gsc_metrics: Phase 2 metric-source-adapters (GSC) not yet "
        "implemented. Requires google-api-python-client + service account JSON."
    )


# ---------------------------------------------------------------------------
# Phase 3 — narrative (TODO)
# ---------------------------------------------------------------------------

def build_narrative(project_id: str,
                    month_iso: str) -> str:
    """Generate the 'what we did' / 'what's next' narrative from
    mp_runs + tasks + plans filtered by project_id.

    Single LLM call via lib/llm_client.complete(task_type='synthesis').
    Never fabricates deliverables — war-room grading includes a
    citation-check dimension.

    TODO: Phase 3 narrative. Currently stubbed.
    """
    raise NotImplementedError(
        "build_narrative: Phase 3 what-we-did-narrative not yet implemented."
    )


# ---------------------------------------------------------------------------
# Phase 4 — report assembler (TODO)
# ---------------------------------------------------------------------------

def assemble_report(client: Client,
                    metrics_bundles: list[MetricsBundle],
                    narrative: str) -> ClientReport:
    """Assemble the final one-page markdown report with:
      1. Month in numbers (3-5 metric cards with MoM delta)
      2. Traffic health
      3. Search visibility
      4. What we did this month (narrative)
      5. What's next month
      6. Status badge (🟢/🟡/🔴)

    War-room A-grade floor enforced.

    TODO: Phase 4 report-assembler. Currently stubbed.
    """
    raise NotImplementedError(
        "assemble_report: Phase 4 report-assembler not yet implemented."
    )


# ---------------------------------------------------------------------------
# Phase 5 — delivery + approval (TODO)
# ---------------------------------------------------------------------------

def deliver_report(report: ClientReport,
                   client: Client,
                   mode: Optional[str] = None) -> ClientReport:
    """Deliver report via Solon's Slack DM (review mode) or via email
    direct to client after 24-hour veto window (auto-ship mode).

    mode override: 'review' | 'auto_ship' | None (uses client setting)

    Red-status reports ALWAYS fall back to review mode regardless of
    auto_ship_enabled.

    After 4 consecutive approved reports without edits, client's
    auto_ship_enabled is flipped to True automatically.

    TODO: Phase 5 delivery-and-approval. Currently stubbed.
    """
    raise NotImplementedError(
        "deliver_report: Phase 5 delivery-and-approval not yet implemented."
    )


def is_enabled() -> bool:
    """True iff policy.yaml autopilot.client_reporting_enabled is true."""
    import os
    return os.environ.get("POLICY_AUTOPILOT_CLIENT_REPORTING_ENABLED", "0") == "1"
