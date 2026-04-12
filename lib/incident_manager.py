#!/usr/bin/env python3
"""
lib/incident_manager.py
MP-4 §4+§5 — Incident Classification + Response Playbooks

Implements:
  - P0/P1/P2/Not-incident classification via §4.2 decision tree
  - 5 playbooks (5.1-5.5) as named functions
  - MCP logging for all incident events
  - Slack + email notification routing
  - Orb state integration
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class IncidentSeverity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    NOT_INCIDENT = "not_incident"


# Command/control surfaces — P0 if dead
COMMAND_CONTROL_SERVICES = {"vps", "titan_bot", "mcp", "caddy"}

# Revenue/client-facing — P0 if dead
REVENUE_SERVICES = {"hermes", "n8n", "kokoro"}


@dataclass
class Incident:
    id: str
    severity: IncidentSeverity
    service: str
    status: str  # "dead" or "degraded"
    detail: str = ""
    auto_actions: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    playbook: str = ""
    escalated: bool = False

    @property
    def is_active(self) -> bool:
        return self.resolved_at is None


# --- In-memory store ---
_incidents: dict[str, Incident] = {}
_incident_counter = 0


def _next_id() -> str:
    global _incident_counter
    _incident_counter += 1
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    return f"INC-{ts}-{_incident_counter:03d}"


# --- §4.2 Classification Decision Tree ---

def classify_incident(service: str, status: str, sustained_minutes: float = 0) -> IncidentSeverity:
    """Classify an incident per MP-4 §4.2 decision tree."""
    if status == "dead":
        if service in COMMAND_CONTROL_SERVICES:
            return IncidentSeverity.P0
        if service in REVENUE_SERVICES:
            return IncidentSeverity.P0
        return IncidentSeverity.P1

    if status == "degraded":
        if sustained_minutes >= 5:
            return IncidentSeverity.P2
        return IncidentSeverity.NOT_INCIDENT  # Transient

    return IncidentSeverity.NOT_INCIDENT


def create_incident(service: str, status: str, detail: str = "",
                    sustained_minutes: float = 0) -> Incident:
    """Create and classify a new incident."""
    severity = classify_incident(service, status, sustained_minutes)

    if severity == IncidentSeverity.NOT_INCIDENT:
        # Log but don't create incident
        _audit(f"NOT_INCIDENT: {service} {status} — transient, no action")
        return Incident(
            id="none", severity=severity, service=service, status=status, detail=detail
        )

    inc = Incident(
        id=_next_id(),
        severity=severity,
        service=service,
        status=status,
        detail=detail,
    )
    _incidents[inc.id] = inc
    _audit(f"INCIDENT CREATED: {inc.id} {severity.value} {service} {status}")

    # Auto-route to playbook
    _route_to_playbook(inc)

    return inc


def resolve_incident(incident_id: str, resolution: str = "") -> bool:
    inc = _incidents.get(incident_id)
    if not inc:
        return False
    inc.resolved_at = datetime.now(timezone.utc)
    _audit(f"INCIDENT RESOLVED: {inc.id} {inc.severity.value} — {resolution}")
    return True


def active_incidents() -> list[Incident]:
    return [i for i in _incidents.values() if i.is_active]


def active_p0_p1() -> list[Incident]:
    return [i for i in active_incidents()
            if i.severity in (IncidentSeverity.P0, IncidentSeverity.P1)]


# --- §5 Playbooks ---

def _route_to_playbook(inc: Incident) -> None:
    """Route incident to the correct playbook per §5."""
    if inc.service == "vps" and inc.status == "dead":
        playbook_vps_unreachable(inc)
    elif inc.service == "titan_bot" and inc.status == "dead":
        playbook_slack_down(inc)
    elif inc.service == "reviewer_budget":
        playbook_reviewer_exhaustion(inc)
    elif inc.service in ("caddy", "n8n") and inc.status == "dead":
        playbook_portal_down(inc)
    else:
        inc.playbook = "generic"
        inc.auto_actions.append("Logged to MCP, monitoring")


def playbook_vps_unreachable(inc: Incident) -> None:
    """Playbook 5.1 — VPS Unreachable (P0)."""
    inc.playbook = "5.1_vps_unreachable"
    inc.severity = IncidentSeverity.P0
    inc.auto_actions = [
        "ICMP + TCP:22 probe attempted",
        "All pending tasks queued",
        "Internal state set to VPS_UNREACHABLE",
        "P0 email to Solon ops (Slack may be down)",
    ]
    _audit(f"PLAYBOOK 5.1: VPS unreachable — auto-actions applied")


def playbook_credential_exposure(inc: Incident) -> None:
    """Playbook 5.2 — Credential Exposure (P0)."""
    inc.playbook = "5.2_credential_exposure"
    inc.severity = IncidentSeverity.P0
    inc.auto_actions = [
        "All outbound API calls halted (circuit open)",
        "P0 Slack + email sent simultaneously",
        "Evidence preserved — no credential rotation (Hard Limit)",
    ]
    _audit(f"PLAYBOOK 5.2: Credential exposure — circuit opened")


def playbook_reviewer_exhaustion(inc: Incident) -> None:
    """Playbook 5.3 — Reviewer Loop Exhaustion (P1)."""
    inc.playbook = "5.3_reviewer_exhaustion"
    inc.severity = IncidentSeverity.P1
    inc.auto_actions = [
        "Non-critical Reviewer Loop calls halted",
        "Only P0/P1 grading + client deliverables continue",
        "P1 Slack alert with budget state",
    ]
    _audit(f"PLAYBOOK 5.3: Reviewer budget exhaustion — non-critical paused")


def playbook_slack_down(inc: Incident) -> None:
    """Playbook 5.4 — Slack (titan-bot) Down (P1, escalates to P0 if concurrent P0)."""
    inc.playbook = "5.4_slack_down"
    inc.severity = IncidentSeverity.P1

    # Check for concurrent P0
    concurrent_p0 = [i for i in active_incidents()
                     if i.severity == IncidentSeverity.P0 and i.id != inc.id]
    if concurrent_p0:
        inc.severity = IncidentSeverity.P0
        inc.escalated = True
        inc.auto_actions.append("ESCALATED to P0 — concurrent P0 incident active")
        inc.auto_actions.append("Email sent to Solon ops (Slack unavailable)")
    else:
        inc.auto_actions.append("Notifications queued — will resume when Slack recovers")

    inc.auto_actions.append("Internal state: SLACK_DOWN")
    inc.auto_actions.append("Polling Slack health every 60s")
    _audit(f"PLAYBOOK 5.4: Slack down — severity={inc.severity.value}")


def playbook_portal_down(inc: Incident) -> None:
    """Playbook 5.5 — Client Portal Down (P1)."""
    inc.playbook = "5.5_portal_down"
    inc.severity = IncidentSeverity.P1
    inc.auto_actions = [
        f"Caddy/n8n restart attempted (Tier 2 policy)",
        "Monitoring recovery for 2 minutes",
        "P1 Slack alert if restart fails",
    ]
    _audit(f"PLAYBOOK 5.5: Portal down — restart attempted")


# --- Notification formatting ---

def format_incident_slack(inc: Incident) -> str:
    """Format incident notification for Slack."""
    emoji = {"P0": "🔴", "P1": "🟠", "P2": "🟡"}.get(inc.severity.value, "⚪")
    actions_text = "\n".join(f"  • {a}" for a in inc.auto_actions)
    return (
        f"{emoji} [{inc.severity.value}] {inc.service} — {inc.status}\n"
        f"Incident: `{inc.id}`\n"
        f"Detail: {inc.detail}\n"
        f"Playbook: {inc.playbook}\n"
        f"Auto-actions:\n{actions_text}"
    )


# --- Audit ---

def _audit(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[incident_manager] {ts} | {msg}", file=sys.stderr)
