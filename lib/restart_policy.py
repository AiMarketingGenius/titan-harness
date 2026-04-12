#!/usr/bin/env python3
"""
lib/restart_policy.py
MP-4 §2 — Auto-Restart Policy + Restart Storm Protection

Implements:
  - 3 restart tiers per §2.1
  - Restart storm detection (≥5 restarts in 300s) per §2.2
  - Slack notification for Tier 2 + Tier 3 events
  - MCP logging for all restart events
  - systemd drop-in generator for restart-policy.conf
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class RestartTier(str, Enum):
    TIER_1 = "tier_1"  # Always restart, no notify
    TIER_2 = "tier_2"  # Restart + notify Solon
    TIER_3 = "tier_3"  # Alert only, no restart


# Tier assignments per MP-4 §2.1
SERVICE_TIERS: dict[str, RestartTier] = {
    "kokoro": RestartTier.TIER_1,
    "hermes": RestartTier.TIER_1,
    "titan_processor": RestartTier.TIER_1,
    "titan_bot": RestartTier.TIER_1,
    "n8n": RestartTier.TIER_1,
    "caddy": RestartTier.TIER_2,
    "mcp": RestartTier.TIER_2,
    "supabase": RestartTier.TIER_3,
    "r2": RestartTier.TIER_3,
    "anthropic_api": RestartTier.TIER_3,
    "vps_resources": RestartTier.TIER_3,
}

# Storm thresholds per §2.2
STORM_WINDOW_SECONDS = 300
STORM_BURST_LIMIT = 5


@dataclass
class RestartEvent:
    service: str
    tier: RestartTier
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attempt: int = 1
    storm_detected: bool = False


# Track restart timestamps per service for storm detection
_restart_history: dict[str, list[float]] = defaultdict(list)


def detect_storm(service: str) -> bool:
    """Check if a service is in a restart storm (≥5 restarts in 300s)."""
    now = time.monotonic()
    history = _restart_history[service]
    # Prune old entries
    history[:] = [t for t in history if now - t < STORM_WINDOW_SECONDS]
    return len(history) >= STORM_BURST_LIMIT


def record_restart(service: str) -> RestartEvent:
    """Record a restart attempt and check for storm."""
    tier = SERVICE_TIERS.get(service, RestartTier.TIER_3)
    now_mono = time.monotonic()
    _restart_history[service].append(now_mono)

    # Prune old entries
    history = _restart_history[service]
    history[:] = [t for t in history if now_mono - t < STORM_WINDOW_SECONDS]

    storm = len(history) >= STORM_BURST_LIMIT
    attempt = len(history)

    event = RestartEvent(
        service=service,
        tier=tier,
        attempt=attempt,
        storm_detected=storm,
    )

    # Log to stderr for systemd journal
    print(f"[restart_policy] {service}: tier={tier.value} attempt={attempt} storm={storm}",
          file=sys.stderr)

    return event


def should_notify(event: RestartEvent) -> bool:
    """Check if Solon should be notified per tier rules."""
    if event.tier == RestartTier.TIER_1 and not event.storm_detected:
        return False  # Tier 1: transparent unless storm
    return True  # Tier 2, 3, or storm on any tier


def should_restart(service: str) -> tuple[bool, str]:
    """Check if systemd should attempt restart.

    Returns (should_restart, reason).
    """
    tier = SERVICE_TIERS.get(service, RestartTier.TIER_3)

    if tier == RestartTier.TIER_3:
        return False, f"Tier 3: {service} is external/infra, alert only"

    if detect_storm(service):
        return False, f"RESTART STORM: {service} has ≥{STORM_BURST_LIMIT} restarts in {STORM_WINDOW_SECONDS}s — manual approval required"

    return True, f"Tier {tier.value[-1]}: auto-restart permitted"


def format_slack_notification(event: RestartEvent) -> str:
    """Format Slack notification for restart events."""
    if event.storm_detected:
        return (
            f"🔴 RESTART STORM: `{event.service}` — {event.attempt} restarts in "
            f"{STORM_WINDOW_SECONDS}s\n"
            f"systemd has stopped restart attempts. Manual approval required.\n"
            f"Escalating to P1/P0."
        )
    if event.tier == RestartTier.TIER_2:
        return (
            f"⚠️ Service restarted: `{event.service}` (Tier 2 — restart + notify)\n"
            f"Attempt #{event.attempt}. Monitoring recovery."
        )
    if event.tier == RestartTier.TIER_3:
        return (
            f"🔴 Service issue: `{event.service}` (Tier 3 — alert only, no auto-restart)\n"
            f"External/infra service. Manual investigation required."
        )
    # Tier 1 storm
    return (
        f"⚠️ `{event.service}` restart storm detected. "
        f"{event.attempt} attempts in {STORM_WINDOW_SECONDS}s."
    )


def generate_systemd_dropin(service: str) -> str:
    """Generate systemd drop-in content for restart policy per §2.2."""
    tier = SERVICE_TIERS.get(service, RestartTier.TIER_3)

    if tier == RestartTier.TIER_3:
        return "# Tier 3: no restart directive (external/infra)\n"

    restart_sec = "5s" if tier == RestartTier.TIER_1 else "10s"

    return f"""# MP-4 §2 Auto-Restart Policy — {service} ({tier.value})
# Generated by lib/restart_policy.py

[Unit]
StartLimitIntervalSec={STORM_WINDOW_SECONDS}
StartLimitBurst={STORM_BURST_LIMIT}

[Service]
Restart=on-failure
RestartSec={restart_sec}
"""


def reset_storm_history(service: str | None = None) -> None:
    """Reset restart history (for testing or after manual intervention)."""
    if service:
        _restart_history[service].clear()
    else:
        _restart_history.clear()
