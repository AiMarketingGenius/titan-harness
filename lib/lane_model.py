#!/usr/bin/env python3
"""
lib/lane_model.py
MP-4 §7 — Multi-Lane Infrastructure Doctrine

7 lanes, each with primary/secondary. Auto-switch on degradation.
All switches logged to MCP.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class LanePosition(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class SwitchType(str, Enum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"  # Requires Solon approval (e.g., payment lane)


@dataclass
class Lane:
    name: str
    primary_provider: str
    secondary_provider: str
    position: LanePosition = LanePosition.PRIMARY
    switch_type: SwitchType = SwitchType.AUTOMATIC
    last_switch_at: str | None = None
    switch_reason: str = ""


# --- Canonical 7 lanes per §7 ---

LANES: dict[str, Lane] = {
    "llm": Lane("llm", "Anthropic API (direct)", "AWS Bedrock (Claude)"),
    "memory": Lane("memory", "MCP (memory.aimarketinggenius.io)", "Supabase direct reads"),
    "file_storage": Lane("file_storage", "VPS NVMe (/data)", "Cloudflare R2"),
    "comms": Lane("comms", "Slack (titan-bot)", "Email (ops inbox)"),
    "payment": Lane("payment", "PayPal", "PaymentCloud + Durango (Phase 2 cutover)", switch_type=SwitchType.MANUAL),
    "version_control": Lane("version_control", "GitHub", "VPS local mirror (/data/git-mirror)"),
}

# Health service → lane mapping
SERVICE_TO_LANE: dict[str, str] = {
    "mcp": "memory",
    "titan_bot": "comms",
    "caddy": "comms",
    "vps_disk": "file_storage",
    "r2": "file_storage",
    "supabase": "memory",
    "kokoro": "llm",
    "hermes": "llm",
}


def get_lane_state() -> dict[str, dict]:
    """Return current state of all lanes for dashboard/API."""
    return {
        name: {
            "name": lane.name,
            "position": lane.position.value,
            "primary": lane.primary_provider,
            "secondary": lane.secondary_provider,
            "switch_type": lane.switch_type.value,
            "last_switch": lane.last_switch_at,
            "reason": lane.switch_reason,
        }
        for name, lane in LANES.items()
    }


def switch_lane(lane_name: str, to_position: LanePosition, reason: str) -> tuple[bool, str]:
    """Switch a lane to primary or secondary.

    Returns (success, message). Manual lanes (payment) return False unless override=True.
    """
    lane = LANES.get(lane_name)
    if not lane:
        return False, f"Unknown lane: {lane_name}"

    if lane.switch_type == SwitchType.MANUAL and to_position == LanePosition.SECONDARY:
        return False, f"Lane {lane_name} requires Solon approval for switch (Hard Limit)"

    old = lane.position
    lane.position = to_position
    lane.last_switch_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lane.switch_reason = reason

    direction = f"{old.value}_to_{to_position.value}"
    _audit_switch(lane_name, direction, reason)

    return True, f"Lane {lane_name}: {direction} — {reason}"


def check_lane_health(service: str, status: str) -> str | None:
    """Check if a health status change should trigger a lane switch.

    Returns the lane name if a switch should happen, None otherwise.
    """
    lane_name = SERVICE_TO_LANE.get(service)
    if not lane_name:
        return None

    lane = LANES.get(lane_name)
    if not lane:
        return None

    if status in ("dead", "degraded") and lane.position == LanePosition.PRIMARY:
        return lane_name
    if status == "healthy" and lane.position == LanePosition.SECONDARY:
        return lane_name  # Signal to switch back

    return None


def auto_switch_on_health(service: str, status: str) -> tuple[bool, str]:
    """Auto-switch lane based on health status change. Returns (switched, message)."""
    lane_name = check_lane_health(service, status)
    if not lane_name:
        return False, "no lane switch needed"

    lane = LANES[lane_name]
    if status in ("dead", "degraded"):
        return switch_lane(lane_name, LanePosition.SECONDARY, f"{service} {status}")
    elif status == "healthy":
        return switch_lane(lane_name, LanePosition.PRIMARY, f"{service} recovered")

    return False, "no action"


def _audit_switch(lane: str, direction: str, reason: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {
        "decision_type": "lane_switch",
        "lane": lane,
        "direction": direction,
        "trigger": reason,
        "ts": ts,
    }
    print(f"[lane_model] {json.dumps(entry)}", file=sys.stderr)
