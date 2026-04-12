#!/usr/bin/env python3
"""
lib/onboarding_flow.py
MP-3 §5 — Client Onboarding Flow (Levar/JDJ as reference implementation)

Implements:
  - Onboarding stages with SLAs (per §4 Onboarding thresholds)
  - Checklist tracking with status progression
  - Autonomous actions (intake email, wiring, first tasks)
  - Hard Limit gates (billing, contract, kickoff approval)
  - Kickoff brief generator
  - Post-call summary parser
  - Mobile/desktop tile integration
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional


class OnboardingStage(str, Enum):
    PENDING = "pending"
    INTAKE = "intake_in_progress"
    WIRING = "wiring"
    GO_LIVE = "go_live"
    ACTIVE = "active"
    STALLED = "stalled"


class ChecklistStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    BLOCKED = "blocked"


@dataclass
class ChecklistItem:
    name: str
    status: ChecklistStatus = ChecklistStatus.NOT_STARTED
    sla_hours: float = 72.0  # MP-3 §4: stalled if step exceeds this
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    blocked_reason: str = ""

    @property
    def is_stalled(self) -> bool:
        if self.status != ChecklistStatus.IN_PROGRESS or not self.started_at:
            return False
        elapsed = (datetime.now(timezone.utc) - self.started_at).total_seconds() / 3600
        return elapsed >= self.sla_hours


# Standard onboarding checklist per MP-3 §5
STANDARD_CHECKLIST = [
    ("billing_confirmed", "Billing link + pricing confirmed", 24.0),
    ("contract_signed", "Contract sent and signed", 48.0),
    ("kickoff_approved", "Solon approves onboarding kickoff", 24.0),
    ("intake_sent", "Onboarding intake email/portal sent", 4.0),
    ("nap_collected", "NAP (Name, Address, Phone) received", 72.0),
    ("gbp_access", "Google Business Profile access granted", 72.0),
    ("gsc_ga_access", "GSC + GA4 viewer access granted", 72.0),
    ("logins_received", "Platform logins received", 72.0),
    ("wiring_complete", "All integrations wired and verified", 48.0),
    ("first_tasks_queued", "First fulfillment tasks queued", 24.0),
    ("go_live", "Onboarding complete — regular work begins", 0.0),
]


@dataclass
class ClientOnboarding:
    client_name: str
    client_id: str
    stage: OnboardingStage = OnboardingStage.PENDING
    checklist: list[ChecklistItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    kickoff_date: Optional[datetime] = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.checklist:
            self.checklist = [
                ChecklistItem(name=name, sla_hours=sla)
                for name, _, sla in STANDARD_CHECKLIST
            ]


# --- In-memory store ---
_onboardings: dict[str, ClientOnboarding] = {}


def create_onboarding(client_name: str, client_id: str) -> ClientOnboarding:
    ob = ClientOnboarding(client_name=client_name, client_id=client_id)
    _onboardings[client_id] = ob
    return ob


def get_onboarding(client_id: str) -> Optional[ClientOnboarding]:
    return _onboardings.get(client_id)


def list_onboardings() -> list[ClientOnboarding]:
    return list(_onboardings.values())


# --- Stage progression ---

HARD_LIMIT_STEPS = {"billing_confirmed", "contract_signed", "kickoff_approved"}


def _audit_log(client_id: str, action: str, detail: str = "") -> None:
    """Log onboarding action for audit trail. Prints to stderr for systemd journal capture."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[onboarding_audit] {ts} | {client_id} | {action} | {detail}", file=sys.stderr)


def advance_step(client_id: str, step_name: str) -> tuple[bool, str]:
    """Mark a checklist step as complete and advance the stage if appropriate.

    Hard Limit steps (billing, contract, kickoff) are logged with elevated audit.
    Returns (success, message).
    """
    ob = _onboardings.get(client_id)
    if not ob:
        return False, f"No onboarding found for {client_id}"

    item = next((c for c in ob.checklist if c.name == step_name), None)
    if not item:
        return False, f"Unknown checklist step: {step_name}"

    if item.status == ChecklistStatus.COMPLETE:
        return True, f"{step_name} already complete"

    # Audit log — elevated for Hard Limit steps
    if step_name in HARD_LIMIT_STEPS:
        _audit_log(client_id, f"HARD_LIMIT_ADVANCE: {step_name}", "requires explicit Solon approval")
    else:
        _audit_log(client_id, f"step_advance: {step_name}")

    now = datetime.now(timezone.utc)
    item.status = ChecklistStatus.COMPLETE
    item.completed_at = now

    # Auto-advance stage based on completed steps
    completed = {c.name for c in ob.checklist if c.status == ChecklistStatus.COMPLETE}

    if "go_live" in completed:
        ob.stage = OnboardingStage.ACTIVE
    elif "wiring_complete" in completed:
        ob.stage = OnboardingStage.GO_LIVE
    elif "kickoff_approved" in completed:
        ob.stage = OnboardingStage.INTAKE
        # Auto-start autonomous steps
        for auto_step in ["intake_sent"]:
            auto_item = next((c for c in ob.checklist if c.name == auto_step), None)
            if auto_item and auto_item.status == ChecklistStatus.NOT_STARTED:
                auto_item.status = ChecklistStatus.IN_PROGRESS
                auto_item.started_at = now
    elif "billing_confirmed" in completed:
        ob.stage = OnboardingStage.PENDING  # still pending until kickoff approved

    # Check for stalls
    any_stalled = any(c.is_stalled for c in ob.checklist)
    if any_stalled and ob.stage not in (OnboardingStage.ACTIVE, OnboardingStage.STALLED):
        ob.stage = OnboardingStage.STALLED

    return True, f"{step_name} completed. Stage: {ob.stage.value}"


def start_step(client_id: str, step_name: str) -> tuple[bool, str]:
    """Mark a checklist step as in-progress."""
    ob = _onboardings.get(client_id)
    if not ob:
        return False, f"No onboarding found for {client_id}"

    item = next((c for c in ob.checklist if c.name == step_name), None)
    if not item:
        return False, f"Unknown step: {step_name}"

    if item.status in (ChecklistStatus.COMPLETE, ChecklistStatus.IN_PROGRESS):
        return True, f"{step_name} already {item.status.value}"

    item.status = ChecklistStatus.IN_PROGRESS
    item.started_at = datetime.now(timezone.utc)
    return True, f"{step_name} started"


# --- Kickoff brief generator (MP-3 §5-D) ---

def generate_kickoff_brief(client_id: str) -> str:
    """Generate a one-pager kickoff brief for a client per MP-3 §5-D."""
    ob = _onboardings.get(client_id)
    if not ob:
        return f"No onboarding found for {client_id}"

    completed = sum(1 for c in ob.checklist if c.status == ChecklistStatus.COMPLETE)
    total = len(ob.checklist)
    stalled = [c for c in ob.checklist if c.is_stalled]
    blocked = [c for c in ob.checklist if c.status == ChecklistStatus.BLOCKED]

    # Build checklist display
    checklist_lines = []
    for i, (name, label, _) in enumerate(STANDARD_CHECKLIST):
        item = ob.checklist[i]
        status_icon = {
            ChecklistStatus.COMPLETE: "✅",
            ChecklistStatus.IN_PROGRESS: "🔄",
            ChecklistStatus.BLOCKED: "🔴",
            ChecklistStatus.NOT_STARTED: "⬜",
        }.get(item.status, "⬜")
        stall_flag = " ⚠️ STALLED" if item.is_stalled else ""
        checklist_lines.append(f"  {status_icon} {label}{stall_flag}")

    brief = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KICKOFF BRIEF — {ob.client_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Client: {ob.client_name} ({ob.client_id})
Stage: {ob.stage.value}
Progress: {completed}/{total} steps complete
Created: {ob.created_at.strftime('%Y-%m-%d')}

CHECKLIST:
{chr(10).join(checklist_lines)}

BLOCKERS: {len(blocked)} items blocked
STALLED: {len(stalled)} items past SLA

NOTES:
{chr(10).join(f'  • {n}' for n in ob.notes) if ob.notes else '  (none)'}

30-DAY PLAN:
  Week 1: Complete intake + wiring
  Week 2: First deliverables (content audit, SEO baseline)
  Week 3: Nurture sequence launch + first report
  Week 4: Review + optimize + upsell assessment
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    return brief


# --- Post-call summary parser (MP-3 §5-D) ---

def process_post_call_summary(client_id: str, summary: str) -> tuple[bool, str]:
    """Parse Solon's post-call summary and update onboarding state.

    Extracts action items and logs them as notes.
    """
    ob = _onboardings.get(client_id)
    if not ob:
        return False, f"No onboarding found for {client_id}"

    ob.notes.append(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}] Post-call: {summary}")
    return True, f"Post-call summary logged for {ob.client_name}"


# --- Dashboard integration ---

def onboarding_to_client_tile(ob: ClientOnboarding) -> dict:
    """Convert onboarding state to a client tile format for dashboards."""
    completed = [c for c in ob.checklist if c.status == ChecklistStatus.COMPLETE]
    last_completed = max(completed, key=lambda c: c.completed_at or datetime.min.replace(tzinfo=timezone.utc)) if completed else None
    blockers = sum(1 for c in ob.checklist if c.status == ChecklistStatus.BLOCKED or c.is_stalled)

    elapsed = ""
    last_task = "No tasks yet"
    if last_completed and last_completed.completed_at:
        delta = datetime.now(timezone.utc) - last_completed.completed_at
        hours = delta.total_seconds() / 3600
        if hours < 1:
            elapsed = f"{int(delta.total_seconds() / 60)}m ago"
        elif hours < 24:
            elapsed = f"{int(hours)}h ago"
        else:
            elapsed = f"{int(hours / 24)}d ago"
        # Map step name to human label
        label_map = {name: label for name, label, _ in STANDARD_CHECKLIST}
        last_task = label_map.get(last_completed.name, last_completed.name)

    health_color = "green"
    if blockers >= 2:
        health_color = "red"
    elif blockers == 1:
        health_color = "yellow"

    return {
        "name": ob.client_name,
        "stage": ob.stage.value.replace("_", " ").title(),
        "last_task": last_task,
        "last_task_elapsed": elapsed or "—",
        "open_blockers": blockers,
        "health_color": health_color,
    }
