#!/usr/bin/env python3
"""
lib/subsystem_health.py
MP-3 §4 — 7 Subsystem Health Flags with Quantitative Thresholds

Implements per-subsystem health evaluation using the thresholds from MP-3 §4.
Each subsystem has measurable "healthy" and "needs_attention" triggers.

Health flags are consumed by:
  - Orb state machine (lib/orb_state_machine.py)
  - Mobile/desktop dashboards
  - Daily Slack summaries
  - MCP logging on threshold crossings
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    NEEDS_ATTENTION = "needs_attention"
    UNKNOWN = "unknown"


@dataclass
class SubsystemMetrics:
    """Raw metrics for a single subsystem evaluation."""
    # Inbound (1)
    lead_response_latency_hours: float = 0.0
    stale_lead_backlog: int = 0

    # Outbound (2)
    complaint_rate_pct: float = 0.0
    bounce_rate_pct: float = 0.0
    sequence_paused_by_guardian: bool = False

    # Nurture (3)
    unsubscribe_rate_pct: float = 0.0
    stalled_sequence_hours: float = 0.0

    # Onboarding (4)
    checklist_step_stalled_hours: float = 0.0

    # Fulfillment (5)
    missed_deliverable_hours: float = 0.0
    consecutive_reviewer_rejections: int = 0

    # Reporting (6)
    report_generation_failed: bool = False
    data_discrepancy_unresolved_hours: float = 0.0

    # Upsell/Retain (7)
    renewal_past_due_days: int = 0
    engagement_drop_wow_pct: float = 0.0
    churn_signal_detected: bool = False


@dataclass
class SubsystemHealthResult:
    name: str
    status: HealthStatus
    triggers: list[str]  # why this status
    metrics_snapshot: dict = field(default_factory=dict)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# --- Per-subsystem evaluation functions ---

SUBSYSTEM_NAMES = [
    "inbound",
    "outbound",
    "nurture",
    "onboarding",
    "fulfillment",
    "reporting",
    "upsell_retain",
]


def _eval_inbound(m: SubsystemMetrics) -> SubsystemHealthResult:
    triggers = []
    if m.lead_response_latency_hours > 4:
        triggers.append(f"Lead response latency {m.lead_response_latency_hours:.1f}h > 4h")
    if m.stale_lead_backlog >= 3:
        triggers.append(f"Stale lead backlog {m.stale_lead_backlog} >= 3")

    return SubsystemHealthResult(
        name="inbound",
        status=HealthStatus.NEEDS_ATTENTION if triggers else HealthStatus.HEALTHY,
        triggers=triggers or ["Lead response ≤4h, backlog clean"],
        metrics_snapshot={"latency_h": m.lead_response_latency_hours, "stale_backlog": m.stale_lead_backlog},
    )


def _eval_outbound(m: SubsystemMetrics) -> SubsystemHealthResult:
    triggers = []
    if m.complaint_rate_pct > 0.08:
        triggers.append(f"Complaint rate {m.complaint_rate_pct:.3f}% > 0.08%")
    if m.bounce_rate_pct > 4:
        triggers.append(f"Bounce rate {m.bounce_rate_pct:.1f}% > 4%")
    if m.sequence_paused_by_guardian:
        triggers.append("Sequence paused by auto-guardian")

    return SubsystemHealthResult(
        name="outbound",
        status=HealthStatus.NEEDS_ATTENTION if triggers else HealthStatus.HEALTHY,
        triggers=triggers or ["Complaint ≤0.08%, bounce ≤4%, sequences running"],
        metrics_snapshot={"complaint_pct": m.complaint_rate_pct, "bounce_pct": m.bounce_rate_pct},
    )


def _eval_nurture(m: SubsystemMetrics) -> SubsystemHealthResult:
    triggers = []
    if m.unsubscribe_rate_pct > 1.5:
        triggers.append(f"Unsubscribe rate {m.unsubscribe_rate_pct:.1f}% > 1.5%")
    if m.stalled_sequence_hours >= 48:
        triggers.append(f"Sequence stalled {m.stalled_sequence_hours:.0f}h >= 48h")

    return SubsystemHealthResult(
        name="nurture",
        status=HealthStatus.NEEDS_ATTENTION if triggers else HealthStatus.HEALTHY,
        triggers=triggers or ["Unsub ≤1.5%, all sequences advancing"],
        metrics_snapshot={"unsub_pct": m.unsubscribe_rate_pct, "stalled_h": m.stalled_sequence_hours},
    )


def _eval_onboarding(m: SubsystemMetrics) -> SubsystemHealthResult:
    triggers = []
    if m.checklist_step_stalled_hours >= 72:
        triggers.append(f"Checklist step stalled {m.checklist_step_stalled_hours:.0f}h >= 72h SLA")

    return SubsystemHealthResult(
        name="onboarding",
        status=HealthStatus.NEEDS_ATTENTION if triggers else HealthStatus.HEALTHY,
        triggers=triggers or ["All checklist steps within SLA"],
        metrics_snapshot={"stalled_h": m.checklist_step_stalled_hours},
    )


def _eval_fulfillment(m: SubsystemMetrics) -> SubsystemHealthResult:
    triggers = []
    if m.missed_deliverable_hours > 24:
        triggers.append(f"Deliverable missed by {m.missed_deliverable_hours:.0f}h > 24h")
    if m.consecutive_reviewer_rejections >= 2:
        triggers.append(f"{m.consecutive_reviewer_rejections} consecutive Reviewer Loop rejections")

    return SubsystemHealthResult(
        name="fulfillment",
        status=HealthStatus.NEEDS_ATTENTION if triggers else HealthStatus.HEALTHY,
        triggers=triggers or ["All deliverables on time, no repeated rejections"],
        metrics_snapshot={"missed_h": m.missed_deliverable_hours, "rejections": m.consecutive_reviewer_rejections},
    )


def _eval_reporting(m: SubsystemMetrics) -> SubsystemHealthResult:
    triggers = []
    if m.report_generation_failed:
        triggers.append("Report generation failed")
    if m.data_discrepancy_unresolved_hours > 2:
        triggers.append(f"Data discrepancy unresolved {m.data_discrepancy_unresolved_hours:.1f}h > 2h")

    return SubsystemHealthResult(
        name="reporting",
        status=HealthStatus.NEEDS_ATTENTION if triggers else HealthStatus.HEALTHY,
        triggers=triggers or ["All reports on time, no data discrepancies"],
        metrics_snapshot={"failed": m.report_generation_failed, "discrepancy_h": m.data_discrepancy_unresolved_hours},
    )


def _eval_upsell_retain(m: SubsystemMetrics) -> SubsystemHealthResult:
    triggers = []
    if m.renewal_past_due_days > 7:
        triggers.append(f"Renewal past due {m.renewal_past_due_days}d > 7d")
    if m.engagement_drop_wow_pct >= 30:
        triggers.append(f"Engagement dropped {m.engagement_drop_wow_pct:.0f}% WoW >= 30%")
    if m.churn_signal_detected:
        triggers.append("Direct churn signal detected")

    return SubsystemHealthResult(
        name="upsell_retain",
        status=HealthStatus.NEEDS_ATTENTION if triggers else HealthStatus.HEALTHY,
        triggers=triggers or ["Renewals on track, engagement stable"],
        metrics_snapshot={"past_due_d": m.renewal_past_due_days, "engagement_drop": m.engagement_drop_wow_pct},
    )


_EVALUATORS = {
    "inbound": _eval_inbound,
    "outbound": _eval_outbound,
    "nurture": _eval_nurture,
    "onboarding": _eval_onboarding,
    "fulfillment": _eval_fulfillment,
    "reporting": _eval_reporting,
    "upsell_retain": _eval_upsell_retain,
}


def evaluate_all(metrics: dict[str, SubsystemMetrics]) -> list[SubsystemHealthResult]:
    """Evaluate health for all 7 subsystems.

    Args:
        metrics: dict mapping subsystem name to its metrics.
                 Missing subsystems default to UNKNOWN status.
    """
    results = []
    for name in SUBSYSTEM_NAMES:
        if name in metrics:
            evaluator = _EVALUATORS[name]
            results.append(evaluator(metrics[name]))
        else:
            results.append(SubsystemHealthResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                triggers=["No metrics available"],
            ))
    return results


def health_summary_slack(results: list[SubsystemHealthResult]) -> str:
    """Format subsystem health as a Slack message."""
    lines = ["*7-Subsystem Health*"]
    for r in results:
        emoji = {"healthy": "🟢", "needs_attention": "🟡", "unknown": "⚪"}.get(r.status.value, "⚪")
        trigger_text = r.triggers[0] if r.triggers else ""
        lines.append(f"{emoji} *{r.name}*: {r.status.value} — {trigger_text}")
    return "\n".join(lines)


def health_to_orb_inputs(results: list[SubsystemHealthResult]):
    """Convert health results to orb state machine inputs."""
    from lib.orb_state_machine import SubsystemHealth
    return [
        SubsystemHealth(
            name=r.name,
            status="needs_attention" if r.status == HealthStatus.NEEDS_ATTENTION else r.status.value,
        )
        for r in results
    ]
