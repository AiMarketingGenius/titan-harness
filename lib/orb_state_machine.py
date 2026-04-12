#!/usr/bin/env python3
"""
lib/orb_state_machine.py
MP-3 §3E — Atlas Voice Orb Color State Machine

Computes the orb's color/pulse state from:
  - 7 subsystem health flags (from MP-4 health JSONL)
  - Active incidents (P0/P1/P2)
  - Pending Hard Limit approvals (count + age)
  - Tier 1/2 service degradation + restart storms

States (ordered by severity):
  GREEN  — all healthy, no incidents, ≤1 approval pending <12h
  YELLOW — subsystem needs attention, no P0/P1, 2-3 approvals <24h
  ORANGE — active P1, approval >24h blocking, restart storm
  RED    — P0 active, Hard Limit violation, multiple P1s

Rule: orb state = max severity across all inputs. MP-4 can pull up, never down.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class OrbColor(IntEnum):
    """Ordered by severity — max() gives the worst state."""
    GREEN = 0
    YELLOW = 1
    ORANGE = 2
    RED = 3


@dataclass
class OrbState:
    color: OrbColor
    pulse: str  # "slow", "medium", "fast"
    drivers: list[str]  # human-readable reasons for this state

    @property
    def css_color(self) -> str:
        return {
            OrbColor.GREEN: "#22c55e",
            OrbColor.YELLOW: "#eab308",
            OrbColor.ORANGE: "#f97316",
            OrbColor.RED: "#ef4444",
        }[self.color]

    @property
    def label(self) -> str:
        return self.color.name.lower()


@dataclass
class SubsystemHealth:
    name: str
    status: str  # "healthy", "degraded", "dead", "needs_attention", "unknown"


@dataclass
class Incident:
    severity: str  # "P0", "P1", "P2"
    subsystem: str
    description: str = ""


@dataclass
class PendingApproval:
    packet_id: str
    age_hours: float
    risk: str  # "low", "medium", "high"


@dataclass
class ServiceRestart:
    service: str
    restart_count: int
    window_seconds: int = 300
    is_storm: bool = False  # True if ≥5 restarts in window


def compute_orb_state(
    subsystems: list[SubsystemHealth],
    incidents: list[Incident],
    approvals: list[PendingApproval],
    restarts: list[ServiceRestart] | None = None,
    hard_limit_violation: bool = False,
) -> OrbState:
    """Compute the orb color/pulse from current system state.

    Returns the max severity across all inputs per MP-3 §3E.
    """
    severity = OrbColor.GREEN
    drivers: list[str] = []

    # --- RED conditions ---

    # P0 active
    p0s = [i for i in incidents if i.severity == "P0"]
    if p0s:
        severity = max(severity, OrbColor.RED)
        drivers.append(f"P0 incident: {p0s[0].subsystem} — {p0s[0].description}")

    # Hard Limit violation
    if hard_limit_violation:
        severity = max(severity, OrbColor.RED)
        drivers.append("Hard Limit violation detected")

    # Multiple P1s spanning different subsystems
    p1s = [i for i in incidents if i.severity == "P1"]
    p1_subsystems = set(i.subsystem for i in p1s)
    if len(p1_subsystems) >= 2:
        severity = max(severity, OrbColor.RED)
        drivers.append(f"Multiple P1s across {len(p1_subsystems)} subsystems")

    # --- ORANGE conditions ---

    # Active P1 (single)
    if p1s and severity < OrbColor.RED:
        severity = max(severity, OrbColor.ORANGE)
        drivers.append(f"Active P1: {p1s[0].subsystem}")

    # Approval >24h blocking work
    stale_approvals = [a for a in approvals if a.age_hours >= 24]
    if stale_approvals:
        severity = max(severity, OrbColor.ORANGE)
        drivers.append(f"{len(stale_approvals)} approval(s) >24h blocking work")

    # Restart storm
    storms = [r for r in (restarts or []) if r.is_storm]
    if storms:
        severity = max(severity, OrbColor.ORANGE)
        drivers.append(f"Restart storm: {storms[0].service}")

    # --- YELLOW conditions ---

    # Subsystem needs attention (no P0/P1)
    needs_attention = [s for s in subsystems if s.status in ("needs_attention", "degraded")]
    if needs_attention and severity < OrbColor.ORANGE:
        severity = max(severity, OrbColor.YELLOW)
        drivers.append(f"Subsystem needs attention: {', '.join(s.name for s in needs_attention)}")

    # 2-3 approvals pending, none >24h
    non_stale_approvals = [a for a in approvals if a.age_hours < 24]
    if 2 <= len(non_stale_approvals) <= 3 and severity < OrbColor.ORANGE:
        severity = max(severity, OrbColor.YELLOW)
        drivers.append(f"{len(non_stale_approvals)} approvals pending (<24h)")

    # Tier 2 degraded <1h (any degraded subsystem counts)
    degraded_short = [s for s in subsystems if s.status == "degraded"]
    if degraded_short and severity < OrbColor.ORANGE:
        severity = max(severity, OrbColor.YELLOW)
        drivers.append(f"Degraded: {', '.join(s.name for s in degraded_short)}")

    # --- GREEN (default) ---
    if severity == OrbColor.GREEN:
        drivers.append("All systems healthy")

    # Determine pulse
    pulse = {
        OrbColor.GREEN: "slow",
        OrbColor.YELLOW: "slow",
        OrbColor.ORANGE: "medium",
        OrbColor.RED: "fast",
    }[severity]

    return OrbState(color=severity, pulse=pulse, drivers=drivers)


def orb_state_to_slack(state: OrbState) -> str:
    """Format orb state as a concise Slack message."""
    emoji = {
        OrbColor.GREEN: "🟢",
        OrbColor.YELLOW: "🟡",
        OrbColor.ORANGE: "🟠",
        OrbColor.RED: "🔴",
    }[state.color]

    drivers_text = "\n".join(f"  • {d}" for d in state.drivers)
    return f"{emoji} Orb: *{state.label.upper()}* (pulse: {state.pulse})\n{drivers_text}"


def orb_state_to_json(state: OrbState) -> dict:
    """Serialize orb state for API/dashboard consumption."""
    return {
        "color": state.label,
        "css_color": state.css_color,
        "pulse": state.pulse,
        "drivers": state.drivers,
        "severity": state.color.value,
    }
