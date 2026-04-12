#!/usr/bin/env python3
"""
lib/reviewer_loop_budget.py
MP-3 §7 — Reviewer Loop Budget Protection + Batching

Implements:
  - $5/mo budget tracking, 5 calls/day limit
  - 4-hour batching window for low-impact changes
  - Immediate submission for high-impact client-facing changes
  - Slack announcements for review runs + results
  - Non-A/A- results treated as approval items
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional


class ReviewImpact(str, Enum):
    HIGH = "high"      # Client-facing, never batched, immediate
    LOW = "low"        # Internal, batchable within 4h window


class ReviewResult(str, Enum):
    PASS = "pass"       # A or A-
    NEEDS_APPROVAL = "needs_approval"  # Below A- or has risk tags
    PENDING = "pending"


@dataclass
class ReviewItem:
    id: str
    description: str
    impact: ReviewImpact
    flow_type: str  # voice_script, outbound_template, content, reporting_template
    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: Optional[datetime] = None
    result: ReviewResult = ReviewResult.PENDING
    grade: str = ""
    risk_tags: list[str] = field(default_factory=list)
    cost_cents: int = 0
    batch_id: Optional[str] = None


@dataclass
class BudgetState:
    monthly_spend_cents: int = 0
    monthly_limit_cents: int = 500  # $5.00
    daily_calls: int = 0
    daily_limit: int = 5
    last_reset_date: str = ""  # YYYY-MM-DD for daily reset
    last_month_reset: str = ""  # YYYY-MM for monthly reset

    @property
    def monthly_spend_dollars(self) -> float:
        return self.monthly_spend_cents / 100

    @property
    def monthly_remaining_cents(self) -> int:
        return max(0, self.monthly_limit_cents - self.monthly_spend_cents)

    @property
    def daily_remaining(self) -> int:
        return max(0, self.daily_limit - self.daily_calls)

    @property
    def can_call(self) -> bool:
        return self.daily_remaining > 0 and self.monthly_remaining_cents > 0


# --- Global state ---

_budget = BudgetState()
_batch_queue: list[ReviewItem] = []
_history: list[ReviewItem] = []

# Batch window: 4 hours per MP-3 §7-C
BATCH_WINDOW_HOURS = 4

# Exempt flows (MP-3 §7-B)
EXEMPT_FLOWS = {"read_only", "internal_logging", "monitoring", "health_logic"}

# Flows requiring review (MP-3 §7-A)
REVIEW_REQUIRED_FLOWS = {"voice_script", "outbound_template", "content", "reporting_template"}


def _reset_daily_if_needed() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _budget.last_reset_date != today:
        _budget.daily_calls = 0
        _budget.last_reset_date = today


def _reset_monthly_if_needed() -> None:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    if _budget.last_month_reset != month:
        _budget.monthly_spend_cents = 0
        _budget.last_month_reset = month


def get_budget() -> dict:
    """Return current budget state as a dict for dashboard display."""
    _reset_daily_if_needed()
    _reset_monthly_if_needed()
    return {
        "monthly_spend": f"${_budget.monthly_spend_dollars:.2f}",
        "monthly_limit": f"${_budget.monthly_limit_cents / 100:.2f}",
        "monthly_pct": round(_budget.monthly_spend_cents / _budget.monthly_limit_cents * 100, 1) if _budget.monthly_limit_cents else 0,
        "daily_calls": _budget.daily_calls,
        "daily_limit": _budget.daily_limit,
        "daily_pct": round(_budget.daily_calls / _budget.daily_limit * 100, 1) if _budget.daily_limit else 0,
        "can_call": _budget.can_call,
        "batch_queue_size": len(_batch_queue),
    }


def should_review(flow_type: str) -> bool:
    """Check if a flow type requires Reviewer Loop per MP-3 §7-A/B."""
    return flow_type in REVIEW_REQUIRED_FLOWS


def queue_review(
    item_id: str,
    description: str,
    flow_type: str,
    impact: ReviewImpact = ReviewImpact.LOW,
) -> tuple[str, str]:
    """Queue a review item. High-impact items are flagged for immediate submission.

    Returns (action, message) where action is "queued", "immediate", or "exempt".
    """
    if flow_type in EXEMPT_FLOWS:
        return "exempt", f"{flow_type} is exempt from Reviewer Loop"

    item = ReviewItem(
        id=item_id,
        description=description,
        impact=impact,
        flow_type=flow_type,
    )

    if impact == ReviewImpact.HIGH:
        # High-impact: never batch, submit immediately
        return "immediate", f"HIGH-IMPACT: {description} — submit to Reviewer Loop immediately"

    # Low-impact: add to batch queue
    _batch_queue.append(item)
    return "queued", f"Queued for batch: {description} (batch window: {BATCH_WINDOW_HOURS}h)"


def get_batch_ready() -> list[ReviewItem]:
    """Return items in the batch queue that are past the 4h window or if there's a high-impact trigger."""
    if not _batch_queue:
        return []

    now = datetime.now(timezone.utc)
    oldest = min(item.queued_at for item in _batch_queue)
    elapsed = (now - oldest).total_seconds() / 3600

    if elapsed >= BATCH_WINDOW_HOURS:
        # Window expired — submit entire batch
        batch = list(_batch_queue)
        return batch

    return []


def flush_batch() -> list[ReviewItem]:
    """Force-flush the batch queue (used when no new items arrive within window)."""
    batch = list(_batch_queue)
    _batch_queue.clear()
    return batch


def record_result(item: ReviewItem, grade: str, risk_tags: list[str], cost_cents: int) -> ReviewResult:
    """Record the result of a Reviewer Loop call and update budget."""
    _reset_daily_if_needed()
    _reset_monthly_if_needed()

    item.grade = grade
    item.cost_cents = cost_cents
    item.submitted_at = datetime.now(timezone.utc)

    # Determine result
    is_pass = grade.upper() in ("A", "A-", "A+")
    has_risk = len(risk_tags) > 0
    item.risk_tags = risk_tags

    if is_pass and not has_risk:
        item.result = ReviewResult.PASS
    else:
        item.result = ReviewResult.NEEDS_APPROVAL

    # Update budget
    _budget.daily_calls += 1
    _budget.monthly_spend_cents += cost_cents
    _history.append(item)

    # Remove from batch queue if present
    _batch_queue[:] = [q for q in _batch_queue if q.id != item.id]

    return item.result


def format_slack_announcement(item: ReviewItem, call_number: int) -> str:
    """Format Slack announcement per MP-3 §7-D."""
    return (
        f"🔍 Reviewer Loop running for *{item.description}*\n"
        f"Cost: ~${item.cost_cents / 100:.2f} | Call #{call_number} today | "
        f"Budget: ${_budget.monthly_spend_dollars:.2f}/${_budget.monthly_limit_cents / 100:.2f}"
    )


def format_slack_result(item: ReviewItem) -> str:
    """Format Reviewer Loop result per MP-3 §7-D."""
    grade_emoji = "✅" if item.result == ReviewResult.PASS else "⚠️"
    risk_text = f" | Risk tags: {', '.join(item.risk_tags)}" if item.risk_tags else ""
    action = "Auto-applied" if item.result == ReviewResult.PASS else "REQUIRES APPROVAL"
    return (
        f"{grade_emoji} Reviewer Loop result: *{item.grade}*{risk_text}\n"
        f"Flow: {item.description} | Action: {action}"
    )
